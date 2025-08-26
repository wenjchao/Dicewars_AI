"""Test M6 penalty system."""

import pytest
from dicewars.api.types import (
    GameConfig, WinnerPolicy, TiebreakToken, MapLayout, TerritoryLayout, Position,
    BattleSystem, SupplyCalculation, SupplyDistribution, SupplyPolicy, 
    TimeoutPolicy, PenaltyAction
)
from dicewars.core.engine import DicewarsEngine
from dicewars.core.penalties import PenaltyManager, DecisionWindow
import json


def create_test_config():
    """Create test game configuration."""
    # Load test map
    with open('tests/fixtures/small_map.json', 'r') as f:
        map_data = json.load(f)

    territories = {}
    for tid, tdata in map_data['territories'].items():
        territories[int(tid)] = TerritoryLayout(
            id=tdata['id'],
            name=tdata['name'],
            adjacencies=tdata['adjacencies'],
            tiles=[Position(x=pos['x'], y=pos['y']) for pos in tdata['tiles']],
            border=[]
        )

    map_layout = MapLayout(
        map_name=map_data['map_name'],
        dimensions=Position(x=map_data['dimensions']['x'], y=map_data['dimensions']['y']),
        territories=territories,
        grid_lookup=map_data['grid_lookup']
    )

    return GameConfig(
        map_layout=map_layout,
        num_players=2,
        max_turns=10,
        max_dice_per_territory=8,
        winner_policy=WinnerPolicy.MOST_TERRITORIES,
        winner_tiebreak_chain=[TiebreakToken.TERRITORIES, TiebreakToken.TOTAL_DICE],
        battle_system=BattleSystem.INDIVIDUAL_DICE_COMPARISON,
        supply_calculation=SupplyCalculation.TOTAL_TERRITORIES,
        supply_distribution=SupplyDistribution.RANDOM,
        fixed_supply_amount=5,
        supply_policy=SupplyPolicy.ALLOW_EARLY_END,
        timeout_policy=TimeoutPolicy.AUTO_END_TURN,
        timeout_ms=1000,
        seed=42
    )


class TestPenaltyAction:
    """Test PenaltyAction creation and validation."""
    
    def test_penalty_action_creation(self):
        """Test PenaltyAction can be created with correct fields."""
        action = PenaltyAction(
            penalty_type="auto_end_turn",
            reason="timeout",
            target_player_id=0
        )
        
        assert action.type == "penalty"
        assert action.penalty_type == "auto_end_turn"
        assert action.reason == "timeout"
        assert action.target_player_id == 0
    
    def test_penalty_action_immutable(self):
        """Test PenaltyAction is immutable."""
        action = PenaltyAction(
            penalty_type="skip_next_turn",
            reason="invalid_action",
            target_player_id=1
        )
        
        with pytest.raises(AttributeError):
            action.penalty_type = "auto_end_turn"  # type: ignore
    
    def test_penalty_action_type_validation(self):
        """Test PenaltyAction validates type field."""
        with pytest.raises(ValueError):
            PenaltyAction(
                type="attack",  # Invalid type
                penalty_type="auto_end_turn",
                reason="timeout", 
                target_player_id=0
            )


