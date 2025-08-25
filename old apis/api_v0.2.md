# Dice Wars AI – API Design Specification (Phase 1, RL-ready Core Internals)

## System Architecture Overview

The Dice Wars system follows a hub-and-spoke pattern with the GameCoordinator as the central orchestrator. All communication flows through the coordinator — no direct Engine↔Player or Player↔Player communication occurs.

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

## Core Roles & Responsibilities

### GameEngine (Backend Authority)

* **Role**: Single source of truth for game rules and state
* **Responsibilities**:

  * Validates all actions according to game rules
  * Maintains authoritative game state
  * Executes battles and state transitions
  * Determines win/loss conditions
  * **Pattern**: Purely reactive — only responds to coordinator requests

### GameCoordinator (Central Orchestrator)

* **Role**: Communication hub between engine and players
* **Responsibilities**:

  * Manages player registration and turn order
  * Requests turn information from engine (bundled as `TurnContext`)
  * Distributes game state and valid actions to players
  * Handles player responses and error cases
  * Notifies observers of all game events
  * **Pattern**: Active controller — initiates all communication

### PlayerClient Interface (Player Contract)

* **Role**: Abstract interface all players must implement
* **Contract**: “Given a `TurnContext` containing a list of **currently legal** actions, pick one of them.”
* **Types**:

  * **HumanPlayer**: GUI/terminal interface for human input
  * **RandomAI**: Makes random valid moves
  * **RuleBasedAI**: Uses heuristics (attack weak neighbors, etc.)
* **Pattern**: Reactive — only responds to coordinator requests
* **Philosophy**: If a client violates its contract (returns invalid action), it’s buggy — notify developers via observers, not the broken client

### GameObserver (Event Watcher)

* **Role**: Watches game events for logging, GUI updates, statistics
* **Types**:

  * **Logger**: Records game events to files
  * **GUIUpdater**: Updates visual display
  * **StatisticsCollector**: Tracks performance metrics
* **Pattern**: Passive listener — receives events from coordinator

## API Contracts

### GameCoordinator Registration API

```python
def register_player(client: PlayerClient, name: str, player_type: str) -> int
    """
    Register a player with the coordinator.
    Static info (name, type) is provided once during registration.
    Returns assigned player_id.
    """
```

### GameCoordinator → GameEngine API

```python
# Game Setup
def initialize_game(player_ids: List[int]) -> None
    """Initialize game with specified players."""

# Streamlined Turn Management (was 3 calls, now 1)  
def get_turn_context() -> TurnContext
    """Bundle current state and valid actions for active player."""

# Streamlined Action Processing (was complex tuple, now clear object)
def apply_action(action: Action) -> ActionResult
    """Validate and apply action, return comprehensive result.
    Engine validates that action.player_id == active_player_id."""

# Penalty Application (engine owns all state mutations)
def apply_penalty(player_id: int, reason: PenaltyReason) -> ActionResult
    """Apply penalty when client violates contract or times out.
    MUST increment tick_id exactly once.
    MUST NOT consume RNG values.
    Default policies:
    - TIMEOUT: auto end-turn (configurable via timeout_policy)
    - INVALID_ACTION: skip action only (does NOT auto end-turn)
    Returns ActionResult with updated state."""

# Note: No is_game_over() method needed — check GameState.winner_id instead
```

### GameCoordinator → PlayerClient API

```python
# Primary Decision Request
def get_action(context: TurnContext) -> Action
    """Choose an action from context.valid_actions.
    EndTurnAction availability:
      - ATTACK phase: always present
      - SUPPLY phase: present only if (supply_policy == ALLOW_EARLY_END) or (supply_remaining == 0)
    """

# Game Lifecycle Events
def on_game_start(player_id: int, config: GameConfig) -> None
    """Called when game begins. Store player_id for reference."""

def on_game_end(winner_id: int) -> None
    """Called when game ends. Clean up resources."""

# Battle Feedback
def on_battle_result(battle: BattleResult) -> None
    """Receive battle outcome information.
    This is a convenience callback for players (e.g., GUIs/humans).
    Observers receive the same data via on_action_executed(...result.battle_result...)."""

# Note: Player name and type are provided during registration, not queried
# Note: No on_invalid_action_attempted - broken clients can't fix themselves
```

