#!/usr/bin/env python3
"""worth-b (v8i, HBTell=worth): what the hearer priced, and what happened to its own board. Logs only.
    nice -n 19 python3 worth.py [MATCH]   -> worth_<MATCH>.txt"""
import collections
import os
import sys

import chess
import chess.variant

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common3 as c3  # noqa: E402

M = sys.argv[1] if len(sys.argv) > 1 else "worth-b"
VAL = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}
d = c3.load(M)
cname = d["games"][0]["names"]["contender"]
games = {g["game"]: g for g in d["games"]}
out = [f"# {M}: {cname} against hb-l50", ""]


def priced(r):
    p = r.get("prices") or {}
    return {k: v for k, v in (p.get("theirs") or {}).items() if v} if p else {}


def material(fen, color):
    """own-board material plus hand, side `color` minus the other, in pawns (promoted pieces count as pawns)"""
    try:
        b = chess.variant.CrazyhouseBoard(fen)
    except ValueError:
        return None
    s = 0
    for sq, pc in b.piece_map().items():
        if pc.piece_type == chess.KING:
            continue
        v = 1 if b.promoted & chess.BB_SQUARES[sq] else VAL[pc.symbol().upper()]
        s += v if pc.color == color else -v
    for col in (chess.WHITE, chess.BLACK):
        for pt, n in b.pockets[col].pieces.items() if hasattr(b.pockets[col], "pieces") else []:
            pass
        for pt in range(1, 6):
            n = b.pockets[col].count(pt)
            v = VAL[chess.piece_symbol(pt).upper()] * n
            s += v if col == color else -v
    return s


rows = d["rows"]
C = [r for r in rows if r["engine"] == cname]
B = [r for r in rows if r["engine"] != cname]
P = [r for r in C if priced(r)]
out.append(f"Decisions: {cname} {len(C)}, hb-l50 {len(B)}. With a price set: {len(P)} ({100 * len(P) / len(C):.1f}%).")
bytype = collections.defaultdict(list)
for r in P:
    for t, v in priced(r).items():
        bytype[t].append(v)
out.append("Prices set, by type: " + ", ".join(f"{t} {len(v)} (median {sorted(v)[len(v) // 2]})" for t, v in sorted(bytype.items(), key=lambda x: "QRBNP".index(x[0]))))
ptypes = collections.Counter(len(priced(r)) for r in P)
out.append("Types priced at once: " + ", ".join(f"{k}: {v}" for k, v in sorted(ptypes.items())))
# own score, plies 40-80, without and with a price
for nm, rs in ((cname, C), ("hb-l50", B)):
    a = [c3.clip(r["score"]) for r in rs if r["score"] is not None and 40 <= r["n"] <= 80 and not priced(r)]
    b = [c3.clip(r["score"]) for r in rs if r["score"] is not None and 40 <= r["n"] <= 80 and priced(r)]
    out.append(f"{nm}: own score, plies 40-80, no price {sum(a) / max(1, len(a)):+.0f} ({len(a)})" +
               (f", with a price {sum(b) / len(b):+.0f} ({len(b)})" if b else ""))
# material on own board (with hands) at plies 20, 40, 60, 80: the seat's first decision at or after that ply
out.append("")
out.append("Own-board material (pieces on the board and in both hands, pawns; seat minus opponent) at the seat's first "
           "decision at or after ply k, mean over seats:")
out.append("")
out.append(f"| ply | {cname} | hb-l50 | seats |")
out.append("|---|---|---|---|")
seq = c3.by_seat(rows)
for k in (20, 30, 40, 60, 80):
    mc, mb = [], []
    for (g, s), xs in seq.items():
        x = next((x for x in xs if x["n"] >= k), None)
        if x is None:
            continue
        col = chess.WHITE if s.endswith("white") else chess.BLACK
        m = material(x["fen_own"], col)
        if m is None:
            continue
        (mc if x["engine"] == cname else mb).append(m)
    out.append(f"| {k} | {sum(mc) / max(1, len(mc)):+.2f} | {sum(mb) / max(1, len(mb)):+.2f} | {len(mc)}/{len(mb)} |")
# games: price set or not, and the result
out.append("")
gp = collections.defaultdict(int)
for r in P:
    gp[r["game"]] += 1
w_with = [games[g] for g in games if gp.get(g)]
w_without = [games[g] for g in games if not gp.get(g)]


def score(gs):
    return sum(1.0 if g["winner"] == g["contender_team"] else 0.5 if g["winner"] not in ("white", "black") else 0 for g in gs)


out.append(f"Games with a price set at least once: {len(w_with)}, contender scored {score(w_with):g}; without: {len(w_without)}, "
           f"{score(w_without):g}.")
# which board was mated in lost games: the board of the seat that priced most?
lost = [g for g in games.values() if g["winner"] in ("white", "black") and g["winner"] != g["contender_team"]]
mated_board = collections.Counter()
for g in lost:
    xs = [r for r in C if r["game"] == g["game"]]
    if not xs:
        continue
    last = max(xs, key=lambda r: (r["n"], r["t"]))
    hearer_seats = collections.Counter(r["seat"] for r in xs if priced(r))
    # the seat whose last score was a mate against is the mated one
    m = [r for r in xs if r["score"] is not None and r["score"] <= -90000]
    if not m:
        mated_board["no mate seen"] += 1
        continue
    s = min(m, key=lambda r: (r["n"], r["t"]))["seat"]
    if not hearer_seats:
        mated_board["no price in the game"] += 1
    elif s == hearer_seats.most_common(1)[0][0]:
        mated_board["first to see mate = the seat that priced most"] += 1
    else:
        mated_board["first to see mate = its partner"] += 1
out.append("Lost games, by who first saw itself mated: " + ", ".join(f"{k} {v}" for k, v in mated_board.most_common()))
# decisions after a price: score change to the seat's next decision
ch_p, ch_n = [], []
for (g, s), xs in seq.items():
    xs = [x for x in xs if x["engine"] == cname and x["score"] is not None]
    for a, b in zip(xs, xs[1:]):
        if abs(a["score"]) > 20000 or abs(b["score"]) > 20000:
            continue
        (ch_p if priced(a) else ch_n).append(c3.clip(b["score"]) - c3.clip(a["score"]))
out.append(f"Score change to the seat's next decision (no mates): after a priced decision {sum(ch_p) / max(1, len(ch_p)):+.0f} "
           f"({len(ch_p)}), after an unpriced one {sum(ch_n) / max(1, len(ch_n)):+.0f} ({len(ch_n)}).")
text = "\n".join(out)
open(os.path.join(HERE, f"worth_{M}.txt"), "w").write(text + "\n")
print(text)
