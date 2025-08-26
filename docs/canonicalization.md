# Canonicalization Rules

This document specifies byte-level canonicalization for all hashing operations. These rules ensure identical hashes across platforms, compilers, and implementations.

## General Principles

- **Endianness**: Little-endian for all multi-byte integers
- **Byte widths**: Fixed widths specified per field
- **Ordering**: Explicit traversal order for all collections
- **String handling**: Convert to numeric identities; no raw string bytes in hash streams

## Layout Hash

**Purpose**: Stable identifier for map topology, excluding cosmetic changes.

**Fields included** (in order):
1. **Territories** (id order 0..T-1):
   - `id`: int32_le
   - ~~`name`~~: **OMITTED** to avoid cosmetic drift
   - `tiles`: [(x:int32_le, y:int32_le)] in input order
   - `adjacencies`: sorted ascending int32_le list
   - `border`: [(start_x:int32_le, start_y:int32_le, end_x:int32_le, end_y:int32_le)] in input order

2. **Dimensions**: (width:int32_le, height:int32_le)

3. **Grid lookup**: rows y=0..H-1, each x=0..W-1 as int32_le (-1 for empty)

**Hash function**: XXH3_64 with seed=0, no secret.

## Attack Pairs Hash  

**Purpose**: Stable identifier for valid attack combinations, critical for RL policy compatibility.

**Fields included**:
- Attack pairs (src:int32_le, dst:int32_le) in lexicographic ascending order

**Hash function**: XXH3_64 with seed=0, no secret.

## State Hash

**Purpose**: Replay equivalence - same inputs produce same game state.

**Fields included** (in order):
1. **Dynamic board**: 
   - `owners`: int32_le array (territory order 0..T-1)
   - `dice`: int16_le array (territory order 0..T-1)

2. **Game metadata**:
   - `active_player_id`: int32_le
   - `phase`: uint8 (0=SETUP, 1=ATTACK, 2=SUPPLY, 3=GAME_OVER)
   - `turn_number`: int32_le  
   - `winner_id`: int32_le (-1 for None)
   - `tick_id`: uint64_le

3. **RNG state**: 
   - RNG counters: uint64_le in alphabetical order by stream name

4. **Static identity**:
   - `layout_hash`: uint64_le
   - `rules_hash`: uint64_le (computed from rules_version, schema_version, battle_system, supply_policy, max_dice_per_territory)

## Position Hash

**Purpose**: Dataset deduplication - same board position regardless of history.

**Fields**: Same as state_hash **EXCEPT**:
- ~~`tick_id`~~: **OMITTED**
- ~~RNG counters~~: **OMITTED**

## NumPy Compatibility

**Critical**: Use pinned dtypes to prevent cross-platform drift:

```python
owners = np.array(owners, dtype=np.int32)    # Exactly 32-bit signed
dice = np.array(dice, dtype=np.int16)        # Exactly 16-bit signed  
```

**Never** use `np.int` (platform-dependent) or unpinned array creation.

## Cross-Platform Test Vectors

Maintained in `tests/fixtures/hash_vectors.jsonl`:

```jsonl
{"map_name": "small_test", "layout_hash": "12345678901234567890", "platform": "linux_x64"}
{"map_name": "small_test", "layout_hash": "12345678901234567890", "platform": "macos_arm64"}
```

All platforms must produce identical hashes for identical inputs.