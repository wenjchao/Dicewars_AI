# Dice Wars AI — Final API Design (v4+v5, Phase 1: RL-ready Core Internals)

> **Purpose**
> A small, stable public API for gameplay + a slim, atomic core for RL.
> This version locks:
>
> 1. **Player SUPPLY contract** (no enumeration; single bulk placement).
> 2. **Tick semantics** (one definition covering actions, penalties, and multi-step supply).
> 3. **Penalty semantics** (policy-driven, no RNG).
> 4. **Determinism surfaces** (XXH3\_64 `state_hash`/`position_hash`, test vectors).
> 5. **Typed public surface** (complete DTOs, enums, actions, wire examples).
>
> Everything else prioritizes determinism, replayability, and easy client implementation.
>
> **v5 Integration Note**: This document integrates v5 improvements (JS-safe uint64s, penalty actions, RL indexing, enhanced errors) while preserving all v4 content.

## What’s new in v4 (relative to v1–v3)

* Keeps **v2** repo layout improvements (pyproject, examples, property tests) and **v3** schema location.
* Restores **v1**’s **complete typed surface** and **validation matrix**, updated with:

  * `TimeoutPolicy`, `SupplyDescriptor.can_end_early`, `GameEngine.__init__(config)`, `get_capabilities()`
* Standardizes on **XXH3\_64**; defines **`state_hash`** vs **`position_hash`** precisely, with cross-platform vectors.
* Clarifies **observer emissions** for penalties and **roll order** (attacker first, raw order).
* Adds optional **JSON Schemas** under `transport/json/schema/` and advertises them in capabilities.

## What's new in v5 (integrated improvements)

1. **Uint64 on the wire is stringified** (JS-safe): `tick_id`, all `Hash64`s are **decimal strings** with format `"uint64"`.
2. **Penalties are first-class actions**: new `PenaltyAction` (`type: "penalty"`, `reason`), so observers/logs are uniform.
3. **RL indexing**: `AttackAction.attack_index` included everywhere; `BattleResult.attack_pair_index` added.
4. **Timeout window semantics**: precise **start/stop/reset** rules, including SUPPLY.
5. **Max-turns winner policy**: deterministic, configurable `WinnerPolicy` with stable tie-break chain.
6. **Canonicalization note**: formalized byte widths/order; `docs/canonicalization.md` is part of the API.
7. **Error taxonomy**: expanded `InvalidAction` and added `error_data` for machine-readable context.
8. **Supply placements > 0**: zero-value entries are invalid.
9. **Skip-turn edge case**: defined behavior if skipped player is eliminated before auto-skip.
10. **`position_hash` is always present** in `ActionResult`.
11. **Schema hygiene**: enums frozen; `additionalProperties:false` across wire schemas.
12. **Replay header** record; **delta transport preview** behind capability switch.
13. **NumPy dtypes pinned** to avoid hash drift.

---

## Repository & Package Layout (authoritative)

> The filesystem layout **is part of the API**. Public symbols live under `dicewars.api.*` (stable). Internals live under `dicewars.core.*` (unstable).

```
dicewars-ai/
├── pyproject.toml
├── src/
│   └── dicewars/
│       ├── __init__.py                 # re-export of public surface (from dicewars.api)
│       ├── __about__.py                # __version__, RULES_VERSION, SCHEMA_VERSION
│       ├── api/                        # ✅ Stable public contracts (import from here)
│       │   ├── __init__.py             # defines __all__; re-exports stable names
│       │   ├── types.py                # DTOs, Enums, type aliases (public)
│       │   ├── client.py               # PlayerClient interface (public)
│       │   ├── observer.py             # GameObserver interface (public)
│       │   ├── coordinator.py          # Coordinator-facing engine signatures
│       │   └── engine.py               # Public GameEngine wrapper signatures
│       ├── engine/
│       │   └── public.py               # Thin wrapper over core with public semantics
│       ├── coordinator/
│       │   ├── loop.py                 # turn loop; penalties; fan-out to observers
│       │   └── penalties.py            # penalty application helpers
│       ├── observers/
│       │   ├── base.py                 # logging/replay observers
│       │   ├── replay.py               # JSONL replayer (later milestone)
│       │   ├── gui.py                  # NEW: Live GUI observer (renders on map creation)
│       │   └── cli.py                  # NEW: Live terminal (ASCII) observer
│       ├── ui/                         # NEW: visualization layer (internal, replaceable; non-API)
│       │   ├── __init__.py
│       │   ├── viewmodel/              # GameState -> RenderState (stable for drawing)
│       │   │   ├── __init__.py
│       │   │   ├── transform.py
│       │   │   └── geometry.py
│       │   ├── gui/
│       │   │   ├── __init__.py
│       │   │   ├── app.py              # window/event loop; renders RenderState
│       │   │   └── renderer.py
│       │   └── cli/
│       │       ├── __init__.py
│       │       ├── app.py              # curses/rich runner
│       │       └── ascii_renderer.py   # grid_lookup -> text
│       ├── clients/
│       │   ├── base.py                 # PlayerClient ABC/examples
│       │   ├── random_bot.py           # baseline
│       │   └── heuristic_bot.py        # baseline
│       ├── core/                       # ❗Internal RL-friendly core (unstable)
│       │   ├── state.py                # CoreState; canonicalize; counters
│       │   ├── attack_pairs.py         # canonical (src,dst) list + hash
│       │   ├── actions.py              # CoreAction; masks; validators
│       │   ├── engine.py               # step(...), battle(...), supply micro-steps
│       │   ├── rng.py                  # Philox/SplitMix streams; counters
│       │   ├── hash.py                 # state_hash/position_hash (XXH3_64)
│       │   └── delta.py                # optional delta mode
│       ├── transport/
│       │   ├── json/
│       │   │   ├── bridge.py           # optional stdio/ws bridge (later milestone)
│       │   │   └── schema/             # ✅ JSON Schemas for wire payloads
│       │   └── __init__.py
│       └── utils/
│           └── typing.py               # shared aliases (if ever needed)
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── property/                       # Hypothesis-based invariants
│   ├── golden/
│   │   ├── test_golden_determinism.py
│   │   └── test_golden_penalties.py
│   └── fixtures/
│       ├── capabilities.json
│       ├── rng_test_vectors.json
│       └── hash_vectors.jsonl
├── examples/
│   └── minimal_client.py
├── scripts/
│   ├── determinism_script.py
│   ├── make_replay.py
│   ├── run_gui.py                      # NEW: run a match with GUI observer
│   ├── run_cli.py                      # NEW: run a match with CLI observer
│   └── preview_map.py                  # NEW: open GUI on MapLayout without starting a game
└── docs/
    ├── roadmap.md
    ├── M0.md
    └── M1.md
```

**Import rule of thumb**

* ✅ Public clients import **only** from `dicewars.api.*` (stable).
* ⚠️ RL/engine development may import `dicewars.core.*` but must expect breaking changes.

**Top-level export**
`import dicewars as dw` re-exports the public API from `dicewars.api`.

