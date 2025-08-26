# Dicewars CLI Guide

## Basic Usage

```bash
python scripts/run_cli.py <map_file> <player1> <player2> [...] [options]
```

## Example Commands

### Quick Start
```bash
# Human vs aggressive bot with default settings
python scripts/run_cli.py tests/fixtures/small_map.json human aggressive

# Human vs random bot with summation battles
python scripts/run_cli.py tests/fixtures/small_map.json human random --battle-system summation

# 3-player game with mixed bots
python scripts/run_cli.py tests/fixtures/small_map.json human aggressive cautious
```

### Advanced Examples
```bash
# Full customization example
python scripts/run_cli.py tests/fixtures/small_map.json human aggressive \
  --battle-system summation \
  --supply-calc largest \
  --seed 42 \
  --observer verbose \
  --timeout 30000 \
  --max-turns 500

# Fixed supply with battlefront distribution
python scripts/run_cli.py map.json human random \
  --supply-calc fixed \
  --supply-amount 10 \
  --supply-distribution battlefront \
  --battle-system individual

# Largest connected region supply calculation
python scripts/run_cli.py map.json human cautious \
  --supply-calc largest \
  --observer quiet \
  --seed 123

# M6/M7 Advanced: Custom winner policy with penalty system
python scripts/run_cli.py tests/fixtures/small_map.json human aggressive \
  --winner-policy largest_connected \
  --tiebreak-chain total_dice territories player_id \
  --timeout-policy skip_next_turn \
  --timeout 10000 \
  --max-turns 100
```

## Player Types

### Bot Players
- `random` - Makes random valid moves
- `passive` - Only attacks when strongly advantaged  
- `aggressive` - Attacks whenever possible
- `heuristic` - Uses strategic evaluation
- `cautious` - Only attacks with minimum 2 dice advantage

### Human Player
- `human` - Interactive player with CLI interface
  - During ATTACK: Choose from numbered attack options or end turn
  - During SUPPLY: Only appears with `--supply-distribution manual`. Distribute dice manually (e.g., `0:2 2:1` gives T0 2 dice, T2 1 die)

## Command Line Options

### Battle System (`--battle-system` or `-b`)
- `individual` (default) - Pairwise dice comparison with AUTO_ALL_BUT_ONE rules
- `summation` - Sum all dice, winner takes all

### Supply Calculation (`--supply-calc`)
- `total` (default) - Based on total territories owned (1 die per territory)
- `largest` - Based on largest connected region size
- `fixed` - Fixed amount per turn (use with `--supply-amount`)
- `bonus` - Total territories + bonuses for large regions

### Supply Options
- `--supply-amount N` - Fixed supply amount when using `--supply-calc fixed` (default: 5)
- `--supply-policy [allow_early_end|must_distribute_all]` - Supply distribution policy (default: allow_early_end)
  - `allow_early_end` - Player can end turn before distributing all supply dice
  - `must_distribute_all` - Player must distribute all available supply dice before ending turn
- `--supply-distribution [manual|uniform|random|battlefront|weakest_first|strongest_first]` - How supply is distributed (default: random)
  - `manual` - Players (human or bot) manually choose where to place supply dice
  - `uniform` - Engine automatically distributes evenly across all territories
  - `random` - Engine automatically distributes randomly across territories  
  - `battlefront` - Engine focuses on territories adjacent to enemies
  - `weakest_first` - Engine prioritizes territories with fewest dice
  - `strongest_first` - Engine builds up territories with most dice

### Game Settings
- `--max-turns N` - Maximum number of turns (default: 1000)
- `--timeout N` - Timeout in milliseconds per action (default: 300000)
- `--seed N` - Random seed for reproducible games

### Penalty System Options (M6)
- `--timeout-policy [no_penalty|auto_end_turn|skip_next_turn|forfeit_game]` - Penalty policy for all violations (default: auto_end_turn)
  - `no_penalty` - No penalties applied for any reason (timeouts, invalid actions, errors). Game continues unchanged. Perfect for practice/analysis mode
  - `auto_end_turn` - Immediately end the current player's turn
  - `skip_next_turn` - Skip the player's next turn entirely
  - `forfeit_game` - Remove player from game (elimination)

### Winner Determination Options (M7)
- `--winner-policy [none|most_territories|most_total_dice|largest_connected|lexicographic]` - How to determine winner (default: most_territories)
  - `none` - Allow draws (winner_id can be None)
  - `most_territories` - Player with most territories wins
  - `most_total_dice` - Player with highest total dice across all territories wins
  - `largest_connected` - Player with largest connected territory region wins
  - `lexicographic` - Lowest player ID wins (deterministic fallback)
  
- `--tiebreak-chain <token1> <token2> ...` - Ordered list of tiebreaker policies (default: territories total_dice player_id)
  - `territories` - Compare territory count
  - `total_dice` - Compare total dice count
  - `largest_connected` - Compare largest connected region size
  - `player_id` - Lexicographic ordering (lowest ID wins)

### Display Options
- `--observer [quiet|normal|verbose]` - Observer verbosity level (default: normal)
  - `quiet` - Minimal output, just game start/end
  - `normal` - Standard game flow and major events
  - `verbose` - Detailed output including all state changes

### Utility Options
- `--validate` - Validate map file and exit without playing

## Supply Phase Mechanics

### Supply Calculation Formulas
- **total** - `supply = total_territories_owned`
  - 1 territory = 1 die
  - 4 territories = 4 dice
  - 10 territories = 10 dice
  - Direct 1:1 relationship
- **largest** - `supply = largest_connected_region_size`
  - Based on your largest group of connected territories
  - Example: 4 connected territories = 4 dice
  - Rewards territorial consolidation over expansion
