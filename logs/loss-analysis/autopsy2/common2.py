#!/usr/bin/env python3
"""Shared loading for autopsy2 (plan-vs-l50 and the matches used beside it).

    nice -n 19 python3 common2.py [MATCH ...]     rebuild cache_<MATCH>.pkl

load(match) -> {"games": [...], "rows": [...]} where
  games: postmortem.load_games plus events, clocks_end, sits, sit_ms, seat_stats from results.jsonl
  rows:  postmortem.collect rows (one per decision, every field of postmortem.jsonl) plus
         mainpv   the exact line at the main depth (postmortem's _mainpv)
         clocks   [aW, aB, bW, bB] ms sent before that go; tadv the TimeAdvantage option
         pvfull   the longest pv among the main search's last two depths
         told     the captures of the partner's told line in hb_forecast (None if none), its weight
         feat     features of the replayed position at the decision (see features())
The rows of both engines are kept; "engine" says whose decision it is.
"""
import collections
import glob
import json
import os
import pickle
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import postmortem as pm  # noqa: E402
import chess  # noqa: E402
import chess.variant  # noqa: E402

MAIN = "plan-vs-l50"
PARTNER = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
SEATS = ["Awhite", "Ablack", "Bwhite", "Bblack"]
VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
LET = {chess.PAWN: "P", chess.KNIGHT: "N", chess.BISHOP: "B", chess.ROOK: "R", chess.QUEEN: "Q"}
MATE = 90000


def seat_board(seat):
    return "1" if seat[0] == "A" else "2"


def seat_white(seat):
    return seat.endswith("white")


def seat_team(seat):
    return "white" if seat in ("Awhite", "Bblack") else "black"


def team_seats(team):
    return ("Awhite", "Bblack") if team == "white" else ("Ablack", "Bwhite")


def fm(v):
    if v is None:
        return "?"
    if v <= -MATE:
        return f"M-{100000 + v}" if v > -100001 else "M-"
    if v >= MATE:
        return f"M+{100000 - v}" if v < 100001 else "M+"
    return str(v)


def replay_boards(toks):
    """-> list of (boardA, boardB) before token i, i = 0..len(toks)"""
    b = {"1": chess.variant.CrazyhouseBoard(), "2": chess.variant.CrazyhouseBoard()}
    snaps = [(b["1"].copy(stack=False), b["2"].copy(stack=False))]
    for t in toks:
        board = b[t[0]]
        mover = board.turn
        before = {p: board.pockets[mover].count(p) for p in VAL}
        board.push(chess.Move.from_uci(t[1:]))
        for p in VAL:
            if board.pockets[mover].count(p) > before[p]:
                board.pockets[mover].remove(p)
                b["2" if t[0] == "1" else "1"].pockets[not mover].add(p)
        snaps.append((b["1"].copy(stack=False), b["2"].copy(stack=False)))
    return snaps


def pocket_value(pocket):
    return sum(VAL[p] * pocket.count(p) for p in VAL)


def drop_check_squares(board, color_dropper, ptype):
    """squares where `color_dropper` could drop a `ptype` giving check to the other king (geometry only)"""
    k = board.king(not color_dropper)
    if k is None:
        return chess.SquareSet()
    occ = board.occupied
    empty = ~occ & chess.BB_ALL
    if ptype == chess.KNIGHT:
        m = chess.BB_KNIGHT_ATTACKS[k]
    elif ptype == chess.BISHOP:
        m = chess.BB_DIAG_ATTACKS[k][chess.BB_DIAG_MASKS[k] & occ]
    elif ptype == chess.ROOK:
        m = chess.BB_RANK_ATTACKS[k][chess.BB_RANK_MASKS[k] & occ] | chess.BB_FILE_ATTACKS[k][chess.BB_FILE_MASKS[k] & occ]
    elif ptype == chess.QUEEN:
        m = (chess.BB_DIAG_ATTACKS[k][chess.BB_DIAG_MASKS[k] & occ] | chess.BB_RANK_ATTACKS[k][chess.BB_RANK_MASKS[k] & occ]
             | chess.BB_FILE_ATTACKS[k][chess.BB_FILE_MASKS[k] & occ])
    elif ptype == chess.PAWN:
        # a pawn of color_dropper on s attacks k  <=>  s in pawn attacks of the other colour from k
        m = chess.BB_PAWN_ATTACKS[not color_dropper][k] & ~(chess.BB_RANK_1 | chess.BB_RANK_8)
    else:
        m = 0
    return chess.SquareSet(m & empty)


