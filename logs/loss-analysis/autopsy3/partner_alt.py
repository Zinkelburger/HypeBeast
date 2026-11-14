#!/usr/bin/env python3
"""AUTOPSY3: at the partner's decision that let the fatal piece go, did one of the partner's own compared
candidates (hb_coord candidates; its main move when it switched) leave the opponent's partner no capture of
that piece type at once? Geometry with python-chess, no engine: after the candidate, does the opponent's
partner have a legal capture of a T (promoted pieces count as P)? Cost: the move played's value minus the
candidate's in the partner's own "none" world (L). -> partner_alt.txt
    nice -n 19 python3 partner_alt.py"""
import collections
import json
import os
import sys

import chess
import chess.variant

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common3 as c3  # noqa: E402

LET = {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q"}
clip = c3.clip


def capture_types(board):
    out = set()
    for m in board.legal_moves:
        if m.drop or not board.is_capture(m):
            continue
        if board.is_en_passant(m) or board.promoted & chess.BB_SQUARES[m.to_square]:
            out.add("P")
        else:
            out.add(LET[board.piece_type_at(m.to_square)])
    return out


def gives(fen, move, T):
    """True if after `move` the side to move next can capture a T at once; None if the move is not legal"""
    try:
        b = chess.variant.CrazyhouseBoard(fen)
        m = chess.Move.from_uci(move)
        if m not in b.legal_moves:
            return None
        b.push(m)
        return T in capture_types(b)
    except (ValueError, AssertionError):
        return None


R = json.load(open(os.path.join(HERE, "falls_l50.json")))
want = collections.defaultdict(list)
for r in R:
    if r["cls"] in ("A1", "A2", "A3", "A4", "A5") and r.get("partner_n") is not None:
        want[r["match"]].append(r)
res = []
for m in c3.L50_MATCHES:
    d = c3.load(m)
    seq = c3.by_seat(d["rows"])
    for r in want.get(m, []):
        P = next((x for x in seq[(r["game"], c3.PARTNER[r["seat"]])] if x["n"] == r["partner_n"]), None)
        if P is None:
            continue
        T = max(r["arr_minus"], key="PNBRQ".index)
        co = P.get("coord") or {}
        none = next((w for w in co.get("worlds", []) if w["arrival"] == "none" and w.get("scored")), None)
        vals = none["values"] if none else {c["move"]: c["L"] for c in co.get("cands", []) if c.get("L") is not None}
        played_gives = gives(P["fen_own"], P["decision"], T)
        alts = []
        for c in co.get("cands", []):
            mv = c["move"]
            if mv == P["decision"]:
                continue
            g = gives(P["fen_own"], mv, T)
            if g is None:
                continue
            cost = (clip(vals[P["decision"]]) - clip(vals[mv])) if mv in vals and P["decision"] in vals else None
            alts.append({"move": mv, "gives": g, "cost": cost, "is_main": mv == P["main"]})
        safe = [a for a in alts if not a["gives"]]
        cheap = [a for a in safe if a["cost"] is not None and a["cost"] <= 150]
        res.append({"key": f"{r['match']}/{r['game']}/{r['seat']}", "price": (r.get("K_fc_prices") or {}).get("-" + T),
                    "safe_costs": sorted(a["cost"] for a in safe if a["cost"] is not None), "cls": r["cls"], "T": T, "played_gives": played_gives, "n_alts": len(alts), "safe": len(safe),
                    "cheap": len(cheap), "best_cost": min([a["cost"] for a in safe if a["cost"] is not None] or [None], key=lambda x: (x is None, x)),
                    "switch": P["override"], "main_safe": any(a["is_main"] and not a["gives"] for a in alts),
                    "main_cost": next((a["cost"] for a in alts if a["is_main"]), None), "won": r["won"],
                    "partner_score": P["score"], "drop": r["drop"]})
    del d
lines = ["# The partner's own candidates at the feeding move", "",
         "Arrival falls (A1-A5). Gives: after the move, the opponent's partner can capture a piece of the fatal type at once.",
         "Cost: the move played's value minus the candidate's in the partner's \"none\" world (positive: the candidate is worse "
         "for the partner's board).", ""]
n = len(res)
lines.append(f"Falls with the partner's decision logged: {n}. The move played left a capture of that type at once: "
             f"{sum(x['played_gives'] is True for x in res)} (the rest gave it later in the line, or by a capture of another piece first).")
lines.append(f"The partner compared other candidates in {sum(x['n_alts'] > 0 for x in res)}; at least one of them left no such capture: "
             f"{sum(x['safe'] > 0 for x in res)}; one of those within 150 cp on the partner's board: {sum(x['cheap'] > 0 for x in res)}.")
sw = [x for x in res if x["switch"]]
lines.append(f"Partner switched: {len(sw)}; its main move left no such capture in {sum(x['main_safe'] for x in sw)}, "
             f"at a median cost of {sorted(x['main_cost'] for x in sw if x['main_safe'] and x['main_cost'] is not None)[len([1 for x in sw if x['main_safe'] and x['main_cost'] is not None]) // 2] if any(x['main_safe'] and x['main_cost'] is not None for x in sw) else '-'} "
             f"cp to the partner's board (negative: the main move was better for the partner's own board too).")
lines.append("")
lines.append("| fatal piece | n | a safe candidate | safe within 150 cp | safe within 150 cp, our drop (median) | team won |")
lines.append("|---|---|---|---|---|---|")
for t in "QRBNP":
    s = [x for x in res if x["T"] == t]
    if not s:
        continue
    ch = [x for x in s if x["cheap"] > 0]
    dm = sorted(x["drop"] for x in ch)
    lines.append(f"| {t} | {len(s)} | {sum(x['safe'] > 0 for x in s)} | {len(ch)} | {dm[len(dm) // 2] if dm else '-'} | {sum(x['won'] == 1 for x in s)} |")
lines.append("")
lines.append("| class | n | a safe candidate | safe within 150 cp |")
lines.append("|---|---|---|---|")
for k in ("A1", "A3", "A4", "A5"):
    s = [x for x in res if x["cls"] == k]
    lines.append(f"| {k} | {len(s)} | {sum(x['safe'] > 0 for x in s)} | {sum(x['cheap'] > 0 for x in s)} |")
pr = [x for x in res if x["price"] is not None and x["price"] >= 500]
beat = [x for x in pr if x["safe_costs"] and x["safe_costs"][0] < x["price"]]
lines.append("")
lines.append(f"Falls our side had priced at 500 or more: {len(pr)}. A partner candidate left no such capture at once and cost the "
             f"partner's board less than that price: {len(beat)} (Q {sum(x['T'] == 'Q' for x in beat)}, R {sum(x['T'] == 'R' for x in beat)}, "
             f"N {sum(x['T'] == 'N' for x in beat)}, B {sum(x['T'] == 'B' for x in beat)}, P {sum(x['T'] == 'P' for x in beat)}); "
             f"the team won {sum(x['won'] == 1 for x in beat)} of them anyway.")
json.dump(res, open(os.path.join(HERE, "partner_alt.json"), "w"))
text = "\n".join(lines)
open(os.path.join(HERE, "partner_alt.txt"), "w").write(text + "\n")
print(text)
