# Dice Wars AI – API Design Specification (Phase 1, RL-ready Core Internals)

## System Architecture Overview

The Dice Wars system follows a hub-and-spoke pattern with the GameCoordinator as the central orchestrator. All communication flows through the coordinator - no direct Engine↔Player or Player↔Player communication occurs.

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
- **Role**: Single source of truth for game rules and state
- **Responsibilities**: 
  - Validates all actions according to game rules
  - Maintains authoritative game state
  - Executes battles and state transitions
  - Determines win/loss conditions
  - **Pattern**: Purely reactive - only responds to coordinator requests

### GameCoordinator (Central Orchestrator)
- **Role**: Communication hub between engine and players
- **Responsibilities**:
  - Manages player registration and turn order
  - Requests turn information from engine (bundled as TurnContext)
  - Distributes game state and valid actions to players
  - Handles player responses and error cases
  - Notifies observers of all game events
  - **Pattern**: Active controller - initiates all communication

### PlayerClient Interface (Player Contract)
- **Role**: Abstract interface all players must implement
- **Contract**: "Given a `TurnContext` containing a list of **currently legal** actions, pick one of them."
- **Types**:
  - **HumanPlayer**: GUI/terminal interface for human input
  - **RandomAI**: Makes random valid moves
  - **RuleBasedAI**: Uses heuristics (attack weak neighbors, etc.)
- **Pattern**: Reactive - only responds to coordinator requests
- **Philosophy**: If a client violates its contract (returns invalid action), it's buggy - notify developers via observers, not the broken client

### GameObserver (Event Watcher)
- **Role**: Watches game events for logging, GUI updates, statistics
- **Types**:
  - **Logger**: Records game events to files
  - **GUIUpdater**: Updates visual display
  - **StatisticsCollector**: Tracks performance metrics
- **Pattern**: Passive listener - receives events from coordinator

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

# Note: No is_game_over() method needed - check GameState.winner_id instead
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
    """Called at beginning of each player's turn."""

def on_action_executed(action: Action, result: ActionResult) -> None
    """Called after successful action execution.
    If result.battle_result is not None, observers should use it for battle details.
    No separate battle observer hook is needed - all info is in ActionResult."""

def on_invalid_action(player_id: int, action: Action, error_code: InvalidAction, error_message: str) -> None
    """Called when player attempts invalid action. Includes both code and message."""

def on_turn_timeout(player_id: int, game_state: GameState) -> None
    """Called when a player's turn times out."""

# Game Lifecycle Events
def on_game_start(config: GameConfig, player_names: List[str]) -> None
    """Called when game begins."""

def on_game_end(winner_id: int, final_state: GameState) -> None
    """Called when game ends."""

def on_supply_distributed(player_id: int, placements: Dict[int, int], game_state: GameState) -> None
    """Called after supply dice are distributed."""
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
- Origin at top-left (0, 0)
- `x` increases rightward, `y` increases downward
- All coordinates are 0-based integers
- `grid_lookup[y][x]` returns territory_id or -1 for out-of-board

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
- Adjacencies must be **symmetric**: if A is adjacent to B, then B is adjacent to A
- No self-loops: territory cannot be adjacent to itself
- `build_attack_pairs()` validates these invariants and fails fast if violated

#### Supporting Static Types
```python
@dataclass(frozen=True)
class Position:
    x: int
    y: int

@dataclass(frozen=True)
class BorderSegment:
    start: Position                             # Line segment for territory border
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

**Purpose**: Lean, dynamic snapshot of current game state. Contains only data that changes during gameplay - references static MapLayout by territory IDs.

#### TerritoryState (Dynamic Territory Data)
```python
@dataclass(frozen=True)
class TerritoryState:
    owner_id: int                               # Which player owns this territory
    dice_count: int                             # Current military strength
```

**Purpose**: Only the changing aspects of a territory. References TerritoryLayout.id for static properties.

#### PlayerInfo (Player Status)
```python
@dataclass(frozen=True)
class PlayerInfo:
    id: int
    name: str
    color: str                                  # Hex color code for rendering
    owned_territory_ids: List[int]             # DERIVED: List of territory IDs this player owns
    total_dice: int                             # Total dice across all territories
    supply_dice: int                            # Supply they'll receive at start of their next SUPPLY phase (0 if eliminated)
    is_alive: bool                              # False if eliminated
    largest_connected_region: int               # Size of largest connected territory group
