#!/usr/bin/env python3
"""show.py MATCH GAME [from_n]: rows of all four seats and events from token from_n, for reading one game."""
import sys
from common import load, MATE
m, gno = sys.argv[1], int(sys.argv[2])
lo = int(sys.argv[3]) if len(sys.argv) > 3 else 0
d = load()[m]
g = next(g for g in d["games"] if g["game"] == gno)
print("seats", g["seats"], "winner", g["winner"], g["termination"], "cand team", g["cand_team"])
rows = sorted([r for r in d["rows"] if r["game"] == gno and r["n"] >= lo], key=lambda r: (r["n"], r["t"]))
mi = 0
def f(s):
    return "?" if s is None else ("M-%d" % (100000 + s) if s <= -MATE else "M+%d" % (100000 - s) if s >= MATE else str(s))
moves = [(i, t, g["times"][i]) for i, t in enumerate(g["toks"]) if i >= lo]
ev = [e for e in g["events"] if e["kind"] in ("sit", "wake", "flag", "end")]
items = [("row", r["t"], r["n"], r) for r in rows] + [("mv", tm, i, t) for i, t, tm in moves] + [("ev", e["t"], -1, e) for e in ev if e["t"] >= (g["times"][lo] if lo < len(g["times"]) else 0)]
items.sort(key=lambda x: (x[1], 0 if x[0] == "row" else 1))
for kind, t, n, x in items:
    if kind == "mv":
        cap = [c for c in g["caps"] if c[0] == n]
        print(f"  t={t:>6} MOVE #{n} {x}" + (f"  captures {cap[0][3]}" if cap else ""))
    elif kind == "ev":
        print(f"  t={t:>6} EVENT {x['kind']} {x.get('seat')} clocks={x['clocks']} eval={x.get('eval')} wake_at={x.get('wake_at')}")
    else:
        r = x
        ws = " ".join(f"{w['arrival']}:{w['p']:.2f}:{f(w['v_chosen'])}/{f(w['v_best'])}" for w in r["worlds"])
        print(f"  t={t:>6} DEC {r['engine']:9} {r['seat']:6} n={r['n']} sc={f(r['score'])} dec={r['decision']} main={r['main']} {r['reason']} E={r['E_chosen']} clk={r['clocks']} adv={r['tadv']} | {ws} | pv={' '.join(r['pvfull'][:6])}")
