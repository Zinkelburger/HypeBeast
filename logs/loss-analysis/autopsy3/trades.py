#!/usr/bin/env python3
"""AUTOPSY3: the capture that fed the opponent, and whether it was half of a trade on the partner board.
For each fall whose key step was an arrival: on the partner board, our partner's captures within 3 plies of
that board before and after the fatal capture; the type; and whether that piece reached our hand before
our next decision after the fall step (N). -> trades.txt
    nice -n 19 python3 trades.py"""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import common3 as c3
R = json.load(open(os.path.join(HERE, "falls_l50.json")))
net = json.load(open(os.path.join(HERE, "partner_net.json")))
games = {}
for m in c3.L50_MATCHES:
    d = c3.load(m)
    for g in d["games"]:
        games[(m, g["game"])] = {"toks": g["toks"], "caps": g["caps"]}
    del d
V = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}
rows = []
for r in R:
    if r["cls"] not in ("A1", "A2", "A3", "A4", "A5") or r.get("fatal_idx") is None:
        continue
    g = games[(r["match"], r["game"])]
    fi = r["fatal_idx"]
    pb = g["toks"][fi][0]
    p_white = c3.c2.seat_white(c3.PARTNER[r["seat"]])
    board_idx = [i for i, t in enumerate(g["toks"]) if t[0] == pb]
    pos = board_idx.index(fi)
    window_before = set(board_idx[max(0, pos - 3):pos])
    window_after = set(board_idx[pos + 1:pos + 4])
    caps = {c[0]: c for c in g["caps"] if c[1] == pb}
    fatal_t = caps[fi][3] if fi in caps else None
    ours_before = [caps[i][3] for i in sorted(window_before) if i in caps and caps[i][2] == p_white]
    ours_after = [(i, caps[i][3]) for i in sorted(window_after) if i in caps and caps[i][2] == p_white]
    if ours_before:
        kind = "partner took first (we got a piece before they did)"
    elif ours_after:
        kind = "partner took back after (they got theirs first)"
    else:
        kind = "no capture by our partner within 3 plies"
    back = max([t for _, t in ours_after], key=V.get) if ours_after else None
    arrived_before_N = any(i < r["N_n"] for i, _ in ours_after)
    k = f"{r['match']}/{r['game']}/{r['seat']}"
    rows.append({"cls": r["cls"], "kind": kind, "fatal": fatal_t, "back": back, "before": ours_before,
                 "back_before_N": arrived_before_N, "won": r["won"], "drop": r["drop"],
                 "p_delta": (net.get(k) or {}).get("p_delta"), "N_mate": r["N_score"] <= -90000})
lines = ["# The fatal capture and trades on the partner board", ""]
lines.append("| how the fatal capture came | n | team won | the fall was a forced mate | our piece back reached our hand before N |")
lines.append("|---|---|---|---|---|")
for kind in sorted({x["kind"] for x in rows}):
    s = [x for x in rows if x["kind"] == kind]
    lines.append(f"| {kind} | {len(s)} | {sum(x['won'] == 1 for x in s)} | {sum(x['N_mate'] for x in s)} | {sum(x['back_before_N'] for x in s)} |")
lines.append("")
lines.append("Partner took back after, by the piece they got and the piece we got back:")
lines.append("")
c = collections.Counter((x["fatal"], x["back"]) for x in rows if x["kind"].startswith("partner took back"))
lines.append("| they got | we got back | n |")
lines.append("|---|---|---|")
for (a, b), n in c.most_common(20):
    lines.append(f"| {a} | {b} | {n} |")
lines.append("")
lines.append("By class:")
lines.append("")
lines.append("| class | n | partner took first | took back after | no capture near |")
lines.append("|---|---|---|---|---|")
for k in ("A1", "A3", "A4", "A5"):
    s = [x for x in rows if x["cls"] == k]
    lines.append(f"| {k} | {len(s)} | {sum(x['kind'].startswith('partner took first') for x in s)} | {sum(x['kind'].startswith('partner took back') for x in s)} | {sum(x['kind'].startswith('no capture') for x in s)} |")
text = "\n".join(lines)
open(os.path.join(HERE, "trades.txt"), "w").write(text + "\n")
print(text)

# ---- appended: piece pairs when the partner took first, and whether our side had priced the fatal piece
c = collections.Counter((x["before"][-1] if x["before"] else None, x["fatal"]) for x in rows if x["kind"].startswith("partner took first"))
extra = ["", "Partner took first, by the piece we got first and the piece they got (the fatal one):", "",
         "| we got first | they got | n |", "|---|---|---|"]
for (a, b), n in c.most_common(20):
    extra.append(f"| {a} | {b} | {n} |")
text2 = "\n".join(extra)
open(os.path.join(HERE, "trades.txt"), "a").write(text2 + "\n")
print(text2)
