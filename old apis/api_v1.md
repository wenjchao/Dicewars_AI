# Dice Wars AI — Final API Design (Phase 1, RL‑ready Core Internals)

> **Purpose**
> A small, stable public API for gameplay + a slim, atomic core for RL. This version fixes two foot‑guns:
>
> 1. **Player contract & SUPPLY enumeration** are now explicit and unambiguous.
> 2. **Tick semantics** are reworded with a single definition that covers actions, penalties, and multi‑step supply.
>
> Everything else is tightened for determinism, replayability, and easy client implementation.

## Repository & Package Layout (authoritative)

> The filesystem layout **is part of the API**: public symbols live under `dicewars.api.*` and are stable; internals live under `dicewars.core.*` and may change.

```
dicewars-ai/
├── src/
│   └── dicewars/
│       ├── __init__.py                 # re-export of public surface (from dicewars.api)
│       ├── __about__.py                # __version__, RULES_VERSION, SCHEMA_VERSION
│       ├── api/                        # ✅ Stable public contracts (import from here)
│       │   ├── __init__.py             # defines __all__; re-exports stable names
│       │   ├── types.py                # DTOs, Enums, type aliases (public)
│       │   ├── client.py               # PlayerClient interface (public)
│       │   ├── observer.py             # GameObserver interface (public)
│       │   ├── coordinator.py          # Coordinator contract (public signatures)
│       │   └── engine.py               # GameEngine public wrapper signatures
│       ├── engine/                     # Public wrapper implementation (thin)
│       │   └── public.py               # GameEngine class that wraps core
│       ├── coordinator/
│       │   ├── loop.py                 # turn loop; penalties; fan-out to observers
│       │   └── penalties.py            # penalty application helpers
│       ├── observers/
│       │   ├── base.py                 # logging/replay observers
│       │   └── replay.py               # JSONL replayer (M7)
│       ├── clients/
│       │   ├── base.py                 # PlayerClient ABC/examples
│       │   ├── random_bot.py           # baseline
│       │   └── heuristic_bot.py        # baseline
│       ├── core/                       # ❗Internal RL-friendly core (unstable)
│       │   ├── state.py                # CoreState; canonicalize; counters
│       │   ├── attack_pairs.py         # canonical (src,dst) list + hash
│       │   ├── actions.py              # CoreAction; masks; validators
│       │   ├── engine.py               # step(...), battle(...), supply micro-steps
│       │   ├── rng.py                  # Philox streams; splitmix; counters
│       │   ├── hash.py                 # state_hash/position_hash (BLAKE3 or XXH3)
│       │   └── delta.py                # optional delta mode
│       ├── wire/
│       │   └── json/
│       │       ├── schema/             # optional JSON Schemas
│       │       └── server.py           # optional stdio/ws bridge (M4)
│       └── utils/
│           └── typing.py               # shared aliases (if needed)
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/
│   │   ├── test_golden_determinism.py
│   │   └── test_golden_penalties.py
│   └── fixtures/
│       ├── capabilities.json
│       ├── rng_test_vectors.json
│       └── hash_vectors.jsonl
├── scripts/
│   ├── determinism_script.py
│   └── make_replay.py
└── docs/
    ├── roadmap.md
    ├── M0.md
    └── M1.md
```

**Import rule of thumb**

* ✅ Public clients import **only** from `dicewars.api.*` (stable).
* ⚠️ RL/engine development may import `dicewars.core.*` but must expect breaking changes.

**Top‑level export**
`import dicewars as dw` re‑exports the public API from `dicewars.api`.


---

## System Architecture Overview

Hub‑and‑spoke: the **GameCoordinator** orchestrates; **GameEngine** is authoritative; **PlayerClient** makes decisions; **GameObserver** watches.

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

* Validates rules and applies all state transitions
* Executes battles
* Determines win/loss
* **Pattern**: reactive only (never initiates calls)

### GameCoordinator (central orchestrator)

