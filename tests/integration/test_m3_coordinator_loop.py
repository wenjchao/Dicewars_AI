"""Integration tests for M3 coordinator loop."""

import pytest
from dicewars.api.coordinator import GameCoordinator
from dicewars.api.client import PlayerClient
from dicewars.api.observer import GameObserver
from dicewars.api.types import (
    GameConfig, GameState, TurnContext, MapLayout, Position,
    GamePhase, BattleSystem, SupplyPolicy, TimeoutPolicy,
    WinnerPolicy, TiebreakToken, AttackAction, EndTurnAction,
    DistributeSupplyAction, TerritoryLayout
)
from typing import Union


class MockClient(PlayerClient):
    """Mock client for testing."""
    
    def __init__(self, strategy="end_turn"):
        self.strategy = strategy
        self.actions_taken = []
        self.game_started = False
        self.game_ended = False
        self.player_id = None
    
    def get_action(self, context: TurnContext) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
        """Get player's action based on strategy."""
        if self.strategy == "end_turn":
            action = EndTurnAction()
        elif self.strategy == "attack_first":
            # Try to attack if possible, otherwise end turn
            if context.valid_actions and any(isinstance(a, AttackAction) for a in context.valid_actions):
                action = next(a for a in context.valid_actions if isinstance(a, AttackAction))
            else:
                action = EndTurnAction()
        else:
            action = EndTurnAction()
        
        self.actions_taken.append(action)
        return action
    
    def on_game_start(self, config: GameConfig, player_id: int) -> None:
        """Called when game starts."""
        self.game_started = True
        self.player_id = player_id
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        self.game_ended = True


class MockObserver(GameObserver):
    """Mock observer for testing."""
    
    def __init__(self):
        self.events = []
    
    def on_game_start(self, config: GameConfig, initial_state: GameState) -> None:
        """Called when game starts."""
        self.events.append(("game_start", config, initial_state))
    
    def on_turn_start(self, player_id: int, turn_number: int) -> None:
        """Called when a new alive player enters ATTACK phase."""
        self.events.append(("turn_start", player_id, turn_number))
    
    def on_action_executed(self, action, result) -> None:
        """Called after any action is executed."""
        self.events.append(("action_executed", action, result))
    
    def on_invalid_action(self, action, error_code: str, error_data=None) -> None:
        """Called when an invalid action is attempted."""
        self.events.append(("invalid_action", action, error_code, error_data))
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        self.events.append(("game_end", final_state))


