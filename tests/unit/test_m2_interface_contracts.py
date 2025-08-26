"""Test M2 interface contracts and abstract base classes."""

import pytest
from abc import ABC
from typing import Union, List, Optional

from dicewars.api.engine import GameEngine
from dicewars.api.client import PlayerClient
from dicewars.api.observer import GameObserver
from dicewars.api.coordinator import GameCoordinator
from dicewars.api.types import (
    GameConfig, Capabilities, TurnContext, ActionResult,
    AttackAction, EndTurnAction, DistributeSupplyAction,
    GameState, Position, MapLayout, GamePhase, StateDelta
)


class TestGameEngineContract:
    """Test GameEngine abstract interface."""
    
    def test_game_engine_is_abstract(self):
        """Test GameEngine cannot be instantiated directly."""
        with pytest.raises(TypeError):
            GameEngine()  # type: ignore
    
    def test_game_engine_abstract_methods(self):
        """Test GameEngine has required abstract methods."""
        abstract_methods = GameEngine.__abstractmethods__
        expected_methods = {
            '__init__',
            'get_capabilities',
            'get_turn_context', 
            'apply_action',
            'apply_penalty'
        }
        assert abstract_methods == expected_methods
    
    def test_concrete_game_engine_implementation(self):
        """Test concrete GameEngine implementation works."""
        
        class ConcreteGameEngine(GameEngine):
            def __init__(self, config: GameConfig) -> None:
                self.config = config
            
            def get_capabilities(self) -> Capabilities:
                return Capabilities(
                    rules_version="1.0",
                    schema_version="5.0",
                    map_name="test_map",
                    num_players=2,
                    num_territories=0,
                    layout_hash="12345",
                    action_index_hash="67890",
                    winner_policy="most_territories",
                    winner_tiebreak_chain=["territories", "total_dice", "player_id"],
                    max_turns=1000,
                    max_dice_per_territory=8
                )
            
            def get_turn_context(self) -> TurnContext:
                # Return minimal valid context
                from dicewars.api.types import GamePhase, GameState
                state = GameState(
                    owners=[],
                    dice=[],
                    active_player_id=1,
                    phase=GamePhase.ATTACK,
                    turn_number=1,
                    tick_id="123"
                )
                return TurnContext(
                    game_state=state,
                    valid_actions=[]
                )
            
            def apply_action(self, action: Union[AttackAction, EndTurnAction, DistributeSupplyAction]) -> ActionResult:
                # Return minimal valid result
                from dicewars.api.types import GamePhase, GameState, StateDelta
                state = GameState(
                    owners=[],
                    dice=[],
                    active_player_id=1,
                    phase=GamePhase.ATTACK,
                    turn_number=1,
                    tick_id="123"
                )
                delta = StateDelta(
                    changed_territories=[],
                    new_owners=[],
                    new_dice=[]
                )
                return ActionResult(
                    success=True,
                    tick_id="124",
                    state_hash="22222",
                    position_hash="77777",
                    new_game_state=state,
                    battle_result=None,
                    error_code=None,
                    error_data=None,
                    delta=delta
                )
            
            def apply_penalty(self, reason: str, penalty_type: str) -> ActionResult:
                # Return minimal valid result
                from dicewars.api.types import GamePhase, GameState, StateDelta
                state = GameState(
                    owners=[],
                    dice=[],
                    active_player_id=1,
                    phase=GamePhase.ATTACK,
                    turn_number=1,
                    tick_id="123"
                )
                delta = StateDelta(
                    territories_changed=[],
                    players_eliminated=[],
                    supply_distributed=False,
                    turn_advanced=True
                )
                return ActionResult(
                    success=True,
                    tick_id="125",
                    state_hash="33333",
                    position_hash="88888",
                    new_game_state=state,
                    battle_result=None,
                    state_delta=delta,
                    error_code=None,
                    error_data=None
                )
        
        # Should be able to create instance
        from dicewars.api.types import GamePhase, BattleSystem, SupplyPolicy, TimeoutPolicy, WinnerPolicy, TiebreakToken, MapLayout, Position
        layout = MapLayout(
            map_name="test_map",
            dimensions=Position(10, 10),
            territories={},
            grid_lookup=[[(-1) for _ in range(10)] for _ in range(10)]
        )
        config = GameConfig(
            map_layout=layout,
            num_players=2
        )
        
        engine = ConcreteGameEngine(config)
        assert isinstance(engine, GameEngine)


