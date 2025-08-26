"""Winner determination system (M7)."""

from typing import Optional, List, Set, Union
from ..api.types import WinnerPolicy, TiebreakToken, GameState, GameConfig
from .territory_utils import get_connected_regions


class WinnerDeterminer:
    """Handles winner determination with configurable policies."""
    
    def __init__(self, state: 'CoreState', config: GameConfig):
        self.state = state
        self.config = config
    
    def determine_winner(self) -> Optional[int]:
        """Apply winner policy chain to determine winner."""
        active_players = self._get_active_players()
        
        # Single player = automatic winner (elimination)
        if len(active_players) == 1:
            return active_players[0]
        elif len(active_players) == 0:
            return None  # No players left
        
        # First apply main winner policy
        winner = self._apply_policy(self.config.winner_policy, active_players)
        if winner is not None:
            return winner
        
        # If main policy results in tie, apply tiebreak chain
        for tiebreak_token in self.config.winner_tiebreak_chain:
            winner = self._apply_tiebreak_token(tiebreak_token, active_players)
            if winner is not None:
                return winner
        
        # Final fallback: lexicographic (lowest ID)
        return min(active_players) if active_players else None
    
    def _get_active_players(self) -> List[int]:
        """Get players who still own territories."""
        active = set()
        for owner in self.state.owners:
            if owner >= 0:  # Valid player ID (not -1 for neutral)
                active.add(owner)
        return list(active)
    
    def _apply_policy(self, policy: WinnerPolicy, candidates: List[int]) -> Optional[int]:
        """Apply single winner policy to candidate players."""
        if policy == WinnerPolicy.NONE:
            return None  # v5: explicit draw support
        
        elif policy == WinnerPolicy.MOST_TERRITORIES:
            return self._winner_by_territories(candidates)
        
        elif policy == WinnerPolicy.MOST_TOTAL_DICE:
            return self._winner_by_total_dice(candidates)
        
        elif policy == WinnerPolicy.LARGEST_CONNECTED:
            return self._winner_by_connected_regions(candidates)
        
        elif policy == WinnerPolicy.LEXICOGRAPHIC:
            return min(candidates) if candidates else None
        
        return None
    
    def _apply_tiebreak_token(self, token: TiebreakToken, candidates: List[int]) -> Optional[int]:
        """Apply tiebreak token to candidate players."""
        if token == TiebreakToken.TERRITORIES:
            return self._winner_by_territories(candidates)
        elif token == TiebreakToken.TOTAL_DICE:
            return self._winner_by_total_dice(candidates)
        elif token == TiebreakToken.LARGEST_CONNECTED:
            return self._winner_by_connected_regions(candidates)
        elif token == TiebreakToken.PLAYER_ID:
            return min(candidates) if candidates else None
        return None
    
    def _winner_by_territories(self, candidates: List[int]) -> Optional[int]:
        """Winner by most territories owned."""
        territory_counts = {}
        for player_id in candidates:
            territory_counts[player_id] = sum(
                1 for owner in self.state.owners if owner == player_id
            )
        
        if not territory_counts:
            return None
        
        max_count = max(territory_counts.values())
        winners = [p for p, count in territory_counts.items() if count == max_count]
        
        return winners[0] if len(winners) == 1 else None  # Tie = no winner
    
    def _winner_by_total_dice(self, candidates: List[int]) -> Optional[int]:
        """Winner by most total dice owned."""
        dice_totals = {}
        for player_id in candidates:
            dice_totals[player_id] = sum(
                dice for i, dice in enumerate(self.state.dice)
                if self.state.owners[i] == player_id
            )
        
        if not dice_totals:
            return None
        
        max_total = max(dice_totals.values())
        winners = [p for p, total in dice_totals.items() if total == max_total]
        
        return winners[0] if len(winners) == 1 else None
    
    def _winner_by_connected_regions(self, candidates: List[int]) -> Optional[int]:
        """Winner by largest connected territory region."""
        region_sizes = {}
        for player_id in candidates:
            regions = get_connected_regions(
                self.state.owners, player_id, self.config.map_layout
            )
            region_sizes[player_id] = max(len(region) for region in regions) if regions else 0
        
        if not region_sizes:
            return None
        
        max_size = max(region_sizes.values())
        winners = [p for p, size in region_sizes.items() if size == max_size]
        
        return winners[0] if len(winners) == 1 else None