def features(board, other, white, partner_white):
    """the seat's board `board` (seat plays `white`), the other board `other` (partner plays `partner_white`)"""
    col = chess.WHITE if white else chess.BLACK
    f = {}
    ho, hp = board.pockets[col], board.pockets[not col]
    f["hand_own"] = pocket_value(ho)
    f["hand_opp"] = pocket_value(hp)
    f["opp_q"] = hp.count(chess.QUEEN)
    f["opp_n"] = hp.count(chess.KNIGHT)
    f["opp_r"] = hp.count(chess.ROOK)
    f["own_q"] = ho.count(chess.QUEEN)
    pm_ = board.piece_map()
    f["mat_own"] = sum(VAL[p.piece_type] for p in pm_.values() if p.color == col and p.piece_type in VAL)
    f["mat_opp"] = sum(VAL[p.piece_type] for p in pm_.values() if p.color != col and p.piece_type in VAL)
    k = board.king(col)
    if k is not None:
        rank = chess.square_rank(k)
        rel = rank if white else 7 - rank
        fl = chess.square_file(k)
        d = 1 if white else -1
        shelter = 0
        for df in (-1, 0, 1):
            ff = fl + df
            if not 0 <= ff <= 7:
                continue
            for dr in (1, 2):
                rr = rank + d * dr
                if 0 <= rr <= 7:
                    p = board.piece_at(chess.square(ff, rr))
                    if p and p.piece_type == chess.PAWN and p.color == col:
                        shelter += 1
                        break
        zone = list(chess.SquareSet(chess.BB_KING_ATTACKS[k])) + [k]
        f["krank"] = rel
        f["kfile"] = fl
        f["kfile_centre"] = 2 <= fl <= 5          # c-f
        f["shelter"] = shelter
        f["kzone_att"] = sum(1 for s in zone if board.is_attacked_by(not col, s))
        f["in_check"] = board.is_check() if board.turn == col else False
        # drop checks the opponent has with what it holds now; "safe": the square is not attacked by us
        sq_all, sq_safe, types = set(), set(), set()
        for pt in VAL:
            if hp.count(pt):
                s = drop_check_squares(board, not col, pt)
                if s:
                    types.add(LET[pt])
                for q in s:
                    sq_all.add(q)
                    if not board.is_attacked_by(col, q):
                        sq_safe.add(q)
        f["opp_drop_checks"] = len(sq_all)
        f["opp_safe_drop_checks"] = len(sq_safe)
        # the same if the opponent also had a queen (what a queen arriving would add)
        s = drop_check_squares(board, not col, chess.QUEEN)
        f["q_drop_checks"] = len(s)
        f["q_safe_drop_checks"] = sum(1 for q in s if not board.is_attacked_by(col, q))
        # our own drop checks
        own = set()
        for pt in VAL:
            if ho.count(pt):
                own |= set(drop_check_squares(board, col, pt))
        f["own_drop_checks"] = len(own)
    f["other_partner_to_move"] = other.turn == (chess.WHITE if partner_white else chess.BLACK)
    return f


def parse_logs(d):
    """-> dict (role, seat, moves tuple) -> list of extras in log order (one per go with a summary)"""
    out = collections.defaultdict(list)
    for path in sorted(glob.glob(f"{d}/engine_logs/w*-*.log")):
        role = "contender" if "-contender-" in path else "baseline"
        seat = moves = clocks = tadv = None
        block = None
        for line in open(path, errors="replace"):
            if line.startswith(">>> setoption name Seat value "):
                seat = line.split()[-1]
            elif line.startswith(">>> setoption name Clocks value "):
                clocks = [int(x) for x in line.split()[-1].split(",")]
            elif line.startswith(">>> setoption name TimeAdvantage value "):
                tadv = line.split()[-1] == "true"
            elif line.startswith(">>> position startpos moves "):
                moves = line.split()[4:]
            elif line.startswith(">>> go"):
                block = {"pvs": [], "coord_seen": False, "told": None}
            elif block is None:
                continue
            elif line.startswith("info depth ") and " pv " in line and not block["coord_seen"]:
                m = re.match(r"info depth (\d+)", line)
                block["pvs"].append((int(m.group(1)), line.split(" pv ", 1)[1].split()))
            elif line.startswith("info string hb_forecast "):
                try:
                    fc = json.loads(line.split("hb_forecast ", 1)[1])
                    tl = [l for l in fc.get("lines", []) if l.get("source") == "told"]
                    if tl:
                        block["told"] = {"w": tl[0]["weight"], "caps": tl[0].get("captures", []), "pv": tl[0].get("pv", [])}
                    block["fc_depth"] = fc.get("depth")
                except ValueError:
                    pass
            elif line.startswith("info string hb_coord "):
                block["coord_seen"] = True
                try:
                    co = json.loads(line.split("hb_coord ", 1)[1])
                    block["coord"] = {"common_depth": co.get("common_depth"),
                                      "cands": [c["move"] for c in co.get("candidates", [])],
                                      "worlds": [{"arrival": w.get("arrival"), "depth": w.get("depth"),
                                                  "values": w.get("values", {})} for w in (co.get("worlds") or [])]}
                except ValueError:
                    pass
            elif line.startswith("info string hb_summary "):
                block["sum"] = True
            elif line.startswith("bestmove"):
                b, block = block, None
                if not b.get("sum") or moves is None or seat is None:
                    continue
                pvs = b["pvs"]
                full = []
                if pvs:
                    top = max(dd for dd, _ in pvs)
                    cands = [p for dd, p in pvs if dd >= top - 1]
                    full = max(cands, key=len)
                out[(role, seat, tuple(moves))].append({"clocks": clocks, "tadv": tadv, "pvfull": full,
                                                        "told": b["told"], "fc_depth": b.get("fc_depth"),
                                                        "coord": b.get("coord")})
    return out


