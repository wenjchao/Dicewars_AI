"""Test M2 type validation and serialization."""

import pytest
from dicewars.api.types import (
    GamePhase, BattleSystem, SupplyPolicy, TimeoutPolicy,
    WinnerPolicy, TiebreakToken, InvalidAction,
    AttackAction, EndTurnAction, DistributeSupplyAction, PenaltyAction,
    BattleResult, ActionResult, StateDelta,
    TurnContext, SupplyDescriptor, GameConfig, Capabilities
)


class TestM2Enums:
    """Test M2 enum values."""
    
    def test_game_phase_values(self):
        """Test GamePhase enum values."""
        assert GamePhase.SETUP.value == "setup"
        assert GamePhase.ATTACK.value == "attack"
        assert GamePhase.SUPPLY.value == "supply"
        assert GamePhase.GAME_OVER.value == "game_over"
    
    def test_battle_system_values(self):
        """Test BattleSystem enum values."""
        assert BattleSystem.INDIVIDUAL_DICE_COMPARISON.value == "individual_dice_comparison"
        assert BattleSystem.SUMMATION_DICE_COMPARISON.value == "summation_dice_comparison"
    
    def test_supply_policy_values(self):
        """Test SupplyPolicy enum values."""
        assert SupplyPolicy.ALLOW_EARLY_END.value == "allow_early_end"
        assert SupplyPolicy.MUST_DISTRIBUTE_ALL.value == "must_distribute_all"
    
    def test_timeout_policy_values(self):
        """Test TimeoutPolicy enum values."""
        assert TimeoutPolicy.AUTO_END_TURN.value == "auto_end_turn"
        assert TimeoutPolicy.SKIP_NEXT_TURN.value == "skip_next_turn"
        assert TimeoutPolicy.FORFEIT_GAME.value == "forfeit_game"
    
    def test_winner_policy_values(self):
        """Test WinnerPolicy enum values."""
        assert WinnerPolicy.NONE.value == "none"
        assert WinnerPolicy.MOST_TERRITORIES.value == "most_territories"
        assert WinnerPolicy.MOST_TOTAL_DICE.value == "most_total_dice"
        assert WinnerPolicy.LARGEST_CONNECTED.value == "largest_connected"
        assert WinnerPolicy.LEXICOGRAPHIC.value == "lexicographic"
    
    def test_tiebreak_token_values(self):
        """Test TiebreakToken enum values."""
        assert TiebreakToken.TERRITORIES.value == "territories"
        assert TiebreakToken.TOTAL_DICE.value == "total_dice"
        assert TiebreakToken.LARGEST_CONNECTED.value == "largest_connected"
        assert TiebreakToken.PLAYER_ID.value == "player_id"
    
    def test_invalid_action_values(self):
        """Test InvalidAction enum values."""
        assert InvalidAction.NOT_YOUR_TURN.value == "not_your_turn"
        assert InvalidAction.BAD_PHASE.value == "bad_phase"
        assert InvalidAction.INVALID_TERRITORY.value == "invalid_territory"
        assert InvalidAction.INSUFFICIENT_DICE.value == "insufficient_dice"


class TestM2Actions:
    """Test M2 action DTOs."""
    
    def test_attack_action_creation(self):
        """Test AttackAction creation."""
        action = AttackAction(
            attacker_territory_id=1,
            defender_territory_id=2,
            attack_index=5
        )
        assert action.attacker_territory_id == 1
        assert action.defender_territory_id == 2
        assert action.attack_index == 5
        assert action.type == "attack"
    
    def test_end_turn_action_creation(self):
        """Test EndTurnAction creation."""
        action = EndTurnAction()
        assert action.type == "end_turn"
    
    def test_distribute_supply_action_creation(self):
        """Test DistributeSupplyAction creation."""
        action = DistributeSupplyAction(
            placements={1: 3, 2: 2}
        )
        assert action.placements[1] == 3
        assert action.placements[2] == 2
        assert action.type == "distribute_supply"
    
    def test_penalty_action_creation(self):
        """Test PenaltyAction creation."""
        action = PenaltyAction(
            reason="timeout",
            penalty_type="skip_turn"
        )
        assert action.reason == "timeout"
        assert action.penalty_type == "skip_turn"
        assert action.type == "penalty"


class TestM2Results:
    """Test M2 result DTOs."""
    
    def test_battle_result_creation(self):
        """Test BattleResult creation."""
        result = BattleResult(
            attacker_casualties=2,
            defender_casualties=1,
            attacker_rolls=[6, 5, 4],
            defender_rolls=[3, 2],
            attack_pair_index=5,
            territory_conquered=True,
            winner="attacker"
        )
        assert result.attacker_casualties == 2
        assert result.defender_casualties == 1
        assert result.attacker_rolls == [6, 5, 4]
        assert result.defender_rolls == [3, 2]
        assert result.attack_pair_index == 5
        assert result.territory_conquered == True
        assert result.winner == "attacker"
    
    def test_state_delta_creation(self):
        """Test StateDelta creation."""
        delta = StateDelta(
            changed_territories=[1, 2, 3],
            new_owners=[0, 1, 0],
            new_dice=[3, 2, 4]
        )
        assert delta.changed_territories == [1, 2, 3]
        assert delta.new_owners == [0, 1, 0]
        assert delta.new_dice == [3, 2, 4]


class TestM2Immutability:
    """Test M2 types are immutable."""
    
    def test_attack_action_immutable(self):
        """Test AttackAction is immutable."""
        action = AttackAction(
            attacker_territory_id=1,
            defender_territory_id=2,
            attack_index=5
        )
        with pytest.raises(AttributeError):
            action.attacker_territory_id = 999  # type: ignore
    
    def test_battle_result_immutable(self):
        """Test BattleResult is immutable."""
        result = BattleResult(
            attacker_casualties=2,
            defender_casualties=1,
            attacker_rolls=[6, 5],
            defender_rolls=[3, 2],
            attack_pair_index=5,
            territory_conquered=True,
            winner="attacker"
        )
        with pytest.raises(AttributeError):
            result.winner = "defender"  # type: ignore