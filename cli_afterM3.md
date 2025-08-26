# CLI Implementation Plan (After M3)

**Goal**: Create a functional CLI interface for running Dice Wars games with ASCII visualization.

**Prerequisites**: M3 complete (walking skeleton with coordinator loop and observers)

**Estimated effort**: 4-6 hours

---

## Overview

After M3, we'll have a working game coordinator that can run games with EndTurnAction only. This provides the perfect foundation for a CLI interface that can:

1. **Load maps** from JSON files
2. **Run games** between bots or human players
3. **Display board state** in ASCII format
4. **Show game logs** with observer events
5. **Support replay** of completed games

The CLI will be built incrementally, starting with the basic functionality and expanding as more game mechanics are added in M4-M7.

---

## Implementation Plan

### Phase 1: Basic ASCII Renderer (After M3)

**Files to create:**
- `src/dicewars/ui/cli/ascii_renderer.py`
- `src/dicewars/observers/cli.py`
- `scripts/run_cli.py`

#### 1.1 ASCII Board Renderer

```python
# src/dicewars/ui/cli/ascii_renderer.py
"""ASCII rendering for CLI display."""

from typing import List, Dict
from ...api.types import GameState, MapLayout


class ASCIIRenderer:
    """Renders game state as ASCII art."""
    
    def __init__(self, map_layout: MapLayout):
        self.map_layout = map_layout
        self.width = map_layout.dimensions.x
        self.height = map_layout.dimensions.y
    
    def render_board(self, game_state: GameState) -> str:
        """Render current board state as ASCII."""
        lines = []
        
        # Header
        lines.append(f"=== {self.map_layout.map_name} ===")
        lines.append(f"Turn: {game_state.turn_number}, Active: P{game_state.active_player_id}, Phase: {game_state.phase.value}")
        lines.append(f"Tick: {game_state.tick_id}")
        lines.append("")
        
        # Board grid
        for y in range(self.height):
            row_chars = []
            for x in range(self.width):
                territory_id = self.map_layout.grid_lookup[y][x]
                if territory_id == -1:
                    row_chars.append("  .")
                else:
                    owner = game_state.owners[territory_id]
                    dice = game_state.dice[territory_id]
                    
                    if owner == -1:
                        # Neutral territory
                        row_chars.append(f"T{territory_id}:{dice}")
                    else:
                        # Player owned
                        row_chars.append(f"P{owner}:{dice}")
            
            lines.append(" ".join(row_chars))
        
        lines.append("")
        
        # Territory summary
        lines.append("Territories:")
        for tid, territory in self.map_layout.territories.items():
            owner = game_state.owners[tid]
            dice_count = game_state.dice[tid]
            owner_str = f"P{owner}" if owner != -1 else "Neutral"
            lines.append(f"  {territory.name} (T{tid}): {owner_str}, {dice_count} dice")
        
        return "\n".join(lines)
    
    def render_stats(self, game_state: GameState) -> str:
        """Render player statistics."""
        lines = []
        lines.append("=== Player Stats ===")
        
        # Count territories and dice per player
        player_territories = {}
        player_dice = {}
        
        for tid, owner in enumerate(game_state.owners):
            if owner != -1:
                player_territories[owner] = player_territories.get(owner, 0) + 1
                player_dice[owner] = player_dice.get(owner, 0) + game_state.dice[tid]
        
        for player_id in sorted(player_territories.keys()):
            territories = player_territories[player_id]
            dice = player_dice[player_id]
            status = "ELIMINATED" if player_id in game_state.eliminated_players else "ACTIVE"
            lines.append(f"  Player {player_id}: {territories} territories, {dice} dice [{status}]")
        
        return "\n".join(lines)
```

#### 1.2 CLI Observer