class TestPlayerClientContract:
    """Test PlayerClient abstract interface."""
    
    def test_player_client_is_abstract(self):
        """Test PlayerClient cannot be instantiated directly."""
        with pytest.raises(TypeError):
            PlayerClient()  # type: ignore
    
    def test_player_client_abstract_methods(self):
        """Test PlayerClient has required abstract methods."""
        abstract_methods = PlayerClient.__abstractmethods__
        expected_methods = {'get_action'}
        assert abstract_methods == expected_methods
    
    def test_concrete_player_client_implementation(self):
        """Test concrete PlayerClient implementation works."""
        
        class ConcretePlayerClient(PlayerClient):
            def get_action(self, context: TurnContext) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
                return EndTurnAction()
        
        client = ConcretePlayerClient()
        assert isinstance(client, PlayerClient)
        
        # Test optional methods exist and are callable
        assert hasattr(client, 'on_game_start')
        assert hasattr(client, 'on_game_end')


class TestGameObserverContract:
    """Test GameObserver interface."""
    
    def test_game_observer_is_abstract(self):
        """Test GameObserver is ABC but can be instantiated (all methods have defaults)."""
        observer = GameObserver()
        assert isinstance(observer, GameObserver)
        assert isinstance(observer, ABC)
    
    def test_game_observer_methods_exist(self):
        """Test GameObserver has expected methods."""
        observer = GameObserver()
        assert hasattr(observer, 'on_game_start')
        assert hasattr(observer, 'on_turn_start')
        assert hasattr(observer, 'on_action_executed')
        assert hasattr(observer, 'on_invalid_action')
        assert hasattr(observer, 'on_game_end')
    
    def test_game_observer_methods_callable(self):
        """Test GameObserver methods are callable with expected signatures."""
        observer = GameObserver()
        
        from dicewars.api.types import GamePhase, BattleSystem, SupplyPolicy, TimeoutPolicy, WinnerPolicy, TiebreakToken, MapLayout, GameState
        
        layout = MapLayout(
            map_name="test_map",
            dimensions=Position(10, 10),
            territories={},
            grid_lookup=[[(-1) for _ in range(10)] for _ in range(10)]
        )
        config = GameConfig(
            map_layout=layout,
            num_players=2
        )
        
        state = GameState(
            owners=[],
            dice=[],
            active_player_id=1,
            phase=GamePhase.ATTACK,
            turn_number=1,
            tick_id="123"
        )
        
        # These should not raise exceptions
        observer.on_game_start(config, state)
        observer.on_turn_start(1, 1)
        observer.on_game_end(state)


class TestGameCoordinatorContract:
    """Test GameCoordinator interface."""
    
    def test_game_coordinator_instantiable(self):
        """Test GameCoordinator can be instantiated."""
        from dicewars.api.types import GamePhase, BattleSystem, SupplyPolicy, TimeoutPolicy, WinnerPolicy, TiebreakToken, MapLayout
        
        layout = MapLayout(
            map_name="test_map",
            dimensions=Position(10, 10),
            territories={},
            grid_lookup=[[(-1) for _ in range(10)] for _ in range(10)]
        )
        config = GameConfig(
            map_layout=layout,
            num_players=2
        )
        
        class MockClient(PlayerClient):
            def get_action(self, context: TurnContext) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
                return EndTurnAction()
        
        clients = [MockClient(), MockClient()]
        coordinator = GameCoordinator(config, clients)
        assert isinstance(coordinator, GameCoordinator)
    
    def test_game_coordinator_with_observers(self):
        """Test GameCoordinator accepts observers."""
        from dicewars.api.types import GamePhase, BattleSystem, SupplyPolicy, TimeoutPolicy, WinnerPolicy, TiebreakToken, MapLayout
        
        layout = MapLayout(
            map_name="test_map",
            dimensions=Position(10, 10),
            territories={},
            grid_lookup=[[(-1) for _ in range(10)] for _ in range(10)]
        )
        config = GameConfig(
            map_layout=layout,
            num_players=2
        )
        
        class MockClient(PlayerClient):
            def get_action(self, context: TurnContext) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
                return EndTurnAction()
        
        clients = [MockClient(), MockClient()]
        observers = [GameObserver()]
        coordinator = GameCoordinator(config, clients, observers)
        assert isinstance(coordinator, GameCoordinator)