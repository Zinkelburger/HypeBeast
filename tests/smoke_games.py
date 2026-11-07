"""Four-seat smoke games: bin/hypebeast plays every seat through full games
using the arena's own simulator and referee (sim.play_game), with a minimal
seat adapter (no modified arena needed).

    python3 tests/smoke_games.py --games 12 --nodes 4000 --workers 6
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
from collections import Counter

import chess

from hbutil import Engine, HYPEBEAST, SEATS, parse_bestmove, summary_fields
from coverage_stats import coverage
from bughouse_arena.referee import Bughouse, team_name  # noqa: E402
from bughouse_arena.sim import ClockConfig, play_game, seat_index  # noqa: E402


class HypeBeastSeat:
    def __init__(self, coordination: bool, budget: str):
        self.engine = Engine(HYPEBEAST, options={"Coordination": "true" if coordination else "false"})
        self.budget = budget
        self.name = f"hb-coord{int(coordination)}"
        self.decisions = self.passes = self.bad = 0
        self.summaries = []

    def new_game(self, board: int, color: chess.Color) -> None:
        self.board = board
        seat = SEATS[seat_index(board, color)]
        team = color if board == 0 else not color
        self.engine.send("ucinewgame")
        self.engine.setoption("Seat", seat)
        self.engine.setoption("Team", team_name(team))
        self.engine.sync()

    def decide(self, view) -> str | None:
        self.engine.setoption("Clocks", ",".join(str(c) for c in view.clocks_ms))
        self.engine.setoption("TimeAdvantage", "true" if view.time_advantage else "false")
        moves = " ".join(view.game.engine_moves())
        self.engine.send(f"position startpos moves {moves}" if moves else "position startpos")
        lines = self.engine.go(f"go {self.budget}", timeout=120)
        self.engine.send("stop")
        if any("hb_error" in l for l in lines):
            self.bad += 1
        self.summaries.append(summary_fields(lines))
        a, b = parse_bestmove(lines)
        own, other = (a, b) if self.board == 0 else (b, a)
        if other != "pass":
            raise RuntimeError(f"non-pass in unused half: {lines[-1]}")
        self.decisions += 1
        if own == "pass":
            self.passes += 1
            return None
        return own

    def close(self):
        self.engine.close()


def run(args) -> dict:
    index, budget = args
    # Alternate which team coordinates; one in four games all-off.
    coord_white = index % 2 == 0
    coord = {s: (coord_white if (s in (0, 3)) else not coord_white) for s in range(4)}
    if index % 4 == 3:
        coord = {s: False for s in range(4)}
    seats = {s: HypeBeastSeat(coord[s], budget) for s in range(4)}
    try:
        result = play_game(Bughouse(), seats, ClockConfig(), cost_key=f"smoke{index}",
                           record_events=False)
        out = {"termination": result.termination,
               "winner": None if result.winner is None else team_name(result.winner),
               "error": result.error, "plies": len(result.moves),
               "decisions": sum(p.decisions for p in seats.values()),
               "passes": sum(p.passes for p in seats.values()),
               "hb_errors": sum(p.bad for p in seats.values()),
               "summaries": [x for p in seats.values() for x in p.summaries]}
    finally:
        for p in seats.values():
            p.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=12)
    ap.add_argument("--nodes", type=int, default=4000)
    ap.add_argument("--movetime", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    budget = f"movetime {args.movetime}" if args.movetime else f"nodes {args.nodes}"
    with mp.Pool(args.workers) as pool:
        results = pool.map(run, [(i, budget) for i in range(args.games)])
    terms = Counter(r["termination"] for r in results)
    bad = [r for r in results if r["error"] or r["termination"] in ("illegal move", "error") or r["hb_errors"]]
    summaries = []
    for i, r in enumerate(results):
        summaries.extend(r.pop("summaries"))
        print(f"game {i}: {r}")
    print("coverage:", coverage(summaries))
    print(f"smoke: games={len(results)} budget='{budget}' terminations={dict(terms)} "
          f"plies={sum(r['plies'] for r in results)} decisions={sum(r['decisions'] for r in results)} "
          f"passes={sum(r['passes'] for r in results)} bad={len(bad)}")
    print("RESULT", "PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
