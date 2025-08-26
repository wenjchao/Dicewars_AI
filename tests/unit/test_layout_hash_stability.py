"""Test layout hash stability and canonicalization."""

import json
import pytest
from pathlib import Path

from dicewars.core.hash import layout_hash, HASHLESS_MODE
from dicewars.api.types import MapLayout, TerritoryLayout, Position, BorderSegment


def load_small_map_layout() -> MapLayout:
    """Load and convert small map to MapLayout."""
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


def test_layout_hash_deterministic():
    """Test that layout hash is deterministic across multiple calls."""
    map_layout = load_small_map_layout()
    
    hash1 = layout_hash(map_layout)
    hash2 = layout_hash(map_layout)
    hash3 = layout_hash(map_layout)
    
    assert hash1 == hash2 == hash3


def test_layout_hash_excludes_names():
    """Test that territory names don't affect layout hash (v5 spec)."""
    map_layout = load_small_map_layout()
    original_hash = layout_hash(map_layout)
    
    # Create identical map with different names
    modified_territories = {}
    for tid, territory in map_layout.territories.items():
        modified_territories[tid] = TerritoryLayout(
            id=territory.id,
            name=f"RENAMED_{territory.name}",  # Different name
            tiles=territory.tiles,
            adjacencies=territory.adjacencies,
            border=territory.border
        )
    
    modified_map = MapLayout(
        map_name="RENAMED_MAP",  # Different map name too
        dimensions=map_layout.dimensions,
        territories=modified_territories,
        grid_lookup=map_layout.grid_lookup
    )
    
    modified_hash = layout_hash(modified_map)
    
    if HASHLESS_MODE:
        assert original_hash == modified_hash == 0
    else:
        assert original_hash == modified_hash, "Names should not affect hash"


def test_layout_hash_sensitive_to_structure():
    """Test that layout hash changes when structure changes.""" 
    map_layout = load_small_map_layout()
    original_hash = layout_hash(map_layout)
    
    # Modify adjacency - should change hash
    modified_territories = {}
    for tid, territory in map_layout.territories.items():
        if tid == 0:
            # Remove one adjacency from territory 0
            modified_adjacencies = [adj for adj in territory.adjacencies if adj != 1]
            modified_territories[tid] = TerritoryLayout(
                id=territory.id,
                name=territory.name,
                tiles=territory.tiles,
                adjacencies=modified_adjacencies,
                border=territory.border
            )
        else:
            modified_territories[tid] = territory
    
    modified_map = MapLayout(
        map_name=map_layout.map_name,
        dimensions=map_layout.dimensions,
        territories=modified_territories,
        grid_lookup=map_layout.grid_lookup
    )
    
    modified_hash = layout_hash(modified_map)
    
    if HASHLESS_MODE:
        assert original_hash == modified_hash == 0
    else:
        assert original_hash != modified_hash, "Structural changes should affect hash"


@pytest.mark.skipif(HASHLESS_MODE, reason="Hash stability test requires real hashing")
def test_layout_hash_matches_golden_vector():
    """Test that layout hash matches expected value from test vectors."""
    map_layout = load_small_map_layout()
    computed_hash = layout_hash(map_layout)
    
    # Load expected hash from test vectors
    vectors_path = Path(__file__).parent.parent / "fixtures" / "hash_vectors.jsonl"
    if not vectors_path.exists():
        pytest.skip("Hash vectors not available")
    
    with open(vectors_path, 'r') as f:
        for line in f:
            vector = json.loads(line.strip())
            if vector.get("test_name") == "small_map_layout":
                expected_hash = int(vector["layout_hash"]) if vector["layout_hash"] != "0" else 0
                assert computed_hash == expected_hash
                return
    
    pytest.skip("No golden vector found for small_map_layout")