Awesome—here’s a clean, drop-in **API v5** that keeps everything you liked from v4 and only changes what we flagged. I’ve written it as a self-contained spec with tight deltas, updated types, and wire examples.

---

# Dice Wars AI — API Design (v5, Phase 1.1)

> **Intent**
> v5 is a minimal, surgical revision of v4 that closes wire-safety and RL ergonomics gaps while preserving all v4 semantics that were already good.

## What’s new in v5 (relative to v4)

1. **Uint64 on the wire is stringified** (JS-safe): `tick_id`, all `Hash64`s (`state_hash`, `position_hash`, `layout_hash`, `action_index_hash`) are **decimal strings** with format `"uint64"`.
2. **Penalties are first-class actions**: new `PenaltyAction` (`type: "penalty"`, `reason`), so observers/logs are uniform.
3. **RL indexing**: `AttackAction.attack_index` included everywhere an attack appears; `BattleResult.attack_pair_index` added.
4. **Timeout window semantics**: precise **start/stop/reset** rules, including SUPPLY.
5. **Max-turns winner policy**: deterministic, configurable `WinnerPolicy` with a stable tie-break chain.
6. **Canonicalization note**: formalized byte widths/order; a `docs/canonicalization.md` is now part of the API.
7. **Error taxonomy**: expanded `InvalidAction` and added `error_data` for machine-readable context.
8. **Supply placements > 0**: zero-value entries are invalid.
9. **Skip-turn edge case**: defined behavior if a skipped player is eliminated before the auto-skip fires.
10. **`position_hash` is always present** in `ActionResult`.
11. **Schema hygiene**: enums frozen; `additionalProperties:false` across wire schemas.
12. **Replay header** record; **delta transport preview** behind capability switch.
13. **NumPy dtypes pinned** in docs to avoid hash drift; lightweight public import guidance (`extras_require`).

---

## Repository & Package Layout (unchanged from v4)

*(Same tree and import rules as v4.)*

---

## Wire & Schema Conventions (updated)

* JSON uses `snake_case`. Enums are lowercase strings.
* **Uint64 on the wire:** the following are **decimal strings** with `"format":"uint64"`:

  * `tick_id`, `state_hash`, `position_hash`, `layout_hash`, `action_index_hash`
* **Schema snippet (reusable):**

```json
{ "type": "string", "pattern": "^[0-9]+$", "format": "uint64", "description": "Decimal-encoded 64-bit unsigned integer" }
```

* All top-level message schemas set `"additionalProperties": false`.
* **Capabilities** adds:

  * `"uint64_encoding": "decimal_string"`

---

## Penalties as First-Class Actions

### Action union (now 4 variants)

`"type": "attack" | "end_turn" | "distribute_supply" | "penalty"`

```python
@dataclass(frozen=True)
class PenaltyAction(Action):
    reason: 'PenaltyReason'  # 'timeout' | 'invalid_action'
```

**Engine rule:** `apply_penalty(...)` yields an `ActionResult` whose `action` (as observed) is a `PenaltyAction`, so observers/logs are uniform through `on_action_executed`.

---

## RL Indexing for Attacks

### AttackAction (extended)

```python
@dataclass(frozen=True)
class AttackAction(Action):
    attacker_territory_id: 'TerritoryID'
    defender_territory_id: 'TerritoryID'
    attack_index: int  # index into AttackPairs.pairs
```

* **Enumeration rule:** In ATTACK, every item of `TurnContext.valid_actions` for attacks **includes** `attack_index`, matching `attack_pairs.pairs` order exactly.

### BattleResult (extended)

```python
@dataclass
class BattleResult:
    ...
    attack_pair_index: int  # mirrors AttackAction.attack_index
```

---

## Timeout Window Semantics (precise)

* A **decision window** starts **immediately before** each call to `PlayerClient.get_action(ctx)`.
* The window **stops/resets** on:

  * any **accepted** action (including an ATTACK that leaves control with the same player),
  * or when a **penalty** is applied.
* **SUPPLY** is a single high-level decision: it gets **its own window** (start before that `get_action`).
* **Timeout ordering:** when a window expires → `on_turn_timeout` → `apply_penalty(TIMEOUT)` (emits `on_action_executed` with a `PenaltyAction`) → proceed per policy.
* Rejected actions (invalid) **do not** reset the window; if a penalty follows due to policy, the penalty resets it.

---

## Max-Turns Winner Policy (deterministic)

### New enum & config

```python
class WinnerPolicy(str, Enum):
    NONE = 'none'
    MOST_TERRITORIES = 'most_territories'
    MOST_TOTAL_DICE = 'most_total_dice'
    LARGEST_CONNECTED = 'largest_connected'
    LEXICOGRAPHIC = 'lexicographic'   # uses a chain

@dataclass(frozen=True)
class GameConfig:
    ...
    max_turns: Optional[int]
    winner_policy: WinnerPolicy            # default: 'none'
    winner_tiebreak_chain: List[str] = field(default_factory=lambda: [
        'most_territories', 'most_total_dice', 'largest_connected', 'lowest_player_id'
    ])
```

