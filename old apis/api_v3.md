# Dice Wars AI — Final API Design (Phase 1, RL-ready Core Internals)

> **Purpose**
> A small, stable public API for gameplay + a slim, atomic core for RL.
> This version **fixes two foot-guns**:
>
> 1. **Player contract & SUPPLY enumeration** are explicit and unambiguous.
> 2. **Tick semantics** have a single precise definition covering actions, penalties, and multi-step supply.
>
> Everything else prioritizes determinism, replayability, and easy client implementation.

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
│       │   └── replay.py               # JSONL replayer (later milestone)
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
│   └── make_replay.py
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
* Applies the returned action and broadcasts results to observers/players.
* **Pattern**: active controller.

### PlayerClient (player contract)

* Single decision entry point: `get_action(context)`.

**Contract (final)**

* **ATTACK**: Return **one** of the enumerated `valid_actions` (multiple `AttackAction`s + one `EndTurnAction`).
* **SUPPLY**: The coordinator **does not enumerate** placements. You **must either**

  1. return a **`DistributeSupplyAction`** whose placements conform to `context.supply` (accepted even if **not** listed in `valid_actions`), **or**
  2. return **`EndTurnAction`** *only if* `SupplyPolicy == ALLOW_EARLY_END` **or** `supply_remaining == 0` **or** supply-exhaustion rule applies.

> Rationale: Enumerating all supply allocations is combinatorial; masks live in the core; the public API accepts a single bulk placement.

**Violation** → engine rejects; coordinator applies penalties; all observable.

### GameObserver (passive watcher)

* Receives turn, action, battle, supply, and lifecycle events for logging/UI/analytics.

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

* `initialize_game` builds initial state for the registered players.
* `get_turn_context` returns the active player’s view, the deterministic `valid_actions`, and the supply descriptor during SUPPLY.
* `apply_action` validates and applies a high-level action:

  * **ATTACK / END\_TURN**: one atomic step each.
  * **DistributeSupplyAction**: expanded into K atomic `place_one_die` steps in deterministic micro-order; returns a single aggregated `ActionResult` whose `tick_id` reflects the **final** micro-step.
* `apply_penalty` applies configured penalties (e.g., timeout), mutates state exactly once, consumes **no RNG**, returns updated state.
* `get_capabilities` exposes versioning and static hashes for compatibility checks.

> **No `is_game_over()`** — check `GameState.winner_id`.

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
* `on_action_executed` fires for every successful high-level action **including penalties** (explicit).

---

## Communication Flow (reference)

1. **Registration** → `initialize_game` → lifecycle `on_game_start`.
2. Loop while `winner_id is None`
   a) `ctx = get_turn_context()`
   b) **Timeout guard**: fire `on_turn_timeout`, then `apply_penalty(TIMEOUT)` and continue
   c) Fire `on_turn_start` **iff** a new player just entered ATTACK
   d) Ask player: `action = get_action(ctx)`
   e) Apply: `result = apply_action(action)`
   f) Broadcast: `on_action_executed`; `on_battle_result` if present; `on_supply_distributed` if placements occurred
3. **Game end** → `on_game_end`.

---

## **Tick Semantics (final, unambiguous)**

> **Definition**: `tick_id` is a monotonically increasing counter of **atomic core steps**.
> A core step is one successful invocation of the engine’s internal `step(...)` that **changes state**.

**Origin**: `tick_id` starts at **0** at game creation. It increments **after** each atomic state mutation.

**Rules**

1. Increment once **per atomic state mutation**. No increment on rejected/invalid actions (state unchanged).
2. **ATTACK** → 1 atomic step → `tick_id += 1`.
3. **END\_TURN** → 1 atomic step → `tick_id += 1`.
4. **DistributeSupplyAction** placing total K dice → **K atomic `place_one_die` steps** → `tick_id += K`.
   Returned `ActionResult.tick_id` is the counter **after the final placement**.
5. **Penalty application** → exactly **1** atomic step → `tick_id += 1` (**must not** consume RNG).
6. Internal reads/housekeeping that do **not** change state must **not** advance `tick_id`.

**Deterministic supply micro-order**

1. Sort `placements.items()` by ascending `territory_id`.
2. For each `(territory_id, dice_to_add)` in that order, place **one die at a time**, repeating `dice_to_add` times.
3. Validate the per-die mask at each micro-step. On any violation, reject the entire action (no partial mutation).

---

## Penalty Semantics (timeout & invalid action)

`TimeoutPolicy` in `GameConfig` controls behavior:

* **AUTO\_END\_TURN**: apply a single **end\_turn** mutation **now** (tick +1). Phase/turn advance accordingly. **No RNG** consumed.
* **SKIP\_NEXT\_TURN**: set a skip flag and advance to the next player **now** (tick +1). When the skipped player’s next turn would begin, the coordinator auto-skips via one mutation (tick +1). **No RNG** consumed for either mutation.

**Observer rule (explicit):** penalty mutations fire `on_action_executed` with their `ActionResult`.

