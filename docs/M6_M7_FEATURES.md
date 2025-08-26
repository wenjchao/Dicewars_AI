# M6 & M7 Features Documentation

## M6: Penalty System

### Overview
The penalty system (M6) implements timeout detection and penalty enforcement for player actions. This ensures fair gameplay and prevents stalling tactics.

### Decision Window Management
- Each player action starts a **decision window** with configurable timeout
- Default timeout: 300,000ms (5 minutes)
- Window tracks: start time, player ID, timeout duration
- Timeout is detected when elapsed time exceeds configured limit

### Penalty Types

#### AUTO_END_TURN (default)
- Immediately ends the current player's turn
- Any pending actions are cancelled
- Game proceeds to next player's turn

#### SKIP_NEXT_TURN
- Adds player to `pending_skips` set
- Player's next turn is completely skipped
- Useful for penalizing timeout violations more severely

#### FORFEIT_GAME
- Eliminates player from the game
- Player loses all territories (implementation pending)
- Harsh penalty for repeated violations

### CLI Usage

```bash
# Set timeout to 10 seconds with skip-next-turn penalty
python scripts/run_cli.py map.json human bot \
  --timeout 10000 \
  --timeout-policy skip_next_turn

# Quick timeout for testing (3 seconds, auto-end)
python scripts/run_cli.py map.json human bot \
  --timeout 3000 \
  --timeout-policy auto_end_turn

# Forfeit game on timeout (harsh mode)
python scripts/run_cli.py map.json human bot \
  --timeout 5000 \
  --timeout-policy forfeit_game
```

### Implementation Details
- Penalties are **first-class actions** with `type="penalty"`
- Penalties do **NOT** consume RNG state (maintains game determinism)
- Pending skips are stored in `CoreState.pending_skips`
- Max-turns boundary has **precedence** over pending penalties

## M7: Winner Determination

### Overview
The winner determination system (M7) provides flexible policies for determining game winners, including support for draws and complex tiebreaker chains.

### Game Over Triggers

1. **Elimination Victory**
   - Triggered when only 1 active player remains
   - Winner determined immediately (same mutation)
   - No separate turn processing needed

2. **Max-Turns Boundary**
   - Triggered when `turn_number >= max_turns`
   - Cancels all pending skip penalties
   - Winner determined by configured policy

### Winner Policies

#### MOST_TERRITORIES (default)
- Player with most territories wins
- Simple and intuitive
- Rewards territorial expansion

#### MOST_TOTAL_DICE
- Player with highest sum of dice across all territories wins
- Rewards both expansion and consolidation
- Strategic dice placement matters

#### LARGEST_CONNECTED
- Player with largest connected territory region wins
- Rewards territorial consolidation
- Encourages defensive play

#### LEXICOGRAPHIC
- Lowest player ID wins (Player 0 > Player 1 > Player 2)
- Deterministic fallback
- Ensures no true ties

#### NONE
- Allows draws (winner_id = None)
- Game can end without a winner
- Useful for tournament formats

### Tiebreaker Chain
When the main winner policy results in a tie, the system applies a configurable tiebreaker chain in order:

1. First tiebreaker in chain
2. Second tiebreaker in chain
3. Continue until winner found
4. Final fallback: lexicographic (lowest player ID)

Default chain: `[territories, total_dice, player_id]`

### CLI Usage

```bash
# Winner by total dice count
python scripts/run_cli.py map.json bot1 bot2 \
  --winner-policy most_total_dice

# Winner by largest connected region
python scripts/run_cli.py map.json bot1 bot2 \
  --winner-policy largest_connected

# Custom tiebreaker chain
python scripts/run_cli.py map.json bot1 bot2 \
  --winner-policy most_territories \
  --tiebreak-chain total_dice largest_connected player_id

# Allow draws
python scripts/run_cli.py map.json bot1 bot2 \
  --winner-policy none \
  --max-turns 50

# Complex configuration
python scripts/run_cli.py map.json human aggressive \
  --winner-policy largest_connected \
  --tiebreak-chain territories total_dice player_id \
  --max-turns 100
```

## Integration Examples

### Quick Competitive Game
```bash
# Fast-paced game with aggressive timeouts and total dice victory
python scripts/run_cli.py tests/fixtures/small_map.json human aggressive \
  --timeout 5000 \
  --timeout-policy skip_next_turn \
  --winner-policy most_total_dice \
  --max-turns 50
```

### Tournament Configuration
```bash
# Tournament with draws allowed and strict penalties
python scripts/run_cli.py tournament_map.json bot1 bot2 \
  --winner-policy none \
  --tiebreak-chain territories total_dice \
  --timeout 30000 \
  --timeout-policy skip_next_turn \
  --max-turns 100 \
  --seed 42
```

### Strategic Consolidation Game
```bash
# Rewards connected regions with forgiving timeouts
python scripts/run_cli.py map.json human cautious \
  --winner-policy largest_connected \
  --tiebreak-chain total_dice territories player_id \
  --timeout 60000 \
  --timeout-policy auto_end_turn \
  --supply-calc largest
```

## Technical Implementation

### State Management
- `GamePhase.GAME_OVER` - New phase for ended games
- `CoreState.winner_id` - Stores determined winner (or None)
- `CoreState.pending_skips` - Set of players to skip next turn
- `CoreState.check_game_over()` - Unified game-over checking

### Engine Integration
- `get_turn_context()` returns empty `valid_actions` after GAME_OVER
- `apply_action()` rejects actions with `BAD_PHASE` error after GAME_OVER
- Penalty actions handled as first-class actions

### Winner Determination Flow
1. Check for single active player (elimination)
2. Apply main `winner_policy`
3. If tied, apply `tiebreak_chain` in order
4. Final fallback to lexicographic ordering

## Configuration Reference

### Penalty System
- `--timeout <ms>` - Action timeout in milliseconds (default: 300000)
- `--timeout-policy <policy>` - Penalty type (default: auto_end_turn)
  - auto_end_turn
  - skip_next_turn
  - forfeit_game

### Winner Determination
- `--winner-policy <policy>` - Main winner policy (default: most_territories)
  - none
  - most_territories
  - most_total_dice
  - largest_connected
  - lexicographic
- `--tiebreak-chain <token>...` - Ordered tiebreakers (default: territories total_dice player_id)
  - territories
  - total_dice
  - largest_connected
  - player_id
- `--max-turns <n>` - Maximum game turns (default: 1000)

## Testing

### Unit Tests
```bash
# Test penalty system
python -m pytest tests/unit/test_m6_penalty_system.py -v

# Test winner determination
python -m pytest tests/unit/test_m7_winner_system.py -v

# Test both systems
python -m pytest tests/unit/test_m6_penalty_system.py tests/unit/test_m7_winner_system.py -v
```

### Integration Testing
```bash
# Quick bot game with custom settings
python scripts/run_cli.py tests/fixtures/small_map.json random aggressive \
  --winner-policy most_total_dice \
  --timeout-policy skip_next_turn \
  --timeout 5000 \
  --max-turns 20 \
  --observer verbose \
  --seed 42
```