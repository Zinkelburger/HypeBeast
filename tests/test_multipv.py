"""MultiPV with Coordination=false: every line is searched in every iteration.

    python3 tests/test_multipv.py

The page's one-board analysis (and the desktop app) sets Coordination=false
and MultiPV=N. The main search must then run N root searches per iteration
(hb_arena passes the count to run_main_search). A build without that prints
N lines but searches one: lines 2..N stay at depth-1 with seldepth 1, score 0
and a stale move. Each completed iteration (every block of N lines but the
last, which a stop cuts short) must show N lines at one depth, seldepth > 1,
scores in descending order, distinct first moves and PVs legal on the board
(seldepth > 1 from depth 2 on: a depth-1 iteration is one ply, as upstream).
"""

from __future__ import annotations

import re
import sys
import time

from hbutil import Bughouse, Engine, parse_bestmove, seat_of, team_of_seat

failures = 0

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1"

INFO = re.compile(r"^info depth (\d+) seldepth (\d+) multipv (\d+) score (cp|mate) (-?\d+)"
                  r"( lowerbound| upperbound)?.* pv (.*)$")


def check(ok: bool, what: str, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"[{'ok' if ok else 'FAIL'}] {what}" + (f": {detail}" if detail else ""))


def order_value(kind: str, n: int) -> int:
    if kind == "cp":
        return n
    return 100000 - n if n > 0 else -100000 - n


def parse_lines(lines: list[str]) -> list[dict]:
    out = []
    for line in lines:
        m = INFO.match(line)
        if m:
            out.append({"depth": int(m[1]), "seldepth": int(m[2]), "k": int(m[3]),
                        "kind": m[4], "score": int(m[5]), "bound": (m[6] or "").strip(),
                        "pv": m[7].split(), "line": line})
    return out


def blocks_of(infos: list[dict]) -> list[list[dict]]:
    blocks: list[list[dict]] = []
    for info in infos:
        if info["k"] == 1 or not blocks:
            blocks.append([])
        blocks[-1].append(info)
    return blocks


def pv_legal(game: Bughouse, board: int, pv: list[str]) -> str:
    g = game.copy()
    for i, move in enumerate(pv):
        if not g.is_legal(board, move):
            return f"ply {i + 1} {move} illegal after {' '.join(pv[:i])}"
        g.push(board, move)
    return ""


def block_problems(block: list[dict], expected: int, game: Bughouse, board: int) -> list[str]:
    bad = []
    if [b["k"] for b in block] != list(range(1, expected + 1)):
        bad.append(f"lines {[b['k'] for b in block]}, expected 1..{expected}")
    depths = {b["depth"] for b in block}
    if len(depths) != 1:
        bad.append(f"depths {[b['depth'] for b in block]}")
    for b in block:
        # a depth-1 root search is one ply: seldepth 1 there, as upstream
        if b["depth"] > 1 and b["seldepth"] <= 1:
            bad.append(f"line {b['k']} seldepth {b['seldepth']}")
        # UCI::pv labels index pvIdx (line N) against line N's last window
        # after the lines are sorted, so a line that moved down into slot N
        # can carry a bound it does not have (upstream does the same).
        if b["bound"] and b["k"] != expected:
            bad.append(f"line {b['k']} {b['bound']}")
        why = pv_legal(game, board, b["pv"])
        if why:
            bad.append(f"line {b['k']} pv {why}")
    values = [order_value(b["kind"], b["score"]) for b in block]
    if values != sorted(values, reverse=True):
        bad.append(f"scores not descending {[(b['kind'], b['score']) for b in block]}")
    firsts = [b["pv"][0] if b["pv"] else "" for b in block]
    if len(set(firsts)) != len(firsts):
        bad.append(f"first moves repeat {firsts}")
    return bad


def analyse(e: Engine, game: Bughouse, seat: str, multipv: int, go: str,
            stop_after: float | None = None) -> list[str]:
    e.setoption("Seat", seat)
    e.setoption("Team", "white" if team_of_seat(seat) else "black")
    e.setoption("MultiPV", multipv)
    e.sync()
    moves = " ".join(game.engine_moves())
    if game.moves:
        e.send(f"position startpos moves {moves}")
    else:
        e.send(f"position fen {game.dual_fen()}")
    if stop_after is None:
        return e.go(go)
    e.send(go)
    time.sleep(stop_after)
    e.send("stop")
    return e.read_until("bestmove")


