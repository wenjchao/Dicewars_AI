"""Test MapLayout schema validation and serialization."""

import json
import pytest
from pathlib import Path

from dicewars.api.types import MapLayout, TerritoryLayout, Position, BorderSegment


def get_small_map() -> dict:
    """Load small test map fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "small_map.json"
    with open(fixture_path, 'r') as f:
        return json.load(f)


def test_map_layout_from_json():
    """Test MapLayout can be constructed from JSON fixture."""
    map_data = get_small_map()
    
    # Convert JSON to MapLayout
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
    
    # Basic validation
    assert map_layout.map_name == "test_6_territories"
    assert len(map_layout.territories) == 6
    assert map_layout.dimensions.x == 4
    assert map_layout.dimensions.y == 3


def test_map_layout_validates_contiguous_territory_ids():
    """Test that MapLayout enforces contiguous territory IDs."""
    map_data = get_small_map()
    
    # Break contiguity by removing territory 2
    territories = {}
    for tid_str, t_data in map_data["territories"].items():
        tid = int(tid_str)
        if tid != 2:  # Skip territory 2
            territories[tid] = TerritoryLayout(
                id=t_data["id"],
                name=t_data["name"], 
                tiles=[Position(x=tile["x"], y=tile["y"]) for tile in t_data["tiles"]],
                adjacencies=t_data["adjacencies"],
                border=[]
            )
    
    with pytest.raises(ValueError, match="Territory IDs must be contiguous"):
        MapLayout(
            map_name="broken",
            dimensions=Position(x=4, y=3),
            territories=territories,
            grid_lookup=map_data["grid_lookup"]
        )


def test_map_layout_validates_grid_dimensions():
    """Test that MapLayout validates grid dimensions match."""
    map_data = get_small_map()
    
    # Break dimensions
    with pytest.raises(ValueError, match="Grid height mismatch"):
        MapLayout(
            map_name="broken",
            dimensions=Position(x=4, y=99),  # Wrong height
            territories={},
            grid_lookup=map_data["grid_lookup"]
        )


def test_schema_validates_small_map():
    """Test that JSON schema validates the small map fixture."""
    import jsonschema
    
    schema_path = Path(__file__).parent.parent.parent / "src" / "dicewars" / "transport" / "json" / "schema" / "map_layout.json"
    if not schema_path.exists() or schema_path.stat().st_size == 0:
        pytest.skip("Schema not implemented yet")
    
    with open(schema_path, 'r') as f:
        schema = json.load(f)
    
    map_data = get_small_map()
    
    # Should not raise ValidationError
    jsonschema.validate(map_data, schema)


def test_territory_adjacency_consistency():
    """Test that adjacency is symmetric in small map."""
    map_data = get_small_map()
    territories = map_data["territories"]
    
    for tid_str, territory in territories.items():
        tid = int(tid_str)
        for adj_id in territory["adjacencies"]:
            # Check reverse adjacency exists
            adj_territory = territories[str(adj_id)]
            assert tid in adj_territory["adjacencies"], \
                f"Adjacency not symmetric: {tid} -> {adj_id}"
        
        # Check no self-loops
        assert tid not in territory["adjacencies"], \
            f"Self-loop detected: {tid}"