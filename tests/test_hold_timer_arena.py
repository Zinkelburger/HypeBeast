#!/usr/bin/env python3
"""HBHoldRace in the real arena: one HypeBeast seat (B-black), three scripted
seats, the game played by bughouse_arena.sim.play_game (its clocks, its one
wake timer per board turn, its react wakes and time-advantage flips) and the
HypeBeast seat driven by the arena's own adapter (players.TeamEngineSeat).
One engine process per scenario.

All four clocks start at 60 s and every think costs 2 s. The scripted seats
sit where a scenario needs time to pass, as a slow or sitting HiveMind would.

  timer   openings/hold_set.json game 10 idx 40 (B-black mated in 2, our
          partner A-white mates in 5), with A-white's N@f6 played before
          B-white's f6g7 (independent moves) so the diagonal seat A-black is
          on turn while B-white sits 13 s and our lead grows to 15 s.
          1. B-black holds with A-black on turn (lead 15 s, need 12.75 s).
          2. A-black sits 4 s, then plays e8e7; our partner is on turn.
          3. B-black holds again; A-white then sits for good.
          Wanted: every timer B-black asks for is one the arena grants, and
          B-black moves once its lead falls below what the hold needs.
          chance12 asks for a timer at step 1 with nothing to shrink the lead;
          it fires there, and the arena ignores the request at step 3, so
          B-black is asked again only when our team's time advantage flips
          (lead 0, 12.75 s late). No flag even then: with equal starting clocks
          the flip comes exactly when the race lead runs out.
  free    openings/hold_race_set.json c9 game 8 idx 53 (B-black mated in 1,
          our partner A-white on turn, the lead gone).
          1. A-white sits 1 s, B-black decides with our partner on turn.
          2. A-white plays N@c6 (the forecast's best move); A-black, on turn
             and up on time, sits for good.
          Wanted: B-black does not sit through its flag; it may sit through
          our partner's move (with a timer), then moves. chance12 holds
          ("race=free") at both decisions and flags at 60 s.

    python3 tests/test_hold_timer_arena.py [--bin PATH] [--nodes 1500000]
                                           [--scenario timer,free]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import chess

from hbutil import ARENA_TOOLS, NET, ROOT  # noqa: F401  (puts the arena on sys.path)
from bughouse_arena.players import EngineSpec, TeamEngineSeat
from bughouse_arena.referee import Bughouse
from bughouse_arena.sim import ClockConfig, SeatView, play_game, seat_index

failures = 0
B_BLACK = seat_index(1, chess.BLACK)
CONFIG = ClockConfig(initial_ms=60_000, move_cost_ms=(2_000, 2_000), react_cost_ms=500)


def check(ok: bool, what: str, info: str = "") -> None:
    global failures
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'} {what}" + (f"  [{info}]" if info else ""), flush=True)


class Stop(RuntimeError):
    """A scripted seat ends the game once the scenario has been decided."""


class Scripted:
    """A seat that answers from a function of (view, call number). Returns a
    UCI move, None to sit, or ("sit", ms) to sit with a wake request."""

    def __init__(self, name: str, fn):
        self.name = name
        self.fn = fn
        self.calls = 0
        self.requested_wake_ms: int | None = None

    def new_game(self, board: int, color: chess.Color) -> None:
        pass

    def decide(self, view: SeatView) -> str | None:
        self.requested_wake_ms = None
        self.calls += 1
        out = self.fn(view, self.calls)
        if isinstance(out, tuple):
            self.requested_wake_ms = out[1]
            return None
        return out


def item(path: str, kind: str, game: int, idx: int) -> dict:
    return next(i for i in json.loads((ROOT / path).read_text())
                if i["kind"] == kind and i["game"] == game and i["idx"] == idx)


def build(moves: list[str]) -> Bughouse:
    g = Bughouse()
    for m in moves:
        g.push(int(m[0]) - 1, m[1:])
    return g


def mate_or_stop(team: chess.Color):
    """Our opponent on board B: mate if it can, else end the game here."""
    def fn(view: SeatView, n: int):
        for m in view.game.legal_moves(view.board):
            g = view.game.copy()
            g.push(view.board, m)
            if g.is_checkmate(team, False) and g.is_checkmate(team, True):
                return m
        raise Stop("scenario decided")
    return fn


def run(args, label: str, game: Bughouse, scripted: dict) -> tuple:
    log = Path(tempfile.mkdtemp(prefix=f"hb-{label}-")) / "uci.log"
    spec = EngineSpec.parse(f"hypebeast,bin={args.bin},net={NET},nodes={args.nodes},"
                            f"HBHoldWhenMated=true,HBHoldRace=250")
    engine = TeamEngineSeat(spec, log_path=log)
    try:
        players = dict(scripted)
        players[B_BLACK] = engine
        result = play_game(game, players, CONFIG, cost_key=label)
    finally:
        engine.close()
    ours = [e for e in result.events if e.get("seat") == "B-black" and e["kind"] in ("sit", "move", "flag")]
    for e in ours:
        c = e["clocks"]
        print(f"   t={e['t']:6} {e['kind']:4} lead={c[3] - c[1]:6} clocks={c}"
              + (f" wake_requested={e['wake_requested_ms']}" if "wake_requested_ms" in e else "")
              + (f" wake_at={e['wake_at']}" if "wake_at" in e else "") + (f" {e['uci']}" if "uci" in e else ""))
    coords = [l.split("hb_coord ", 1)[1] for l in log.read_text().splitlines() if "hb_coord " in l]
    for c in coords:
        print("   ", c[:300])
    print(f"   end: {result.termination} {result.error or ''}")
    return result, ours


def honoured(ours: list[dict]) -> tuple[bool, str]:
    bad = [e for e in ours if e["kind"] == "sit" and "wake_requested_ms" in e
           and e.get("wake_at") != e["t"] + max(1, int(e["wake_requested_ms"]))]
    return not bad, ", ".join(f"t={e['t']} asked {e['wake_requested_ms']} got {e.get('wake_at')}" for e in bad)


def scenario_timer(args) -> None:
    print("timer: a timer spent while the lead cannot shrink is missing later", flush=True)
    it = item("openings/hold_set.json", "hold", 10, 40)
    assert it["prefix"][-2:] == ["2f6g7", "1N@f6"]
    game = build(it["prefix"][:-2] + ["1N@f6"])
    assert game.turn(0) == chess.BLACK and game.turn(1) == chess.WHITE

    played = []

    def b_white(view, n):              # sits 13 s, plays f6g7, then the game is decided
        if view.now_ms < 15_000:
            return ("sit", 13_000)
        if not played:
            played.append(view.now_ms)
            return "f6g7"
        return mate_or_stop(chess.WHITE)(view, n)

    def a_black(view, n):              # sits, then 4 s more, then e8e7; sits afterwards
        if view.now_ms < 15_000:
            return None
        if "e8e7" in view.game.legal_moves(0) and view.game.turn(0) == chess.BLACK:
            if view.now_ms < 19_500:
                return ("sit", 19_500 - view.now_ms)
            return "e8e7"
        return None

    result, ours = run(args, "timer", game, {
        seat_index(0, chess.WHITE): Scripted("A-white", lambda v, n: None),   # our partner sits for good
        seat_index(0, chess.BLACK): Scripted("A-black", a_black),
        seat_index(1, chess.WHITE): Scripted("B-white", b_white),
    })
    sits = [e for e in ours if e["kind"] == "sit"]
    move = next((e for e in ours if e["kind"] == "move"), None)
    check(len(sits) >= 2 and sits[0]["clocks"][3] - sits[0]["clocks"][1] == 15_000,
          "B-black holds at lead 15 s with the diagonal seat on turn", f"{len(sits)} sits")
    ok, bad = honoured(ours)
    check(ok, "every timer B-black asks for is granted", bad)
    lead = move["clocks"][3] - move["clocks"][1] if move else None
    check(move is not None and lead >= 12_750 - 2_500 - 1,
          "B-black moves while its lead still covers the partner's mate (not at lead 0)", f"lead at move {lead}")
    check(not any(e["kind"] == "flag" for e in ours), "B-black does not flag")


def scenario_free(args) -> None:
    print("free: a mated-in-1 hold with the race lost", flush=True)
    it = item("openings/hold_race_set.json", "race", 8, 53)
    game = build(it["prefix"])
    assert game.turn(0) == chess.WHITE and game.turn(1) == chess.BLACK

    def a_white(view, n):              # 1 s more thinking, then the forecast's best move
        if n == 1:
            return ("sit", 1_000)
        if view.game.turn(0) == chess.WHITE and "N@c6" in view.game.legal_moves(0):
            return "N@c6"
        return None

    result, ours = run(args, "free", game, {
        seat_index(0, chess.WHITE): Scripted("A-white", a_white),
        seat_index(0, chess.BLACK): Scripted("A-black", lambda v, n: None),   # up on time: sits
        seat_index(1, chess.WHITE): Scripted("B-white", mate_or_stop(chess.WHITE)),
    })
    first = ours[0] if ours else None
    check(first is not None and first["t"] == 2_000, "B-black decides at 2 s with our partner on turn")
    ok, bad = honoured(ours)
    check(ok, "every timer B-black asks for is granted", bad)
    if first and first["kind"] == "sit":
        check("wake_requested_ms" in first, "a free hold with the race lost sits only with a timer")
    move = next((e for e in ours if e["kind"] == "move"), None)
    check(move is not None and move["t"] <= 4_501,
          "B-black moves once our partner has moved (diagonal seat on turn, lead < 0)",
          f"move at {move['t'] if move else None}")
    check(not any(e["kind"] == "flag" for e in ours), "B-black does not flag",
          f"{result.termination}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=str(ROOT / "bin/hypebeast"))
    ap.add_argument("--nodes", type=int, default=1_500_000)
    ap.add_argument("--scenario", default="timer,free")
    args = ap.parse_args()
    args.bin = str(Path(args.bin).resolve())
    for name in args.scenario.split(","):
        {"timer": scenario_timer, "free": scenario_free}[name](args)
    print("RESULT", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