* Registers players and manages turn order
* Asks the engine for `TurnContext`, forwards to the active player
* Applies the returned action and broadcasts results to observers/players
* **Pattern**: active controller

### PlayerClient (player contract)

* Implements a single decision entry point: `get_action(context)`
* **Contract (final)**

  * **ATTACK phase**: You **must** return one of the enumerated `valid_actions` (typically many `AttackAction`s + one `EndTurnAction`).
  * **SUPPLY phase**: The coordinator **does not enumerate** placements. You **must either**

    1. return a **`DistributeSupplyAction`** whose placements conform to `context.supply` (allowed even though it is **not** listed in `valid_actions`), **or**
    2. return **`EndTurnAction`** *only if* `ALLOW_EARLY_END` or `supply_remaining == 0`.
  * Rationale: enumerating all supply allocations is combinatorial; we keep masks in the core and accept a single bulk placement in the public API.
* If a client violates the contract, the engine rejects the action; penalties are coordinated and all details are observable.

### GameObserver (passive watcher)

* Receives turn, action, battle, supply, and lifecycle events for logging/UI/analytics

---

## API Contracts

### GameCoordinator ⇄ PlayerClient

```python
get_action(context: TurnContext) -> Action
```

**Goal**: return exactly one decision for the current phase.

* **ATTACK**: choose one of `context.valid_actions` (attacks + end-turn)
* **SUPPLY**: return `DistributeSupplyAction(placements)` (not enumerated; validated against `context.supply`) **or** `EndTurnAction` when allowed

Lifecycle convenience:

```python
on_game_start(player_id: int, config: GameConfig) -> None
on_game_end(winner_id: int) -> None
on_battle_result(battle: BattleResult) -> None   # UX helper (same data is in observers)
```

> **Do/Don’t**
>
> * ✅ In SUPPLY, compute your own placements from `context.supply` and send one `DistributeSupplyAction`.
> * ❌ Don’t expect the engine to enumerate placements; the list would explode combinatorially.

---

### GameCoordinator → GameEngine (public service)

```python
initialize_game(player_ids: List[int]) -> None
```

**Goal**: build the initial state for the registered players.

```python
get_turn_context() -> TurnContext
```

**Goal**: obtain the active player’s view, the deterministically ordered `valid_actions`, and supply descriptor (when in SUPPLY).

```python
apply_action(action: Action) -> ActionResult
```

**Goal**: validate and apply a high‑level action.

* Validates `action.player_id == active_player_id`
* **ATTACK / END\_TURN**: one atomic step each
* **DistributeSupplyAction**: expanded internally into K atomic `place_one_die` steps in a deterministic order (see *Supply semantics*), returning a single aggregated `ActionResult` whose `tick_id` reflects the **final** atomic step

```python
apply_penalty(player_id: int, reason: PenaltyReason) -> ActionResult
```

**Goal**: apply configured penalties (e.g., timeout), mutate state exactly once, consume **no RNG**, and return the updated state.

> **No `is_game_over()`** — check `GameState.winner_id`.

---

### GameCoordinator → GameObserver

```python
on_turn_start(player_id: int, game_state: GameState) -> None
```

* Fired **only** when a **new** player enters **ATTACK** (i.e., the active player changes). Not fired between ATTACK↔SUPPLY for the same player.

```python
on_action_executed(action: Action, result: ActionResult) -> None
```

* Fired after each successful high‑level action (including aggregated supply). If a battle occurred, details are inside `result.battle_result`.

```python
on_invalid_action(player_id: int, action: Action, error_code: InvalidAction, error_message: str) -> None
on_turn_timeout(player_id: int, game_state: GameState) -> None
on_game_start(config: GameConfig, player_names: List[str]) -> None
on_game_end(winner_id: int, final_state: GameState) -> None
on_supply_distributed(player_id: int, placements: Dict[int,int], game_state: GameState) -> None
```

---

## Key DTOs

### Static map layout (sent once)

