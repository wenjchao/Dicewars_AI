"""Heuristic bot client implementation."""

import random
from typing import Union, List, Tuple
from ..api.client import PlayerClient
from ..api.types import (
    TurnContext, GameConfig, GameState,
    AttackAction, EndTurnAction, DistributeSupplyAction
)


class HeuristicBot(PlayerClient):
    """Bot that uses simple heuristics to make decisions."""
    
    def __init__(self, name: str = "HeuristicBot", seed: int = None):
        """Initialize heuristic bot.
        
        Args:
            name: Bot name for identification
            seed: Random seed for tie-breaking
        """
        self.name = name
        self.player_id = None
        self.rng = random.Random(seed)
        
    def get_action(self, context: TurnContext) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
        """Get action using simple heuristics."""
        game_state = context.game_state
        
        # Filter attack actions
        attack_actions = [action for action in context.valid_actions 
                         if isinstance(action, AttackAction)]
        
        if not attack_actions:
            return EndTurnAction()
        
        # Score each attack based on heuristics
        scored_attacks = []
        for attack in attack_actions:
            score = self._score_attack(attack, game_state)
            scored_attacks.append((attack, score))
        
        # Sort by score (higher is better)
        scored_attacks.sort(key=lambda x: x[1], reverse=True)
        
        # Take the best attack with some randomness for ties
        best_score = scored_attacks[0][1]
        best_attacks = [attack for action, score in scored_attacks if score == best_score]
        
        if best_score > 0:  # Only attack if score is positive
            return self.rng.choice(best_attacks)
        else:
            return EndTurnAction()  # No good attacks available
    
    def _score_attack(self, attack: AttackAction, game_state: GameState) -> float:
        """Score an attack action using heuristics."""
        attacker_dice = game_state.dice[attack.attacker_territory_id]
        defender_dice = game_state.dice[attack.defender_territory_id]
        defender_owner = game_state.owners[attack.defender_territory_id]
        
        score = 0.0
        
        # 1. Prefer attacks we're likely to win (more dice)
        dice_advantage = attacker_dice - defender_dice
        if dice_advantage > 0:
            score += dice_advantage * 2.0  # Strong preference for dice advantage
        else:
            score += dice_advantage * 1.0  # Penalty for disadvantage
        
        # 2. Bonus for attacking weak territories (1-2 dice)
        if defender_dice <= 2:
            score += 3.0
        
        # 3. Bonus for attacking neutral territories
        if defender_owner == -1:
            score += 1.5
        
        # 4. Prefer attacking with strong territories (more dice)
        if attacker_dice >= 5:
            score += 1.0
        
        # 5. Small randomness to break ties
        score += self.rng.random() * 0.1
        
        return score
    
    def on_game_start(self, config: GameConfig, player_id: int) -> None:
        """Called when game starts."""
        self.player_id = player_id
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        pass
    
    def __str__(self) -> str:
        return f"{self.name}(P{self.player_id})" if self.player_id is not None else self.name


class CautiousBot(PlayerClient):
    """Bot that only attacks when it has significant advantage."""
    
    def __init__(self, name: str = "CautiousBot", min_advantage: int = 2):
        """Initialize cautious bot.
        
        Args:
            name: Bot name for identification
            min_advantage: Minimum dice advantage required to attack
        """
        self.name = name
        self.player_id = None
        self.min_advantage = min_advantage
        
    def get_action(self, context: TurnContext) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
        """Attack only with significant advantage."""
        game_state = context.game_state
        
        # Filter attack actions
        attack_actions = [action for action in context.valid_actions 
                         if isinstance(action, AttackAction)]
        
        # Find attacks with sufficient advantage
        good_attacks = []
        for attack in attack_actions:
            attacker_dice = game_state.dice[attack.attacker_territory_id]
            defender_dice = game_state.dice[attack.defender_territory_id]
            
            if attacker_dice - defender_dice >= self.min_advantage:
                good_attacks.append(attack)
        
        if good_attacks:
            # Pick the attack with the highest dice advantage
            best_attack = max(good_attacks, 
                            key=lambda a: game_state.dice[a.attacker_territory_id] - 
                                        game_state.dice[a.defender_territory_id])
            return best_attack
        else:
            return EndTurnAction()
    
    def on_game_start(self, config: GameConfig, player_id: int) -> None:
        """Called when game starts."""
        self.player_id = player_id
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        pass
    
    def __str__(self) -> str:
        return f"{self.name}(P{self.player_id})" if self.player_id is not None else self.name