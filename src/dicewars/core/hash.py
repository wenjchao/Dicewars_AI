"""Canonical hashing implementation for deterministic state and layout hashes."""

import struct
from typing import List, Dict, Any, Optional

# Hashless profile: Set this to True to return 0 for all hashes
HASHLESS_MODE = True  # Using hashless mode for Phase 1

try:
    import xxhash
    _xxhash_available = True
except ImportError:
    _xxhash_available = False


def xxh3_64_uint64(data: bytes) -> int:
    """
    Compute XXH3_64 hash over byte stream, return as uint64.
    In hashless mode, returns 0.
    """
    if HASHLESS_MODE or not _xxhash_available:
        return 0
    
    hasher = xxhash.xxh3_64()
    hasher.update(data)
    return hasher.intdigest()


def layout_hash(map_layout: 'MapLayout') -> int:
    """
    Compute canonical hash of MapLayout.
    
    Per v5 spec: omits TerritoryLayout.name to avoid cosmetic drift.
    
    Canonical byte stream:
    - territories visited in id order 0..T-1
    - for each territory: id:int32_le, tiles:[(x:int32_le,y:int32_le)] in input order,
      adjacencies: sorted ascending int32_le list, border segments in input order
    - dimensions (width,height) as int32_le each
    - grid_lookup rows y=0..H-1, each x=0..W-1 encoded as int32_le territory_id or -1
    """
    if HASHLESS_MODE:
        return 0
    
    from ..api.types import MapLayout
    
    stream = bytearray()
    
    # Territories in id order 0..T-1
    for territory_id in sorted(map_layout.territories.keys()):
        territory = map_layout.territories[territory_id]
        
        # Territory ID as int32_le
        stream.extend(struct.pack('<i', territory.id))
        
        # Tiles in input order (x, y as int32_le each)
        for tile in territory.tiles:
            stream.extend(struct.pack('<i', tile.x))
            stream.extend(struct.pack('<i', tile.y))
        
        # Adjacencies sorted ascending
        for adj_id in sorted(territory.adjacencies):
            stream.extend(struct.pack('<i', adj_id))
        
        # Border segments in input order
        for segment in territory.border:
            stream.extend(struct.pack('<i', segment.start.x))
            stream.extend(struct.pack('<i', segment.start.y))
            stream.extend(struct.pack('<i', segment.end.x))
            stream.extend(struct.pack('<i', segment.end.y))
    
    # Dimensions
    stream.extend(struct.pack('<i', map_layout.dimensions.x))
    stream.extend(struct.pack('<i', map_layout.dimensions.y))
    
    # Grid lookup rows y=0..H-1, each x=0..W-1  
    for y in range(map_layout.dimensions.y):
        for x in range(map_layout.dimensions.x):
            territory_id = map_layout.grid_lookup[y][x]
            stream.extend(struct.pack('<i', territory_id))
    
    return xxh3_64_uint64(bytes(stream))


def state_hash_bytes(owners: List[int], dice: List[int], 
                    active_player_id: int, phase: int, turn_number: int,
                    winner_id: Optional[int], tick_id: int, rng_counters: Dict[str, int],
                    layout_hash: int, rules_version: str, schema_version: str,
                    battle_system: str, supply_policy: str, 
                    max_dice_per_territory: int) -> bytes:
    """
    Generate canonical byte stream for state hash.
    In hashless mode, returns empty bytes.
    """
    if HASHLESS_MODE:
        return b""
    
    stream = bytearray()
    
    # Dynamic board state
    for owner in owners:
        stream.extend(struct.pack('<i', owner))  # int32
    for die_count in dice:
        stream.extend(struct.pack('<h', die_count))  # int16
    
    # Game meta state  
    stream.extend(struct.pack('<i', active_player_id))  # int32
    stream.extend(struct.pack('B', phase))  # uint8
    stream.extend(struct.pack('<i', turn_number))  # int32
    stream.extend(struct.pack('<i', winner_id if winner_id is not None else -1))  # int32
    stream.extend(struct.pack('<Q', tick_id))  # uint64
    
    # RNG counters in sorted order by stream name
    for stream_name in sorted(rng_counters.keys()):
        stream.extend(struct.pack('<Q', rng_counters[stream_name]))  # uint64
    
    # Static layout/rules identity
    stream.extend(struct.pack('<Q', layout_hash))  # uint64
    
    # Rule identity (as numeric hashes, not raw strings)
    # For now, use simple string hash - in production would be more sophisticated
    rules_hash = hash(f"{rules_version}:{schema_version}:{battle_system}:{supply_policy}:{max_dice_per_territory}") & 0xFFFFFFFFFFFFFFFF
    stream.extend(struct.pack('<Q', rules_hash))  # uint64
    
    return bytes(stream)


def position_hash_bytes(owners: List[int], dice: List[int],
                       active_player_id: int, phase: int, turn_number: int,
                       winner_id: Optional[int], layout_hash: int, 
                       rules_version: str, schema_version: str,
                       battle_system: str, supply_policy: str,
                       max_dice_per_territory: int) -> bytes:
    """
    Generate canonical byte stream for position hash.
    Same as state_hash but excludes tick_id and rng_counters.
    """
    if HASHLESS_MODE:
        return b""
    
    stream = bytearray()
    
    # Dynamic board state
    for owner in owners:
        stream.extend(struct.pack('<i', owner))  # int32
    for die_count in dice:
        stream.extend(struct.pack('<h', die_count))  # int16
    
    # Game meta state (no tick_id, no rng_counters)
    stream.extend(struct.pack('<i', active_player_id))  # int32
    stream.extend(struct.pack('B', phase))  # uint8
    stream.extend(struct.pack('<i', turn_number))  # int32
    stream.extend(struct.pack('<i', winner_id if winner_id is not None else -1))  # int32
    
    # Static layout/rules identity
    stream.extend(struct.pack('<Q', layout_hash))  # uint64
    
    # Rules identity
    rules_hash = hash(f"{rules_version}:{schema_version}:{battle_system}:{supply_policy}:{max_dice_per_territory}") & 0xFFFFFFFFFFFFFFFF
    stream.extend(struct.pack('<Q', rules_hash))  # uint64
    
    return bytes(stream)


def state_hash(*args, **kwargs) -> int:
    """Compute state hash from canonical byte stream.""" 
    return xxh3_64_uint64(state_hash_bytes(*args, **kwargs))


def position_hash(*args, **kwargs) -> int:
    """Compute position hash from canonical byte stream."""
    return xxh3_64_uint64(position_hash_bytes(*args, **kwargs))