# Dice Wars AI — Roadmap (v4+v5, RL‑ready core)

**Guiding principles**

* Determinism first: same seed + actions ⇒ identical `tick_id`, `state_hash`, `position_hash`.
* Stable public surface under `dicewars.api.*`. Core remains internal and changeable.
* Test‑driven: every milestone lands with unit + property + (when applicable) golden tests.
* Build static map **before** dynamic engine to lock canonicalization & `action_index_hash` early.

---

## Hashless Development Profile (optional)

You **can** build and ship the game without real hashing in Phase 1. Keep the *fields* on the wire for forward compatibility, but return the decimal string `"0"` for:

* `state_hash`, `position_hash` in `ActionResult`
* `layout_hash`, `action_index_hash` in `get_capabilities()`

**Implications**

* Determinism can still be verified via: (a) full `GameState` deep-compare per tick, and/or (b) scripted action replays that check `tick_id` + board arrays.
* RL can still rely on `attack_index` and `AttackPairs.index_map`; policy ↔ map compatibility just won’t be auto-checked by `action_index_hash` until later.
* Replays remain valid; equality checks use deep state compare instead of hash equality.

**Recommended**: implement `core/hash.py` functions as **stubs that return 0** for now. This preserves the public API and lets you swap in real XXH3 later with **no** wire change.

---

## Milestones overview

* **M0 — Repo scaffolding & standards** (you can run this immediately)
* **M1 — Static Map & Canonicalization** (layout, `layout_hash`, `AttackPairs`, `action_index_hash`)
* **M2 — Types, Schemas, Capabilities** (DTOs/enums, wire schemas, `get_capabilities`)
* **M3 — Coordinator walking skeleton** (pure `get_turn_context`, `EndTurnAction`, ticks & hashes)
* **M4 — Attack engine** (masks, RNG streams, `BattleResult`, enumeration order)
* **M5 — Supply engine** (bulk placements, micro‑steps, early‑end legality)
* **M6 — Penalties & timeout windows** (system `PenaltyAction`, ordering)
* **M7 — Winner & game over** (elimination, max‑turns, deterministic tie‑breaks)
* **M8 — Observers & UI** (CLI first; GUI minimal; snapshot stability)
* **M9 — Baseline bots** (random + simple heuristic; PlayerClient lifecycle)
* **M10 — Replays & delta preview** (header record; deterministic replayer)
* **M11 — Polish & docs** (error taxonomy, schema hygiene, examples)

> Dependencies: M1 → M2 (schemas reference types); M2 → M3; M3 → M4/5; M4/5 → M6/7; UI can start after M3 (CLI), GUI after M5.

---

## M0 — Repo scaffolding & standards

### Goals

* Create the full directory structure with placeholder files.
* Tooling: lint, type‑check, test, property testing; CI ready from day one.

### Deliverables

* Exact filesystem layout (empty stubs allowed).
* `pyproject.toml` with pinned tools; `pre-commit` hooks; GitHub Actions CI.

### Directory & file skeleton