```

**Purpose**: Complete player status information. Updated each turn to reflect current power and resources.

**Invariants**:
- `owned_territory_ids` is **derived** from territory ownership and maintained by the engine
- When `player_id == active_player_id` and `phase == SUPPLY`: `supply_dice == CoreState.supply_remaining`
- Otherwise: `supply_dice` shows the supply they'll receive on their next turn (or 0 if eliminated)

### Game Enumerations

#### GamePhase (Turn Phase)
```python
class GamePhase(Enum):
    SETUP = "setup"                             # Initial game setup
    ATTACK = "attack"                           # Player can make attacks
    SUPPLY = "supply"                           # Player receives and distributes dice
    GAME_OVER = "game_over"                    # Game has ended
```

**Purpose**: Tracks current phase within a turn. Different actions are valid in different phases:
- **ATTACK**: Player can attack adjacent enemy territories or end turn
- **SUPPLY**: Player receives dice based on largest connected region and distributes them
- **GAME_OVER**: Game has ended, winner determined

#### BattleSystem (Combat Rules)
```python
class BattleSystem(Enum):
    AUTO_ALL_BUT_ONE = "auto_all_but_one"      # Attacker uses all dice except 1, no choice needed
    # VARIABLE = "variable"                    # Future: AttackAction would include dice_count field
```

**Purpose**: Defines combat mechanics. With `AUTO_ALL_BUT_ONE`, attacks automatically use maximum available dice (leaving 1 behind). No dice count specification needed in `AttackAction`.

#### InvalidAction (Error Codes)
```python
class InvalidAction(Enum):
    ILLEGAL_ATTACK = "illegal_attack"           # Attack violates adjacency or ownership rules
    OVER_SUPPLY_LIMIT = "over_supply_limit"     # Supply placement exceeds limits
    NOT_YOUR_TURN = "not_your_turn"             # Action from wrong player
    BAD_PHASE = "bad_phase"                     # Action invalid in current phase
    TERRITORY_NOT_OWNED = "territory_not_owned" # Trying to place dice on enemy territory
    INSUFFICIENT_DICE = "insufficient_dice"     # Not enough dice for attack
```

**Purpose**: Machine-readable error codes for precise error handling. Clients should branch on `error_code` rather than parsing `error_message` strings.

#### PenaltyReason (Penalty Types)
```python
class PenaltyReason(Enum):
    TIMEOUT = "timeout"                         # Turn time limit exceeded
    INVALID_ACTION = "invalid_action"           # Client sent invalid action
```

**Purpose**: Reasons for applying penalties. Separate from InvalidAction to allow flexible penalty policies.

#### SupplyPolicy (Supply Distribution Rules)
```python
class SupplyPolicy(Enum):
    MUST_PLACE_ALL = "must_place_all"          # Must distribute all supply dice
    ALLOW_EARLY_END = "allow_early_end"         # Can end turn early, forfeiting remaining dice
```

**Purpose**: Controls whether players can end their turn during SUPPLY phase with unplaced dice.

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
    attacker_territory_id: int                  # Territory initiating the attack
    defender_territory_id: int                  # Territory being attacked
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
    placements: Dict[int, int]                  # {territory_id: dice_to_add}
```

**Validation Rules**:
- If `supply_policy == MUST_PLACE_ALL`: `sum(placements.values()) == supply_remaining`
- If `supply_policy == ALLOW_EARLY_END`: `sum(placements.values()) <= supply_remaining`
- All territories in `placements.keys()` must be owned by `player_id`
- For each territory: `current_dice + dice_to_add <= max_dice_per_territory`
- Dictionary iteration must be **deterministic** (sort by territory_id) for reproducibility
- On violation: entire action rejected with `error_code=OVER_SUPPLY_LIMIT` (no partial application)

**Supply Exhaustion (Deadlock Escape)**:
- If `phase==SUPPLY`, `supply_policy==MUST_PLACE_ALL`, `supply_remaining>0` **and** no territories can accept dice:
  - Engine sets `supply_remaining=0` (discards unplaceable dice)
  - Allows `EndTurnAction` to avoid deadlock