def run_case(e: Engine, name: str, game: Bughouse, seat: str, multipv: int, go: str,
             stop_after: float | None = None, want_drop: bool = False,
             want_mate1: bool = False, verbose: bool = False) -> dict:
    board, colour = seat_of(seat)
    assert game.turn(board) == colour, f"{name}: {seat} is not on turn"
    expected = min(multipv, len(game.legal_moves(board)))
    lines = analyse(e, game, seat, multipv, go, stop_after)
    blocks = blocks_of(parse_lines(lines))
    complete = blocks[:-1]   # the last block is the iteration the stop cut short
    # A search longer than 3 s prints after every line; only the block that
    # ends an iteration (all lines at one depth) is a completed iteration.
    complete = [b for b in complete if len(b) == expected and len({x["depth"] for x in b}) == 1]
    problems = []
    for b in blocks[:-1]:
        if len(b) == expected and b[-1]["depth"] != b[0]["depth"]:
            # a block where line N is still at depth-1 must be followed by
            # more lines at the same depth (the >3 s partial prints)
            later = [x for x in blocks[blocks.index(b) + 1:] if x[0]["depth"] == b[0]["depth"]]
            if not later:
                problems.append(f"depth {b[0]['depth']}: lines at {[x['depth'] for x in b]}, "
                                f"seldepth {[x['seldepth'] for x in b]}")
    depths = sorted({b[0]["depth"] for b in complete})
    for b in complete:
        for p in block_problems(b, expected, game, board):
            problems.append(f"depth {b[0]['depth']}: {p}")
    if not complete:
        problems.append("no completed iteration with every line searched")
    elif depths != list(range(1, depths[-1] + 1)):
        problems.append(f"completed depths not contiguous: {depths}")
    a, b_ = parse_bestmove(lines)
    ours = a if board == 0 else b_
    if complete and ours != blocks[-1][0]["pv"][0] and ours != complete[-1][0]["pv"][0]:
        problems.append(f"bestmove {ours} is neither line 1 of the last iteration nor of the last block")
    if want_drop and not any("@" in m for blk in complete for x in blk for m in x["pv"]):
        problems.append("no drop in any line")
    if want_mate1 and complete and (complete[-1][0]["kind"], complete[-1][0]["score"]) != ("mate", 1):
        problems.append(f"line 1 is not mate 1: {complete[-1][0]['line']}")
    fed = [l for l in lines if l.startswith("info string hb_fed")]
    detail = (f"{len(complete)} iterations, depth {depths[-1] if depths else 0}, "
              f"{expected} lines, last block {[(x['depth'], x['kind'], x['score']) for x in blocks[-1]]}")
    check(not problems, f"{name} MultiPV={multipv} {go}" + (f" stop@{stop_after}s" if stop_after else ""),
          detail if not problems else "; ".join(problems[:4]))
    if verbose:
        for x in blocks[-1]:
            print("    last:", x["line"])
    return {"complete": complete, "last": blocks[-1], "fed": fed, "lines": lines}


def game_from(prefix: list[str] | None = None, fen_a: str = START, fen_b: str = START) -> Bughouse:
    g = Bughouse(fen_a, fen_b)
    for tok in prefix or []:
        g.push(int(tok[0]) - 1, tok[1:])
    return g


OPENING = ["1e2e4", "2d2d4", "1e7e5", "2d7d5", "1g1f3"]
CASES = [
    # name, game, seat, flags
    ("mate in one", lambda: game_from(fen_a="6k1/5ppp/8/8/8/8/5PPP/4R1K1[] w - - 0 1"),
     "Awhite", {"want_mate1": True}),
    ("two legal moves", lambda: game_from(fen_a="k7/8/8/8/8/8/8/K6r[] w - - 0 1"), "Awhite", {}),
    ("in check, drops", lambda: game_from(
        fen_a="rnb1kbnr/pppp1ppp/8/4p3/4P2q/5P2/PPPP2PP/RNBQKBNR[Nn] w KQkq - 1 3"), "Awhite", {}),
    ("pieces in hand", lambda: game_from(
        fen_a="r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R[BNPbp] w KQkq - 2 3"),
     "Awhite", {"want_drop": True}),
]


def main() -> int:
    e = Engine(options={"Coordination": "false", "Threads": 1, "Hash": 64})
    try:
        opening = game_from(OPENING)
        for n in (2, 3, 5):
            run_case(e, "opening", opening, "Ablack", n, "go nodes 200000")
        run_case(e, "opening", opening, "Ablack", 3, "go movetime 1000")
        run_case(e, "opening", opening, "Ablack", 3, "go infinite", stop_after=1.0)
        for name, make, seat, flags in CASES:
            run_case(e, name, make(), seat, 3 if name != "two legal moves" else 5,
                     "go nodes 100000", **flags)
        # Coordination=false prints no feed prices; with them on, every hb_fed
        # line must follow the info line of the same multipv.
        r = run_case(e, "opening", opening, "Ablack", 3, "go nodes 50000")
        check(not r["fed"], "no hb_fed lines without coordination", f"{len(r['fed'])} lines")
    finally:
        e.close()
    print(f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
