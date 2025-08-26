"""Action validation and execution."""

from typing import Union, Optional, Dict, Any
from ..api.types import (
    AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction,
    ActionResult, InvalidAction, GamePhase, StateDelta, BattleResult
)
from .state import CoreState


class ActionValidator:
    """Validates actions against game state."""
    
    def __init__(self, state: CoreState):
        self.state = state
    
    def validate_action(
        self, 
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction],
        player_id: int
    ) -> Optional[str]:
        """Validate action against current state. Returns error code or None if valid."""
        
        # Check if it's player's turn
        if player_id != self.state.active_player_id:
            return InvalidAction.NOT_YOUR_TURN.value
        
        # Check if player is eliminated
        if player_id in self.state.eliminated_players:
            return InvalidAction.NOT_YOUR_TURN.value
        
        # Check phase-specific validations
        if isinstance(action, AttackAction):
            return self._validate_attack(action, player_id)
        elif isinstance(action, EndTurnAction):
            return self._validate_end_turn(action, player_id)
        elif isinstance(action, DistributeSupplyAction):
            return self._validate_distribute_supply(action, player_id)
        
        return InvalidAction.UNKNOWN_ACTION_TYPE.value
    
    def _validate_attack(self, action: AttackAction, player_id: int) -> Optional[str]:
        """Validate attack action."""
        if self.state.phase != GamePhase.ATTACK:
            return InvalidAction.BAD_PHASE.value
        
        # Validate territory IDs
        if not self._is_valid_territory(action.attacker_territory_id):
            return InvalidAction.INVALID_TERRITORY.value
        if not self._is_valid_territory(action.defender_territory_id):
            return InvalidAction.INVALID_TERRITORY.value
        
        # Check ownership
        if self.state.owners[action.attacker_territory_id] != player_id:
            return InvalidAction.NOT_OWNED.value
        
        # Can't attack your own territory
        if self.state.owners[action.defender_territory_id] == player_id:
            return InvalidAction.INVALID_TERRITORY.value
        
        # Check adjacency
        if not self._are_adjacent(action.attacker_territory_id, action.defender_territory_id):
            return InvalidAction.NOT_ADJACENT.value
        
        # Check sufficient dice (need at least 2 to attack)
        if self.state.dice[action.attacker_territory_id] < 2:
            return InvalidAction.INSUFFICIENT_DICE.value
        
        return None
    
    def _validate_end_turn(self, action: EndTurnAction, player_id: int) -> Optional[str]:
        """Validate end turn action."""
        # EndTurn is always valid in M3 (can end turn from any phase)
        return None
    
    def _validate_distribute_supply(self, action: DistributeSupplyAction, player_id: int) -> Optional[str]:
        """Validate supply distribution action according to v5 rules."""
        if self.state.phase != GamePhase.SUPPLY:
            return InvalidAction.BAD_PHASE.value
        
        # v5: Reject if placements is empty
        if not action.placements:
            return InvalidAction.ZERO_PLACEMENT.value
        
        # v5: Reject zero or negative values
        for territory_id, dice_count in action.placements.items():
            if dice_count <= 0:
                return InvalidAction.ZERO_PLACEMENT.value
        
        # Check territory validity and ownership
        for territory_id, dice_count in action.placements.items():
            if not self._is_valid_territory(territory_id):
                return InvalidAction.INVALID_TERRITORY.value
            
            if self.state.owners[territory_id] != player_id:
                return InvalidAction.NOT_OWNED.value
            
            # Check max dice limit
            new_dice_count = self.state.dice[territory_id] + dice_count
            if new_dice_count > self.state.config.max_dice_per_territory:
                return InvalidAction.EXCEEDS_MAX_DICE.value
        
        # Calculate available supply using configured method
        from ..api.types import SupplyCalculation
        
        if self.state.config.supply_calculation == SupplyCalculation.TOTAL_TERRITORIES:
            owned_territories = sum(1 for owner in self.state.owners if owner == player_id)
            total_supply = owned_territories
        elif self.state.config.supply_calculation == SupplyCalculation.LARGEST_CONNECTED:
            from .territory_utils import get_largest_connected_region_size
            total_supply = get_largest_connected_region_size(
                self.state.owners, player_id, self.state.config.map_layout
            )
        elif self.state.config.supply_calculation == SupplyCalculation.FIXED_AMOUNT:
            total_supply = self.state.config.fixed_supply_amount
        elif self.state.config.supply_calculation == SupplyCalculation.TERRITORIES_PLUS_BONUS:
            owned_territories = sum(1 for owner in self.state.owners if owner == player_id)
            # Get connected regions
            from .territory_utils import get_connected_regions
            regions = get_connected_regions(self.state.owners, player_id, self.state.config.map_layout)
            bonus = len([r for r in regions if len(r) >= 4])  # +1 for each region with 4+ territories
            total_supply = owned_territories + bonus
        else:
            # Default to total territories
            owned_territories = sum(1 for owner in self.state.owners if owner == player_id)
            total_supply = owned_territories
            
        available_supply = total_supply - self.state.supply_used
        
        # Check if total requested exceeds available supply
        total_dice_to_place = sum(action.placements.values())
        if total_dice_to_place > available_supply:
            return InvalidAction.SUPPLY_EXHAUSTED.value
        
        return None
    
    def _is_valid_territory(self, territory_id: int) -> bool:
        """Check if territory ID is valid."""
        return 0 <= territory_id < len(self.state.owners)
    
    def _are_adjacent(self, territory1_id: int, territory2_id: int) -> bool:
        """Check if two territories are adjacent."""
        # Get territory layout from config
        territory1_layout = self.state.config.map_layout.territories.get(territory1_id)
        if not territory1_layout:
            return False
        
        return territory2_id in territory1_layout.adjacencies