### BattleResult (Combat Outcome)
```python
@dataclass(frozen=True)
class BattleResult:
    """Complete, self-contained information about a battle outcome."""
    # Pre-battle state
    attacker_player_id: int                     # Player who initiated the attack
    defender_player_id: int                     # Player who defended
    attacker_territory_id: int                  # Territory that initiated attack
    defender_territory_id: int                  # Territory that was attacked
    attacker_dice_count: int                    # Number of dice used in attack
    defender_dice_count: int                    # Number of dice used in defense
    
    # Battle execution
    attacker_rolls: List[int]                   # Actual dice roll results for attacker
    defender_rolls: List[int]                   # Actual dice roll results for defender
    attacker_wins: bool                         # True if attacker captured territory
    attacker_casualties: int                    # Dice lost by attacker
    defender_casualties: int                    # Dice lost by defender
    
    # Post-battle state (fully self-contained)
    post_attacker_source_dice: int              # Dice remaining in attacking territory
    post_defender_target_dice: int              # Dice remaining/placed in target territory
    new_owner_id: int                           # Owner after battle (attacker_id if captured)
    dice_transferred: int                        # Dice moved to captured territory (AUTO_ALL_BUT_ONE)
```

**Purpose**: Complete, self-contained battle information. No GameState lookup needed.

**AUTO_ALL_BUT_ONE Transfer Rule**: 
- Attacks use all dice except 1 from source territory
- On **capture**: 
  - `dice_transferred = attacker_dice_count` (all attacking dice move)
  - `post_attacker_source_dice = 1` (always leave 1 behind)
  - `post_defender_target_dice = dice_transferred`
  - `new_owner_id = attacker_player_id`
- On **failure**:
  - `dice_transferred = 0`
  - `post_attacker_source_dice = original_dice - attacker_casualties`
  - `post_defender_target_dice = original_dice - defender_casualties`
  - `new_owner_id = defender_player_id`

### Game Configuration

```python
@dataclass(frozen=True)
class GameConfig:
    """Complete game configuration for reproducible, well-defined games."""
    name: str                                   # Configuration name/description
    map_layout: MapLayout                       # Static map definition
    
    # Player Configuration
    max_players: int                            # Maximum players allowed
    min_players: int                            # Minimum players required
    
    # Game Rules
    max_dice_per_territory: int                 # Dice limit per territory
    initial_dice_per_territory: int             # Starting dice count
    max_supply_dice: int                        # Maximum supply dice a player can hold
    supply_dice_calculation: str                # "largest_connected", "territory_count", etc.
    battle_system: BattleSystem                 # Combat mechanics (AUTO_ALL_BUT_ONE, etc.)
    supply_policy: SupplyPolicy                 # MUST_PLACE_ALL or ALLOW_EARLY_END
    
    # Game Flow
    turn_timeout_seconds: Optional[int]         # Time limit per turn (None = no limit)
    timeout_policy: Literal["auto_end_turn", "skip_next_turn"] = "auto_end_turn"  # What happens on timeout
    max_turns: Optional[int]                    # Game length limit (None = no limit)
    
    # Reproducibility
    random_seed: Optional[int]                  # For deterministic games
    
    # Metadata
    created_timestamp: str                      # When config was created
    schema_version: str                         # DTO schema version (e.g., "1.0")
    rules_version: str                          # Game rules version (e.g., "2024.1")
```

**Purpose**: Complete, explicit game setup that defines all rules, limits, and parameters. Enables reproducible games and clear rule communication.

### TurnContext (Reduces API Chattiness)
```python
@dataclass(frozen=True)
class SupplyDescriptor:
    """Describes available supply placement options."""
    supply_remaining: int              # Total dice to place
    eligible_territories: List[int]   # Territories with room (dice < max)
    per_territory_cap: int           # Max dice per territory from config

@dataclass
class TurnContext:
    game_state: GameState          # Complete current state
    valid_actions: List[Action]    # Currently legal actions (ordered deterministically)
    current_player_id: int         # Convenience field
    supply: Optional[SupplyDescriptor] = None  # Present only in SUPPLY phase
```

**Purpose**: Bundles everything needed for a turn decision into a single API call.

**Enumeration Order (Deterministic)**:
- In **ATTACK**: `AttackAction`s listed in `attack_pairs.pairs` order, then `EndTurnAction`
- In **SUPPLY**:
  - `MUST_PLACE_ALL`: `EndTurnAction` only when `supply_remaining == 0` or supply exhaustion
  - `ALLOW_EARLY_END`: `EndTurnAction` always present
  - `DistributeSupplyAction` is **never** enumerated (combinatorial explosion avoided)

