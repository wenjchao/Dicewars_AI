"""Property tests for adjacency graph invariants."""

import pytest
from hypothesis import given, strategies as st
from typing import Dict, List, Set

from dicewars.api.types import MapLayout, TerritoryLayout, Position, BorderSegment
from dicewars.core.attack_pairs import AttackPairs


def adjacency_list_strategy(num_territories: int) -> st.SearchStrategy[Dict[int, List[int]]]:
    """Generate random symmetric adjacency graphs."""
    
    @st.composite
    def _adjacency_graph(draw):
        adjacencies = {i: [] for i in range(num_territories)}
        
        # Generate random edges and ensure symmetry
        for i in range(num_territories):
            for j in range(i + 1, num_territories):
                # 30% chance of edge between i and j
                if draw(st.booleans()) and draw(st.random_module()).random() < 0.3:
                    adjacencies[i].append(j)
                    adjacencies[j].append(i)
        
        return adjacencies
    
    return _adjacency_graph()


def map_layout_from_adjacencies(adjacencies: Dict[int, List[int]]) -> MapLayout:
    """Create minimal MapLayout from adjacency data."""
    num_territories = len(adjacencies)
    
    territories = {}
    for tid, adj_list in adjacencies.items():
        territories[tid] = TerritoryLayout(
            id=tid,
            name=f"Territory_{tid}",
            tiles=[Position(x=tid, y=0)],  # Minimal tile placement
            adjacencies=adj_list,
            border=[]  # Minimal border
        )
    
    # Create minimal grid
    grid_width = max(4, num_territories)
    grid = [[-1] * grid_width for _ in range(2)]
    for tid in range(min(num_territories, grid_width)):
        grid[0][tid] = tid
    
    return MapLayout(
        map_name=f"test_{num_territories}_territories",
        dimensions=Position(x=grid_width, y=2),
        territories=territories,
        grid_lookup=grid
    )


@given(adjacency_list_strategy(6))
def test_adjacency_symmetry_property(adjacencies):
    """Property test: adjacency graphs must be symmetric."""
    # Verify input is symmetric
    for i, adj_list in adjacencies.items():
        for j in adj_list:
            assert i in adjacencies[j], f"Asymmetric edge: {i} -> {j}"
    
    map_layout = map_layout_from_adjacencies(adjacencies)
    
    # AttackPairs generation should not raise
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    
    # Validate invariants
    attack_pairs.validate_adjacency_invariants(map_layout)


@given(adjacency_list_strategy(4))
def test_no_self_loops_property(adjacencies):
    """Property test: adjacency graphs must have no self-loops."""
    # Ensure no self-loops in input
    for tid, adj_list in adjacencies.items():
        adjacencies[tid] = [adj for adj in adj_list if adj != tid]
    
    map_layout = map_layout_from_adjacencies(adjacencies)
    
    # Verify no self-loops in AttackPairs
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    for src, dst in attack_pairs.pairs:
        assert src != dst, f"Self-loop found: ({src}, {dst})"


@given(st.integers(min_value=3, max_value=8))
def test_attack_pairs_count_property(num_territories):
    """Property test: attack pairs count matches adjacency edges."""
    # Create a connected graph (ring topology for simplicity)
    adjacencies = {i: [] for i in range(num_territories)}
    for i in range(num_territories):
        next_i = (i + 1) % num_territories
        adjacencies[i].append(next_i)
        adjacencies[next_i].append(i)
    
    map_layout = map_layout_from_adjacencies(adjacencies)
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    
    # Count expected directed edges
    expected_edges = sum(len(adj_list) for adj_list in adjacencies.values())
    assert len(attack_pairs.pairs) == expected_edges


@given(adjacency_list_strategy(5))
def test_canonical_order_property(adjacencies):
    """Property test: pairs are always in canonical lexicographic order."""
    map_layout = map_layout_from_adjacencies(adjacencies)
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    
    # Verify lexicographic ordering
    for i in range(1, len(attack_pairs.pairs)):
        prev_pair = attack_pairs.pairs[i-1] 
        curr_pair = attack_pairs.pairs[i]
        assert prev_pair < curr_pair, f"Non-canonical order: {prev_pair} >= {curr_pair}"