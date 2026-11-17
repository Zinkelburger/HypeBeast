"""Referee draws (HBAvoidDraw, HBSeekDraw) on three real games.

    HB_BIN=engine/src/stockfish python3 tests/test_draw.py

In logs/basefix-vs-hm-n1500 (base at 4.5M nodes against HiveMind at 1500)
all three draws were the referee's threefold repetition of the board with the
pockets ignored, forced by HiveMind from lost positions with a drop/capture
cycle. Each case is our last move before the draw, searched in fresh
processes with the option off and on (1M nodes):

  game 4  (A-white): g4h3 lets Black drop a pawn on g4 for the third
          occurrence, a pawn that only arrives after HiveMind's partner takes
          on d5 on board B (move 2c3d5 of the game).
  game 13 (B-white): our capture e3f2 completes the threefold itself.
  game 14 (B-black): our capture f5e6 completes the threefold itself.

Off must reproduce the drawing line; on must choose a move after which the
python referee finds no draw, neither at once nor after any reply on our board
(for game 4 also after the game's partner-board continuation). The seek-draw
case is game 4 from HiveMind's side: Black, lost, may draw with P@g4.
"""

from __future__ import annotations

import sys

from hbutil import Bughouse, Engine, parse_bestmove

NODES = 1_000_000
GAMES = {
    "game4": {
      "seat": "Awhite", "played": "1g4h3", "after": ["2c3d5", "1P@g4"],
      "clocks": [92474, 89399, 92207, 89666], "advantage": True,
      "prefix": [
        "2e2e4", "1e2e4", "2e7e6", "1b7b6", "2b1c3", "2d7d5", "1b1c3", "2e4d5", "2e6d5",
        "1c8b7", "2f1b5", "2b8c6", "1g1f3", "2d1e2", "1e7e6", "2f8e7", "2d2d4", "1f1e2",
        "2g8f6", "1g8f6", "2g1f3", "1e4e5", "2e8g8", "1f6g4", "2b5c6", "1e1g1", "2b7c6",
        "1N@f4", "2f3e5", "1d2d4", "2d8d6", "1f4e2", "2B@c5", "1d1e2", "2d6c5", "2d4c5",
        "1P@h3", "1g2h3", "2e7c5", "2e5c6", "1P@g2", "1g1g2", "2c8g4", "2f2f3", "2P@f2",
        "2e2f2", "1g4e5", "2c5f2", "1d4e5", "2e1f2", "1P@g4", "2g4e6", "1h3g4", "2P@h6",
        "1h7h5", "2g7h6", "1B@h3", "2c1h6", "1h5g4", "2P@g7", "1h3g4", "2c6e7", "1B@h3",
        "2g8h8", "1g4h3", "2h6g7", "1P@g4", "2h8g7", "1h3g4", "2e7f5", "1P@h3", "2e6f5"
      ],
    },
    "game13": {
      "seat": "Bwhite", "played": "2e3f2", "after": [],
      "clocks": [85163, 88089, 86590, 86662], "advantage": True,
      "prefix": [
        "1e2e4", "2d2d4", "2g8f6", "1e7e6", "2g1f3", "1b1c3", "1d7d5", "2e7e6", "2b1c3",
        "1e4d5", "1g8f6", "1f1b5", "2d7d5", "1c7c6", "1d5c6", "2h2h4", "1b7c6", "2P@g3",
        "1b5e2", "2f2g3", "1f8e7", "2P@f2", "1d2d4", "2e1f2", "2f6g4", "1b8d7", "2f2g1",
        "1g1f3", "2b8c6", "1e8g8", "2P@h3", "1c1f4", "2g4f6", "1c8b7", "2d1e1", "1d1d2",
        "1c6c5", "2f6e4", "1d4c5", "2c1e3", "2e4c3", "1P@g4", "2b2c3", "1f3h4", "2f8d6",
        "1N@e4", "2e3f2", "1c3e4", "2N@e4", "1f6e4", "2N@h5", "1d2d4", "2h8g8", "1e7c5",
        "2P@e5", "2e4f2", "1N@h6", "1g7h6", "2e1f2", "2c6e5", "1f4h6", "2d4e5", "1c5d4",
        "2P@e3", "1B@e3", "2f2e3", "1d8h4", "2P@f2", "1e3d4", "2e3f2", "1h4h6", "1e2g4",
        "2P@e3", "1h6d2", "2f2e3", "1e1f1", "2B@f2", "1d2d4"
      ],
    },
    "game14": {
      "seat": "Bblack", "played": "2f5e6", "after": [],
      "clocks": [77150, 74042, 76649, 74543], "advantage": True,
      "prefix": [
        "1e2e3", "2e2e4", "2d7d5", "2b1c3", "2d5e4", "2c3e4", "2g8f6", "1e7e6", "1d2d4",
        "2e4g5", "2e7e5", "1d7d6", "1g1f3", "2g5f7", "2e8f7", "1f8e7", "1N@h5", "2g1f3",
        "1e7f8", "2e5e4", "2f3e5", "1h2h3", "2f7e8", "1P@g6", "2d2d4", "1h5g3", "2b8d7",
        "2f1c4", "1b8c6", "2d7e5", "1f1d3", "2d4e5", "1g8f6", "2d8d1", "1e1g1", "2e1d1",
        "1P@g4", "2f6g4", "1h3g4", "2c1f4", "1f6g4", "2f8c5", "1P@h3", "2P@f7", "1g4f6",
        "1N@g5", "2e8e7", "1d8e7", "2f4g5", "1d3b5", "2P@f6", "1c8d7", "2e5f6", "1e3e4",
        "2g7f6", "1c6d4", "2P@g7", "1f3d4", "2g4f2", "1d7b5", "2d1c1", "1d4b5", "2c8e6",
        "2g7h8q", "1P@h4", "2a8h8", "1b1c3", "2g5f6", "1h4g3", "2e7f6", "1f2g3", "2N@h5",
        "2f6f7", "1P@h4", "2c4e6", "1P@h2", "2f7e6", "1h4g3", "2c1b1", "1h2g3", "2N@d2",
        "1B@b6", "1B@e3", "2b1c1", "2B@e3", "1b6e3", "1c1e3", "2P@f5", "2e6f5", "1N@c4",
        "1P@a6", "2B@e6", "2f5e6", "1b7a6", "1Q@c6", "2P@f5", "1f6d7", "2e6f5", "1b5c7",
        "2B@e6", "1e8d8"
      ],
    },
}

