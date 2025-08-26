"""ASCII rendering for CLI display."""

from typing import List, Dict, Optional
from ...api.types import GameState, MapLayout, Position


class ASCIIRenderer:
    """Renders game state as ASCII art."""
    
    def __init__(self, map_layout: MapLayout):
        self.map_layout = map_layout
        self.width = map_layout.dimensions.x
        self.height = map_layout.dimensions.y
        
        # Color codes for different players (0-7)
        self.player_colors = {
            -1: '.',  # Neutral territory
            0: '0',   # Player 0
            1: '1',   # Player 1  
            2: '2',   # Player 2
            3: '3',   # Player 3
            4: '4',   # Player 4
            5: '5',   # Player 5
            6: '6',   # Player 6
            7: '7',   # Player 7
        }
    
    def render_board(self, game_state: GameState) -> str:
        """Render the game board with clear territory boundaries."""
        lines = []
        
        # Header
        lines.append(f"Map: {self.map_layout.map_name}")
        lines.append(f"Turn {game_state.turn_number} | Player {game_state.active_player_id} | Phase: {game_state.phase.value}")
        lines.append("")
        
        # Show territory layout with clear boundaries
        lines.append("🗺️  TERRITORY LAYOUT:")
        
        # Create territory map from tiles
        territory_map = {}
        for tid, territory in self.map_layout.territories.items():
            for tile in territory.tiles:
                territory_map[(tile.x, tile.y)] = int(tid)
        
        # Render grid with territory IDs
        lines.append("+" + "----+" * self.width)
        for y in range(self.height):
            row = "|"
            for x in range(self.width):
                if (x, y) in territory_map:
                    tid = territory_map[(x, y)]
                    row += f" T{tid:2d}|"
                else:
                    row += "    |"
            lines.append(row)
            lines.append("+" + "----+" * self.width)
        
        lines.append("")
        
        # Show adjacencies first
        lines.append("🔗 TERRITORY ADJACENCIES:")
        for tid, territory in self.map_layout.territories.items():
            adj_names = [f"T{adj}({self.map_layout.territories[adj].name})" for adj in territory.adjacencies]
            lines.append(f"  T{tid} ({territory.name}) → adjacent to: {', '.join(adj_names)}")
        lines.append("")
        
        # Current game state table
        lines.append("📊 CURRENT GAME STATE:")
        lines.append("Territory | Name      | Owner | Dice | Can Attack?")
        lines.append("-" * 50)
        
        for tid, territory in self.map_layout.territories.items():
            tid_int = int(tid)
            owner = game_state.owners[tid_int]
            dice = game_state.dice[tid_int]
            
            # Check if this territory can attack
            can_attack = "No"
            if owner == game_state.active_player_id:
                # Check if any adjacent territory belongs to enemy
                for adj_tid in territory.adjacencies:
                    if game_state.owners[adj_tid] != owner:
                        can_attack = "YES!"
                        break
            
            owner_marker = "👤 YOU" if owner == game_state.active_player_id else f"P{owner}"
            
            lines.append(f"T{str(tid):8s} | {territory.name:9s} | {owner_marker:7s} | {dice:4d} | {can_attack}")
        
        return "\n".join(lines)
    
    def render_player_stats(self, game_state: GameState) -> str:
        """Render player statistics."""
        lines = []
        lines.append("Player Statistics:")
        lines.append("-" * 50)
        
        # Count territories and dice for each player
        player_stats = {}
        for player_id in range(8):  # Support up to 8 players
            player_stats[player_id] = {"territories": 0, "dice": 0}
        
        for i, owner in enumerate(game_state.owners):
            if owner >= 0:
                player_stats[owner]["territories"] += 1
                player_stats[owner]["dice"] += game_state.dice[i]
        
        # Display stats for active players
        for player_id in range(8):
            stats = player_stats[player_id]
            if stats["territories"] > 0:
                status = ""
                if player_id in game_state.eliminated_players:
                    status = " (ELIMINATED)"
                elif player_id == game_state.active_player_id:
                    status = " (ACTIVE)"
                
                lines.append(f"Player {player_id}: {stats['territories']} territories, {stats['dice']} dice{status}")
        
        return "\n".join(lines)
    
    def render_game_status(self, game_state: GameState) -> str:
        """Render overall game status."""
        lines = []
        
        if game_state.phase.value == "game_over":
            lines.append("*** GAME OVER! ***")
            if game_state.winner_id is not None:
                lines.append(f"Winner: Player {game_state.winner_id}")
            else:
                lines.append("No winner determined")
        else:
            lines.append(f"Game in progress - {game_state.phase.value.upper()} phase")
        
        lines.append(f"Turn: {game_state.turn_number}")
        lines.append(f"Tick: {game_state.tick_id}")
        
        return "\n".join(lines)
    
    def render_map_info(self) -> str:
        """Render map information."""
        lines = []
        lines.append(f"Map: {self.map_layout.map_name}")
        lines.append(f"Size: {self.width}x{self.height}")
        lines.append(f"Territories: {len(self.map_layout.territories)}")
        
        return "\n".join(lines)
    
    def render_full_state(self, game_state: GameState) -> str:
        """Render complete game state display."""
        sections = [
            self.render_map_info(),
            "",
            self.render_board(game_state),
            "",
            self.render_player_stats(game_state),
            "",
            self.render_game_status(game_state)
        ]
        
        return "\n".join(sections)


def render_territory_legend(map_layout: MapLayout) -> str:
    """Render legend showing territory IDs and names."""
    lines = []
    lines.append("Territory Legend:")
    lines.append("-" * 30)
    
    for territory_id, territory in map_layout.territories.items():
        lines.append(f"T{territory_id:2d}: {territory.name}")
    
    return "\n".join(lines)


def render_adjacency_info(map_layout: MapLayout, territory_id: int) -> str:
    """Render adjacency information for a specific territory."""
    if territory_id not in map_layout.territories:
        return f"Territory {territory_id} not found."
    
    territory = map_layout.territories[territory_id]
    lines = []
    lines.append(f"Territory {territory_id} ({territory.name}):")
    lines.append(f"Adjacent to: {', '.join(map(str, territory.adjacencies))}")
    lines.append(f"Grid positions: {', '.join(f'({pos.x},{pos.y})' for pos in territory.tiles)}")
    
    return "\n".join(lines)