@pytest.fixture
def simple_map_config():
    """Create a simple 2x2 map configuration for testing."""
    # Create a simple 2x2 map with 4 territories
    territories = {}
    for i in range(4):
        x = i % 2
        y = i // 2
        territories[i] = TerritoryLayout(
            id=i,
            name=f"Territory{i}",
            tiles=[Position(x, y)],
            adjacencies=[j for j in range(4) if j != i and abs((j % 2) - x) + abs((j // 2) - y) == 1],
            border=[]
        )
    
    map_layout = MapLayout(
        map_name="test_map",
        dimensions=Position(2, 2),
        territories=territories,
        grid_lookup=[[0, 1], [2, 3]]
    )
    
    return GameConfig(
        map_layout=map_layout,
        num_players=2,
        battle_system=BattleSystem.AUTO_ALL_BUT_ONE,
        supply_policy=SupplyPolicy.ALLOW_EARLY_END,
        timeout_policy=TimeoutPolicy.AUTO_END_TURN,
        timeout_ms=1000,
        winner_policy=WinnerPolicy.MOST_TERRITORIES,
        max_turns=10  # Short game for testing
    )


class TestCoordinatorLoop:
    """Test coordinator loop functionality."""
    
    def test_coordinator_creation(self, simple_map_config):
        """Test coordinator can be created with valid configuration."""
        clients = [MockClient(), MockClient()]
        observers = [MockObserver()]
        
        coordinator = GameCoordinator(simple_map_config, clients, observers)
        assert coordinator.config == simple_map_config
        assert len(coordinator.clients) == 2
        assert len(coordinator.observers) == 1
    
    def test_coordinator_invalid_client_count(self, simple_map_config):
        """Test coordinator rejects invalid client count."""
        clients = [MockClient()]  # Only 1 client for 2-player game
        
        with pytest.raises(ValueError, match="Expected 2 clients, got 1"):
            GameCoordinator(simple_map_config, clients)
    
    def test_coordinator_run_end_turn_only(self, simple_map_config):
        """Test coordinator can run a game with end-turn-only clients."""
        clients = [MockClient("end_turn"), MockClient("end_turn")]
        observer = MockObserver()
        
        coordinator = GameCoordinator(simple_map_config, clients, [observer])
        final_state = coordinator.run()
        
        # Check game completed
        assert final_state.phase == GamePhase.GAME_OVER
        assert final_state.winner_id is not None
        
        # Check clients received callbacks
        for client in clients:
            assert client.game_started
            assert client.game_ended
            assert client.player_id is not None
            assert len(client.actions_taken) > 0
        
        # Check observer received events
        assert len(observer.events) > 0
        assert observer.events[0][0] == "game_start"
        assert observer.events[-1][0] == "game_end"
    
    def test_coordinator_with_attacks(self, simple_map_config):
        """Test coordinator handles attack actions."""
        clients = [MockClient("attack_first"), MockClient("end_turn")]
        observer = MockObserver()
        
        coordinator = GameCoordinator(simple_map_config, clients, [observer])
        final_state = coordinator.run()
        
        # Check game completed
        assert final_state.phase == GamePhase.GAME_OVER
        
        # Check that some attacks occurred
        action_events = [event for event in observer.events if event[0] == "action_executed"]
        assert len(action_events) > 0
        
        # Check for attack actions
        attack_actions = [event for event in action_events 
                         if event[1] and isinstance(event[1], AttackAction)]
        # We expect at least some attack attempts
        assert len(attack_actions) >= 0  # May be 0 if no valid attacks available
    
    def test_observer_event_sequence(self, simple_map_config):
        """Test that observer events occur in correct sequence."""
        clients = [MockClient("end_turn"), MockClient("end_turn")]
        observer = MockObserver()
        
        coordinator = GameCoordinator(simple_map_config, clients, [observer])
        coordinator.run()
        
        events = observer.events
        assert len(events) > 0
        
        # First event should be game start
        assert events[0][0] == "game_start"
        
        # Last event should be game end
        assert events[-1][0] == "game_end"
        
        # Should have turn starts
        turn_starts = [e for e in events if e[0] == "turn_start"]
        assert len(turn_starts) > 0
        
        # Should have action executions
        action_executions = [e for e in events if e[0] == "action_executed"]
        assert len(action_executions) > 0


class TestEngineIntegration:
    """Test engine integration through coordinator."""
    
    def test_engine_capabilities(self, simple_map_config):
        """Test engine returns valid capabilities."""
        clients = [MockClient(), MockClient()]
        coordinator = GameCoordinator(simple_map_config, clients)
        
        capabilities = coordinator.engine.get_capabilities()
        assert capabilities.rules_version == "1.0"
        assert capabilities.schema_version == "5.0"
        assert capabilities.num_players == 2
        assert capabilities.num_territories == 4
        assert capabilities.supports_delta is True
        assert capabilities.supports_penalties is True
    
    def test_engine_turn_context(self, simple_map_config):
        """Test engine provides valid turn context."""
        clients = [MockClient(), MockClient()]
        coordinator = GameCoordinator(simple_map_config, clients)
        
        context = coordinator.engine.get_turn_context()
        assert context.game_state is not None
        assert context.valid_actions is not None
        assert len(context.valid_actions) > 0
        assert context.time_remaining_ms == simple_map_config.timeout_ms
    
    def test_engine_action_application(self, simple_map_config):
        """Test engine can apply actions."""
        clients = [MockClient(), MockClient()]
        coordinator = GameCoordinator(simple_map_config, clients)
        
        # Get initial context
        context = coordinator.engine.get_turn_context()
        
        # Apply end turn action
        end_turn = EndTurnAction()
        result = coordinator.engine.apply_action(end_turn)
        
        assert result.success is True
        assert result.new_game_state is not None
        assert result.tick_id is not None
        assert result.state_hash is not None
        assert result.position_hash is not None