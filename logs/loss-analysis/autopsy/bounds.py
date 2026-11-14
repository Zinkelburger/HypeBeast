#!/usr/bin/env python3
"""Game sets behind each suggestion's upper bound (from detail.json, classes.json, timeline.json)."""
import collections, json, os
from common import HERE, MATE, load
from detail import key_has
X = json.load(open(os.path.join(HERE, "detail.json")))
C = {(c["match"], c["game"]): c for c in json.load(open(os.path.join(HERE, "classes.json")))}
data = load()
rows = collections.defaultdict(list)
for m in data:
    for r in data[m]["rows"]:
        rows[(m, r["game"], r["seat"])].append(r)
sets = collections.defaultdict(set)
plies = collections.Counter()
for x in X:
    if "piece" not in x or x["s_kind"] not in ("a", "a2", "a3", "a4", "b", "b2"):
        continue
    pv = x.get("partner") or {}
    pn = pv.get("n")
    g = (x["match"][:7], x["game"])
    if pn is None:
        continue
    rs = sorted(rows[(x["match"], x["game"], x["S"])], key=lambda r: (r["n"], r["t"]))
    before = [r for r in rs if r["n"] <= pn]
    told = None
    if before:
        r = before[-1]
        ws = [w for w in r["worlds"] if key_has(w["arrival"], x["piece"])]
        none = next((w for w in r["worlds"] if w["arrival"] == "none"), None)
        if ws:
            w = min(ws, key=lambda w: w["v_chosen"] if w["v_chosen"] is not None else 10 ** 6)
            told = (w["v_chosen"], none["v_chosen"] if none else None)
    known = pv.get("known")
    if told and told[0] is not None and told[0] <= -MATE and (told[1] is None or told[1] > -MATE):
        sets["alarm in time"].add(g)
        if known in ("in its line", "in its line later/elsewhere"):
            sets["alarm in time, partner's own line had the capture"].add(g)
    elif told and told[0] is not None and told[1] is not None and told[1] - told[0] >= 300:
        sets["worth >= 300 in time (not a mate)"].add(g)
    elif told is None:
        sets["piece in no world of the seat before the partner's decision"].add(g)
        if known in ("in its line", "in its line later/elsewhere"):
            sets["... and the partner's own line had the capture (plan message)"].add(g)
            plies[pv.get("plies_after")] += 1
    if x["s_kind"] in ("a", "a2", "a3", "b") and (pv.get("score") or 0) > 300:
        sets["sudden mate while the partner was ahead (> 300)"].add(g)
for k, c in C.items():
    sets["class " + c["cls"]].add((k[0][:7], k[1]))
for k, v in sets.items():
    print(f"{k}: {len(v)}  {sorted(v)}")
print("plies of the partner's board between its decision and the capture, for the 'plan message' set:", dict(plies))
