"""Canonical attack pairs generation and indexing for RL compatibility."""

import struct
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .hash import xxh3_64_uint64, HASHLESS_MODE


@dataclass(frozen=True)
class AttackPairs:
    """
    Canonical attack pairs with deterministic ordering and indexing.
    
    Critical for RL: attack_index must be stable across engine versions
    for the same map layout.
    """
    pairs: List[Tuple[int, int]]  # (src, dst) in canonical order
    hash64: int  # XXH3_64 over canonical byte stream
    index_map: Dict[Tuple[int, int], int]  # (src, dst) -> index
    
    @classmethod
    def from_map_layout(cls, map_layout: 'MapLayout') -> 'AttackPairs':
        """
        Generate AttackPairs from MapLayout adjacency information.
        
        Canonical order: lexicographic ascending by (src, dst).
        """
        from ..api.types import MapLayout
        
        pairs = []
        
        # Generate all directed attack pairs from adjacency
        for src_id, territory in map_layout.territories.items():
            for dst_id in territory.adjacencies:
                # Validate adjacency is symmetric (invariant check)
                if src_id not in map_layout.territories[dst_id].adjacencies:
                    raise ValueError(f"Asymmetric adjacency: {src_id} -> {dst_id}")
                
                pairs.append((src_id, dst_id))
        
        # Canonical order: lexicographic ascending by (src, dst)
        pairs.sort()
        
        # Build index map for O(1) lookup
        index_map = {pair: idx for idx, pair in enumerate(pairs)}
        
        # Compute hash
        if HASHLESS_MODE:
            hash64 = 0
        else:
            stream = bytearray()
            for src, dst in pairs:
                stream.extend(struct.pack('<i', src))  # int32_le
                stream.extend(struct.pack('<i', dst))  # int32_le
            hash64 = xxh3_64_uint64(bytes(stream))
        
        return cls(pairs=pairs, hash64=hash64, index_map=index_map)
    
    def get_attack_index(self, attacker_territory_id: int, 
                        defender_territory_id: int) -> int:
        """Get attack index for RL agents."""
        pair = (attacker_territory_id, defender_territory_id)
        if pair not in self.index_map:
            raise ValueError(f"Invalid attack pair: {pair}")
        return self.index_map[pair]
    
    def validate_adjacency_invariants(self, map_layout: 'MapLayout') -> None:
        """Validate adjacency graph invariants."""
        from ..api.types import MapLayout
        
        # Check symmetry: if A adjacent to B, then B adjacent to A
        for src_id, territory in map_layout.territories.items():
            for dst_id in territory.adjacencies:
                if src_id not in map_layout.territories[dst_id].adjacencies:
                    raise ValueError(f"Adjacency not symmetric: {src_id} <-> {dst_id}")
        
        # Check no self-loops
        for territory_id, territory in map_layout.territories.items():
            if territory_id in territory.adjacencies:
                raise ValueError(f"Self-loop detected: {territory_id}")
        
        # Verify our pairs match the adjacency
        expected_pairs = set()
        for src_id, territory in map_layout.territories.items():
            for dst_id in territory.adjacencies:
                expected_pairs.add((src_id, dst_id))
        
        actual_pairs = set(self.pairs)
        if expected_pairs != actual_pairs:
            raise ValueError("AttackPairs do not match adjacency")