* `MapLayout{ map_name, dimensions, territories, grid_lookup }`
* `TerritoryLayout{ id, name, tiles, adjacencies, border }`
* Invariants: adjacencies are symmetric; no self‑loops; validated by `build_attack_pairs()`

### Dynamic state (sent every turn)

* `GameState{ active_player_id, turn_number, winner_id, territories, players, phase }`
* `TerritoryState{ owner_id, dice_count }`
* `PlayerInfo{ id, name, color, owned_territory_ids, total_dice, supply_dice, is_alive, largest_connected_region }`

  * When `player_id == active` **and** `phase == SUPPLY`: `supply_dice == CoreState.supply_remaining`

### Enums

* `GamePhase = { SETUP, ATTACK, SUPPLY, GAME_OVER }`
* `BattleSystem = { AUTO_ALL_BUT_ONE }`
* `InvalidAction = { ILLEGAL_ATTACK, OVER_SUPPLY_LIMIT, NOT_YOUR_TURN, BAD_PHASE, TERRITORY_NOT_OWNED, INSUFFICIENT_DICE }`
* `PenaltyReason = { TIMEOUT, INVALID_ACTION }`
* `SupplyPolicy = { MUST_PLACE_ALL, ALLOW_EARLY_END }`

### Actions

* `AttackAction{ player_id, attacker_territory_id, defender_territory_id }`
* `EndTurnAction{ player_id }`
* `DistributeSupplyAction{ player_id, placements: { territory_id: dice_to_add } }`

  * Validation rules:

    * `sum(placements) == supply_remaining` for `MUST_PLACE_ALL`
    * `sum(placements) <= supply_remaining` for `ALLOW_EARLY_END`
    * All territories owned by `player_id`; each obeys `current_dice + add <= max_dice_per_territory`
    * **Whole‑action atomicity**: on any violation, **reject entirely** with `OVER_SUPPLY_LIMIT` (no partial application)

### BattleResult (self‑contained)

* Includes pre‑battle participants & dice, per‑side rolls, outcome, casualties, and post‑battle dice/ownership including `dice_transferred` (AUTO\_ALL\_BUT\_ONE rules)

### GameConfig

* Includes map, player counts, dice caps, supply calculation mode, battle system, supply policy, timeouts, max turns, RNG seed, and version metadata
* **Supply award note**: `max_supply_dice` caps the **per‑turn award** at the start of SUPPLY. Unused dice **do not** carry over between turns.

### TurnContext

* `game_state`: the current snapshot
* `valid_actions` (deterministic order):

  * **ATTACK**: all mask‑legal `AttackAction`s in `attack_pairs.pairs` order **then** one `EndTurnAction`
  * **SUPPLY**: **only** `EndTurnAction` when allowed (**no** enumeration of placements)
* `current_player_id`: convenience mirror of `game_state.active_player_id`
* `supply` (only in SUPPLY):

  * `supply_remaining`: dice to place
  * `eligible_territories`: owned territories with room (`dice < max`)
  * `per_territory_cap`: equals `config.max_dice_per_territory`

> **Why no supply enumeration?** It’s exponential in map size. We expose masks in the core and accept a single bulk placement at the public layer.

### ActionResult

* `success: bool`
* `new_game_state: GameState` (unchanged if failed)
* `battle_result: Optional[BattleResult]`
* `supply_placements: Optional[Dict[int,int]]` (echo of applied placements)
* `error_code, error_message`
* `tick_id: int` — see **Tick semantics**
* `state_hash: int` — 64‑bit canonical hash of the resulting state

---

## Communication Flow (reference)

1. **Registration** → `initialize_game` → lifecycle `on_game_start`

2. **Loop while `winner_id is None`**

* (a) Coordinator asks Engine: `ctx = get_turn_context()`
* (b) **Timeout guard** (if the player stalls): fire `on_turn_timeout`, then `apply_penalty(TIMEOUT)` and continue
* (c) Fire `on_turn_start` **iff** a new player just entered ATTACK
* (d) Coordinator asks player: `action = get_action(ctx)`
* (e) Coordinator applies: `result = apply_action(action)`
* (f) Broadcast results: `on_action_executed`; `on_battle_result` if present; `on_supply_distributed` if placements occurred

