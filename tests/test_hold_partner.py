#!/usr/bin/env python3
"""HBHoldPartnerMate: sit while our partner has a forced mate we can out-sit.

Board A is the partner board of openings/hold_set.json, hold game 10 idx 46
(A-white, our partner, on turn with a mate in 4 by the forecast). Board B is
ours (B-black) and quiet: the position after 1.e4, so we are not mated and
have no mate. The lead is our clock minus the diagonal seat's (bB - aB); the
hold needs 250 ms + 3 partner moves x 2500 ms = 7.75 s of it: the seat being
mated has its last turn before the fourth, mating move. Clocks keep
aW + aB = bW + bB, as the arena does.

  1. lead 20 s, partner on turn: the engine sits (hold_partner_mate) and asks
     for the turn's timer at lead - need + 1 (its lead shrinks while our
     partner thinks)
  2. the same boards with the lead down to 12 s (a wake, nothing moved): the
     hold continues without a search
  3. the same boards, lead 7 s: the hold ends (hold_end=race_lead) and the
     engine moves
  4. a fresh process, lead 5 s: no hold (hold_declined ... race_lead)
  5. lead 20 s with HBHoldPartnerMate=false: no hold
  6. lead 20 s with HBHoldRace=0: no hold (the rule needs the race guard)
  7. our partner has played the first move of its mate, the diagonal seat is
     on turn: the engine sits again, without a timer (that seat's move wakes
     us, and if it sits the lower clock, its own, flags first)

    python3 tests/test_hold_partner.py [--bin PATH] [--nodes 500000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hbutil import ROOT, Engine, parse_bestmove

A_FEN = "r1bq1br1/ppp1kp1p/2n1pN1p/3pP2N/2pP4/2P2N2/P1Pn1PPP/R3KB1R[QBPqbp] w KQ - 0 16"
B_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR[] b KQkq - 0 1"
NEED = 250 + 3 * 2500

failures = 0


def check(ok: bool, what: str, info: str = "") -> None:
    global failures
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'} {what}" + (f"  [{info}]" if info else ""), flush=True)


def summary(lines: list[str]) -> dict:
    line = next(l for l in lines if l.startswith("info string hb_summary "))
    return dict(kv.split("=", 1) for kv in line.split()[3:] if "=" in kv)


def wake_of(lines: list[str]) -> int | None:
    return next((int(l.split("=")[1]) for l in lines if l.startswith("info string hb_wake_after_ms=")), None)


def clocks(lead: int) -> str:
    """aW, aB, bW, bB with bB - aB = lead and aW + aB = bW + bB."""
    return f"{60000 + lead},60000,60000,{60000 + lead}"


def go(e: Engine, lead: int, nodes: int, moves: str = ""):
    e.setoption("Clocks", clocks(lead))
    e.setoption("TimeAdvantage", "true")
    e.send(f"position fen {A_FEN}|{B_FEN}" + (f" moves {moves}" if moves else ""))
    lines = e.go(f"go nodes {nodes}", timeout=300)
    return parse_bestmove(lines)[1], summary(lines), wake_of(lines), lines


def engine(binary: Path, options: dict | None = None) -> Engine:
    e = Engine(binary, options=options)
    e.setoption("Seat", "Bblack")
    e.setoption("Team", "white")
    return e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=str(ROOT / "bin/hypebeast"))
    ap.add_argument("--nodes", type=int, default=500_000)
    args = ap.parse_args()
    binary = Path(args.bin)

    e = engine(binary)
    try:
        move, s, wake, _ = go(e, 20000, args.nodes)
        check(move == "pass" and s.get("coord_reason") == "hold_partner_mate" and wake == 20000 - NEED + 1,
              "lead 20 s, partner on turn: sits, timer at lead - need + 1",
              f"{move} reason={s.get('coord_reason')} wake={wake} hold={s.get('hold')} declined={s.get('hold_declined')}")
        move, s, wake, _ = go(e, 12000, args.nodes)
        check(move == "pass" and s.get("wait") == "hold_continue", "lead 12 s, nothing moved: hold continues",
              f"{move} wait={s.get('wait')}")
        move, s, wake, _ = go(e, 7000, args.nodes)
        check(move != "pass" and s.get("hold_end") == "race_lead", "lead 7 s: the hold ends and the engine moves",
              f"{move} hold_end={s.get('hold_end')} declined={s.get('hold_declined')}")
    finally:
        e.close()

    e = engine(binary)
    try:
        move, s, wake, _ = go(e, 5000, args.nodes)
        check(move != "pass" and s.get("hold_declined") == "race_lead", "lead 5 s: no hold",
              f"{move} declined={s.get('hold_declined')}")
    finally:
        e.close()

    for opts, what in (({"HBHoldPartnerMate": "false"}, "HBHoldPartnerMate=false"),
                       ({"HBHoldRace": "0"}, "HBHoldRace=0")):
        e = engine(binary, opts)
        try:
            move, s, wake, _ = go(e, 20000, args.nodes)
            check(move != "pass" and "hold" not in s, f"lead 20 s, {what}: no hold",
                  f"{move} reason={s.get('coord_reason')}")
        finally:
            e.close()

    # The first move of the mate, from the forecast's best line
    e = engine(binary)
    try:
        _, _, _, lines = go(e, 20000, args.nodes)
        fc = next(l for l in lines if l.startswith("info string hb_forecast "))
        first = fc.split('"lines":[{"move":"', 1)[1].split('"', 1)[0]
    finally:
        e.close()
    e = engine(binary)
    try:
        move, s, wake, _ = go(e, 18000, args.nodes, f"1{first}")
        check(move == "pass" and s.get("coord_reason") == "hold_partner_mate" and wake is None,
              f"after 1{first}, the diagonal seat on turn: sits, no timer",
              f"{move} reason={s.get('coord_reason')} wake={wake} hold={s.get('hold')} declined={s.get('hold_declined')}")
    finally:
        e.close()

    print("test_hold_partner:", "OK" if not failures else f"{failures} FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
