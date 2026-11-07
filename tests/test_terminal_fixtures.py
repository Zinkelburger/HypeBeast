"""Root terminal fixtures: engine hbstate vs referee.py on crafted positions.

Each fixture also asserts what the referee itself says, so a fixture that
does not test what its name claims fails loudly instead of passing vacuously.

    python3 tests/test_terminal_fixtures.py
"""

from __future__ import annotations

import sys

import chess

from hbutil import (Bughouse, Engine, clocks_for, compare_state, parse_bestmove,
                    position_command, referee_expectation, summary_fields)

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1"

# Board A, black to move, in check, no legal move.
A_PAWN_BLOCKABLE = "6rk/6p1/8/8/8/8/8/K6R[] b - - 0 1"   # rook h1: h2..h7 blockable
A_BACK_RANK = "R6k/6pp/8/8/8/8/8/K7[] b - - 0 1"         # rook a8: only rank-8 squares
A_KNIGHT = "6rk/5Npp/8/8/8/8/8/K7[] b - - 0 1"           # smothered: unblockable
A_DOUBLE = "R6k/5Npp/8/8/8/8/8/K7[] b - - 0 1"           # rook + knight
A_CONTACT = "7k/6Q1/5K2/8/8/8/8/8[] b - - 0 1"           # adjacent queen
A_STALEMATE = "7k/5Q2/6K1/8/8/8/8/8[] b - - 0 1"         # black: no moves, not in check

# Board B. Partner of black-on-A is white-on-B.
B_W_CAPTURES_KNIGHT = "k7/8/8/8/8/8/n7/1K6[] w - - 0 1"
B_W_CAPTURES_PAWN = "k7/8/8/8/8/8/p7/1K6[] w - - 0 1"
B_W_NO_CAPTURE = "k7/8/8/8/8/8/8/1K6[] w - - 0 1"
B_W_STALEMATE = "k7/8/8/8/8/1q6/8/K7[] w - - 0 1"
# Black to move on B; every black reply leaves white Rxb7 (knight).
B_B_ALL_REPLIES_KEEP = "1k6/1n6/8/8/8/8/8/1R5K[] b - - 0 1"
# Black to move on B; Nb7 can run away, so not every reply keeps a capture.
B_B_SOME_REPLY_ESCAPES = "1k6/1n6/8/8/8/8/8/R6K[] b - - 0 1"

FIXTURES = [
    # name, fenA, fenB, moves, adv_white, adv_black, expected referee facts
    ("pawn-blockable, partner on turn with knight capture", A_PAWN_BLOCKABLE, B_W_CAPTURES_KNIGHT,
     [], False, False, {"black_mated": False}),
    ("pawn-blockable, partner on turn with pawn capture", A_PAWN_BLOCKABLE, B_W_CAPTURES_PAWN,
     [], False, False, {"black_mated": False}),
    ("pawn-blockable, partner on turn without capture", A_PAWN_BLOCKABLE, B_W_NO_CAPTURE,
     [], False, False, {"black_mated": True}),
    ("back rank, partner can only capture a pawn", A_BACK_RANK, B_W_CAPTURES_PAWN,
     [], False, False, {"black_mated": True}),
    ("back rank, partner captures a knight", A_BACK_RANK, B_W_CAPTURES_KNIGHT,
     [], False, False, {"black_mated": False}),
    ("knight check unblockable", A_KNIGHT, B_W_CAPTURES_KNIGHT,
     [], True, True, {"black_mated": True}),
    ("double check", A_DOUBLE, B_W_CAPTURES_KNIGHT,
     [], True, True, {"black_mated": True}),
    ("contact check", A_CONTACT, B_W_CAPTURES_KNIGHT,
     [], True, True, {"black_mated": True}),
    ("partner not on turn, no time advantage", A_PAWN_BLOCKABLE, B_B_ALL_REPLIES_KEEP,
     [], False, False, {"black_mated": True}),
    ("partner not on turn, up on time, every reply keeps a capture", A_PAWN_BLOCKABLE,
     B_B_ALL_REPLIES_KEEP, [], False, True, {"black_mated": False}),
    ("partner not on turn, up on time, a reply removes the capture", A_PAWN_BLOCKABLE,
     B_B_SOME_REPLY_ESCAPES, [], False, True, {"black_mated": True}),
    ("no moves on both boards (both on turn) even up on time", A_STALEMATE, B_W_STALEMATE,
     [], False, True, {"black_mated": True}),
    ("no move on A, off turn on B, not up on time", A_STALEMATE, B_B_ALL_REPLIES_KEEP,
     [], False, False, {"black_mated": True}),
    ("no move on A, off turn on B, up on time: waits", A_STALEMATE, B_B_ALL_REPLIES_KEEP,
     [], False, True, {"black_mated": False}),
    ("in check on A, partner stalemated on B", A_PAWN_BLOCKABLE, B_W_STALEMATE,
     [], False, True, {"black_mated": True}),
    # time-advantage flip on the same position
    ("advantage flip off", A_PAWN_BLOCKABLE, B_B_ALL_REPLIES_KEEP, [], True, False,
     {"black_mated": True}),
    ("advantage flip on", A_PAWN_BLOCKABLE, B_B_ALL_REPLIES_KEEP, [], False, True,
     {"black_mated": False}),
    # draws
    ("fifty moves by a quiet move", "4k3/8/8/8/8/8/8/R3K3[] w - - 99 60", START,
     ["1a1a2"], False, False, {"draw": True}),
    ("drops do not reset the referee's clock", "4k3/8/8/8/8/8/8/R3K3[N] w - - 98 60", START,
     ["1N@c3", "1e8d8"], False, False, {"draw": True}),
    ("a capture resets the clock", "4k3/8/8/8/8/8/p7/R3K3[] w - - 99 60", START,
     ["1a1a2"], False, False, {"draw": False}),
    ("threefold repetition on A", START, START,
     ["1g1f3", "1g8f6", "1f3g1", "1f6g8", "1g1f3", "1g8f6", "1f3g1", "1f6g8"],
     False, False, {"draw": True}),
    ("twofold is not a draw", START, START,
     ["1g1f3", "1g8f6", "1f3g1", "1f6g8"], False, False, {"draw": False}),
    ("repetition ignores pockets (transfers from B in between)", START, START,
     ["1g1f3", "2e2e4", "1g8f6", "2d7d5", "1f3g1", "2e4d5", "1f6g8", "1g1f3", "1g8f6",
      "1f3g1", "2d8d5", "1f6g8"], False, False, {"draw": True}),
    ("repetition on B", START, START,
     ["2g1f3", "2g8f6", "2f3g1", "2f6g8", "2g1f3", "2g8f6", "2f3g1", "2f6g8"],
     False, False, {"draw": True}),
]