```python
# src/dicewars/observers/cli.py
"""CLI observer for live game display."""

import os
import time
from typing import Optional, Union
from ..api.observer import GameObserver
from ..api.types import (
    GameConfig, GameState, ActionResult,
    AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction
)
from ..ui.cli.ascii_renderer import ASCIIRenderer


class CLIObserver(GameObserver):
    """Live CLI observer with ASCII display."""
    
    def __init__(self, clear_screen: bool = True, delay_ms: int = 1000):
        self.clear_screen = clear_screen
        self.delay_ms = delay_ms
        self.renderer = None
        self.move_count = 0
    
    def on_game_start(self, config: GameConfig, initial_state: GameState) -> None:
        """Called when game starts."""
        self.renderer = ASCIIRenderer(config.map_layout)
        
        if self.clear_screen:
            os.system('clear' if os.name == 'posix' else 'cls')
        
        print("🎮 DICE WARS - Game Starting!")
        print("=" * 50)
        print(f"Map: {config.map_layout.map_name}")
        print(f"Players: {config.num_players}")
        print(f"Max Turns: {config.max_turns}")
        print()
        
        # Show initial board
        print(self.renderer.render_board(initial_state))
        print(self.renderer.render_stats(initial_state))
        
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)
    
    def on_turn_start(self, player_id: int, turn_number: int) -> None:
        """Called when a new alive player enters ATTACK phase."""
        print(f"\n🚀 Turn {turn_number}: Player {player_id}'s turn begins")
        print("-" * 30)
    
    def on_action_executed(
        self, 
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction],
        result: ActionResult
    ) -> None:
        """Called after any action is executed."""
        self.move_count += 1
        
        if isinstance(action, PenaltyAction):
            print(f"⚠️  PENALTY: {action.reason} -> {action.penalty_type}")
        elif isinstance(action, EndTurnAction):
            print(f"✋ Player {result.new_game_state.active_player_id} ended turn")
        elif isinstance(action, AttackAction):
            # Will be implemented in M4
            print(f"⚔️  Attack: T{action.attacker_territory_id} -> T{action.defender_territory_id}")
            if result.battle_result:
                br = result.battle_result
                print(f"   Rolls: {br.attacker_rolls} vs {br.defender_rolls}")
                print(f"   Winner: {br.winner}")
        
        if self.clear_screen and self.move_count % 3 == 0:
            # Clear screen every few moves for better visibility
            os.system('clear' if os.name == 'posix' else 'cls')
        
        # Always show updated board
        print()
        print(self.renderer.render_board(result.new_game_state))
        
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)
    
    def on_invalid_action(
        self,
        action: Union[AttackAction, EndTurnAction, DistributeSupplyAction],
        error_code: str,
        error_data: Optional[dict] = None
    ) -> None:
        """Called when an invalid action is attempted."""
        print(f"❌ INVALID ACTION: {action.type} -> {error_code}")
        if error_data and 'message' in error_data:
            print(f"   {error_data['message']}")
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        print("\n" + "=" * 50)
        print("🏆 GAME OVER!")
        print("=" * 50)
        
        if final_state.winner_id is not None:
            print(f"🥇 Winner: Player {final_state.winner_id}!")
        else:
            print("🤝 Game ended in a tie!")
        
        print(f"Final turn: {final_state.turn_number}")
        print(f"Total moves: {self.move_count}")
        print()
        
        # Final board state
        print(self.renderer.render_board(final_state))
        print(self.renderer.render_stats(final_state))
```

#### 1.3 CLI Script

```python
# scripts/run_cli.py
"""CLI script for running Dice Wars games."""

import argparse
import json
import sys
from pathlib import Path
from typing import List

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dicewars.api.coordinator import GameCoordinator
from dicewars.api.types import GameConfig, MapLayout, TerritoryLayout, Position, BorderSegment
from dicewars.clients.base import EndTurnOnlyClient, VerboseEndTurnClient
from dicewars.observers.cli import CLIObserver
from dicewars.observers.base import LoggingObserver


def load_map_layout(map_file: Path) -> MapLayout:
    """Load MapLayout from JSON file."""
    with open(map_file, 'r') as f:
        map_data = json.load(f)
    
    # Convert JSON to MapLayout
    territories = {}
    for tid_str, t_data in map_data["territories"].items():
        tid = int(tid_str)
        territories[tid] = TerritoryLayout(
            id=t_data["id"],
            name=t_data["name"],
            tiles=[Position(x=tile["x"], y=tile["y"]) for tile in t_data["tiles"]],
            adjacencies=t_data["adjacencies"],
            border=[BorderSegment(
                start=Position(x=seg["start"]["x"], y=seg["start"]["y"]),
                end=Position(x=seg["end"]["x"], y=seg["end"]["y"])
            ) for seg in t_data["border"]]
        )
    
    return MapLayout(
        map_name=map_data["map_name"],
        dimensions=Position(x=map_data["dimensions"]["x"], y=map_data["dimensions"]["y"]),
        territories=territories,
        grid_lookup=map_data["grid_lookup"]
    )


def create_clients(num_players: int, client_type: str) -> List:
    """Create client instances."""
    if client_type == "end_turn":
        return [EndTurnOnlyClient(i) for i in range(num_players)]
    elif client_type == "verbose":
        return [VerboseEndTurnClient(i) for i in range(num_players)]
    else:
        raise ValueError(f"Unknown client type: {client_type}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Run a Dice Wars game")
    parser.add_argument("map_file", help="Path to map JSON file")
    parser.add_argument("--players", "-p", type=int, default=2, help="Number of players")
    parser.add_argument("--client", "-c", default="end_turn", 
                       choices=["end_turn", "verbose"],
                       help="Client type to use")
    parser.add_argument("--max-turns", type=int, default=10, 
                       help="Maximum turns before game ends")
    parser.add_argument("--no-clear", action="store_true", 
                       help="Don't clear screen during game")
    parser.add_argument("--fast", action="store_true",
                       help="Run without delays")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")
    
    args = parser.parse_args()
    
    try:
        # Load map
        print(f"Loading map from {args.map_file}...")
        map_layout = load_map_layout(Path(args.map_file))
        
        # Create config
        config = GameConfig(
            map_layout=map_layout,
            num_players=args.players,
            max_turns=args.max_turns
        )
        
        # Create clients
        clients = create_clients(args.players, args.client)
        
        # Create observers
        observers = []
        
        # CLI observer for live display
        cli_observer = CLIObserver(
            clear_screen=not args.no_clear,
            delay_ms=0 if args.fast else 1500
        )
        observers.append(cli_observer)
        
        # Debug logging if requested
        if args.debug:
            observers.append(LoggingObserver(verbose=True))
        
        print(f"Starting game: {map_layout.map_name} with {args.players} players")
        print("Press Ctrl+C to exit\n")
        
        # Run game
        coordinator = GameCoordinator(config, clients, observers)
        final_state = coordinator.run()
        
        print("\nGame completed successfully!")
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Game interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

### Phase 2: Enhanced Features (After M4-M5)

Once more game mechanics are implemented, enhance the CLI:

#### 2.1 Interactive Human Player

```python
# src/dicewars/clients/human.py
"""Human CLI client."""