### GameCoordinator → GameObserver API

```python
# Turn Events
def on_turn_start(player_id: int, game_state: GameState) -> None
    """Called when a NEW player's ATTACK phase begins (i.e., when the active player changes).
    Not fired during SUPPLY for the same player."""

def on_action_executed(action: Action, result: ActionResult) -> None
    """Called after successful action execution.
    If result.battle_result is not None, use it for battle details."""

def on_invalid_action(player_id: int, action: Action, error_code: InvalidAction, error_message: str) -> None
    """Called when player attempts invalid action. Includes both code and message."""

def on_turn_timeout(player_id: int, game_state: GameState) -> None
    """Called when a player's decision times out (before penalty is applied)."""

# Game Lifecycle Events
def on_game_start(config: GameConfig, player_names: List[str]) -> None
    """Called when game begins."""

def on_game_end(winner_id: int, final_state: GameState) -> None
    """Called when game ends."""

def on_supply_distributed(player_id: int, placements: Dict[int, int], game_state: GameState) -> None
    """Called after supply dice are distributed (pass the UPDATED state)."""
```

## Key Data Transfer Objects

### Static Map Layout (Sent Once at Game Start)

#### MapLayout (Complete Static Board Definition)

```python
@dataclass(frozen=True)
class MapLayout:
    map_name: str
    dimensions: Position                         # Board width/height (width, height)
    territories: Dict[int, TerritoryLayout]     # Fast lookup for territory definitions
    grid_lookup: List[List[int]]                # Fast lookup: grid[y][x] -> territory_id (-1 for out-of-board)
```

**Purpose**: Complete static definition of the game board. Sent once at game start and never changes during gameplay.

**Coordinate Conventions**:

* Origin at top-left (0, 0)
* `x` increases rightward, `y` increases downward
* All coordinates are 0-based integers
* `grid_lookup[y][x]` returns territory\_id or -1 for out-of-board

#### TerritoryLayout (Static Territory Definition)

```python
@dataclass(frozen=True)
class TerritoryLayout:
    id: int
    name: str
    tiles: List[Position]                       # Tiles that make up this territory
    adjacencies: List[int]                      # IDs of neighboring territories (symmetric, no self-loops)
    border: List[BorderSegment]                 # Pre-calculated outer border for rendering
```

**Purpose**: Defines the unchanging physical properties of one territory including shape, neighbors, and rendering data.

**Invariants**:

* Adjacencies must be **symmetric**: if A is adjacent to B, then B is adjacent to A
* No self-loops: territory cannot be adjacent to itself
* `build_attack_pairs()` validates these invariants and fails fast if violated

#### Supporting Static Types

```python
@dataclass(frozen=True)
class Position:
    x: int
    y: int

@dataclass(frozen=True)
class BorderSegment:
    start: Position
    end: Position
```

### Dynamic Game State (Sent Every Turn)

#### GameState (Lightweight Dynamic Snapshot)

```python
@dataclass(frozen=True)
class GameState:
    active_player_id: int                       # Whose turn it is
    turn_number: int                            # Current turn counter
    winner_id: Optional[int]                    # Game result (None = ongoing)
    territories: Dict[int, TerritoryState]      # Fast lookup for current territory states
    players: List[PlayerInfo]                   # Player status information
    phase: GamePhase                            # Current game phase
```

**Purpose**: Lean, dynamic snapshot of current game state. Contains only data that changes during gameplay — references static `MapLayout` by territory IDs.

#### TerritoryState (Dynamic Territory Data)

```python
@dataclass(frozen=True)
class TerritoryState:
    owner_id: int                               # Which player owns this territory
    dice_count: int                             # Current military strength
```

#### PlayerInfo (Player Status)