3. **Game end** → `on_game_end`

---

## **Tick semantics (final, unambiguous)**

> **Definition**: `tick_id` is a monotonically increasing counter of **atomic core steps**. A core step is one successful invocation of the engine’s internal `step(...)` that **changes state**.

**Rules**

1. **Increment once per atomic state mutation**. No increment on rejected/invalid actions (state unchanged).
2. **ATTACK** → 1 atomic step → `tick_id += 1`.
3. **END\_TURN** → 1 atomic step → `tick_id += 1`.
4. **DistributeSupplyAction** with total K dice placed → **K atomic `place_one_die` steps** → `tick_id += K`.

   * The single returned `ActionResult.tick_id` is the counter **after the final placement**.
5. **Penalty application** (e.g., TIMEOUT) → exactly **1** atomic step → `tick_id += 1` (and **must not** consume RNG).
6. Any internal housekeeping that does **not** change state must **not** advance `tick_id`.

**Deterministic supply micro‑order**

* When applying `DistributeSupplyAction(placements)`, the engine expands it into single‑die placements in this fixed order to guarantee replayability:

  1. Sort `placements.items()` by ascending `territory_id`.
  2. For each `(territory_id, dice_to_add)` in that order, place **one die at a time**, repeating `dice_to_add` times.
  3. Validate the per‑die mask at each micro‑step (ownership/cap not violated).
* The aggregated `supply_placements` echoes the caller’s requested totals (on success). On any violation, reject the entire action and **do not** change state.

---

## Engine Core (RL‑friendly internals)

> Internal only; not exposed to Coordinator/Players. The public service wraps this.

**AttackPairs (stable action indices)**

* Canonical list `pairs[(src,dst), ...]`, sorted by `(src_id, dst_id)`
* `hash64` for dataset/model compatibility checking

**CoreState (dense arrays)**

* `owners[num_territories]`, `dice[num_territories]`
* `active_player_id, phase, turn_number, winner_id`
* `supply_remaining`, `player_alive[num_players]`
* Cached: `largest_connected[num_players]`, `territory_counts[num_players]`
* Repro: `rng_counters{"setup","turn","battle"}`, `tick_id`

**ActionMasks**

* `attack[len(attack_pairs)]`, `place_one_die[num_territories]`, `can_end_turn`
* Mask rules match public semantics; used for RL action masking

**CoreAction primitives**

* `{"attack", "place_one_die", "end_turn"}` with indices/ids

**Step(...) → (CoreState, StepInfo)**

* Applies one atomic step, updates `rng_counters`, recomputes `state_hash`, increments `tick_id`

**RNG streams**

* Split seeded streams; **battle** stream consumes 1 value per die, **attacker** rolls first, then **defender**

**Canonicalization**

* Remap so the active player is always 0 for RL consistency; keep reversible permutations

**Delta mode (optional)**

* Minimal change set between states for efficient synchronization

---

## Integration: GameEngine public wrapper

* Holds `attack_pairs` and `core_state`
* `get_turn_context()` converts masks → enumerated actions (ATTACK) and builds `SupplyDescriptor` (SUPPLY)
* `_masks_to_actions(masks)` **contract**:

  * enumerate all mask‑legal attacks in `attack_pairs.pairs` order
  * append **one** `EndTurnAction` **iff** `masks.can_end_turn` is `True`
  * **never** enumerate supply placements

---

## Capabilities Discovery

Report versioning and static hashes so GUIs, log replayers, and RL models can assert compatibility:

* `rules_version, schema_version`
* `layout_hash` (canonical map bytes)
* `action_index_hash` (from `AttackPairs.hash64`)
* counts: territories, attack pairs
* current rules:

  * `battle_system`, `supply_policy`, `max_dice_per_territory`
* `supports_delta`, `rng_streams`

