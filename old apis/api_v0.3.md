# Dice Wars AI — Final API Design (Phase 1, RL‑ready Core Internals)

> **Purpose**
> A small, stable public API for gameplay + a slim, atomic core for RL. This version fixes two foot‑guns:
>
> 1. **Player contract & SUPPLY enumeration** are now explicit and unambiguous.
> 2. **Tick semantics** are reworded with a single definition that covers actions, penalties, and multi‑step supply.
>
> Everything else is tightened for determinism, replayability, and easy client implementation.

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