def build(match):
    d = os.path.join(REPO, "logs", match)
    tag, games, rows, unmatched = pm.collect(d)
    raw = {json.loads(l)["game"]: json.loads(l) for l in open(f"{d}/results.jsonl")}
    for g in games:
        r = raw[g["game"]]
        g["events"] = r["result"]["events"]
        g["clocks_end"] = r["result"]["clocks_ms"]
        g["sits"] = r["result"]["sits"]
        g["sit_ms"] = r["result"]["sit_ms"]
        g["seat_stats"] = r["seat_stats"]
        g["contender_team"] = r.get("contender_team")
    extras = parse_logs(d)
    gby = {g["game"]: g for g in games}
    snaps = {}
    used = collections.Counter()
    for r in rows:
        r["mainpv"] = r.pop("_mainpv", None)
        r.pop("_prices", None)
        r.pop("_next", None)
        g = gby[r["game"]]
        role = "contender" if g["names"]["contender"] == r["engine"] else "baseline"
        key = (role, r["seat"], tuple(g["toks"][:r["n"]]))
        i = used[key]
        used[key] += 1
        ex = extras.get(key, [])
        r.update(ex[i] if i < len(ex) else {"clocks": None, "tadv": None, "pvfull": r["pv"], "told": None,
                                            "fc_depth": None, "coord": None})
        if r["game"] not in snaps:
            snaps[r["game"]] = replay_boards(g["toks"])
        bA, bB = snaps[r["game"]][r["n"]]
        board = bA if r["seat"][0] == "A" else bB
        other = bB if r["seat"][0] == "A" else bA
        r["feat"] = features(board, other, seat_white(r["seat"]), seat_white(PARTNER[r["seat"]]))
    data = {"games": games, "rows": rows, "unmatched": unmatched}
    with open(os.path.join(HERE, f"cache_{match}.pkl"), "wb") as f:
        pickle.dump(data, f)
    print(match, len(games), "games", len(rows), "rows, unmatched", unmatched,
          "extras missing", sum(1 for r in rows if r.get("clocks") is None), file=sys.stderr)
    return data


def load(match=MAIN):
    p = os.path.join(HERE, f"cache_{match}.pkl")
    if not os.path.exists(p):
        return build(match)
    with open(p, "rb") as f:
        return pickle.load(f)


def by_seat(rows):
    out = collections.defaultdict(list)
    for r in rows:
        out[(r["game"], r["seat"])].append(r)
    for k in out:
        out[k].sort(key=lambda r: (r["n"], r["t"]))
    return out


if __name__ == "__main__":
    for m in (sys.argv[1:] or [MAIN]):
        build(m)


# ------------------------------------------------------------------ resampling helpers
def boot_ratio(per, B=2000, seed=11):
    """per: game -> (numerator, denominator). -> (estimate, lo, hi) of sum(num)/sum(den), 95% by game resampling"""
    import random
    rnd = random.Random(seed)
    gl = sorted(per)
    n = sum(per[g][0] for g in gl)
    d = sum(per[g][1] for g in gl)
    if not d:
        return None, None, None
    bs = []
    for _ in range(B):
        s = rnd.choices(gl, k=len(gl))
        nn = sum(per[g][0] for g in s)
        dd = sum(per[g][1] for g in s)
        if dd:
            bs.append(nn / dd)
    bs.sort()
    return n / d, bs[int(.025 * len(bs))], bs[int(.975 * len(bs)) - 1]


def boot_diff(perA, perB, games, B=2000, seed=13):
    """difference of two ratios (A - B) resampling the same games for both. -> (est, lo, hi)"""
    import random
    rnd = random.Random(seed)
    gl = sorted(games)

    def ratio(per, s):
        nn = sum(per.get(g, (0, 0))[0] for g in s)
        dd = sum(per.get(g, (0, 0))[1] for g in s)
        return nn / dd if dd else None
    est = (ratio(perA, gl) or 0) - (ratio(perB, gl) or 0)
    bs = []
    for _ in range(B):
        s = rnd.choices(gl, k=len(gl))
        a, b = ratio(perA, s), ratio(perB, s)
        if a is not None and b is not None:
            bs.append(a - b)
    bs.sort()
    return est, bs[int(.025 * len(bs))], bs[int(.975 * len(bs)) - 1]


def clip(v, cap=2000):
    return max(-cap, min(cap, v))