---

## Conformance & Golden Tests

1. **Determinism** — same seed + same high‑level action sequence → identical `tick_id` and `state_hash` after **every** action
2. **Mask soundness** — every enumerated action is mask‑legal; every mask‑legal attack appears in order
3. **Supply exhaustion** — with `MUST_PLACE_ALL` and no eligible cells, SUPPLY must allow `EndTurnAction`
4. **Timeout policy** — `on_turn_timeout` fires; `apply_penalty(TIMEOUT)` advances `tick_id` by **exactly 1** and consumes **no RNG**
5. **Bulk supply determinism** — repeating the same `DistributeSupplyAction` yields identical per‑die micro‑order and `state_hash`

---

## FAQ (common traps we eliminated)

* **“Why isn’t my `DistributeSupplyAction` in `valid_actions`?”**
  Because it’s not enumerated by design. You can always submit it in SUPPLY; the engine validates against `context.supply`.

* **“When does `turn_number` increment?”**
  When entering **ATTACK** for the **next alive player** (i.e., on active‑player change). It does **not** change within a player’s ATTACK↔SUPPLY cycle.

* **“What advances `tick_id`?”**
  Only atomic state mutations (core steps): ATTACK, END\_TURN, per‑die SUPPLY placements, and penalty application. Invalid actions and pure reads do not.

* **“Do unused supply dice carry over?”**
  No. `max_supply_dice` caps **per‑turn award**; unplaced dice are discarded when the player ends SUPPLY (or when MUST\_PLACE\_ALL meets an unsatisfiable board and we allow end‑turn via supply exhaustion rule).

---

## Minimal Client Pseudocode (SUPPLY safe)

```python
def get_action(ctx):
    if ctx.game_state.phase == ATTACK:
        return pick_from(ctx.valid_actions)  # attacks or EndTurnAction

    # SUPPLY
    s = ctx.supply
    if s.supply_remaining == 0 or can_end_early(ctx):
        return EndTurnAction(player_id=ctx.current_player_id)

    placements = my_placement_policy(s.eligible_territories, s.supply_remaining, s.per_territory_cap)
    return DistributeSupplyAction(player_id=ctx.current_player_id, placements=placements)
```

That’s it: one decision function, no enumeration explosion, deterministic internals, and crystal‑clear ticks.

---

# **Typed Interface Reference (authoritative)**

This section gives **explicit types** for every public function, callback, DTO, and core structure, plus a JSON wire representation. Python typing is used for clarity; the wire format is language‑neutral JSON.

## Type System & Conventions

**Primitive aliases**

* `PlayerID = int`  (≥ 0)
* `TerritoryID = int`  (≥ 0, contiguous 0..N-1)
* `TickID = int`  (monotonic, fits 64‑bit signed)
* `Hash64 = int`  (0..2^64-1)
* `ColorHex = str`  ("#RRGGBB")
* `TimestampISO8601 = str`  (RFC3339, e.g., "2025-08-23T17:00:00Z")
* `RulesVersion = str`
* `SchemaVersion = str`

**JSON wire conventions**

* Keys use `snake_case`.
* Enums serialize as lowercase strings.
* Integers are decimal JSON numbers; no NaN/Infinity.
* Lists are ordered arrays; ordering is normative wherever stated.
* All DTOs are fully serializable; no object references.

**Numeric constraints** (engine MUST enforce)

* `max_dice_per_territory >= 1`
* `initial_dice_per_territory in [1, max_dice_per_territory]`
* `supply_remaining >= 0`
* `dice_count in [1, max_dice_per_territory]`

---

## Public Service API (GameCoordinator → GameEngine)

```python
from typing import List, Dict, Optional, Literal, Union, Tuple

# Registration lives on the Coordinator; shown here with types for completeness.
def register_player(client: 'PlayerClient', name: str, player_type: Literal['human','random_ai','rule_based_ai','other']) -> PlayerID: ...

class GameEngine:
    def initialize_game(self, player_ids: List[PlayerID]) -> None: ...

    def get_turn_context(self) -> 'TurnContext': ...

    def apply_action(self, action: 'Action') -> 'ActionResult': ...

    def apply_penalty(self, player_id: PlayerID, reason: 'PenaltyReason') -> 'ActionResult': ...
```

