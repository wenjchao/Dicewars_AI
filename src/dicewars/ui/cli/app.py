"""CLI application for running Dice Wars games."""

import json
import sys
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Any

from ...api.coordinator import GameCoordinator
from ...api.client import PlayerClient
from ...api.types import (
    GameConfig, MapLayout, Position, TerritoryLayout, BattleSystem, 
    SupplyDistribution, SupplyPolicy, TimeoutPolicy, WinnerPolicy, TiebreakToken
)
from ...observers.cli import CLIObserver, QuietCLIObserver, VerboseCLIObserver
from ...clients.random_bot import RandomBot, PassiveBot, AggressiveBot
from ...clients.heuristic_bot import HeuristicBot, CautiousBot
from ...clients.human_player import HumanPlayer


def load_map_from_json(map_path: Path) -> MapLayout:
    """Load map layout from JSON file."""
    try:
        with open(map_path, 'r') as f:
            data = json.load(f)
        
        # Convert JSON data to MapLayout
        territories = {}
        territories_data = data['territories']
        
        # Handle both list and dictionary formats
        if isinstance(territories_data, dict):
            # Dictionary format: {"0": {...}, "1": {...}}
            for key, territory_data in territories_data.items():
                territory_id = int(key)
                territories[territory_id] = TerritoryLayout(
                    id=territory_id,
                    name=territory_data['name'],
                    tiles=[Position(pos['x'], pos['y']) for pos in territory_data['tiles']],
                    adjacencies=territory_data['adjacencies'],
                    border=[]  # Border segments not implemented yet
                )
        else:
            # List format: [{"id": 0, ...}, {"id": 1, ...}]
            for territory_data in territories_data:
                territories[territory_data['id']] = TerritoryLayout(
                    id=territory_data['id'],
                    name=territory_data['name'],
                    tiles=[Position(pos['x'], pos['y']) for pos in territory_data['tiles']],
                    adjacencies=territory_data['adjacencies'],
                    border=[]  # Border segments not implemented yet
                )
        
        return MapLayout(
            map_name=data.get('map_name', 'Unknown Map'),
            dimensions=Position(data['dimensions']['x'], data['dimensions']['y']),
            territories=territories,
            grid_lookup=data['grid_lookup']
        )
    
    except Exception as e:
        raise ValueError(f"Failed to load map from {map_path}: {e}")


def create_bot(bot_type: str, player_id: int, **kwargs) -> PlayerClient:
    """Create a bot client of the specified type."""
    name = f"{bot_type}_{player_id}"
    
    if bot_type == "random":
        return RandomBot(name, seed=kwargs.get('seed'))
    elif bot_type == "passive":
        return PassiveBot(name)
    elif bot_type == "aggressive":
        return AggressiveBot(name, seed=kwargs.get('seed'))
    elif bot_type == "heuristic":
        return HeuristicBot(name, seed=kwargs.get('seed'))
    elif bot_type == "cautious":
        return CautiousBot(name, min_advantage=kwargs.get('min_advantage', 2))
    elif bot_type == "human":
        return HumanPlayer(player_id)
    else:
        raise ValueError(f"Unknown bot type: {bot_type}")


def create_observer(observer_type: str) -> CLIObserver:
    """Create an observer of the specified type."""
    if observer_type == "quiet":
        return QuietCLIObserver()
    elif observer_type == "verbose":
        return VerboseCLIObserver()
    elif observer_type == "normal":
        return CLIObserver()
    else:
        raise ValueError(f"Unknown observer type: {observer_type}")


