#!/usr/bin/env python3
"""AUTOPSY3 tables from falls_<tag>.json -> report3_<tag>.md and classes_<tag>.txt (game lists per class).
    nice -n 19 python3 report3.py [falls_l50.json]"""
import collections
import json
import os
import random
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else "falls_l50.json"
R = json.load(open(os.path.join(HERE, src)))
tag = src[len("falls_"):-len(".json")]
F = [r for r in R if r["cls"] != "none"]
ORDER = ["A1", "A2", "A3", "A4", "A5", "C1", "C2", "C3", "C4", "C5", "G", "H", "S", "O"]
NAME = {
    "A1": "arrival in no world", "A2": "arrival; the move played not scored in its world",
    "A3": "arrival; its world had the move played holding", "A4": "arrival; another candidate held in its world",
    "A5": "arrival; every candidate fell in its world", "C1": "own board: a forced mate appeared",
    "C2": "own board: the reply K's line expected", "C3": "own board: another reply", "C4": "own board: no reply",
    "C5": "own board after a switch (no line for the move played)", "G": "a switch that went wrong",
    "H": "a sit", "S": "slide (no step of 200 cp)", "O": "lost from the first decision"}


def med(xs, fmt="{:+.0f}"):
    xs = [x for x in xs if x is not None]
    return fmt.format(st.median(xs)) if xs else "-"


def top(r):
    return max(r["arr_minus"], key="PNBRQ".index) if r.get("arr_minus") else None


out = [f"# AUTOPSY3 tables ({src})", ""]
lost = [r for r in F if r["won"] == 0]
first_lost = [r for r in F if r["won"] == 0 and r["team_first"]]
out.append(f"Seats: {len(R)}; falls: {len(F)} ({sum(r['won'] == 0 for r in F)} on teams that lost, "
           f"{sum(r['won'] == 1 for r in F)} on teams that won, {sum(r['won'] == 0.5 for r in F)} drawn). "
           f"Team's first fall in lost games: {len(first_lost)}. Seats that never fell: {len(R) - len(F)}.")
out.append("")
out.append("## Classes")
out.append("")
out.append("| class | all falls | team lost | team's first fall, lost | key step: score at K → at N (medians) | N a forced mate |")
out.append("|---|---|---|---|---|---|")
for k in ORDER:
    s = [r for r in F if r["cls"] == k]
    if not s:
        continue
    out.append(f"| {k} {NAME[k]} | {len(s)} | {sum(r['won'] == 0 for r in s)} | {sum(r['won'] == 0 and r['team_first'] for r in s)} | "
               f"{med([r.get('K_score') for r in s])} → {med([max(r.get('N_score', 0), -100000) if r.get('N_score') is not None else None for r in s])} | "
               f"{sum((r.get('N_score') or 0) <= -90000 for r in s)} |")
out.append("")
# by match
out.append("By match (all falls):")
out.append("")
ms = sorted({r["match"] for r in R}, key=lambda m: [r["match"] for r in R].index(m))
out.append("| class | " + " | ".join(ms) + " |")
out.append("|---|" + "---|" * len(ms))
for k in ORDER:
    s = [r for r in F if r["cls"] == k]
    if s:
        out.append(f"| {k} | " + " | ".join(str(sum(r["match"] == m for r in s)) for m in ms) + " |")
out.append("| seats | " + " | ".join(str(sum(r["match"] == m for r in R)) for m in ms) + " |")
out.append("")
# arrivals detail
A = [r for r in F if r["cls"] in ("A1", "A2", "A3", "A4", "A5")]
out.append("## Arrival falls")
out.append("")
out.append("| class | n | fatal piece Q / R / B / N / P | world p (median) | move played in \"none\" → in its world (median) | "
           "best candidate in its world (median) | candidates compared (median) | seen at 1+ of the 2 decisions before (p>=0.10) |")
out.append("|---|---|---|---|---|---|---|---|")
for k in ("A1", "A2", "A3", "A4", "A5"):
    s = [r for r in A if r["cls"] == k]
    if not s:
        continue
    pc = collections.Counter(top(r) for r in s)
    out.append(f"| {k} | {len(s)} | {' / '.join(str(pc.get(t, 0)) for t in 'QRBNP')} | {med([r.get('world_p') for r in s], '{:.2f}')} | "
               f"{med([r.get('v_none_play') for r in s])} → {med([r.get('v_play') for r in s])} | {med([r.get('v_best') for r in s])} | "
               f"{med([r.get('n_cands') for r in s], '{:.0f}')} | {sum((r.get('seen_before') or 0) >= 1 for r in s)} |")
out.append("")
a1 = [r for r in A if r["cls"] == "A1"]
if a1:
    nw = [r for r in a1 if r["worlds_scored"] == 0]
    ww = [r for r in a1 if r["worlds_scored"] > 0]
    pr = [r for r in ww if ("-" + top(r)) in r.get("K_fc_prices", {})]
    out.append(f"A1 split: no worlds scored at K {len(nw)} (reasons {dict(collections.Counter(r['K_reason'] for r in nw))}; "
               f"one legal move {sum(r['legal'] == 1 for r in nw)}); worlds scored but none held the piece {len(ww)} "
               f"(worlds scored: {dict(collections.Counter(r['worlds_scored'] for r in ww))}); of those, the forecast had measured the "
               f"piece's price (a line held it) {len(pr)}, at 500 or more {sum(r['K_fc_prices']['-' + top(r)] >= 500 for r in pr)}.")
    out.append("")
