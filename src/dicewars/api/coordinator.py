"""Coordinator-facing engine interface."""

import time
from typing import List, Optional, Union
from .types import (
    GameConfig, GameState, AttackAction, EndTurnAction, 
    DistributeSupplyAction, GamePhase, InvalidAction
)
from .client import PlayerClient
from .observer import GameObserver
from ..engine.public import create_engine
from ..core.penalties import PenaltyManager


class GameCoordinator:
    """Game coordinator facade."""
    
    def __init__(
        self, 
        config: GameConfig,
        clients: List[PlayerClient],
        observers: Optional[List[GameObserver]] = None
    ) -> None:
        """Initialize coordinator."""
        self.config = config
        self.clients = clients
        self.observers = observers or []
        self.engine = create_engine(config)
        
        # M6: Initialize penalty manager
        self.penalty_manager = PenaltyManager(
            timeout_ms=config.timeout_ms,
            timeout_policy=config.timeout_policy
        )
        
        # Validate client count matches config
        if len(clients) != config.num_players:
            raise ValueError(f"Expected {config.num_players} clients, got {len(clients)}")
    
    def run(self) -> GameState:
        """Run game to completion."""
        # Notify observers of game start
        initial_state = self.engine.get_turn_context().game_state
        for observer in self.observers:
            observer.on_game_start(self.config, initial_state)
        
        # Notify clients of game start
        for i, client in enumerate(self.clients):
            client.on_game_start(self.config, i)
        
        # Main game loop
        while True:
            context = self.engine.get_turn_context()
            current_state = context.game_state
            
            # Check if game is over
            if current_state.phase == GamePhase.GAME_OVER:
                break
            
            current_player_id = current_state.active_player_id
            
            # Skip eliminated players
            if current_player_id in current_state.eliminated_players:
                # Apply penalty to advance to next player
                result = self.engine.apply_penalty("eliminated", "skip_next_turn")
                continue
            
            # Notify observers of turn start
            for observer in self.observers:
                observer.on_turn_start(current_player_id, current_state.turn_number)
            
            # Get action from client with timeout handling
            try:
                action = self._get_client_action(current_player_id, context)
                
                # Apply action
                result = self.engine.apply_action(action)
                
                # Notify observers
                for observer in self.observers:
                    if result.success:
                        observer.on_action_executed(action, result)
                    else:
                        observer.on_invalid_action(action, result.error_code, result.error_data)
                
                # If action was invalid, apply penalty based on policy
                if not result.success:
                    penalty_result = self._handle_invalid_action(result.error_code)
                    if penalty_result:
                        # M6: Window does NOT reset on invalid action (timeout can still occur)
                        for observer in self.observers:
                            observer.on_action_executed(penalty_result.penalty_action, penalty_result)
                
            except TimeoutError:
                # Handle timeout based on policy  
                penalty_result = self._handle_timeout()
                # M6: Reset window after penalty applied
                self.penalty_manager.reset_window()
                for observer in self.observers:
                    observer.on_action_executed(penalty_result.penalty_action, penalty_result)
            
            except Exception as e:
                # Handle unexpected errors
                penalty_result = self._handle_client_error(str(e))
                for observer in self.observers:
                    observer.on_action_executed(None, penalty_result)
        
        # Game is over
        final_state = self.engine.get_turn_context().game_state
        
        # Notify observers and clients
        for observer in self.observers:
            observer.on_game_end(final_state)
        
        for client in self.clients:
            client.on_game_end(final_state)
        
        return final_state
    
    def _get_client_action(
        self, 
        player_id: int, 
        context
    ) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
        """Get action from client with timeout handling."""
        client = self.clients[player_id]
        
        # M6: Start decision window before get_action()
        self.penalty_manager.start_decision_window()
        
        try:
            # Get action from client
            action = client.get_action(context)
            
            # Check for timeout after getting action
            if self.penalty_manager.check_timeout():
                self.penalty_manager.reset_window()
                raise TimeoutError(f"Client {player_id} exceeded timeout")
                
            # M6: Reset window on successful action
            self.penalty_manager.reset_window()
            return action
            
        except TimeoutError:
            # Don't reset window here - timeout penalty will reset it
            raise
        except Exception as e:
            # Other exceptions don't reset window (invalid actions can still timeout)
            raise e
    
    def _handle_invalid_action(self, error_code: str):
        """Handle invalid action - let engine decide penalty based on policy."""
        # Engine will determine penalty based on configured policy
        return self.engine.apply_penalty("invalid_action")
    
    def _handle_timeout(self):
        """Handle client timeout - let engine decide penalty based on policy."""
        # Engine will determine penalty based on configured timeout policy
        return self.engine.apply_penalty("timeout")
    
    def _handle_client_error(self, error_message: str):
        """Handle client exception - let engine decide penalty based on policy."""
        # Treat client errors as timeouts
        return self.engine.apply_penalty("client_error")