failures = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"[{'ok' if ok else 'FAIL'}] {what}" + (f": {detail}" if detail else ""))


def game_after(prefix: list[str]) -> Bughouse:
    g = Bughouse()
    for token in prefix:
        g.push(int(token[0]) - 1, token[1:])
    return g


def drawing_reply(g: Bughouse, board: int) -> str | None:
    for reply in g.legal_moves(board):
        h = g.copy()
        h.push(board, reply)
        if h.is_draw():
            return reply
    return None


def decide(prefix, seat, clocks, advantage, options) -> tuple[str, list[str]]:
    team = "white" if seat in ("Awhite", "Bblack") else "black"
    e = Engine(options={"Seat": seat, "Team": team, "Clocks": ",".join(map(str, clocks)),
                        "TimeAdvantage": "true" if advantage else "false", **options})
    try:
        e.send("position startpos moves " + " ".join(prefix))
        lines = e.go(f"go nodes {NODES}", timeout=300)
    finally:
        e.close()
    board = 0 if seat[0] == "A" else 1
    return parse_bestmove(lines)[board], lines


def main() -> int:
    for name, it in GAMES.items():
        board = 0 if it["seat"][0] == "A" else 1
        token = str(board + 1)
        off, _ = decide(it["prefix"], it["seat"], it["clocks"], it["advantage"],
                        {"HBAvoidDraw": "false", "HBSeekDraw": "false"})
        on, lines = decide(it["prefix"], it["seat"], it["clocks"], it["advantage"], {"HBAvoidDraw": "true"})
        report = next((l for l in lines if l.startswith("info string hb_draw ")), "")

        # off: the drawing line of the game
        g = game_after(it["prefix"])
        g.push(board, off)
        drawn_off = g.is_draw()
        for t in it["after"]:
            b, uci = int(t[0]) - 1, t[1:]
            if b != board and g.is_legal(b, uci):
                g.push(b, uci)
        drawn_off = drawn_off or drawing_reply(g, board) is not None
        check(token + off == it["played"] and drawn_off, f"{name} off: plays the game move, which draws or allows a draw",
              f"off={token}{off} game={it['played']}")

        # on: no draw at once, after any reply, or after the game's partner-board moves
        g = game_after(it["prefix"])
        g.push(board, on)
        problems = []
        if g.is_draw():
            problems.append("draws at once")
        if drawing_reply(g, board):
            problems.append("reply " + drawing_reply(g, board))
        for t in it["after"]:
            b, uci = int(t[0]) - 1, t[1:]
            if b != board and g.is_legal(b, uci):
                g.push(b, uci)
                r = drawing_reply(g, board)
                if r:
                    problems.append(f"after {t}: reply {r}")
        check(token + on != it["played"] and not problems, f"{name} on: avoids the draw",
              f"on={token}{on} {'; '.join(problems)} {report[len('info string hb_draw '):][:200]}")

    # seek: game 4 from Black's side after 1g4h3 2c3d5
    it = GAMES["game4"]
    prefix = it["prefix"] + ["1g4h3", "2c3d5"]
    clocks = [92474, 89399, 90850, 89666]
    off, _ = decide(prefix, "Ablack", clocks, False, {"HBSeekDraw": "false", "HBAvoidDraw": "false"})
    on, lines = decide(prefix, "Ablack", clocks, False, {"HBSeekDraw": "true"})
    g = game_after(prefix)
    check(drawing_reply(g, 0) == "P@g4", "seek: P@g4 is the drawing move there")
    h = g.copy()
    h.push(0, on)
    check(h.is_draw(), "seek on: Black, lost, takes the draw", f"on={on}")
    h = g.copy()
    h.push(0, off)
    check(not h.is_draw(), "seek off: no draw", f"off={off}")

    print(f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
