#!/usr/bin/env python3
"""
Local CLI entry point — no PYTHONPATH or `cd` into `src/` required.

Usage (from this directory):
  python run_signal.py migrate
  python run_signal.py collect-hn
  python run_signal.py extract --limit 20
"""
from __future__ import annotations

import sys
from pathlib import Path

# Parent of `problem_discovery` package = `src` (must be on sys.path)
_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from problem_discovery.signal.cli import main

if __name__ == "__main__":
    main()