class TestPenaltyManager:
    """Test penalty manager decision window functionality."""
    
    def test_penalty_manager_creation(self):
        """Test PenaltyManager can be created."""
        manager = PenaltyManager(5000, TimeoutPolicy.AUTO_END_TURN)
        
        assert manager.timeout_ms == 5000
        assert manager.timeout_policy == TimeoutPolicy.AUTO_END_TURN
        assert manager.current_window is None
        assert len(manager.pending_skips) == 0
    
    def test_decision_window_lifecycle(self):
        """Test decision window start/reset lifecycle."""
        manager = PenaltyManager(1000, TimeoutPolicy.AUTO_END_TURN)
        
        # No window initially
        assert manager.current_window is None
        assert not manager.check_timeout()
        
        # Start window
        manager.start_decision_window()
        assert manager.current_window is not None
        assert manager.current_window.is_active
        
        # Reset window
        manager.reset_window()
        assert manager.current_window is None or not manager.current_window.is_active
    
    def test_pending_skip_management(self):
        """Test pending skip management."""
        manager = PenaltyManager(1000, TimeoutPolicy.SKIP_NEXT_TURN)
        
        # No pending skips initially
        assert not manager.has_pending_skip(0)
        assert not manager.has_pending_skip(1)
        
        # Add pending skip
        manager.add_pending_skip(0)
        assert manager.has_pending_skip(0)
        assert not manager.has_pending_skip(1)
        
        # Remove pending skip
        assert manager.remove_pending_skip(0)  # Returns True if was skipped
        assert not manager.has_pending_skip(0)
        assert not manager.remove_pending_skip(0)  # Returns False if not pending
        
        # Clear all pending skips
        manager.add_pending_skip(0)
        manager.add_pending_skip(1)
        manager.clear_pending_skips()
        assert not manager.has_pending_skip(0)
        assert not manager.has_pending_skip(1)


class TestEnginePenaltyIntegration:
    """Test engine penalty integration."""
    
    def test_apply_penalty_auto_end_turn(self):
        """Test apply_penalty with auto_end_turn."""
        config = create_test_config()
        engine = DicewarsEngine(config)
        
        # Get initial state
        initial_context = engine.get_turn_context()
        initial_player = initial_context.game_state.active_player_id
        
        # Apply penalty
        result = engine.apply_penalty("timeout", "auto_end_turn")
        
        # Verify penalty action in result
        assert result.success
        assert result.penalty_action is not None
        assert result.penalty_action.type == "penalty"
        assert result.penalty_action.penalty_type == "auto_end_turn"
        assert result.penalty_action.reason == "timeout"
        assert result.penalty_action.target_player_id == initial_player
        
        # Verify game state advanced
        new_context = engine.get_turn_context()
        assert new_context.game_state.tick_id != initial_context.game_state.tick_id
    
    def test_apply_penalty_skip_next_turn(self):
        """Test apply_penalty with skip_next_turn."""
        config = create_test_config()
        engine = DicewarsEngine(config)
        
        # Get initial state
        initial_context = engine.get_turn_context()
        initial_player = initial_context.game_state.active_player_id
        
        # Apply penalty
        result = engine.apply_penalty("invalid_action", "skip_next_turn")
        
        # Verify penalty action
        assert result.success
        assert result.penalty_action is not None
        assert result.penalty_action.penalty_type == "skip_next_turn"
        assert result.penalty_action.reason == "invalid_action"
        assert result.penalty_action.target_player_id == initial_player
        
        # Verify turn advanced to next player
        new_context = engine.get_turn_context()
        assert new_context.game_state.active_player_id != initial_player
    
    def test_penalty_no_rng_consumption(self):
        """Test that penalties don't consume RNG."""
        config = create_test_config()
        engine = DicewarsEngine(config)
        
        # Get initial RNG state
        initial_rng = engine.state.rng_stream
        initial_setup = initial_rng.setup_counter
        initial_turn = initial_rng.turn_counter
        initial_battle = initial_rng.battle_counter
        
        # Apply penalty
        result = engine.apply_penalty("system", "auto_end_turn")
        assert result.success
        
        # Verify RNG counters unchanged
        final_rng = engine.state.rng_stream
        assert final_rng.setup_counter == initial_setup
        assert final_rng.turn_counter == initial_turn
        assert final_rng.battle_counter == initial_battle
    
    def test_penalty_tick_increment(self):
        """Test that penalties increment tick by exactly 1."""
        config = create_test_config()
        engine = DicewarsEngine(config)
        
        # Get initial tick
        initial_context = engine.get_turn_context()
        initial_tick = int(initial_context.game_state.tick_id)
        
        # Apply penalty
        result = engine.apply_penalty("timeout", "auto_end_turn")
        
        # Verify tick incremented by exactly 1
        final_tick = int(result.tick_id)
        assert final_tick == initial_tick + 1


if __name__ == "__main__":
    pytest.main([__file__])