from typing import Union
from ..api.client import PlayerClient
from ..api.types import (
    TurnContext, GameConfig, GameState,
    AttackAction, EndTurnAction, DistributeSupplyAction
)


class HumanCLIClient(PlayerClient):
    """Human player via CLI input."""
    
    def __init__(self, player_id: int, name: str = None):
        self.player_id = player_id
        self.name = name or f"Human_{player_id}"
    
    def get_action(
        self, 
        context: TurnContext
    ) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
        """Get action from human player."""
        print(f"\n🎯 {self.name}, it's your turn!")
        
        # Show available actions
        print("Available actions:")
        for i, action in enumerate(context.valid_actions):
            if isinstance(action, AttackAction):
                print(f"  {i}: Attack T{action.attacker_territory_id} -> T{action.defender_territory_id}")
            elif isinstance(action, EndTurnAction):
                print(f"  {i}: End Turn")
            elif isinstance(action, DistributeSupplyAction):
                print(f"  {i}: Distribute Supply (not implemented)")
        
        while True:
            try:
                choice = input("Enter action number (or 'q' to quit): ").strip()
                
                if choice.lower() == 'q':
                    raise KeyboardInterrupt("Player quit")
                
                idx = int(choice)
                if 0 <= idx < len(context.valid_actions):
                    return context.valid_actions[idx]
                else:
                    print(f"Invalid choice. Enter 0-{len(context.valid_actions)-1}")
            
            except ValueError:
                print("Please enter a number")
            except KeyboardInterrupt:
                raise
```

#### 2.2 Map Preview Script

```python
# scripts/preview_map.py
"""Preview map layout without running a game."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dicewars.api.types import GameState, GamePhase
from dicewars.ui.cli.ascii_renderer import ASCIIRenderer
from scripts.run_cli import load_map_layout


def main():
    """Preview map layout."""
    parser = argparse.ArgumentParser(description="Preview a Dice Wars map")
    parser.add_argument("map_file", help="Path to map JSON file")
    
    args = parser.parse_args()
    
    try:
        # Load map
        map_layout = load_map_layout(Path(args.map_file))
        
        # Create dummy game state for preview
        num_territories = len(map_layout.territories)
        preview_state = GameState(
            owners=[-1] * num_territories,  # All neutral
            dice=[1] * num_territories,     # 1 die each
            active_player_id=0,
            phase=GamePhase.SETUP,
            turn_number=0,
            tick_id="0"
        )
        
        # Render
        renderer = ASCIIRenderer(map_layout)
        print(renderer.render_board(preview_state))
        
        # Show adjacencies
        print("\n=== Territory Adjacencies ===")
        for tid, territory in map_layout.territories.items():
            adj_names = [map_layout.territories[adj_id].name for adj_id in territory.adjacencies]
            print(f"{territory.name} (T{tid}): {', '.join(adj_names)}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

#### 2.3 Replay System

```python
# scripts/replay_game.py
"""Replay a completed game from log file."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dicewars.observers.cli import CLIObserver