```
dicewars-ai/
├── pyproject.toml
├── .pre-commit-config.yaml
├── .gitignore
├── src/
│   └── dicewars/
│       ├── __init__.py
│       ├── __about__.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── types.py
│       │   ├── client.py
│       │   ├── observer.py
│       │   ├── coordinator.py
│       │   └── engine.py
│       ├── engine/
│       │   └── public.py
│       ├── coordinator/
│       │   ├── loop.py
│       │   └── penalties.py
│       ├── observers/
│       │   ├── base.py
│       │   ├── replay.py
│       │   ├── gui.py
│       │   └── cli.py
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── viewmodel/
│       │   │   ├── __init__.py
│       │   │   ├── transform.py
│       │   │   └── geometry.py
│       │   ├── gui/
│       │   │   ├── __init__.py
│       │   │   ├── app.py
│       │   │   └── renderer.py
│       │   └── cli/
│       │       ├── __init__.py
│       │       ├── app.py
│       │       └── ascii_renderer.py
│       ├── clients/
│       │   ├── base.py
│       │   ├── random_bot.py
│       │   └── heuristic_bot.py
│       ├── core/
│       │   ├── state.py
│       │   ├── attack_pairs.py
│       │   ├── actions.py
│       │   ├── engine.py
│       │   ├── rng.py
│       │   ├── hash.py
│       │   └── delta.py
│       ├── transport/
│       │   ├── __init__.py
│       │   └── json/
│       │       ├── bridge.py
│       │       └── schema/
│       │           ├── turn_context.json
│       │           ├── action_result.json
│       │           └── capabilities.json
│       └── utils/
│           └── typing.py
├── tests/
│   ├── unit/
│   │   ├── test_imports.py
│   │   ├── test_schemas_exist.py
│   │   └── test_uint64_wire_helpers.py
│   ├── integration/
│   │   └── test_empty_coordinator_loop.py
│   ├── property/
│   │   └── test_types_are_serializable.py
│   ├── golden/
│   │   ├── test_ascii_placeholder.py
│   │   ├── test_golden_determinism_placeholder.py
│   │   └── test_golden_penalties_placeholder.py
│   └── fixtures/
│       ├── capabilities.json
│       ├── rng_test_vectors.json
│       └── hash_vectors.jsonl
├── examples/
│   └── minimal_client.py
├── scripts/
│   ├── determinism_script.py
│   ├── make_replay.py
│   ├── run_gui.py
│   ├── run_cli.py
│   └── preview_map.py
└── docs/
    ├── roadmap.md
    ├── M0.md
    └── M1.md
```

### Minimal file contents (stubs)

```python
# src/dicewars/__init__.py
from .api import *  # re-export public API (will be populated in M2)
```

```python
# src/dicewars/__about__.py
__version__ = "0.0.0"
RULES_VERSION = "v1"
SCHEMA_VERSION = "v5"
```

```python
# src/dicewars/api/__init__.py
__all__ = []  # will be filled in M2
```

### Tooling & config

```toml
# pyproject.toml (minimal)
[project]
name = "dicewars-ai"
version = "0.0.0"
description = "Deterministic Dice Wars engine (v4+v5 API)"
requires-python = ">=3.11"
dependencies = ["numpy>=1.26", "xxhash>=3.4", "pydantic>=2", "jsonschema>=4"]

[project.optional-dependencies]
dev = [
  "pytest", "hypothesis", "ruff", "mypy", "pytest-cov",
  "types-xxhash"
]

[tool.ruff]
line-length = 100

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
addopts = "-q"
```

```yaml
# .pre-commit-config.yaml
repos:
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.6.8
  hooks: [ { id: ruff }, { id: ruff-format } ]
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.11.1
  hooks: [ { id: mypy } ]
```

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e .[dev]
      - run: pytest --maxfail=1 --disable-warnings