def build(fen_a: str, fen_b: str, moves: list[str]) -> Bughouse:
    game = Bughouse(fen_a, fen_b)
    for token in moves:
        game.push(int(token[0]) - 1, token[1:])
    return game


def main() -> int:
    engine = Engine(options={"Seat": "Ablack", "Team": "black"})
    failures = 0
    for name, fen_a, fen_b, moves, adv_w, adv_b, facts in FIXTURES:
        game = build(fen_a, fen_b, moves)
        clocks = clocks_for(adv_w, adv_b)
        expect = referee_expectation(game, clocks)
        problems = []
        if "black_mated" in facts:
            got = game.is_checkmate(chess.BLACK, adv_b)
            if got != facts["black_mated"]:
                problems.append(f"fixture broken: referee black mated={got}")
        if "draw" in facts and game.is_draw() != facts["draw"]:
            problems.append(f"fixture broken: referee draw={game.is_draw()}")
        engine.setoption("Clocks", ",".join(map(str, clocks)))
        engine.setoption("TimeAdvantage", "true" if adv_b else "false")
        engine.send(position_command(game))
        state = engine.hbstate()
        problems += compare_state(state, expect, "Ablack")
        status = "ok" if not problems else "FAIL"
        failures += bool(problems)
        print(f"[{status}] {name}: verdict={state['verdict']} mate={state['mate']} draw={state['draw']}")
        for p in problems:
            print("      ", p)

    # Mandatory wait: our seat has no legal move but the game goes on -> pass.
    game = build(A_PAWN_BLOCKABLE, B_W_CAPTURES_KNIGHT, [])
    engine.setoption("Clocks", ",".join(map(str, clocks_for(False, False))))
    engine.setoption("TimeAdvantage", "false")
    engine.send(position_command(game))
    lines = engine.go("go movetime 200")
    a, b = parse_bestmove(lines)
    s = summary_fields(lines)
    ok = (a, b) == ("pass", "pass") and s.get("reason") == "no_legal_moves" and s.get("verdict") == "none"
    failures += not ok
    print(f"[{'ok' if ok else 'FAIL'}] mandatory wait returns pass: {lines[-1]} reason={s.get('reason')}")

    # Not on turn on our board -> pass, and the other half is pass as well.
    engine.setoption("Seat", "Bblack")
    engine.setoption("Team", "white")
    lines = engine.go("go nodes 1000")
    ok = parse_bestmove(lines) == ("pass", "pass")
    failures += not ok
    print(f"[{'ok' if ok else 'FAIL'}] seat not on turn passes: {lines[-1]}")

    # Seat/Team mismatch: hb_error and still a legal answer.
    engine.setoption("Seat", "Bwhite")
    engine.setoption("Team", "white")   # Bwhite belongs to team black
    lines = engine.go("go nodes 2000")
    err = any(l.startswith("info string hb_error seat_team_mismatch") for l in lines)
    a, b = parse_bestmove(lines)
    legal = b in game.legal_moves(1)
    ok = err and a == "pass" and legal
    failures += not ok
    print(f"[{'ok' if ok else 'FAIL'}] seat/team mismatch reported and legal: {lines[-1]} hb_error={err}")

    engine.close()
    print("RESULT", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