```python
@dataclass(frozen=True)
class PlayerInfo:
    id: int
    name: str
    color: str                                  # Hex color code for rendering
    owned_territory_ids: List[int]              # DERIVED: List of territory IDs this player owns
    total_dice: int                             # Total dice across all territories
    supply_dice: int                            # Supply they'll receive at start of their next SUPPLY phase (0 if eliminated)
    is_alive: bool                              # False if eliminated
    largest_connected_region: int               # Size of largest connected territory group
```

**Purpose**: Complete player status information. Updated each turn to reflect current power and resources.

**Invariants**:

* `owned_territory_ids` is **derived** from territory ownership and maintained by the engine
* When `player_id == active_player_id` and `phase == SUPPLY`: `supply_dice == CoreState.supply_remaining`
* Otherwise: `supply_dice` shows the supply they'll receive on their next turn (or 0 if eliminated)

### Game Enumerations

#### GamePhase (Turn Phase)

```python
class GamePhase(Enum):
    SETUP = "setup"                              # Initial game setup
    ATTACK = "attack"                            # Player can make attacks
    SUPPLY = "supply"                            # Player receives and distributes dice
    GAME_OVER = "game_over"                      # Game has ended
```

#### BattleSystem (Combat Rules)

```python
class BattleSystem(Enum):
    AUTO_ALL_BUT_ONE = "auto_all_but_one"       # Attacker uses all dice except 1, no choice needed
    # VARIABLE = "variable"                      # Future: AttackAction would include dice_count field
```

#### InvalidAction (Error Codes)

```python
class InvalidAction(Enum):
    ILLEGAL_ATTACK = "illegal_attack"            # Attack violates adjacency or ownership rules
    OVER_SUPPLY_LIMIT = "over_supply_limit"      # Supply placement exceeds limits
    NOT_YOUR_TURN = "not_your_turn"              # Action from wrong player
    BAD_PHASE = "bad_phase"                      # Action invalid in current phase
    TERRITORY_NOT_OWNED = "territory_not_owned"  # Trying to place dice on enemy territory
    INSUFFICIENT_DICE = "insufficient_dice"      # Not enough dice for attack
```

#### PenaltyReason (Penalty Types)

```python
class PenaltyReason(Enum):
    TIMEOUT = "timeout"                          # Turn time limit exceeded
    INVALID_ACTION = "invalid_action"            # Client sent invalid action
```

#### SupplyPolicy (Supply Distribution Rules)

```python
class SupplyPolicy(Enum):
    MUST_PLACE_ALL = "must_place_all"            # Must distribute all supply dice
    ALLOW_EARLY_END = "allow_early_end"          # Can end turn early, forfeiting remaining dice
```

### Action Hierarchy (Player Decisions)

#### Base Action Class

```python
@dataclass(frozen=True)
class Action:
    """Base class for all player decisions. Engine validates player_id == active_player_id."""
    player_id: int
```

#### AttackAction

```python
@dataclass(frozen=True)
class AttackAction(Action):
    """Represents an attack from one territory to another."""
    attacker_territory_id: int
    defender_territory_id: int
```

#### EndTurnAction

```python
@dataclass(frozen=True)
class EndTurnAction(Action):
    """Represents the decision to end the current turn."""
    pass
```

#### DistributeSupplyAction

```python
@dataclass(frozen=True)
class DistributeSupplyAction(Action):
    """Represents the distribution of all supply dice in a single turn."""
    placements: Dict[int, int]                   # {territory_id: dice_to_add}
```

**Validation Rules**:

* If `supply_policy == MUST_PLACE_ALL`: `sum(placements.values()) == supply_remaining`
* If `supply_policy == ALLOW_EARLY_END`: `sum(placements.values()) <= supply_remaining`
* All territories in `placements.keys()` must be owned by `player_id`
* For each territory: `current_dice + dice_to_add <= max_dice_per_territory`
* Dictionary iteration must be **deterministic** (sort by `territory_id`) for reproducibility
* On violation: entire action rejected with `error_code=OVER_SUPPLY_LIMIT` (no partial application)

**Supply Exhaustion (Deadlock Escape)**:

* If `phase == SUPPLY`, `supply_policy == MUST_PLACE_ALL`, `supply_remaining > 0` **and** no territories can accept dice:

  * Engine sets `supply_remaining = 0` (discards unplaceable dice)
  * Allows `EndTurnAction` to avoid deadlock

### BattleResult (Combat Outcome)

```python
@dataclass(frozen=True)
class BattleResult:
    """Complete, self-contained information about a battle outcome."""
    # Pre-battle state
    attacker_player_id: int
    defender_player_id: int
    attacker_territory_id: int
    defender_territory_id: int
    attacker_dice_count: int
    defender_dice_count: int

    # Battle execution
    attacker_rolls: List[int]
    defender_rolls: List[int]
    attacker_wins: bool
    attacker_casualties: int
    defender_casualties: int

    # Post-battle state (fully self-contained)
    post_attacker_source_dice: int
    post_defender_target_dice: int
    new_owner_id: int
    dice_transferred: int
```

**AUTO\_ALL\_BUT\_ONE Transfer Rule**:

* Attacks use all dice except 1 from source territory
* On **capture**:

  * `dice_transferred = attacker_dice_count` (all attacking dice move)
  * `post_attacker_source_dice = 1` (always leave 1 behind)
  * `post_defender_target_dice = dice_transferred`
  * `new_owner_id = attacker_player_id`
* On **failure**:

  * `dice_transferred = 0`
  * `post_attacker_source_dice = original_dice - attacker_casualties`
  * `post_defender_target_dice = original_dice - defender_casualties`
  * `new_owner_id = defender_player_id`

### Game Configuration

```python
@dataclass(frozen=True)
class GameConfig:
    """Complete game configuration for reproducible, well-defined games."""
    name: str
    map_layout: MapLayout
    
    # Player Configuration
    max_players: int
    min_players: int
    
    # Game Rules
    max_dice_per_territory: int
    initial_dice_per_territory: int
    max_supply_dice: int                        # Per-turn cap on awarded supply dice at start of SUPPLY (no carry-over bank)
    supply_dice_calculation: str                # "largest_connected", "territory_count", etc.
    battle_system: BattleSystem
    supply_policy: SupplyPolicy
    
    # Game Flow
    turn_timeout_seconds: Optional[int]
    timeout_policy: Literal["auto_end_turn", "skip_next_turn"] = "auto_end_turn"
    max_turns: Optional[int]
    
    # Reproducibility
    random_seed: Optional[int]
    
    # Metadata
    created_timestamp: str
    schema_version: str
    rules_version: str
```

**Key Rule Note**:

* `max_supply_dice` limits the **award for the turn** before placement. Unused dice are **not** stored between turns.

### TurnContext (Reduces API Chattiness)

```python
@dataclass(frozen=True)
class SupplyDescriptor:
    """Describes available supply placement options."""
    supply_remaining: int
    eligible_territories: List[int]   # Territories with room (dice < max)
    per_territory_cap: int            # From config.max_dice_per_territory

@dataclass
class TurnContext:
    game_state: GameState
    valid_actions: List[Action]       # Currently legal actions (ordered deterministically)
    current_player_id: int
    supply: Optional[SupplyDescriptor] = None  # Present only in SUPPLY phase
```

**Enumeration Order (Deterministic)**:

* **ATTACK**: enumerate all legal `AttackAction`s in `attack_pairs.pairs` order, then append `EndTurnAction`.
* **SUPPLY**:

  * `MUST_PLACE_ALL`: `EndTurnAction` only when `supply_remaining == 0` or supply exhaustion
  * `ALLOW_EARLY_END`: `EndTurnAction` always present
  * `DistributeSupplyAction` is **never** enumerated (combinatorial explosion avoided)

**Implementation Requirement** (`_masks_to_actions` contract):

* Must enumerate (1) all mask-legal attacks in `attack_pairs.pairs` order; (2) append a single `EndTurnAction` **iff** `masks.can_end_turn` is `True`. No other actions are enumerated.

### ActionResult (Self-Documenting Returns)

