#!/usr/bin/env python3
"""HBHoldRace: a hold has to win the clock race, and ends when it no longer can.

One engine, one position (openings/hold_set.json, hold game 10 idx 40:
B-black mated in 2, partner A-white mates in 5 by the forecast). The logged
clocks give a lead of 1.8 s over the diagonal seat (A-black); here our clock
is raised so the lead covers the partner's mate (250 + 5 x 2500 ms).

  1. lead 16.3 s: the engine holds; the diagonal seat is on turn, so the
     lead cannot shrink before it moves (its move wakes us) and no timer is
     spent (the arena grants one per board turn)
  2. same boards, lead 14.0 s (a wake with nothing moved): hold continues
  3. same boards, lead 11.3 s: the hold ends (hold_end=race_lead), the
     position is searched again and the engine moves
  4. a fresh process at the logged clocks (lead 1.8 s): no hold

Board B, one board turn of B-black while board A follows the forecast's line
(e8e7 N@g8 h8g8): the race pair is B-black against A-black (lead = bB - aB),
the time-advantage flip that wakes our team is A-white against B-white.

  5. arena clocks (aW + aB = bW + bB, as sim.py keeps them): partner on turn,
     hold with a timer at lead - need + 1; diagonal on turn, hold without
     one; the timer fires with nothing moved, hold continues; partner on
     turn again with the timer spent: the hold stands, since our team's
     flip comes exactly when the lead runs out
  6. the same with clocks the arena cannot produce (aW - bW < 0 < bB - aB,
     the second reviewer's example): with the timer spent and no flip ahead
     nothing would wake us before our flag, so the engine does not sit

    python3 tests/test_hold_race.py [--bin PATH] [--nodes 4500000]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hbutil import ROOT, Engine, parse_bestmove

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


def board_b_turn(args, item: dict, opts: dict) -> None:
    """Fixtures 5 and 6: one board turn of B-black, board A moving."""
    line = ["1e8e7", "1N@g8", "1h8g8"]
    steps = {
        # (extra board-A moves, aW, aB, bW, bB) ; arena: aW + aB == bW + bB
        "arena": [(1, 50000, 20000, 30000, 40000), (2, 48000, 20000, 30000, 38000),
                  (2, 48000, 12000, 30000, 30000), (3, 47500, 11500, 30000, 29000)],
        "other": [(1, 50000, 20000, 60000, 40000), (2, 48000, 20000, 60000, 38000),
                  (2, 48000, 12000, 60000, 30000), (3, 47500, 11500, 60000, 29000)],
    }
    for kind, seq in steps.items():
        e = Engine(Path(args.bin), options=opts)
        out = []
        try:
            e.setoption("Seat", item["seat"])
            e.setoption("Team", item["team"])
            for n, aw, ab, bw, bb in seq:
                e.setoption("Clocks", f"{aw},{ab},{bw},{bb}")
                e.setoption("TimeAdvantage", "true" if aw > bw else "false")
                e.send("position startpos moves " + " ".join(item["prefix"] + line[:n]))
                lines = e.go(f"go nodes {args.nodes}", timeout=120 + args.nodes / 20_000)
                out.append((parse_bestmove(lines)[1], summary(lines), wake_of(lines), bb - ab))
        finally:
            e.close()
        (m1, s1, w1, l1), (m2, s2, w2, _), (m3, s3, w3, _), (m4, s4, w4, l4) = out
        # hb_summary splits the hold detail into its own key=value fields
        need1 = int(s1["need"]) if "need" in s1 else None
        check(m1 == "pass" and s1.get("lead") == str(l1) and need1 is not None and w1 == l1 - need1 + 1,
              f"{kind}: board B, partner on turn: hold, race pair bB - aB, timer at lead - need + 1",
              f"{m1} wake={w1} lead={s1.get('lead')} need={need1}")
        check(m2 == "pass" and s2.get("reason") == "hold_mated" and w2 is None,
              f"{kind}: diagonal seat on turn: hold, no timer", f"{m2} wake={w2} reason={s2.get('reason')}")
        check(m3 == "pass" and s3.get("wait") == "hold_continue",
              f"{kind}: timer fired, nothing moved, lead unchanged: hold continues", f"{m3} wait={s3.get('wait')}")
        if kind == "arena":
            check(m4 == "pass" and s4.get("reason") == "hold_mated" and w4 is None,
                  "arena: partner on turn, timer spent: hold (our team's flip wakes us at lead 0)",
                  f"{m4} wake={w4} hold={s4.get('hold')} declined={s4.get('hold_declined')}")
        else:
            check(m4 != "pass" and s4.get("hold_declined") == "no_wake",
                  "other: partner on turn, timer spent, no flip ahead: no hold, moves",
                  f"{m4} declined={s4.get('hold_declined')} lead={l4}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=str(ROOT / "bin/hypebeast-chance13"))
    ap.add_argument("--nodes", type=int, default=4_500_000)
    args = ap.parse_args()
    item = next(i for i in json.loads((ROOT / "openings/hold_set.json").read_text())
                if i["kind"] == "hold" and i["game"] == 10 and i["idx"] == 40)
    opts = {"HBHoldWhenMated": "true", "HBHoldRace": "250"}
    board = 0 if item["seat"][0] == "A" else 1
    diagonal = item["clocks"][1]          # A-black: same colour on the partner board

    def go(e: Engine, ours: int) -> tuple[str, dict, list[str]]:
        clocks = list(item["clocks"])
        clocks[3] = ours                  # B-black
        e.setoption("Clocks", ",".join(map(str, clocks)))
        e.setoption("TimeAdvantage", "true" if ours > diagonal else "false")
        e.send("position startpos moves " + " ".join(item["prefix"]))
        lines = e.go(f"go nodes {args.nodes}", timeout=120 + args.nodes / 20_000)
        return parse_bestmove(lines)[board], summary(lines), lines

    def start(e: Engine) -> None:
        e.setoption("Seat", item["seat"])
        e.setoption("Team", item["team"])

    e = Engine(Path(args.bin), options=opts)
    try:
        start(e)
        move, s, lines = go(e, diagonal + 16296)
        wake = next((l.split("=")[1] for l in lines if l.startswith("info string hb_wake_after_ms=")), None)
        check(move == "pass" and s.get("reason") == "hold_mated", "lead 16.3 s: hold",
              f"{move} reason={s.get('reason')} hold={s.get('hold')}")
        check(wake is None, "diagonal seat on turn: no timer spent", f"wake={wake}")
        move, s, _ = go(e, diagonal + 14000)
        check(move == "pass" and s.get("wait") == "hold_continue", "lead 14.0 s, nothing moved: hold continues",
              f"{move} wait={s.get('wait')}")
        move, s, _ = go(e, diagonal + 11296)
        check(move != "pass" and s.get("hold_end") == "race_lead" and s.get("hold_declined") == "race_lead",
              "lead 11.3 s: hold ends, searched again, moves",
              f"{move} hold_end={s.get('hold_end')} declined={s.get('hold_declined')}")
    finally:
        e.close()
    e = Engine(Path(args.bin), options=opts)
    try:
        start(e)
        move, s, _ = go(e, item["clocks"][3])
        check(move != "pass" and s.get("hold_declined") == "race_lead", "logged clocks (lead 1.8 s): no hold",
              f"{move} declined={s.get('hold_declined')}")
    finally:
        e.close()
    board_b_turn(args, item, opts)
    print("RESULT", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
