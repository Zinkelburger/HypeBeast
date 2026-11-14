#!/usr/bin/env python3
"""Upper bounds for the suggestions: how many lost games had the property at the turning point (the falling seat's pre)."""
import collections, json, os
from common2 import MATE, PARTNER, by_seat, load
HERE = os.path.dirname(os.path.abspath(__file__))
d = load("plan-vs-l50")
rbs = by_seat(d["rows"])
L = json.load(open(os.path.join(HERE, "lost_plan-vs-l50.json")))
for e in ("hb-l50", "hb-plan"):
    sets = collections.defaultdict(list)
    for r in L:
        if r["loser"] != e:
            continue
        seat = r["fall_seat"] or r["S"]
        pre = r[seat].get("pre")
        if not pre:
            sets["no pre decision"].append(r["game"])
            continue
        f = pre["feat"]
        if f.get("kzone_att", 0) >= 3:
            sets["kzone 3+ attacked at TP"].append(r["game"])
        if f.get("krank", 0) >= 1:
            sets["king off home rank at TP"].append(r["game"])
        if f.get("kzone_att", 0) >= 3 or f.get("krank", 0) >= 1 or f.get("in_check"):
            sets["any king-danger flag at TP (kzone 3+, off home rank, in check)"].append(r["game"])
        prs = [x for x in rbs[(r["game"], PARTNER[seat])] if x["n"] <= pre["n"] and x["score"] is not None]
        ps = prs[-1]["score"] if prs else None
        if ps is not None and ps < -300:
            sets["partner behind (< -300) at TP"].append(r["game"])
        if ps is not None and ps > 300:
            sets["partner ahead (> 300) at TP"].append(r["game"])
        if pre["override"] and pre["decision"] != "pass":
            sets["TP was a switch"].append(r["game"])
            if pre.get("talk") == "plan":
                sets["TP was a switch under talk=plan"].append(r["game"])
        if pre["decision"] == "pass" and pre["reason"] == "stall_deny":
            sets["TP was a stall_deny sit"].append(r["game"])
        if pre["feat"].get("other_partner_to_move") is False:
            sets["partner NOT to move on the other board at TP"].append(r["game"])
        if pre.get("score") is not None and pre["score"] > 0:
            sets["TP score > 0"].append(r["game"])
    stall = sorted({x["game"] for x in d["rows"] if x["engine"] == e and x["reason"] == "stall_deny" and x["won"] == 0})
    sets["lost games with any stall_deny sit"] = stall
    print(f"## {e}: {sum(1 for r in L if r['loser'] == e)} lost")
    for k, v in sets.items():
        print(f"  {k}: {len(v)}  {sorted(v)}")