```python
@dataclass 
class ActionResult:
    success: bool
    new_game_state: GameState                   # Updated state (unchanged if failed)
    battle_result: Optional[BattleResult] = None
    supply_placements: Optional[Dict[int, int]] = None
    error_code: Optional[InvalidAction] = None
    error_message: Optional[str] = None
    tick_id: int = 0                            # Monotonic step counter (last atomic step)
    state_hash: int = 0                         # 64-bit hash for state verification
```

## Communication Flow

### Complete Game Sequence

```
1) PLAYER REGISTRATION
   For each player:
      Coordinator: register_player(client, name="RandomAI", player_type="random_ai")
      Returns: player_id
      Coordinator stores: {player_id: {client, name, type}}

2) GAME SETUP
   Coordinator → Engine: initialize_game(player_ids)
   Coordinator → Players: on_game_start(player_id, config)
   Coordinator → Observers: on_game_start(config, player_names)

3) TURN EXECUTION LOOP
   while self.current_state.winner_id is None:

   a) Get Turn Information (1 call)
      ctx = engine.get_turn_context()

   a.1) TIMEOUT HANDLING
       If player's decision times out:
         Coordinator → Observers: on_turn_timeout(player_id, self.current_state)
         penalty = engine.apply_penalty(player_id, PenaltyReason.TIMEOUT)
         self.current_state = penalty.new_game_state
         continue

   b) Turn-start event (only when a NEW player becomes active in ATTACK)
      if turn advanced since last tick:
         Coordinator → Observers: on_turn_start(ctx.current_player_id, self.current_state)

      Coordinator → Player: get_action(ctx)

   c) Execute Action
      result = engine.apply_action(chosen_action)

   d) Handle Results
      if result.success:
         self.current_state = result.new_game_state
         Coordinator → Observers: on_action_executed(chosen_action, result)
         if result.battle_result:
            Coordinator → All Players: on_battle_result(result.battle_result)
         if result.supply_placements:
            Coordinator → Observers: on_supply_distributed(
                ctx.current_player_id, result.supply_placements, result.new_game_state
            )
      else:
         Coordinator → Observers: on_invalid_action(
             ctx.current_player_id, chosen_action, result.error_code, result.error_message
         )
         penalty = engine.apply_penalty(ctx.current_player_id, PenaltyReason.INVALID_ACTION)
         self.current_state = penalty.new_game_state

   e) Check Game End
      if self.current_state.winner_id is not None:
         break

4) GAME END
   Coordinator → Players: on_game_end(winner_id)
   Coordinator → Observers: on_game_end(winner_id, final_state)
```

## Phase Transitions

| Current Phase | Action                 | Result                                           |
| ------------- | ---------------------- | ------------------------------------------------ |
| ATTACK        | EndTurnAction          | → SUPPLY (same player), compute supply dice      |
| SUPPLY        | EndTurnAction          | → ATTACK (next alive player)                     |
| SUPPLY        | DistributeSupplyAction | Remains in SUPPLY                                |
| Any           | Invalid action         | No phase change                                  |
| Any           | Penalty                | Depends on penalty policy (see `timeout_policy`) |

**Tick Semantics**: Every **successful** state transition increments `tick_id` exactly once.

## Architectural Principles

1. **Hub-and-Spoke Communication** — Coordinator is the hub; others are reactive spokes
2. **Request-Response Pattern** — Engine/Players never initiate calls
3. **Bundled Information Transfer** — `TurnContext` & `ActionResult` reduce chattiness
4. **Pure Data Transfer** — DTOs are serializable data only
5. **Error Handling** — Engine owns all mutations; invalid actions don’t change state; penalties via engine; observers notified

## Engine Core API (RL-Friendly Internals)

> Internal only — not exposed to Coordinator or Players.

### Core Data Structures

#### AttackPairs (Stable Action Indexing)

```python
@dataclass(frozen=True)
class AttackPairs:
    """Canonical, deterministic ordering of all possible attacks."""
    pairs: List[Tuple[int, int]]
    hash64: int
    index_map: Dict[Tuple[int, int], int]

def build_attack_pairs(layout: MapLayout) -> AttackPairs:
    """Sort by (src_id, dst_id) for determinism; validate adjacency invariants."""
```

