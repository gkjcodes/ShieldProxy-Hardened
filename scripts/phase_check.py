#!/usr/bin/env python3
"""
ShieldProxy Phase Check CLI
Runs verification suites for individual phases or all phases.
Usage:
    python scripts/phase_check.py --phase 1
    python scripts/phase_check.py --all
"""

import sys
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.checkpoints.phase1 import run_phase1_checkpoints


def main():
    parser = argparse.ArgumentParser(description="ShieldProxy Security Phase Verification")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--phase", type=int, choices=[1, 2, 3, 4], help="Target phase to verify")
    group.add_argument("--all", action="store_true", help="Verify all implemented phases")

    args = parser.parse_args()

    if args.phase == 1 or args.all:
        success = run_phase1_checkpoints()
        if not success:
            sys.exit(1)
        if args.phase == 1:
            sys.exit(0)

    if args.phase in (2, 3, 4):
        print(f"Phase {args.phase} verification is not yet implemented (Phase 1 currently completed).")
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()