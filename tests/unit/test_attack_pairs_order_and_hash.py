"""Test AttackPairs canonical ordering and hash computation."""

import json
import pytest
from pathlib import Path

from dicewars.core.attack_pairs import AttackPairs
from dicewars.core.hash import HASHLESS_MODE


def load_small_map_layout():
    """Load small map MapLayout for testing."""
    from pathlib import Path
    from dicewars.api.types import MapLayout, TerritoryLayout, Position, BorderSegment
    
    fixture_path = Path(__file__).parent.parent / "fixtures" / "small_map.json"
    with open(fixture_path, 'r') as f:
        map_data = json.load(f)
    
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


def test_attack_pairs_canonical_order():
    """Test that attack pairs are generated in canonical lexicographic order."""
    map_layout = load_small_map_layout()
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    
    # Verify ordering is lexicographic
    for i in range(1, len(attack_pairs.pairs)):
        prev_pair = attack_pairs.pairs[i-1]
        curr_pair = attack_pairs.pairs[i]
        assert prev_pair < curr_pair, f"Pairs not in order: {prev_pair} >= {curr_pair}"


def test_attack_pairs_match_expected():
    """Test that generated pairs match expected from test vectors."""
    map_layout = load_small_map_layout()
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    
    # Load expected pairs from test vectors
    vectors_path = Path(__file__).parent.parent / "fixtures" / "hash_vectors.jsonl"
    if vectors_path.exists():
        with open(vectors_path, 'r') as f:
            for line in f:
                vector = json.loads(line.strip())
                if vector.get("test_name") == "attack_pairs_canonical_order":
                    expected_pairs = [tuple(pair) for pair in vector["expected_pairs"]]
                    assert attack_pairs.pairs == expected_pairs
                    return
    
    # Fallback: verify manually for small test map
    # Based on small_map.json adjacencies
    expected_pairs = [
        (0, 1), (0, 2),  # Territory 0 -> {1, 2}
        (1, 0), (1, 2), (1, 3),  # Territory 1 -> {0, 2, 3} 
        (2, 0), (2, 1), (2, 4), (2, 5),  # Territory 2 -> {0, 1, 4, 5}
        (3, 1), (3, 4),  # Territory 3 -> {1, 4}
        (4, 2), (4, 3), (4, 5),  # Territory 4 -> {2, 3, 5}
        (5, 2), (5, 4)   # Territory 5 -> {2, 4}
    ]
    
    assert attack_pairs.pairs == expected_pairs


def test_attack_pairs_index_map_consistency():
    """Test that index_map provides correct indices."""
    map_layout = load_small_map_layout()
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    
    for expected_index, pair in enumerate(attack_pairs.pairs):
        actual_index = attack_pairs.index_map[pair]
        assert actual_index == expected_index, \
            f"Index mismatch for {pair}: expected {expected_index}, got {actual_index}"


def test_get_attack_index():
    """Test get_attack_index method."""
    map_layout = load_small_map_layout()
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    
    # Test valid attack
    index = attack_pairs.get_attack_index(0, 1)
    assert isinstance(index, int)
    assert index >= 0
    
    # Test invalid attack
    with pytest.raises(ValueError, match="Invalid attack pair"):
        attack_pairs.get_attack_index(0, 5)  # Not adjacent


def test_adjacency_validation():
    """Test that adjacency invariants are enforced."""
    map_layout = load_small_map_layout()
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    
    # Should not raise
    attack_pairs.validate_adjacency_invariants(map_layout)


def test_attack_pairs_hash_deterministic():
    """Test that attack pairs hash is deterministic."""
    map_layout = load_small_map_layout()
    
    pairs1 = AttackPairs.from_map_layout(map_layout)
    pairs2 = AttackPairs.from_map_layout(map_layout)
    
    assert pairs1.hash64 == pairs2.hash64


@pytest.mark.skipif(HASHLESS_MODE, reason="Hash stability test requires real hashing")
def test_attack_pairs_hash_stability():
    """Test attack pairs hash for stability across calls."""
    map_layout = load_small_map_layout()
    attack_pairs = AttackPairs.from_map_layout(map_layout)
    
    # Hash should be non-zero and consistent
    assert attack_pairs.hash64 != 0
    
    # Multiple generations should produce same hash
    pairs2 = AttackPairs.from_map_layout(map_layout)
    assert attack_pairs.hash64 == pairs2.hash64