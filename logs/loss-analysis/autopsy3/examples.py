#!/usr/bin/env python3
"""AUTOPSY3: the ten clearest falls, with the positions and the logged lines. -> examples.md
Selection (fixed): team lost, the team's first fall, K at 0 or better but not a forced mate for us, K's coordinator log present; per class
the largest drops, in the quotas below; ties by match order and game number.
    nice -n 19 python3 examples.py"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common3 as c3  # noqa: E402

QUOTA = [("A5", 3), ("A1", 2), ("A4", 1), ("A3", 1), ("C2", 1), ("C5", 1), ("H", 1)]
R = json.load(open(os.path.join(HERE, "falls_l50.json")))
net = json.load(open(os.path.join(HERE, "partner_net.json")))
order = {m: i for i, m in enumerate(c3.L50_MATCHES)}
pick = []
for cls, k in QUOTA:
    s = [r for r in R if r["cls"] == cls and r["won"] == 0 and r["team_first"] and 0 <= r["K_score"] < 90000]
    s.sort(key=lambda r: (r["drop"], order[r["match"]], r["game"]))
    if cls == "A1":   # one with a forecast that missed the piece, one with no forecast at all
        a = [r for r in s if r["worlds_scored"] > 0][:1]
        b = [r for r in s if r["worlds_scored"] == 0][:1]
        pick += a + b
    else:
        pick += s[:k]

NAMES = {"A1": "arrival in no world", "A3": "arrival; its world had the move holding", "A4": "arrival; another candidate held in its world",
         "A5": "arrival; every candidate fell in its world", "C2": "own board; the reply its line expected",
         "C5": "own board after a switch", "H": "a sit"}


def fm(v):
    return c3.c2.fm(v)


out = ["# AUTOPSY3: ten falls in detail", "",
       "Selection: lost games, the team's first fall, score at K of 0 or better but not a forced mate for us (4 falls start from one), largest drop per class "
       "(A5 three, A1 two of which one without a forecast, one each of A4, A3, C2, C5, H). FENs are crazyhouse "
       "FENs with the hands in brackets (upper case: White's hand). Scores are the seat's main score in cp, from "
       "its side; M-n: mated in n plies.", ""]
cache = {}
for i, r in enumerate(pick, 1):
    if r["match"] not in cache:
        cache.clear()
        cache[r["match"]] = c3.load(r["match"])
    d = cache[r["match"]]
    seq = c3.by_seat(d["rows"])
    g = next(x for x in d["games"] if x["game"] == r["game"])
    S = [x for x in seq[(r["game"], r["seat"])] if x["score"] is not None]
    K = next(x for x in S if x["n"] == r["K_n"])
    N = next(x for x in S if x["n"] == r["N_n"])
    co = K.get("coord") or {}
    out.append(f"## {i}. {r['match']} game {r['game']}, {r['seat']} ({r['cls']}: {NAMES[r['cls']]})")
    out.append("")
    out.append(f"- Scores at its last decisions into the fall: {' → '.join(fm(x) for x in r['trail'])}. Key step n={r['K_n']} → n={r['N_n']}: "
               f"{fm(r['K_score'])} → {fm(r['N_score'])}. Team result: lost ({g['termination']}).")
    ck = K.get("clocks")
    if ck:
        out.append(f"- Clocks at K (aW, aB, bW, bB): {', '.join(f'{c / 1000:.1f}' for c in ck)} s.")
    out.append(f"- Our board at K: `{K['fen_own']}`")
    out.append(f"- Other board at K: `{K['fen_other']}`")
    f = K["feat"]
    out.append(f"- King: rank {f.get('krank')} from home, {f.get('kzone_att')} king-zone squares attacked, in check: {bool(f.get('in_check'))}; "
               f"opponent's hand worth {f.get('hand_opp')}, ours {f.get('hand_own')}. Partner's last score: {fm(r.get('partner_score'))}.")
    out.append(f"- K played `{K['decision']}` ({K['reason']}{'; main ' + K['main'] if K['override'] else ''}), main depth {K['depth']}, "
               f"main line: `{' '.join((K.get('mainpv') or [])[:10])}`")
    if K.get("dscores"):
        out.append(f"- K's last depths: {', '.join(f'd{dd} {fm(s)}' for dd, s in K['dscores'][-5:])}")
    if co.get("worlds"):
        cands = [c["move"] for c in co.get("cands", [])]
        out.append("")
        out.append("| world at K | p | " + " | ".join(f"`{c}`" + (" (played)" if c == K["decision"] else "") for c in cands) + " |")
        out.append("|---|---|" + "---|" * len(cands))
        for w in co["worlds"]:
            out.append(f"| {w['arrival']} | {w['p']:.2f} | " + " | ".join(fm(w["values"].get(c)) if w.get("scored") else "not scored" for c in cands) + " |")
        out.append("")
        if K.get("fc_prices"):
            out.append(f"- Our forecast's measured price of one arriving piece: {K['fc_prices']}")
    else:
        out.append(f"- No coordinator worlds at K (reason {K['reason']}, {r['legal']} legal moves).")
    arr = ", ".join(r["arr_minus"]) or "nothing"
    out.append(f"- Reached the opponent's hand in the step: {arr}" + (f"; ours: {', '.join(r['arr_plus'])}" if r["arr_plus"] else "")
               + (f". The capture: `{r['fatal_move'][1:]}` on the other board, the reply to the partner's `{r.get('partner_decision')}`"
                  f" (partner's own line had that capture: {'yes' if r.get('partner_line') else 'no'})." if r.get("fatal_move") else "."))
    k = f"{r['match']}/{r['game']}/{r['seat']}"
    if k in net:
        nn = net[k]
        out.append(f"- The partner at that decision: {fm(nn['p_before'])} → {fm(nn['p_after'])} at its next; its line `{' '.join(nn['p_line'] or [])}`.")
    if r.get("they_took") or r.get("we_took"):
        out.append(f"- Captures on our board in the step: we took {r['we_took'] or 'nothing'}, they took {r['they_took'] or 'nothing'}.")
    out.append(f"- Opponent's reply on our board: `{r['reply']}` (K's line expected `{r['pv_reply']}`).")
    out.append(f"- At N: `{N['fen_own']}`, score {fm(N['score'])}, line `{' '.join((N.get('mainpv') or [])[:10])}`; "
               f"first depth below -300: {r['depth_seen']}.")
    if r.get("early"):
        e = [x for x in r["early"] if x]
        if e:
            out.append(f"- The same piece in its worlds at the two decisions before K: "
                       + "; ".join(f"p {x['p']:.2f}, move played {fm(x['v_play'])}, best candidate {fm(x['v_best'])}" for x in e) + ".")
    out.append("")
text = "\n".join(out)
open(os.path.join(HERE, "examples.md"), "w").write(text + "\n")
print(text)