---

## System Architecture Overview

Hub-and-spoke: the **GameCoordinator** orchestrates; **GameEngine** is authoritative; **PlayerClient** makes decisions; **GameObserver** watches.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GameEngine    │◄───│ GameCoordinator │───►│  PlayerClient   │
│  (Authority)    │    │  (Orchestrator) │    │   (Decision)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  GameObserver   │
                       │   (Watcher)     │
                       └─────────────────┘
```

---

## Core Roles & Responsibilities

### GameEngine (backend authority)

* Validates rules and applies all state transitions.
* Executes battles; determines win/loss.
* **Pattern**: reactive only (never initiates calls).

### GameCoordinator (central orchestrator)

* Registers players and manages turn order.
* Asks engine for `TurnContext`, forwards to active player.
* Applies returned action and broadcasts results to observers/players.
* **Pattern**: active controller.

### PlayerClient (player contract)

* Single decision entry point: `get_action(context)`.

**Contract (final)**

* **ATTACK**: Return **one** of the enumerated `valid_actions` (multiple `AttackAction`s + one `EndTurnAction`).
* **SUPPLY**: The coordinator **does not enumerate** placements. You **must either**

  1. return a **`DistributeSupplyAction`** whose placements conform to `context.supply` (accepted even if **not** listed in `valid_actions`), **or**
  2. return **`EndTurnAction`** *only if* `SupplyPolicy == ALLOW_EARLY_END` **or** `supply_remaining == 0` **or** supply-exhaustion rule applies.
* Violations are rejected by the engine; penalties may be applied; all observable.

### GameObserver (passive watcher)

* Receives turn, action, battle, supply, and lifecycle events for logging/UI/analytics.
* **UI guidance**: A GUI/CLI observer can render immediately at `on_game_start(config, ...)`
  using `config.map_layout`. Subsequent frames are driven by `on_action_executed(..., result)`,
  which contains the authoritative `new_game_state` (and `BattleResult`, if any).

---

## API Contracts

### GameCoordinator ⇄ PlayerClient

```python
get_action(context: TurnContext) -> Action
```

* **ATTACK**: choose one of `context.valid_actions` (attacks + end-turn).
* **SUPPLY**: return `DistributeSupplyAction(placements)` (validated against `context.supply`) **or** `EndTurnAction` when allowed.

Lifecycle (optional):

```python
on_game_start(player_id: int, config: GameConfig) -> None
on_game_end(winner_id: int | None) -> None
on_battle_result(battle: BattleResult) -> None
```

**Decision cadence (MUST)**

* After **every successful ATTACK** that leaves control with the same player, the coordinator **MUST** call `get_turn_context()` again and pass that fresh `TurnContext` into the next `get_action(...)` call.
* **SUPPLY** is a **single high-level action** (either `DistributeSupplyAction` or `EndTurnAction`). After it succeeds, control hands off per phase rules; the coordinator does **not** request another action from the same player in that turn.
* `get_turn_context()` is a **pure read** and **does not** advance `tick_id`.

---

### GameCoordinator → GameEngine (public service)

**Construction**
`engine = GameEngine(config: GameConfig)`

**Game lifecycle**

```python
initialize_game(player_ids: list[PlayerID]) -> None
get_turn_context() -> TurnContext
apply_action(action: Action) -> ActionResult
apply_penalty(player_id: PlayerID, reason: PenaltyReason) -> ActionResult
get_capabilities() -> dict[str, object]
```

* `initialize_game` builds initial state for registered players.
* `get_turn_context` returns the active player’s view, deterministic `valid_actions`, and supply descriptor during SUPPLY.
* `apply_action` validates and applies a high-level action:

  * **ATTACK / END\_TURN**: one atomic step each.
  * **DistributeSupplyAction**: expanded into K atomic `place_one_die` steps in deterministic micro-order; returns one aggregated `ActionResult` with `tick_id` **after** the final micro-step.
* `apply_penalty` applies configured penalties (e.g., timeout), mutates state exactly once, consumes **no RNG**, returns updated state.
* `get_capabilities` exposes versioning and static hashes for compatibility checks.

> **No `is_game_over()`** — check `phase == GAME_OVER`.

---

### GameCoordinator → GameObserver

```python
on_turn_start(player_id: PlayerID, game_state: GameState) -> None
on_action_executed(action: Action, result: ActionResult) -> None
on_invalid_action(player_id: PlayerID, action: Action,
                  error_code: InvalidAction, error_message: str) -> None
on_turn_timeout(player_id: PlayerID, game_state: GameState) -> None
on_game_start(config: GameConfig, player_names: list[str]) -> None
on_game_end(winner_id: PlayerID | None, final_state: GameState) -> None
on_supply_distributed(player_id: PlayerID, placements: dict[int,int],
                      game_state: GameState) -> None
