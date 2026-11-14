#!/usr/bin/env python3
"""accounts.py MATCH GAME SEAT: the seat's step into lost-for-good, its partner's decision before the capture,
the next decisions, and the move-list prefix up to the seat's decision (arena format: board digit + uci)."""
import json, os, sys
from common import HERE, MATE, PARTNER, load
m, gno, seat = sys.argv[1], int(sys.argv[2]), sys.argv[3]
T = {(r["match"], r["game"]): r for r in json.load(open(os.path.join(HERE, "timeline.json")))}
t = T[(m, gno)]
d = load()[m]
g = next(g for g in d["games"] if g["game"] == gno)
rows = sorted([r for r in d["rows"] if r["game"] == gno], key=lambda r: (r["n"], r["t"]))
def f(s):
    return "?" if s is None else (f"M-{100000 + s}" if s <= -MATE else f"M+{100000 - s}" if s >= MATE else str(s))
info = t[seat]
bad_n = info["bad_n"]
mine = [r for r in rows if r["seat"] == seat]
pre = [r for r in mine if r["n"] < bad_n][-1]
print(f"{m} game {gno} {seat} ({g['seats'][seat[0] + '-' + seat[1:]]}), team {t['team']} lost by {t['termination']}; mated seat {t['S']}; plies {t['plies']}")
print(f"lost for good from n={bad_n}; first mate seen n={info['mate_n']}")
def show(r, tag):
    ws = "; ".join(f"{w['arrival']} p={w['p']:.2f} chosen={f(w['v_chosen'])} best={f(w['v_best'])}" for w in r["worlds"])
    print(f"  {tag} {r['seat']} n={r['n']} t={r['t']/1000:.1f}s score={f(r['score'])} depth={r['depth']} played={r['decision']} main={r['main']} reason={r['reason']} "
          f"E={r['E_chosen']} clocks={r['clocks']} pv={' '.join(r['pvfull'][:8])}\n      worlds: {ws}")
show(pre, "DECISION")
for c in info.get("arrivals_into_bad", []):
    print(f"  then token #{c['idx']} {g['toks'][c['idx']]} gives {c['k']} (world p {c.get('world_p')}, chosen move there {f(c.get('v_chosen'))})")
    if c["k"][0] == "-":
        pr = [r for r in rows if r["seat"] == PARTNER[seat] and r["n"] <= c["idx"]]
        if pr:
            show(pr[-1], "PARTNER")
nx = [r for r in mine if r["n"] >= bad_n][:3]
for r in nx:
    show(r, "NEXT")
print(f"  game end: winner {g['winner']}, clocks {g['clocks_end']}")
print("PREFIX (" + str(pre["n"]) + " tokens): " + " ".join(g["toks"][:pre["n"]]))
