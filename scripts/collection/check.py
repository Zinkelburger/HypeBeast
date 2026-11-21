#!/usr/bin/env python3
"""Check the merged site files against the data contract, the referee and the notes rules.

    python3 scripts/collection/check.py [SITE_DIR]   (default logs/collection/site)

Fails (exit 1) with one precise message per problem when:
  - index.json or a game file breaks the contract (fields, types, codes, the
    file name's hash, the counts in the index);
  - a game move or a line move does not replay legally with the arena's
    referee (bughouse_arena.referee.Bughouse), or a FEN differs from the
    referee's, or a line's start is not its move's position plus `assume`;
  - the published file differs from its fact sheet in anything but text
    (title, summary, glyph, notes) and lines the notes dropped;
  - a note, title or summary mentions a piece move, capture, drop, castling or
    promotion in SAN that is not a move of the game, a move of one of the
    annotated move's lines, or a move named in that move's facts (title and
    summary: any move of the game or its lines);
  - a note is longer than 500 characters or a title longer than 60.
A bare square such as "e4" may be a square, not a pawn move: one that is not
an allowed move is reported as a warning only.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("hb_collection_common", HERE / "common.py")
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)

import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402

import chess  # noqa: E402
from chess.variant import CrazyhouseBoard  # noqa: E402

ID_RE = re.compile(r"^[A-Za-z0-9][\w-]{0,63}$")
UCI_RE = re.compile(r"^(?:[a-h][1-8][a-h][1-8][qrbn]?|[PNBRQ]@[a-h][1-8])$")
GLYPHS = {None, "!", "!!", "?", "??", "!?", "?!"}
KINDS = {"played", "instead", "threat", "arrives"}
SEATS = set(c.SEATS)
MOVE_KEYS = {"i", "board", "seat", "num", "uci", "san", "fen", "t", "clocks", "eval", "mate", "book", "waited",
             "glyph", "note", "lines"}
LINE_KEYS = {"id", "kind", "from", "board", "start", "assume", "moves", "eval", "mate", "note"}
GAME_KEYS = {"version", "id", "title", "summary", "event", "date", "seats", "teams", "result", "initial_clock",
             "start", "moves"}
INDEX_GAME_KEYS = {"id", "file", "title", "summary", "event", "date", "seats", "winner", "how", "moves", "notes"}
TEXT_FIELDS = {"title", "summary", "glyph", "note"}
# SAN that cannot be a square name: piece moves, captures, drops, castling, promotions
SAN_STRONG = re.compile(r"(?<![\w@])(?:O-O(?:-O)?|[KQRBN][a-h]?[1-8]?x?[a-h][1-8]|[a-h]x[a-h][1-8](?:=[QRBN])?|"
                        r"[a-h][18]=[QRBN]|[PNBRQ]@[a-h][1-8])[+#]?(?![\w@])")
SAN_SQUARE = re.compile(r"(?<![\w@=])[a-h][1-8](?![\w@=])")

errors: list[str] = []
warnings: list[str] = []


def err(where, msg):
    errors.append(f"{where}: {msg}")


def norm(san: str) -> str:
    return san.rstrip("+#")


def check_fen(where, fen):
    try:
        CrazyhouseBoard(fen)
    except ValueError as e:
        err(where, f"unreadable FEN {fen!r}: {e}")
        return False
    if " " not in fen or "/" not in fen.split(" ")[0]:
        err(where, f"FEN not in readBoard's form: {fen!r}")
        return False
    return True


def same_board(a: str, b: str) -> bool:
    """Equal positions: placement (promotion marks kept), reserves, turn, castling, ep."""
    return a.split(" ")[:4] == b.split(" ")[:4]


def check_line(where, ln, mv, before, after):
    if set(ln) != LINE_KEYS:
        err(where, f"line keys {sorted(set(ln) ^ LINE_KEYS)} differ from the contract")
        return
    if not ID_RE.match(str(ln["id"])):
        err(where, f"bad line id {ln['id']!r}")
    if ln["kind"] not in KINDS:
        err(where, f"unknown kind {ln['kind']!r}")
    if ln["from"] not in ("before", "after"):
        err(where, f"bad from {ln['from']!r}")
    if ln["board"] != mv["board"]:
        err(where, f"line board {ln['board']} is not the move's board {mv['board']}")
    if not isinstance(ln["moves"], list) or not (2 <= len(ln["moves"]) <= 8):
        err(where, f"a line has 2 to 8 moves, this one {len(ln['moves']) if isinstance(ln['moves'], list) else '?'}")
    for k in ("eval", "mate"):
        if ln[k] is not None and not isinstance(ln[k], int):
            err(where, f"{k} must be an integer or null")
    if ln["note"] is not None and not isinstance(ln["note"], str):
        err(where, "note must be text or null")
    if not check_fen(where + " start", ln["start"]):
        return
    b = "AB".index(mv["board"])
    ref = before if ln["from"] == "before" else after
    assume = ln["assume"] or ""
    if not re.fullmatch(r"[PNBRQpnbrq]*", assume):
        err(where, f"assume {assume!r} is not piece letters")
        return
    diff = c.pocket_diff(ln["start"], ref[b])
    want = "".join(sorted(assume, key=lambda ch: ("PNBRQ".index(ch.upper()), ch.islower())))
    start_turn_ok = ln["start"].split(" ")[1] == ref[b].split(" ")[1]
    if ln["kind"] == "threat":
        start_turn_ok = ln["start"].split(" ")[1] != ref[b].split(" ")[1]
    placement_ok = ln["start"].split(" ")[0].split("[")[0] == ref[b].split(" ")[0].split("[")[0]
    if not placement_ok or diff is None or diff != want or not start_turn_ok:
        if ln["kind"] == "played" and ln["from"] == "after" and placement_ok and diff is not None and diff == want:
            pass
        else:
            err(where, f"start is not the {ln['from']} position plus assume {assume!r}"
                       f"{' with the turn passed' if ln['kind'] == 'threat' else ''}: start {ln['start']!r}, position {ref[b]!r}")
    # replay with the referee: this board from start, the other board as it stands
    game = c.single_board_game(ln["start"], ref[1 - b], b)
    for k, m in enumerate(ln["moves"]):
        w = f"{where} move {k + 1} {m.get('san')!r}"
        if not UCI_RE.match(str(m.get("uci"))):
            err(w, f"bad uci {m.get('uci')!r}")
            return
        if not game.is_legal(b, m["uci"]):
            err(w, f"illegal by the referee in {c.board_fen(game, b)}")
            return
        pos = game.boards[b]
        san = c.san_of(pos, chess.Move.from_uci(m["uci"]))
        game.push(b, m["uci"])
        if norm(san) != norm(m["san"]):
            err(w, f"SAN should be {san!r}")
        if not same_board(m["fen"], c.board_fen(game, b)):
            err(w, f"FEN {m['fen']!r} differs from the referee's {c.board_fen(game, b)!r}")


def allowed_sans(game: dict, i: int) -> set[str]:
    """Any move of the game (a note may follow a piece across the boards from
    its capture to its drop), and the moves of this move's own lines."""
    moves = game["moves"]
    out = {norm(m["san"]) for m in moves}
    for ln in moves[i]["lines"]:
        out |= {norm(m["san"]) for m in ln["moves"]}
    return out


