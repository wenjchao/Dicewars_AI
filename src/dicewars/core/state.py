"""Core game state management."""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from ..api.types import GamePhase, GameState, GameConfig, MapLayout
from .hash import state_hash, position_hash, layout_hash
from .rng import RNGStream, create_rng_stream


@dataclass
class CoreState:
    """Internal core game state."""
    
    # Board state
    owners: List[int]  # Territory owners (player_id or -1 for neutral)
    dice: List[int]  # Dice per territory
    
    # Game metadata  
    active_player_id: int
    phase: GamePhase
    turn_number: int
    tick_id: int
    
    # Configuration reference (required field)
    config: GameConfig = field(repr=False)
    
    # Optional fields with defaults
    eliminated_players: List[int] = field(default_factory=list)
    winner_id: Optional[int] = None
    
    # Supply tracking (for current turn)
    supply_used: int = 0
    
    # Penalty tracking (M6)
    pending_skips: set = field(default_factory=set)
    
    # RNG state
    rng_stream: RNGStream = field(default_factory=lambda: create_rng_stream())
    
    def to_public_state(self) -> GameState:
        """Convert to public API GameState."""
        return GameState(
            owners=self.owners.copy(),
            dice=self.dice.copy(),
            active_player_id=self.active_player_id,
            phase=self.phase,
            turn_number=self.turn_number,
            tick_id=str(self.tick_id),  # Convert to decimal string for v5
            winner_id=self.winner_id,
            eliminated_players=self.eliminated_players.copy()
        )
    
    def get_state_hash(self) -> str:
        """Get current state hash as decimal string."""
        return str(state_hash(
            owners=self.owners,
            dice=self.dice,
            active_player_id=self.active_player_id,
            phase=self.phase.value,
            turn_number=self.turn_number,
            winner_id=self.winner_id,
            tick_id=self.tick_id,
            rng_counters={
                "setup": self.rng_stream.setup_counter,
                "turn": self.rng_stream.turn_counter,
                "battle": self.rng_stream.battle_counter
            },
            layout_hash=layout_hash(self.config.map_layout),
            rules_version="1.0",
            schema_version="5.0",
            battle_system=self.config.battle_system.value,
            supply_policy=self.config.supply_policy.value,
            max_dice_per_territory=self.config.max_dice_per_territory
        ))
    
    def get_position_hash(self) -> str:
        """Get current position hash as decimal string."""
        return str(position_hash(
            owners=self.owners,
            dice=self.dice,
            active_player_id=self.active_player_id,
            phase=self.phase.value,
            turn_number=self.turn_number,
            winner_id=self.winner_id,
            layout_hash=layout_hash(self.config.map_layout),
            rules_version="1.0",
            schema_version="5.0",
            battle_system=self.config.battle_system.value,
            supply_policy=self.config.supply_policy.value,
            max_dice_per_territory=self.config.max_dice_per_territory
        ))
    
    def advance_tick(self) -> None:
        """Advance tick counter."""
        self.tick_id += 1
    
    def advance_turn(self) -> None:
        """Advance to next player's turn, handling skip penalties (M6)."""
        self.turn_number += 1
        
        # Find next active player, handling pending skips
        while True:
            # Move to next player
            self.active_player_id = (self.active_player_id + 1) % self.config.num_players
            
            # Skip eliminated players
            if self.active_player_id in self.eliminated_players:
                continue
                
            # Check for pending skip
            if self.active_player_id in self.pending_skips:
                # Skip this player's turn
                self.pending_skips.remove(self.active_player_id)
                # Continue to next player (no turn_start for skipped player)
                continue
                
            # Normal turn start
            self.phase = GamePhase.ATTACK
            break
    
    def eliminate_player(self, player_id: int) -> None:
        """Eliminate a player from the game."""
        if player_id not in self.eliminated_players:
            self.eliminated_players.append(player_id)
    
    def check_game_over(self) -> bool:
        """Check if game should end and update winner (M7)."""
        # Check elimination victory first
        if self.check_elimination_victory():
            return True
        
        # Check max-turns boundary
        if self.check_max_turns_boundary():
            return True
        
        return False
    
    def check_elimination_victory(self) -> bool:
        """Check for elimination victory (same mutation)."""
        active_players = self._get_active_players()
        
        if len(active_players) <= 1:
            # Elimination victory - set game over immediately
            self.phase = GamePhase.GAME_OVER
            
            # Determine winner using policy system
            from .winner import WinnerDeterminer
            winner_determiner = WinnerDeterminer(self, self.config)
            self.winner_id = winner_determiner.determine_winner()
            
            return True
        
        return False
    
    def check_max_turns_boundary(self) -> bool:
        """Check max-turns boundary with precedence over penalties (M7)."""
        if self.turn_number >= self.config.max_turns:
            # v5: Max-turns precedence - cancel pending penalties
            self.pending_skips.clear()
            
            # Set game over
            self.phase = GamePhase.GAME_OVER
            
            # Determine winner by policy
            from .winner import WinnerDeterminer
            winner_determiner = WinnerDeterminer(self, self.config)
            self.winner_id = winner_determiner.determine_winner()
            
            return True
        
        return False
    
    def _get_active_players(self) -> List[int]:
        """Get players who still own territories."""
        active = set()
        for owner in self.owners:
            if owner >= 0:  # Valid player ID (not -1 for neutral)
                active.add(owner)
        return list(active)


def create_initial_state(config: GameConfig, seed: Optional[int] = None) -> CoreState:
    """Create initial game state from configuration."""
    num_territories = len(config.map_layout.territories)
    
    # Initialize with all territories neutral (-1) and minimum dice
    owners = [-1] * num_territories
    dice = [config.initial_dice_per_territory] * num_territories
    
    # For M3, we'll implement proper territory assignment later
    # For now, just assign territories in order to players
    territories_per_player = num_territories // config.num_players
    for player_id in range(config.num_players):
        start_idx = player_id * territories_per_player
        end_idx = start_idx + territories_per_player
        if player_id == config.num_players - 1:  # Last player gets remainder
            end_idx = num_territories
        
        for i in range(start_idx, end_idx):
            owners[i] = player_id
    
    return CoreState(
        owners=owners,
        dice=dice,
        active_player_id=0,
        phase=GamePhase.ATTACK,  # Start in attack phase for M3 simplicity
        turn_number=1,
        tick_id=1,
        config=config,
        rng_stream=create_rng_stream(seed)
    )