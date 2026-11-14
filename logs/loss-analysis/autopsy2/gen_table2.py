#!/usr/bin/env python3
"""Markdown table of every lost game (both sides) from lost_<MATCH>.json and q3_<MATCH>.json, plus clock and
turning-point summaries.   nice -n 19 python3 gen_table2.py [MATCH] > table_<MATCH>.md"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from common2 import SEATS, fm  # noqa: E402

MATCH = sys.argv[1] if len(sys.argv) > 1 else "plan-vs-l50"
L = json.load(open(os.path.join(HERE, f"lost_{MATCH}.json")))
Q = {x["game"]: x for x in json.load(open(os.path.join(HERE, f"q3_{MATCH}.json")))}

print("| loser | game | class | turning point | fall: score before -> after (n) | piece to opponent (world p; move's value there) | partner's decision before the capture | who could see it | clocks at the turning point (seat / its opponent, s) | end |")
print("|---|---|---|---|---|---|---|---|---|---|")
clk = collections.defaultdict(list)
for r in sorted(L, key=lambda r: (r["loser"], r["game"])):
    q = Q.get(r["game"], {})
    seat = r["fall_seat"] or r["S"]
    s = r[seat]
    pre = s.get("pre") or {}
    c = s.get("fatal")
    piece = f"{c['k']} ({c.get('world_p', 0):.2f}; {fm(c.get('v_chosen'))})" if c else "none"
    pv = (c or {}).get("partner") or {}
    part = f"{pv.get('known')}, score {fm(pv.get('score'))}" if pv else "-"
    cl = pre.get("clocks")
    if cl:
        i = SEATS.index(seat)
        ct = f"{cl[i] / 1000:.0f} / {cl[i ^ 1] / 1000:.0f}"
        clk[r["loser"]].append((cl[i] - cl[i ^ 1]) / 1000)
    else:
        ct = "-"
    tp = r["tp"] or {}
    cls = r["cls"] + (f"/{r['sub']}" if r["cls"] == "d" else "")
    play = pre.get("decision", "")
    if pre.get("override"):
        play += f" (main {pre.get('main')}, {pre.get('reason')})"
    elif play == "pass":
        play += f" ({pre.get('reason')})"
    end = r["termination"]
    print(f"| {r['loser']} | {r['game']} | {cls} | {tp.get('seat')} n={tp.get('n')} {play} | {fm(s.get('pre_bad_score'))} -> {fm(s.get('bad_score'))} ({s.get('bad_n')}) | "
          f"{piece} | {part} | {q.get('who', '-')} | {ct} | {end} |")
print()
for e, v in clk.items():
    v.sort()
    print(f"{e}: seat clock minus its opponent's at the turning point: median {v[len(v) // 2]:+.1f} s, |diff| > 5 s in {sum(abs(x) > 5 for x in v)} of {len(v)}")

# turning-point decisions against the base rate (the engine's moving decisions at -300 or better)
from common2 import load  # noqa: E402
data = load(MATCH)
for e in sorted({r["loser"] for r in L}):
    tps = [r[r["fall_seat"]]["pre"] for r in L if r["loser"] == e and r["fall_seat"] and r[r["fall_seat"]].get("pre")]
    base = [x for x in data["rows"] if x["engine"] == e and x["score"] is not None and x["score"] >= -300]
    sw = sum(1 for p in tps if p["override"] and p["decision"] != "pass")
    st = sum(1 for p in tps if p["decision"] == "pass")
    bsw = sum(1 for x in base if x["override"] and x["decision"] != "pass")
    bst = sum(1 for x in base if x["decision"] == "pass")
    print(f"{e}: turning points {len(tps)}: switched {sw}, sat {st}; base rate at >= -300: switched {bsw}/{len(base)} = {bsw / len(base):.3f}, sat {bst / len(base):.3f}")
    if e == "hb-plan":
        print("   talk at the turning point:", dict(collections.Counter(p.get("talk") for p in tps)),
              " base:", dict(collections.Counter(x.get("talk") for x in base)))
