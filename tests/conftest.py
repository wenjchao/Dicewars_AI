"""Pytest configuration and shared fixtures."""

from typing import Any

import pytest


def deep_state_key(game_state: Any) -> tuple[Any, ...]:
    """
    Create a canonical tuple for GameState equality in hashless mode.
    Used by tests when hash fields return "0".
    """
    if not hasattr(game_state, "territories"):
        return ()

    # Territory state: (id, owner, dice) sorted by id
    terr = tuple(
        sorted(
            (tid, getattr(ts, "owner_id", 0), getattr(ts, "dice_count", 0))
            for tid, ts in game_state.territories.items()
        )
    )

    # Player state: (id, territories, dice, alive, connected)
    players = tuple(
        (
            p.id,
            tuple(sorted(p.owned_territory_ids)),
            p.total_dice,
            p.is_alive,
            p.largest_connected_region,
        )
        for p in game_state.players
    )

    return (
        game_state.active_player_id,
        game_state.turn_number,
        game_state.phase.value if hasattr(game_state.phase, "value") else game_state.phase,
        game_state.winner_id,
        terr,
        players,
    )


@pytest.fixture
def hashless_mode() -> bool:
    """Fixture to enable hashless testing mode."""
    import os

    return os.environ.get("HASHLESS", "0") == "1"


@pytest.fixture
def sample_capabilities() -> dict[str, Any]:
    """Minimal capabilities response for testing."""
    return {
        "rules_version": "v1",
        "schema_version": "v5",
        "layout_hash": "0",
        "action_index_hash": "0",
        "num_territories": 6,
        "num_attack_pairs": 12,
        "battle_system": "auto_all_but_one",
        "supply_policy": "must_place_all",
        "max_dice_per_territory": 8,
        "winner_policy": "most_territories",
        "winner_tiebreak_chain": ["most_territories", "lowest_player_id"],
        "max_turns": None,
        "supports_delta": False,
        "uint64_encoding": "decimal_string",
        "rng_streams": ["setup", "turn", "battle"],
        "wire_schemas": {},
    }