# Optional future-proofing:
# on_phase_change(player_id: PlayerID, from_phase: GamePhase, to_phase: GamePhase, game_state: GameState) -> None
```

* `on_turn_start` fires **only** when a **new** player enters **ATTACK** (not between ATTACK↔SUPPLY for the same player).
* `on_action_executed` fires for every successful high-level action **including penalties**.

**Note:** There is **no** observer-level `on_battle_result`. Observers read battle details from
`on_action_executed(..., result)` via `result.battle_result`. The `on_battle_result(...)` callback
belongs to **PlayerClient** as a convenience hook.

**UI note (render cadence):**
1) First paint at `on_game_start` with the static `MapLayout`.
2) Every subsequent paint is a pure function of `(last_action, result.new_game_state)`.
   This preserves determinism and makes replays visually identical.

---

## Communication Flow (reference)

1. **Registration** → `initialize_game` → lifecycle `on_game_start`.
2. Loop while `game_state.phase != GAME_OVER`
   a) `ctx = get_turn_context()`
   b) **Timeout guard**: fire `on_turn_timeout`, then `apply_penalty(TIMEOUT)` and continue
   c) Fire `on_turn_start` **iff** a new player just entered ATTACK
   d) Ask player: `action = get_action(ctx)`
   e) Apply: `result = apply_action(action)`
      · If `result.success == False`: emit `on_invalid_action(...)` **exactly once**.
        If policy applies, call `apply_penalty(INVALID_ACTION)` and continue the loop.
        **Ordering**: `on_invalid_action` happens before any penalty; if a penalty is applied,
        it emits `on_action_executed` with a `PenaltyAction` (coordinator MUST pass this to observers)
        after `on_invalid_action` and before any subsequent `on_turn_start`. 
        **No RNG** and **no `tick_id`** change on the rejected action; penalties advance `tick_id` by exactly 1.
   f) Broadcast: `on_action_executed`; **PlayerClient**.`on_battle_result` if present; `on_supply_distributed` if placements occurred
      · A GUI/CLI observer should re-render here using `result.new_game_state`.
   g) If control remains with the same player, fetch a **fresh** `TurnContext` (see Decision cadence) and repeat (d–f)
3. **Game end** → `on_game_end`.

---

## **Tick Semantics (final, unambiguous)**

> **Definition**: `tick_id` is a monotonically increasing counter of **atomic core steps**.
> A core step is one successful invocation of the engine’s internal `step(...)` that **changes state**.

**Origin**: `tick_id` starts at **0** at game creation and increments **after** each atomic state mutation.

**Rules**

1. Increment once **per atomic state mutation**. No increment on rejected/invalid actions.
2. **ATTACK** → 1 atomic step → `tick_id += 1`.
3. **END\_TURN** → 1 atomic step → `tick_id += 1`.
4. **DistributeSupplyAction** placing total K dice → **K atomic `place_one_die` steps** → `tick_id += K`. Returned `ActionResult.tick_id` is the counter **after** the final placement. The final placement step ALSO performs the phase/turn advance and discards any unused supply (ALLOW_EARLY_END), with **no additional tick** beyond those K.
5. **Penalty application** → exactly **1** atomic step → `tick_id += 1` (**must not** consume RNG).
6. Reads/housekeeping that do **not** change state **must not** advance `tick_id`.
7. **Elimination victory**: When the number of alive players drops to **1**, set `phase = GAME_OVER` and `winner_id = surviving_player` **in the same mutation** that caused the elimination (no extra tick).

**Deterministic supply micro-order**

1. Sort `placements.items()` by ascending `territory_id`.
2. For each `(territory_id, dice_to_add)` in that order, place **one die at a time**.
3. Validate the per-die mask at each micro-step. On any violation, reject the entire action (no partial mutation).

**Supply exhaustion rule**

* If `SupplyPolicy == MUST_PLACE_ALL` **and** there are **0** eligible territories (all capped or none owned), coordinator **must** allow `EndTurnAction` during SUPPLY.

---

## Penalty Semantics (timeout & invalid action)

`TimeoutPolicy` in `GameConfig` controls behavior:

* **AUTO\_END\_TURN**: apply a single **end\_turn** mutation **now** (tick +1). Phase/turn advance accordingly. **No RNG** consumption.
* **SKIP\_NEXT\_TURN**: set a skip flag and advance to the next player **now** (tick +1). When the skipped player's next turn would begin, the coordinator auto-skips via one mutation (tick +1). **No RNG** for either mutation.
* **Event ordering**: For `SKIP_NEXT_TURN`, do **not** fire `on_turn_start` for the skipped player.
  The auto-skip mutation instead emits `on_action_executed` and advances to the next player.
* **Skip-turn edge case (v5)**: If a skipped player is **eliminated** before their auto-skip moment:
  * The skip flag is cleared.
  * **No** `on_turn_start` is fired for them.
  * **No extra tick** is consumed beyond the initial "mark skip" mutation already accounted for.
* **Auto-skip vs max-turns boundary**: If `max_turns` is hit at a boundary where a skipped player would be auto-skipped, **apply max-turns first** (end the game) and **do not** perform the pending auto-skip mutation.

**Observer rule**: penalty mutations fire `on_action_executed` with their `ActionResult`.

**Penalties as First-Class Actions (v5)**: `apply_penalty(...)` yields an `ActionResult` whose action (as observed) is a `PenaltyAction`, so observers/logs are uniform through `on_action_executed`.

## Timeout Window Semantics (v5, precise)

* A **decision window** starts **immediately before** each call to `PlayerClient.get_action(ctx)`.
* The window **stops/resets** on:
  * any **accepted** action (including an ATTACK that leaves control with the same player),
  * or when a **penalty** is applied.
* **SUPPLY** is a single high-level decision: it gets **its own window** (start before that `get_action`).
* **Timeout ordering:** when a window expires → `on_turn_timeout` → `apply_penalty(TIMEOUT)` (emits `on_action_executed` with a `PenaltyAction`) → proceed per policy.
* Rejected actions (invalid) **do not** reset the window; if a penalty follows due to policy, the penalty resets it.

---

## Hash Semantics (authoritative)

Two 64-bit hashes using **XXH3\_64** with seed = 0 (no secret), over a canonical byte stream (little-endian integers, canonical ordering):

* **`state_hash`** (replay equivalence): includes dynamic board (`owners[]`, `dice[]`), meta (`active_player_id`, `phase`, `turn_number`, `winner_id`, `tick_id`), RNG counters for all streams (`setup`, `turn`, `battle`), and layout/rules identity (`layout_hash`, `rules_version`, `schema_version`, `battle_system`, `supply_policy`, `max_dice_per_territory`).
* **`position_hash`** (dataset dedup): same as `state_hash` **minus** `tick_id` and **minus** all `rng_counters`.

**Emission**: `ActionResult` includes the post-state `state_hash` and **always includes** `position_hash` (v5).

**Golden requirement**: identical inputs on any platform → identical 64-bit hashes. Test vectors live in `tests/fixtures/hash_vectors.jsonl`.

### Hash Canonicalization (v5, formalized)

A normative `docs/canonicalization.md` (part of the API) specifies:

* **Byte widths**: `owners:int32`, `dice:int16`, `active_player_id:int32`, `phase:uint8`, `turn_number:int32`, `winner_id:int32(-1 for None)`, `tick_id:uint64`, RNG counters: `uint64`.
* **Ordering**: exact field order and array traversal (territories `0..T-1`, players `0..P-1`).
* **Endianness**: little-endian for all integers.
* **Strings/enums**: hashes include only numeric identities (no raw strings).
* **Vectors**: a minimal set of cross-platform vectors (Linux/macOS) maintained under `tests/fixtures/hash_vectors.jsonl`.

### Layout Hash (normative)

`layout_hash` (normative): XXH3_64 over a canonical MapLayout byte stream:
territories visited in id order 0..T-1; for each territory:
  id:int32_le, tiles:[(x:int32_le,y:int32_le)] in input order,
  adjacencies: sorted ascending int32_le list, border segments in input order.
dimensions (width,height) as int32_le each; grid_lookup rows y=0..H-1, each x=0..W-1
encoded as int32_le territory_id or -1. Seed 0, no secret.

`layout_hash` **omits** `TerritoryLayout.name` to avoid cosmetic drift.

---

## RNG & Battles (deterministic)

* Independent seeded streams: `setup`, `turn`, `battle` with explicit counters.
* **Battle roll order**: **attacker first**, then **defender**. Consume **one RNG** value **per die** rolled. `BattleResult` stores **raw order** (unsorted).

---

## JSON Wire Conventions & Examples

* JSON keys use `snake_case`. Enums serialize as lowercase strings.
* Lists are ordered; ordering is normative wherever stated.
* For maps like `territories: {TerritoryID -> TerritoryState}`, JSON object keys may be
  serialized as **strings** by some stacks; clients MUST parse them as numeric IDs and MUST NOT
  rely on property order (use the explicit IDs).
* Action union discriminated by `"type": "attack" | "end_turn" | "distribute_supply" | "penalty"`.
* Integers are decimal JSON numbers **except** the following fields, which are JS-safe **decimal strings** (format `"uint64"`): `tick_id`, `state_hash`, `position_hash`, `layout_hash`, `action_index_hash`. No NaN/Infinity.
* **Schema snippet (reusable):**
  ```json
  { "type": "string", "pattern": "^[0-9]+$", "format": "uint64", "description": "Decimal-encoded 64-bit unsigned integer" }
  ```
* All top-level message schemas set `"additionalProperties": false`.
* **Numeric-keyed map schema pattern** (for `placements`, `territories`):
  ```json
  {
    "type": "object",
    "propertyNames": { "pattern": "^[0-9]+$" },
    "additionalProperties": { "type": "integer", "minimum": 1 }
  }
  ```
  (For `territories`, swap the value schema to the TerritoryState schema; for `placements`, keep `minimum: 1` to enforce "> 0".)
* **Examples below are truncated for brevity** (e.g., empty `territories`/`players` objects). Real responses contain a **full** `GameState`.

**TurnContext (ATTACK) — example**

```json
{
  "game_state": {
    "active_player_id": 1,
    "turn_number": 7,
    "winner_id": null,
    "phase": "attack",
    "territories": {"12": {"owner_id": 1, "dice_count": 5}},
    "players": [
      {"id": 0, "name": "BotA", "color": "#3366CC",
       "owned_territory_ids": [3,8], "total_dice": 14,
       "supply_dice": 0, "is_alive": true, "largest_connected_region": 2},
      {"id": 1, "name": "BotB", "color": "#DC3912",
       "owned_territory_ids": [12], "total_dice": 9,
       "supply_dice": 0, "is_alive": true, "largest_connected_region": 1}
    ]
  },
  "valid_actions": [
    {"type": "attack", "player_id": 1, "attacker_territory_id": 12, "defender_territory_id": 9, "attack_index": 73},
    {"type": "end_turn", "player_id": 1}
  ],
  "current_player_id": 1
}
```

**TurnContext (SUPPLY) — example**

```json
{
  "game_state": {"active_player_id": 1, "turn_number": 7, "winner_id": null, "phase": "supply",
                 "territories": {}, "players": []},
  "valid_actions": [{"type": "end_turn", "player_id": 1}],
  "current_player_id": 1,
  "supply": {
    "supply_remaining": 5,
    "eligible_territories": [2, 4, 7],
    "per_territory_cap": 8,
    "can_end_early": false
  }
}
```

**DistributeSupplyAction (request) → ActionResult (response)**

```json
{"type": "distribute_supply", "player_id": 1, "placements": {"2": 3, "4": 2}}
```

```json
{"success": true, "new_game_state": {"phase": "supply", "active_player_id": 1, "turn_number": 7, "winner_id": null,
 "territories": {}, "players": []}, "supply_placements": {"2": 3, "4": 2}, "tick_id": "1432",
 "state_hash": "15465789324567891234", "position_hash": "15465789324567890000"}
