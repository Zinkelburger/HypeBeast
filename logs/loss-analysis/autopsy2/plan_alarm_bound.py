#!/usr/bin/env python3
"""Bound for "plan, then alarm/worth" in hb-plan's lost games: at the seat's last decision no later than the partner's
decision that let the fatal piece go, (1) the partner's told line (in the seat's forecast) contained that piece going to
the opponent, and (2) the seat's world with that piece had the move played mated while "none" was not (alarm) or
300+ cp worse than "none" (worth). Also counts (1) alone, and the same test for hb-l50's own forecast lines."""
import collections, json, os
from common2 import MATE, by_seat, fm, load
HERE = os.path.dirname(os.path.abspath(__file__))
d = load("plan-vs-l50")
rbs = by_seat(d["rows"])
L = json.load(open(os.path.join(HERE, "lost_plan-vs-l50.json")))
def has(a, k):
    return k in a.replace("+", " +").replace("-", " -").split()
res = collections.defaultdict(list)
for r in L:
    seat = r["fall_seat"] or r["S"]
    c = r[seat].get("fatal")
    pre = r[seat].get("pre")
    if not c or c["k"][0] != "-" or not pre:
        continue
    pv = c.get("partner") or {}
    pn = pv.get("n")
    if pn is None:
        continue
    xs = [x for x in rbs[(r["game"], seat)] if x["n"] <= min(pn, pre["n"])]
    if not xs:
        continue
    x = xs[-1]
    told = x.get("told") or {}
    in_told = any(cc.endswith(c["k"]) for cc in told.get("caps", []))
    in_lines = any(any(cc.endswith(c["k"]) for cc in l["caps"]) for l in x["lines"])
    none = next((w for w in x["worlds"] if w["arrival"] == "none"), None)
    nv = none["v_chosen"] if none else None
    tag = "no world"
    for w in x["worlds"]:
        if has(w["arrival"], c["k"]) and w["v_chosen"] is not None:
            if w["v_chosen"] <= -MATE and (nv is None or nv > -MATE):
                tag = "alarm"
                break
            if nv is not None and nv > -MATE and nv - max(w["v_chosen"], -100000) >= 300:
                tag = "worth"
            elif tag == "no world":
                tag = "in a world, under 300"
    res[r["loser"]].append((r["game"], r["cls"], c["k"], x["n"], pn, x.get("talk"), in_told, in_lines, tag))
for e, v in res.items():
    print(f"## {e}: {len(v)} falls with a fatal piece and a partner decision before it")
    print("  told line had it:", sum(1 for t in v if t[6]), "| some forecast line had it:", sum(1 for t in v if t[7]))
    print("  message the seat could send then:", dict(collections.Counter(t[8] for t in v)))
    both = [t for t in v if t[6] and t[8] in ("alarm", "worth")]
    print(f"  told line had it AND alarm/worth: {len(both)}: games {[t[0] for t in both]}")
    lines = [t for t in v if t[7] and t[8] in ("alarm", "worth")]
    print(f"  some forecast line had it AND alarm/worth: {len(lines)}: games {[t[0] for t in lines]}")
    for t in v:
        print("   ", t)
