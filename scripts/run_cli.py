#!/usr/bin/env python3
"""
Dice Wars CLI Runner Script

This script provides easy access to the Dice Wars CLI application.
Run from the project root directory.

Examples:
    # Basic 2-player game with random bots
    python scripts/run_cli.py tests/fixtures/small_map.json random random

    # 3-player game with different bot types
    python scripts/run_cli.py tests/fixtures/small_map.json heuristic aggressive cautious

    # Quiet mode for testing
    python scripts/run_cli.py tests/fixtures/small_map.json random random --observer quiet

    # Verbose mode with seed for debugging
    python scripts/run_cli.py tests/fixtures/small_map.json random random --observer verbose --seed 42

    # Validate map file
    python scripts/run_cli.py tests/fixtures/small_map.json --validate
"""

import sys
from pathlib import Path

# Add src to Python path so we can import dicewars
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Import and run the CLI app
try:
    from dicewars.ui.cli.app import main
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"Error importing dicewars package: {e}", file=sys.stderr)
    print("Make sure to run this script from the project root directory.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Error running CLI: {e}", file=sys.stderr)
    sys.exit(1)