```

**Invalid ATTACK (example)**

```json
{"success": false, "new_game_state": {"phase": "attack", "active_player_id": 1, "turn_number": 7, "winner_id": null,
 "territories": {}, "players": []}, "error_code": "illegal_attack", "error_message": "Defender not adjacent",
 "error_data": {"attacker": 12, "defender": 15}, "tick_id": "1432", "state_hash": "15465789324567891234",
 "position_hash": "15465789324567890000"}
```

**Penalty emission (v5, observer sees)**

```json
{"type": "penalty", "player_id": 1, "reason": "timeout"}
```

**Capabilities (example)**

```json
{
  "rules_version": "v1",
  "schema_version": "v5",
  "layout_hash": "7123456789012345678",
  "action_index_hash": "6234567890123456789",
  "num_territories": 42,
  "num_attack_pairs": 180,
  "battle_system": "auto_all_but_one",
  "supply_policy": "must_place_all",
  "max_dice_per_territory": 8,
  "winner_policy": "most_territories",
  "winner_tiebreak_chain": ["most_territories", "most_total_dice", "largest_connected", "lowest_player_id"],
  "max_turns": 100,
  "supports_delta": true,
  "uint64_encoding": "decimal_string",
  "rng_streams": ["setup","turn","battle"],
  "wire_schemas": {
    "turn_context.json": "v1.0+sha256:…",
    "action_result.json": "v1.0+sha256:…"
  }
}
```

---

# **Typed Interface Reference (authoritative)**

> Complete public surface, including enums/DTOs and signatures.

## Type System & Conventions

**Primitive aliases**

* `PlayerID = int` (≥ 0)
* `TerritoryID = int` (≥ 0, contiguous 0..N-1)
* `TickID = int` (monotonic, **non-negative**, fits 64-bit signed; **wire:** decimal string `"uint64"`)
* `Hash64 = int` (0..2^64-1)
* `ColorHex = str` ("#RRGGBB")
* `TimestampISO8601 = str` (RFC3339)
* `RulesVersion = str`, `SchemaVersion = str`

**JSON wire**: snake_case keys; enums as strings; lists ordered; all DTOs serializable.

**Wire vs In-Memory Types:**

| Field                              | In-memory type | Wire type (JSON)  |
| ---------------------------------- | -------------- | ----------------- |
| `tick_id`                          | int64 ≥ 0      | string (`uint64`) |
| `state_hash`, `position_hash`      | uint64         | string (`uint64`) |
| `layout_hash`, `action_index_hash` | uint64         | string (`uint64`) |

**Engine numeric constraints (authoritative)**

All values are integers unless noted. **MUST** indicates a hard requirement.

**Notation**: Let `T := len(GameConfig.map_layout.territories)` (also equals `get_capabilities().num_territories`) and `P := len(GameState.players)`.

### Global
* `0 ≤ active_player_id < len(players)`
* `winner_id is None` **or** `0 ≤ winner_id < len(players)`
* `min_players ≤ len(players) ≤ max_players`
* Player IDs contiguous `0..P-1`; Territory IDs contiguous `0..T-1`
* `players` list is ordered by ascending ID and **canonical**: `players[i].id == i` for all `i ∈ [0..P-1]`
* `turn_number ≥ 0`
* Turn origin: `turn_number == 0` at game creation. It increments to `1` exactly when Player 0 (or the first alive player) first enters ATTACK.
* `tick_id ≥ 0`
* `tick_id` fits signed 64-bit and is **monotonic non-decreasing**

### Players
* `owned_territory_ids == { t | territories[t].owner_id == player.id }` and is **sorted ascending, deduplicated**
* `total_dice == Σ_{t ∈ owned_territory_ids} territories[t].dice_count`
* `0 ≤ largest_connected_region ≤ len(owned_territory_ids)`
* `is_alive == (len(owned_territory_ids) > 0)`; if not alive ⇒ `supply_dice == 0`
* `color` matches `#RRGGBB`

### Territories & dice
* Every `territories[t].owner_id` is a valid `PlayerID`
* `territories[t].dice_count ∈ [1, max_dice_per_territory]`
* No neutral territories (every territory has an owner)
* `territories` keys are **exactly** `{0,1,...,T-1}` (no gaps; full coverage)