```

### Unit tests (M0)

* `tests/unit/test_imports.py` — `import dicewars as dw` succeeds.
* `tests/unit/test_schemas_exist.py` — schema files present and are valid JSON; `additionalProperties` set to `false`.
* `tests/property/test_types_are_serializable.py` — placeholder ensuring DTOs (added later) will round‑trip via JSON.

### Definition of done (M0)

* Repo installs in editable mode; CI green; pre‑commit hooks run locally.

---

## M1 — Static Map & Canonicalization

### Goals

* Define `MapLayout` dataclasses + JSON Schema.
* Implement canonical `layout_hash` (XXH3\_64, little‑endian byte stream).
* Build `AttackPairs` from adjacency; compute canonical `action_index_hash` and `index_map`.

### Deliverables

* `src/dicewars/core/hash.py` with `xxh3_64_uint64(data: bytes) -> int` and layout hashing.
* `src/dicewars/core/attack_pairs.py` with canonical pairs & hash; docstring points to canonicalization rules.
* `docs/canonicalization.md` (byte widths/order; endianness; traversal order; strings kept as numeric ids only).
* `tests/fixtures/small_map.json` (6‑territory map) and `tests/golden/test_ascii_placeholder.py` uses it for rendering later.

### Tasks

**Hashless profile (M1):** Skip computing `layout_hash`/`action_index_hash` for now. Still generate `AttackPairs.pairs` and `index_map` deterministically. In capabilities, set both hashes to the decimal string `"0"`.

1. Define `MapLayout`, `TerritoryLayout`, `Position`, `BorderSegment` in `api/types.py` (public).
2. JSON Schema for MapLayout under `transport/json/schema/map_layout.json`.
3. Implement layout hashing per spec (omit `TerritoryLayout.name`).
4. Implement `AttackPairs` generation: lexicographic ascending by `(src, dst)`; build `index_map` and `hash64`.

### Tests

* **Unit**

  * `test_map_schema_roundtrip.py` — schema validates `small_map.json`; round‑trip serializes identically except ordering.
  * `test_layout_hash_stability.py` — fixed `small_map.json` ⇒ stable `layout_hash`.
  * `test_attack_pairs_order_and_hash.py` — adjacency symmetry enforced; canonical order; golden `action_index_hash`.
* **Property**

  * `test_adjacency_symmetry.py` — generated random symmetric graphs remain symmetric; no self loops.
  * `test_grid_lookup_consistency.py` — disjoint territory tiles; ids in `grid_lookup` match `territories` keys.

### Definition of done (M1)

* `layout_hash` and `action_index_hash` are reproducible; golden snapshots added under `tests/fixtures/hash_vectors.jsonl`.

---

## M2 — Types, Schemas, Capabilities

### Goals

* Complete public DTOs/enums in `api/types.py` and interfaces in `api/*.py`.
* Implement wire schemas (`turn_context.json`, `action_result.json`, `capabilities.json`).
* Implement `GameEngine.__init__(config)` and `get_capabilities()` (static fields filled from M1; dynamic counts allowed).

### Deliverables

* Public `GamePhase`, `BattleSystem`, `SupplyPolicy`, `TimeoutPolicy`, `WinnerPolicy`, `TiebreakToken`, action DTOs, `GameState`, `TurnContext`, etc. (as spec).
* `uint64` fields encoded as decimal strings in schemas with `format:"uint64"`.
* Enhanced `InvalidAction` enum with new v5 error codes (`ILLEGAL_END_TURN`, `SCHEMA_MISMATCH`, `UNKNOWN_ENUM`, `BAD_PAYLOAD`).
* All schemas set `additionalProperties: false` for wire format compliance.

### Tests

* **Unit**

  * `test_public_surface_exports.py` — `from dicewars.api import ...` exposes stable names.
  * `test_capabilities_shape.py` — required keys present; `uint64` fields are decimal strings; includes `winner_policy`, `winner_tiebreak_chain`, `max_turns`.
  * `test_enum_wire_values.py` — lowercase strings serialized; unknown enum → `UNKNOWN_ENUM` rejection (schema test hook).
  * `test_schema_additional_properties.py` — all schemas reject unknown fields with `additionalProperties: false`.
  * `test_uint64_js_safety.py` — `tick_id`, hash fields serialize as decimal strings, parse correctly in JS-compatible range.
  * `test_uint64_fields_are_decimal_strings_only.py` — round-trips through JSON and rejects non-decimal strings.
  * `test_schema_additional_properties_sweep.py` — iterate all schemas and assert `additionalProperties:false` is set.
  * `test_numeric_map_keys_parsed_as_ints_no_order_dependency.py` — clients must parse numeric object keys as ints (placements, territories).
  * `test_client_penalty_action_rejected_bad_payload.py` — success:false, no tick/RNG/hash changes, `position_hash` still present.
* **Property**

  * `test_wire_roundtrip.py` — Hypothesis generates random small `GameState`/`TurnContext` instances that serialize & validate.
  * `test_error_data_schema.py` — `error_data` field validates against expected machine-readable context schemas.

### Definition of done (M2)

* A client can parse schemas and compare `action_index_hash` from `get_capabilities()`.

---

## M3 — Coordinator walking skeleton

### Goals

* Implement minimal coordinator loop with observers.
* Implement `GameEngine.get_turn_context()` (pure) and `apply_action(EndTurnAction)`.
* Implement `state_hash` vs `position_hash` (canonical streams); return hashes on results.

### Deliverables

* `coordinator/loop.py` with registration, turn order, observer calls, and decision cadence (no ATTACK/SUPPLY yet).
* `core/state.py` with `CoreState` (owners/dice may be placeholders until M4/M5), tick rules, and hash integration.

### Tests

**Hashless profile (M3):** `ActionResult.state_hash` and `position_hash` may both be the decimal string `"0"`. Determinism tests should deep-compare `GameState` snapshots per tick (owners/dice arrays, phase, active player) and verify `tick_id` monotonicity.

* **Unit**

  * `test_turn_context_pure_read.py` — no tick/hash/RNG change across repeated reads.
  * `test_end_turn_increments_tick.py` — `EndTurnAction` advances tick by 1.
  * `test_position_hash_present_on_results.py` — always present even on rejects; `position_hash` excludes `tick_id` and RNG counters.
  * `test_game_over_api_behavior.py` — after GAME_OVER, `apply_action`/`apply_penalty` return `success:false`, `error_code:bad_phase`.
  * `test_numpy_dtype_pinning.py` — `owners` array is `int32`, `dice` array is `int16` for hash stability.
  * `test_turn_number_changes_only_on_new_alive_player_entering_attack.py` — no change on SUPPLY or PENALTY; unchanged if dead player would be next.
  * `test_no_rng_consumption_on_get_turn_context_end_turn.py` — pure reads and non-battle actions don't advance RNG counters.
* **Integration**

  * `test_walking_skeleton_loop.py` — multiple `EndTurnAction`s cycle players, `on_turn_start` only when new player enters ATTACK (placeholder phase for now).

### Definition of done (M3)

* Deterministic loop with `EndTurnAction`; replay of a sequence yields identical ticks/hashes.

---

## M4 — Attack engine

### Goals

* Implement masks, ATTACK validation, RNG streams (`setup`,`turn`,`battle`), and battle resolution (`AUTO_ALL_BUT_ONE`).
* Deterministic enumeration (`attack_pairs.pairs` order); `AttackAction.attack_index` enforced.
* **v5**: `BattleResult.attack_pair_index` mirrors `AttackAction.attack_index` for RL indexing consistency.

### Deliverables

* `core/engine.py` battle step; `BattleResult` filled (raw roll order; attacker first).
* `api/engine.py` exposes public wrapper signatures; `TurnContext.valid_actions` populated with attacks + one `EndTurnAction`.

### Tests

* **Unit**

  * `test_attack_enumeration_order.py` — masks match actions; order equals `attack_pairs.pairs`.
  * `test_battle_roll_order_and_casualties.py` — attacker first; one RNG per die.
  * `test_attack_pair_index_consistency.py` — **v5**: `BattleResult.attack_pair_index` equals `AttackAction.attack_index`.
* **Property**

  * `test_attack_mask_soundness.py` — every legal mask appears exactly once; duplicates impossible.
  * `test_rng_determinism.py` — identical seeds + actions ⇒ identical `state_hash` & counters at each step.

### Definition of done (M4)

* Golden determinism pack for a short scripted battle added under `tests/golden/`.

---

## M5 — Supply engine

### Goals

* Implement `DistributeSupplyAction` with deterministic micro‑order (by territory id, one die at a time).
* Enforce `> 0` values (v5: zero entries are invalid and rejected); sum rules; early end legality; supply exhaustion rule.

### Tests

* **Unit**

  * `test_supply_micro_order_ticks.py` — K dice ⇒ `tick += K`; final placement advances phase/turn with no extra tick.
  * `test_supply_validation_rules.py` — **zero values rejected with `error_code`**; caps respected; keys owned by player.
  * `test_supply_error_data.py` — failed supply validation includes `error_data` with violating territories.
  * `test_valid_actions_during_supply_contains_at_most_one_end_turn_and_never_distribute_supply.py` — supply actions not enumerated.
* **Property**

  * `test_supply_repeatability.py` — repeating the same placement yields identical `state_hash`.

### Definition of done (M5)

* `on_supply_distributed` emits placements; observers re-render using `ActionResult.new_game_state`.

---

## M6 — Penalties & timeout windows

### Goals

* Implement decision window start/stop/reset; `apply_penalty` producing `PenaltyAction` (no RNG; `tick += 1`).
* Implement `AUTO_END_TURN` and `SKIP_NEXT_TURN` (including eliminated‑before‑auto‑skip edge case).
* **v5**: Penalties are first-class actions; observers see `PenaltyAction` via `on_action_executed`.
* **v5**: Auto-skip vs max-turns boundary — max-turns precedence (no pending auto-skip mutation).

### Tests

* **Unit**

  * `test_penalty_no_rng_consumption.py` — RNG counters unchanged.
  * `test_invalid_then_penalty_ordering.py` — `on_invalid_action` → `on_action_executed(penalty)` → optional next `on_turn_start`.
  * `test_skip_next_turn_eliminated_edge.py` — no extra tick; no `on_turn_start` for eliminated player.
  * `test_penalty_action_observer_uniformity.py` — **v5**: penalties emit `PenaltyAction` with `type:"penalty"`, `reason`.
  * `test_max_turns_vs_auto_skip_boundary.py` — **v5**: max-turns applied first, pending auto-skip cancelled.
  * `test_timeout_window_starts_before_get_action_and_resets_on_accept_or_penalty.py` — precise window semantics.
  * `test_rejected_action_does_not_reset_timeout_window.py` — invalid actions don't reset timer.
  * `test_no_rng_consumption_on_penalty.py` — penalties advance tick by 1 but don't consume RNG.

### Definition of done (M6)

* Timeouts fire deterministically; penalties uniform in observers/logs.

---

## M7 — Winner & game over

### Goals

* Game ends on elimination inside the same mutation; max‑turns boundary; deterministic `WinnerPolicy`/`winner_tiebreak_chain`.
* **v5**: Winner policies (`NONE`, `MOST_TERRITORIES`, `MOST_TOTAL_DICE`, `LARGEST_CONNECTED`, `LEXICOGRAPHIC`) with configurable tiebreak chains.
* **v5**: Elimination victory sets `phase=GAME_OVER` and `winner_id` in same mutation (no extra tick).

### Tests

* **Unit**

  * `test_elimination_same_tick.py` — elimination sets `GAME_OVER` with no extra tick.
  * `test_max_turns_boundary_first.py` — max‑turns triggers before pending auto‑skip.
  * `test_winner_lexicographic_chain.py` — tie‑break chain honored.
  * `test_winner_policy_none.py` — **v5**: `WinnerPolicy.NONE` allows `winner_id = None` at game end.
  * `test_winner_policy_deterministic.py` — **v5**: all policies produce identical results across repeated runs.

### Definition of done (M7)

* `get_turn_context()` after `GAME_OVER` returns `phase: game_over`, empty `valid_actions`, and does not mutate state.

---

## M8 — Observers & UI

### Goals

* CLI observer (ASCII) with snapshot golden; GUI observer minimal using `ui/viewmodel/transform.py`.

### Tests

* **Golden**

  * `test_ascii_board_snapshot.py` — 6‑territory map renders to stable text.
* **Unit**

  * `test_viewmodel_snapshot.py` — `to_render_state(game_state)` produces stable JSON (rounded floats) across platforms.
  * `test_on_turn_start_only_on_new_alive_player_entering_attack_not_between_attack_supply.py` — observer event ordering correctness.

### Definition of done (M8)

* `scripts/run_cli.py` runs a sample match and prints board; `preview_map.py` opens map without running a game.

---

## M9 — Baseline bots

### Goals

* `random_bot.py` and `heuristic_bot.py`; lifecycle callbacks; always choose from `valid_actions`.

### Tests

* **Integration**

  * `test_random_bot_legal_actions_only.py` — never submits illegal actions.
  * `test_deterministic_selfplay.py` — fixed seeds + scripted choices ⇒ identical logs over 100 games.

### Definition of done (M9)

* Example `examples/minimal_client.py` shows a tiny loop with a bot vs bot.

---

## M10 — Replays & delta preview

### Goals

* JSONL replay writer with **v5 header record** (includes `uint64_encoding`, `layout_hash`, `action_index_hash`); optional `delta` under capability flag; deterministic replayer.

### Tests

**Hashless profile (M10):** Replay equality uses deep state compare (or canonical JSON of `GameState`) per tick instead of hash equality. Keep `tick_id` equality assertions.

* **Integration**

  * `test_replay_roundtrip.py` — replay reproduces every `tick_id`, `state_hash`, `position_hash`.
  * `test_delta_only_emitted_when_supports_delta_true.py` — delta transport behind capability flag.
  * `test_delta_invariants_lengths_match.py` — `len(changed_territories) == len(new_owners) == len(new_dice)`.
  * `test_replay_header_completeness.py` — header contains `schema_version`, `rules_version`, `uint64_encoding`, `layout_hash`, `action_index_hash`.

### Definition of done (M10)

* `scripts/make_replay.py` produces logs; `observers/replay.py` replays them identically.

---

## M11 — Polish & docs

### Goals

* Error taxonomy filled (`InvalidAction`, `error_data`); schema `additionalProperties:false` everywhere; docs pass.

### Tests

* **Unit**

  * `test_error_taxonomy.py` — representative invalid payloads → `success:false`, no tick/hash/RNG changes, `position_hash` present.

### Definition of done (M11)

* Capabilities advertise schema versions & hashes; README and API docs match implementation.

---

## Bootstrap helper (optional)

Run once to create directories and minimal stubs (safe to re‑run).

```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p dicewars-ai/{src/dicewars/{api,engine,coordinator,observers,ui/{viewmodel,gui,cli},clients,core,transport/json/schema,utils},tests/{unit,integration,property,golden,fixtures},examples,scripts,docs,.github/workflows}
# Minimal files
cat > dicewars-ai/src/dicewars/__init__.py <<'PY'
from .api import *  # noqa: F401,F403
PY
cat > dicewars-ai/src/dicewars/__about__.py <<'PY'
__version__ = "0.0.0"; RULES_VERSION = "v1"; SCHEMA_VERSION = "v5"
PY
cat > dicewars-ai/src/dicewars/api/__init__.py <<'PY'
__all__: list[str] = []
PY
cat > dicewars-ai/pyproject.toml <<'TOML'
[project]
name = "dicewars-ai"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = ["numpy>=1.26","xxhash>=3.4","pydantic>=2","jsonschema>=4"]
[project.optional-dependencies]
dev=["pytest","hypothesis","ruff","mypy","pytest-cov","types-xxhash"]
[tool.pytest.ini_options]
addopts="-q"
TOML
cat > dicewars-ai/.pre-commit-config.yaml <<'YML'
repos:
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.6.8
  hooks: [ { id: ruff }, { id: ruff-format } ]
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.11.1
  hooks: [ { id: mypy } ]
YML
cat > dicewars-ai/.github/workflows/ci.yml <<'YML'
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e .[dev]
      - run: pytest -q
YML
```

---

## Test matrix quick reference

* **Ticks**: ATTACK +1; END\_TURN +1; SUPPLY +K; PENALTY +1; invalid +0.
* **Hashes**: `position_hash` excludes RNG counters & `tick_id` and is present on **every** `ActionResult`.
* **v5 Wire format**: `tick_id`, hash fields are decimal strings; `additionalProperties:false` on all schemas.
  * **Hashless profile**: in Phase 1 you may emit `"0"` for all hash fields; tests should compare full `GameState` snapshots (owners/dice/phase/players) and `tick_id` instead of hash equality.
* **ATTACK**: enumeration equals `attack_pairs.pairs` order; `AttackAction.attack_index` enforced; `BattleResult.attack_pair_index` matches.
* **SUPPLY**: not enumerated; placements `> 0` **(v5: zero values rejected)**; per‑die micro‑order by territory id; K dice ⇒ K ticks.
* **Penalties**: produce `PenaltyAction` **(v5: first-class actions)**; consume no RNG; ordering against invalids respected.
* **Winner**: elimination in same mutation; max‑turns boundary applied before pending auto‑skip; **(v5: `WinnerPolicy.NONE` allows `winner_id = None`)**; lexicographic chain deterministic.
* **Observer**: `on_turn_start` only when a **new alive** player enters ATTACK; render on `on_action_executed`; **(v5: penalties emit `PenaltyAction`)**.
* **Error handling**: **(v5: `error_data` field for machine-readable context)**; after GAME_OVER, API calls return `error_code:bad_phase`.

---

## FAQ

**Q: Can I delete all hashing and keep everything else?**
**A:** Yes for Phase 1, if you keep the wire fields but stub them to `"0"`. The game loop, attacks, supply, penalties, UI, and AI all work. You’ll temporarily lose cheap equivalence checks, cross‑platform snapshot matching, and automatic RL policy/map compatibility checks. The roadmap now includes a **Hashless profile** with specific test substitutions so you don’t block on hashing.

**Q: Is building the map before engine reasonable?**
**A:** Yes. It de‑risks determinism early by locking `layout_hash` and `action_index_hash`, and lets you start UI work (`preview_map.py`) without any dynamic state. M1 is intentionally placed before engine work.
