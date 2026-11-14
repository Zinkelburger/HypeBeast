#!/usr/bin/env python3
"""When do we get mated? King-safety features at every decision, against what followed.

usage: hazard.py OUT_JSON MATCH_DIR [MATCH_DIR ...]
Pure Python over results.jsonl. After each move a seat plays, the opponent is on
turn; the features describe the position that seat just handed over.
"""
import collections
import json
import multiprocessing as mp
import statistics
import sys

sys.dont_write_bytecode = True
import chess  # noqa: E402

from losses import TEAM, Replay, bad  # noqa: E402

TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
LET = {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q"}
HORIZON_S = 20_000  # "soon" = forced mate seen within this much game time


def drop_mates(board, color, piece):
    """Squares where `color` dropping `piece` mates now, as if it held one.
    The board is one where `color` is on turn. The defender's own hand can block."""
    out = []
    empties = ~board.occupied & chess.BB_ALL
    if piece == chess.PAWN:
        empties &= ~(chess.BB_RANK_1 | chess.BB_RANK_8)
    king = board.king(not color)
    if king is None:
        return out
    b = board.copy(stack=False)
    had = b.pockets[color].count(piece)
    if had == 0:
        b.pockets[color].add(piece)
    for sq in chess.scan_forward(empties):
        # only squares that give check can mate
        probe = chess.Piece(piece, color)
        attacks = chess.BaseBoard.attacks_mask
        b2 = b.copy(stack=False)
        b2.push(chess.Move(sq, sq, drop=piece))
        if b2.is_check() and b2.is_checkmate():
            out.append(sq)
    return out


def features(board, seat_white):
    """Features of `board`, the opponent on turn, for the seat that just moved."""
    me = seat_white
    king = board.king(me)
    opp = not me
    rank = chess.square_rank(king)
    home = 0 if me else 7
    ring = chess.BB_KING_ATTACKS[king]
    ring_list = list(chess.scan_forward(ring))
    attacked = sum(1 for s in ring_list if board.is_attacked_by(opp, s))
    empty_ring = sum(1 for s in ring_list if board.piece_at(s) is None)
    # own pawns in the three squares ahead of the king
    step = 1 if me else -1
    shield = 0
    f = chess.square_file(king)
    r2 = rank + step
    if 0 <= r2 <= 7:
        for df in (-1, 0, 1):
            if 0 <= f + df <= 7:
                p = board.piece_at(chess.square(f + df, r2))
                if p and p.color == me and p.piece_type == chess.PAWN:
                    shield += 1
    escapes = 0
    for s in ring_list:
        p = board.piece_at(s)
        if (p is None or p.color == opp) and not board.is_attacked_by(opp, s):
            escapes += 1
    short = {}
    for pt in TYPES:
        short[LET[pt]] = len(drop_mates(board, opp, pt))
    return {"off_home": abs(rank - home), "attacked_ring": attacked, "empty_ring": empty_ring,
            "shield": shield, "escapes": escapes, "short": short,
            "opp_hand": {LET[pt]: board.pockets[opp].count(pt) for pt in TYPES},
            "my_hand_val": sum(board.pockets[me].count(pt) * v for pt, v in zip(TYPES, (1, 3, 3, 5, 9))),
            "opp_hand_val": sum(board.pockets[opp].count(pt) * v for pt, v in zip(TYPES, (1, 3, 3, 5, 9)))}


def game_rows(line):
    r = json.loads(line)
    res = r["result"]
    rp = Replay(r["opening"]["dual_fen"])
    for m in r["opening"]["moves"]:
        rp.push("A" if m[0] == "1" else "B", m[1:])
    ev = res["events"]
    winner = res["winner"]
    team_of = {s: t for t, ss in TEAM.items() for s in ss}
    # when each seat first stands mated by force, to its last decision
    seen = {}
    for s in r["seats"]:
        dec = [e for e in ev if e.get("seat") == s and e["kind"] in ("move", "sit") and e.get("eval") is not None]
        k = len(dec)
        while k > 0 and bad(dec[k - 1]["eval"]):
            k -= 1
        if k < len(dec):
            seen[s] = dec[k]["t"]
    final_mated = None
    moves = [e for e in ev if e["kind"] == "move"]
    if res["termination"] == "checkmate":
        l = moves[-1]
        final_mated = f"{l['board']}-{'black' if l['seat'].endswith('white') else 'white'}"
    rows = []
    for e in ev:
        if e["kind"] != "move":
            continue
        rp.push(e["board"], e["uci"])
        board = rp.b[e["board"]]
        if board.is_game_over():
            continue
        seat = e["seat"]
        if seat in seen and e["t"] >= seen[seat]:
            continue  # already standing mated: the question is what comes before
        white = seat.endswith("white")
        other = rp.b["B" if e["board"] == "A" else "A"]
        f = features(board, white)
        # the opponent's partner plays the colour opposite to the opponent on the other board
        wp_white = white  # the partner of our opponent plays our colour on the other board
        caps = collections.Counter()
        if other.turn == wp_white:
            for m in other.legal_moves:
                if not m.drop and other.is_capture(m):
                    v = other.piece_at(m.to_square)
                    if v:
                        pt = chess.PAWN if other.promoted & chess.BB_SQUARES[m.to_square] else v.piece_type
                        caps[LET[pt]] += 1
        f["wp_on_turn"] = other.turn == wp_white
        f["partner_caps"] = dict(caps)
        f.update(game=r["game"], seat=seat, engine=r["seats"][seat], t=e["t"], uci=e["uci"], in_check=board.is_check(),
                 eval=e["eval"], won=team_of[seat] == winner, draw=winner not in TEAM, end=res["duration_ms"],
                 seen=seen.get(seat), mated_this_seat=final_mated == seat,
                 ply=sum(1 for x in moves if x["t"] <= e["t"]))
        rows.append(f)
    return rows


def main():
    out = sys.argv[1]
    lines = []
    for d in sys.argv[2:]:
        tag = d.rstrip("/").split("/")[-1]
        for l in open(f"{d}/results.jsonl"):
            x = json.loads(l)
            x["game"] = f"{tag}:{x['game']}"
            lines.append(json.dumps(x))
    with mp.Pool(3) as pool:
        rows = [r for g in pool.imap(game_rows, lines, chunksize=4) for r in g]
    json.dump(rows, open(out, "w"))
    print("decisions", len(rows), "games", len(lines))


if __name__ == "__main__":
    main()