**Return/Argument types**

* `initialize_game`: **input** list of `PlayerID`; **output** `None`.
* `get_turn_context`: **output** `TurnContext`.
* `apply_action`: **input** `Action` (`AttackAction | DistributeSupplyAction | EndTurnAction`); **output** `ActionResult`.
* `apply_penalty`: **input** `PlayerID`, `PenaltyReason`; **output** `ActionResult`.

---

## PlayerClient Interface (GameCoordinator ⇄ PlayerClient)

```python
class PlayerClient:
    def get_action(self, context: 'TurnContext') -> 'Action': ...

    # Lifecycle (optional but recommended)
    def on_game_start(self, player_id: PlayerID, config: 'GameConfig') -> None: ...
    def on_game_end(self, winner_id: Optional[PlayerID]) -> None: ...
    def on_battle_result(self, battle: 'BattleResult') -> None: ...
```

**`get_action` contract**

* **Input**: `TurnContext`
* **Output**: `Action`

  * ATTACK → one of `context.valid_actions`
  * SUPPLY → `DistributeSupplyAction` **or** `EndTurnAction` when allowed (not enumerated)

---

## Observer Interface (GameCoordinator → GameObserver)

```python
class GameObserver:
    def on_turn_start(self, player_id: PlayerID, game_state: 'GameState') -> None: ...
    def on_action_executed(self, action: 'Action', result: 'ActionResult') -> None: ...
    def on_invalid_action(self, player_id: PlayerID, action: 'Action', error_code: 'InvalidAction', error_message: str) -> None: ...
    def on_turn_timeout(self, player_id: PlayerID, game_state: 'GameState') -> None: ...
    def on_game_start(self, config: 'GameConfig', player_names: List[str]) -> None: ...
    def on_game_end(self, winner_id: Optional[PlayerID], final_state: 'GameState') -> None: ...
    def on_supply_distributed(self, player_id: PlayerID, placements: Dict[TerritoryID, int], game_state: 'GameState') -> None: ...
```

---

## DTOs (Authoritative Types)

### Enums

```python
from enum import Enum

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

class PenaltyReason(str, Enum):
    TIMEOUT = 'timeout'
    INVALID_ACTION = 'invalid_action'

class SupplyPolicy(str, Enum):
    MUST_PLACE_ALL = 'must_place_all'
    ALLOW_EARLY_END = 'allow_early_end'
```

### Static Map

```python
from dataclasses import dataclass
from typing import List, Dict

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
    id: TerritoryID
    name: str
    tiles: List[Position]
    adjacencies: List[TerritoryID]
    border: List[BorderSegment]

@dataclass(frozen=True)
class MapLayout:
    map_name: str
    dimensions: Position              # (width, height)
    territories: Dict[TerritoryID, TerritoryLayout]
    grid_lookup: List[List[int]]      # grid[y][x] → territory_id or -1
```

### Dynamic State

```python
@dataclass(frozen=True)
class TerritoryState:
    owner_id: PlayerID
    dice_count: int  # 1..config.max_dice_per_territory

@dataclass(frozen=True)
class PlayerInfo:
    id: PlayerID
    name: str
    color: ColorHex
    owned_territory_ids: List[TerritoryID]
    total_dice: int
    supply_dice: int  # active+SUPPLY: equals CoreState.supply_remaining; else next award (or 0 if eliminated)
    is_alive: bool
    largest_connected_region: int

@dataclass(frozen=True)
class GameState:
    active_player_id: PlayerID
    turn_number: int                  # increments when a NEW player enters ATTACK
    winner_id: Optional[PlayerID]
    territories: Dict[TerritoryID, TerritoryState]
    players: List[PlayerInfo]
    phase: GamePhase
```