### ActionResult (Self-Documenting Returns)
```python
@dataclass 
class ActionResult:
    success: bool                           # Action succeeded
    new_game_state: GameState              # Updated state (unchanged if failed)
    battle_result: Optional[BattleResult] = None  # Combat details if attack
    supply_placements: Optional[Dict[int, int]] = None  # Supply distribution if supply phase
    error_code: Optional[InvalidAction] = None    # Machine-readable error code
    error_message: Optional[str] = None           # Human-readable error description
    tick_id: int = 0                             # Monotonic step counter (last atomic step)
    state_hash: int = 0                          # 64-bit hash for state verification
```

**Purpose**: Comprehensive result object with all transition metadata.

**Key Fields**:
- `new_game_state`: Updated on success, unchanged on failure
- `error_code`: Machine-readable for programmatic handling
- `tick_id`: For compound actions (e.g., DistributeSupplyAction), reports the **last** atomic step's tick
- `state_hash`: 64-bit hash of final state for verification
- `supply_placements`: Aggregated from atomic place_one_die operations (deterministic order)

## Communication Flow

### Complete Game Sequence
```
1. PLAYER REGISTRATION
   For each player:
      Coordinator: register_player(client, name="RandomAI", player_type="random_ai")
      Returns: player_id
      Coordinator stores: {player_id: {client, name, type}}

2. GAME SETUP
   Coordinator → Engine: initialize_game(player_ids)
   Coordinator → Players: on_game_start(player_id, config)
   Coordinator → Observers: on_game_start(config, player_names)

3. TURN EXECUTION LOOP
   While self.current_state.winner_id is None:
   
   a) Get Turn Information (1 API call instead of 3)
      Coordinator → Engine: get_turn_context()
      Returns: TurnContext{game_state, valid_actions, current_player_id, supply}
   
   b) Player Decision
      Coordinator → Observer: on_turn_start(player_id, context.game_state)
      Coordinator → Player: get_action(context)
   
   c) Execute Action
      Coordinator → Engine: apply_action(chosen_action)
      Returns: ActionResult{success, new_game_state, battle_result, supply_placements, error_code, ...}
   
   d) Handle Results
      IF success:
          self.current_state = result.new_game_state
          Coordinator → Observers: on_action_executed(action, result)
          IF battle_result:
              Coordinator → All Players: on_battle_result(battle_result)
          IF supply_placements:
              Coordinator → Observers: on_supply_distributed(player_id, supply_placements, game_state)
      ELSE:
          # State unchanged on failure
          Coordinator → Observers: on_invalid_action(player_id, action, error_code, error_message)
          # Apply penalty through engine (engine owns all mutations)
          penalty_result = engine.apply_penalty(player_id, PenaltyReason.INVALID_ACTION)
          self.current_state = penalty_result.new_game_state
   
   e) Check Game End (single source of truth)
      IF self.current_state.winner_id is not None:
          Break loop

4. GAME END
   Coordinator → Players: on_game_end(winner_id)
   Coordinator → Observers: on_game_end(winner_id, final_state)
```

## Phase Transitions

| Current Phase | Action | Result |
|--------------|--------|---------|
| ATTACK | EndTurnAction | → SUPPLY (same player), compute supply dice |
| SUPPLY | EndTurnAction | → ATTACK (next alive player) |
| SUPPLY | DistributeSupplyAction | Remains in SUPPLY |
| Any | Invalid action | No phase change |
| Any | Penalty | Depends on penalty policy |

**Tick Semantics**: Every successful state transition increments `tick_id` exactly once.

## Architectural Principles

### 1. Hub-and-Spoke Communication
- GameCoordinator is the central hub
- Engine and Players are spokes that only respond
- No direct Engine↔Player communication
- No Player↔Player communication

### 2. Request-Response Pattern
- Engine never initiates calls (purely reactive)
- Players never initiate calls (purely reactive)
- Coordinator orchestrates all communication
- All interactions are synchronous

### 3. Bundled Information Transfer
- TurnContext bundles state + valid_actions (reduces API calls 3→1)
- ActionResult bundles success + new_state + battle_info (eliminates separate state queries)
- DTOs are self-documenting and extensible

