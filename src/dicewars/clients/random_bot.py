"""Random bot client implementation."""

import random
from typing import Union
from ..api.client import PlayerClient
from ..api.types import (
    TurnContext, GameConfig, GameState,
    AttackAction, EndTurnAction, DistributeSupplyAction
)


class RandomBot(PlayerClient):
    """Bot that makes random valid moves."""
    
    def __init__(self, name: str = "RandomBot", seed: int = None):
        """Initialize random bot.
        
        Args:
            name: Bot name for identification
            seed: Random seed for reproducible behavior
        """
        self.name = name
        self.player_id = None
        self.rng = random.Random(seed)
        
    def get_action(self, context: TurnContext) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
        """Get random valid action."""
        if not context.valid_actions:
            return EndTurnAction()
        
        # Handle manual supply distribution (only reached when distribution=MANUAL)
        if context.game_state.phase.value == "supply" and context.supply and context.supply.supply_remaining > 0:
            # Bot provides manual supply distribution when game is configured for it
            # Simple random distribution across owned territories
            territories = context.supply.territories_owned.copy()
            if territories and context.supply.supply_remaining > 0:
                placements = {}
                remaining = context.supply.supply_remaining
                
                while remaining > 0 and territories:
                    territory = self.rng.choice(territories)
                    current_dice = context.game_state.dice[territory] 
                    max_additional = context.supply.max_dice_per_territory - current_dice
                    
                    if max_additional > 0:
                        # Add 1-3 dice randomly
                        to_add = min(remaining, max_additional, self.rng.randint(1, min(3, remaining)))
                        placements[territory] = placements.get(territory, 0) + to_add
                        remaining -= to_add
                    else:
                        territories.remove(territory)
                
                if placements:
                    from ..api.types import DistributeSupplyAction
                    return DistributeSupplyAction(placements=placements)
            
            # If no placements possible, end turn
            return EndTurnAction()
        
        # Filter out EndTurnAction to prefer other actions
        non_end_turn_actions = [action for action in context.valid_actions 
                               if not isinstance(action, EndTurnAction)]
        
        if non_end_turn_actions and self.rng.random() < 0.8:  # 80% chance to take non-end-turn action
            return self.rng.choice(non_end_turn_actions)
        else:
            return EndTurnAction()
    
    def on_game_start(self, config: GameConfig, player_id: int) -> None:
        """Called when game starts."""
        self.player_id = player_id
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        pass
    
    def __str__(self) -> str:
        return f"{self.name}(P{self.player_id})" if self.player_id is not None else self.name


class PassiveBot(PlayerClient):
    """Bot that always ends turn immediately."""
    
    def __init__(self, name: str = "PassiveBot"):
        self.name = name
        self.player_id = None
    
    def get_action(self, context: TurnContext) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
        """Always end turn."""
        return EndTurnAction()
    
    def on_game_start(self, config: GameConfig, player_id: int) -> None:
        """Called when game starts."""
        self.player_id = player_id
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        pass
    
    def __str__(self) -> str:
        return f"{self.name}(P{self.player_id})" if self.player_id is not None else self.name


class AggressiveBot(PlayerClient):
    """Bot that always attacks when possible."""
    
    def __init__(self, name: str = "AggressiveBot", seed: int = None):
        """Initialize aggressive bot.
        
        Args:
            name: Bot name for identification  
            seed: Random seed for attack selection
        """
        self.name = name
        self.player_id = None
        self.rng = random.Random(seed)
    
    def get_action(self, context: TurnContext) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
        """Always attack if possible."""
        # Look for attack actions
        attack_actions = [action for action in context.valid_actions 
                         if isinstance(action, AttackAction)]
        
        if attack_actions:
            return self.rng.choice(attack_actions)
        else:
            return EndTurnAction()
    
    def on_game_start(self, config: GameConfig, player_id: int) -> None:
        """Called when game starts."""
        self.player_id = player_id
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        pass
    
    def __str__(self) -> str:
        return f"{self.name}(P{self.player_id})" if self.player_id is not None else self.name