### Actions

```python
@dataclass(frozen=True)
class Action:
    player_id: PlayerID

@dataclass(frozen=True)
class AttackAction(Action):
    attacker_territory_id: TerritoryID
    defender_territory_id: TerritoryID

@dataclass(frozen=True)
class EndTurnAction(Action):
    pass

@dataclass(frozen=True)
class DistributeSupplyAction(Action):
    placements: Dict[TerritoryID, int]  # per‑territory dice additions
```

### Turn Context

```python
@dataclass(frozen=True)
class SupplyDescriptor:
    supply_remaining: int
    eligible_territories: List[TerritoryID]
    per_territory_cap: int

@dataclass
class TurnContext:
    game_state: GameState
    valid_actions: List[Action]      # deterministic order; see rules below
    current_player_id: PlayerID
    supply: Optional[SupplyDescriptor] = None
```

**Deterministic enumeration**

* ATTACK: all mask‑legal `AttackAction`s in `attack_pairs.pairs` order, then one `EndTurnAction`.
* SUPPLY: **only** `EndTurnAction` when allowed; supply placements are **not** enumerated.

### Action Result

```python
@dataclass
class BattleResult:
    attacker_player_id: PlayerID
    defender_player_id: PlayerID
    attacker_territory_id: TerritoryID
    defender_territory_id: TerritoryID
    attacker_dice_count: int
    defender_dice_count: int
    attacker_rolls: List[int]
    defender_rolls: List[int]
    attacker_wins: bool
    attacker_casualties: int
    defender_casualties: int
    post_attacker_source_dice: int
    post_defender_target_dice: int
    new_owner_id: PlayerID
    dice_transferred: int

@dataclass
class ActionResult:
    success: bool
    new_game_state: GameState
    battle_result: Optional[BattleResult] = None
    supply_placements: Optional[Dict[TerritoryID, int]] = None
    error_code: Optional[InvalidAction] = None
    error_message: Optional[str] = None
    tick_id: TickID = 0
    state_hash: Hash64 = 0
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
    turn_timeout_seconds: Optional[int]
    timeout_policy: Literal['auto_end_turn','skip_next_turn']
    max_turns: Optional[int]
    random_seed: Optional[int]
    created_timestamp: TimestampISO8601
    schema_version: SchemaVersion
    rules_version: RulesVersion
```

---

## Core Internals (typed) — RL & determinism

```python
@dataclass(frozen=True)
class AttackPairs:
    pairs: List[Tuple[TerritoryID, TerritoryID]]
    hash64: Hash64
    index_map: Dict[Tuple[TerritoryID, TerritoryID], int]

@dataclass(frozen=True)
class ActionMasks:
    attack: 'np.ndarray'      # shape=(len(attack_pairs),), dtype=bool
    place_one_die: 'np.ndarray'  # shape=(num_territories,), dtype=bool
    can_end_turn: bool

@dataclass(frozen=True)
class RNGStream:
    name: Literal['setup','turn','battle']
    seed: int
    counter: int

@dataclass(frozen=True)
class CoreState:
    active_player_id: PlayerID
    turn_number: int
    phase: GamePhase
    winner_id: Optional[PlayerID]
    owners: 'np.ndarray'     # (T,), int32
    dice: 'np.ndarray'       # (T,), int16
    supply_remaining: int
    player_alive: 'np.ndarray'  # (P,), bool
    largest_connected: 'np.ndarray'  # (P,), int32
    territory_counts: 'np.ndarray'   # (P,), int32
    rng_counters: Dict[str, int]
    tick_id: TickID

@dataclass(frozen=True)
class CoreAction:
    kind: Literal['attack','place_one_die','end_turn']
    attack_index: Optional[int] = None
    territory_id: Optional[TerritoryID] = None

@dataclass(frozen=True)
class StateDelta:
    changed_territories: List[TerritoryID]
    new_owners: 'np.ndarray'
    new_dice: 'np.ndarray'
    phase_changed: bool
    new_phase: Optional[GamePhase]
    turn_advanced: bool
    new_turn: Optional[int]
    game_ended: bool
    winner: Optional[PlayerID]

@dataclass(frozen=True)
class StepInfo:
    battle_result: Optional[BattleResult]
    rng_counters: Dict[str, int]
    tick_id: TickID
    state_hash: Hash64
    delta: Optional[StateDelta]
```