### 4. Pure Data Transfer
- All DTOs contain only serializable data
- No object references or business logic in DTOs
- Network/storage/serialization compatible

### 5. Error Handling Strategy
- Engine owns all state mutations
- Invalid actions don't change state
- Penalties applied through engine API
- Observers notified for debugging

## Engine Core API (RL-Friendly Internals)

**Who can call this**: Internal engine implementation only. Not exposed to Coordinator or Players.

The GameEngine Service internally uses a lower-level Core API optimized for RL training and reproducibility. This API is an internal implementation detail that enables future RL integration without breaking the public API.

### Why Build Core API Now

These aren't optional features - they're **foundational data-model decisions** that shape everything:

1. **Masks vs Enumerations**: Switching later forces changes across logs, observers, tests, GUIs
2. **Sequential Supply**: Changing granularity later breaks invariants, replays, and test fixtures
3. **Stable Action Indices**: The `(src,dst)` index table is a contract - changing it invalidates all datasets
4. **RNG Streams**: Adding later means old logs can't be replayed bit-exact
5. **State Hash**: Enables cheap golden tests from day 1 - retrofitting invalidates test logs
6. **Canonicalization**: Deciding now keeps owner remapping a thin view vs deep surgery later

Cost now: ~300 LOC. Cost later: Rewrite validators, observers, replays, logs, regenerate datasets.

### Core Data Structures

#### AttackPairs (Stable Action Indexing)
```python
@dataclass(frozen=True)
class AttackPairs:
    """Canonical, deterministic ordering of all possible attacks."""
    pairs: List[Tuple[int, int]]    # [(src_territory_id, dst_territory_id), ...]
    hash64: int                     # Stable 64-bit hash for version checking
    index_map: Dict[Tuple[int, int], int]  # (src, dst) -> index for O(1) lookup

def build_attack_pairs(layout: MapLayout) -> AttackPairs:
    """Build canonical attack pairs once per map. Sort by (src, dst) for determinism."""
```

**Purpose**: Creates a stable, global indexing of all possible attacks. Essential for RL models that need consistent action spaces across games.

#### CoreState (Dense Internal Representation)
```python
@dataclass(frozen=True)
class CoreState:
    """Dense, array-based game state optimized for RL and performance."""
    # Core game state
    active_player_id: int
    turn_number: int
    phase: GamePhase
    winner_id: Optional[int]
    
    # Territory data as dense typed arrays (index = territory_id)
    owners: np.ndarray       # shape=(num_territories,) dtype=int32
    dice: np.ndarray         # shape=(num_territories,) dtype=int16
    
    # Player-specific state
    supply_remaining: int    # Dice left to place for active player
    player_alive: np.ndarray # shape=(num_players,) dtype=bool
    
    # Cached computations (updated incrementally)
    largest_connected: np.ndarray  # shape=(num_players,) dtype=int32
    territory_counts: np.ndarray   # shape=(num_players,) dtype=int32
    
    # Reproducibility tracking
    rng_counters: Dict[str, int]   # {"setup": N, "turn": N, "battle": N}
    tick_id: int                   # Monotonic step counter
```

**Purpose**: Dense array representation enables fast numpy operations and efficient serialization. All derived data is cached and updated incrementally.

#### ActionMasks (Boolean Legality Arrays)
```python
@dataclass(frozen=True)
class ActionMasks:
    """Boolean arrays indicating legal actions - no enumeration needed."""
    attack: np.ndarray           # shape=(len(attack_pairs),) dtype=bool
    place_one_die: np.ndarray    # shape=(num_territories,) dtype=bool
    can_end_turn: bool

def legal_masks(state: CoreState, attack_pairs: AttackPairs, config: GameConfig) -> ActionMasks:
    """
    Compute legality as boolean masks. O(1) per check, no list building.
    
    Mask Rules:
    - attack[k] = True iff:
        * (src, dst) = attack_pairs.pairs[k]
        * owners[src] == active_player_id
        * owners[dst] != active_player_id  
        * dice[src] >= 2 (must leave one die behind)
        * phase == ATTACK
    
    - place_one_die[t] = True iff:
        * owners[t] == active_player_id
        * dice[t] < max_dice_per_territory
        * phase == SUPPLY
        * supply_remaining > 0
    
    - can_end_turn = True iff:
        * phase == ATTACK, OR
        * phase == SUPPLY AND (supply_policy == ALLOW_EARLY_END OR supply_remaining == 0)
    
    Supply Exhaustion: If MUST_PLACE_ALL and supply_remaining > 0 but no place_one_die
    entries are True, the engine first sets supply_remaining = 0 for mask computation;
    therefore can_end_turn = True.
    """
```

