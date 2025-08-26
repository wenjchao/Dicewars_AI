"""RNG stream management for deterministic game execution."""

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class RNGStream:
    """Deterministic RNG with separate counters for different operations."""
    
    seed: int
    setup_counter: int = 0      # Map initialization, territory assignment
    turn_counter: int = 0       # Turn progression, phase changes
    battle_counter: int = 0     # Dice rolls during battles
    
    def get_battle_rng(self) -> random.Random:
        """Get RNG instance for battle resolution."""
        # Combine base seed with battle counter for determinism
        battle_seed = (self.seed ^ self.battle_counter) & 0xFFFFFFFF
        self.battle_counter += 1
        return random.Random(battle_seed)
    
    def get_setup_rng(self) -> random.Random:
        """Get RNG instance for initial setup operations."""
        setup_seed = (self.seed ^ (self.setup_counter << 16)) & 0xFFFFFFFF
        self.setup_counter += 1
        return random.Random(setup_seed)
    
    def get_turn_rng(self) -> random.Random:
        """Get RNG instance for turn progression operations."""
        turn_seed = (self.seed ^ (self.turn_counter << 8)) & 0xFFFFFFFF
        self.turn_counter += 1
        return random.Random(turn_seed)
    
    def clone(self) -> 'RNGStream':
        """Create a copy of this RNG stream."""
        return RNGStream(
            seed=self.seed,
            setup_counter=self.setup_counter,
            turn_counter=self.turn_counter,
            battle_counter=self.battle_counter
        )


def create_rng_stream(seed: int = None) -> RNGStream:
    """Create a new RNG stream with optional seed."""
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    return RNGStream(seed=seed)