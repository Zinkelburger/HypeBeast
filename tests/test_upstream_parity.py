"""Upstream parity with HypeBeast off, contract options, NNUE loading, and
the frozen-hand gate with HypeBeast on.

    python3 tests/test_upstream_parity.py
"""

from __future__ import annotations

import random
import subprocess
import sys

import chess
from chess.variant import CrazyhouseBoard

import hbutil
from hbutil import Bughouse, Engine, FSF_REF, HYPEBEAST, NET, ROOT

failures = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"[{'ok' if ok else 'FAIL'}] {what}" + (f": {detail}" if detail else ""))


def bench(binary, *args) -> str:
    out = subprocess.run([str(binary), "bench", *args], capture_output=True, text=True, timeout=900)
    return [l for l in (out.stdout + out.stderr).splitlines() if l.startswith("Nodes searched")][0]


def sample_positions(n: int, seed: int = 7) -> list[str]:
    """Single-board bughouse FENs with real pockets from random two-board play."""
    rng = random.Random(seed)
    fens = [CrazyhouseBoard.starting_fen]
    while len(fens) < n:
        game = Bughouse()
        for ply in range(rng.randint(10, 80)):
            boards = [b for b in (0, 1) if game.has_legal_move(b)]
            if not boards:
                break
            b = rng.choice(boards)
            moves = game.legal_moves(b)
            game.push(b, rng.choice(moves))
            if game.is_checkmate(chess.WHITE, False) or game.is_checkmate(chess.BLACK, False):
                break
        for b in (0, 1):
            if game.has_legal_move(b) and len(fens) < n:
                fens.append(game.boards[b].fen())
    return fens


def plain_search(binary, fen: str, nodes: int) -> tuple[str, str]:
    e = Engine(binary, hypebeast=False)
    e.send("ucinewgame")
    e.send(f"position fen {fen}")
    lines = e.go(f"go nodes {nodes}")
    e.close()
    info = [l for l in lines if l.startswith("info depth") and " score " in l][-1]
    score = info.split(" score ")[1].split(" nodes ")[0]
    return lines[-1], f"{score} {info.split(' nodes ')[1].split()[0]}"


def static_eval(binary, fen: str) -> str:
    e = Engine(binary, hypebeast=False)
    e.send(f"position fen {fen}")
    e.send("eval")
    lines = e.read_until("Final evaluation")
    e.close()
    return [l for l in lines if l.startswith("NNUE evaluation")][0]


def legal_pv(fen: str, pv: list[str]) -> bool:
    """Replay a PV with frozen hands: drops need a real pocket piece and
    captures leave the board (bughouse), never refilling a pocket."""
    board = CrazyhouseBoard(fen)
    for uci in pv:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            return False
        mover = board.turn
        captured = None
        if board.is_en_passant(move):
            captured = chess.PAWN
        elif not move.drop and board.piece_type_at(move.to_square):
            captured = chess.PAWN if board.promoted & chess.BB_SQUARES[move.to_square] \
                else board.piece_type_at(move.to_square)
        board.push(move)
        if captured:
            board.pockets[mover].remove(captured)
    return True


def main() -> int:
    for args in ((), ("bughouse",), ("crazyhouse",)):
        a, b = bench(FSF_REF, *args), bench(HYPEBEAST, *args)
        check(a == b, f"bench {' '.join(args) or 'default'} identical", f"ref '{a}' hb '{b}'")

    # Contract options
    e = Engine(HYPEBEAST, hypebeast=False, net=None)
    opts = [l for l in e.uci_lines if l.startswith("option name ")]
    e.close()
    want = ["option name HypeBeast type check default false",
            "option name Coordination type check default true",
            "option name Seat type combo default Awhite var Awhite var Ablack var Bwhite var Bblack",
            "option name Team type combo default white var white var black",
            "option name TimeAdvantage type check default false"]
    for w in want:
        check(w in opts, f"advertised: {w}")
    check(any(l.rstrip() == "option name Clocks type string default" for l in opts),
          "advertised: option name Clocks type string default")

    # Bughouse fixed-node agreement (HypeBeast off) and identical static NNUE
    fens = sample_positions(12)
    agree = 0
    for fen in fens:
        ra, rb = plain_search(FSF_REF, fen, 40000), plain_search(HYPEBEAST, fen, 40000)
        agree += ra == rb
        if ra != rb:
            print("   differs:", fen, ra, rb)
    check(agree == len(fens), "bughouse fixed-node bestmove/score/nodes agreement", f"{agree}/{len(fens)}")
    same = sum(static_eval(FSF_REF, f) == static_eval(HYPEBEAST, f) for f in fens)
    check(same == len(fens), "identical static NNUE evaluation", f"{same}/{len(fens)}")

    # Active NNUE loading, both binaries and HypeBeast mode
    for binary, hb in ((FSF_REF, False), (HYPEBEAST, False), (HYPEBEAST, True)):
        e = Engine(binary, hypebeast=hb, options={"Seat": "Awhite", "Team": "white"} if hb else None)
        e.send("position startpos")
        lines = e.go("go nodes 2000")
        e.close()
        loaded = any(l == f"info string NNUE evaluation using {NET} enabled" for l in lines)
        check(loaded, f"NNUE active: {binary.name} HypeBeast={hb}")
    # A non-bughouse net is never silently swapped in: classical fallback is reported
    e = Engine(HYPEBEAST, hypebeast=True, net=None, options={"Seat": "Awhite"})
    e.send("position startpos")
    lines = e.go("go nodes 2000")
    e.close()
    check(any("hb_error nnue_inactive" in l for l in lines), "missing net reported as hb_error")

    # Frozen hands: upstream PVs contain virtual drops, HypeBeast PVs never do
    def pvs(binary, hb, fen_or_cmd):
        e = Engine(binary, hypebeast=hb, options={"Seat": "Ablack", "Team": "black"} if hb else None)
        e.send(fen_or_cmd)
        lines = e.go("go movetime 1500")
        e.close()
        return [l.split(" pv ")[1].split() for l in lines if l.startswith("info depth") and " pv " in l]
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR[] b KQkq - 0 1"
    ref_bad = sum(not legal_pv(fen, pv) for pv in pvs(FSF_REF, False, f"position fen {fen}"))
    hb_lines = pvs(HYPEBEAST, True, "position startpos moves 1e2e4")
    hb_bad = sum(not legal_pv(fen, pv) for pv in hb_lines)
    check(ref_bad > 0, "upstream PVs use virtual drops (detector works)", f"{ref_bad} PVs")
    check(hb_bad == 0 and hb_lines, "HypeBeast PVs use only physical drops", f"{len(hb_lines)} PVs checked")

    print("RESULT", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
