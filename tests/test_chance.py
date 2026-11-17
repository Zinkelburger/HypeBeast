"""Chance inside the tree (HBChance) on crafted two-board positions.

    HB_BIN=engine/src/stockfish python3 tests/test_chance.py
    HB_CHANCE_OPTS="HBChanceHorizon=1,HBChanceStable=true" ...   (extra options with chance on)

Each case is searched twice in fresh processes, with HBChance off and on
(HBWorlds off, so the root-level worlds of v4 cannot find the same idea).

(a) Their knight. Black mates us on board A with N@f2 if a knight arrives;
    White is offered a free rook (Nxa4) that does not defend.
    - injected table (-N 90%): with chance White defends, without it grabs.
    - real forecast: White on board B (their partner) wins a black knight at
      once. The exposure veto already turns Nxa4 down in both modes, so the
      check is the main search: with chance it defends by itself.
(b) Our knight. Qg8+ Rxg8 N@f7 is a smothered mate if a knight reaches us.
    - injected table (+N 90%) and real forecast (Black on board B, our
      partner, wins a white knight at once): with chance White sacrifices
      the queen, without it does not.
"""

from __future__ import annotations

import json
import os
import sys

import chess
import chess.variant

from hbutil import Engine

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1"
A_THEIRS = "1k6/ppp5/8/8/r7/2N5/PPP3PP/6RK[] w - - 0 1"
B_THEY_WIN_N = "4k3/8/8/3n4/4P3/8/8/4K3[] w - - 0 1"
A_OURS = "r4r1k/pb4pp/1p2Q3/8/2B5/8/PP3PPP/6K1[] w - - 0 1"
B_WE_WIN_N = "4k3/8/8/4p3/3N4/8/8/4K3[] b - - 0 1"
NODES = 400000

failures = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"[{'ok' if ok else 'FAIL'}] {what}" + (f": {detail}" if detail else ""))


def search(fen_a: str, fen_b: str, chance: bool, table: str = "") -> dict:
    opts = {"Seat": "Awhite", "Team": "white", "HBWorlds": "false",
            "HBChance": "true" if chance else "false"}
    if table:
        opts["HBChanceTable"] = table
    if chance:
        for kv in filter(None, os.environ.get("HB_CHANCE_OPTS", "").split(",")):
            key, value = kv.split("=", 1)
            opts[key] = value
    e = Engine(options=opts)
    try:
        e.send(f"position fen {fen_a}|{fen_b}")
        lines = e.go(f"go nodes {NODES}")
    finally:
        e.close()
    out = {"lines": lines, "table": None, "main": None, "coord": None}
    for l in lines:
        if l.startswith("info string hb_chance "):
            out["table"] = json.loads(l[len("info string hb_chance "):])
        elif l.startswith("info string hb_coord "):
            out["coord"] = json.loads(l[len("info string hb_coord "):])
        elif l.startswith("info depth") and " pv " in l and out["coord"] is None:
            out["main"] = l.split(" pv ")[1].split()[0]   # last main-search iteration
        elif l.startswith("bestmove"):
            out["best"] = l.split("(")[1].split(",")[0]
    return out


def their_knight_mates(fen_a: str, move: str) -> bool:
    """After our move on board A, can Black mate at once with a knight drop?"""
    board = chess.variant.CrazyhouseBoard(fen_a.replace("[]", "[n]"))
    board.push_uci(move)
    for m in list(board.legal_moves):
        if m.drop == chess.KNIGHT:
            board.push(m)
            mate = board.is_checkmate()
            board.pop()
            if mate:
                return True
    return False


def main() -> int:
    # ---- (a) their knight, injected
    off = search(A_THEIRS, STARTPOS, False)
    on = search(A_THEIRS, STARTPOS, True, "-N=90/90")
    check(on["table"] is not None and on["table"]["p"].get("-N") == [0.9, 0.9],
          "a/injected: table printed", json.dumps(on["table"]))
    check(off["best"] == "c3a4", "a/injected: without chance White grabs the rook", off["best"])
    check(their_knight_mates(A_THEIRS, off["best"]), "a/injected: that move allows N@f2 mate", off["best"])
    check(not their_knight_mates(A_THEIRS, on["best"]), "a/injected: with chance White defends", on["best"])

    # ---- (a) their knight, real forecast
    off = search(A_THEIRS, B_THEY_WIN_N, False)
    on = search(A_THEIRS, B_THEY_WIN_N, True)
    p = (on["table"] or {}).get("p", {}).get("-N", [0, 0])
    check(on["table"] is not None and on["table"]["source"] == "forecast" and p[0] >= 0.2,
          "a/forecast: the forecast gives Black a knight", json.dumps(on["table"]))
    check(off["main"] == "c3a4", "a/forecast: without chance the main search grabs the rook", str(off["main"]))
    check(on["main"] is not None and not their_knight_mates(A_THEIRS, on["main"]),
          "a/forecast: with chance the main search defends", str(on["main"]))
    check(not their_knight_mates(A_THEIRS, off["best"]) and not their_knight_mates(A_THEIRS, on["best"]),
          "a/forecast: both final moves defend (exposure veto without chance)",
          f"off={off['best']} ({off['coord']['reason']}) on={on['best']} ({on['coord']['reason']})")

    # ---- (b) our knight, injected and real forecast
    for name, fen_b, table in (("injected", STARTPOS, "+N=90/90"), ("forecast", B_WE_WIN_N, "")):
        off = search(A_OURS, fen_b, False)
        on = search(A_OURS, fen_b, True, table)
        p = (on["table"] or {}).get("p", {}).get("+N", [0, 0])
        check(p[0] >= 0.5, f"b/{name}: a knight is likely to reach us", json.dumps(on["table"]))
        check(off["best"] != "e6g8", f"b/{name}: without chance no queen sacrifice", off["best"])
        check(on["best"] == "e6g8", f"b/{name}: with chance Qg8+ (Rxg8 N@f7 mate)", on["best"])

    print(f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
