"""Supply distribution strategies."""

import random
from typing import Dict, List
from ..api.types import SupplyDistribution, GameState, SupplyDescriptor, DistributeSupplyAction


class SupplyDistributor:
    """Handles different supply distribution strategies."""
    
    def __init__(self, config, state: GameState, supply: SupplyDescriptor, seed: int = None):
        self.config = config
        self.state = state
        self.supply = supply
        self.rng = random.Random(seed) if seed else random.Random()
    
    def distribute(self, strategy: SupplyDistribution = None) -> DistributeSupplyAction:
        """Distribute supply using specified strategy."""
        strategy = strategy or self.config.supply_distribution
        
        if strategy == SupplyDistribution.UNIFORM:
            return self._distribute_uniform()
        elif strategy == SupplyDistribution.RANDOM:
            return self._distribute_random()
        elif strategy == SupplyDistribution.BATTLEFRONT:
            return self._distribute_battlefront()
        elif strategy == SupplyDistribution.WEAKEST_FIRST:
            return self._distribute_weakest_first()
        elif strategy == SupplyDistribution.STRONGEST_FIRST:
            return self._distribute_strongest_first()
        else:
            # Default to uniform
            return self._distribute_uniform()
    
    def _distribute_uniform(self) -> DistributeSupplyAction:
        """Distribute supply evenly across all territories."""
        if not self.supply.territories_owned or self.supply.supply_remaining <= 0:
            return DistributeSupplyAction(placements={})
        
        placements = {}
        territories = self.supply.territories_owned
        supply_per_territory = self.supply.supply_remaining // len(territories)
        remainder = self.supply.supply_remaining % len(territories)
        
        for i, tid in enumerate(territories):
            amount = supply_per_territory + (1 if i < remainder else 0)
            if amount > 0:
                # Check max dice limit
                current_dice = self.state.dice[tid]
                max_additional = self.config.max_dice_per_territory - current_dice
                amount = min(amount, max_additional)
                if amount > 0:
                    placements[tid] = amount
        
        return DistributeSupplyAction(placements=placements)
    
    def _distribute_random(self) -> DistributeSupplyAction:
        """Distribute supply randomly across territories."""
        if not self.supply.territories_owned or self.supply.supply_remaining <= 0:
            return DistributeSupplyAction(placements={})
        
        placements = {}
        remaining = self.supply.supply_remaining
        territories = list(self.supply.territories_owned)
        
        while remaining > 0 and territories:
            # Pick random territory
            tid = self.rng.choice(territories)
            current_dice = self.state.dice[tid]
            
            if current_dice >= self.config.max_dice_per_territory:
                territories.remove(tid)
                continue
            
            # Place 1-3 dice randomly
            amount = min(self.rng.randint(1, 3), remaining, 
                        self.config.max_dice_per_territory - current_dice)
            
            if tid in placements:
                placements[tid] += amount
            else:
                placements[tid] = amount
            
            remaining -= amount
            
            # Update state tracking
            self.state.dice[tid] += amount
            if self.state.dice[tid] >= self.config.max_dice_per_territory:
                territories.remove(tid)
        
        # Reset state (we were just simulating)
        for tid, amount in placements.items():
            self.state.dice[tid] -= amount
        
        return DistributeSupplyAction(placements=placements)
    
    def _distribute_battlefront(self) -> DistributeSupplyAction:
        """Focus supply on territories adjacent to enemies."""
        if not self.supply.territories_owned or self.supply.supply_remaining <= 0:
            return DistributeSupplyAction(placements={})
        
        # Find battlefront territories (adjacent to enemy)
        battlefront = []
        for tid in self.supply.territories_owned:
            territory_layout = self.config.map_layout.territories.get(tid)
            if territory_layout:
                for neighbor_id in territory_layout.adjacencies:
                    if self.state.owners[neighbor_id] != self.supply.player_id:
                        battlefront.append(tid)
                        break
        
        if not battlefront:
            # No battlefront, fall back to uniform
            return self._distribute_uniform()
        
        # Distribute to battlefront territories
        placements = {}
        remaining = self.supply.supply_remaining
        
        # Sort by current dice (weakest first on battlefront)
        battlefront.sort(key=lambda t: self.state.dice[t])
        
        for tid in battlefront:
            if remaining <= 0:
                break
            
            current_dice = self.state.dice[tid]
            max_additional = self.config.max_dice_per_territory - current_dice
            amount = min(max(2, remaining // len(battlefront)), max_additional, remaining)
            
            if amount > 0:
                placements[tid] = amount
                remaining -= amount
        
        return DistributeSupplyAction(placements=placements)
    
    def _distribute_weakest_first(self) -> DistributeSupplyAction:
        """Prioritize territories with fewest dice."""
        if not self.supply.territories_owned or self.supply.supply_remaining <= 0:
            return DistributeSupplyAction(placements={})
        
        # Sort territories by dice count (ascending)
        sorted_territories = sorted(self.supply.territories_owned, 
                                  key=lambda t: self.state.dice[t])
        
        placements = {}
        remaining = self.supply.supply_remaining
        
        for tid in sorted_territories:
            if remaining <= 0:
                break
            
            current_dice = self.state.dice[tid]
            # Try to bring weak territories up to at least 3 dice
            target = max(3, current_dice + 1)
            amount = min(target - current_dice, remaining,
                        self.config.max_dice_per_territory - current_dice)
            
            if amount > 0:
                placements[tid] = amount
                remaining -= amount
        
        return DistributeSupplyAction(placements=placements)
    
    def _distribute_strongest_first(self) -> DistributeSupplyAction:
        """Prioritize territories with most dice (build strongholds)."""
        if not self.supply.territories_owned or self.supply.supply_remaining <= 0:
            return DistributeSupplyAction(placements={})
        
        # Sort territories by dice count (descending)
        sorted_territories = sorted(self.supply.territories_owned, 
                                  key=lambda t: self.state.dice[t], reverse=True)
        
        placements = {}
        remaining = self.supply.supply_remaining
        
        for tid in sorted_territories:
            if remaining <= 0:
                break
            
            current_dice = self.state.dice[tid]
            max_additional = self.config.max_dice_per_territory - current_dice
            
            # Try to max out strong territories
            amount = min(max_additional, remaining)
            
            if amount > 0:
                placements[tid] = amount
                remaining -= amount
        
        return DistributeSupplyAction(placements=placements)