def run_game(map_path: Path,
             bot_types: List[str],
             observer_type: str = "normal",
             max_turns: int = 1000,
             timeout_ms: int = 300000,
             seed: Optional[int] = None,
             battle_system: str = "individual",
             supply_calc: str = "total",
             supply_amount: int = 5,
             supply_policy: str = "allow_early_end",
             supply_distribution: str = "random",
             timeout_policy: str = "auto_end_turn",
             winner_policy: str = "most_territories",
             tiebreak_chain: Optional[List[str]] = None) -> None:
    """Run a single game with the specified parameters."""
    
    # Load map
    try:
        map_layout = load_map_from_json(map_path)
        print(f"Loaded map: {map_layout.map_name}")
        print(f"Size: {map_layout.dimensions.x}x{map_layout.dimensions.y}")
        print(f"Territories: {len(map_layout.territories)}")
        print(f"Players: {len(bot_types)}")
        print()
    except Exception as e:
        print(f"Error loading map: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Import additional types
    from ...api.types import SupplyCalculation
    
    # Convert battle system string to enum
    battle_system_enum = (BattleSystem.SUMMATION_DICE_COMPARISON 
                         if battle_system == "summation" 
                         else BattleSystem.INDIVIDUAL_DICE_COMPARISON)
    
    # Convert supply calculation string to enum
    supply_calc_map = {
        "total": SupplyCalculation.TOTAL_TERRITORIES,
        "largest": SupplyCalculation.LARGEST_CONNECTED,
        "fixed": SupplyCalculation.FIXED_AMOUNT,
        "bonus": SupplyCalculation.TERRITORIES_PLUS_BONUS
    }
    supply_calc_enum = supply_calc_map.get(supply_calc, SupplyCalculation.TOTAL_TERRITORIES)
    
    # Convert supply policy string to enum
    supply_policy_enum = (SupplyPolicy.MUST_DISTRIBUTE_ALL 
                         if supply_policy == "must_distribute_all"
                         else SupplyPolicy.ALLOW_EARLY_END)
    
    # Convert supply distribution string to enum
    supply_distribution_map = {
        "manual": SupplyDistribution.MANUAL,
        "uniform": SupplyDistribution.UNIFORM,
        "random": SupplyDistribution.RANDOM,
        "battlefront": SupplyDistribution.BATTLEFRONT,
        "weakest_first": SupplyDistribution.WEAKEST_FIRST,
        "strongest_first": SupplyDistribution.STRONGEST_FIRST
    }
    supply_distribution_enum = supply_distribution_map.get(supply_distribution, SupplyDistribution.RANDOM)
    
    # Convert timeout policy string to enum
    timeout_policy_map = {
        "no_penalty": TimeoutPolicy.NO_PENALTY,
        "auto_end_turn": TimeoutPolicy.AUTO_END_TURN,
        "skip_next_turn": TimeoutPolicy.SKIP_NEXT_TURN,
        "forfeit_game": TimeoutPolicy.FORFEIT_GAME
    }
    timeout_policy_enum = timeout_policy_map.get(timeout_policy, TimeoutPolicy.AUTO_END_TURN)
    
    # Convert winner policy string to enum
    winner_policy_map = {
        "none": WinnerPolicy.NONE,
        "most_territories": WinnerPolicy.MOST_TERRITORIES,
        "most_total_dice": WinnerPolicy.MOST_TOTAL_DICE,
        "largest_connected": WinnerPolicy.LARGEST_CONNECTED,
        "lexicographic": WinnerPolicy.LEXICOGRAPHIC
    }
    winner_policy_enum = winner_policy_map.get(winner_policy, WinnerPolicy.MOST_TERRITORIES)
    
    # Convert tiebreak chain strings to enums
    tiebreak_token_map = {
        "territories": TiebreakToken.TERRITORIES,
        "total_dice": TiebreakToken.TOTAL_DICE,
        "largest_connected": TiebreakToken.LARGEST_CONNECTED,
        "player_id": TiebreakToken.PLAYER_ID
    }
    
    if tiebreak_chain:
        tiebreak_chain_enums = [tiebreak_token_map[token] for token in tiebreak_chain 
                                if token in tiebreak_token_map]
    else:
        # Default tiebreak chain
        tiebreak_chain_enums = [
            TiebreakToken.TERRITORIES,
            TiebreakToken.TOTAL_DICE,
            TiebreakToken.PLAYER_ID
        ]
    
    # Create game configuration
    config = GameConfig(
        map_layout=map_layout,
        num_players=len(bot_types),
        battle_system=battle_system_enum,
        supply_calculation=supply_calc_enum,
        supply_distribution=supply_distribution_enum,
        supply_policy=supply_policy_enum,
        fixed_supply_amount=supply_amount,
        timeout_policy=timeout_policy_enum,
        timeout_ms=timeout_ms,
        winner_policy=winner_policy_enum,
        winner_tiebreak_chain=tiebreak_chain_enums,
        max_turns=max_turns,
        seed=seed
    )
    
    # Create bot clients
    clients = []
    for i, bot_type in enumerate(bot_types):
        try:
            bot = create_bot(bot_type, i, seed=seed)
            clients.append(bot)
            print(f"Player {i}: {bot}")
        except Exception as e:
            print(f"Error creating bot {i} ({bot_type}): {e}", file=sys.stderr)
            sys.exit(1)
    
    # Create observer
    observer = create_observer(observer_type)
    
    print()
    print("Starting game...")
    print("=" * 60)
    
    # Run game
    try:
        coordinator = GameCoordinator(config, clients, [observer])
        final_state = coordinator.run()
        
        print("=" * 60)
        print("Game completed successfully!")
        return final_state
        
    except Exception as e:
        print(f"Error during game: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """CLI application entry point."""
    parser = argparse.ArgumentParser(description="Dice Wars CLI Game Runner")
    
    # Required arguments
    parser.add_argument("map", type=Path, help="Path to map JSON file")
    parser.add_argument("bots", nargs="*", 
                       help="Bot types for each player: random, passive, aggressive, heuristic, cautious, human")
    
    # Optional arguments
    parser.add_argument("--observer", "-o", default="normal",
                       choices=["quiet", "normal", "verbose"],
                       help="Observer verbosity level")
    parser.add_argument("--max-turns", "-t", type=int, default=1000,
                       help="Maximum number of turns")
    parser.add_argument("--timeout", type=int, default=300000,
                       help="Timeout in milliseconds per action (default: 300000ms = 5 minutes)")
    parser.add_argument("--seed", type=int, default=None,
                       help="Random seed for reproducible games")
    parser.add_argument("--battle-system", "-b", default="individual", 
                       choices=["individual", "summation"],
                       help="Battle resolution system: individual dice comparison vs summation")
    parser.add_argument("--supply-calc", default="total",
                       choices=["total", "largest", "fixed", "bonus"],
                       help="Supply calculation: total territories, largest connected, fixed amount, or with bonuses")
    parser.add_argument("--supply-amount", type=int, default=5,
                       help="Fixed supply amount when using --supply-calc fixed")
    parser.add_argument("--supply-policy", default="allow_early_end",
                       choices=["allow_early_end", "must_distribute_all"],
                       help="Supply distribution policy: allow early turn end or must distribute all dice")
    parser.add_argument("--supply-distribution", default="random",
                       choices=["manual", "uniform", "random", "battlefront", "weakest_first", "strongest_first"],
                       help="Supply distribution strategy: manual (players decide) or automated strategy")
    
    # M6 Penalty system options
    parser.add_argument("--timeout-policy", default="auto_end_turn",
                       choices=["no_penalty", "auto_end_turn", "skip_next_turn", "forfeit_game"],
                       help="Penalty policy for timeout violations (M6)")
    
    # M7 Winner determination options
    parser.add_argument("--winner-policy", default="most_territories",
                       choices=["none", "most_territories", "most_total_dice", 
                               "largest_connected", "lexicographic"],
                       help="Winner determination policy (M7)")
    parser.add_argument("--tiebreak-chain", nargs="+", 
                       choices=["territories", "total_dice", "largest_connected", "player_id"],
                       help="Tiebreaker chain for winner determination (M7)")
    
    parser.add_argument("--validate", action="store_true",
                       help="Validate map file and exit")
    
    args = parser.parse_args()
    
    # Validate bot types
    valid_bot_types = ["random", "passive", "aggressive", "heuristic", "cautious", "human"]
    if not args.validate:
        if len(args.bots) < 2:
            print("Error: At least 2 players required", file=sys.stderr)
            sys.exit(1)
        
        if len(args.bots) > 8:
            print("Error: Maximum 8 players supported", file=sys.stderr)
            sys.exit(1)
        
        for bot_type in args.bots:
            if bot_type not in valid_bot_types:
                print(f"Error: Invalid bot type '{bot_type}'. Valid types: {valid_bot_types}", file=sys.stderr)
                sys.exit(1)
    
    if not args.map.exists():
        print(f"Error: Map file not found: {args.map}", file=sys.stderr)
        sys.exit(1)
    
    # Validate map if requested
    if args.validate:
        try:
            map_layout = load_map_from_json(args.map)
            print(f" Map validation successful: {map_layout.map_name}")
            print(f"   Size: {map_layout.dimensions.x}x{map_layout.dimensions.y}")
            print(f"   Territories: {len(map_layout.territories)}")
            
            # Show territory adjacencies
            for tid, territory in map_layout.territories.items():
                print(f"   T{tid} ({territory.name}): adjacent to {territory.adjacencies}")
            
            sys.exit(0)
        except Exception as e:
            print(f"L Map validation failed: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Run the game
    run_game(
        map_path=args.map,
        bot_types=args.bots,
        observer_type=args.observer,
        max_turns=args.max_turns,
        timeout_ms=args.timeout,
        seed=args.seed,
        battle_system=args.battle_system,
        supply_calc=args.supply_calc,
        supply_amount=args.supply_amount,
        supply_policy=args.supply_policy,
        supply_distribution=args.supply_distribution,
        timeout_policy=args.timeout_policy,
        winner_policy=args.winner_policy,
        tiebreak_chain=args.tiebreak_chain
    )


if __name__ == "__main__":
    main()