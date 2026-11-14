"""What the mate-price probes of F6 (mateprice-vs-np) flagged, and how many of them a cheaper guard would need.

For every decision of the contender: which piece types its probes priced as mating (theirs: lost here, it
mates our partner; ours: won here, our partner mates), which of our piece types are on our board, and which
of them the opponent could capture at once if it were on move. Logs only.
"""
import json, sys, glob, collections
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")
import chess
from hbutil import Bughouse
d = sys.argv[1]
SYM = {chess.PAWN: "P", chess.KNIGHT: "N", chess.BISHOP: "B", chess.ROOK: "R", chess.QUEEN: "Q"}
n = collections.Counter(); flag = collections.Counter(); flips = clears = pairs = 0
present_n = attacked_n = 0
depths = collections.Counter()
for path in sorted(glob.glob(f"{d}/engine_logs/w*-contender-*.log")):
    seat = moves = None; block = None; prev = {}
    for line in open(path, errors="replace"):
        if line.startswith(">>> setoption name Seat value "): seat = line.split()[-1]
        elif line.startswith(">>> position startpos moves "): moves = line.split()[4:]
        elif line.startswith(">>> ucinewgame"): prev = {}
        elif line.startswith(">>> go"): block = {}
        elif block is None: continue
        elif line.startswith("info string hb_prices "): block["p"] = json.loads(line.split("hb_prices ", 1)[1])
        elif line.startswith("info string hb_summary "): block["s"] = dict(p.split("=", 1) for p in line.split()[3:] if "=" in p)
        elif line.startswith("bestmove"):
            b, block = block, None
            p = b.get("p")
            if not p or moves is None or seat is None: continue
            n["decisions with probes"] += 1
            theirs = {t for t, v in p["theirs"].items() if v == 1500}
            ours = {t for t, v in p["ours"].items() if v == 800}
            if b.get("s", {}).get("price_depth"): depths[int(b["s"]["price_depth"])] += 1
            g = Bughouse()
            for t in moves: g.push(int(t[0]) - 1, t[1:])
            bd = g.boards[0 if seat[0] == "A" else 1]
            me = chess.WHITE if seat.endswith("white") else chess.BLACK
            present, attacked, undefended = set(), set(), set()
            for sq, pc in bd.piece_map().items():
                if pc.color != me or pc.piece_type == chess.KING: continue
                s = SYM[pc.piece_type]; present.add(s)
                if bd.is_attacked_by(not me, sq): attacked.add(s)
            present_n += len(present); attacked_n += len(attacked)
            n["any theirs mate flag"] += bool(theirs); n["any ours mate flag"] += bool(ours)
            n["any flag at all"] += bool(theirs or ours)
            for t in theirs:
                flag["theirs " + t] += 1
                flag["theirs, type on our board"] += t in present
                flag["theirs, type attacked now"] += t in attacked
                flag["theirs flags"] += 1
            n["a flagged type is on our board"] += bool(theirs & present)
            n["a flagged type is attacked now"] += bool(theirs & attacked)
            key = (seat,)
            if key in prev:
                pairs += 1
                flips += prev[key] != (theirs, ours)
                clears += bool(prev[key][0] or prev[key][1] or theirs or ours)
            prev[key] = (theirs, ours)
N = n["decisions with probes"]
for k, v in n.most_common(): print(f"{v:6d} {100*v/N:5.1f}%  {k}")
print("flags by kind:", dict(flag))
print(f"our piece types on the board: {present_n/N:.2f} a decision; attacked now: {attacked_n/N:.2f}")
print(f"consecutive decisions of a seat: {pairs}; flags changed {flips} ({100*flips/pairs:.1f}%); table cleared under HBPriceKeepTable {clears} ({100*clears/pairs:.1f}%)")
print("probe depth:", sorted(depths.items()))
