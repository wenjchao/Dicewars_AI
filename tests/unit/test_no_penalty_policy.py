"""Test NO_PENALTY timeout policy."""

import pytest
from dicewars.api.types import GameConfig, TimeoutPolicy
from dicewars.core.engine import DicewarsEngine
from tests.unit.test_m7_winner_system import create_test_config


class TestNoPenaltyPolicy:
    """Test NO_PENALTY timeout policy."""
    
    def test_no_penalty_policy_creation(self):
        """Test config with NO_PENALTY policy."""
        config = create_test_config()
        import dataclasses
        config = dataclasses.replace(config, timeout_policy=TimeoutPolicy.NO_PENALTY)
        
        assert config.timeout_policy == TimeoutPolicy.NO_PENALTY
    
    def test_no_penalty_on_timeout(self):
        """Test that NO_PENALTY policy doesn't change state."""
        import dataclasses
        config = create_test_config()
        config = dataclasses.replace(config, timeout_policy=TimeoutPolicy.NO_PENALTY)
        engine = DicewarsEngine(config)
        
        # Get initial state
        initial_state = engine.get_turn_context().game_state
        initial_player = initial_state.active_player_id
        initial_tick = initial_state.tick_id
        
        # Apply timeout penalty with NO_PENALTY policy
        result = engine.apply_penalty("timeout")
        
        # Verify state didn't change
        assert result.success
        assert result.penalty_action is None  # No penalty action taken
        assert result.error_data["action"] == "no_penalty"
        
        new_state = result.new_game_state
        assert new_state.active_player_id == initial_player  # Same player
        assert new_state.tick_id == initial_tick  # Tick didn't advance
    
    def test_no_penalty_on_client_error(self):
        """Test that NO_PENALTY policy applies to client errors too."""
        import dataclasses
        config = create_test_config()
        config = dataclasses.replace(config, timeout_policy=TimeoutPolicy.NO_PENALTY)
        engine = DicewarsEngine(config)
        
        # Get initial state
        initial_state = engine.get_turn_context().game_state
        initial_player = initial_state.active_player_id
        
        # Apply client_error penalty with NO_PENALTY policy
        result = engine.apply_penalty("client_error")
        
        # Verify no penalty was applied
        assert result.success
        assert result.penalty_action is None
        assert result.new_game_state.active_player_id == initial_player
    
    def test_invalid_action_no_penalty(self):
        """Test that invalid_action also gets NO_PENALTY when policy is set."""
        import dataclasses
        config = create_test_config()
        config = dataclasses.replace(config, timeout_policy=TimeoutPolicy.NO_PENALTY)
        engine = DicewarsEngine(config)
        
        # Get initial state
        initial_state = engine.get_turn_context().game_state
        initial_player = initial_state.active_player_id
        initial_tick = initial_state.tick_id
        initial_phase = initial_state.phase
        
        # Apply invalid_action penalty with NO_PENALTY policy
        result = engine.apply_penalty("invalid_action")
        
        # Verify NO penalty was applied
        assert result.success
        assert result.penalty_action is None  # No penalty action taken
        assert result.error_data["action"] == "no_penalty"
        
        new_state = result.new_game_state
        # Nothing should have changed
        assert new_state.active_player_id == initial_player
        assert new_state.tick_id == initial_tick
        assert new_state.phase == initial_phase
    
    def test_policy_precedence(self):
        """Test that explicit penalty_type overrides policy."""
        import dataclasses
        config = create_test_config()
        config = dataclasses.replace(config, timeout_policy=TimeoutPolicy.NO_PENALTY)
        engine = DicewarsEngine(config)
        
        # Get initial state
        initial_player = engine.get_turn_context().game_state.active_player_id
        
        # Apply timeout with explicit penalty_type (overrides NO_PENALTY)
        result = engine.apply_penalty("timeout", "skip_next_turn")
        
        # Verify explicit penalty was applied
        assert result.success
        assert result.penalty_action is not None
        assert result.penalty_action.penalty_type == "skip_next_turn"
        
        # Skip penalty should be recorded
        assert initial_player in engine.state.pending_skips


if __name__ == "__main__":
    pytest.main([__file__, "-v"])