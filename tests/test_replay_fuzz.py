"""Both-board replay and root terminal rules vs the python referee, on
random legal games, for all four seats.

After every ply the engine is sent the arena's exact position command and
answers hbstate; every field is compared with referee.py: placement with
promotion markers, pockets, turn, castling, legal en passant, halfmove and
fullmove counters, repetition count, check, the full legal move list of
both boards, mate under both time-advantage values for both teams, draw,
and the combined verdict. Periodically hbmakeundo runs randomized
make/undo + incremental-vs-fresh NNUE checks on isolated copies.

    python3 tests/test_replay_fuzz.py --games 2000 --workers 20
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import random
import sys
import time

import chess

import hbutil
from hbutil import Bughouse, Engine, SEATS, clocks_for, compare_state, position_command, \
    referee_expectation, seat_of, team_of_seat


def pick_move(game: Bughouse, board: int, rng: random.Random) -> str:
    position = game.boards[board]
    moves = list(position.legal_moves)
    # Bias towards rare events so they are exercised often.
    promos = [m for m in moves if m.promotion]
    eps = [m for m in moves if position.is_en_passant(m)]
    caps = [m for m in moves if position.is_capture(m)]
    drops = [m for m in moves if m.drop]
    roll = rng.random()
    if promos and roll < 0.7:
        return rng.choice(promos).uci()
    if eps and roll < 0.8:
        return rng.choice(eps).uci()
    if caps and roll < 0.35:
        # Prefer capturing promoted pieces (they must transfer as pawns)
        promoted = [m for m in caps if position.promoted & chess.BB_SQUARES[m.to_square]]
        if promoted and rng.random() < 0.7:
            return rng.choice(promoted).uci()
        return rng.choice(caps).uci()
    if drops and roll < 0.55:
        return rng.choice(drops).uci()
    # Pawn pushes towards promotion now and then
    pawn_moves = [m for m in moves if not m.drop and position.piece_type_at(m.from_square) == chess.PAWN]
    if pawn_moves and roll < 0.75:
        return rng.choice(pawn_moves).uci()
    return rng.choice(moves).uci()


def random_start(rng: random.Random) -> Bughouse:
    """Start position, or a dual FEN reached by random play (real pockets,
    promoted pieces, castling changes) so the fen path is exercised too."""
    game = Bughouse()
    if rng.random() < 0.6:
        return game
    for _ in range(rng.randint(4, 60)):
        boards = [b for b in (0, 1) if game.has_legal_move(b)]
        if not boards:
            break
        b = rng.choice(boards)
        game.push(b, pick_move(game, b, rng))
        if game.is_draw() or game.is_checkmate(chess.WHITE, False) or game.is_checkmate(chess.BLACK, False):
            return Bughouse()
    return Bughouse.from_dual_fen(game.dual_fen())


def play_one(engine: Engine, seed: int, max_plies: int, makeundo_every: int) -> dict:
    rng = random.Random(seed)
    game = random_start(rng)
    seat = SEATS[seed % 4]
    engine.setoption("Seat", seat)
    engine.setoption("Team", "white" if team_of_seat(seat) == chess.WHITE else "black")
    stats = {"positions": 0, "promotions": 0, "ep": 0, "transfers": 0, "drops": 0,
             "promoted_captures": 0, "mates": 0, "draws": 0, "checks": 0,
             "rep2": 0, "makeundo": 0, "diffs": [], "seed": seed}

    def check() -> bool:
        adv_w, adv_b = rng.random() < 0.5, rng.random() < 0.5
        clocks = clocks_for(adv_w, adv_b)
        engine.setoption("Clocks", ",".join(map(str, clocks)))
        team = team_of_seat(seat)
        engine.setoption("TimeAdvantage", "true" if (adv_w if team == chess.WHITE else adv_b) else "false")
        engine.send(position_command(game))
        state = engine.hbstate()
        expect = referee_expectation(game, clocks)
        diffs = compare_state(state, expect, seat)
        stats["positions"] += 1
        stats["checks"] += any(b["in_check"] for b in expect["boards"])
        stats["rep2"] += any(b["repetitions"] >= 2 for b in expect["boards"])
        if diffs:
            stats["diffs"].append({"seed": seed, "seat": seat, "position": position_command(game),
                                   "clocks": clocks, "diffs": diffs[:8]})
            return False
        return expect["verdict"] == "none"

    if not check():
        return stats
    for ply in range(max_plies):
        boards = [b for b in (0, 1) if game.has_legal_move(b)]
        if not boards:
            break
        b = rng.choice(boards)
        uci = pick_move(game, b, rng)
        move = chess.Move.from_uci(uci)
        position = game.boards[b]
        stats["promotions"] += bool(move.promotion)
        stats["ep"] += position.is_en_passant(move)
        stats["drops"] += bool(move.drop)
        if position.is_capture(move):
            stats["transfers"] += 1
            if not position.is_en_passant(move) and position.promoted & chess.BB_SQUARES[move.to_square]:
                stats["promoted_captures"] += 1
        game.push(b, uci)
        alive = check()
        if stats["diffs"]:
            break
        if makeundo_every and ply % makeundo_every == makeundo_every - 1:
            engine.send(f"hbmakeundo iterations 4 plies 8 seed {seed * 1000 + ply + 1}")
            line = engine.read_until("hbmakeundo ")[-1]
            stats["makeundo"] += 1
            if not line.startswith("hbmakeundo ok"):
                stats["diffs"].append({"seed": seed, "position": position_command(game),
                                       "diffs": [line]})
                break
        if not alive:
            v = referee_expectation(game, (0, 0, 0, 0))["verdict"]
            stats["mates"] += v.endswith("mated")
            stats["draws"] += v == "draw"
            break
    return stats


def worker(args) -> dict:
    seeds, max_plies, makeundo_every = args
    engine = Engine()
    total = {}
    try:
        for seed in seeds:
            stats = play_one(engine, seed, max_plies, makeundo_every)
            for k, v in stats.items():
                if k == "diffs":
                    total.setdefault("diffs", []).extend(v)
                elif k != "seed":
                    total[k] = total.get(k, 0) + v
            total["games"] = total.get("games", 0) + 1
    finally:
        engine.close()
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--max-plies", type=int, default=300)
    ap.add_argument("--makeundo-every", type=int, default=15)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    seeds = list(range(args.seed, args.seed + args.games))
    chunks = [seeds[i::args.workers] for i in range(args.workers) if seeds[i::args.workers]]
    started = time.time()
    with mp.Pool(len(chunks)) as pool:
        results = pool.map(worker, [(c, args.max_plies, args.makeundo_every) for c in chunks])
    total = {}
    diffs = []
    for r in results:
        diffs.extend(r.pop("diffs", []))
        for k, v in r.items():
            total[k] = total.get(k, 0) + v
    total["seconds"] = round(time.time() - started, 1)
    print("replay fuzz:", " ".join(f"{k}={v}" for k, v in sorted(total.items())))
    for d in diffs[:10]:
        print("DIFF", d)
    print("RESULT", "PASS" if not diffs else f"FAIL ({len(diffs)} games with differences)")
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main())
