#!/usr/bin/env python3
"""Split a match's results by how the games ended, and say what a flag meant.

    python3 tests/flag_report.py MATCH_DIR [MATCH_DIR ...] [--bar 300]

The arena clock is virtual: every move costs the same seeded 1.5-2.5 s for
both sides whatever the search took, so a clock only runs out when a seat
sits. A flag is therefore not a win on thinking speed. This report reads
results.jsonl and, for every flagged game, takes the last evaluation each
team reported before the flag (centipawns, from that team's point of view)
and puts the game in one of four classes:

  agreed-lost   both teams' last evals say the flagged team was losing by
                at least --bar cp (the flag ended a game that was decided)
  agreed-won    both say the flagged team was winning by at least --bar
                (the flag reversed the board result)
  one-sided     only one team's eval passes the bar, the other is inside it
  unclear       neither passes the bar, or they disagree in sign

It then prints the contender's score three ways: as the arena counts it,
with flags left out, and with only agreed-lost flags kept as wins/losses.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path


def team_of(seat: str) -> str:
    board, colour = seat.split("-")
    return colour if board == "A" else ("black" if colour == "white" else "white")


def last_evals(events: list[dict]) -> dict[str, int | None]:
    """Last reported cp per team (own point of view), from moves only: a sit
    after a refused search carries no evaluation."""
    out: dict[str, int | None] = {"white": None, "black": None}
    for e in events:
        if e.get("kind") != "move" or not e.get("seat"):
            continue
        ev = e.get("eval") or {}
        if "mate" in ev and ev["mate"] is not None:
            cp = 100000 if ev["mate"] > 0 else -100000
        elif "cp" in ev and ev["cp"] is not None:
            cp = ev["cp"]
        else:
            continue
        out[team_of(e["seat"])] = cp
    return out


def classify(flagged: str, evals: dict[str, int | None], bar: int) -> str:
    other = "black" if flagged == "white" else "white"
    mine, theirs = evals[flagged], evals[other]
    # Both as "how the flagged team stands": its own eval, and minus the other's.
    views = [v for v in (mine, -theirs if theirs is not None else None) if v is not None]
    if not views:
        return "unclear"
    lost = [v <= -bar for v in views]
    won = [v >= bar for v in views]
    if len(views) == 2 and all(lost):
        return "agreed-lost"
    if len(views) == 2 and all(won):
        return "agreed-won"
    if (any(lost) and not any(won)) or (any(won) and not any(lost)):
        return "one-sided"
    return "unclear"


def wilson(points: float, n: int) -> str:
    if not n:
        return "no games"
    p, z = points / n, 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{points:g}/{n} = {100 * p:.1f}% (95% {100 * (centre - half):.1f} to {100 * (centre + half):.1f}, games as the unit)"


def report(match: Path, bar: int) -> None:
    games = [json.loads(line) for line in (match / "results.jsonl").read_text().splitlines() if line.strip()]
    games = [g for g in games if not g["result"].get("error")]
    print(f"== {match.name}: {len(games)} games, contender {games[0]['contender']} vs {games[0]['baseline']}")
    terms = Counter(g["result"]["termination"] for g in games)
    print("  terminations", dict(terms))
    all_pts = sum(g["contender_score"] for g in games)
    board = [g for g in games if g["result"]["termination"] != "flag"]
    classes: Counter = Counter()
    kept = list(board)
    for g in games:
        r = g["result"]
        if r["termination"] != "flag":
            continue
        flagged = "black" if r["winner"] == "white" else "white"
        evals = last_evals(r["events"])
        cls = classify(flagged, evals, bar)
        who = "contender" if g["contender_team"] == flagged else "baseline"
        classes[(who, cls)] += 1
        sits = r.get("sit_ms", {}).get(flagged, 0)
        print(f"  game {g['game']:>3}: {who} flagged; its eval {evals[flagged]}, "
              f"opponent's eval {evals['black' if flagged == 'white' else 'white']}, "
              f"sat {sits / 1000:.0f} s -> {cls}")
        if cls == "agreed-lost":
            kept.append(g)
    for (who, cls), n in sorted(classes.items()):
        print(f"  flags: {who} {cls}: {n}")
    print("  as counted        ", wilson(all_pts, len(games)))
    print("  flags left out    ", wilson(sum(g["contender_score"] for g in board), len(board)))
    print("  + agreed-lost flags", wilson(sum(g["contender_score"] for g in kept), len(kept)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("match", nargs="+", type=Path)
    ap.add_argument("--bar", type=int, default=300, help="cp both evals must pass (default 300)")
    args = ap.parse_args()
    for match in args.match:
        report(match, args.bar)


if __name__ == "__main__":
    main()