### Supply
* `max_dice_per_territory ≥ 1`
* `initial_dice_per_territory ∈ [1, max_dice_per_territory]`
* `supply_remaining ≥ 0`
* At start of **SUPPLY**: `supply_remaining == min(calculated_award, max_supply_dice)` where `calculated_award` follows `supply_dice_calculation ∈ {'largest_connected','territory_count'}`
* `SupplyDescriptor.eligible_territories ⊆ owned_territory_ids` and is **sorted ascending, deduplicated**
* For each `t ∈ eligible_territories`: `territories[t].dice_count < max_dice_per_territory`
* `SupplyDescriptor.per_territory_cap == max_dice_per_territory`
* `SupplyDescriptor.can_end_early == (supply_policy == ALLOW_EARLY_END) or (supply_remaining == 0) or (supply_exhaustion_rule_triggers)`

### Map integrity
* `grid_lookup[y][x] ∈ {-1} ∪ {0..T-1}`; territory tile sets are pairwise disjoint
* Adjacency symmetric and loop-free: `v ∈ adj(u) ⇔ u ∈ adj(v)` and `u ∉ adj(u)`
* `len(grid_lookup) == map_layout.dimensions.y` and for every row `r`,
  `len(r) == map_layout.dimensions.x`

### RNG & hashing
* RNG stream counters (`setup`,`turn`,`battle`) are `≥ 0` and **monotonic non-decreasing**
* `Hash64` is an unsigned 64-bit (`0..2^64-1`) **XXH3_64** value

### Public Service API (GameCoordinator → GameEngine)

```python
from typing import List, Dict, Optional, Literal, Union, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# Registration lives on the Coordinator; shown for completeness.
def register_player(client: 'PlayerClient', name: str,
                    player_type: Literal['human','random_ai','rule_based_ai','other']) -> 'PlayerID': ...

class GameEngine:
    def __init__(self, config: 'GameConfig') -> None: ...
    def initialize_game(self, player_ids: List['PlayerID']) -> None: ...
    def get_turn_context(self) -> 'TurnContext': ...  # (pure read; MUST NOT mutate state, consume RNG, or advance `tick_id`.)
    def apply_action(self, action: 'Action') -> 'ActionResult': ...  # PenaltyAction is rejected (system-only).
    def apply_penalty(self, player_id: 'PlayerID', reason: 'PenaltyReason') -> 'ActionResult': ...
    def get_capabilities(self) -> Dict[str, Any]: ...
```

### PlayerClient Interface

```python
class PlayerClient:
    def get_action(self, context: 'TurnContext') -> 'Action': ...
    # Lifecycle (optional)
    def on_game_start(self, player_id: 'PlayerID', config: 'GameConfig') -> None: ...
    def on_game_end(self, winner_id: Optional['PlayerID']) -> None: ...
    def on_battle_result(self, battle: 'BattleResult') -> None: ...
```

### Observer Interface

```python
class GameObserver:
    def on_turn_start(self, player_id: 'PlayerID', game_state: 'GameState') -> None: ...
    def on_action_executed(self, action: 'Action', result: 'ActionResult') -> None: ...
    # For penalties, `action` is a PenaltyAction produced by `apply_penalty(...)`.
    def on_invalid_action(self, player_id: 'PlayerID', action: 'Action',
                          error_code: 'InvalidAction', error_message: str) -> None: ...
    def on_turn_timeout(self, player_id: 'PlayerID', game_state: 'GameState') -> None: ...
    def on_game_start(self, config: 'GameConfig', player_names: List[str]) -> None: ...
    def on_game_end(self, winner_id: Optional['PlayerID'], final_state: 'GameState') -> None: ...
    def on_supply_distributed(self, player_id: 'PlayerID', placements: Dict['TerritoryID', int],
                              game_state: 'GameState') -> None: ...
    # Note: Concrete observers (GUI/CLI/replay) are reference implementations and
    # non-normative. Only this interface is covered by stability guarantees.
```

### Enums

```python
class GamePhase(str, Enum):
    SETUP = 'setup'
    ATTACK = 'attack'
    SUPPLY = 'supply'
    GAME_OVER = 'game_over'

class BattleSystem(str, Enum):
    AUTO_ALL_BUT_ONE = 'auto_all_but_one'

class InvalidAction(str, Enum):
    ILLEGAL_ATTACK = 'illegal_attack'
    OVER_SUPPLY_LIMIT = 'over_supply_limit'
    NOT_YOUR_TURN = 'not_your_turn'
    BAD_PHASE = 'bad_phase'
    TERRITORY_NOT_OWNED = 'territory_not_owned'
    INSUFFICIENT_DICE = 'insufficient_dice'
    ILLEGAL_END_TURN = 'illegal_end_turn'         # v5
    SCHEMA_MISMATCH = 'schema_mismatch'           # v5
    UNKNOWN_ENUM = 'unknown_enum'                 # v5
    BAD_PAYLOAD = 'bad_payload'                   # v5

class PenaltyReason(str, Enum):
    TIMEOUT = 'timeout'
    INVALID_ACTION = 'invalid_action'

class SupplyPolicy(str, Enum):
    MUST_PLACE_ALL = 'must_place_all'
    ALLOW_EARLY_END = 'allow_early_end'

class TimeoutPolicy(str, Enum):
    AUTO_END_TURN = 'auto_end_turn'
    SKIP_NEXT_TURN = 'skip_next_turn'

class WinnerPolicy(str, Enum):                    # v5
    NONE = 'none'
    MOST_TERRITORIES = 'most_territories'
    MOST_TOTAL_DICE = 'most_total_dice'
    LARGEST_CONNECTED = 'largest_connected'
    LEXICOGRAPHIC = 'lexicographic'

class TiebreakToken(str, Enum):                   # v5
    MOST_TERRITORIES = 'most_territories'
    MOST_TOTAL_DICE = 'most_total_dice'
    LARGEST_CONNECTED = 'largest_connected'
    LOWEST_PLAYER_ID = 'lowest_player_id'
```

### Static Map (layout sent once)

```python
@dataclass(frozen=True)
class Position:
    x: int  # ≥ 0
    y: int  # ≥ 0

@dataclass(frozen=True)
class BorderSegment:
    start: Position
    end: Position

@dataclass(frozen=True)
class TerritoryLayout:
    id: 'TerritoryID'
    name: str
    tiles: List[Position]
    adjacencies: List['TerritoryID']
    border: List[BorderSegment]

@dataclass(frozen=True)
class MapLayout:
    map_name: str
    dimensions: Position               # (width, height)
    territories: Dict['TerritoryID', TerritoryLayout]
    grid_lookup: List[List[int]]       # grid[y][x] → territory_id or -1
```

### Dynamic State (sent every turn)

