#!/usr/bin/env python3
"""Print one decision in full: show2.py MATCH GAME SEAT N  (worlds with values of main and played, told line, pv)"""
import sys
from common2 import by_seat, fm, load
m, g, seat, n = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
d = load(m)
rs = by_seat(d["rows"])[(g, seat)]
for r in rs:
    if abs(r["n"] - n) <= 0 or r["n"] == n:
        print(f"{m} g{g} {seat} n={r['n']} t={r['t']} engine={r['engine']} score={fm(r['score'])} depth={r['depth']} main={r['main']} played={r['decision']} reason={r['reason']} talk={r.get('talk')} E main/played {r['E_main']}/{r['E_chosen']}")
        print("  pv:", " ".join((r.get('pvfull') or r['pv'])[:10]))
        print("  told:", r.get("told"))
        co = r.get("coord") or {}
        for w in co.get("worlds") or []:
            p = next((x["p"] for x in r["worlds"] if x["arrival"] == w["arrival"]), None)
            print(f"   world {w['arrival']:10} p={p} depth={w['depth']} " + " ".join(f"{k}={fm(v)}" for k, v in w["values"].items()))
        print("  future arrivals (q, key):", [(f[0], f[1]) for f in r["future"]][:6])
        print("  feat:", r["feat"])
