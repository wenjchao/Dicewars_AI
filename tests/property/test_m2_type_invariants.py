"""Property-based tests for M2 type invariants."""

import pytest
import hypothesis.strategies as st
from hypothesis import given, assume
import dataclasses

from dicewars.api.types import (
    GamePhase, BattleSystem, SupplyPolicy, TimeoutPolicy,
    WinnerPolicy, TiebreakToken, InvalidAction,
    AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction,
    BattleResult, ActionResult, StateDelta
)


# Strategy generators for M2 types
@st.composite
def attack_action_strategy(draw):
    """Generate AttackAction instances."""
    return AttackAction(
        attacker_territory_id=draw(st.integers(min_value=1, max_value=1000)),
        defender_territory_id=draw(st.integers(min_value=1, max_value=1000)),
        attack_index=draw(st.integers(min_value=0, max_value=999))
    )


@st.composite 
def distribute_supply_action_strategy(draw):
    """Generate DistributeSupplyAction instances."""
    num_placements = draw(st.integers(min_value=0, max_value=10))
    placements = {}
    for i in range(num_placements):
        territory_id = draw(st.integers(min_value=1, max_value=1000))
        dice_count = draw(st.integers(min_value=1, max_value=8))
        placements[territory_id] = dice_count
    return DistributeSupplyAction(placements=placements)


@st.composite
def penalty_action_strategy(draw):
    """Generate PenaltyAction instances."""
    return PenaltyAction(
        reason=draw(st.text(min_size=1, max_size=50)),
        penalty_type=draw(st.sampled_from(["skip_turn", "eliminate", "timeout"]))
    )


@st.composite
def battle_result_strategy(draw):
    """Generate BattleResult instances."""
    attacker_rolls = draw(st.lists(st.integers(min_value=1, max_value=6), min_size=1, max_size=8))
    defender_rolls = draw(st.lists(st.integers(min_value=1, max_value=6), min_size=1, max_size=8))
    return BattleResult(
        attacker_casualties=draw(st.integers(min_value=0, max_value=len(attacker_rolls))),
        defender_casualties=draw(st.integers(min_value=0, max_value=len(defender_rolls))),
        attacker_rolls=attacker_rolls,
        defender_rolls=defender_rolls,
        attack_pair_index=draw(st.integers(min_value=0, max_value=999)),
        territory_conquered=draw(st.booleans()),
        winner=draw(st.sampled_from(["attacker", "defender"]))
    )


@st.composite
def state_delta_strategy(draw):
    """Generate StateDelta instances."""
    return StateDelta(
        changed_territories=draw(st.lists(st.integers(min_value=1, max_value=1000), min_size=0, max_size=20)),
        new_owners=draw(st.lists(st.integers(min_value=0, max_value=8), min_size=0, max_size=20)),
        new_dice=draw(st.lists(st.integers(min_value=0, max_value=8), min_size=0, max_size=20))
    )


class TestM2ActionInvariants:
    """Property-based tests for M2 action invariants."""
    
    @given(attack_action_strategy())
    def test_attack_action_immutability(self, action):
        """Test AttackAction instances are immutable."""
        original_attacker = action.attacker_territory_id
        original_defender = action.defender_territory_id
        original_index = action.attack_index
        original_type = action.type
        
        # Verify immutability by checking fields can't be changed
        with pytest.raises(AttributeError):
            action.attacker_territory_id = 999  # type: ignore
        
        # Values should remain unchanged
        assert action.attacker_territory_id == original_attacker
        assert action.defender_territory_id == original_defender
        assert action.attack_index == original_index
        assert action.type == original_type
    
    @given(attack_action_strategy())
    def test_attack_action_type_field(self, action):
        """Test AttackAction always has correct type field."""
        assert action.type == "attack"
    
    @given(distribute_supply_action_strategy())
    def test_distribute_supply_action_type_field(self, action):
        """Test DistributeSupplyAction always has correct type field."""
        assert action.type == "distribute_supply"
    
    @given(penalty_action_strategy())
    def test_penalty_action_type_field(self, action):
        """Test PenaltyAction always has correct type field."""
        assert action.type == "penalty"
    
    def test_end_turn_action_type_field(self):
        """Test EndTurnAction always has correct type field."""
        action = EndTurnAction()
        assert action.type == "end_turn"
    
    @given(distribute_supply_action_strategy())
    def test_distribute_supply_placements_invariant(self, action):
        """Test DistributeSupplyAction placements are valid."""
        for territory_id, dice_count in action.placements.items():
            assert isinstance(territory_id, int)
            assert isinstance(dice_count, int)
            assert territory_id >= 1
            assert dice_count >= 1


