"""
Run this script from project root to initialize database.

Usage:
  python run_seed.py
"""

import subprocess
import sys
from pathlib import Path

def run_seed():
    """Run seed.py with correct Python path setup."""
    root = Path(__file__).parent
    
    # Use python -m to run module properly
    result = subprocess.run(
        [sys.executable, "-m", "backend.seed"],
        cwd=root,
        capture_output=False
    )
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    run_seed()
