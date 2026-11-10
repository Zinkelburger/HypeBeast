#!/usr/bin/env python3
"""A fixed test set cut from lost games: did we close the hole we were mated through?

Every game a side lost by checkmate ends with the opponent's mating move on
some board X. Moves on a board alternate, so the move before it on X was ours:
the last chance to prevent the mate. An item is the position before that move,
plus the partner-board moves that were then played before the mate (they
deliver whatever pieces arrived in between).

A binary passes an item when, after the move it chooses and those same
partner-board moves, the opponent has no immediate mate on X. Items where no
legal move avoids that are listed as unavoidable and not counted.

With `build --earlier`, the item is our move before that one, where there was
still time. No single reply decides it, so a judge does: after the chosen move
the pieces that really arrived before the mate are handed over, and a plain
one-board search for the opponent (bin/hypebeast-v3, Coordination=false) says
whether it is a forced mate.

  loss_set.py build --out FILE.json [--side contender] [--earlier] RESULTS.jsonl [...]
  loss_set.py run FILE.json --bin PATH [--movetime 1000] [--workers 3] [--option K=V ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import chess

from hbutil import ROOT, Bughouse, Engine, parse_bestmove

JUDGE = ROOT / "bin/hypebeast-v3"
JUDGE_NODES = 400_000

SEAT = {(0, chess.WHITE): "Awhite", (0, chess.BLACK): "Ablack",
        (1, chess.WHITE): "Bwhite", (1, chess.BLACK): "Bblack"}


def mated_after(prefix: list[str], board: int, move: str, between: list[str], team: chess.Color) -> bool:
    """Play `move`, then the partner-board moves that followed in the game.
    Is there then an immediate mating move on `board` against `team`?"""
    game = Bughouse()
    for token in prefix:
        game.push(int(token[0]) - 1, token[1:])
    game.push(board, move)
    for token in between:
        b, uci = int(token[0]) - 1, token[1:]
        if not game.is_legal(b, uci):
            break
        game.push(b, uci)
    for reply in game.legal_moves(board):
        after = game.copy()
        after.push(board, reply)
        if after.is_checkmate(team, False) and after.is_checkmate(team, True):
            return True
    return False


def forced_mate_after(prefix: list[str], board: int, move: str, between: list[str]) -> bool:
    """Play `move`, hand over what arrived from the partner board before the
    mate, and ask the judge whether the opponent now mates by force."""
    game = Bughouse()
    for token in prefix:
        game.push(int(token[0]) - 1, token[1:])
    game.push(board, move)
    for token in between:
        b, uci = int(token[0]) - 1, token[1:]
        if b != board and game.is_legal(b, uci):
            game.push(b, uci)
    color = game.turn(board)                       # the opponent, to move
    if not game.legal_moves(board):
        return False
    team = color if board == 0 else (not color)
    judge = Engine(JUDGE, options={"Coordination": "false", "Seat": SEAT[(board, color)],
                                   "Team": "white" if team == chess.WHITE else "black"})
    try:
        judge.send(f"position fen {game.dual_fen()}")
        lines = judge.go(f"go nodes {JUDGE_NODES}", timeout=120)
    finally:
        judge.close()
    scores = [l for l in lines if l.startswith("info depth") and " score " in l]
    return bool(scores) and " score mate " in scores[-1] and not scores[-1].split(" score mate ")[1].startswith("-")


def build(args) -> int:
    items = []
    for path in args.results:
        with open(path) as handle:
            for line_no, line in enumerate(handle):
                record = json.loads(line)
                result = record["result"]
                if result["termination"] != "checkmate":
                    continue
                side_team = record["contender_team"] if args.side == "contender" else (
                    "black" if record["contender_team"] == "white" else "white")
                if result["winner"] == side_team:
                    continue
                team = chess.WHITE if side_team == "white" else chess.BLACK
                tokens = result["moves"]
                board = int(tokens[-1][0]) - 1                  # the mating move's board
                own = [i for i in range(len(tokens) - 1) if int(tokens[i][0]) - 1 == board][::-2]
                move_count = sum(1 for e in result["events"] if e["kind"] == "move")
                if args.earlier:
                    if len(own) < 2 or own[1] < len(tokens) - move_count:
                        continue                                # no earlier move of ours in the game
                    last = own[1]
                    prefix, played, between = tokens[:last], tokens[last][1:], tokens[last + 1:-1]
                    game = Bughouse()
                    for token in prefix:
                        game.push(int(token[0]) - 1, token[1:])
                    color = game.turn(board)
                    move_events = [e for e in result["events"] if e["kind"] == "move"]
                    event = move_events[last - (len(tokens) - len(move_events))]
                    items.append({
                        "source": str(path), "game": line_no, "ply": last, "earlier": True,
                        "seat": SEAT[(board, color)], "team": side_team,
                        "prefix": prefix, "played": played, "between": between, "mate": tokens[-1][1:],
                        "arrived_between": [], "clocks": event["clocks"], "advantage": event["advantage"],
                        "legal": len(game.legal_moves(board)), "avoiding_moves": -1,
                    })
                    continue
                last = own[0]
                prefix, played, between = tokens[:last], tokens[last][1:], tokens[last + 1:-1]
                game = Bughouse()
                for token in prefix:
                    game.push(int(token[0]) - 1, token[1:])
                color = game.turn(board)
                move_events = [e for e in result["events"] if e["kind"] == "move"]
                event = move_events[last - (len(tokens) - len(move_events))]
                avoiding = [m for m in game.legal_moves(board)
                            if not mated_after(prefix, board, m, between, team)]
                arrived = []
                probe = game.copy()
                probe.push(board, played)
                for token in between:
                    b, uci = int(token[0]) - 1, token[1:]
                    captured = Bughouse._captured_type(probe.boards[b], chess.Move.from_uci(uci))
                    if captured and probe.turn(b) == color:    # the opponent's partner feeds our opponent
                        arrived.append(chess.piece_symbol(captured).upper())
                    probe.push(b, uci)
                items.append({
                    "source": str(path), "game": line_no, "ply": last,
                    "seat": SEAT[(board, color)], "team": side_team,
                    "prefix": prefix, "played": played, "between": between, "mate": tokens[-1][1:],
                    "arrived_between": arrived, "clocks": event["clocks"], "advantage": event["advantage"],
                    "legal": len(game.legal_moves(board)), "avoiding_moves": len(avoiding),
                })
    args.out.write_text(json.dumps(items, indent=1))
    avoidable = sum(1 for i in items if i["avoiding_moves"])
    fed = sum(1 for i in items if i["arrived_between"])
    print(f"{args.out}: {len(items)} lost games, {avoidable} with a move that avoids the mate, "
          f"{fed} where the mating side was fed in between")
    return 0


def run_item(job) -> dict:
    item, binary, movetime, options = job
    engine = Engine(Path(binary), options=options)
    try:
        engine.setoption("Seat", item["seat"])
        engine.setoption("Team", item["team"])
        engine.setoption("Clocks", ",".join(map(str, item["clocks"])))
        engine.setoption("TimeAdvantage", "true" if item["advantage"] else "false")
        engine.send("position startpos moves " + " ".join(item["prefix"]))
        lines = engine.go(f"go movetime {movetime}", timeout=60 + movetime / 1000)
    finally:
        engine.close()
    board = 0 if item["seat"][0] == "A" else 1
    move = parse_bestmove(lines)[board]
    reason = next((l.split("reason=")[1].split()[0] for l in lines
                   if l.startswith("info string hb_summary ") and " reason=" in l), "?")
    team = chess.WHITE if item["team"] == "white" else chess.BLACK
    if move == "pass":
        verdict = "sat"
    elif item.get("earlier"):
        verdict = "mated" if forced_mate_after(item["prefix"], board, move, item["between"]) else "avoided"
    elif mated_after(item["prefix"], board, move, item["between"], team):
        verdict = "mated"
    else:
        verdict = "avoided"
    return {"game": item["game"], "ply": item["ply"], "seat": item["seat"], "played": item["played"],
            "move": move, "reason": reason, "verdict": verdict}


def run(args) -> int:
    items = [i for i in json.loads(args.items.read_text()) if i["avoiding_moves"]]
    options = dict(o.split("=", 1) for o in args.option)
    jobs = [(i, str(args.bin.resolve()), args.movetime, options) for i in items]
    with ProcessPoolExecutor(args.workers) as pool:
        rows = list(pool.map(run_item, jobs))
    counts: dict = {}
    for item, row in zip(items, rows):
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        if args.verbose:
            print(f"  game {row['game']:3} ply {row['ply']:3} {row['seat']:6} game move {row['played']:6} "
                  f"-> {row['move']:6} {row['verdict']:8} ({row['reason']}) arrived={''.join(item['arrived_between']) or '-'}")
    print(f"{args.bin.name} movetime={args.movetime} {options or ''}: {len(rows)} items: "
          + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("results", nargs="+", type=Path)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--side", choices=("contender", "baseline"), default="contender")
    b.add_argument("--earlier", action="store_true", help="our move before the last one, judged by search")
    b.set_defaults(fn=build)
    r = sub.add_parser("run")
    r.add_argument("items", type=Path)
    r.add_argument("--bin", type=Path, required=True)
    r.add_argument("--movetime", type=int, default=1000)
    r.add_argument("--workers", type=int, default=3)
    r.add_argument("--option", action="append", default=[])
    r.add_argument("--verbose", action="store_true")
    r.set_defaults(fn=run)
    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
