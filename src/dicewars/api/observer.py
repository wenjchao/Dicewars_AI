"""Game observer interface."""

from abc import ABC
from typing import Optional, Union
from .types import (
    GameConfig, GameState, ActionResult,
    AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction
)


class GameObserver(ABC):
    """Game observer interface."""
    
    def on_game_start(self, config: GameConfig, initial_state: GameState) -> None:
        """Called when game starts."""
        pass
    
    def on_turn_start(self, player_id: int, turn_number: int) -> None:
        """Called when a new alive player enters ATTACK phase."""
        pass
    
    def on_action_executed(
        self, 
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction],
        result: ActionResult
    ) -> None:
        """Called after any action is executed."""
        pass
    
    def on_invalid_action(
        self,
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction],
        error_code: str,
        error_data: Optional[dict] = None
    ) -> None:
        """Called when an invalid action is attempted."""
        pass
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        pass