class ActionExecutor:
    """Executes validated actions and produces results."""
    
    def __init__(self, state: CoreState):
        self.state = state
    
    def execute_action(
        self,
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction],
        player_id: int
    ) -> ActionResult:
        """Execute a validated action and return result."""
        
        # Create delta tracking what changed
        delta = StateDelta(
            changed_territories=[],
            new_owners=[],
            new_dice=[]
        )
        
        battle_result = None
        
        if isinstance(action, AttackAction):
            battle_result, delta = self._execute_attack(action, player_id)
        elif isinstance(action, EndTurnAction):
            delta = self._execute_end_turn(action, player_id)
        elif isinstance(action, DistributeSupplyAction):
            delta = self._execute_distribute_supply(action, player_id)
        
        # Advance tick
        self.state.advance_tick()
        
        # Check for game over
        self.state.check_game_over()
        
        return ActionResult(
            success=True,
            tick_id=str(self.state.tick_id),
            state_hash=self.state.get_state_hash(),
            position_hash=self.state.get_position_hash(),
            new_game_state=self.state.to_public_state(),
            battle_result=battle_result,
            error_code=None,
            error_data=None,
            delta=delta
        )
    
    def execute_penalty(self, reason: str, penalty_type: str) -> ActionResult:
        """Execute a penalty action (M6 implementation)."""
        from ..api.types import PenaltyAction
        
        # Create penalty action (v5: first-class action)
        penalty_action = PenaltyAction(
            penalty_type=penalty_type,
            reason=reason,
            target_player_id=self.state.active_player_id
        )
        
        delta = StateDelta(
            changed_territories=[],
            new_owners=[],
            new_dice=[]
        )
        
        if penalty_type == "auto_end_turn":
            # Handle AUTO_END_TURN penalty - end current player's turn immediately
            delta = self._handle_auto_end_turn_penalty()
            
        elif penalty_type == "skip_next_turn":
            # Handle SKIP_NEXT_TURN penalty - mark player for skip and advance turn
            delta = self._handle_skip_next_turn_penalty()
            
        elif penalty_type == "forfeit_game":
            # Handle FORFEIT_GAME penalty - eliminate player
            self.state.eliminate_player(self.state.active_player_id)
            self.state.advance_turn()
        
        # M6: Penalties advance tick by exactly 1, no RNG consumption
        self.state.advance_tick()
        
        # Check game over conditions
        self.state.check_game_over()
        
        return ActionResult(
            success=True,  # Penalties always succeed
            tick_id=str(self.state.tick_id),
            state_hash=self.state.get_state_hash(),
            position_hash=self.state.get_position_hash(),
            new_game_state=self.state.to_public_state(),
            penalty_action=penalty_action,  # v5: include penalty action
            battle_result=None,
            error_code=None,
            error_data={"penalty_reason": reason, "penalty_type": penalty_type},
            delta=delta
        )
    
    def _handle_auto_end_turn_penalty(self) -> StateDelta:
        """Handle AUTO_END_TURN penalty."""
        # Transition to SUPPLY if needed, otherwise advance turn
        if self.state.phase == GamePhase.ATTACK and self._should_enter_supply_phase(self.state.active_player_id):
            self.state.phase = GamePhase.SUPPLY
            self.state.supply_used = 0  # Reset supply tracking
        else:
            self.state.advance_turn()
            
        return StateDelta(
            changed_territories=[],
            new_owners=[],
            new_dice=[]
        )
    
    def _handle_skip_next_turn_penalty(self) -> StateDelta:
        """Handle SKIP_NEXT_TURN penalty."""
        # Add player to pending skip list
        self.state.pending_skips.add(self.state.active_player_id)
        
        # Immediately advance to next player
        self.state.advance_turn()
        
        return StateDelta(
            changed_territories=[],
            new_owners=[],
            new_dice=[]
        )
    
    def _execute_attack(self, action: AttackAction, player_id: int) -> tuple[BattleResult, StateDelta]:
        """Execute attack action with M4 battle resolution."""
        attacker_dice = self.state.dice[action.attacker_territory_id]
        defender_dice = self.state.dice[action.defender_territory_id]
        
        # Get RNG for battle resolution
        battle_rng = self.state.rng_stream.get_battle_rng()
        
        # Roll dice (attacker first for canonical ordering)
        attacker_rolls = [battle_rng.randint(1, 6) for _ in range(attacker_dice)]
        defender_rolls = [battle_rng.randint(1, 6) for _ in range(defender_dice)]
        
        # Calculate casualties using configured battle system
        attacker_casualties, defender_casualties = self._calculate_casualties(
            attacker_rolls, defender_rolls, attacker_dice, defender_dice
        )
        
        # Apply casualties
        new_attacker_dice = attacker_dice - attacker_casualties
        new_defender_dice = defender_dice - defender_casualties
        territory_conquered = (new_defender_dice == 0)
        
        # Update game state
        changed_territories = []
        new_owners = []
        new_dice = []
        
        if territory_conquered:
            # Conquest: attacker takes territory
            old_owner = self.state.owners[action.defender_territory_id]
            self.state.owners[action.defender_territory_id] = player_id
            
            # Handle dice distribution based on battle system
            from ..api.types import BattleSystem
            if self.state.config.battle_system == BattleSystem.SUMMATION_DICE_COMPARISON:
                # Summation: keep 1 in original, rest move to conquered territory
                self.state.dice[action.attacker_territory_id] = 1
                self.state.dice[action.defender_territory_id] = attacker_dice - 1
            else:
                # Individual: standard movement of 1 die
                self.state.dice[action.attacker_territory_id] = new_attacker_dice - 1
                self.state.dice[action.defender_territory_id] = 1
            
            # Check if defender is eliminated
            if old_owner >= 0 and not any(owner == old_owner for owner in self.state.owners):
                self.state.eliminate_player(old_owner)
            
            changed_territories = [action.attacker_territory_id, action.defender_territory_id]
            new_owners = [player_id, player_id]
            new_dice = [self.state.dice[action.attacker_territory_id], self.state.dice[action.defender_territory_id]]
            winner = "attacker"  # If territory conquered, attacker always won
        else:
            # No conquest: just apply casualties
            self.state.dice[action.attacker_territory_id] = new_attacker_dice
            self.state.dice[action.defender_territory_id] = new_defender_dice
            
            changed_territories = [action.attacker_territory_id, action.defender_territory_id]
            new_owners = [
                self.state.owners[action.attacker_territory_id],
                self.state.owners[action.defender_territory_id]
            ]
            new_dice = [new_attacker_dice, new_defender_dice]
            winner = "attacker" if attacker_casualties < defender_casualties else "defender"
        
        delta = StateDelta(
            changed_territories=changed_territories,
            new_owners=new_owners,
            new_dice=new_dice
        )
        
        battle_result = BattleResult(
            attacker_rolls=attacker_rolls,
            defender_rolls=defender_rolls,
            attacker_casualties=attacker_casualties,
            defender_casualties=defender_casualties,
            attack_pair_index=action.attack_index,
            territory_conquered=territory_conquered,
            winner=winner
        )
        
        return battle_result, delta
    
    def _calculate_casualties(self, attacker_rolls: list[int], defender_rolls: list[int], 
                            attacker_total: int, defender_total: int) -> tuple[int, int]:
        """Calculate casualties using configured battle system."""
        from ..api.types import BattleSystem
        
        if self.state.config.battle_system == BattleSystem.INDIVIDUAL_DICE_COMPARISON:
            return self._individual_dice_comparison(attacker_rolls, defender_rolls, attacker_total, defender_total)
        elif self.state.config.battle_system == BattleSystem.SUMMATION_DICE_COMPARISON:
            return self._summation_dice_comparison(attacker_rolls, defender_rolls, attacker_total, defender_total)
        else:
            # Default to individual dice comparison
            return self._individual_dice_comparison(attacker_rolls, defender_rolls, attacker_total, defender_total)
    
    def _individual_dice_comparison(self, attacker_rolls: list[int], defender_rolls: list[int], 
                                  attacker_total: int, defender_total: int) -> tuple[int, int]:
        """Calculate casualties using individual dice comparison with AUTO_ALL_BUT_ONE rules."""
        # Sort rolls descending for comparison
        att_sorted = sorted(attacker_rolls, reverse=True)
        def_sorted = sorted(defender_rolls, reverse=True)
        
        attacker_losses = 0
        defender_losses = 0
        
        # Compare pairs of highest dice
        for att_die, def_die in zip(att_sorted, def_sorted):
            if att_die > def_die:
                defender_losses += 1
            else:
                attacker_losses += 1
                
        # AUTO_ALL_BUT_ONE: attacker must keep 1 die
        max_attacker_losses = attacker_total - 1
        attacker_losses = min(attacker_losses, max_attacker_losses)
        
        # Defender can lose all dice (conquest)
        defender_losses = min(defender_losses, defender_total)
        
        return attacker_losses, defender_losses
    
    def _summation_dice_comparison(self, attacker_rolls: list[int], defender_rolls: list[int], 
                                 attacker_total: int, defender_total: int) -> tuple[int, int]:
        """Calculate casualties using summation comparison - winner takes all approach."""
        attacker_sum = sum(attacker_rolls)
        defender_sum = sum(defender_rolls)
        
        if attacker_sum > defender_sum:
            # Attacker wins: defender loses all dice, attacker loses nothing (will handle movement separately)
            attacker_losses = 0                   # No losses, just movement
            defender_losses = defender_total      # Defender loses all
        else:
            # Defender wins (includes ties): attacker loses all but 1, defender keeps all
            attacker_losses = attacker_total - 1  # Must keep 1 die in original territory  
            defender_losses = 0                   # Defender takes no losses
        
        return attacker_losses, defender_losses
    
    def _execute_end_turn(self, action: EndTurnAction, player_id: int) -> StateDelta:
        """Execute end turn action."""
        # Flexible phase transitions based on configuration
        if self.state.phase == GamePhase.ATTACK:
            # From ATTACK, handle supply distribution
            if self._should_enter_supply_phase(player_id):
                from ..api.types import SupplyDistribution
                
                if self.state.config.supply_distribution == SupplyDistribution.MANUAL:
                    # Manual distribution: transition to SUPPLY phase for user input
                    self.state.phase = GamePhase.SUPPLY
                    self.state.supply_used = 0  # Reset supply tracking
                    # Player will provide DistributeSupplyAction in next turn
                else:
                    # Automated distribution: handle internally without phase transition
                    self.state.supply_used = 0  # Reset supply tracking
                    supply_delta = self._auto_distribute_supply(player_id)
                    # After auto-distribution, advance turn immediately
                    self.state.supply_used = 0
                    self.state.advance_turn()
                    return supply_delta
            else:
                # No supply needed, advance to next player
                self.state.advance_turn()
        elif self.state.phase == GamePhase.SUPPLY:
            # From SUPPLY phase (only reached with MANUAL distribution)
            # Player has finished manual supply distribution, now decide next phase
            if self.state.config.allow_multiple_supply_phases and self._player_can_attack(player_id):
                # Go back to attack phase if player can still attack
                self.state.phase = GamePhase.ATTACK
            else:
                # Otherwise advance to next player
                self.state.supply_used = 0
                self.state.advance_turn()
        
        return StateDelta(
            changed_territories=[],
            new_owners=[],
            new_dice=[]
        )
    
    def _auto_distribute_supply(self, player_id: int) -> StateDelta:
        """Automatically distribute supply using configured strategy."""
        from ..api.types import SupplyDescriptor
        from .supply_distributor import SupplyDistributor
        
        # Create supply descriptor
        owned_territories = [i for i, owner in enumerate(self.state.owners) if owner == player_id]
        
        # Calculate available supply
        from ..api.types import SupplyCalculation
        if self.state.config.supply_calculation == SupplyCalculation.TOTAL_TERRITORIES:
            owned_territories_count = len(owned_territories)
            total_supply = owned_territories_count
        elif self.state.config.supply_calculation == SupplyCalculation.LARGEST_CONNECTED:
            from .territory_utils import get_largest_connected_region_size
            total_supply = get_largest_connected_region_size(
                self.state.owners, player_id, self.state.config.map_layout
            )
        elif self.state.config.supply_calculation == SupplyCalculation.FIXED_AMOUNT:
            total_supply = self.state.config.fixed_supply_amount
        elif self.state.config.supply_calculation == SupplyCalculation.TERRITORIES_PLUS_BONUS:
            from .territory_utils import get_connected_regions
            regions = get_connected_regions(self.state.owners, player_id, self.state.config.map_layout)
            bonus = len([r for r in regions if len(r) >= 4])
            total_supply = len(owned_territories) + bonus
        else:
            total_supply = len(owned_territories)
            
        supply_remaining = total_supply - self.state.supply_used
        
        if supply_remaining <= 0:
            return StateDelta(changed_territories=[], new_owners=[], new_dice=[])
        
        supply_descriptor = SupplyDescriptor(
            player_id=player_id,
            supply_remaining=supply_remaining,
            can_end_early=True,  # Always allow early end for auto-distribution
            territories_owned=owned_territories,
            max_dice_per_territory=self.state.config.max_dice_per_territory
        )
        
        # Create distributor and get action
        distributor = SupplyDistributor(
            self.state.config, 
            self.state.to_public_state(), 
            supply_descriptor, 
            seed=self.state.rng_stream.turn_counter + self.state.rng_stream.battle_counter
        )
        supply_action = distributor.distribute()
        
        # Apply the distribution
        changed_territories = []
        new_dice = []
        
        for territory_id, dice_to_add in supply_action.placements.items():
            if territory_id in owned_territories:
                old_dice = self.state.dice[territory_id]
                new_dice_count = min(old_dice + dice_to_add, self.state.config.max_dice_per_territory)
                self.state.dice[territory_id] = new_dice_count
                
                changed_territories.append(territory_id)
                new_dice.append(new_dice_count)
                
                # Track used supply
                self.state.supply_used += (new_dice_count - old_dice)
        
        return StateDelta(
            changed_territories=changed_territories,
            new_owners=[self.state.owners[t] for t in changed_territories],
            new_dice=new_dice
        )
    
    def _should_enter_supply_phase(self, player_id: int) -> bool:
        """Determine if player should enter SUPPLY after attacks."""
        from ..api.types import SupplyCalculation
        
        # Calculate available supply using configured method
        if self.state.config.supply_calculation == SupplyCalculation.TOTAL_TERRITORIES:
            owned_territories = sum(1 for owner in self.state.owners if owner == player_id)
            available_supply = owned_territories
        elif self.state.config.supply_calculation == SupplyCalculation.LARGEST_CONNECTED:
            from .territory_utils import get_largest_connected_region_size
            available_supply = get_largest_connected_region_size(
                self.state.owners, player_id, self.state.config.map_layout
            )
        elif self.state.config.supply_calculation == SupplyCalculation.FIXED_AMOUNT:
            available_supply = self.state.config.fixed_supply_amount
        else:
            # Default to total territories
            owned_territories = sum(1 for owner in self.state.owners if owner == player_id)
            available_supply = owned_territories
        
        # Enter supply if player has available supply and owns territories
        return available_supply > 0
    
    
    def _execute_distribute_supply(self, action: DistributeSupplyAction, player_id: int) -> StateDelta:
        """Execute supply distribution with deterministic micro-order."""
        # Sort placements by territory_id for deterministic order
        sorted_placements = sorted(action.placements.items())
        
        changed_territories = []
        new_owners = []
        new_dice = []
        
        # Place dice one at a time, advancing tick for each
        for territory_id, amount in sorted_placements:
            for _ in range(amount):
                self.state.dice[territory_id] += 1
                # Note: tick advance happens in execute_action after this returns
            
            # Track changes for delta
            changed_territories.append(territory_id)
            new_owners.append(self.state.owners[territory_id])
            new_dice.append(self.state.dice[territory_id])
        
        # Update supply used
        total_placed = sum(action.placements.values())
        self.state.supply_used += total_placed
        
        # Calculate remaining supply using configured method
        from ..api.types import SupplyCalculation
        
        if self.state.config.supply_calculation == SupplyCalculation.TOTAL_TERRITORIES:
            owned_territories = sum(1 for owner in self.state.owners if owner == player_id)
            available_supply = owned_territories
        elif self.state.config.supply_calculation == SupplyCalculation.LARGEST_CONNECTED:
            from .territory_utils import get_largest_connected_region_size
            available_supply = get_largest_connected_region_size(
                self.state.owners, player_id, self.state.config.map_layout
            )
        elif self.state.config.supply_calculation == SupplyCalculation.FIXED_AMOUNT:
            available_supply = self.state.config.fixed_supply_amount
        elif self.state.config.supply_calculation == SupplyCalculation.TERRITORIES_PLUS_BONUS:
            owned_territories = sum(1 for owner in self.state.owners if owner == player_id)
            from .territory_utils import get_connected_regions
            regions = get_connected_regions(self.state.owners, player_id, self.state.config.map_layout)
            bonus = len([r for r in regions if len(r) >= 4])
            available_supply = owned_territories + bonus
        else:
            owned_territories = sum(1 for owner in self.state.owners if owner == player_id)
            available_supply = owned_territories
            
        remaining_supply = available_supply - self.state.supply_used
        
        # Check if supply exhausted
        if remaining_supply == 0:
            # Supply exhausted - must transition
            if self.state.config.allow_multiple_supply_phases and self._player_can_attack(player_id):
                self.state.phase = GamePhase.ATTACK
                self.state.supply_used = 0  # Reset for potential next supply phase
            else:
                self.state.supply_used = 0  # Reset for next player
                self.state.advance_turn()
        # Otherwise, player can continue distributing or end turn early
        
        return StateDelta(
            changed_territories=changed_territories,
            new_owners=new_owners,
            new_dice=new_dice
        )
    
    def _player_can_attack(self, player_id: int) -> bool:
        """Check if player has any valid attacks available."""
        for i, owner in enumerate(self.state.owners):
            if owner == player_id and self.state.dice[i] >= 2:
                # Check if this territory can attack any neighbor
                territory_layout = self.state.config.map_layout.territories.get(i)
                if territory_layout:
                    for neighbor_id in territory_layout.adjacencies:
                        if self.state.owners[neighbor_id] != player_id:
                            return True
        return False