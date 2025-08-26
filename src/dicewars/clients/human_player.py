"""Human player client for interactive CLI gameplay."""

import sys
from typing import Union, Optional, List
from dicewars.api.client import PlayerClient
from dicewars.api.types import (
    GameConfig, GameState, TurnContext, AttackAction, EndTurnAction,
    DistributeSupplyAction
)


class HumanPlayer(PlayerClient):
    """Interactive human player for CLI."""
    
    def __init__(self, player_id: Optional[int] = None):
        self.player_id = player_id
        self.name = f"human_{player_id}" if player_id is not None else "human"
    
    def get_action(self, context: TurnContext) -> Union[AttackAction, EndTurnAction, DistributeSupplyAction]:
        """Get human player's action through CLI input."""
        game_state = context.game_state
        valid_actions = context.valid_actions
        
        print("\n" + "="*60)
        print(f"YOUR TURN - Player {self.player_id}")
        print(f"Phase: {game_state.phase.value}")
        print(f"Time remaining: {context.time_remaining_ms/1000:.1f} seconds")
        
        # Show supply info if in supply phase
        if game_state.phase.value == "supply" and context.supply:
            print(f"Supply available: {context.supply.supply_remaining} dice")
        
        print("="*60)
        
        # Show valid actions
        print("\nAvailable actions:")
        attack_actions = [a for a in valid_actions if isinstance(a, AttackAction)]
        supply_actions = [a for a in valid_actions if isinstance(a, DistributeSupplyAction)]
        end_turn_actions = [a for a in valid_actions if isinstance(a, EndTurnAction)]
        
        action_list = []
        action_index = 1
        
        # List attack actions
        if attack_actions:
            print(f"\n  ATTACK ACTIONS:")
            for action in attack_actions:
                attacker_dice = game_state.dice[action.attacker_territory_id]
                defender_dice = game_state.dice[action.defender_territory_id]
                defender_owner = game_state.owners[action.defender_territory_id]
                print(f"    {action_index}. Attack T{action.defender_territory_id} from T{action.attacker_territory_id}")
                print(f"       Your dice: {attacker_dice}, Enemy dice: {defender_dice} (Player {defender_owner})")
                action_list.append(action)
                action_index += 1
        
        # List supply actions
        if supply_actions:
            print(f"\n  SUPPLY ACTIONS:")
            for action in supply_actions:
                print(f"    {action_index}. Distribute supply to T{action.territory_id}")
                action_list.append(action)
                action_index += 1
        
        # In supply phase, add option to distribute supply
        if game_state.phase.value == "supply" and context.supply and context.supply.supply_remaining > 0:
            print(f"\n  SUPPLY DISTRIBUTION:")
            print(f"    {action_index}. Distribute supply dice")
            action_list.append("distribute_supply")  # Special marker
            action_index += 1
        
        # List end turn action
        if end_turn_actions:
            print(f"\n  END TURN:")
            for action in end_turn_actions:
                print(f"    {action_index}. End turn (skip supply)" if game_state.phase.value == "supply" else f"    {action_index}. End turn")
                action_list.append(action)
                action_index += 1
        
        # Show your territories
        your_territories = []
        for i, owner in enumerate(game_state.owners):
            if owner == self.player_id:
                your_territories.append((i, game_state.dice[i]))
        
        print(f"\nYour territories:")
        for tid, dice in your_territories:
            print(f"  T{tid}: {dice} dice")
        
        # Get user input
        while True:
            try:
                print(f"\nEnter action number (1-{len(action_list)}), 'help', or 'quit': ", end="")
                user_input = input().strip().lower()
                
                if user_input == 'help':
                    self._show_help()
                    continue
                
                if user_input == 'quit' or user_input == 'q':
                    print("Quitting game...")
                    sys.exit(0)
                
                action_num = int(user_input)
                if 1 <= action_num <= len(action_list):
                    selected_action = action_list[action_num - 1]
                    
                    # Handle supply distribution
                    if selected_action == "distribute_supply":
                        supply_action = self._get_supply_distribution(context)
                        if supply_action:
                            return supply_action
                        continue
                    
                    print(f"Selected: {self._format_action(selected_action)}")
                    return selected_action
                else:
                    print(f"Invalid action number. Please enter 1-{len(action_list)}")
                    
            except ValueError:
                print("Please enter a valid number or 'help'")
            except KeyboardInterrupt:
                print("\nQuitting game...")
                sys.exit(0)
    
    def _show_help(self):
        """Show help information."""
        print("\nHELP:")
        print("  - Enter the number of the action you want to take")
        print("  - Attack actions let you attack adjacent enemy territories")
        print("  - Supply actions distribute new dice to your territories")
        print("  - End turn passes control to the next player")
        print("  - Type 'quit' or 'q' to exit the game")
        print("  - Territories are numbered (T0, T1, etc.) and shown on the board")
    
    def _get_supply_distribution(self, context: TurnContext) -> Optional[DistributeSupplyAction]:
        """Get supply distribution from user input."""
        if not context.supply:
            return None
        
        supply_remaining = context.supply.supply_remaining
        territories_owned = context.supply.territories_owned
        max_dice = context.supply.max_dice_per_territory
        
        print(f"\n=== SUPPLY DISTRIBUTION ===")
        print(f"You have {supply_remaining} dice to distribute")
        print(f"Your territories (current dice / max {max_dice}):")
        
        for tid in territories_owned:
            current_dice = context.game_state.dice[tid]
            print(f"  T{tid}: {current_dice}/{max_dice} dice")
        
        print(f"\nEnter distribution (e.g., '0:2 2:1' to give T0 2 dice and T2 1 die)")
        print("Or 'cancel' to go back, 'quit' to exit game:")
        
        while True:
            try:
                print("> ", end="", flush=True)
                user_input = input().strip()
                
                if user_input.lower() == 'cancel':
                    return None
                
                if user_input.lower() == 'quit' or user_input.lower() == 'q':
                    print("Quitting game...")
                    sys.exit(0)
                
                # Parse input like "0:2 2:1"
                placements = {}
                total = 0
                
                if user_input:  # If not empty, parse placements
                    for placement in user_input.split():
                        if ':' in placement:
                            tid_str, amount_str = placement.split(':')
                            tid = int(tid_str)
                            amount = int(amount_str)
                            
                            if tid not in territories_owned:
                                print(f"Error: T{tid} is not your territory")
                                break
                            
                            if amount <= 0:
                                print(f"Error: Amount must be positive")
                                break
                            
                            current = context.game_state.dice[tid]
                            if current + amount > max_dice:
                                print(f"Error: T{tid} would exceed max dice ({current} + {amount} > {max_dice})")
                                break
                            
                            placements[tid] = placements.get(tid, 0) + amount
                            total += amount
                    else:
                        # All placements valid
                        if total > supply_remaining:
                            print(f"Error: Total {total} exceeds available supply {supply_remaining}")
                            continue
                        
                        if total == 0:
                            print("Error: Must place at least 1 die")
                            continue
                        
                        return DistributeSupplyAction(placements=placements)
                
            except (ValueError, IndexError):
                print("Invalid format. Use 'territory:amount' (e.g., '0:2 2:1')")
            except KeyboardInterrupt:
                return None
    
    def _format_action(self, action) -> str:
        """Format action for display."""
        if isinstance(action, AttackAction):
            return f"Attack T{action.defender_territory_id} from T{action.attacker_territory_id}"
        elif isinstance(action, DistributeSupplyAction):
            return f"Distribute supply to T{action.territory_id}"
        elif isinstance(action, EndTurnAction):
            return "End turn"
        else:
            return str(action)
    
    def on_game_start(self, config: GameConfig, player_id: int) -> None:
        """Called when game starts."""
        self.player_id = player_id
        self.name = f"human_{player_id}"
        print(f"\n*** WELCOME! You are Player {player_id} ***")
        print(f"Game starting on map: {config.map_layout.map_name}")
        print(f"Players: {config.num_players}")
        print(f"Max turns: {config.max_turns}")
    
    def on_game_end(self, final_state: GameState) -> None:
        """Called when game ends."""
        if final_state.winner_id == self.player_id:
            print(f"\n🎉 CONGRATULATIONS! You won as Player {self.player_id}! 🎉")
        elif final_state.winner_id is not None:
            print(f"\n😞 Game over. Player {final_state.winner_id} won. Better luck next time!")
        else:
            print(f"\n🤝 Game ended in a draw!")
    
    def __str__(self):
        return self.name