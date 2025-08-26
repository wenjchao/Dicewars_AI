"""Property tests for grid lookup consistency."""

import pytest
from hypothesis import given, strategies as st, assume
from typing import List, Dict, Set

from dicewars.api.types import MapLayout, TerritoryLayout, Position, BorderSegment


@st.composite 
def valid_map_layout(draw, max_territories=6, max_dimension=8):
    """Generate valid MapLayout instances."""
    num_territories = draw(st.integers(min_value=2, max_value=max_territories))
    width = draw(st.integers(min_value=2, max_value=max_dimension))
    height = draw(st.integers(min_value=2, max_value=max_dimension))
    
    # Generate grid with some territories placed
    grid = [[-1] * width for _ in range(height)]
    territory_tiles = {i: [] for i in range(num_territories)}
    
    # Place each territory on at least one tile
    for tid in range(num_territories):
        x = draw(st.integers(min_value=0, max_value=width-1))
        y = draw(st.integers(min_value=0, max_value=height-1))
        
        if grid[y][x] == -1:  # Only if tile is free
            grid[y][x] = tid
            territory_tiles[tid].append(Position(x=x, y=y))
    
    # Randomly assign remaining tiles
    for y in range(height):
        for x in range(width):
            if grid[y][x] == -1 and draw(st.booleans()):
                tid = draw(st.integers(min_value=0, max_value=num_territories-1))
                grid[y][x] = tid
                territory_tiles[tid].append(Position(x=x, y=y))
    
    # Ensure each territory has at least one tile
    for tid in range(num_territories):
        if not territory_tiles[tid]:
            # Find a free tile or take one
            for y in range(height):
                for x in range(width):
                    if grid[y][x] == -1:
                        grid[y][x] = tid
                        territory_tiles[tid].append(Position(x=x, y=y))
                        break
                if territory_tiles[tid]:
                    break
            else:
                # No free tiles, take tile from territory 0 (if different)
                if tid != 0 and territory_tiles[0]:
                    pos = territory_tiles[0][0]
                    grid[pos.y][pos.x] = tid
                    territory_tiles[tid].append(pos)
                    territory_tiles[0].remove(pos)
    
    # Generate minimal adjacencies (connect adjacent grid neighbors)
    adjacencies = {i: set() for i in range(num_territories)}
    
    for y in range(height):
        for x in range(width):
            tid = grid[y][x]
            if tid == -1:
                continue
                
            # Check 4-connected neighbors
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    neighbor_tid = grid[ny][nx]
                    if neighbor_tid != -1 and neighbor_tid != tid:
                        adjacencies[tid].add(neighbor_tid)
                        adjacencies[neighbor_tid].add(tid)
    
    # Convert to lists
    for tid in adjacencies:
        adjacencies[tid] = list(adjacencies[tid])
    
    # Create territories
    territories = {}
    for tid in range(num_territories):
        territories[tid] = TerritoryLayout(
            id=tid,
            name=f"Territory_{tid}",
            tiles=territory_tiles[tid],
            adjacencies=adjacencies[tid],
            border=[]  # Simplified
        )
    
    return MapLayout(
        map_name=f"generated_{num_territories}",
        dimensions=Position(x=width, y=height),
        territories=territories,
        grid_lookup=grid
    )


@given(valid_map_layout())
def test_grid_lookup_references_valid_territories(map_layout):
    """Property test: all grid references point to valid territories."""
    valid_territory_ids = set(map_layout.territories.keys())
    
    for y, row in enumerate(map_layout.grid_lookup):
        for x, territory_id in enumerate(row):
            if territory_id != -1:
                assert territory_id in valid_territory_ids, \
                    f"Invalid territory_id {territory_id} at grid[{y}][{x}]"


@given(valid_map_layout())
def test_territory_tiles_match_grid_lookup(map_layout):
    """Property test: territory tiles match their grid lookup positions."""
    
    for territory_id, territory in map_layout.territories.items():
        # Collect all grid positions for this territory
        grid_positions = set()
        for y, row in enumerate(map_layout.grid_lookup):
            for x, tid in enumerate(row):
                if tid == territory_id:
                    grid_positions.add((x, y))
        
        # Compare with territory.tiles
        tile_positions = {(tile.x, tile.y) for tile in territory.tiles}
        
        assert grid_positions == tile_positions, \
            f"Territory {territory_id} tiles mismatch: grid={grid_positions}, tiles={tile_positions}"


@given(valid_map_layout())
def test_territory_ids_are_contiguous(map_layout):
    """Property test: territory IDs are contiguous 0..N-1."""
    territory_ids = set(map_layout.territories.keys())
    num_territories = len(territory_ids)
    expected_ids = set(range(num_territories))
    
    assert territory_ids == expected_ids, \
        f"Non-contiguous territory IDs: {territory_ids}"


@given(valid_map_layout())
def test_grid_dimensions_consistent(map_layout):
    """Property test: grid dimensions match declared dimensions."""
    assert len(map_layout.grid_lookup) == map_layout.dimensions.y, \
        f"Grid height {len(map_layout.grid_lookup)} != declared {map_layout.dimensions.y}"
    
    for y, row in enumerate(map_layout.grid_lookup):
        assert len(row) == map_layout.dimensions.x, \
            f"Grid row {y} width {len(row)} != declared {map_layout.dimensions.x}"


@given(valid_map_layout())
def test_no_territory_overlaps_in_tiles(map_layout):
    """Property test: no two territories claim the same tile position."""
    all_positions = []
    
    for territory_id, territory in map_layout.territories.items():
        for tile in territory.tiles:
            all_positions.append((tile.x, tile.y, territory_id))
    
    # Check for duplicates
    position_counts = {}
    for x, y, tid in all_positions:
        pos = (x, y)
        if pos in position_counts:
            pytest.fail(f"Position ({x}, {y}) claimed by both territory {position_counts[pos]} and {tid}")
        position_counts[pos] = tid