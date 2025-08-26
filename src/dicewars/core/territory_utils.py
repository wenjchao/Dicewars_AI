"""Territory analysis utilities."""

from typing import List, Set, Tuple
from ..api.types import MapLayout


def get_connected_regions(owners: List[int], player_id: int, map_layout: MapLayout) -> List[Set[int]]:
    """Get all connected regions owned by a player."""
    owned = {i for i, owner in enumerate(owners) if owner == player_id}
    if not owned:
        return []
    
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
                territory_layout = map_layout.territories.get(current)
                if territory_layout:
                    for neighbor_id in territory_layout.adjacencies:
                        if neighbor_id in owned and neighbor_id not in visited:
                            queue.append(neighbor_id)
            
            regions.append(region)
    
    return regions


def get_largest_connected_region_size(owners: List[int], player_id: int, map_layout: MapLayout) -> int:
    """Get size of largest connected region for a player."""
    regions = get_connected_regions(owners, player_id, map_layout)
    return max(len(region) for region in regions) if regions else 0


def calculate_supply(owners: List[int], player_id: int, map_layout: MapLayout, 
                    supply_calculation, fixed_amount: int = 5) -> int:
    """Calculate supply for a player based on the supply calculation method."""
    from ..api.types import SupplyCalculation
    
    if supply_calculation == SupplyCalculation.TOTAL_TERRITORIES:
        owned_territories = sum(1 for owner in owners if owner == player_id)
        return owned_territories
        
    elif supply_calculation == SupplyCalculation.LARGEST_CONNECTED:
        return get_largest_connected_region_size(owners, player_id, map_layout)
        
    elif supply_calculation == SupplyCalculation.FIXED_AMOUNT:
        return fixed_amount
        
    elif supply_calculation == SupplyCalculation.TERRITORIES_PLUS_BONUS:
        owned_territories = sum(1 for owner in owners if owner == player_id)
        regions = get_connected_regions(owners, player_id, map_layout)
        bonus = len([r for r in regions if len(r) >= 4])
        return owned_territories + bonus
    
    # Default to total territories
    owned_territories = sum(1 for owner in owners if owner == player_id)
    return owned_territories