**Purpose**: Avoids expensive enumeration. RL agents need masks for action masking. Coordinator can still enumerate for backward compatibility.

### Core Actions (Atomic Primitives)

#### CoreAction (Low-Level Primitives)
```python
@dataclass(frozen=True)
class CoreAction:
    """Atomic action primitives - no compound actions."""
    kind: Literal["attack", "place_one_die", "end_turn"]
    attack_index: Optional[int] = None      # Index into attack_pairs.pairs
    territory_id: Optional[int] = None      # For place_one_die

# Note: No "distribute_all_supply" - atomicity is key for RL
```

**Purpose**: Atomic primitives enable fine-grained control and learning. The Coordinator translates compound actions (like DistributeSupplyAction) into sequences of primitives.

#### StepInfo (Transition Metadata)
```python
@dataclass(frozen=True)
class StepInfo:
    """Rich metadata about the state transition."""
    battle_result: Optional[BattleResult]   # If attack occurred
    rng_counters: Dict[str, int]           # Updated RNG stream positions
    tick_id: int                            # New tick counter
    state_hash: int                         # 64-bit hash of new state
    delta: Optional['StateDelta']           # Changes since last state

def step(state: CoreState, action: CoreAction, config: GameConfig, 
         attack_pairs: AttackPairs) -> Tuple[CoreState, StepInfo]:
    """
    Apply atomic action to state. Updates RNG counters, computes hash.
    Validates action against masks - returns same state if invalid.
    """
```

**Purpose**: Single source of truth for state transitions. Returns rich metadata for debugging, replay, and learning.

### Reproducibility & Canonicalization

#### RNG Streams (Deterministic Randomness)
```python
@dataclass(frozen=True)
class RNGStream:
    """Deterministic RNG with explicit counter tracking."""
    name: str           # "setup", "turn", "battle"
    seed: int          # Stream-specific seed
    counter: int       # Number of values consumed

def reseed(state: CoreState, master_seed: int) -> CoreState:
    """
    Derive deterministic per-stream seeds from master_seed.
    Resets all counters to 0.
    Algorithm: SplitMix64
    - setup_seed = splitmix64(master_seed ^ 0x9E3779B97F4A7C15)
    - turn_seed = splitmix64(master_seed ^ 0xBF58476D1CE4E5B9)
    - battle_seed = splitmix64(master_seed ^ 0x94D049BB133111EB)
    """

def consume_random(stream: RNGStream, count: int = 1) -> Tuple[List[int], RNGStream]:
    """Consume N random values, return values and updated stream with counter += count."""
```

**Purpose**: Perfect reproducibility. Same seed + same actions = identical game, down to individual die rolls.

**Dice Roll Order**:
- Battle: Attacker rolls first (all dice), then defender (all dice)
- Each die consumes one 32-bit value from the battle stream
- Counter increments by exact number of dice rolled

#### State Hashing (Golden Testing)
```python
def state_hash(state: CoreState) -> int:
    """
    Compute 64-bit hash of canonical state representation.
    Covers: owners, dice, active_player, phase, turn, supply, winner.
    Uses xxhash, FNV-1a, or similar fast hash.
    """

def canonical_bytes(state: CoreState) -> bytes:
    """
    Serialize state to canonical byte representation.
    Fixed order, no player ID dependencies.
    """

def canonical_bytes_layout(layout: MapLayout) -> bytes:
    """
    Serialize layout deterministically for hashing.
    Territories sorted by id, then fields in fixed order.
    """
```

**Purpose**: Instant detection of state divergence. Essential for debugging and ensuring parity across implementations.

#### Canonicalization (Player-Agnostic Views)
```python
@dataclass(frozen=True)
class CanonicalView:
    """State from active player's perspective - player 0 is always self."""
    owners: np.ndarray          # Remapped: active=0, others=1..N-1
    dice: np.ndarray            # Unchanged
    phase: GamePhase
    supply_remaining: int
    
    # Permutation mappings for reverse translation
    player_perm: np.ndarray     # old_id -> new_id
    inv_perm: np.ndarray        # new_id -> old_id

def canonicalize(state: CoreState) -> CanonicalView:
    """
    Remap player IDs so active player is always 0.
    Other players mapped to 1..N-1 in consistent order.
    Eliminated players mapped to special value (e.g., -1).
    """
```

