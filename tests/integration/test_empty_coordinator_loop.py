"""Integration test placeholder for coordinator loop."""

import pytest


@pytest.mark.skip("Implemented in M3")
def test_coordinator_registration_and_basic_loop():
    """
    Integration test for basic coordinator functionality.
    Will test player registration and turn cycling.
    """
    pass


@pytest.mark.skip("Implemented in M3")
def test_observer_wiring():
    """
    Test that observers receive events in correct order.
    Will verify on_game_start -> on_turn_start -> on_action_executed -> on_game_end flow.
    """
    pass
