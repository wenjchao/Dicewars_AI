"""Penalty system with decision window management."""

import time
from dataclasses import dataclass
from typing import Optional, Set
from ..api.types import TimeoutPolicy


@dataclass
class DecisionWindow:
    """Decision window for timeout tracking."""
    start_time: float
    timeout_ms: int
    is_active: bool = False


class PenaltyManager:
    """Manages decision windows and penalty application."""
    
    def __init__(self, timeout_ms: int, timeout_policy: TimeoutPolicy):
        self.timeout_ms = timeout_ms
        self.timeout_policy = timeout_policy
        self.current_window: Optional[DecisionWindow] = None
        self.pending_skips: Set[int] = set()
    
    def start_decision_window(self) -> None:
        """Start decision window before get_action()."""
        self.current_window = DecisionWindow(
            start_time=time.time(),
            timeout_ms=self.timeout_ms,
            is_active=True
        )
    
    def check_timeout(self) -> bool:
        """Check if current window has timed out."""
        if not self.current_window or not self.current_window.is_active:
            return False
        
        elapsed_ms = (time.time() - self.current_window.start_time) * 1000
        return elapsed_ms >= self.current_window.timeout_ms
    
    def reset_window(self) -> None:
        """Reset window on action accept or penalty."""
        if self.current_window:
            self.current_window.is_active = False
        self.current_window = None
    
    def add_pending_skip(self, player_id: int) -> None:
        """Add player to pending skip list."""
        self.pending_skips.add(player_id)
    
    def remove_pending_skip(self, player_id: int) -> bool:
        """Remove player from pending skip list. Returns True if player was skipped."""
        if player_id in self.pending_skips:
            self.pending_skips.remove(player_id)
            return True
        return False
    
    def has_pending_skip(self, player_id: int) -> bool:
        """Check if player has pending skip."""
        return player_id in self.pending_skips
    
    def clear_pending_skips(self) -> None:
        """Clear all pending skips (used for max-turns precedence)."""
        self.pending_skips.clear()