#### CoreState (Dense Internal Representation)

```python
@dataclass(frozen=True)
class CoreState:
    active_player_id: int
    turn_number: int
    phase: GamePhase
    winner_id: Optional[int]
    owners: np.ndarray       # shape=(num_territories,), dtype=int32
    dice: np.ndarray         # shape=(num_territories,), dtype=int16
    supply_remaining: int
    player_alive: np.ndarray # shape=(num_players,), dtype=bool
    largest_connected: np.ndarray  # shape=(num_players,), dtype=int32
    territory_counts: np.ndarray   # shape=(num_players,), dtype=int32
    rng_counters: Dict[str, int]   # {"setup": N, "turn": N, "battle": N}
    tick_id: int
```

#### ActionMasks (Boolean Legality Arrays)

```python
@dataclass(frozen=True)
class ActionMasks:
    attack: np.ndarray           # shape=(len(attack_pairs),), dtype=bool
    place_one_die: np.ndarray    # shape=(num_territories,), dtype=bool
    can_end_turn: bool

def legal_masks(state: CoreState, attack_pairs: AttackPairs, config: GameConfig) -> ActionMasks:
    """
    - attack[k] = True iff owners[src]==active, owners[dst]!=active, dice[src]>=2, phase==ATTACK
    - place_one_die[t] = True iff owners[t]==active, dice[t] < max_dice, phase==SUPPLY, supply_remaining>0
    - can_end_turn = (phase==ATTACK) or (phase==SUPPLY and (ALLOW_EARLY_END or supply_remaining==0))
    Supply Exhaustion: If MUST_PLACE_ALL and supply_remaining>0 but no place_one_die,
    treat as supply_remaining==0 for mask computation so can_end_turn==True.
    """
```

### Core Actions (Atomic Primitives)

```python
@dataclass(frozen=True)
class CoreAction:
    kind: Literal["attack", "place_one_die", "end_turn"]
    attack_index: Optional[int] = None
    territory_id: Optional[int] = None
```

### StepInfo (Transition Metadata)

```python
@dataclass(frozen=True)
class StepInfo:
    battle_result: Optional[BattleResult]
    rng_counters: Dict[str, int]
    tick_id: int
    state_hash: int
    delta: Optional['StateDelta']
```

### Reproducibility & Canonicalization

#### RNG Streams

```python
@dataclass(frozen=True)
class RNGStream:
    name: str
    seed: int
    counter: int

def reseed(state: CoreState, master_seed: int) -> CoreState: ...
def consume_random(stream: RNGStream, count: int = 1) -> Tuple[List[int], RNGStream]: ...
```

**Dice Roll Order**: Attacker rolls first (all dice), then defender; each die consumes one 32-bit value from the battle stream.

#### State Hashing

```python
def state_hash(state: CoreState) -> int: ...
def canonical_bytes(state: CoreState) -> bytes: ...
def canonical_bytes_layout(layout: MapLayout) -> bytes: ...
```

#### Canonicalization (Player-Agnostic Views)

```python
@dataclass(frozen=True)
class CanonicalView:
    owners: np.ndarray
    dice: np.ndarray
    phase: GamePhase
    supply_remaining: int
    player_perm: np.ndarray
    inv_perm: np.ndarray

def canonicalize(state: CoreState) -> CanonicalView: ...
```

### Optional: Delta Mode (Efficient Updates)

```python
@dataclass(frozen=True)
class StateDelta:
    changed_territories: List[int]
    new_owners: np.ndarray
    new_dice: np.ndarray
    phase_changed: bool
    new_phase: Optional[GamePhase]
    turn_advanced: bool
    new_turn: Optional[int]
    game_ended: bool
    winner: Optional[int]

def compute_delta(old_state: CoreState, new_state: CoreState) -> StateDelta: ...
```

### Integration with GameEngine Service (Public API wrapper)