**When `max_turns` is hit** (i.e., just before a **new alive** player would enter ATTACK):

* `phase = GAME_OVER`
* Winner chosen by `winner_policy`:

  * `none` → `winner_id = None`
  * metrics are computed deterministically from `GameState`:

    * `most_territories` (descending)
    * `most_total_dice` (descending)
    * `largest_connected` (descending)
    * `lowest_player_id` (ascending, acts as final deterministic tie)
  * `lexicographic` evaluates the `winner_tiebreak_chain` left→right.

---

## Hash Canonicalization (formalized)

A new, normative `docs/canonicalization.md` (part of the API) specifies:

* **Byte widths**: `owners:int32`, `dice:int16`, `active_player_id:int32`, `phase:uint8`, `turn_number:int32`, `winner_id:int32(-1 for None)`, `tick_id:uint64`, RNG counters: `uint64`.
* **Ordering**: exact field order and array traversal (territories `0..T-1`, players `0..P-1`).
* **Endianness**: little-endian for all integers.
* **Strings/enums**: hashes include only numeric identities (no raw strings).
* **Vectors**: a minimal set of cross-platform vectors (Linux/macOS) maintained under `tests/fixtures/hash_vectors.jsonl`.

*(All other v4 hash semantics remain unchanged.)*

---

## Error Taxonomy & Payload (expanded)

### `InvalidAction` additions

```python
class InvalidAction(str, Enum):
    ILLEGAL_ATTACK = 'illegal_attack'
    OVER_SUPPLY_LIMIT = 'over_supply_limit'
    NOT_YOUR_TURN = 'not_your_turn'
    BAD_PHASE = 'bad_phase'
    TERRITORY_NOT_OWNED = 'territory_not_owned'
    INSUFFICIENT_DICE = 'insufficient_dice'
    ILLEGAL_END_TURN = 'illegal_end_turn'
    SCHEMA_MISMATCH = 'schema_mismatch'
    UNKNOWN_ENUM = 'unknown_enum'
    BAD_PAYLOAD = 'bad_payload'
```

### `ActionResult` addition

```python
@dataclass
class ActionResult:
    ...
    error_data: Optional[Dict[str, Any]] = None  # machine-readable context
```

*Engine use:* gameplay errors use specific codes; wire/bridge parsing may bubble `bad_payload`, `unknown_enum`, `schema_mismatch` with `error_data` to aid clients.

---

## Supply Placements Must Be > 0

* `DistributeSupplyAction.placements[t] > 0` for all entries (no zeros).
* Validation section updated; schemas enforce `minimum: 1`.

---

## Skip-Turn Edge Case

If a player marked to be skipped (due to `SKIP_NEXT_TURN`) is **eliminated** before their auto-skip moment:

* The skip flag is cleared.
* **No** `on_turn_start` is fired for them.
* **No extra tick** is consumed beyond the initial “mark skip” mutation already accounted for.

---

## Turn Numbering Clarity

* `turn_number` **increments only** when a **new alive** player enters **ATTACK**.
* Entering **SUPPLY** does **not** increment it.
* Penalties that pass control to another player **do not** increment it unless that player actually **enters ATTACK** (and is alive).

Property tests in M5 enforce these rules.

---

## Delta Transport (preview; optional)

* Capability flag: `"supports_delta": true` means the engine **may** include a `delta` in `ActionResult`.
* **Wire shape** (compact and JSON-friendly):

```json
"delta": {
  "changed_territories": [12, 9, 4],
  "new_owners": [1, 0, 0],
  "new_dice":   [3, 1, 2],
  "phase_changed": true,
  "new_phase": "attack",
  "turn_advanced": false,
  "game_ended": false,
  "winner_id": null
}
```

* Clients can ignore this until promoted to stable transport.

---

## Replay Header (self-describing logs)

First JSONL record:

```json
{
  "type": "header",
  "rules_version": "v1",
  "schema_version": "v5",
  "engine_build": "commit:abc123",
  "layout_hash": "7123456789012345678",
  "action_index_hash": "6234567890123456789",
  "random_seed": 1337,
  "uint64_encoding": "decimal_string"
}
```

---

## Typed Interface Reference (only the diffs vs v4)

*(Unchanged items omitted for brevity; all v4 types remain unless modified below.)*

### Enums (new/extended)

```python
class WinnerPolicy(str, Enum):
    NONE = 'none'
    MOST_TERRITORIES = 'most_territories'
    MOST_TOTAL_DICE = 'most_total_dice'
    LARGEST_CONNECTED = 'largest_connected'
    LEXICOGRAPHIC = 'lexicographic'
```

*(Extended `InvalidAction` as shown above.)*

### Actions

```python
@dataclass(frozen=True)
class AttackAction(Action):
    attacker_territory_id: 'TerritoryID'
    defender_territory_id: 'TerritoryID'
    attack_index: int  # NEW

@dataclass(frozen=True)
class PenaltyAction(Action):
    reason: 'PenaltyReason'
```