```python
@dataclass(frozen=True)
class TerritoryState:
    owner_id: 'PlayerID'
    dice_count: int  # 1..config.max_dice_per_territory

@dataclass(frozen=True)
class PlayerInfo:
    id: 'PlayerID'
    name: str
    color: 'ColorHex'
    owned_territory_ids: List['TerritoryID']
    total_dice: int
    supply_dice: int  # active+SUPPLY: equals CoreState.supply_remaining; else next award (or 0)
    is_alive: bool
    largest_connected_region: int

@dataclass(frozen=True)
class GameState:
    active_player_id: 'PlayerID'
    turn_number: int                  # increments when a NEW alive player enters ATTACK
    winner_id: Optional['PlayerID']
    territories: Dict['TerritoryID', TerritoryState]
    players: List[PlayerInfo]
    phase: GamePhase
    # Note: `tick_id` is not embedded here; it is returned alongside results
    # to keep GameState transport minimal. Use `ActionResult.tick_id`.
```

### Actions

```python
@dataclass(frozen=True)
class Action:
    player_id: 'PlayerID'

@dataclass(frozen=True)
class AttackAction(Action):
    attacker_territory_id: 'TerritoryID'
    defender_territory_id: 'TerritoryID'
    attack_index: int  # v5: index into AttackPairs.pairs

@dataclass(frozen=True)
class EndTurnAction(Action):
    pass

@dataclass(frozen=True)
class DistributeSupplyAction(Action):
    placements: Dict['TerritoryID', int]  # per-territory dice additions (v5: all values > 0)

@dataclass(frozen=True)
class PenaltyAction(Action):  # v5: new action type
    reason: 'PenaltyReason'  # 'timeout' | 'invalid_action'
```

**Validation (engine MUST enforce)**

* **AttackAction**: active owns `src`; `dst` adjacent & enemy; `dice[src] ≥ 2`; `phase == ATTACK`.
  * `attack_index` MUST equal `attack_pairs.index_map[(attacker_territory_id, defender_territory_id)]` at this tick.
* **EndTurnAction**: allowed in ATTACK; allowed in SUPPLY **iff** `ALLOW_EARLY_END` or `supply_remaining == 0` or supply-exhaustion rule.
* **DistributeSupplyAction**:

  * `sum(placements) == supply_remaining` for `MUST_PLACE_ALL`; otherwise `<=` for `ALLOW_EARLY_END`.
  * every value `add > 0` (zero entries are invalid and rejected).
  * every key owned by `player_id`; `dice[t] + add ≤ max_dice_per_territory`.
  * apply per-die in deterministic micro-order; reject whole action on any violation; **no partial** mutations.

### Turn Context

```python
@dataclass(frozen=True)
class SupplyDescriptor:
    supply_remaining: int
    eligible_territories: List['TerritoryID']
    per_territory_cap: int
    can_end_early: bool

@dataclass
class TurnContext:
    game_state: GameState
    valid_actions: List[Action]      # deterministic order; see rules above
    current_player_id: 'PlayerID'
    supply: Optional[SupplyDescriptor] = None
```

**Deterministic enumeration**

* **ATTACK**: all mask-legal `AttackAction`s in `attack_pairs.pairs` order, then one `EndTurnAction`.
* **SUPPLY**: **only** `EndTurnAction` when allowed; supply placements are **not** enumerated.
* **PenaltyAction**: never appears in `valid_actions`; it is a system action only (emitted via penalties).

### Action Result & Battle Result

```python
@dataclass
class BattleResult:
    attacker_player_id: 'PlayerID'
    defender_player_id: 'PlayerID'
    attacker_territory_id: 'TerritoryID'
    defender_territory_id: 'TerritoryID'
    attacker_dice_count: int
    defender_dice_count: int
    attacker_rolls: List[int]        # raw order (attacker first)
    defender_rolls: List[int]        # raw order
    attacker_wins: bool
    attacker_casualties: int
    defender_casualties: int
    post_attacker_source_dice: int
    post_defender_target_dice: int
    new_owner_id: 'PlayerID'
    dice_transferred: int
    attack_pair_index: int            # v5: mirrors AttackAction.attack_index

@dataclass
class ActionResult:
    success: bool
    new_game_state: GameState
    battle_result: Optional[BattleResult] = None
    supply_placements: Optional[Dict['TerritoryID', int]] = None
    error_code: Optional[InvalidAction] = None
    error_message: Optional[str] = None
    error_data: Optional[Dict[str, Any]] = None       # v5: machine-readable context
    tick_id: 'TickID' = 0                             # v5: wire format is decimal string
    state_hash: 'Hash64' = 0                          # v5: wire format is decimal string
    position_hash: 'Hash64' = 0                       # v5: NOW REQUIRED (not Optional)
    delta: Optional['StateDeltaWire'] = None          # v5: OPTIONAL, guarded by capability
```

### Game Config

```python
@dataclass(frozen=True)
class GameConfig:
    name: str
    map_layout: MapLayout
    max_players: int
    min_players: int
    max_dice_per_territory: int
    initial_dice_per_territory: int
    max_supply_dice: int
    supply_dice_calculation: Literal['largest_connected','territory_count']
    battle_system: BattleSystem
    supply_policy: SupplyPolicy
    turn_timeout_seconds: Optional[int]  # None disables timeouts entirely; when set, timeouts fire
                                         # per player at the start of their decision window.
    timeout_policy: TimeoutPolicy
    max_turns: Optional[int]          # if set, reaching this cap ends the game at the moment a NEW alive
                                      # player would enter ATTACK; engine sets phase=GAME_OVER and winner by
                                      # policy (see WinnerPolicy below).
    winner_policy: WinnerPolicy = WinnerPolicy.NONE  # v5: deterministic winner selection
    winner_tiebreak_chain: List['TiebreakToken'] = field(default_factory=lambda: [  # v5
        TiebreakToken.MOST_TERRITORIES, TiebreakToken.MOST_TOTAL_DICE, 
        TiebreakToken.LARGEST_CONNECTED, TiebreakToken.LOWEST_PLAYER_ID
    ])
    random_seed: Optional[int]
    created_timestamp: 'TimestampISO8601'
    schema_version: 'SchemaVersion'
    rules_version: 'RulesVersion'
```

---

## Max-Turns Winner Policy (v5, deterministic)

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

**Allowed tiebreak tokens:** See `TiebreakToken` enum above.  
Engines **MUST** validate `winner_tiebreak_chain` contains only valid `TiebreakToken` values (duplicates allowed).

---

## Core Internals (typed) — RL & determinism (informative, not public)