def main():
    """Replay game from JSONL log."""
    parser = argparse.ArgumentParser(description="Replay a Dice Wars game")
    parser.add_argument("replay_file", help="Path to replay JSONL file")
    parser.add_argument("--fast", action="store_true", help="Fast playback")
    
    args = parser.parse_args()
    
    try:
        # Implementation after M10 (Replay system)
        print("Replay system will be implemented in M10")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

### Phase 3: Advanced CLI Features (After M6-M7)

#### 3.1 Tournament Mode

```python
# scripts/run_tournament.py
"""Run a tournament between multiple bots."""

import argparse
from itertools import combinations
from collections import defaultdict


def run_tournament(clients, maps, games_per_matchup=5):
    """Run round-robin tournament."""
    results = defaultdict(lambda: defaultdict(int))
    
    # All vs all matchups
    for client1, client2 in combinations(clients, 2):
        for _ in range(games_per_matchup):
            # Alternate who goes first
            for first_player in [client1, client2]:
                # Run game
                winner = run_single_game([first_player, client1 if first_player == client2 else client2])
                if winner is not None:
                    results[winner.name]["wins"] += 1
                else:
                    results[client1.name]["draws"] += 1
                    results[client2.name]["draws"] += 1
    
    return results
```

#### 3.2 Statistics Tracking

```python
# src/dicewars/observers/stats.py
"""Statistics tracking observer."""

class StatsObserver(GameObserver):
    """Track detailed game statistics."""
    
    def __init__(self):
        self.stats = {
            "total_turns": 0,
            "total_attacks": 0,
            "successful_attacks": 0,
            "territories_captured": 0,
            "dice_lost_in_attacks": 0,
            "average_dice_per_attack": 0.0
        }
    
    # Implementation tracks various metrics...
```

---

## Usage Examples

### Basic Usage (After M3)

```bash
# Run a simple 2-player game
python scripts/run_cli.py tests/fixtures/small_map.json --players 2

# Quick game without delays
python scripts/run_cli.py tests/fixtures/small_map.json --fast

# Verbose mode with debug logging  
python scripts/run_cli.py tests/fixtures/small_map.json --client verbose --debug

# Preview a map without playing
python scripts/preview_map.py tests/fixtures/small_map.json
```

### Advanced Usage (After M4-M7)

```bash
# Human vs bot game
python scripts/run_cli.py my_map.json --players 2 --client human_vs_bot

# 4-player tournament
python scripts/run_tournament.py --bots random,heuristic,minimax --maps map1.json,map2.json

# Replay a saved game
python scripts/replay_game.py game_20241201_143052.jsonl --fast
```

---

## Integration with Testing

### CLI Integration Tests

```python
# tests/integration/test_cli_integration.py
"""Integration tests for CLI functionality."""

import subprocess
import tempfile
from pathlib import Path


def test_cli_script_runs():
    """Test that CLI script runs without error."""
    map_file = Path("tests/fixtures/small_map.json")
    
    result = subprocess.run([
        "python", "scripts/run_cli.py", 
        str(map_file), 
        "--players", "2",
        "--max-turns", "5",
        "--fast"
    ], capture_output=True, text=True, timeout=30)
    
    assert result.returncode == 0
    assert "Game completed successfully!" in result.stdout


def test_map_preview():
    """Test map preview script."""
    map_file = Path("tests/fixtures/small_map.json")
    
    result = subprocess.run([
        "python", "scripts/preview_map.py", str(map_file)
    ], capture_output=True, text=True, timeout=10)
    
    assert result.returncode == 0
    assert "test_6_territories" in result.stdout
    assert "Territory Adjacencies" in result.stdout
```

---

## Benefits of This Approach

1. **Incremental Development**: Each phase builds on the previous, allowing CLI functionality from M3 onwards

2. **Visual Debugging**: ASCII renderer helps debug game mechanics as they're implemented

3. **User Experience**: Provides immediate visual feedback for game development and testing

4. **Educational**: Shows game state transitions clearly for understanding mechanics

5. **Extensible**: Framework supports adding new features (human players, replay, tournaments) easily

6. **Testing Integration**: CLI scripts can be used in integration tests to verify end-to-end functionality

---

## Implementation Timeline

| Milestone | CLI Features Available |
|-----------|----------------------|
| M3 | Basic ASCII rendering, EndTurn-only games, CLI observer |
| M4 | Attack visualization, battle results display |
| M5 | Supply phase display, placement visualization |
| M6 | Timeout handling, penalty display |
| M7 | Winner determination, final statistics |
| M8+ | Enhanced UI, tournaments, human players |

This progressive enhancement ensures that the CLI remains useful and demonstrates progress at every milestone while building towards a full-featured interface.