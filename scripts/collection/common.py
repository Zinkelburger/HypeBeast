"""Shared pieces of the annotated-games pipeline (scripts/collection/).

Everything here reads match directories made by the bughouse arena
(results.jsonl, engine_logs/) and replays positions with the arena's own
referee, imported read-only from a Chess-Auto-Prep checkout
(HB_ARENA_TOOLS, default ~/Projects/Chess-Auto-Prep/tools), the way
tests/hbutil.py does. The per-decision rows come from the post-mortem script
(HB_POSTMORTEM, default ~/Projects/HypeBeast-v5/scripts/postmortem.py); this
module only adds the transcript fields that script does not keep (the whole
main line, the options and clocks a decision was searched with, the raw
hb_coord / hb_forecast / hb_prices objects).
"""
from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
OUT = LOGS / "collection"
CACHE = OUT / "cache"

ARENA_TOOLS = Path(os.environ.get("HB_ARENA_TOOLS", Path.home() / "Projects/Chess-Auto-Prep/tools"))
for p in (ARENA_TOOLS, ARENA_TOOLS / "mcp"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import chess  # noqa: E402
from chess.variant import CrazyhouseBoard  # noqa: E402

from bughouse_arena.referee import Bughouse  # noqa: E402
from bughouse_arena.sim import time_advantage  # noqa: E402
from bughouse.board import san as _bpgn_san  # noqa: E402  (P@e5 for pawn drops)

POSTMORTEM = Path(os.environ.get("HB_POSTMORTEM", Path.home() / "Projects/HypeBeast-v5/scripts/postmortem.py"))
_spec = importlib.util.spec_from_file_location("postmortem", POSTMORTEM)
postmortem = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(postmortem)

NET = ROOT / "nets/bughouse-cd8cceab93fe.nnue"
# The binary that played v1.1.1's seats in v7b-vs-v110-sanity and v7-selfplay-flags
# (sha256 1dc5e015...), and v1.1.0 (022f0d72...). v7-vs-v110-sanity's contender was a
# pre-release build (d0128a29..., before the partner-mate hold's `pm - 1` change) that is
# no longer on this machine; its decisions are replayed with the release binary.
BIN_V111 = ROOT / "bin/hypebeast-v7"
BIN_V110 = ROOT / "bin/hypebeast-v1.1.0"
# engine/src/stockfish: the v1.1.1 search plus the page reports of commit cc47c8a
# (hb_fed after every line, hb_values with the prices). Used only after it has been
# checked to print the same search as the binary that played (see build_game.py).
BIN_REPORTS = ROOT / "engine/src/stockfish"
# How the v1.1.1 source plays as v1.1.0 (docs/OPTIONS.md, "To play as v6").
V110_SETTINGS = {"HBHoldWhenMated": "false", "HBHoldPartnerMate": "false", "HBHoldRace": "0"}

SEATS = ("Awhite", "Ablack", "Bwhite", "Bblack")
ARENA_SEAT = {"Awhite": "A-white", "Ablack": "A-black", "Bwhite": "B-white", "Bblack": "B-black"}
SEAT_OF_ARENA = {v: k for k, v in ARENA_SEAT.items()}
TEAMS = [["Awhite", "Bblack"], ["Ablack", "Bwhite"]]   # index 0: the arena's team "white"
PARTNER = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
MATE = 90000

MATCHES = {
    "v7-vs-v110-sanity": {
        "names": {"contender": "HypeBeast 1.1.1 (pre-release build)", "baseline": "HypeBeast 1.1.0"},
        "binaries": {"contender": BIN_V111, "baseline": BIN_V110},
        "event": "HypeBeast 1.1.1 (pre-release build) against HypeBeast 1.1.0, 500,000 nodes a move",
        "short": "v111pre-v110",
    },
    "v7b-vs-v110-sanity": {
        "names": {"contender": "HypeBeast 1.1.1", "baseline": "HypeBeast 1.1.0"},
        "binaries": {"contender": BIN_V111, "baseline": BIN_V110},
        "event": "HypeBeast 1.1.1 against HypeBeast 1.1.0, 500,000 nodes a move",
        "short": "v111-v110",
    },
    "v7-selfplay-flags": {
        "names": {"contender": "HypeBeast 1.1.1 (500k)", "baseline": "HypeBeast 1.1.1 (450k)"},
        "binaries": {"contender": BIN_V111, "baseline": BIN_V111},
        "event": "HypeBeast 1.1.1 against itself, 500,000 nodes a move for one team and 450,000 for the other",
        "short": "selfplay",
    },
}

# What each decision reason in hb_summary means, checked against
# engine/src/hb_coordinator.cpp (coordinate, draw_policy, consider_voluntary_wait)
# and engine/src/hb_arena.cpp (controller). One plain line each.
REASONS = {
    "kept_main": "the board's own search move was kept: no other candidate had a probability-weighted winning chance over the forecast worlds at least 25 cp-equivalent better",
    "world_switch": "another candidate replaced the board's own search move: over the forecast worlds of what may arrive from the partner board, its probability-weighted winning chance was at least 25 cp-equivalent better",
    "no_arrivals": "the forecast expected nothing to arrive soon, so the board's own search move was played (the leftover budget may deepen that search and change the move)",
    "only_move": "it was the only legal move",
    "team_win_main": "the board's own search move ends the game at once by the referee's rules",
    "team_win_override": "another move ends the game at once by the referee's rules, so it replaced the board's own search move",
    "delivery_win_main": "the board's own search move is a capture that lets the partner, on turn, drop the captured piece for an immediate team mate",
    "delivery_win": "a capture that lets the partner, on turn, drop the captured piece for an immediate team mate replaced the board's own search move",
    "exposure_veto": "the board's own search move let the opponent capture a piece that their partner can drop for mate on the other board (at once, or whatever the mover's partner, in check there, replies), so a safer candidate was played",
    "soft_switch": "the board's own search move could hand the opponent's partner a mating drop if our partner did not move away in time, so a safe candidate scoring within 600 cp was played",
    "stall_deny": "sat: every move (or every reasonable one) let the opponent capture a piece their partner can drop for mate (at once, or whatever the mover's partner, in check there, replies), and the clocks allowed waiting, since the opponent cannot capture until this seat moves",
    "hold_mated": "sat: every legal move is mated on this board, the partner is still in the game, and this seat's clock outlasts the seat it races",
    "hold_partner_mate": "sat: the partner has a forced mate on the other board, and while this seat sits its opponent can capture nothing to send to the side being mated",
    "voluntary_wait": "sat for a few seconds: the partner, on turn, can capture a piece that gives this seat a winning drop (or a block while in check)",
    "avoid_draw": "the chosen move would let the referee's threefold repetition happen while not losing, so the best move that avoids it was played",
    "seek_draw": "clearly lost, so a move that draws by the referee's threefold repetition was played",
    "main": "Coordination off: the board's own search move",
}
# The sit reasons, with the short codes written into a move's `waited.why`.
WAIT_CODES = {"hold_partner_mate": "partner_mate", "hold_mated": "mated", "stall_deny": "deny_feed",
              "voluntary_wait": "wait_delivery"}

PIECE_NAMES = {"P": "pawn", "N": "knight", "B": "bishop", "R": "rook", "Q": "queen"}


# ---------------------------------------------------------------- positions

def san_of(board: CrazyhouseBoard, move: chess.Move) -> str:
    """SAN as the BPGN writes it (P@e5 for a pawn drop), with '+' for check.
    '#' is never written here: python-chess judges mate on one board, the
    referee on two (a partner may still supply a blocker)."""
    text = _bpgn_san(board, move)
    return text[:-1] + "+" if text.endswith("#") else text


def board_fen(game: Bughouse, b: int) -> str:
    return game.boards[b].fen()


def bare_san(s: str) -> str:
    return s.rstrip("+#!?")


def game_tokens(record: dict) -> list[str]:
    toks = list(record["opening"]["moves"])
    for e in record["result"]["events"]:
        if e["kind"] == "move":
            toks.append(("1" if e["board"] == "A" else "2") + e["uci"])
    return toks


def start_game(record: dict) -> Bughouse:
    o = record["opening"]
    return Bughouse.from_dual_fen(o["dual_fen"]) if o.get("dual_fen") else Bughouse()


def replay_states(record: dict) -> list[dict]:
    """One entry per half-move: board index, uci, san, both FENs after it,
    and both FENs before it."""
    game = start_game(record)
    out = []
    for tok in game_tokens(record):
        b = int(tok[0]) - 1
        before = (board_fen(game, 0), board_fen(game, 1))
        pos = game.boards[b]
        mv = chess.Move.from_uci(tok[1:])
        s = san_of(pos, mv)
        num = pos.fullmove_number
        white = pos.turn == chess.WHITE
        game.push(b, tok[1:])
        out.append({"board": b, "uci": mv.uci(), "san": s, "num": num, "white": white,
                    "before": before, "after": (board_fen(game, 0), board_fen(game, 1))})
    return out


def game_at(record: dict, n: int) -> Bughouse:
    game = start_game(record)
    for tok in game_tokens(record)[:n]:
        game.push(int(tok[0]) - 1, tok[1:])
    return game


def single_board_game(fen_this: str, fen_other: str, b: int) -> Bughouse:
    return Bughouse(fen_this, fen_other) if b == 0 else Bughouse(fen_other, fen_this)


def walk_line(fen_this: str, fen_other: str, b: int, ucis: list[str], max_moves: int = 8):
    """Plays a line on board b with the referee; the other board is not moved,
    so this board's reserves change only by its own drops. Stops at the first
    move that is not legal there. -> [(uci, san, fen after)]"""
    game = single_board_game(fen_this, fen_other, b)
    out = []
    for u in ucis[:max_moves]:
        try:
            mv = chess.Move.from_uci(u)
        except ValueError:
            break
        pos = game.boards[b]
        if mv not in pos.legal_moves:
            break
        s = san_of(pos, mv)
        game.push(b, mv.uci())
        out.append((mv.uci(), s, board_fen(game, b)))
    return out


def pocket_of(fen: str) -> str:
    field = fen.split(" ")[0]
    return field[field.index("[") + 1:field.index("]")] if "[" in field else ""


def with_pocket(fen: str, extra: str) -> str:
    """fen with the letters of `extra` added to its reserve (python-chess order)."""
    b = CrazyhouseBoard(fen)
    for ch in extra:
        b.pockets[chess.WHITE if ch.isupper() else chess.BLACK].add(chess.PIECE_SYMBOLS.index(ch.lower()))
    return b.fen()


def pocket_diff(after: str, before: str) -> str | None:
    """Letters in after's reserve beyond before's, or None if before has something after lacks."""
    a, b = collections.Counter(pocket_of(after)), collections.Counter(pocket_of(before))
    if any(b[k] > a[k] for k in b):
        return None
    return "".join(sorted((a - b).elements(), key=lambda c: ("PNBRQ".index(c.upper()), c.islower())))


# ------------------------------------------------------------ match loading

def load_records(match: str) -> dict[int, dict]:
    return {r["game"]: r for r in (json.loads(l) for l in open(LOGS / match / "results.jsonl"))}


def seat_events(record: dict) -> dict[str, list[dict]]:
    """Move and sit events per seat (engine spelling), in order."""
    out = collections.defaultdict(list)
    for e in record["result"]["events"]:
        if e["kind"] in ("move", "sit"):
            out[SEAT_OF_ARENA[e["seat"]]].append(e)
    return out


def _options_set(line: str):
    m = re.match(r">>> setoption name (.+?) value (.*)$", line)
    return (m.group(1), m.group(2)) if m else None


def read_sessions(match: str):
    """Every engine process of a match: role, file, and its decisions in order.
    A decision: options in force, position, go, and the lines it printed."""
    for path in sorted((LOGS / match / "engine_logs").glob("w*-*.log")):
        role = "contender" if "-contender-" in path.name else "baseline"
        session = None
        dec = None
        for raw in open(path, errors="replace"):
            line = raw.rstrip("\n")
            if line == ">>> uci":
                if session is not None:
                    yield session
                session = {"role": role, "file": path.name, "options": {}, "decisions": [], "commands": []}
                continue
            if session is None:
                continue
            if line.startswith(">>> "):
                session["commands"].append(line[4:])
                kv = _options_set(line)
                if kv:
                    session["options"][kv[0]] = kv[1]
                elif line.startswith(">>> position "):
                    session["position"] = line[4:]
                elif line.startswith(">>> go"):
                    dec = {"options": dict(session["options"]), "position": session["position"],
                           "go": line[4:], "lines": [], "cmd_index": len(session["commands"]) - 1}
                continue
            if dec is not None:
                dec["lines"].append(line)
                if line.startswith("bestmove"):
                    session["decisions"].append(dec)
                    dec = None
        if session is not None:
            yield session


def parse_output(lines: list[str]) -> dict:
    """What one go printed: hb_* objects, every pv line (with its hb_fed when
    printed), the final score line, the summary and our half of bestmove."""
    out = {"pvs": [], "summary": {}, "final": None, "bestmove": None}
    for line in lines:
        if line.startswith("info string hb_"):
            name, _, rest = line[len("info string "):].partition(" ")
            if name in ("hb_prices", "hb_forecast", "hb_coord", "hb_chance", "hb_values"):
                try:
                    out[name[3:]] = json.loads(rest)
                except json.JSONDecodeError:
                    pass
            elif name == "hb_summary":
                out["summary"] = dict(p.split("=", 1) for p in rest.split() if "=" in p)
            elif name == "hb_fed":
                m = re.match(r"multipv (\d+) cp (-?\d+)", rest)
                if m and out["pvs"] and out["pvs"][-1]["multipv"] == int(m.group(1)):
                    out["pvs"][-1]["fed"] = int(m.group(2))
            elif name.startswith("hb_wake_after_ms="):
                out["wake_after_ms"] = int(name.split("=")[1])
            continue
        if line.startswith("info depth "):
            t = line.split()
            if " pv " in line:
                head = line.split(" pv ", 1)[0].split()
                si = head.index("score")
                out["pvs"].append({
                    "depth": int(head[2]),
                    "multipv": int(head[head.index("multipv") + 1]) if "multipv" in head else 1,
                    "kind": head[si + 1], "value": int(head[si + 2]),
                    "bound": "lowerbound" in head or "upperbound" in head,
                    "nodes": int(head[head.index("nodes") + 1]) if "nodes" in head else None,
                    "moves": line.split(" pv ", 1)[1].split(), "fed": None})
            elif "score" in t:
                si = t.index("score")
                out["final"] = {t[si + 1]: int(t[si + 2]), "depth": int(t[2]),
                                "nodes": int(t[t.index("nodes") + 1]) if "nodes" in t else None}
            else:
                out["final"] = {"depth": int(t[2]), "nodes": int(t[t.index("nodes") + 1]) if "nodes" in t else None}
        elif line.startswith("bestmove"):
            out["bestmove"] = line.split()[1]
    s = out["summary"]
    depth = int(s.get("main_depth", 0) or 0)
    main = [p for p in out["pvs"] if p["depth"] == depth and p["multipv"] == 1 and not p["bound"]]
    out["main_pv"] = main[-1] if main else None
    return out


def score_dict(kind: str, value: int) -> dict:
    return {kind: value}


def cp_of_score(s: dict | None):
    """A UCI score dict -> cp with mates as +-100000 (side-to-move view)."""
    if not s:
        return None
    if "mate" in s:
        return 100000 if s["mate"] > 0 else -100000
    return s.get("cp")


def load_match(match: str) -> dict:
    """records, decisions joined to games and events, post-mortem rows."""
    records = load_records(match)
    toks_of = {g: game_tokens(r) for g, r in records.items()}
    names = None
    decisions = collections.defaultdict(list)   # game -> [decision]
    sessions = {}                                # (game, seat) -> the commands the arena sent
    unmatched = 0
    for session in read_sessions(match):
        decs = session["decisions"]
        seat = session["options"].get("Seat")
        if not decs or not seat:
            continue
        last = decs[-1]["position"].split()
        moves = last[last.index("moves") + 1:] if "moves" in last else []
        cand = [g for g, r in records.items()
                if toks_of[g][:len(moves)] == moves and r["seats"][ARENA_SEAT[seat]] == r[session["role"]]]
        if len(cand) != 1:
            unmatched += len(decs)
            continue
        g = cand[0]
        rec = records[g]
        events = seat_events(rec)[seat]
        if len(events) != len(decs):
            unmatched += len(decs)
            continue
        sessions[(g, seat)] = session["commands"]
        for k, (d, e) in enumerate(zip(decs, events)):
            pos = d["position"].split()
            mv = pos[pos.index("moves") + 1:] if "moves" in pos else []
            d.update({"match": match, "game": g, "seat": seat, "role": session["role"], "k": k,
                      "n": len(mv), "event": e, "file": session["file"]})
            d["out"] = parse_output(d["lines"])
            del d["lines"]
            decisions[g].append(d)
    for g in decisions:
        decisions[g].sort(key=lambda d: (d["event"]["t"], d["n"], d["seat"]))
    # post-mortem rows, joined by (game, seat, n, occurrence)
    _, games, rows, _ = postmortem.collect(str(LOGS / match))
    fed = postmortem.fed_in_scores(games, rows)
    byk = collections.defaultdict(list)
    for r in rows:
        r["_fed_estimate"] = fed.get(id(r))
        byk[(r["game"], r["seat"], r["n"])].append(r)
    for g, ds in decisions.items():
        seen = collections.Counter()
        for d in ds:
            key = (g, d["seat"], d["n"])
            lst = byk.get(key, [])
            i = seen[key]
            seen[key] += 1
            d["pm"] = lst[i] if i < len(lst) else None
    return {"match": match, "records": records, "decisions": decisions, "unmatched": unmatched,
            "sessions": sessions,
            "pm_games": {x["game"]: x for x in games}}


# ------------------------------------------------------------------ engine

class Search:
    """One search in a fresh engine process (the engine keeps state per
    process, so a fresh one reproduces a logged decision). Results are cached
    on disk by the exact command list."""

    def __init__(self, binary: Path, setup: list[str], position: str, go: str):
        self.binary = Path(binary)
        self.commands = (["uci"] + setup + ["isready"] if setup else ["uci", "isready"])
        self.position = position
        self.go = go

    def script(self) -> list[str]:
        return self.commands + [self.position, self.go]

    def key(self) -> str:
        h = hashlib.sha256()
        h.update(sha256_file(self.binary).encode())
        h.update("\n".join(self.script()).encode())
        return h.hexdigest()[:24]

    def run(self, timeout: float = 600) -> dict:
        CACHE.mkdir(parents=True, exist_ok=True)
        path = CACHE / f"{self.key()}.json"
        if path.exists():
            return dict(json.loads(path.read_text()), _cached=True)
        env = dict(os.environ, HB_EXPERIMENTAL="1")
        t0 = time.time()
        proc = subprocess.Popen(["nice", "-n", "19", str(self.binary)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                bufsize=1, cwd=str(ROOT), env=env)
        lines = []

        def send(c):
            proc.stdin.write(c + "\n")
            proc.stdin.flush()

        def until(prefix):
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                lines.append(line)
                if line.startswith(prefix):
                    return
            raise RuntimeError(f"engine ended before {prefix!r}")

        try:
            send("uci")
            until("uciok")
            for c in self.commands[1:]:
                send(c)
                if c == "isready":
                    until("readyok")
            send(self.position)
            send(self.go)
            mark = len(lines)
            until("bestmove")
            send("quit")
            proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
        result = {"binary": str(self.binary.relative_to(ROOT)) if self.binary.is_relative_to(ROOT) else str(self.binary),
                  "binary_sha256": sha256_file(self.binary), "script": self.script(),
                  "seconds": round(time.time() - t0, 2), "lines": lines[mark:]}
        path.write_text(json.dumps(result))
        return result


class SessionReplay:
    """Replays one engine process of a match in a fresh process: every command
    the arena sent it, in order (the local net in place of the logged path),
    so each go starts from the same search history as in the game. -> the
    lines of every go, in order. Cached on disk."""

    def __init__(self, binary: Path, commands: list[str], upto: int | None = None):
        self.binary = Path(binary)
        cmds = []
        for c in commands[:upto]:
            if c.startswith("setoption name EvalFile value "):
                c = f"setoption name EvalFile value {NET}"
            cmds.append(c)
        self.commands = cmds

    def key(self) -> str:
        h = hashlib.sha256()
        h.update(sha256_file(self.binary).encode())
        h.update("\n".join(self.commands).encode())
        return "s" + h.hexdigest()[:24]

    def run(self) -> dict:
        CACHE.mkdir(parents=True, exist_ok=True)
        path = CACHE / f"{self.key()}.json"
        if path.exists():
            return json.loads(path.read_text())
        env = dict(os.environ, HB_EXPERIMENTAL="1")
        t0 = time.time()
        proc = subprocess.Popen(["nice", "-n", "19", str(self.binary)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                bufsize=1, cwd=str(ROOT), env=env)
        gos = []

        def send(c):
            proc.stdin.write(c + "\n")
            proc.stdin.flush()

        def until(prefix, keep=None):
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                if keep is not None:
                    keep.append(line)
                if line.startswith(prefix):
                    return
            raise RuntimeError(f"engine ended before {prefix!r}")

        try:
            for c in self.commands:
                send(c)
                if c == "uci":
                    until("uciok")
                elif c == "isready":
                    until("readyok")
                elif c.startswith("go"):
                    out = []
                    until("bestmove", out)
                    gos.append(out)
            send("quit")
            proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
        result = {"binary": str(self.binary.relative_to(ROOT)), "binary_sha256": sha256_file(self.binary),
                  "commands": self.commands, "seconds": round(time.time() - t0, 2), "gos": gos}
        path.write_text(json.dumps(result))
        return result


_SHA = {}


def sha256_file(path: Path) -> str:
    path = Path(path)
    if path not in _SHA:
        _SHA[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return _SHA[path]


def arena_setup(seat: str, coordination: bool = True, extra: dict | None = None,
                time_adv: bool = False, clocks: str | None = None) -> list[str]:
    """The option sequence the arena sends a HypeBeast seat (players.py
    TeamEngineSeat), with the local net."""
    team = "white" if seat in ("Awhite", "Bblack") else "black"
    cmds = ["setoption name Ponder value false", "setoption name UCI_Variant value bughouse",
            f"setoption name EvalFile value {NET}", "setoption name HypeBeast value true",
            f"setoption name Coordination value {'true' if coordination else 'false'}"]
    for k, v in (extra or {}).items():
        cmds.append(f"setoption name {k} value {v}")
    cmds += ["isready", "ucinewgame", f"setoption name Team value {team}",
             f"setoption name Seat value {seat}", "isready",
             f"setoption name TimeAdvantage value {'true' if time_adv else 'false'}"]
    if clocks:
        cmds.append(f"setoption name Clocks value {clocks}")
    return cmds


def team_of(seat: str) -> bool:
    return seat in ("Awhite", "Bblack")    # True: the arena's team white


def position_cmd(record: dict, tokens: list[str]) -> str:
    o = record["opening"]
    base = f"position fen {o['dual_fen']}" if o.get("dual_fen") else "position startpos"
    return f"{base} moves {' '.join(tokens)}" if tokens else base


def clocks_str(clocks: list[int]) -> str:
    return ",".join(str(int(c)) for c in clocks)


def adv_for(clocks: list[int], seat: str) -> bool:
    return time_advantage(list(clocks), chess.WHITE if team_of(seat) else chess.BLACK)


def opponent_seat(seat: str) -> str:
    return seat[0] + ("black" if seat.endswith("white") else "white")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")
    tmp.replace(path)


def session_binary(match: str, role: str) -> Path:
    """The binary a session is replayed with: v1.1.0's own binary for its seats;
    for v1.1.1's seats the build with the page reports (same search, checked
    against bin/hypebeast-v7 by replay.py --check), so hb_fed is printed."""
    b = MATCHES[match]["binaries"][role]
    return BIN_REPORTS if b == BIN_V111 else b


def replay_sessions(m: dict, g: int, binary_for=None, skip_binaries=()) -> dict:
    """Replays every engine process of game g. -> {seat: [parsed output per go]}"""
    out = {}
    for seat in SEATS:
        cmds = m["sessions"].get((g, seat))
        if not cmds:
            continue
        role = next(d["role"] for d in m["decisions"][g] if d["seat"] == seat)
        binary = (binary_for or session_binary)(m["match"], role)
        if binary in skip_binaries:
            continue
        r = SessionReplay(binary, cmds).run()
        out[seat] = {"binary": r["binary"], "binary_sha256": r["binary_sha256"], "seconds": r["seconds"],
                     "gos": [parse_output(x) for x in r["gos"]]}
    return out


def same_decision(logged: dict, replayed: dict) -> bool:
    """Move, score and node count as the arena recorded them."""
    return (logged.get("bestmove") == replayed.get("bestmove") and logged.get("final") == replayed.get("final"))
