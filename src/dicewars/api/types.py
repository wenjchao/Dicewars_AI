"""Public API types and data structures."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any, Tuple
from enum import Enum


@dataclass(frozen=True)
class Position:
    """A coordinate position on the game grid."""
    x: int  # e 0
    y: int  # e 0


@dataclass(frozen=True)
class BorderSegment:
    """A line segment forming part of a territory border."""
    start: Position
    end: Position


@dataclass(frozen=True)
class TerritoryLayout:
    """Static layout information for a single territory."""
    id: int  # TerritoryID, e 0, contiguous 0..N-1
    name: str
    tiles: List[Position]  # Grid positions occupied by this territory
    adjacencies: List[int]  # List of adjacent territory IDs
    border: List[BorderSegment]  # Visual border for rendering


@dataclass(frozen=True)
class MapLayout:
    """Complete static map layout information."""
    map_name: str
    dimensions: Position  # (width, height)
    territories: Dict[int, TerritoryLayout]  # territory_id -> layout
    grid_lookup: List[List[int]]  # grid[y][x] -> territory_id or -1

    def __post_init__(self) -> None:
        """Validate map layout constraints."""
        # Territory IDs must be contiguous 0..N-1
        territory_ids = set(self.territories.keys())
        expected_ids = set(range(len(self.territories)))
        if territory_ids != expected_ids:
            raise ValueError(f"Territory IDs must be contiguous 0..{len(self.territories)-1}")
        
        # Grid dimensions must match
        if len(self.grid_lookup) != self.dimensions.y:
            raise ValueError("Grid height mismatch")
        for row in self.grid_lookup:
            if len(row) != self.dimensions.x:
                raise ValueError("Grid width mismatch")
        
        # All territory references in grid must be valid
        for y, row in enumerate(self.grid_lookup):
            for x, territory_id in enumerate(row):
                if territory_id != -1 and territory_id not in self.territories:
                    raise ValueError(f"Invalid territory_id {territory_id} at grid[{y}][{x}]")


# Game Phase and Policy Enums

class GamePhase(Enum):
    """Game phase states."""
    SETUP = "setup"
    ATTACK = "attack" 
    SUPPLY = "supply"
    GAME_OVER = "game_over"


class BattleSystem(Enum):
    """Battle resolution system."""
    INDIVIDUAL_DICE_COMPARISON = "individual_dice_comparison"  # Compare dice pairwise, AUTO_ALL_BUT_ONE rules
    SUMMATION_DICE_COMPARISON = "summation_dice_comparison"    # Sum all dice, winner takes all
    MANUAL = "manual"  # For legacy compatibility


class SupplyPolicy(Enum):
    """Supply distribution policy."""
    ALLOW_EARLY_END = "allow_early_end"
    MUST_DISTRIBUTE_ALL = "must_distribute_all"


class SupplyCalculation(Enum):
    """Supply calculation algorithm."""
    TOTAL_TERRITORIES = "total_territories"      # floor(territories / 3), min 3
    LARGEST_CONNECTED = "largest_connected"      # Based on largest connected region
    FIXED_AMOUNT = "fixed_amount"                # Fixed amount per turn (e.g., 5)
    TERRITORIES_PLUS_BONUS = "territories_plus_bonus"  # Territories + region bonuses


class SupplyDistribution(Enum):
    """Supply distribution strategy for bots."""
    MANUAL = "manual"                # Human player manual input
    UNIFORM = "uniform"              # Distribute evenly across territories
    RANDOM = "random"                # Random distribution
    BATTLEFRONT = "battlefront"      # Focus on territories adjacent to enemies
    WEAKEST_FIRST = "weakest_first"  # Prioritize territories with fewest dice
    STRONGEST_FIRST = "strongest_first"  # Prioritize territories with most dice


class TimeoutPolicy(Enum):
    """Timeout penalty policy."""
    NO_PENALTY = "no_penalty"          # No penalty, continue normally
    AUTO_END_TURN = "auto_end_turn"
    SKIP_NEXT_TURN = "skip_next_turn"
    FORFEIT_GAME = "forfeit_game"


class WinnerPolicy(Enum):
    """Winner determination policy."""
    NONE = "none"
    MOST_TERRITORIES = "most_territories"
    MOST_TOTAL_DICE = "most_total_dice"
    LARGEST_CONNECTED = "largest_connected"
    LEXICOGRAPHIC = "lexicographic"


class TiebreakToken(Enum):
    """Tiebreak token for winner determination."""
    TERRITORIES = "territories"
    TOTAL_DICE = "total_dice"
    LARGEST_CONNECTED = "largest_connected"
    PLAYER_ID = "player_id"


class InvalidAction(Enum):
    """Invalid action error codes."""
    # Core violations
    NOT_YOUR_TURN = "not_your_turn"
    BAD_PHASE = "bad_phase"
    INVALID_TERRITORY = "invalid_territory"
    NOT_ADJACENT = "not_adjacent"
    NOT_OWNED = "not_owned"
    INSUFFICIENT_DICE = "insufficient_dice"
    
    # Supply violations
    ILLEGAL_END_TURN = "illegal_end_turn"
    SUPPLY_EXHAUSTED = "supply_exhausted"
    INVALID_PLACEMENT = "invalid_placement"
    ZERO_PLACEMENT = "zero_placement"  # v5
    EXCEEDS_MAX_DICE = "exceeds_max_dice"
    
    # Schema/protocol violations (v5)
    SCHEMA_MISMATCH = "schema_mismatch"
    UNKNOWN_ENUM = "unknown_enum"
    BAD_PAYLOAD = "bad_payload"
    UNKNOWN_ACTION_TYPE = "unknown_action_type"


# Action DTOs

@dataclass(frozen=True)
class AttackAction:
    """Attack action DTO."""
    attacker_territory_id: int
    defender_territory_id: int
    attack_index: int  # For RL indexing
    type: str = "attack"  # Literal["attack"]


@dataclass(frozen=True)
class EndTurnAction:
    """End turn action DTO."""
    type: str = "end_turn"  # Literal["end_turn"]


@dataclass(frozen=True)
class DistributeSupplyAction:
    """Distribute supply action DTO."""
    placements: Dict[int, int]  # territory_id -> dice_count
    type: str = "distribute_supply"  # Literal["distribute_supply"]


@dataclass(frozen=True)
class PenaltyAction:
    """Penalty action DTO (v5)."""
    reason: str  # e.g., "timeout", "invalid_action"
    penalty_type: str  # e.g., "auto_end_turn", "skip_next_turn"
    type: str = "penalty"  # Literal["penalty"]


# Result DTOs

@dataclass(frozen=True)
class BattleResult:
    """Battle resolution result."""
    attacker_rolls: List[int]  # Raw dice values (attacker first)
    defender_rolls: List[int]  # Raw dice values
    attacker_casualties: int  # Dice lost by attacker
    defender_casualties: int  # Dice lost by defender
    attack_pair_index: int    # v5: mirrors AttackAction.attack_index
    territory_conquered: bool # True if defender eliminated
    winner: str              # "attacker" or "defender"


@dataclass(frozen=True)
class PenaltyAction:
    """v5 penalty action (first-class action type)."""
    penalty_type: str            # "auto_end_turn" | "skip_next_turn" | "forfeit_game"  
    reason: str                  # "timeout" | "invalid_action" | "system"
    target_player_id: int        # Player receiving penalty
    type: str = "penalty"         # Always "penalty" for PenaltyAction
    
    def __post_init__(self):
        if self.type != "penalty":
            raise ValueError("PenaltyAction must have type='penalty'")


@dataclass(frozen=True)
class StateDelta:
    """State delta for optional delta mode (v5)."""
    changed_territories: List[int]
    new_owners: List[int]
    new_dice: List[int]


@dataclass(frozen=True)
class ActionResult:
    """Result of applying an action."""
    success: bool
    tick_id: str  # Decimal string (v5)
    state_hash: str  # Decimal string (v5)
    position_hash: str  # Decimal string (v5) - always present
    new_game_state: 'GameState'
    battle_result: Optional[BattleResult] = None
    penalty_action: Optional[PenaltyAction] = None  # v5: penalty actions
    error_code: Optional[str] = None
    error_data: Optional[Dict[str, Any]] = None  # v5: machine-readable context
    delta: Optional[StateDelta] = None  # v5: optional delta mode


# Game State DTO

@dataclass(frozen=True)
class GameState:
    """Complete game state."""
    owners: List[int]  # Territory owners (player_id or -1)
    dice: List[int]  # Dice counts per territory
    active_player_id: int
    phase: GamePhase
    turn_number: int
    tick_id: str  # Decimal string (v5)
    winner_id: Optional[int] = None
    eliminated_players: List[int] = field(default_factory=list)


# Turn Context DTO

@dataclass(frozen=True)
class SupplyDescriptor:
    """Supply phase information."""
    player_id: int
    supply_remaining: int
    can_end_early: bool
    territories_owned: List[int]
    max_dice_per_territory: int


@dataclass(frozen=True)
class TurnContext:
    """Context for player decision."""
    game_state: GameState
    valid_actions: List[Union[AttackAction, EndTurnAction, DistributeSupplyAction]]
    supply: Optional[SupplyDescriptor] = None
    time_remaining_ms: Optional[int] = None


# Configuration DTOs

@dataclass(frozen=True)
class GameConfig:
    """Game configuration."""
    map_layout: MapLayout
    num_players: int
    battle_system: BattleSystem = BattleSystem.INDIVIDUAL_DICE_COMPARISON
    supply_policy: SupplyPolicy = SupplyPolicy.ALLOW_EARLY_END
    supply_calculation: SupplyCalculation = SupplyCalculation.TOTAL_TERRITORIES
    supply_distribution: SupplyDistribution = SupplyDistribution.MANUAL
    fixed_supply_amount: int = 5  # Used when supply_calculation is FIXED_AMOUNT
    allow_multiple_supply_phases: bool = True  # Allow ATTACK → SUPPLY → ATTACK → etc.
    timeout_policy: TimeoutPolicy = TimeoutPolicy.AUTO_END_TURN
    timeout_ms: int = 30000
    winner_policy: WinnerPolicy = WinnerPolicy.MOST_TERRITORIES
    winner_tiebreak_chain: List[TiebreakToken] = field(default_factory=lambda: [
        TiebreakToken.TERRITORIES,
        TiebreakToken.TOTAL_DICE,
        TiebreakToken.PLAYER_ID
    ])
    max_turns: int = 1000
    max_dice_per_territory: int = 8
    initial_dice_per_territory: int = 3
    seed: Optional[int] = None


@dataclass(frozen=True)
class Capabilities:
    """Engine capabilities response."""
    rules_version: str
    schema_version: str
    map_name: str
    num_players: int
    num_territories: int
    layout_hash: str  # Decimal string (v5)
    action_index_hash: str  # Decimal string (v5)
    winner_policy: str
    winner_tiebreak_chain: List[str]
    max_turns: int
    max_dice_per_territory: int
    supports_delta: bool = False
    supports_penalties: bool = True
    uint64_encoding: str = "decimal"  # v5