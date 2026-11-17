#!/usr/bin/env python3
"""Positions from the games v5 lost to HiveMind at 5000 nodes
(logs/c6all-vs-hm-n5000), for the round-8 coordinator rules.

openings/hold_set.json, one decision each, with the moves, seat, team,
clocks and time advantage as logged:

  hold    every move is mated on our board while the partner is winning:
          pass = the engine sits (HBHoldWhenMated). With HBHoldRace on (the default), game
          10 idx 40 moves by design: its partner's mate in 5 needs 12.75 s
          of lead over the diagonal seat and there are 1.8 s.
  feed    two near-equal moves, one hands over a dearer piece:
          pass = the engine does not play `avoid` (HBFeedTieBreak)
  castle  castling into HiveMind's pawn-drop storm:
          pass = the engine does not castle here. Kept as positions only:
          the rule they were collected for, a root penalty on castling,
          showed nothing in play and is gone (docs/REJECTED.md), so they
          are not in the default --kind

openings/hold_race_set.json, the first hold of every game HypeBeast lost on
its flag with HBHoldWhenMated against HiveMind at 1500 nodes
(logs/c8hold-vs-hm-n1500, logs/c9hold-fix-vs-hm-n1500). The one hold there
that won (c9 game 25) is left out: a fresh process does not find the mate
the match process found (main -2598 at 4.5M nodes), so it never reaches the
race test.

  race    expect "move": the hold cannot win the clock race against the
          diagonal seat (no forced mate for our partner that our lead
          covers), so the engine plays on; expect "pass": mated in 1 (a free
          hold). These are the defaults (HBHoldWhenMated, HBHoldRace=250);
          with HBHoldRace=0 the "move" items fail (the old rule sits in all 14).
          Then the last hold before each of the 14 flags (notes "LAST
          HOLD"): every one has the diagonal seat on turn, up on time, and
          our lead below zero, so expect "move" in all 14, the four mated-in-1
          holds among them too (c8 18, c9 7, 8, 21: a free hold sits with the
          lead gone only while our partner is on turn).

  hold_set.py run [openings/hold_set.json] --bin PATH [--nodes 4500000]
              [--workers 2] [--option K=V ...] [--kind hold,feed,race,castle] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from hbutil import ROOT, Engine, parse_bestmove

DEFAULT = ROOT / "openings/hold_set.json"


def run_item(job) -> dict:
    item, binary, nodes, options = job
    engine = Engine(Path(binary), options=options)
    try:
        engine.setoption("Seat", item["seat"])
        engine.setoption("Team", item["team"])
        engine.setoption("Clocks", ",".join(map(str, item["clocks"])))
        engine.setoption("TimeAdvantage", "true" if item["advantage"] else "false")
        engine.send("position startpos moves " + " ".join(item["prefix"]))
        lines = engine.go(f"go nodes {nodes}", timeout=120 + nodes / 20_000)
    finally:
        engine.close()
    board = 0 if item["seat"][0] == "A" else 1
    move = parse_bestmove(lines)[board]
    reason = next((l.split("reason=")[1].split()[0] for l in lines
                   if l.startswith("info string hb_summary ") and " reason=" in l), "?")
    detail = next((l.split(key, 1)[1].split('"', 1)[0] for l in lines for key in ('"hold":"', '"hold_declined":"')
                   if l.startswith("info string hb_coord ") and key in l), "")
    if item["expect"] == "pass":
        ok = move == "pass"
    elif item["expect"] == "move":
        ok = move != "pass"
    else:
        ok = move != item["avoid"]
    return {"move": move, "reason": reason, "ok": ok, "detail": detail}


def run(args) -> int:
    kinds = set(args.kind.split(","))
    items = [i for i in json.loads(Path(args.items).read_text()) if i["kind"] in kinds]
    options = dict(o.split("=", 1) for o in args.option)
    jobs = [(i, str(Path(args.bin).resolve()), args.nodes, options) for i in items]
    with ProcessPoolExecutor(args.workers) as pool:
        rows = list(pool.map(run_item, jobs))
    score: dict = {}
    for item, row in zip(items, rows):
        n, p = score.get(item["kind"], (0, 0))
        score[item["kind"]] = (n + 1, p + row["ok"])
        if args.verbose:
            want = {"pass": "sit", "move": "move"}.get(item["expect"], f"not {item['avoid']}")
            print(f"  {item['kind']:6} game {item['game']:3} idx {item['idx']:3} {item['seat']:6} want {want:12} "
                  f"-> {row['move']:6} {'ok' if row['ok'] else 'FAIL':4} ({row['reason']}) logged {item['logged_move']}"
                  + (f"\n         {row['detail']}" if row["detail"] else ""))
    print(f"{Path(args.bin).name} nodes={args.nodes} {options or ''}: "
          + ", ".join(f"{k} {p}/{n}" for k, (n, p) in sorted(score.items())))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("items", nargs="?", default=str(DEFAULT))
    r.add_argument("--bin", required=True)
    r.add_argument("--nodes", type=int, default=4_500_000)
    r.add_argument("--workers", type=int, default=2)
    r.add_argument("--option", action="append", default=[])
    r.add_argument("--kind", default="hold,feed,race")
    r.add_argument("--verbose", action="store_true")
    r.set_defaults(fn=run)
    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
