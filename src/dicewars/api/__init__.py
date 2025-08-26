"""Public API exports."""

from .types import (
    # Map types (from M1)
    Position, BorderSegment, TerritoryLayout, MapLayout,
    
    # Enums
    GamePhase, BattleSystem, SupplyPolicy, TimeoutPolicy, 
    WinnerPolicy, TiebreakToken, InvalidAction,
    
    # Actions
    AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction,
    
    # Results
    BattleResult, ActionResult, StateDelta,
    
    # State
    GameState, TurnContext, SupplyDescriptor,
    
    # Config
    GameConfig, Capabilities
)

from .client import PlayerClient
from .observer import GameObserver
from .coordinator import GameCoordinator
from .engine import GameEngine

__all__ = [
    # Map types
    'Position', 'BorderSegment', 'TerritoryLayout', 'MapLayout',
    
    # Enums
    'GamePhase', 'BattleSystem', 'SupplyPolicy', 'TimeoutPolicy',
    'WinnerPolicy', 'TiebreakToken', 'InvalidAction',
    
    # Actions
    'AttackAction', 'EndTurnAction', 'DistributeSupplyAction', 'PenaltyAction',
    
    # Results
    'BattleResult', 'ActionResult', 'StateDelta',
    
    # State
    'GameState', 'TurnContext', 'SupplyDescriptor',
    
    # Config
    'GameConfig', 'Capabilities',
    
    # Interfaces
    'PlayerClient', 'GameObserver', 'GameCoordinator', 'GameEngine'
]
