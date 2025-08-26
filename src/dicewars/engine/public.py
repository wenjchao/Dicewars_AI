"""Public engine interface implementation."""

from ..api.types import GameConfig
from ..api.engine import GameEngine
from ..core.engine import DicewarsEngine


def create_engine(config: GameConfig) -> GameEngine:
    """Create a game engine instance."""
    return DicewarsEngine(config)


__all__ = ['create_engine']