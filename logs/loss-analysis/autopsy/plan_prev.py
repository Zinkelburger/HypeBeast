#!/usr/bin/env python3
"""For every fall after an arrival (sudden mates and decisive drops): did the partner's PREVIOUS decision (one before
the decision that let the piece go) already have the fatal capture in its main line? If so a 'plan' message from
it would have reached the mated seat in time for that seat's alarm to come back before the partner's next decision."""
import collections, json, os
from common import HERE, load
X = json.load(open(os.path.join(HERE, "detail.json")))
data = load()
rows = collections.defaultdict(list)
for m in data:
    for r in data[m]["rows"]:
        rows[(m, r["game"], r["seat"])].append(r)
P = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
res = collections.Counter(); games = collections.defaultdict(list)
for x in X:
    if "piece" not in x or x["s_kind"] not in ("a", "a2", "a3", "a4", "b", "b2"):
        continue
    pv = x.get("partner") or {}
    if pv.get("n") is None:
        continue
    g = next(g for g in data[x["match"]]["games"] if g["game"] == x["game"])
    prs = [r for r in sorted(rows[(x["match"], x["game"], P[x["S"]])], key=lambda r: (r["n"], r["t"])) if r["n"] < pv["n"] and r["decision"] != "pass"]
    if not prs:
        res["no earlier partner decision"] += 1; continue
    pr = prs[-1]
    board = g["toks"][x["capture_idx"]][0]
    between = [t[1:] for t in g["toks"][pr["n"]:x["capture_idx"]] if t[0] == board]
    line = pr.get("pvfull") or pr["pv"]
    j = len(between)
    if len(line) > j and line[:j] == between and line[j] == x["capture_uci"]:
        k = "previous decision's line had it, moves matching"
    elif x["capture_uci"] in line:
        k = "previous decision's line had that move, other order"
    else:
        k = "not in the previous decision's line"
    res[k] += 1; games[k].append((x["match"][:7], x["game"], x["s_kind"], j))
for k, v in res.items():
    print(k, v, games.get(k, ""))