# early escape (A5)
a5 = [r for r in A if r["cls"] == "A5"]
if a5:
    esc = collections.Counter()
    for r in a5:
        e = [x for x in r.get("early", []) if x]
        if not e:
            esc["no world held the piece at either"] += 1
        elif any(x["v_play"] is not None and x["v_play"] < -300 and x["v_best"] >= -300 for x in e):
            esc["a candidate held (>= -300) where the move played fell"] += 1
        elif any(x["v_play"] is not None and x["v_best"] - max(x["v_play"], -3000) >= 200 for x in e):
            esc["a candidate 200+ cp better, not holding"] += 1
        else:
            esc["no candidate 200 cp better"] += 1
    out.append("A5: the same piece at the seat's two decisions before K (the world holding it with the largest p):")
    out.append("")
    out.append("| at the two decisions before K | n |")
    out.append("|---|---|")
    for k2, v in esc.most_common():
        out.append(f"| {k2} | {v} |")
    out.append("")
# flags
out.append("## Flags at K, by class")
out.append("")
flags = [("in check", lambda r: r.get("in_check")), ("king off home rank", lambda r: r.get("king_off_home")),
         ("3+ king-zone squares attacked", lambda r: (r.get("kzone_att") or 0) >= 3),
         ("partner sat in the step", lambda r: r.get("partner_sat")), ("partner's board below -300", lambda r: r.get("partner_lost")),
         ("K switched", lambda r: r.get("K_override")), ("opponent's hand 6+", lambda r: (r.get("opp_hand") or 0) >= 6),
         ("our hand 6+", lambda r: (r.get("own_hand") or 0) >= 6),
         ("clock 5 s+ behind", lambda r: r.get("clock_gap") is not None and r["clock_gap"] <= -5000)]
out.append("| class | n | " + " | ".join(f for f, _ in flags) + " |")
out.append("|---|---|" + "---|" * len(flags))
for k in ORDER:
    s = [r for r in F if r["cls"] == k and k != "O"]
    if s:
        out.append(f"| {k} | {len(s)} | " + " | ".join(str(sum(bool(fn(r)) for r in s)) for _, fn in flags) + " |")
s = [r for r in F if r["cls"] != "O"]
out.append(f"| all | {len(s)} | " + " | ".join(str(sum(bool(fn(r)) for r in s)) for _, fn in flags) + " |")
out.append("")
# information
out.append("## Information that existed")
out.append("")
out.append("| class | n | its worlds had a move 200+ better in the world that came true | ... and that move cost <= 100 in \"none\" | "
           "partner's own line had the capture | partner had a candidate within 150 cp | fall visible at depth 1 at N | K's score fell with depth |")
out.append("|---|---|---|---|---|---|---|---|")
for k in ORDER:
    s = [r for r in F if r["cls"] == k and k != "O"]
    if not s:
        continue
    wb = [r for r in s if r.get("worlds_better")]
    cheap = [r for r in wb if r["worlds_better"].get("cost_none") is not None and r["worlds_better"]["cost_none"] <= 100]
    arr = [r for r in s if r.get("arr_minus")]
    out.append(f"| {k} | {len(s)} | {len(wb)} | {len(cheap)} | {sum(bool(r.get('partner_line')) for r in arr)} of {len(arr)} | "
               f"{sum(bool(r.get('partner_alt')) for r in arr)} of {len(arr)} | {sum(r.get('depth_seen') == 1 for r in s)} | "
               f"{sum(bool(r.get('fell_with_depth')) for r in s)} |")
out.append("")
# key step position and drop sizes
out.append("## Shape of the fall")
out.append("")
out.append(f"Key step: the last step into F in {sum(r.get('key_pos') == 0 for r in F)}, one before in {sum(r.get('key_pos') == 1 for r in F)}, "
           f"two before in {sum(r.get('key_pos') == 2 for r in F)}. The fall was the seat's last decision in {sum(bool(r.get('fall_is_last')) for r in F)}. "
           f"The seat ended mated in {sum(bool(r.get('ends_mated')) for r in F)}.")
out.append("")
bins = [(-100000, -3000), (-3000, -1500), (-1500, -800), (-800, -500), (-500, -300), (-300, -200), (-200, 0)]
out.append("| drop at the key step (clipped at +-3000) | n | team lost |")
out.append("|---|---|---|")
for lo, hi in bins:
    s = [r for r in F if r.get("drop") is not None and lo < r["drop"] <= hi]
    out.append(f"| {lo} to {hi} | {len(s)} | {sum(r['won'] == 0 for r in s)} |")
out.append("")
open(os.path.join(HERE, f"report3_{tag}.md"), "w").write("\n".join(out) + "\n")
# class lists
cl = []
for k in ORDER:
    s = sorted([r for r in F if r["cls"] == k], key=lambda r: (r["match"], r["game"], r["seat"]))
    if s:
        cl.append(f"{k} ({NAME[k]}), {len(s)}:")
        by = collections.defaultdict(list)
        for r in s:
            by[r["match"]].append(f"{r['game']}{r['seat'][0]}{'w' if r['seat'].endswith('white') else 'b'}{'' if r['won'] == 0 else '*'}")
        for m, gs in by.items():
            cl.append(f"  {m}: {' '.join(gs)}")
cl.append("")
cl.append("Format: game number, board (A/B), colour (w/b); * = the seat's team won or drew anyway.")
open(os.path.join(HERE, f"classes_{tag}.txt"), "w").write("\n".join(cl) + "\n")
print("\n".join(out))