### Battle & Results

```python
@dataclass
class BattleResult:
    ...
    attack_pair_index: int  # NEW

@dataclass
class ActionResult:
    success: bool
    new_game_state: GameState
    battle_result: Optional[BattleResult] = None
    supply_placements: Optional[Dict['TerritoryID', int]] = None
    error_code: Optional[InvalidAction] = None
    error_message: Optional[str] = None
    error_data: Optional[Dict[str, Any]] = None       # NEW
    tick_id: 'TickID' = 0
    state_hash: 'Hash64' = 0
    position_hash: 'Hash64' = 0                       # NOW REQUIRED
    delta: Optional['StateDeltaWire'] = None          # OPTIONAL, guarded by capability
```

*(Define `StateDeltaWire` per Delta section.)*

### Game Config

```python
@dataclass(frozen=True)
class GameConfig:
    ...
    max_turns: Optional[int]
    winner_policy: WinnerPolicy = WinnerPolicy.NONE
    winner_tiebreak_chain: List[str] = field(default_factory=lambda: [
        'most_territories', 'most_total_dice', 'largest_connected', 'lowest_player_id'
    ])
```

---

## JSON Examples (updated)

**ATTACK TurnContext (excerpt with index)**

```json
{
  "valid_actions": [
    {"type":"attack","player_id":1,"attacker_territory_id":12,"defender_territory_id":9,"attack_index":73},
    {"type":"end_turn","player_id":1}
  ]
}
```

**Supply placements (>0 only)**

```json
{"type":"distribute_supply","player_id":1,"placements":{"2":3,"4":2}}
```

**Penalty emission (observer sees)**

```json
{"type":"penalty","player_id":1,"reason":"timeout"}
```

**ActionResult with JS-safe uint64s & required position\_hash**

```json
{
  "success": true,
  "new_game_state": {"phase":"attack", "active_player_id":1, "turn_number":7, "winner_id":null, "territories":{}, "players":[]},
  "tick_id": "1432",
  "state_hash": "15465789324567891234",
  "position_hash": "15465789324567890000"
}
```

**Capabilities (excerpt)**

```json
{
  "schema_version":"v5",
  "layout_hash":"7123456789012345678",
  "action_index_hash":"6234567890123456789",
  "uint64_encoding":"decimal_string",
  "supports_delta": true
}
```

---

## Validation Matrix (additions)

* **Wire**: `tick_id`/hashes are decimal strings matching `"format":"uint64"`.
* **Attack enumeration**: `attack_index` present and matches `attack_pairs.pairs` order.
* **Penalty**: a penalty produces an observable `PenaltyAction` via `on_action_executed`.
* **Supply**: `placements` values are strictly `> 0`.
* **Skip-turn eliminated**: no auto-skip tick later; skip flag cleared; no `on_turn_start`.
* **Turn number**: does not change on SUPPLY or penalty unless a **new alive** player enters ATTACK.
* **ActionResult**: always includes `position_hash`.
* **Schemas**: `additionalProperties:false` for all payloads.

---

## Test Plan (new cases added to v4)

* **Uint64 JS round-trip**: parse/stringify in JS & Python → hashes/ticks unchanged.
* **Timeout reset**: after each accepted ATTACK (same player continues), window resets.
* **Skip-turn elimination**: mark skip → eliminate → assert no later auto-skip tick.
* **Penalty as action**: logs/replays treat penalty uniformly; round-trip replays match.
* **Winner policy**: deterministic resolution for each `WinnerPolicy`, including `lexicographic` chain.
* **Schema hygiene**: reject unknown fields (`additionalProperties:false`) and zero entries in `placements`.

---

## Implementation Notes

* **NumPy dtypes (doc-pinned):** `owners:int32`, `dice:int16`; keep these stable to avoid hash drift.
* **Public import weight:** keep default import light; fence optional UI deps under `extras_require = { "ui": [...], "dev": [...] }`.
* **Docs:** add `docs/canonicalization.md` (normative), and update schema files under `transport/json/schema/` with uint64 string formats and `additionalProperties:false`.

---

## Minimal Client Pseudocode (v5, ATTACK index aware)

```python
def get_action(ctx: TurnContext) -> Action:
    if ctx.game_state.phase == GamePhase.ATTACK:
        # Choose from ctx.valid_actions; attacks include .attack_index for RL agents
        return pick_from(ctx.valid_actions)

    s = ctx.supply  # SUPPLY
    assert s is not None
    if s.can_end_early or s.supply_remaining == 0:
        return EndTurnAction(player_id=ctx.current_player_id)

    placements = my_policy(s.eligible_territories, s.supply_remaining, s.per_territory_cap)
    # Ensure all placements > 0
    placements = {t:n for t,n in placements.items() if n > 0}
    return DistributeSupplyAction(player_id=ctx.current_player_id, placements=placements)
```

---

If you want, I can also spit out the **JSON Schema stubs** for `turn_context.json`, `action_result.json`, and `capabilities.json` with the `uint64` string formats and `additionalProperties:false` baked in.
