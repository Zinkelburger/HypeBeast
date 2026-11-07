#!/usr/bin/env bash
# Full engine-side verification (PLAN.md section 8, engine parts).
# Usage: tests/run_all.sh [fuzz_games] [workers]
set -euo pipefail
cd "$(dirname "$0")"
GAMES=${1:-2000}
WORKERS=${2:-18}
python3 test_upstream_parity.py
python3 test_terminal_fixtures.py
python3 test_probe.py --long
python3 test_replay_fuzz.py --games "$GAMES" --workers "$WORKERS"
python3 smoke_games.py --games 16 --nodes 4000 --workers 5
