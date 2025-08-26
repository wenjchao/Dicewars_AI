"""Player client interface."""

from abc import ABC, abstractmethod
from typing import Union
from .types import (
    TurnContext, GameConfig, GameState,
    AttackAction, EndTurnAction, DistributeSupplyAction
)


class PlayerClient(ABC):
    """Player client interface."""
    
    @abstractmethod
    def get_action(
        self, 
        context: TurnContext
    ) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
        """Get player's action for current turn."""
        pass
    
    def on_game_start(self, config: GameConfig, player_id: int) -> None:
        """Called when game starts."""
        pass
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        pass