def fact_sans(obj) -> set[str]:
    """Every move the builder itself names in a move's `facts` (the board's own
    move, the capture and drop it was exposed to, the candidates, the captures
    that fed this board): an annotator may repeat those too."""
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and SAN_STRONG.fullmatch(norm(k)):
                out.add(norm(k))
            out |= fact_sans(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= fact_sans(v)
    elif isinstance(obj, str) and SAN_STRONG.fullmatch(norm(obj)):
        out.add(norm(obj))
    return out


def check_text(where, text, allowed, limit):
    if text is None:
        return
    if not isinstance(text, str):
        err(where, "text must be a string or null")
        return
    if limit and len(text) > limit:
        err(where, f"{len(text)} characters, more than {limit}")
    if re.search(r"<[a-zA-Z/][^>]*>|\[[^\]]*\]\([^)]*\)|\*\*|`", text):
        err(where, "markup in plain text")
    for mt in SAN_STRONG.finditer(text):
        if norm(mt.group(0)) not in allowed:
            err(where, f"mentions {mt.group(0)!r}, which is not a move of this game, of this move's lines or of its facts")
    for mt in SAN_SQUARE.finditer(text):
        if mt.group(0) not in allowed:
            warnings.append(f"{where}: {mt.group(0)!r} is not an allowed move (fine if it names a square)")


def check_game(path: Path, entry: dict | None):
    raw = path.read_bytes()
    where0 = path.name
    try:
        game = json.loads(raw)
    except json.JSONDecodeError as e:
        err(where0, f"not JSON: {e}")
        return None
    if set(game) != GAME_KEYS:
        err(where0, f"top-level keys {sorted(set(game) ^ GAME_KEYS)} differ from the contract")
    if game.get("version") != 1:
        err(where0, "version must be 1")
    gid = game.get("id", "")
    if not ID_RE.match(str(gid)):
        err(where0, f"bad id {gid!r}")
    if path.name != f"{gid}-{hashlib.sha256(raw).hexdigest()[:10]}.json":
        err(where0, f"file name should be {gid}-{hashlib.sha256(raw).hexdigest()[:10]}.json")
    if set(game.get("seats", {})) != SEATS:
        err(where0, "seats must name Awhite, Ablack, Bwhite, Bblack")
    if game.get("teams") != c.TEAMS:
        err(where0, f"teams must be {c.TEAMS}")
    res = game.get("result", {})
    if set(res) != {"winner", "how", "board", "text"} or res.get("winner") not in (0, 1, None) or \
            res.get("board") not in ("A", "B", None):
        err(where0, f"bad result {res}")
    for b in "AB":
        check_fen(f"{where0} start {b}", game["start"][b])
    # game moves replay
    ref = c.Bughouse(game["start"]["A"], game["start"]["B"])
    texts_allowed_all = set()
    for k, mv in enumerate(game["moves"]):
        where = f"{gid} move i={mv.get('i')}"
        if set(mv) != MOVE_KEYS:
            err(where, f"move keys {sorted(set(mv) ^ MOVE_KEYS)} differ from the contract")
            return game
        if mv["i"] != k:
            err(where, f"i should be {k}")
        b = "AB".index(mv["board"])
        pos = ref.boards[b]
        seat = mv["board"] + ("white" if pos.turn == chess.WHITE else "black")
        if mv["seat"] != seat:
            err(where, f"seat should be {seat}")
        if mv["num"] != pos.fullmove_number:
            err(where, f"num should be {pos.fullmove_number}")
        if not UCI_RE.match(mv["uci"]) or not ref.is_legal(b, mv["uci"]):
            err(where, f"{mv['uci']!r} is not legal by the referee in {pos.fen()}")
            return game
        before = (c.board_fen(ref, 0), c.board_fen(ref, 1))
        san = c.san_of(pos, chess.Move.from_uci(mv["uci"]))
        ref.push(b, mv["uci"])
        after = (c.board_fen(ref, 0), c.board_fen(ref, 1))
        if norm(san) != norm(mv["san"]):
            err(where, f"SAN {mv['san']!r} should be {san!r}")
        for bb, name in enumerate("AB"):
            if not same_board(mv["fen"][name], after[bb]):
                err(where, f"fen {name} {mv['fen'][name]!r} differs from the referee's {after[bb]!r}")
        for kname in ("t",):
            if mv[kname] is not None and not isinstance(mv[kname], (int, float)):
                err(where, "t must be a number or null")
        if mv["clocks"] is not None and set(mv["clocks"]) != SEATS:
            err(where, "clocks must name the four seats")
        for kname in ("eval", "mate"):
            if mv[kname] is not None and not isinstance(mv[kname], int):
                err(where, f"{kname} must be an integer or null")
        if mv["book"] and (mv["eval"] is not None or mv["mate"] is not None):
            err(where, "a book move has no eval")
        if mv["waited"] is not None and (set(mv["waited"]) != {"seconds", "why"}
                                          or not isinstance(mv["waited"]["why"], str)):
            err(where, f"bad waited {mv['waited']}")
        if mv["glyph"] not in GLYPHS:
            err(where, f"bad glyph {mv['glyph']!r}")
        ids = [ln.get("id") for ln in mv["lines"]]
        if len(ids) != len(set(ids)):
            err(where, "line ids repeat")
        for ln in mv["lines"]:
            check_line(f"{where} line {ln.get('id')}", ln, mv, before, after)
        texts_allowed_all.add(norm(mv["san"]))
        for ln in mv["lines"]:
            texts_allowed_all |= {norm(m["san"]) for m in ln.get("moves", [])}
    if game["result"]["how"] == "checkmate" and game["moves"]:
        loser = 1 - game["result"]["winner"] if game["result"]["winner"] is not None else None
        team = chess.WHITE if loser == 0 else chess.BLACK
        if loser is not None and not (ref.is_checkmate(team, False) or ref.is_checkmate(team, True)):
            err(gid, "the result says checkmate but the referee does not see the losing team mated")
    # text
    check_text(f"{gid} title", game["title"], texts_allowed_all, 60)
    check_text(f"{gid} summary", game["summary"], texts_allowed_all, None)
    fpath = c.OUT / "facts" / f"{gid}.json"
    facts = json.loads(fpath.read_text()) if fpath.exists() else None
    named = {m["i"]: fact_sans(m.get("facts")) for m in facts["moves"]} if facts else {}
    for mv in game["moves"]:
        allowed = allowed_sans(game, mv["i"]) | named.get(mv["i"], set())
        check_text(f"{gid} move i={mv['i']} note", mv["note"], allowed, 500)
        for ln in mv["lines"]:
            check_text(f"{gid} move i={mv['i']} line {ln['id']} note", ln["note"], allowed, 500)
    # against the fact sheet: only text may differ, lines may only be dropped
    if facts:
        compare_with_facts(gid, game, facts)
    else:
        err(gid, f"no fact sheet {fpath}")
    # index entry
    if entry is not None:
        want = {"moves": len(game["moves"]), "notes": sum(1 for m in game["moves"] if m["note"]),
                "title": game["title"], "summary": game["summary"], "event": game["event"], "date": game["date"],
                "seats": game["seats"], "winner": game["result"]["winner"], "how": game["result"]["how"]}
        for k, v in want.items():
            if entry.get(k) != v:
                err(f"index.json {gid}", f"{k} is {entry.get(k)!r}, the game file says {v!r}")
    return game


def compare_with_facts(gid, game, facts):
    def strip_text(obj, path=""):
        if isinstance(obj, dict):
            return {k: strip_text(v, f"{path}.{k}") for k, v in obj.items()
                    if k not in TEXT_FIELDS and k not in ("facts", "builder")}
        if isinstance(obj, list):
            return [strip_text(v, path) for v in obj]
        return obj
    f = strip_text(facts)
    g = strip_text(game)
    fm, gm = f.pop("moves"), g.pop("moves")
    if f != g:
        diffs = [k for k in set(f) | set(g) if f.get(k) != g.get(k)]
        err(gid, f"notes changed more than text: {diffs}")
    if len(fm) != len(gm):
        err(gid, "notes changed the number of moves")
        return
    for a, b in zip(fm, gm):
        la, lb = a.pop("lines"), b.pop("lines")
        if a != b:
            err(f"{gid} move i={a['i']}", f"notes changed {[k for k in a if a[k] != b.get(k)]}")
        ids = [x["id"] for x in la]
        kept = [x["id"] for x in lb]
        if [x for x in ids if x in kept] != kept:
            err(f"{gid} move i={a['i']}", f"lines {sorted(set(kept) - set(ids))} are not in the fact sheet, or reordered")
        byid = {x["id"]: x for x in la}
        for x in lb:
            if x["id"] in byid and byid[x["id"]] != x:
                err(f"{gid} move i={a['i']} line {x['id']}", "notes changed more than the line's note")
        orig = next((m for m in facts["moves"] if m["i"] == a["i"]), {})
        pub = next((m for m in game["moves"] if m["i"] == a["i"]), {})
        if pub.get("glyph") is not None and not (orig.get("facts") or {}).get("key"):
            err(f"{gid} move i={a['i']}", "a glyph on a move that is not key")


def main():
    site = Path(sys.argv[1]) if len(sys.argv) > 1 else c.OUT / "site"
    index_path = site / "index.json"
    if not index_path.exists():
        print(f"no {index_path}")
        sys.exit(1)
    index = json.loads(index_path.read_text())
    if set(index) != {"version", "generated", "source", "games"} or index.get("version") != 1:
        err("index.json", "top-level fields differ from the contract")
    seen = set()
    for e in index.get("games", []):
        if set(e) != INDEX_GAME_KEYS:
            err(f"index.json {e.get('id')}", f"keys {sorted(set(e) ^ INDEX_GAME_KEYS)} differ from the contract")
        if e.get("id") in seen:
            err("index.json", f"{e.get('id')} listed twice")
        seen.add(e.get("id"))
        p = site / str(e.get("file"))
        if not p.exists():
            err(f"index.json {e.get('id')}", f"file {e.get('file')} missing")
            continue
        check_game(p, e)
    for p in site.glob("*.json"):
        if p.name != "index.json" and p.name not in {e.get("file") for e in index.get("games", [])}:
            err(p.name, "not listed in index.json")
    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("FAIL:", e)
    n = len(index.get("games", []))
    print(f"{n} games checked: {len(errors)} failures, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
