"""What the mate prices cost the seat that pays them: its own board's score after a decision with a mate price set.

    python3 guardcost.py logs/matefree [logs/mateprice-vs-np ...]
For the contender: decisions with no mate price, with one on a type not on its board, on a type on its board,
on a type that can be taken at once; whose move it was on the partner's board (hb_values stm); and the seat's
own main score at its next decision minus now (drift), beside the baseline's drift over all its decisions.
"""
import json, sys, glob, collections, statistics
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")
import chess
from hbutil import Bughouse
SYM = {chess.PAWN: "P", chess.KNIGHT: "N", chess.BISHOP: "B", chess.ROOK: "R", chess.QUEEN: "Q"}
for d in sys.argv[1:]:
    d = d.rstrip("/")
    rows = [json.loads(l) for l in open(f"{d}/postmortem.jsonl")]
    res = [json.loads(l) for l in open(f"{d}/results.jsonl")]
    con = res[0]["contender"]
    pm = {}
    index = collections.defaultdict(list)
    for r in res:
        toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
        index[tuple(toks[:12])].append((r, toks))
    for r in rows: pm[(r["game"], r["seat"], r["n"])] = r
    groups = collections.defaultdict(list)
    for path in sorted(glob.glob(f"{d}/engine_logs/w*-contender-*.log")):
        seat = moves = None; block = None
        for line in open(path, errors="replace"):
            if line.startswith(">>> setoption name Seat value "): seat = line.split()[-1]
            elif line.startswith(">>> position startpos moves "): moves = line.split()[4:]
            elif line.startswith(">>> go"): block = {}
            elif block is None: continue
            elif line.startswith("info string hb_prices "): block["p"] = json.loads(line.split("hb_prices ", 1)[1])
            elif line.startswith("info string hb_values "): block["v"] = json.loads(line.split("hb_values ", 1)[1])
            elif line.startswith("bestmove"):
                b, block = block, None
                p = b.get("p")
                if not p or moves is None or seat is None: continue
                g0 = next(((r, t) for r, t in index.get(tuple(moves[:12]), []) if t[:len(moves)] == moves and r["seats"][seat[0] + "-" + seat[1:]] == con), None)
                row = pm.get((g0[0]["game"], seat, len(moves))) if g0 else None
                if not row: continue
                theirs = {t for t, v in p["theirs"].items() if v == 1500}
                g = Bughouse()
                for t in moves: g.push(int(t[0]) - 1, t[1:])
                bi = 0 if seat[0] == "A" else 1
                bd = g.boards[bi]; me = chess.WHITE if seat.endswith("white") else chess.BLACK
                present, attacked = set(), set()
                for sq, pc in bd.piece_map().items():
                    if pc.color == me and pc.piece_type != chess.KING:
                        present.add(SYM[pc.piece_type])
                        if bd.is_attacked_by(not me, sq): attacked.add(SYM[pc.piece_type])
                # on the partner's board: is our partner on move?
                partner_on_move = g.boards[1 - bi].turn != me
                kind = "no mate price" if not theirs else "mate price, type not on our board" if not theirs & present else \
                       "mate price, type on our board, not attacked" if not theirs & attacked else "mate price, type can be taken now"
                groups[kind].append(row)
                if theirs:
                    groups["  ... partner on move there" if partner_on_move else "  ... partner's opponent on move there"].append(row)
                    if theirs & attacked:
                        groups["  can be taken now, partner on move there" if partner_on_move else "  can be taken now, opponent on move there"].append(row)
    def line(name, rs):
        ds = [r["next_score"] - r["score"] for r in rs if r["next_score"] is not None and r["score"] is not None and abs(r["score"]) < 90000 and abs(r["next_score"]) < 90000]
        sc = [max(-1500, min(1500, r["score"])) for r in rs if r["score"] is not None and abs(r["score"]) < 90000]
        if not ds: return f"{name} | {len(rs)}"
        mated = sum(1 for r in rs if r["next_score"] is not None and r["next_score"] <= -90000 and r["score"] is not None and r["score"] > -90000)
        return f"{name} | {len(rs)} | {statistics.mean(sc):+.0f} | {statistics.mean(ds):+.0f} | {statistics.median(ds):+.0f} | {100*sum(x <= -200 for x in ds)/len(ds):.1f}% | {mated} | {100*statistics.mean(r['won'] for r in rs):.0f}%"
    print(f"\n{d}: contender {con}")
    print("decisions | n | mean score now | mean drift to next decision | median | 200+ worse | then mated | games won")
    for k in ("no mate price", "mate price, type not on our board", "mate price, type on our board, not attacked", "mate price, type can be taken now",
              "  ... partner on move there", "  ... partner's opponent on move there", "  can be taken now, partner on move there", "  can be taken now, opponent on move there"):
        print(line(k, groups[k]))
    for e in sorted({r["engine"] for r in rows}):
        print(line(f"all decisions of {e}", [r for r in rows if r["engine"] == e]))
        for lo, hi in ((0, 40), (40, 80), (80, 400)):
            rs = [r for r in rows if r["engine"] == e and lo <= r["n"] < hi and r["score"] is not None and abs(r["score"]) < 90000]
            print(f"   plies {lo}-{hi}: n {len(rs)}, mean score {statistics.mean(max(-1500, min(1500, r['score'])) for r in rs):+.0f}")
