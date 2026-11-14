#!/usr/bin/env python3
"""Markdown table: one row per lost game, the timeline facts of both seats of the losing team."""
import json, os
from common import HERE, MATE
T = {(r["match"], r["game"]): r for r in json.load(open(os.path.join(HERE, "timeline.json")))}
C = json.load(open(os.path.join(HERE, "classes.json")))
X = {(x["match"], x["game"]): x for x in json.load(open(os.path.join(HERE, "detail.json")))}
def f(s):
    if s is None: return "?"
    if s <= -MATE: return "M-"
    if s >= MATE: return "M+"
    return str(s)
print("| match | game | class | mated seat | its fall (n: score before -> after) | mate seen at n | piece to opponent in that step (world p; move's value there) | partner's decision before the capture | partner lost at n | team mate first at n | end |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for c in sorted(C, key=lambda c: (c["match"] != "worlds5-vs-l50", c["game"])):
    t = T[(c["match"], c["game"])]; x = X[(c["match"], c["game"])]
    S, P = t["S"], t["P"]; s = t[S]
    fp = c.get("fatal")
    piece = "none"
    if fp:
        piece = f"{fp['k']} ({fp.get('world_p') if fp.get('world_p') is not None else 0:.2f}; {f(fp.get('v_chosen'))})"
    pv = (fp or {}).get("partner") or {}
    pdesc = f"{pv.get('known')}, score {f(pv.get('score'))}" if pv else "-"
    end = t["termination"] + (f", S clock {t['clocks_end'][['Awhite','Ablack','Bwhite','Bblack'].index(S)]} ms")
    print(f"| {c['match'][:7]} | {c['game']} | {c['cls']} | {S} | {s.get('bad_n')}: {f(s.get('pre_bad_score'))} -> {f(s.get('bad_score'))} | {s.get('mate_n') or '-'} | {piece} | {pdesc} | {t[P].get('bad_n') or '-'} | {t.get('own_first_mate_n') or '-'} | {end} |")
