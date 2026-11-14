#!/usr/bin/env python3
"""Shared loading for the autopsy: games, postmortem rows, and what the engine logs add.

build() writes cache.pkl next to this file: per match, the games (from postmortem.load_games plus
events, clocks and sits) and the postmortem rows enriched with
  clocks   [aW, aB, bW, bB] ms sent before that go
  tadv     the TimeAdvantage option sent before that go (True/False/None)
  pvfull   the longest pv among the main search's last two depths (postmortem keeps the last one only)
  feat     features of the replayed position before the decision (hands, king, shelter)
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

MATCHES = {"worlds5-vs-l50": "hb-l50", "late50-vs-np-b": "hb-late50"}
PARTNER = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
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


def pocket_value(pocket):
    return sum(VAL[p] * pocket.count(p) for p in VAL)


def king_features(board, white):
    color = chess.WHITE if white else chess.BLACK
    k = board.king(color)
    if k is None:
        return {}
    rank = chess.square_rank(k)
    rel = rank if white else 7 - rank
    f = chess.square_file(k)
    d = 1 if white else -1
    shelter = 0
    for df in (-1, 0, 1):
        ff = f + df
        if not 0 <= ff <= 7:
            continue
        for dr in (1, 2):
            rr = rank + d * dr
            if 0 <= rr <= 7:
                p = board.piece_at(chess.square(ff, rr))
                if p and p.piece_type == chess.PAWN and p.color == color:
                    shelter += 1
                    break
    # enemy attacks on the 8 squares around the king and the king square
    zone = [s for s in chess.SquareSet(chess.BB_KING_ATTACKS[k])] + [k]
    att = sum(1 for s in zone if board.is_attacked_by(not color, s))
    return {"krank": rel, "shelter": shelter, "castled": f in (6, 7, 0, 1, 2) and rel == 0 and f != 4,
            "kzone_att": att, "in_check": board.is_check()}


def replay_boards(toks):
    """-> list of (boardA, boardB) copies before token i, i = 0..len(toks)"""
    b = {"1": chess.variant.CrazyhouseBoard(), "2": chess.variant.CrazyhouseBoard()}
    snaps = [(b["1"].copy(), b["2"].copy())]
    for t in toks:
        board = b[t[0]]
        mover = board.turn
        before = {p: board.pockets[mover].count(p) for p in VAL}
        board.push(chess.Move.from_uci(t[1:]))
        for p in VAL:
            if board.pockets[mover].count(p) > before[p]:
                board.pockets[mover].remove(p)
                b["2" if t[0] == "1" else "1"].pockets[not mover].add(p)
        snaps.append((b["1"].copy(), b["2"].copy()))
    return snaps


def parse_logs(d):
    """-> dict (game_first12_tuple, seat, n) -> list of extras in log order (one per go with a summary)"""
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
                block = {"pvs": [], "coord_seen": False}
            elif block is None:
                continue
            elif line.startswith("info depth ") and " pv " in line and not block["coord_seen"]:
                m = re.match(r"info depth (\d+)", line)
                block["pvs"].append((int(m.group(1)), line.split(" pv ", 1)[1].split()))
            elif line.startswith("info string hb_coord "):
                block["coord_seen"] = True
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
                out[(role, seat, tuple(moves))].append({"clocks": clocks, "tadv": tadv, "pvfull": full})
    return out


def build():
    data = {}
    for m, cand in MATCHES.items():
        d = os.path.join(REPO, "logs", m)
        games = pm.load_games(d)
        raw = {json.loads(l)["game"]: json.loads(l) for l in open(f"{d}/results.jsonl")}
        for g in games:
            r = raw[g["game"]]
            g["events"] = r["result"]["events"]
            g["clocks_end"] = r["result"]["clocks_ms"]
            g["sits"] = r["result"]["sits"]
            g["sit_ms"] = r["result"]["sit_ms"]
            g["seat_stats"] = r["seat_stats"]
            g["cand_team"] = "white" if g["seats"]["A-white"] == cand else "black"
        extras = parse_logs(d)
        rows = [json.loads(l) for l in open(f"{d}/postmortem.jsonl")]
        gby = {g["game"]: g for g in games}
        snaps = {}
        used = collections.Counter()
        for r in rows:
            g = gby[r["game"]]
            role = "contender" if g["names"]["contender"] == r["engine"] else "baseline"
            key = (role, r["seat"], tuple(g["toks"][:r["n"]]))
            i = used[key]
            used[key] += 1
            ex = extras.get(key, [])
            r.update(ex[i] if i < len(ex) else {"clocks": None, "tadv": None, "pvfull": r["pv"]})
            if r["game"] not in snaps:
                snaps[r["game"]] = replay_boards(g["toks"])
            bA, bB = snaps[r["game"]][r["n"]]
            board = bA if r["seat"][0] == "A" else bB
            other = bB if r["seat"][0] == "A" else bA
            white = seat_white(r["seat"])
            col = chess.WHITE if white else chess.BLACK
            f = {"hand_own": pocket_value(board.pockets[col]), "hand_opp": pocket_value(board.pockets[not col]),
                 "opp_q_in_hand": board.pockets[not col].count(chess.QUEEN),
                 "mat_own": sum(VAL[p.piece_type] for p in board.piece_map().values() if p.color == col and p.piece_type in VAL),
                 "mat_opp": sum(VAL[p.piece_type] for p in board.piece_map().values() if p.color != col and p.piece_type in VAL)}
            f.update(king_features(board, white))
            r["feat"] = f
        data[m] = {"games": games, "rows": rows, "cand": cand}
        print(m, len(games), "games", len(rows), "rows", "extras missing:",
              sum(1 for r in rows if r.get("clocks") is None), file=sys.stderr)
    with open(os.path.join(HERE, "cache.pkl"), "wb") as f:
        pickle.dump(data, f)
    return data


def load():
    p = os.path.join(HERE, "cache.pkl")
    if not os.path.exists(p):
        return build()
    with open(p, "rb") as f:
        return pickle.load(f)


if __name__ == "__main__":
    build()
