"""Public GameEngine interface."""

from abc import ABC, abstractmethod
from typing import Union
from .types import (
    GameConfig, Capabilities, TurnContext, ActionResult,
    AttackAction, EndTurnAction, DistributeSupplyAction
)


class GameEngine(ABC):
    """Public game engine interface."""
    
    @abstractmethod
    def __init__(self, config: GameConfig) -> None:
        """Initialize engine with configuration."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Capabilities:
        """Get engine capabilities."""
        pass
    
    @abstractmethod
    def get_turn_context(self) -> TurnContext:
        """Get current turn context (pure read)."""
        pass
    
    @abstractmethod
    def apply_action(
        self, 
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction]
    ) -> ActionResult:
        """Apply player action."""
        pass
    
    @abstractmethod
    def apply_penalty(self, reason: str, penalty_type: str) -> ActionResult:
        """Apply penalty action (v5)."""
        pass