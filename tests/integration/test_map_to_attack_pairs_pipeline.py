"""Integration test for complete map loading -> attack pairs pipeline."""

import json
import pytest
from pathlib import Path

from dicewars.api.types import MapLayout, TerritoryLayout, Position, BorderSegment
from dicewars.core.attack_pairs import AttackPairs
from dicewars.core.hash import layout_hash, HASHLESS_MODE


def test_small_map_complete_pipeline():
    """Test complete pipeline from JSON -> MapLayout -> AttackPairs -> hashes."""
    # Load fixture
    fixture_path = Path(__file__).parent.parent / "fixtures" / "small_map.json"
    with open(fixture_path, 'r') as f:
        map_data = json.load(f)
    
    # Parse to MapLayout
    territories = {}
    for tid_str, t_data in map_data["territories"].items():
        tid = int(tid_str)
        territories[tid] = TerritoryLayout(
            id=t_data["id"],
            name=t_data["name"],
            tiles=[Position(x=tile["x"], y=tile["y"]) for tile in t_data["tiles"]],
            adjacencies=t_data["adjacencies"],
            border=[BorderSegment(
                start=Position(x=seg["start"]["x"], y=seg["start"]["y"]),
                end=Position(x=seg["end"]["x"], y=seg["end"]["y"])
            ) for seg in t_data["border"]]
        )
    
    map_layout = MapLayout(
        map_name=map_data["map_name"],
        dimensions=Position(x=map_data["dimensions"]["x"], y=map_data["dimensions"]["y"]),
        territories=territories,
        grid_lookup=map_data["grid_lookup"]
    )
    
    # Generate AttackPairs
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    
    # Compute hashes
    map_hash = layout_hash(map_layout)
    
    # Validate results
    assert len(attack_pairs.pairs) > 0
    assert len(attack_pairs.index_map) == len(attack_pairs.pairs)
    
    if HASHLESS_MODE:
        assert map_hash == 0
        assert attack_pairs.hash64 == 0
    else:
        assert map_hash != 0
        assert attack_pairs.hash64 != 0
    
    # Validate attack pairs make sense for the map
    expected_num_pairs = sum(len(t.adjacencies) for t in map_layout.territories.values())
    assert len(attack_pairs.pairs) == expected_num_pairs


def test_attack_index_stability():
    """Test that attack indices are stable for RL compatibility."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "small_map.json"
    with open(fixture_path, 'r') as f:
        map_data = json.load(f)
    
    # Create same map multiple times
    def create_map_layout():
        territories = {}
        for tid_str, t_data in map_data["territories"].items():
            tid = int(tid_str)
            territories[tid] = TerritoryLayout(
                id=t_data["id"],
                name=t_data["name"],
                tiles=[Position(x=tile["x"], y=tile["y"]) for tile in t_data["tiles"]],
                adjacencies=t_data["adjacencies"],
                border=[BorderSegment(
                    start=Position(x=seg["start"]["x"], y=seg["start"]["y"]),
                    end=Position(x=seg["end"]["x"], y=seg["end"]["y"])
                ) for seg in t_data["border"]]
            )
        
        return MapLayout(
            map_name=map_data["map_name"],
            dimensions=Position(x=map_data["dimensions"]["x"], y=map_data["dimensions"]["y"]),
            territories=territories,
            grid_lookup=map_data["grid_lookup"]
        )
    
    # Generate attack pairs multiple times
    pairs1 = AttackPairs.from_map_layout(create_map_layout())
    pairs2 = AttackPairs.from_map_layout(create_map_layout())
    pairs3 = AttackPairs.from_map_layout(create_map_layout())
    
    # Indices must be identical (critical for RL)
    assert pairs1.pairs == pairs2.pairs == pairs3.pairs
    assert pairs1.index_map == pairs2.index_map == pairs3.index_map
    assert pairs1.hash64 == pairs2.hash64 == pairs3.hash64
    
    # Test specific attack index lookup
    if len(pairs1.pairs) > 0:
        first_pair = pairs1.pairs[0]
        index1 = pairs1.get_attack_index(first_pair[0], first_pair[1])
        index2 = pairs2.get_attack_index(first_pair[0], first_pair[1]) 
        index3 = pairs3.get_attack_index(first_pair[0], first_pair[1])
        
        assert index1 == index2 == index3 == 0  # First pair should have index 0