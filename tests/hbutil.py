"""Shared helpers for the HypeBeast engine tests.

The referee is imported from the arena checkout, never copied, so a rules
change there shows up here as a test failure.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
ARENA_TOOLS = Path(os.environ.get("HB_ARENA_TOOLS",
                                  Path.home() / "Projects/Chess-Auto-Prep/tools"))
if str(ARENA_TOOLS) not in sys.path:
    sys.path.insert(0, str(ARENA_TOOLS))

from bughouse_arena.referee import (BOARD_A, BOARD_B, BOARDS, STARTING_FEN,  # noqa: E402
                                    Bughouse, seat_team)
from bughouse_arena.sim import time_advantage  # noqa: E402

HYPEBEAST = Path(os.environ.get("HB_BIN", ROOT / "bin/hypebeast"))
FSF_REF = Path(os.environ.get("HB_REF_BIN", ROOT / "bin/fsf-ref"))
NET = Path(os.environ.get("HB_NET", ROOT / "nets/bughouse-cd8cceab93fe.nnue"))

SEATS = ("Awhite", "Ablack", "Bwhite", "Bblack")


def seat_of(name: str) -> tuple[int, chess.Color]:
    board = 0 if name[0] == "A" else 1
    return board, chess.WHITE if name[1:] == "white" else chess.BLACK


def team_of_seat(name: str) -> chess.Color:
    return seat_team(*seat_of(name))


class Engine:
    """Line-oriented UCI process with timeouts."""

    def __init__(self, binary: Path = HYPEBEAST, hypebeast: bool = True,
                 net: Path | None = NET, options: dict | None = None):
        self.proc = subprocess.Popen([str(binary)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1, cwd=str(ROOT))
        self.lines: queue.Queue = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.send("uci")
        self.uci_lines = self.read_until("uciok")
        if hypebeast:
            self.setoption("HypeBeast", "true")
        else:
            self.setoption("UCI_Variant", "bughouse")
        if net is not None:
            self.setoption("EvalFile", str(net))
        for key, value in (options or {}).items():
            self.setoption(key, value)
        self.sync()

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(line.rstrip("\n"))
        self.lines.put(None)

    def send(self, cmd: str):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def setoption(self, name: str, value) -> None:
        self.send(f"setoption name {name} value {value}")

    def read_until(self, prefix: str, timeout: float = 120.0) -> list[str]:
        deadline = time.monotonic() + timeout
        seen = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"waiting for {prefix!r}; tail={seen[-5:]}")
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty:
                continue
            if line is None:
                raise RuntimeError(f"engine exited waiting for {prefix!r}; tail={seen[-5:]}")
            seen.append(line)
            if line.startswith(prefix):
                return seen

    def sync(self):
        self.send("isready")
        self.read_until("readyok")

    def hbstate(self) -> dict:
        self.send("hbstate")
        line = self.read_until("hbstate ")[-1]
        return json.loads(line[len("hbstate "):])

    def go(self, cmd: str = "go nodes 2000", timeout: float = 120.0) -> list[str]:
        self.send(cmd)
        lines = self.read_until("bestmove", timeout)
        return lines

    def close(self):
        try:
            self.send("quit")
            self.proc.wait(timeout=20)
        except Exception:
            self.proc.kill()
            self.proc.wait()


def position_command(game: Bughouse) -> str:
    moves = " ".join(game.engine_moves())
    if game.start_fens == (STARTING_FEN, STARTING_FEN):
        base = "position startpos"
    else:
        base = f"position fen {game.start_fens[0]}|{game.start_fens[1]}"
    return f"{base} moves {moves}" if moves else base


def clocks_for(adv_white: bool, adv_black: bool) -> tuple[int, int, int, int]:
    """Four clocks (aW, aB, bW, bB) realising the requested advantages."""
    aw, bw = (60000, 50000) if adv_white else (50000, 60000)
    ab, bb = (60000, 50000) if adv_black else (50000, 60000)
    return aw, ab, bw, bb


def referee_expectation(game: Bughouse, clocks: tuple[int, int, int, int]) -> dict:
    """What hbstate should say, computed with the python referee only."""
    out = {"boards": []}
    for b in BOARDS:
        pos = game.boards[b]
        ep = chess.square_name(pos.ep_square) if pos.has_legal_en_passant() else "-"
        out["boards"].append({
            "placement": pos.board_fen(promoted=True),
            "pockets": {color: {pt: pos.pockets[color].count(pt) for pt in range(1, 6)}
                        for color in (chess.WHITE, chess.BLACK)},
            "stm": "w" if pos.turn == chess.WHITE else "b",
            "castling": pos.castling_xfen(),
            "ep": ep,
            "halfmove": pos.halfmove_clock,
            "fullmove": pos.fullmove_number,
            "repetitions": game._repetitions[b][game._board_key(b)],
            "in_check": pos.is_check(),
            "legal": sorted(game.legal_moves(b)),
        })
    out["mate"] = {name: [game.is_checkmate(team, False), game.is_checkmate(team, True)]
                   for name, team in (("white", chess.WHITE), ("black", chess.BLACK))}
    out["draw"] = game.is_draw()
    clocks_list = list(clocks)
    adv = {chess.WHITE: time_advantage(clocks_list, chess.WHITE),
           chess.BLACK: time_advantage(clocks_list, chess.BLACK)}
    out["advantage"] = {"white": adv[chess.WHITE], "black": adv[chess.BLACK]}
    # sim.terminal(first): first = team on move on the board that just moved
    if game.moves:
        last = game.moves[-1].board
        first = seat_team(last, game.turn(last))
    else:
        first = chess.WHITE
    verdict = "none"
    for team in (first, not first):
        if game.is_checkmate(team, adv[team]):
            verdict = "white_mated" if team == chess.WHITE else "black_mated"
            break
    else:
        if game.is_draw():
            verdict = "draw"
    out["verdict"] = verdict
    out["first"] = "white" if first == chess.WHITE else "black"
    return out


def pocket_counts(s: str) -> dict:
    letters = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5}
    counts = {pt: 0 for pt in range(1, 6)}
    for ch in s:
        counts[letters[ch]] += 1
    return counts


def compare_state(state: dict, expect: dict, seat: str) -> list[str]:
    """Differences between engine hbstate and referee expectation."""
    diffs = []
    for b in BOARDS:
        e, x = state["boards"][b], expect["boards"][b]
        for key in ("placement", "stm", "castling", "ep", "halfmove", "fullmove",
                    "repetitions", "in_check", "legal"):
            if e[key] != x[key]:
                diffs.append(f"board {'AB'[b]} {key}: engine={e[key]!r} referee={x[key]!r}")
        pockets = {chess.WHITE: pocket_counts(e["pocket_white"]),
                   chess.BLACK: pocket_counts(e["pocket_black"])}
        if pockets != x["pockets"]:
            diffs.append(f"board {'AB'[b]} pockets: engine={pockets} referee={x['pockets']}")
    for key in ("mate", "draw", "verdict", "first"):
        if state[key] != expect[key]:
            diffs.append(f"{key}: engine={state[key]} referee={expect[key]}")
    for team in ("white", "black"):
        if state["advantage"][team] != expect["advantage"][team]:
            diffs.append(f"advantage {team}: engine={state['advantage'][team]} "
                         f"referee={expect['advantage'][team]}")
    board, color = seat_of(seat)
    on_turn = expect["boards"][board]["stm"] == ("w" if color == chess.WHITE else "b")
    if state["on_turn"] != on_turn:
        diffs.append(f"on_turn: engine={state['on_turn']} referee={on_turn}")
    if state["our_legal"] != len(expect["boards"][board]["legal"]):
        diffs.append(f"our_legal: engine={state['our_legal']} "
                     f"referee={len(expect['boards'][board]['legal'])}")
    if not state["keys_ok"]:
        diffs.append(f"keys: {state['key_error']}")
    if state["position_error"]:
        diffs.append(f"position_error: {state['position_error']}")
    return diffs


def parse_bestmove(lines: list[str]) -> tuple[str, str]:
    tokens = lines[-1].split()
    assert tokens[0] == "bestmove", lines[-1]
    joint = tokens[1]
    assert joint.startswith("(") and joint.endswith(")") and joint.count(",") == 1, lines[-1]
    a, b = joint[1:-1].split(",")
    return a, b


def summary_fields(lines: list[str]) -> dict:
    for line in lines:
        if line.startswith("info string hb_summary "):
            return dict(kv.split("=", 1) for kv in line.split()[3:] if "=" in kv)
    return {}
