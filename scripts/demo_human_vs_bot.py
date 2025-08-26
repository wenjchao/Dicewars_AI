#!/usr/bin/env python3
"""
Demo script showing human vs bot gameplay with improved CLI.

This demonstrates the new features:
1. 1-minute timeout (60 seconds per action)
2. Human player with interactive controls 
3. Clear map visualization with legend and territory details
4. Attack options display with dice counts
"""

import sys
from pathlib import Path

# Add src to Python path so we can import dicewars
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from dicewars.ui.cli.app import main

if __name__ == "__main__":
    # Set up demo arguments
    demo_args = [
        "tests/fixtures/small_map.json",  # Map file
        "human",                          # Player 0: human
        "aggressive",                     # Player 1: aggressive bot  
        "--observer", "normal",           # Normal verbosity
        "--timeout", "60000",            # 1 minute per action
        "--seed", "42"                   # Reproducible for demo
    ]
    
    print("🎮 Dice Wars Demo: Human vs Aggressive Bot")
    print("=" * 50)
    print("Features demonstrated:")
    print("• 1-minute timeout per action")
    print("• Interactive human player controls")
    print("• Clear map visualization with legend")
    print("• Territory details and adjacencies")
    print("• Attack options with dice counts")
    print("=" * 50)
    print()
    
    # Replace sys.argv to simulate command line args
    original_argv = sys.argv
    sys.argv = ["demo"] + demo_args
    
    try:
        main()
    finally:
        sys.argv = original_argv