---

## JSON Wire Examples

**TurnContext (ATTACK)**

```json
{
  "game_state": {
    "active_player_id": 1,
    "turn_number": 7,
    "winner_id": null,
    "phase": "attack",
    "territories": {"12": {"owner_id": 1, "dice_count": 5}},
    "players": [
      {"id": 0, "name": "BotA", "color": "#3366CC", "owned_territory_ids": [3,8], "total_dice": 14, "supply_dice": 0, "is_alive": true, "largest_connected_region": 4},
      {"id": 1, "name": "BotB", "color": "#DC3912", "owned_territory_ids": [12], "total_dice": 9, "supply_dice": 0, "is_alive": true, "largest_connected_region": 3}
    ]
  },
  "valid_actions": [
    {"type": "attack", "player_id": 1, "attacker_territory_id": 12, "defender_territory_id": 9},
    {"type": "end_turn", "player_id": 1}
  ],
  "current_player_id": 1
}
```

**TurnContext (SUPPLY)**

```json
{
  "game_state": {"active_player_id": 1, "turn_number": 7, "winner_id": null, "phase": "supply", "territories": {}, "players": []},
  "valid_actions": [
    {"type": "end_turn", "player_id": 1}
  ],
  "current_player_id": 1,
  "supply": {
    "supply_remaining": 5,
    "eligible_territories": [2, 4, 7],
    "per_territory_cap": 8
  }
}
```

**DistributeSupplyAction (request) → ActionResult (response)**

```json
// request action (player → coordinator → engine)
{
  "type": "distribute_supply",
  "player_id": 1,
  "placements": {"2": 3, "4": 2}
}
```

```json
// response (engine → coordinator)
{
  "success": true,
  "new_game_state": {"phase": "supply", "active_player_id": 1, "turn_number": 7, "winner_id": null, "territories": {}, "players": []},
  "supply_placements": {"2": 3, "4": 2},
  "tick_id": 1432,
  "state_hash": 15465789324567891234
}
```

**Invalid ATTACK (example)**

```json
{
  "success": false,
  "new_game_state": {"phase": "attack", "active_player_id": 1, "turn_number": 7, "winner_id": null, "territories": {}, "players": []},
  "error_code": "illegal_attack",
  "error_message": "Defender not adjacent",
  "tick_id": 1432,
  "state_hash": 15465789324567891234
}
```

---

## Validation Matrix (engine MUST enforce)

* `AttackAction`: active owns `src`; `dst` is adjacent and enemy; `dice[src] >= 2`; `phase == ATTACK`.
* `EndTurnAction`: allowed in ATTACK; allowed in SUPPLY **iff** `ALLOW_EARLY_END` or `supply_remaining == 0` or supply‑exhaustion rule triggers.
* `DistributeSupplyAction`:

  * `sum(placements) == supply_remaining` for `MUST_PLACE_ALL`; otherwise `<=` for `ALLOW_EARLY_END`.
  * Every key is owned by the active player; `dice[t] + add <= max_dice_per_territory`.
  * Apply per‑die in deterministic micro‑order; reject whole action on any violation; **no partial** mutations.

---

## Version/Compatibility Surface

* `capabilities`: returns `{ rules_version, schema_version, layout_hash, action_index_hash, num_territories, num_attack_pairs, battle_system, supply_policy, max_dice_per_territory, supports_delta, rng_streams }`
* Clients **must** verify `action_index_hash` before loading RL policies trained on a specific map.

---

This completes the fully‑typed, wire‑ready API while preserving the lean public surface and RL‑friendly core.