```python
@dataclass(frozen=True)
class AttackPairs:
    pairs: List[Tuple['TerritoryID', 'TerritoryID']]
    hash64: 'Hash64'
    index_map: Dict[Tuple['TerritoryID', 'TerritoryID'], int]
    # Canonical order: lexicographic ascending by (src, dst).
    # Hash64: XXH3_64 over the byte stream of pairs encoded as
    # [int32_le(src), int32_le(dst)] repeated in that order.

@dataclass(frozen=True)
class ActionMasks:
    attack: 'np.ndarray'          # shape=(len(attack_pairs),), dtype=bool
    place_one_die: 'np.ndarray'   # shape=(num_territories,), dtype=bool
    can_end_turn: bool

@dataclass(frozen=True)
class RNGStream:
    name: Literal['setup','turn','battle']
    seed: int
    counter: int

@dataclass(frozen=True)
class CoreState:
    active_player_id: 'PlayerID'
    turn_number: int
    phase: GamePhase
    winner_id: Optional['PlayerID']
    owners: 'np.ndarray'          # (T,), int32
    dice: 'np.ndarray'            # (T,), int16
    supply_remaining: int
    player_alive: 'np.ndarray'    # (P,), bool
    largest_connected: 'np.ndarray'  # (P,), int32
    territory_counts: 'np.ndarray'   # (P,), int32
    rng_counters: Dict[str, int]
    tick_id: 'TickID'

@dataclass(frozen=True)
class CoreAction:
    kind: Literal['attack','place_one_die','end_turn']
    attack_index: Optional[int] = None
    territory_id: Optional['TerritoryID'] = None

@dataclass(frozen=True)
class StateDelta:
    changed_territories: List['TerritoryID']
    new_owners: 'np.ndarray'
    new_dice: 'np.ndarray'
    phase_changed: bool
    new_phase: Optional[GamePhase]
    turn_advanced: bool
    new_turn: Optional[int]
    game_ended: bool
    winner: Optional['PlayerID']

@dataclass(frozen=True)
class StepInfo:
    battle_result: Optional['BattleResult']
    rng_counters: Dict[str, int]
    tick_id: 'TickID'
    state_hash: 'Hash64'
    delta: Optional['StateDelta']
```

---

## Capabilities Discovery

```python
def get_capabilities(self) -> dict[str, object]
```

**Payload (minimum)**

* `rules_version: str`, `schema_version: str`
* `layout_hash: Hash64`, `action_index_hash: Hash64`  — **wire:** decimal strings (`"uint64"`)
* `num_territories: int`, `num_attack_pairs: int`
* `battle_system: str`, `supply_policy: str`, `max_dice_per_territory: int`
* `winner_policy: str`, `winner_tiebreak_chain: list[str]`, `max_turns: int | None`
* `supports_delta: bool`
* `rng_streams: list[str]`  (e.g., `["setup","turn","battle"]`)
* `wire_schemas: dict[str, str]` (schema name → version/hash for files under `transport/json/schema/`)
* `uint64_encoding: str`  # v5: "decimal_string" for JS safety

**Client rule**: compare `action_index_hash` before loading RL policies trained on a specific map.

**Delta note (v4)**: `supports_delta` is **informative** in v4. Delta transport is not part of the
stable public response types yet; it may be surfaced in a later version via an opt-in field.

---

## Delta Transport (v5 preview; optional)

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

**StateDeltaWire definition:**

```python
@dataclass
class StateDeltaWire:
    changed_territories: List['TerritoryID']
    new_owners: List['PlayerID']
    new_dice: List[int]
    phase_changed: bool
    new_phase: Optional['GamePhase']
    turn_advanced: bool
    game_ended: bool
    winner_id: Optional['PlayerID']
```

**Delta invariants:** `len(changed_territories) == len(new_owners) == len(new_dice)`.

---

## Replay Header (v5, self-describing logs)

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

## Conformance & Golden Tests

1. **Determinism** — same seed + same high-level action sequence → identical `tick_id`, `state_hash`, and `rng_counters` after **every** action.
2. **Mask soundness** — every enumerated action is mask-legal; every mask-legal attack appears in order.
3. **Supply exhaustion** — with `MUST_PLACE_ALL` and no eligible cells, SUPPLY must allow `EndTurnAction`.
4. **Timeout policy** — `on_turn_timeout` fires; `apply_penalty(TIMEOUT)` advances `tick_id` by **exactly 1** and consumes **no RNG** (both policies).
5. **Bulk supply determinism** — repeating the same `DistributeSupplyAction` yields identical micro-order and `state_hash`.
6. **Hash cross-platform** — `state_hash` and `position_hash` match `tests/fixtures/hash_vectors.jsonl` on Linux/macOS, 64/32-bit.
7. **Property tests** — invariants via Hypothesis in `tests/property/`:

   * adjacency symmetry; no self-loops
   * dice bounds never violated
   * masks ↔ actions round-trip (ATTACK)
   * tick monotonicity and conservation rules
   * penalties never consume RNG
8. **ViewModel snapshot** — `to_render_state(game_state)` produces a stable JSON blob
   (round floats) across platforms; guards deterministic drawing.
9. **ASCII golden** — tiny 6-territory map renders to a fixed ASCII board.
10. **Observer wiring** — sequence: `on_game_start` → N×`on_action_executed` → `on_game_end`.
11. **Invalid action callback** — submitting an illegal action emits `on_invalid_action` exactly once,
    does **not** advance `tick_id`, and only advances `tick_id` if a configured penalty is applied.
12. **Penalty event order** — for a rejected action followed by a penalty, the order is
    `on_invalid_action` → `on_action_executed`(penalty) → (optional) `on_turn_start` of the next player.

---

## Validation Matrix (engine MUST enforce)

Checks the engine MUST enforce at runtime.

### A) Always true
* IDs in range and contiguous as above
* `phase ∈ {SETUP, ATTACK, SUPPLY, GAME_OVER}`
* `phase == GAME_OVER` ⇒ no further player decisions requested
* `TurnContext.current_player_id == GameState.active_player_id`
* `TurnContext` shape by phase: `ATTACK ⇒ supply is None`, `SUPPLY ⇒ supply is not None`
* For any **applied** action: `action.player_id == GameState.active_player_id`
* Client-submitted `PenaltyAction` via `apply_action` **MUST** be rejected with `error_code = bad_payload`.
* **After GAME_OVER**: `apply_action(...)` and `apply_penalty(...)` **MUST** return `success:false`, `error_code:bad_phase`, and **must not** change state or `tick_id`.
* **After GAME_OVER**: `get_turn_context()` **MAY** be called; return a context with `phase:game_over`, `valid_actions:[]`, `supply:null`.

### B) ATTACK: valid-actions enumeration
* `valid_actions` lists **all** mask-legal `AttackAction`s in **`attack_pairs.pairs` order**
* `EndTurnAction` appears **exactly once** iff `masks.can_end_turn == True`
* No duplicates; every listed action is mask-legal **at this tick**
* **SUPPLY**: placements are **not** enumerated; at most one `EndTurnAction` when allowed

### C) Tick & RNG
* **Success**: `tick_id` advances per rules; `state_hash` and RNG counters match the post-state
* **Reject** (`success == False`): no change to state, `tick_id`, `state_hash`, or RNG counters
* **Reject**: `position_hash` is still present and equals the pre-action `position_hash`.
* **Penalty**: `tick_id += 1`; **no RNG** consumed
* Tick advance rules: `AttackAction` +1; `EndTurnAction` +1; `DistributeSupplyAction` placing `K` dice ⇒ +`K`; reads/housekeeping ⇒ +0

