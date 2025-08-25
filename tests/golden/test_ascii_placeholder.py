"""Golden test placeholder for ASCII rendering determinism."""

import pytest


@pytest.mark.skip("Implemented in M8")
def test_ascii_board_renders_deterministically():
    """
    Golden test that 6-territory map renders to stable ASCII.
    Will use fixed terminal width to avoid CI differences.
    """
    pass


@pytest.mark.skip("Implemented in M8")
def test_viewmodel_snapshot_stability():
    """
    Test that to_render_state produces stable JSON across platforms.
    Will verify floating point determinism.
    """
    pass
