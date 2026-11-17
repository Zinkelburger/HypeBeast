#!/usr/bin/env python3
"""A fixed test set of decisive feeding mistakes: does the engine still hand
the opponent the piece that mates our partner?

Each item (openings/feed_set.json) is one decision from a lost game against
HiveMind (1500 nodes): the full move list before it, the seat, team, clocks
and time advantage as logged, and the move that was played and fed the
mating attack on the other board. A binary passes an item when it plays any
other move (sitting counts as passing and is reported).

  feed_set.py run [openings/feed_set.json] --bin PATH [--nodes 4500000]
              [--workers 2] [--option K=V ...] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from hbutil import ROOT, Engine, parse_bestmove

DEFAULT = ROOT / "openings/feed_set.json"


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
    prices = next((json.loads(l[len("info string hb_prices "):]) for l in lines
                   if l.startswith("info string hb_prices ")), None)
    verdict = "sat" if move == "pass" else "fed" if move == item["feed"] else "declined"
    return {"game": item["game"], "idx": item["idx"], "seat": item["seat"], "feed": item["feed"],
            "move": move, "reason": reason, "verdict": verdict,
            "theirs": prices.get("theirs") if prices else None, "base": prices.get("base") if prices else None}


def run(args) -> int:
    items = json.loads(Path(args.items).read_text())
    options = dict(o.split("=", 1) for o in args.option)
    jobs = [(i, str(Path(args.bin).resolve()), args.nodes, options) for i in items]
    with ProcessPoolExecutor(args.workers) as pool:
        rows = list(pool.map(run_item, jobs))
    counts: dict = {}
    for item, row in zip(items, rows):
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        if args.verbose:
            print(f"  {item['source'][:24]:24} game {row['game']:3} idx {row['idx']:3} {row['seat']:6} "
                  f"feed {row['feed']:6} -> {row['move']:6} {row['verdict']:8} ({row['reason']}) "
                  f"base={row['base']} theirs={row['theirs']}")
    passed = counts.get("declined", 0) + counts.get("sat", 0)
    print(f"{Path(args.bin).name} nodes={args.nodes} {options or ''}: {passed}/{len(rows)} declined "
          + "(" + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) + ")")
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
    r.add_argument("--verbose", action="store_true")
    r.set_defaults(fn=run)
    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