### D) Phase-specific action validity
**D1. AttackAction**
* Preconditions: `phase == ATTACK`; attacker owned by active; defender owned by opponent; defender adjacent; attacker dice ≥ 2
* Postconditions (AUTO_ALL_BUT_ONE): `BattleResult` present and coherent; board updated; if conquest, ownership/dice transfer per rules; next `TurnContext` consistent (`owned_territory_ids`, `total_dice`)

**D2. EndTurnAction**
* Valid in `ATTACK`
* Valid in `SUPPLY` iff `(supply_policy == ALLOW_EARLY_END) or (supply_remaining == 0) or (supply_exhaustion_rule_triggers)`
* Applying performs **one** atomic mutation (tick +1) and advances phase/turn

**D3. DistributeSupplyAction**
* Preconditions: `phase == SUPPLY`; keys ⊆ owned; each `add > 0` (v5: no zero values) and `dice[t] + add ≤ max_dice_per_territory`; sum rule → `Σ add == supply_remaining` if `MUST_PLACE_ALL`, else `Σ add ≤ supply_remaining`
* Application: expand to **single-die** placements in **deterministic** order (by ascending `territory_id`, one die at a time); re-validate mask at each micro-step; on any violation → **reject entire action** (no partial mutation)
* Success: `supply_placements` echoes request; `tick_id` is after the final micro-step; end of SUPPLY discards unused dice (if any) and hands off to next player's ATTACK

### E) Map/graph invariants
* Adjacency symmetric and loop-free
* `attack_pairs.pairs` is the canonical, globally sorted list of directed edges; `index_map` consistent
* `get_capabilities().action_index_hash == AttackPairs.hash64`

### F) Observer & lifecycle
* `on_turn_start` fires **only** when a **new alive player** enters **ATTACK**
* `on_action_executed` fires for **every** successful high-level action, including penalties and aggregated supply
* `on_supply_distributed` fires after a successful bulk supply application

### G) ActionResult coherence
* `ActionResult.new_game_state`, `tick_id`, and `state_hash` equal the engine's post-mutation values
* If a battle occurred: `ActionResult.battle_result` is present and matches the applied board changes

### H) v5 Additions
* **Wire**: `tick_id`/hashes are decimal strings matching `"format":"uint64"`
* **Attack enumeration**: `attack_index` present and matches `attack_pairs.pairs` order
* **Penalty**: a penalty produces an observable `PenaltyAction` via `on_action_executed`
* **Supply**: `placements` values are strictly `> 0`
* **Skip-turn eliminated**: no auto-skip tick later; skip flag cleared; no `on_turn_start`
* **Turn number**: does not change on SUPPLY or penalty unless a **new alive** player enters ATTACK
* **ActionResult**: always includes `position_hash`
* **Schemas**: `additionalProperties:false` for all payloads

---

## Minimal Client Pseudocode (SUPPLY-safe)

```python
def get_action(ctx: TurnContext) -> Action:
    if ctx.game_state.phase == GamePhase.ATTACK:
        # v5: Choose from ctx.valid_actions; attacks include .attack_index for RL agents
        return pick_from(ctx.valid_actions)  # attacks or EndTurnAction

    # SUPPLY
    s = ctx.supply
    assert s is not None
    if s.can_end_early or s.supply_remaining == 0:
        return EndTurnAction(player_id=ctx.current_player_id)

    placements = my_policy(s.eligible_territories, s.supply_remaining, s.per_territory_cap)
    # v5: Ensure all placements > 0
    placements = {t:n for t,n in placements.items() if n > 0}
    return DistributeSupplyAction(player_id=ctx.current_player_id, placements=placements)
```

---

## Implementation Checklist (for the repo)

* [ ] `dicewars.api.*` re-exports only stable symbols; `import dicewars as dw` works.
* [ ] `GameEngine.__init__(config)` + `get_capabilities()` implemented.
* [ ] **SUPPLY**: not enumerated; enforce deterministic per-die micro-order; v5: reject zero values.
* [ ] **Ticks**: ATTACK +1; END\_TURN +1; SUPPLY K dice ⇒ +K; penalty +1; invalid 0.
* [ ] **Penalties**: implement `AUTO_END_TURN` and `SKIP_NEXT_TURN`; no RNG; emit `on_action_executed` with `PenaltyAction` (v5).
* [ ] **Observer**: `on_turn_start` only when entering ATTACK for a new active player; keep `on_supply_distributed`.
* [ ] **RNG**: separate streams; attacker rolls first; one value per die.
* [ ] **Hashes**: XXH3\_64; `state_hash` vs `position_hash` semantics; add `tests/fixtures/hash_vectors.jsonl`.
* [ ] **Capabilities**: include layout/action hashes, counts, rules knobs, streams, optional `wire_schemas`, `uint64_encoding` (v5).
* [ ] **Tests**: golden determinism/penalties/supply; property tests for invariants; v5: uint64 JS round-trip.
* [ ] **Schemas**: add `transport/json/schema/*.json` and reference in capabilities; v5: `additionalProperties:false`.
* [ ] **UI**: `ui/viewmodel/transform.py` + basic GUI/CLI observers; `scripts/run_gui.py`, `run_cli.py`, `preview_map.py`.
* [ ] **NumPy dtypes (v5)**: Pin `owners:int32`, `dice:int16` to avoid hash drift.
* [ ] **Entry points** (optional):
  ```
  # pyproject.toml
  [project.scripts]
  dicewars-cli = "dicewars.ui.cli.app:main"
  dicewars-gui = "dicewars.ui.gui.app:main"
  dicewars-preview-map = "dicewars.scripts.preview_map:main"
  ```

---

## UI & Visualization Layer (informative)

### Design goals
* Keep the **core headless and deterministic**; UI is a thin, replaceable skin.
* Render **immediately** when the map exists (`on_game_start`).
* Subsequent frames are a pure function of `(last_action, new_game_state)`.

### Render model (internal)
```python
@dataclass(frozen=True)
class RenderTerritory:
    id: int
    polygon: list[tuple[int,int]]      # screen-space points
    centroid: tuple[float,float]
    owner_id: int
    dice_count: int
    is_eligible_for_supply: bool

@dataclass(frozen=True)
class RenderState:
    turn_number: int
    phase: str
    active_player_id: int
    winner_id: int | None
    territories: list[RenderTerritory]
    players: list[dict]                # id, name, color, total_dice, largest_connected_region
    last_action: dict | None
    hint_attack_pairs: list[tuple[int,int]]  # optional
```

### Observer wiring (informative)
Concrete observers (e.g., a GUI or CLI) **are examples only** and **not part of the public API**.
They should subscribe to `on_game_start` (first paint using `MapLayout`) and re-render on
`on_action_executed` using the authoritative `ActionResult.new_game_state`.
Keep such implementations in `src/dicewars/ui/*` or `examples/` and **do not** treat them
as stable interfaces.

### Map preview (no match)
Use `scripts/preview_map.py` to open the GUI with just `MapLayout` for designers.

---
