#!/usr/bin/env python3
"""Sitting in the lost games and in all games: what sits came before the mated seat's fall, and how the
team fared after the candidate's seats sat for each reason (all games of both matches)."""
import collections, json, os
from common import load, HERE, MATE, team_seats
data = load()
T = {(r["match"], r["game"]): r for r in json.load(open(os.path.join(HERE, "timeline.json")))}
pre = collections.Counter(); pre_games = collections.defaultdict(set)
for (m, g), t in T.items():
    for seat in team_seats(t["team"]):
        bad = t[t["S"]]["bad_n"]
        for r in data[m]["rows"]:
            if r["game"] == g and r["seat"] == seat and r["decision"] == "pass" and bad is not None and r["n"] < bad:
                pre[(seat == t["S"], r["reason"])] += 1; pre_games[(seat == t["S"], r["reason"])].add((m[:7], g))
print("sits by the losing team before the mated seat's fall: (is mated seat, reason): decisions, games")
for k, v in pre.most_common():
    print("  ", k, v, sorted(pre_games[k]))
print("\nall games, candidate seats: games in which a seat sat for this reason at least once, and the team's score")
for m, d in data.items():
    res = collections.defaultdict(dict)
    for r in d["rows"]:
        if r["engine"] == d["cand"] and r["decision"] == "pass":
            res[r["reason"]][(r["game"], r["seat"])] = r["won"]
    for why, gs in sorted(res.items(), key=lambda kv: -len(kv[1])):
        print(f"  {m[:7]} {why:15} seat-games {len(gs):3} team won {sum(gs.values()):.1f} ({100*sum(gs.values())/len(gs):.0f}%)")
# first sight of a forced mate against a candidate seat, then hold_mated vs played on: team result
print("\ncandidate seats that saw a forced mate against themselves: what the seat did at that first sight, team result")
for m, d in data.items():
    first = {}
    for r in sorted(d["rows"], key=lambda r: (r["game"], r["n"], r["t"])):
        if r["engine"] == d["cand"] and r["score"] is not None and r["score"] <= -MATE and (r["game"], r["seat"]) not in first:
            first[(r["game"], r["seat"])] = r
    c = collections.defaultdict(list)
    for r in first.values():
        c["sat" if r["decision"] == "pass" else "moved"].append(r["won"])
    for k, v in c.items():
        print(f"  {m[:7]} {k}: {len(v)} seat-games, team won {sum(v):.1f}")