---

## Hash Semantics (authoritative)

Two 64-bit hashes using **XXH3\_64** over a canonical byte stream (little-endian integers, canonical ordering as specified):

* **`state_hash`** (replay equivalence): includes dynamic board (`owners[]`, `dice[]`), meta (`active_player_id`, `phase`, `turn_number`, `winner_id`, `tick_id`), RNG counters for all streams, and layout/rules identity (`layout_hash`, `rules_version`, `schema_version`, `battle_system`, `supply_policy`, `max_dice_per_territory`).

* **`position_hash`** (dataset dedup): same as `state_hash` **minus** `tick_id` and **minus** `rng_counters`.

**Golden requirement:** identical inputs on any platform → identical hashes. Test vectors live in `tests/fixtures/hash_vectors.jsonl`.

---

## JSON Wire Conventions & Examples

* Keys use `snake_case`. Enums serialize as lowercase strings.
* Lists are ordered; ordering is normative wherever stated.
* Action union discriminated by `"type": "attack" | "end_turn" | "distribute_supply"`.

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
       "supply_dice": 0, "is_alive": true, "largest_connected_region": 4},
      {"id": 1, "name": "BotB", "color": "#DC3912",
       "owned_territory_ids": [12], "total_dice": 9,
       "supply_dice": 0, "is_alive": true, "largest_connected_region": 3}
    ]
  },
  "valid_actions": [
    {"type": "attack", "player_id": 1, "attacker_territory_id": 12, "defender_territory_id": 9},
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
 "territories": {}, "players": []}, "supply_placements": {"2": 3, "4": 2}, "tick_id": 1432,
 "state_hash": 15465789324567891234}
```

**Invalid ATTACK (example)**

```json
{"success": false, "new_game_state": {"phase": "attack", "active_player_id": 1, "turn_number": 7, "winner_id": null,
 "territories": {}, "players": []}, "error_code": "illegal_attack", "error_message": "Defender not adjacent",
 "tick_id": 1432, "state_hash": 15465789324567891234}
```

**Capabilities (example)**

```json
{
  "rules_version": "v1",
  "schema_version": "v1",
  "layout_hash": 7123456789012345678,
  "action_index_hash": 6234567890123456789,
  "num_territories": 42,
  "num_attack_pairs": 180,
  "battle_system": "auto_all_but_one",
  "supply_policy": "must_place_all",
  "max_dice_per_territory": 8,
  "supports_delta": true,
  "rng_streams": ["setup","turn","battle"],
  "wire_schemas": {
    "turn_context.json": "v1.0+sha256:…",
    "action_result.json": "v1.0+sha256:…"
  }
}
```

---

# **Typed Interface Reference (authoritative)**

> Restored from v1 and updated for v2 (adds `TimeoutPolicy`, `can_end_early`, `GameEngine.__init__`, and `get_capabilities()`).

## Type System & Conventions

**Primitive aliases**

* `PlayerID = int`  (≥ 0)
* `TerritoryID = int`  (≥ 0, contiguous 0..N-1)
* `TickID = int`  (monotonic, fits 64-bit signed)
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
from typing import List, Dict, Optional, Literal, Union, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# Registration lives on the Coordinator; shown for completeness.
def register_player(client: 'PlayerClient', name: str,
                    player_type: Literal['human','random_ai','rule_based_ai','other']) -> 'PlayerID': ...

class GameEngine:
    def __init__(self, config: 'GameConfig') -> None: ...
    def initialize_game(self, player_ids: List['PlayerID']) -> None: ...
    def get_turn_context(self) -> 'TurnContext': ...
    def apply_action(self, action: 'Action') -> 'ActionResult': ...
    def apply_penalty(self, player_id: 'PlayerID', reason: 'PenaltyReason') -> 'ActionResult': ...
    def get_capabilities(self) -> Dict[str, Any]: ...
```

**Return/Argument types**

* `initialize_game`: **input** list of `PlayerID`; **output** `None`.
* `get_turn_context`: **output** `TurnContext`.
* `apply_action`: **input** `Action` (`AttackAction | DistributeSupplyAction | EndTurnAction`); **output** `ActionResult`.
* `apply_penalty`: **input** `PlayerID`, `PenaltyReason`; **output** `ActionResult`.
* `get_capabilities`: **output** `dict[str, Any]` (see schema above).

---

## PlayerClient Interface (GameCoordinator ⇄ PlayerClient)

```python
class PlayerClient:
    def get_action(self, context: 'TurnContext') -> 'Action': ...

    # Lifecycle (optional)
    def on_game_start(self, player_id: 'PlayerID', config: 'GameConfig') -> None: ...
    def on_game_end(self, winner_id: Optional['PlayerID']) -> None: ...
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
    def on_turn_start(self, player_id: 'PlayerID', game_state: 'GameState') -> None: ...
    def on_action_executed(self, action: 'Action', result: 'ActionResult') -> None: ...
    def on_invalid_action(self, player_id: 'PlayerID', action: 'Action',
                          error_code: 'InvalidAction', error_message: str) -> None: ...
    def on_turn_timeout(self, player_id: 'PlayerID', game_state: 'GameState') -> None: ...
    def on_game_start(self, config: 'GameConfig', player_names: List[str]) -> None: ...
    def on_game_end(self, winner_id: Optional['PlayerID'], final_state: 'GameState') -> None: ...
    def on_supply_distributed(self, player_id: 'PlayerID', placements: Dict['TerritoryID', int],
                              game_state: 'GameState') -> None: ...
```

