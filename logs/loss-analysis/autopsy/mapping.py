#!/usr/bin/env python3
"""Which planned partner message could have reached each lost game in time, by first-cause class.
alarm: the mated seat's worlds marked the fatal piece '#' at its last decision before the partner's decision.
worth: they said >= 300 cp (not a mate) then.
plan+alarm: neither, but the partner's previous decision had the capture in its line with matching moves.
supply: a missed supply (+T=# half of alarm).
none: nothing of the above."""
import collections, json, os, re, subprocess, sys
from common import HERE
def parse(path, keys):
    out = {}
    for line in open(path):
        for k in keys:
            if line.startswith(k + ":"):
                out[k] = set(eval(line.split("  ", 1)[1].strip()))
    return out
B = parse(os.path.join(HERE, "bounds.txt"), ["alarm in time", "worth >= 300 in time (not a mate)", "piece in no world of the seat before the partner's decision"])
plan = set()
for line in open(os.path.join(HERE, "plan_prev.txt")):
    if line.startswith("previous decision's line had it, moves matching"):
        plan = {(a, b) for a, b, _, _ in eval(line.split(" ", 7)[7].split(" ", 1)[1])}
C = json.load(open(os.path.join(HERE, "classes.json")))
T = {(r["match"], r["game"]): r for r in json.load(open(os.path.join(HERE, "timeline.json")))}
tab = collections.defaultdict(collections.Counter)
for c in C:
    g = (c["match"][:7], c["game"])
    t = T[(c["match"], c["game"])]
    if g in B["alarm in time"]:
        k = "alarm"
    elif g in B["worth >= 300 in time (not a mate)"]:
        k = "worth"
    elif g in plan:
        k = "plan+alarm"
    elif any(x.get("legal") and not x.get("made") for x in t["missed"]):
        k = "supply"
    else:
        k = "none"
    tab[c["cls"]][k] += 1
cols = ["alarm", "worth", "plan+alarm", "supply", "none"]
print("| class | " + " | ".join(cols) + " | total |")
print("|---|" + "---|" * (len(cols) + 1))
tot = collections.Counter()
for cls in sorted(tab, key=lambda k: -sum(tab[k].values())):
    print(f"| {cls} | " + " | ".join(str(tab[cls][k]) for k in cols) + f" | {sum(tab[cls].values())} |")
    tot.update(tab[cls])
print("| all | " + " | ".join(str(tot[k]) for k in cols) + f" | {sum(tot.values())} |")
