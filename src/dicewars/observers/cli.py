"""CLI observer for game event logging and display."""

import time
from typing import Optional, Union, TextIO
import sys
from ..api.observer import GameObserver
from ..api.types import (
    GameConfig, GameState, ActionResult,
    AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction
)
from ..ui.cli.ascii_renderer import ASCIIRenderer


class CLIObserver(GameObserver):
    """Observer that logs game events to CLI."""
    
    def __init__(self, 
                 show_board: bool = True,
                 show_events: bool = True,
                 pause_between_turns: float = 1.0,
                 output: TextIO = sys.stdout):
        """Initialize CLI observer.
        
        Args:
            show_board: Whether to display the board after each action
            show_events: Whether to log individual events
            pause_between_turns: Seconds to pause between turns (0 = no pause)
            output: Output stream for messages
        """
        self.show_board = show_board
        self.show_events = show_events
        self.pause_between_turns = pause_between_turns
        self.output = output
        self.renderer: Optional[ASCIIRenderer] = None
        self.turn_count = 0
        self.action_count = 0
        
    def _log(self, message: str) -> None:
        """Log a message to output."""
        print(message, file=self.output)
    
    def _pause(self) -> None:
        """Pause if configured."""
        if self.pause_between_turns > 0:
            time.sleep(self.pause_between_turns)
    
    def on_game_start(self, config: GameConfig, initial_state: GameState) -> None:
        """Called when game starts."""
        self.renderer = ASCIIRenderer(config.map_layout)
        
        if self.show_events:
            self._log("*** GAME STARTED ***")
            self._log(f"Map: {config.map_layout.map_name}")
            self._log(f"Players: {config.num_players}")
            self._log(f"Max turns: {config.max_turns}")
            self._log(f"Battle system: {config.battle_system.value}")
            self._log(f"Timeout: {config.timeout_ms}ms")
            self._log("=" * 60)
        
        if self.show_board and self.renderer:
            self._log("\nInitial Board State:")
            self._log(self.renderer.render_full_state(initial_state))
            self._log("")
    
    def on_turn_start(self, player_id: int, turn_number: int) -> None:
        """Called when a new alive player enters ATTACK phase."""
        self.turn_count += 1
        
        if self.show_events:
            self._log(f"Turn {turn_number}: Player {player_id}'s turn")
        
        self._pause()
    
    def on_action_executed(
        self, 
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction, None],
        result: ActionResult
    ) -> None:
        """Called after any action is executed."""
        self.action_count += 1
        
        if self.show_events:
            if action is None:
                # Penalty action
                self._log(f"PENALTY applied: {result.error_data}")
            else:
                action_desc = self._describe_action(action)
                if result.success:
                    self._log(f"SUCCESS: {action_desc}")
                    
                    # Show battle result if available
                    if result.battle_result:
                        battle = result.battle_result
                        attacker_sum = sum(battle.attacker_rolls)
                        defender_sum = sum(battle.defender_rolls)
                        
                        self._log(f"   Battle: {battle.winner} wins")
                        self._log(f"   Rolls - Attacker: {battle.attacker_rolls} (sum={attacker_sum}), "
                                f"Defender: {battle.defender_rolls} (sum={defender_sum})")
                        
                        if battle.territory_conquered:
                            self._log(f"   Territory conquered! Casualties: A-{battle.attacker_casualties}, D-{battle.defender_casualties}")
                        else:
                            self._log(f"   Territory held! Casualties: A-{battle.attacker_casualties}, D-{battle.defender_casualties}")
                else:
                    self._log(f"FAILED: {action_desc} - {result.error_code}")
        
        # Show board state after significant actions
        if (self.show_board and self.renderer and result.success and
            (not action or not isinstance(action, EndTurnAction))):
            self._log(self.renderer.render_full_state(result.new_game_state))
            self._log("")
    
    def on_invalid_action(
        self,
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction],
        error_code: str,
        error_data: Optional[dict] = None
    ) -> None:
        """Called when an invalid action is attempted."""
        if self.show_events:
            action_desc = self._describe_action(action)
            self._log(f"INVALID action: {action_desc}")
            self._log(f"   Error: {error_code}")
            if error_data:
                self._log(f"   Details: {error_data}")
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        if self.show_events:
            self._log("*** GAME ENDED ***")
            self._log("=" * 60)
        
        if self.show_board and self.renderer:
            self._log("\nFinal Board State:")
            self._log(self.renderer.render_full_state(final_state))
        
        if self.show_events:
            self._log(f"\nGame Summary:")
            self._log(f"Total turns: {self.turn_count}")
            self._log(f"Total actions: {self.action_count}")
            
            if final_state.winner_id is not None:
                self._log(f"*** Winner: Player {final_state.winner_id} ***")
            else:
                self._log("No winner determined")
            
            # Show final player stats
            if self.renderer:
                self._log("\n" + self.renderer.render_player_stats(final_state))
    
    def _describe_action(
        self, 
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction]
    ) -> str:
        """Create human-readable description of an action."""
        if isinstance(action, AttackAction):
            return f"Attack: T{action.attacker_territory_id} -> T{action.defender_territory_id}"
        elif isinstance(action, EndTurnAction):
            return "End Turn"
        elif isinstance(action, DistributeSupplyAction):
            placements = ", ".join(f"T{tid}:+{dice}" for tid, dice in action.placements.items())
            return f"Supply: {placements}"
        elif isinstance(action, PenaltyAction):
            return f"Penalty: {action.reason} ({action.penalty_type})"
        else:
            return f"Unknown action: {type(action).__name__}"


class QuietCLIObserver(CLIObserver):
    """CLI observer that only shows final results."""
    
    def __init__(self, output: TextIO = sys.stdout):
        super().__init__(
            show_board=False,
            show_events=False,
            pause_between_turns=0,
            output=output
        )
    
    def on_game_start(self, config: GameConfig, initial_state: GameState) -> None:
        """Only set up renderer, no output."""
        self.renderer = ASCIIRenderer(config.map_layout)
    
    def on_turn_start(self, player_id: int, turn_number: int) -> None:
        """Count turns but don't output."""
        self.turn_count += 1
    
    def on_action_executed(self, action, result: ActionResult) -> None:
        """Count actions but don't output."""
        self.action_count += 1
    
    def on_invalid_action(self, action, error_code: str, error_data: Optional[dict] = None) -> None:
        """No output for invalid actions."""
        pass


class VerboseCLIObserver(CLIObserver):
    """CLI observer with maximum detail."""
    
    def __init__(self, output: TextIO = sys.stdout):
        super().__init__(
            show_board=True,
            show_events=True,
            pause_between_turns=2.0,  # Longer pauses for detailed viewing
            output=output
        )
    
    def on_action_executed(self, action, result: ActionResult) -> None:
        """Show extra details for verbose mode."""
        super().on_action_executed(action, result)
        
        if self.show_events and result.success:
            # Show state delta details
            if result.delta:
                delta = result.delta
                if delta.changed_territories:
                    self._log(f"   State changes: {len(delta.changed_territories)} territories affected")
            
            # Show hash information
            self._log(f"   Tick: {result.tick_id}, State hash: {result.state_hash[:8]}...{result.state_hash[-8:]}")