- **fixed** - Always get the amount specified by `--supply-amount`
  - Consistent supply regardless of territory count
  - Example: `--supply-amount 8` always gives 8 dice
- **bonus** - `supply = total_territories + region_bonuses`
  - Base territories plus +1 for each region with 4+ territories
  - Rewards both expansion and consolidation

### Supply Distribution Strategies
Supply distribution is controlled by the `--supply-distribution` option and applies to all players in the game:

**Manual Distribution (`--supply-distribution manual`):**
- All players (human or bot) provide manual supply placement decisions
- Human players: Interactive input with format `territory:dice` (e.g., `0:2 1:1`)  
- Bot players: Make strategic placement decisions
- Can distribute partial supply (if `--supply-policy allow_early_end`)

**Automated Distribution (engine handles internally):**
- **UNIFORM** - Engine distributes evenly across all territories
- **RANDOM** - Engine distributes randomly across territories
- **BATTLEFRONT** - Engine focuses on territories adjacent to enemies
- **WEAKEST_FIRST** - Engine prioritizes territories with fewest dice
- **STRONGEST_FIRST** - Engine builds up territories with most dice
- Players never see supply phase - engine handles everything during turn transitions

### Phase Transitions
Phase transitions depend on the supply distribution configuration:

**With Manual Distribution (`--supply-distribution manual`):**
- ATTACK → SUPPLY → ATTACK → end turn (if `allow_multiple_supply_phases`)
- ATTACK → SUPPLY → end turn
- Players interact during SUPPLY phase

**With Automated Distribution (`--supply-distribution random/uniform/etc`):**
- ATTACK → [internal supply] → end turn
- No SUPPLY phase visible to players
- Engine handles supply distribution during turn transitions

## Map Files

Map files should be JSON format with territory layout and adjacencies. Example maps are provided in:
- `tests/fixtures/small_map.json` - 6 territories, good for quick games
- `tests/fixtures/medium_map.json` - Medium-sized map
- Custom maps can be created following the same JSON structure

## Tips for Playing

1. **As Human Player**:
   - Press Enter to see available actions
   - Type action number (1, 2, 3, etc.) to select
   - During supply (if `--supply-distribution manual`), use format `territory:dice` (e.g., `0:3 2:2`)
   - Type `help` for in-game help
   - Type `quit` or `q` to exit

2. **Battle Systems**:
   - Individual: More tactical, gradual conquest
   - Summation: High-stakes, winner takes all

3. **Supply Strategies**:
   - Total territories rewards expansion
   - Largest connected rewards consolidation
   - Fixed amount creates consistent gameplay

## Common Issues & Troubleshooting

### Supply Phase Issues
- **Supply amount confusion**: With the `total` calculation, 4 territories = 4 dice. Each territory gives 1 supply die.
- **"No supply phase appearing"**: If you don't see a supply phase, the game is using automated distribution (`--supply-distribution random/uniform/etc`). Use `--supply-distribution manual` to interact with supply.
- **"Supply timeout too fast"**: Only applies to manual distribution. Type quickly during supply input or use `--timeout-policy no_penalty` for practice.

### Battle System Confusion  
- **Individual vs Summation**: Individual allows gradual conquest, summation is all-or-nothing
- **"Defender wins but lost territory"**: In summation system, attacker can win the dice sum but still be called "defender wins" in some display bugs

### Performance Tips
- Use `--observer quiet` for fast bot vs bot games
- Use `--timeout 5000` for quicker human games (5 seconds per action)
- Use seeds (`--seed 42`) for reproducible games during testing

## Debugging and Testing

```bash
# Reproducible game with specific seed
python scripts/run_cli.py map.json random random --seed 42

# Quick bot-only game
python scripts/run_cli.py map.json aggressive cautious --observer quiet

# Verbose output for debugging
python scripts/run_cli.py map.json human random --observer verbose --seed 123

# Fast human game with shorter timeout
python scripts/run_cli.py map.json human random --timeout 5000

# Fixed supply for consistent testing
python scripts/run_cli.py map.json human aggressive --supply-calc fixed --supply-amount 8

# Test penalty system with skip-next-turn policy
python scripts/run_cli.py map.json human random --timeout-policy skip_next_turn --timeout 5000

# Game with winner determined by total dice
python scripts/run_cli.py map.json aggressive passive --winner-policy most_total_dice

# Custom tiebreaker chain
python scripts/run_cli.py map.json human cautious --tiebreak-chain total_dice largest_connected player_id

# Allow draws with NONE winner policy
python scripts/run_cli.py map.json random random --winner-policy none --max-turns 50

# Test penalty system with aggressive timeout
python scripts/run_cli.py map.json human aggressive --timeout 3000 --timeout-policy skip_next_turn

# Practice mode - no timeout penalties
python scripts/run_cli.py map.json human cautious --timeout-policy no_penalty

# Analysis mode - track timeouts but don't penalize
python scripts/run_cli.py map.json human heuristic --timeout 10000 --timeout-policy no_penalty --observer verbose

# Manual supply distribution for strategic gameplay
python scripts/run_cli.py map.json human aggressive --supply-distribution manual

# Automated battlefront strategy for bots
python scripts/run_cli.py map.json aggressive cautious --supply-distribution battlefront

# Uniform automated distribution - engine handles all supply for consistency
python scripts/run_cli.py map.json human random --supply-distribution uniform

# I like this
python scripts/run_cli.py tests/fixtures/medium_map.json human aggressive passive \
    --supply-distribution random \
    --timeout-policy no_penalty \
    --supply-calc largest \
    --battle-system summation \
    --observer verbose \
    --max-turns 1000
```