---

## Enums

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

class PenaltyReason(str, Enum):
    TIMEOUT = 'timeout'
    INVALID_ACTION = 'invalid_action'

class SupplyPolicy(str, Enum):
    MUST_PLACE_ALL = 'must_place_all'
    ALLOW_EARLY_END = 'allow_early_end'

class TimeoutPolicy(str, Enum):
    AUTO_END_TURN = 'auto_end_turn'
    SKIP_NEXT_TURN = 'skip_next_turn'
```

---

## Static Map (layout sent once)

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

---

## Dynamic State (sent every turn)

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
```

---

## Actions

```python
@dataclass(frozen=True)
class Action:
    player_id: 'PlayerID'

@dataclass(frozen=True)
class AttackAction(Action):
    attacker_territory_id: 'TerritoryID'
    defender_territory_id: 'TerritoryID'

@dataclass(frozen=True)
class EndTurnAction(Action):
    pass

@dataclass(frozen=True)
class DistributeSupplyAction(Action):
    placements: Dict['TerritoryID', int]  # per-territory dice additions
```

**Validation (engine MUST enforce)**

* `AttackAction`: active owns `src`; `dst` adjacent & enemy; `dice[src] ≥ 2`; `phase == ATTACK`.
* `EndTurnAction`: allowed in ATTACK; allowed in SUPPLY **iff** `ALLOW_EARLY_END` or `supply_remaining == 0` or supply-exhaustion rule.
* `DistributeSupplyAction`:

  * `sum(placements) == supply_remaining` for `MUST_PLACE_ALL`; otherwise `<=` for `ALLOW_EARLY_END`.
  * each key is owned by `player_id`; `dice[t] + add ≤ max_dice_per_territory`.
  * apply per-die in deterministic micro-order; reject whole action on any violation; **no partial** mutations.

---

## Turn Context

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

---

## Action Result & Battle Result

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

@dataclass
class ActionResult:
    success: bool
    new_game_state: GameState
    battle_result: Optional[BattleResult] = None
    supply_placements: Optional[Dict['TerritoryID', int]] = None
    error_code: Optional[InvalidAction] = None
    error_message: Optional[str] = None
    tick_id: 'TickID' = 0
    state_hash: 'Hash64' = 0
```

---

## Game Config

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
    timeout_policy: TimeoutPolicy
    max_turns: Optional[int]
    random_seed: Optional[int]
    created_timestamp: 'TimestampISO8601'
    schema_version: 'SchemaVersion'
    rules_version: 'RulesVersion'
```

---

## Core Internals (typed) — RL & determinism (informative, not public)

```python
@dataclass(frozen=True)
class AttackPairs:
    pairs: List[Tuple['TerritoryID', 'TerritoryID']]
    hash64: 'Hash64'
    index_map: Dict[Tuple['TerritoryID', 'TerritoryID'], int]

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
* `layout_hash: int` (hash of canonical map bytes)
* `action_index_hash: int` (from `AttackPairs.hash64`)
* `num_territories: int`, `num_attack_pairs: int`
* `battle_system: str`, `supply_policy: str`, `max_dice_per_territory: int`
* `supports_delta: bool`
* `rng_streams: list[str]`  (e.g., `["setup","turn","battle"]`)
* `wire_schemas: dict[str, str]`  (schema name → version/hash for files under `transport/json/schema/`)

---

## Conformance & Golden Tests

1. **Determinism** — same seed + same high-level action sequence → identical `tick_id`, `state_hash`, and `rng_counters` after **every** action.
2. **Mask soundness** — every enumerated action is mask-legal; every mask-legal attack appears in order.
3. **Supply exhaustion** — with `MUST_PLACE_ALL` and no eligible cells, SUPPLY must allow `EndTurnAction`.
4. **Timeout policy** — `on_turn_timeout` fires; `apply_penalty(TIMEOUT)` advances `tick_id` by **exactly 1** and consumes **no RNG** (both policies).
5. **Bulk supply determinism** — repeating the same `DistributeSupplyAction` yields identical micro-order and `state_hash`.
6. **Hash cross-platform** — `state_hash` and `position_hash` match test vectors on Linux/macOS, 64/32-bit.

---

This version keeps **all v2 behavior and layout** while restoring v1’s **complete typed surface** so every input/output is precisely defined. If you want, I can split the **Typed Interface Reference** into `docs/api_types.md` and leave `final_api.md` slimmer, but for now it’s embedded here exactly as requested.
