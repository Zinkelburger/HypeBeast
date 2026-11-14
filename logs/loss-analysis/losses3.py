#!/usr/bin/env python3
"""Third pass: who saw mate first, the descent before it, and thrown-win timelines.

usage: losses3.py MATCH_DIR GAME [GAME ...]
"""
import collections
import json
import statistics
import sys

from losses import TEAM, bad, cp, good


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


d = sys.argv[1]
want = {int(x) for x in sys.argv[2:]}
rs = [json.loads(l) for l in open(f"{d}/results.jsonl")]
first_lost = collections.Counter()
lead = collections.defaultdict(list)
descent = collections.defaultdict(list)
for r in rs:
    res = r["result"]
    ev = res["events"]
    winner = res["winner"]
    team_of = {s: t for t, ss in TEAM.items() for s in ss}
    # first seat in the game whose evaluation is a forced mate against it, standing to its last decision
    first = None
    for s in r["seats"]:
        dec = [e for e in ev if e.get("seat") == s and e["kind"] in ("move", "sit") and e.get("eval") is not None]
        k = len(dec)
        while k > 0 and bad(dec[k - 1]["eval"]):
            k -= 1
        if k < len(dec) and (first is None or dec[k]["t"] < first[0]):
            first = (dec[k]["t"], s)
    if first:
        eng = r["seats"][first[1]]
        first_lost[(eng, "lost" if team_of[first[1]] != winner else "won")] += 1
    # descent of the losing team's mated seat
    loser = "black" if winner == "white" else "white"
    eng = r["seats"][TEAM[loser][0]]
    moves = [e for e in ev if e["kind"] == "move"]
    if res["termination"] == "checkmate":
        last = moves[-1]
        m = f"{last['board']}-{'black' if last['seat'].endswith('white') else 'white'}"
        dec = [e for e in ev if e.get("seat") == m and e["kind"] in ("move", "sit") and e.get("eval") is not None]
        ok = [e for e in dec if cp(e["eval"]) >= -100]
        if ok:
            descent[eng].append((res["duration_ms"] - ok[-1]["t"]) / 1000)
print("first seat to stand mated by force, and the game's result for it:")
for k, v in sorted(first_lost.items()):
    print("  ", k, v)
print("seconds before the end of the mated seat's last eval >= -100, median:",
      {k: med(v) for k, v in descent.items()})

for r in rs:
    if r["game"] not in want:
        continue
    res = r["result"]
    print(f"\n##### game {r['game']} winner {res['winner']} {res['termination']} at {res['duration_ms']}ms")
    print("seats", r["seats"])
    ev = res["events"]
    # compress runs of sits: print moves and the first sit of a run per seat
    shown = 0
    last_sit = {}
    for e in ev[-60:]:
        if e["kind"] == "flip":
            continue
        if e["kind"] == "sit":
            if last_sit.get(e["seat"]):
                continue
            last_sit[e["seat"]] = True
        elif e.get("seat"):
            last_sit[e["seat"]] = False
        print(e["t"], e["kind"], e.get("seat"), e.get("uci"), e.get("eval"), e.get("clocks"), e.get("reason") or "", e.get("wake_at") or "")