**Purpose**: RL agents always see themselves as player 0. Enables training one model that works from any position.

### Optional: Delta Mode (Efficient Updates)

#### StateDelta (Incremental Changes)
```python
@dataclass(frozen=True)
class StateDelta:
    """Describes what changed in the last transition."""
    changed_territories: List[int]      # Which territories changed
    new_owners: np.ndarray              # New owner for each changed territory
    new_dice: np.ndarray                # New dice for each changed territory
    
    # Phase/turn changes
    phase_changed: bool
    new_phase: Optional[GamePhase]
    turn_advanced: bool
    new_turn: Optional[int]
    
    # Game ending
    game_ended: bool
    winner: Optional[int]

def compute_delta(old_state: CoreState, new_state: CoreState) -> StateDelta:
    """Compute minimal delta between states."""
```

**Purpose**: Efficient state synchronization for networked play or large-scale training. Only transmit what changed.

### Integration with GameEngine Service

**Who can call this**: Public API callable by GameCoordinator.

The GameEngine Service (public API) wraps the Engine Core (internal API):

```python
class GameEngine:  # This is the public GameEngine Service
    def __init__(self, config: GameConfig):
        self.config = config
        self.attack_pairs = build_attack_pairs(config.map_layout)
        self.core_state = None
        
    def initialize_game(self, player_ids: List[int]) -> None:
        """Public API - initialize game."""
        # Build initial CoreState
        self.core_state = self._build_initial_state(player_ids)
        
    def get_turn_context(self) -> TurnContext:
        """Public API - get current turn info."""
        # Get masks from core
        masks = legal_masks(self.core_state, self.attack_pairs, self.config)
        
        # Convert masks to Action objects for backward compatibility
        valid_actions = self._masks_to_actions(masks)
        
        # Convert CoreState to GameState DTO
        game_state = self._core_to_game_state(self.core_state)
        
        # Build supply descriptor if in SUPPLY phase
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
        """Public API - apply player action."""
        # Validate actor
        if action.player_id != self.core_state.active_player_id:
            return ActionResult(
                success=False,
                new_game_state=self._core_to_game_state(self.core_state),
                error_code=InvalidAction.NOT_YOUR_TURN,
                error_message="Not your turn",
                tick_id=self.core_state.tick_id,
                state_hash=state_hash(self.core_state)
            )
        
        # Convert high-level Action to CoreAction(s)
        # Implementation handles AttackAction, DistributeSupplyAction, EndTurnAction
        # Returns comprehensive ActionResult with all fields populated
        ...
    
    def apply_penalty(self, player_id: int, reason: PenaltyReason) -> ActionResult:
        """
        Public API - apply penalty.
        MUST increment tick_id exactly once.
        MUST NOT consume RNG values.
        Returns ActionResult with updated state.
        """
        ...
```

### Capabilities Discovery

```python
def get_capabilities(config: GameConfig, layout: MapLayout) -> Dict[str, Any]:
    """
    Return capability metadata for version checking and compatibility.
    """
    attack_pairs = build_attack_pairs(layout)
    return {
        "rules_version": config.rules_version,
        "schema_version": config.schema_version,
        "layout_hash": xxhash64(canonical_bytes_layout(layout)),  # Detect board mismatches
        "action_index_hash": attack_pairs.hash64,  # Critical for RL model compatibility
        "num_territories": len(layout.territories),
        "num_attack_pairs": len(attack_pairs.pairs),
        "battle_system": config.battle_system.value,
        "supply_policy": config.supply_policy.value,
        "max_dice_per_territory": config.max_dice_per_territory,
        "supports_delta": True,
        "rng_streams": ["setup", "turn", "battle"],
    }
```

**Purpose**: RL models can verify they're compatible with this game instance. Essential for loading pre-trained models.

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

This API design achieves maximum simplicity and efficiency. The PlayerClient contract is crystal clear: "Given a `TurnContext` with **currently legal** actions, select one of them." The internal Core API ensures we can add RL training later without touching the public API.