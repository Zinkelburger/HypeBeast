#!/usr/bin/env python3
"""Class c (and every class): the mated seat at its first lost-for-good decision: score, hands, king; plies to the end;
how many pieces reached its opponent from then to the end; what the seat's worlds said."""
import collections, json, os, statistics
from common import HERE, MATE, load
data = load()
T = {(r["match"], r["game"]): r for r in json.load(open(os.path.join(HERE, "timeline.json")))}
C = json.load(open(os.path.join(HERE, "classes.json")))
rows = collections.defaultdict(list)
for m in data:
    for r in data[m]["rows"]:
        rows[(m, r["game"], r["seat"])].append(r)
by = collections.defaultdict(list)
for c in C:
    t = T[(c["match"], c["game"])]
    S = t["S"]; s = t[S]
    rs = sorted(rows[(c["match"], c["game"], S)], key=lambda r: (r["n"], r["t"]))
    bad = [r for r in rs if r["n"] >= (s["bad_n"] or 10**9)]
    if not bad:
        continue
    b = bad[0]
    g = next(g for g in data[c["match"]]["games"] if g["game"] == c["game"])
    white = S.endswith("white")
    to_opp = [x for x in g["caps"] if x[0] >= b["n"] and x[1] != ("1" if S[0] == "A" else "2") and x[2] == white]
    rec = {"g": f"{c['match'][:7]} g{c['game']}", "score": b["score"], "plies_to_end": t["plies"] - b["n"],
           "decisions_to_end": len(bad), "hand_opp": b["feat"]["hand_opp"], "hand_own": b["feat"]["hand_own"],
           "krank": b["feat"].get("krank"), "shelter": b["feat"].get("shelter"), "mat_diff": b["feat"]["mat_own"] - b["feat"]["mat_opp"],
           "pieces_to_opp_after": "".join(x[3] for x in to_opp), "kind": c["s_kind"],
           "first_score_below_-800": next((r["n"] for r in rs if r["score"] is not None and r["score"] < -800), None)}
    by[c["cls"]].append(rec)
for cls in ("c", "d"):
    L = by[cls]
    print(f"## class {cls}: {len(L)} games")
    for r in L:
        print("  ", r)
    print("   median plies from lost-for-good to the end:", statistics.median(r["plies_to_end"] for r in L),
          "median decisions:", statistics.median(r["decisions_to_end"] for r in L),
          "king off home at that point:", sum(1 for r in L if (r["krank"] or 0) >= 1),
          "median material on boards own-opp:", statistics.median(r["mat_diff"] for r in L),
          "median opp hand:", statistics.median(r["hand_opp"] for r in L), "median own hand:", statistics.median(r["hand_own"] for r in L))
