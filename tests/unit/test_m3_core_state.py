"""Unit tests for M3 core state management."""

import pytest
from dicewars.core.state import CoreState, create_initial_state
from dicewars.api.types import (
    GameConfig, GamePhase, BattleSystem, SupplyPolicy, TimeoutPolicy,
    WinnerPolicy, TiebreakToken, MapLayout, Position, TerritoryLayout
)


@pytest.fixture
def simple_config():
    """Create a simple test configuration."""
    territories = {}
    for i in range(4):
        territories[i] = TerritoryLayout(
            id=i,
            name=f"Territory{i}",
            tiles=[Position(i % 2, i // 2)],
            adjacencies=[j for j in range(4) if j != i],
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
        max_turns=10
    )


class TestCoreState:
    """Test CoreState functionality."""
    
    def test_core_state_creation(self, simple_config):
        """Test CoreState can be created with valid parameters."""
        state = CoreState(
            owners=[0, 1, 0, 1],
            dice=[3, 3, 3, 3],
            active_player_id=0,
            phase=GamePhase.ATTACK,
            turn_number=1,
            tick_id=1,
            config=simple_config
        )
        
        assert len(state.owners) == 4
        assert len(state.dice) == 4
        assert state.active_player_id == 0
        assert state.phase == GamePhase.ATTACK
        assert state.turn_number == 1
        assert state.tick_id == 1
        assert state.config == simple_config
    
    def test_to_public_state(self, simple_config):
        """Test conversion to public API state."""
        state = CoreState(
            owners=[0, 1, 0, 1],
            dice=[3, 2, 4, 1],
            active_player_id=1,
            phase=GamePhase.SUPPLY,
            turn_number=5,
            tick_id=42,
            config=simple_config
        )
        
        public_state = state.to_public_state()
        
        assert public_state.owners == [0, 1, 0, 1]
        assert public_state.dice == [3, 2, 4, 1]
        assert public_state.active_player_id == 1
        assert public_state.phase == GamePhase.SUPPLY
        assert public_state.turn_number == 5
        assert public_state.tick_id == "42"  # Should be string
        assert public_state.winner_id is None
        assert public_state.eliminated_players == []
    
    def test_hash_methods(self, simple_config):
        """Test state and position hash methods."""
        state = CoreState(
            owners=[0, 1, 0, 1],
            dice=[3, 3, 3, 3],
            active_player_id=0,
            phase=GamePhase.ATTACK,
            turn_number=1,
            tick_id=1,
            config=simple_config
        )
        
        state_hash = state.get_state_hash()
        position_hash = state.get_position_hash()
        
        assert isinstance(state_hash, str)
        assert isinstance(position_hash, str)
        
        # In HASHLESS_MODE, both hashes are "0", which is expected for M3
        from dicewars.core.hash import HASHLESS_MODE
        if not HASHLESS_MODE:
            assert state_hash != position_hash  # Should be different in full mode
        else:
            assert state_hash == "0"
            assert position_hash == "0"
    
    def test_advance_tick(self, simple_config):
        """Test tick advancement."""
        state = CoreState(
            owners=[0, 1, 0, 1],
            dice=[3, 3, 3, 3],
            active_player_id=0,
            phase=GamePhase.ATTACK,
            turn_number=1,
            tick_id=1,
            config=simple_config
        )
        
        initial_tick = state.tick_id
        state.advance_tick()
        assert state.tick_id == initial_tick + 1
    
    def test_advance_turn(self, simple_config):
        """Test turn advancement."""
        state = CoreState(
            owners=[0, 1, 0, 1],
            dice=[3, 3, 3, 3],
            active_player_id=0,
            phase=GamePhase.ATTACK,
            turn_number=1,
            tick_id=1,
            config=simple_config
        )
        
        initial_turn = state.turn_number
        initial_player = state.active_player_id
        
        state.advance_turn()
        
        assert state.turn_number == initial_turn + 1
        assert state.active_player_id == (initial_player + 1) % simple_config.num_players
        assert state.phase == GamePhase.ATTACK
    
    def test_advance_turn_skip_eliminated(self, simple_config):
        """Test turn advancement skips eliminated players."""
        state = CoreState(
            owners=[0, 1, 0, 1],
            dice=[3, 3, 3, 3],
            active_player_id=0,
            phase=GamePhase.ATTACK,
            turn_number=1,
            tick_id=1,
            eliminated_players=[1],  # Player 1 eliminated
            config=simple_config
        )
        
        state.advance_turn()
        
        # Should skip player 1 and go back to player 0
        assert state.active_player_id == 0
    
    def test_eliminate_player(self, simple_config):
        """Test player elimination."""
        state = CoreState(
            owners=[0, 1, 0, 1],
            dice=[3, 3, 3, 3],
            active_player_id=0,
            phase=GamePhase.ATTACK,
            turn_number=1,
            tick_id=1,
            config=simple_config
        )
        
        assert 1 not in state.eliminated_players
        state.eliminate_player(1)
        assert 1 in state.eliminated_players
        
        # Eliminating again should not duplicate
        state.eliminate_player(1)
        assert state.eliminated_players.count(1) == 1
    
    def test_check_game_over_single_player(self, simple_config):
        """Test game over condition with single remaining player."""
        state = CoreState(
            owners=[0, 0, 0, 0],  # All territories owned by player 0
            dice=[3, 3, 3, 3],
            active_player_id=0,
            phase=GamePhase.ATTACK,
            turn_number=1,
            tick_id=1,
            eliminated_players=[1],  # Player 1 eliminated
            config=simple_config
        )
        
        game_over = state.check_game_over()
        
        assert game_over is True
        assert state.phase == GamePhase.GAME_OVER
        assert state.winner_id == 0
    
    def test_check_game_over_max_turns(self, simple_config):
        """Test game over condition when max turns reached."""
        state = CoreState(
            owners=[0, 1, 0, 1],
            dice=[3, 3, 3, 3],
            active_player_id=0,
            phase=GamePhase.ATTACK,
            turn_number=simple_config.max_turns,  # At max turns
            tick_id=1,
            config=simple_config
        )
        
        game_over = state.check_game_over()
        
        assert game_over is True
        assert state.phase == GamePhase.GAME_OVER
        assert state.winner_id is not None
    
    def test_winner_determination_territories(self, simple_config):
        """Test winner determination by territory count."""
        # Player 0 has 3 territories, player 1 has 1
        state = CoreState(
            owners=[0, 0, 0, 1],
            dice=[3, 3, 3, 3],
            active_player_id=0,
            phase=GamePhase.ATTACK,
            turn_number=simple_config.max_turns,
            tick_id=1,
            config=simple_config
        )
        
        state.check_game_over()
        assert state.winner_id == 0  # Player 0 has most territories


class TestCreateInitialState:
    """Test initial state creation."""
    
    def test_create_initial_state(self, simple_config):
        """Test creating initial state from config."""
        state = create_initial_state(simple_config)
        
        assert len(state.owners) == 4
        assert len(state.dice) == 4
        assert state.active_player_id == 0
        assert state.phase == GamePhase.ATTACK
        assert state.turn_number == 1
        assert state.tick_id == 1
        assert state.config == simple_config
        
        # Check territory assignment
        territories_per_player = 4 // 2  # 4 territories, 2 players
        player_0_territories = sum(1 for owner in state.owners if owner == 0)
        player_1_territories = sum(1 for owner in state.owners if owner == 1)
        
        assert player_0_territories == territories_per_player
        assert player_1_territories == territories_per_player
    
    def test_create_initial_state_with_seed(self, simple_config):
        """Test creating initial state with seed."""
        state1 = create_initial_state(simple_config, seed=42)
        state2 = create_initial_state(simple_config, seed=42)
        
        # States should be identical with same seed
        assert state1.owners == state2.owners
        assert state1.dice == state2.dice
    
    def test_initial_dice_distribution(self, simple_config):
        """Test initial dice distribution."""
        state = create_initial_state(simple_config)
        
        # All territories should start with initial dice count
        for dice_count in state.dice:
            assert dice_count == simple_config.initial_dice_per_territory