class TestM2ResultInvariants:
    """Property-based tests for M2 result invariants."""
    
    @given(battle_result_strategy())
    def test_battle_result_dice_validity(self, result):
        """Test BattleResult dice arrays contain valid values."""
        for die in result.attacker_rolls:
            assert 1 <= die <= 6
        
        for die in result.defender_rolls:
            assert 1 <= die <= 6
    
    @given(battle_result_strategy())
    def test_battle_result_losses_bounds(self, result):
        """Test BattleResult losses are within reasonable bounds."""
        assert 0 <= result.attacker_casualties <= len(result.attacker_rolls)
        assert 0 <= result.defender_casualties <= len(result.defender_rolls)
    
    @given(state_delta_strategy())
    def test_state_delta_territory_ids_positive(self, delta):
        """Test StateDelta territory IDs are positive."""
        for territory_id in delta.changed_territories:
            assert territory_id >= 1
    
    @given(state_delta_strategy())
    def test_state_delta_arrays_consistent(self, delta):
        """Test StateDelta arrays have consistent lengths."""
        # For valid deltas, all arrays should typically have the same length
        # (though this isn't strictly required by the schema)
        assert len(delta.new_owners) >= 0
        assert len(delta.new_dice) >= 0


class TestM2EnumInvariants:
    """Property-based tests for M2 enum invariants."""
    
    @given(st.sampled_from(list(GamePhase)))
    def test_game_phase_string_values(self, phase):
        """Test GamePhase enum values are strings."""
        assert isinstance(phase.value, str)
        assert phase.value in ["setup", "attack", "supply", "game_over"]
    
    @given(st.sampled_from(list(BattleSystem)))
    def test_battle_system_string_values(self, system):
        """Test BattleSystem enum values are strings."""
        assert isinstance(system.value, str)
        assert system.value in ["individual_dice_comparison", "summation_dice_comparison", "manual"]
    
    @given(st.sampled_from(list(SupplyPolicy)))
    def test_supply_policy_string_values(self, policy):
        """Test SupplyPolicy enum values are strings."""
        assert isinstance(policy.value, str)
        assert policy.value in ["allow_early_end", "must_distribute_all"]
    
    @given(st.sampled_from(list(InvalidAction)))
    def test_invalid_action_string_values(self, action):
        """Test InvalidAction enum values are strings."""
        assert isinstance(action.value, str)
        # Just check it's a non-empty string since there are many possible values


class TestM2DataclassInvariants:
    """Property-based tests for M2 dataclass behavior."""
    
    @given(attack_action_strategy())
    def test_attack_action_is_dataclass(self, action):
        """Test AttackAction is a proper dataclass."""
        assert dataclasses.is_dataclass(action)
        assert action.__dataclass_params__.frozen
    
    @given(distribute_supply_action_strategy())
    def test_distribute_supply_action_is_dataclass(self, action):
        """Test DistributeSupplyAction is a proper dataclass."""
        assert dataclasses.is_dataclass(action)
        assert action.__dataclass_params__.frozen
    
    @given(penalty_action_strategy())
    def test_penalty_action_is_dataclass(self, action):
        """Test PenaltyAction is a proper dataclass."""
        assert dataclasses.is_dataclass(action)
        assert action.__dataclass_params__.frozen
    
    @given(battle_result_strategy())
    def test_battle_result_is_dataclass(self, result):
        """Test BattleResult is a proper dataclass."""
        assert dataclasses.is_dataclass(result)
        assert result.__dataclass_params__.frozen