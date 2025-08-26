"""Core game engine implementation."""

from typing import Union, List, Optional
from ..api.types import (
    GameConfig, Capabilities, TurnContext, ActionResult,
    AttackAction, EndTurnAction, DistributeSupplyAction,
    SupplyDescriptor, GamePhase
)
from ..api.engine import GameEngine
from .state import CoreState, create_initial_state
from .actions import ActionValidator, ActionExecutor
from .attack_pairs import AttackPairs


class DicewarsEngine(GameEngine):
    """Core Dicewars game engine implementation."""
    
    def __init__(self, config: GameConfig) -> None:
        """Initialize engine with configuration."""
        self.config = config
        self.state = create_initial_state(config, config.seed)
        self.validator = ActionValidator(self.state)
        self.executor = ActionExecutor(self.state)
    
    def get_capabilities(self) -> Capabilities:
        """Get engine capabilities."""
        from .hash import layout_hash
        # Compute action index hash from attack pairs
        attack_pairs_obj = AttackPairs.from_map_layout(self.config.map_layout)
        action_index_hash = attack_pairs_obj.hash64
        
        return Capabilities(
            rules_version="1.0",
            schema_version="5.0",
            map_name=self.config.map_layout.map_name,
            num_players=self.config.num_players,
            num_territories=len(self.config.map_layout.territories),
            layout_hash=str(layout_hash(self.config.map_layout)),
            action_index_hash=str(action_index_hash),
            winner_policy=self.config.winner_policy.value,
            winner_tiebreak_chain=[token.value for token in self.config.winner_tiebreak_chain],
            max_turns=self.config.max_turns,
            max_dice_per_territory=self.config.max_dice_per_territory,
            supports_delta=True,
            supports_penalties=True,
            uint64_encoding="decimal"
        )
    
    def get_turn_context(self) -> TurnContext:
        """Get current turn context (pure read), handling GAME_OVER (M7)."""
        
        if self.state.phase == GamePhase.GAME_OVER:
            # No valid actions after game over
            return TurnContext(
                game_state=self.state.to_public_state(),
                valid_actions=[],  # Empty - game is over
                supply=None,
                time_remaining_ms=0
            )
        
        # Generate valid actions for current player
        valid_actions = self._generate_valid_actions()
        
        # Generate supply descriptor if in supply phase
        supply = None
        if self.state.phase.value == "supply":
            supply = self._generate_supply_descriptor()
        
        return TurnContext(
            game_state=self.state.to_public_state(),
            valid_actions=valid_actions,
            supply=supply,
            time_remaining_ms=self.config.timeout_ms
        )
    
    def apply_action(
        self, 
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction]
    ) -> ActionResult:
        """Apply player action, rejecting actions after GAME_OVER (M7)."""
        
        if self.state.phase == GamePhase.GAME_OVER:
            return ActionResult(
                success=False,
                tick_id=str(self.state.tick_id),
                state_hash=self.state.get_state_hash(),
                position_hash=self.state.get_position_hash(),
                new_game_state=self.state.to_public_state(),
                battle_result=None,
                penalty_action=None,
                error_code="BAD_PHASE",
                error_data={"current_phase": "game_over", "message": "Game has ended"},
                delta=None
            )
        
        current_player = self.state.active_player_id
        
        # Validate action
        error_code = self.validator.validate_action(action, current_player)
        if error_code:
            return ActionResult(
                success=False,
                tick_id=str(self.state.tick_id),
                state_hash=self.state.get_state_hash(),
                position_hash=self.state.get_position_hash(),
                new_game_state=self.state.to_public_state(),
                battle_result=None,
                error_code=error_code,
                error_data={"action_type": action.type, "player_id": current_player},
                delta=None
            )
        
        # Execute valid action
        return self.executor.execute_action(action, current_player)
    
    def apply_penalty(self, reason: str, penalty_type: Optional[str] = None) -> ActionResult:
        """Apply penalty action based on reason and configured policy.
        
        Args:
            reason: Why the penalty is being applied ("timeout", "invalid_action", etc.)
            penalty_type: Override penalty type, or None to use configured policy
        """
        # If no penalty type specified, determine from configured policy
        if penalty_type is None:
            penalty_type = self._determine_penalty_type(reason)
        
        # NO_PENALTY means do nothing - return success with no state change
        if penalty_type == "no_penalty":
            return self._handle_no_penalty(reason)
        
        return self.executor.execute_penalty(reason, penalty_type)
    
    def _determine_penalty_type(self, reason: str) -> str:
        """Determine penalty type based on reason and configured policy."""
        from ..api.types import TimeoutPolicy
        
        # If NO_PENALTY policy is set, apply it to ALL penalty reasons
        if self.config.timeout_policy == TimeoutPolicy.NO_PENALTY:
            return "no_penalty"
        
        # Apply timeout policy for timeout-related reasons
        if reason in ["timeout", "client_error"]:
            if self.config.timeout_policy == TimeoutPolicy.AUTO_END_TURN:
                return "auto_end_turn"
            elif self.config.timeout_policy == TimeoutPolicy.SKIP_NEXT_TURN:
                return "skip_next_turn"
            elif self.config.timeout_policy == TimeoutPolicy.FORFEIT_GAME:
                return "forfeit_game"
        
        # For invalid_action and other reasons when not NO_PENALTY
        return "auto_end_turn"
    
    def _handle_no_penalty(self, reason: str) -> ActionResult:
        """Handle NO_PENALTY case - continue without any state change."""
        from ..api.types import StateDelta
        
        # No state change, just return success
        return ActionResult(
            success=True,
            tick_id=str(self.state.tick_id),
            state_hash=self.state.get_state_hash(),
            position_hash=self.state.get_position_hash(),
            new_game_state=self.state.to_public_state(),
            penalty_action=None,  # No penalty action taken
            battle_result=None,
            error_code=None,
            error_data={"reason": reason, "action": "no_penalty"},
            delta=StateDelta(changed_territories=[], new_owners=[], new_dice=[])
        )
    
    def _generate_valid_actions(self) -> List[Union[AttackAction, EndTurnAction, DistributeSupplyAction]]:
        """Generate all valid actions for current player."""
        actions = []
        current_player = self.state.active_player_id
        
        if self.state.phase.value == "attack":
            # Generate attack actions based on current game state
            attack_pairs_obj = AttackPairs.from_map_layout(self.config.map_layout)
            
            for i, (attacker_id, defender_id) in enumerate(attack_pairs_obj.pairs):
                # Only include valid attacks (owned by current player, sufficient dice, different owner)
                if (self.state.owners[attacker_id] == current_player and
                    self.state.dice[attacker_id] >= 2 and
                    self.state.owners[defender_id] != current_player):
                    
                    actions.append(AttackAction(
                        attacker_territory_id=attacker_id,
                        defender_territory_id=defender_id,
                        attack_index=i
                    ))
            
            # Always can end turn
            actions.append(EndTurnAction())
        
        elif self.state.phase.value == "supply":
            # During SUPPLY: only EndTurnAction available
            # Supply actions are not enumerated - player constructs them
            actions.append(EndTurnAction())
        
        else:
            # In other phases, just allow ending turn
            actions.append(EndTurnAction())
        
        return actions
    
    def _calculate_available_supply(self, player_id: int) -> int:
        """Calculate supply dice available for player this turn."""
        from .territory_utils import calculate_supply
        
        return calculate_supply(
            self.state.owners, 
            player_id, 
            self.config.map_layout,
            self.config.supply_calculation,
            self.config.fixed_supply_amount
        )
    
    def _get_player_region_info(self, player_id: int) -> tuple[int, list[set[int]]]:
        """Get connected region information for a player. Returns (largest_size, all_regions)."""
        owned = {i for i, owner in enumerate(self.state.owners) if owner == player_id}
        if not owned:
            return 0, []
        
        regions = []
        visited = set()
        
        for territory_id in owned:
            if territory_id not in visited:
                # BFS to find connected region
                region = set()
                queue = [territory_id]
                
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    
                    visited.add(current)
                    region.add(current)
                    
                    # Check neighbors
                    territory_layout = self.config.map_layout.territories.get(current)
                    if territory_layout:
                        for neighbor_id in territory_layout.adjacencies:
                            if neighbor_id in owned and neighbor_id not in visited:
                                queue.append(neighbor_id)
                
                regions.append(region)
        
        largest_size = max(len(region) for region in regions) if regions else 0
        return largest_size, regions
    
    def _get_largest_connected_region(self, player_id: int) -> int:
        """Get size of largest connected region for a player."""
        largest_size, _ = self._get_player_region_info(player_id)
        return largest_size
    
    def _get_connected_regions(self, player_id: int) -> list[set[int]]:
        """Get all connected regions owned by a player."""
        _, regions = self._get_player_region_info(player_id)
        return regions
    
    def _generate_supply_descriptor(self) -> SupplyDescriptor:
        """Generate supply descriptor for current player."""
        current_player = self.state.active_player_id
        
        # Count territories owned by player
        owned_territories = [i for i, owner in enumerate(self.state.owners) 
                           if owner == current_player]
        
        # Calculate available supply minus what's already used
        total_supply = self._calculate_available_supply(current_player)
        supply_remaining = total_supply - self.state.supply_used
        
        return SupplyDescriptor(
            player_id=current_player,
            supply_remaining=supply_remaining,
            can_end_early=self.config.supply_policy.value == "allow_early_end",
            territories_owned=owned_territories,
            max_dice_per_territory=self.config.max_dice_per_territory
        )