```python
class GameEngine:
    def __init__(self, config: GameConfig):
        self.config = config
        self.attack_pairs = build_attack_pairs(config.map_layout)
        self.core_state = None

    def initialize_game(self, player_ids: List[int]) -> None: ...
    
    def get_turn_context(self) -> TurnContext:
        masks = legal_masks(self.core_state, self.attack_pairs, self.config)
        valid_actions = self._masks_to_actions(masks)  # Deterministic order contract applies
        game_state = self._core_to_game_state(self.core_state)

        supply_desc = None
        if self.core_state.phase == GamePhase.SUPPLY:
            eligible = [t for t, can_place in enumerate(masks.place_one_die) if can_place]
            supply_desc = SupplyDescriptor(
                supply_remaining=self.core_state.supply_remaining,
                eligible_territories=eligible,
                per_territory_cap=self.config.max_dice_per_territory
            )

        return TurnContext(
            game_state=game_state,
            valid_actions=valid_actions,
            current_player_id=self.core_state.active_player_id,
            supply=supply_desc
        )
        
    def apply_action(self, action: Action) -> ActionResult:
        # Validate actor; convert high-level Action to CoreAction(s); return ActionResult
        ...

    def apply_penalty(self, player_id: int, reason: PenaltyReason) -> ActionResult:
        # MUST increment tick_id exactly once; MUST NOT consume RNG values
        ...
```

### Capabilities Discovery

```python
def get_capabilities(config: GameConfig, layout: MapLayout) -> Dict[str, Any]:
    attack_pairs = build_attack_pairs(layout)
    return {
        "rules_version": config.rules_version,
        "schema_version": config.schema_version,
        "layout_hash": xxhash64(canonical_bytes_layout(layout)),
        "action_index_hash": attack_pairs.hash64,
        "num_territories": len(layout.territories),
        "num_attack_pairs": len(attack_pairs.pairs),
        "battle_system": config.battle_system.value,
        "supply_policy": config.supply_policy.value,
        "max_dice_per_territory": config.max_dice_per_territory,
        "supports_delta": True,
        "rng_streams": ["setup", "turn", "battle"],
    }
```

## Conformance Testing

### Determinism Test
* Same `random_seed` + same action sequence → identical `tick_id` and `state_hash` at each step

### Mask Soundness Test
* Every action in enumerated `valid_actions` must satisfy `legal_masks` in the core
* Every mask-legal attack must appear in `valid_actions`

### Supply Exhaustion Test
* When `MUST_PLACE_ALL` and all territories at max dice, `EndTurnAction` must be available

## Benefits of This Design

1. **Reduced API Calls**: 3→1 calls per turn (get_turn_context vs separate state/actions queries)
2. **Minimal Engine API**: Only 4 methods needed (initialize_game, get_turn_context, apply_action, apply_penalty)
3. **Ultra-Minimal PlayerClient API**: Only 4 methods total (get_action + 3 lifecycle events)
4. **Clean Error Philosophy**: Broken clients aren't notified - debugging info goes to observers/developers
5. **Consistent Data Flow**: TurnContext used end-to-end without unbundling
6. **Single Source of Truth**: GameState is authoritative for all status (no is_game_over needed)
7. **Static Info Cached**: Player name/type provided once at registration, not repeatedly queried
8. **Self-Documenting**: ActionResult vs cryptic tuples, EndTurnAction for explicit turn ending
9. **Atomic Operations**: Each call returns complete, consistent information
10. **Extensible**: Easy to add fields to DTOs without breaking existing code
11. **Performance**: Less serialization/network overhead, no redundant queries or state checks
12. **Maintainable**: Clear separation of concerns and communication patterns
13. **Testable**: Each component can be mocked/tested independently
14. **Bug-Resistant**: Encourages correct client implementations by design
15. **RL-Ready**: Core API enables masks, atomic actions, canonicalization, and perfect reproducibility
16. **Future-Proof**: Data model decisions made upfront prevent expensive refactoring later

---

**Player contract (final)**: “Given a `TurnContext` with **currently legal** actions, select one of them.”
