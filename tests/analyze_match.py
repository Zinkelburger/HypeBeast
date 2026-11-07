"""Match report and loss analysis from an arena output directory.

    python3 tests/analyze_match.py <match_dir> [--side contender]

Reads results.jsonl, summary.json and engine_logs/ (arena --engine-logs).
Engine logs are split per game at each '>>> uci' (fresh process per game).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import chess

import hbutil  # noqa: F401  (puts the arena on sys.path)
from bughouse_arena.referee import Bughouse, seat_team, team_color
from coverage_stats import coverage

SEATS = ("A-white", "A-black", "B-white", "B-black")


def seat_of(name: str) -> tuple[int, chess.Color]:
    return (0 if name[0] == "A" else 1), (chess.WHITE if name.endswith("white") else chess.BLACK)


def split_games(log: Path) -> list[list[str]]:
    games, cur = [], None
    for line in log.read_text(errors="replace").splitlines():
        if line == ">>> uci":
            cur = []
            games.append(cur)
        elif cur is not None:
            cur.append(line)
    return games


def decisions(lines: list[str]) -> list[dict]:
    """One dict per go: ply (moves in the position), summary, coord report."""
    out, cur = [], None
    for line in lines:
        if line.startswith(">>> position"):
            moves = line.split(" moves ")[1].split() if " moves " in line else []
            cur = {"ply": len(moves), "moves": moves, "summary": {}, "coord": None}
        elif cur is None:
            continue
        elif line.startswith("info string hb_coord "):
            cur["coord"] = json.loads(line[len("info string hb_coord "):])
        elif line.startswith("info string hb_summary "):
            cur["summary"] = dict(kv.split("=", 1) for kv in line.split()[3:] if "=" in kv)
        elif line.startswith("bestmove"):
            cur["bestmove"] = line.split()[1]
            out.append(cur)
            cur = None
    return out


def replay(result: dict) -> Bughouse:
    opening = result["opening"]
    game = Bughouse.from_dual_fen(opening["dual_fen"]) if opening.get("dual_fen") else Bughouse()
    for token in result["result"]["moves"]:
        game.push(int(token[0]) - 1, token[1:])
    return game


def mate_board(game: Bughouse, loser: chess.Color) -> str:
    for b in (0, 1):
        pos = game.boards[b]
        if pos.turn == team_color(loser, b) and pos.is_check() and not game.has_legal_move(b):
            return "AB"[b] + "-check"
    return "no-moves"


def feeding(result: dict, winner: chess.Color, last_plies: int = 8) -> list[str]:
    """Where the winner's drops in the final plies came from (captures of
    the loser's pieces on the other board)."""
    opening = result["opening"]
    game = Bughouse.from_dual_fen(opening["dual_fen"]) if opening.get("dual_fen") else Bughouse()
    moves = result["result"]["moves"]
    captures = []   # (ply, board, captured type, capturer team)
    notes = []
    for ply, token in enumerate(moves):
        b, uci = int(token[0]) - 1, token[1:]
        pos = game.boards[b]
        move = chess.Move.from_uci(uci)
        team = seat_team(b, pos.turn)
        captured = Bughouse._captured_type(pos, move)
        if captured:
            captures.append((ply, b, captured, team))
        if move.drop and team == winner and ply >= len(moves) - last_plies:
            src = [c for c in captures if c[1] != b and c[2] == move.drop and c[3] == winner]
            where = f"captured on {'AB'[src[-1][1]]} at ply {src[-1][0]}" if src else "from opening pockets"
            notes.append(f"ply {ply} {token} ({chess.piece_name(move.drop)} {where})")
        game.push(b, uci)
    return notes


def lat(values: list[float]) -> str:
    if not values:
        return "n/a"
    v = sorted(values)
    return f"mean {statistics.mean(v):.0f} median {v[len(v)//2]:.0f} p95 {v[int(len(v)*0.95)-1]:.0f} max {v[-1]:.0f} ms"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("match")
    args = ap.parse_args()
    root = Path(args.match)
    results = sorted((json.loads(l) for l in (root / "results.jsonl").read_text().splitlines() if l.strip()),
                     key=lambda r: r["game"])
    summary = json.loads((root / "summary.json").read_text()) if (root / "summary.json").exists() else {}
    name = results[0]["contender"]
    logs = {role: split_games(root / "engine_logs" / f"w0-contender-{role}.log")
            for role in ("A", "B") if (root / "engine_logs" / f"w0-contender-{role}.log").exists()}

    print(f"== {name} vs {results[0]['baseline']}: {len(results)} games")
    if summary:
        for k in ("contender_wins", "contender_losses", "draws", "contender_score", "score_confidence_95",
                  "contender_elo", "elo_confidence_95", "pentanomial", "terminations"):
            print(f"  {k}: {summary.get(k)}")
    errors = Counter(r["result"]["termination"] for r in results)
    print("  terminations:", dict(errors), "errors:", sum(bool(r["result"]["error"]) for r in results))

    # latency, sits, flags per side
    side_lat = defaultdict(list)
    sits = Counter()
    for r in results:
        for seat, st in r["seat_stats"].items():
            who = r["seats"][seat]
            side_lat[who] += [x for x in st["latency_ms"] if x > 50]
            sits[who, "passes"] += st.get("passes", 0)
            sits[who, "mandatory"] += st.get("mandatory_sits", 0)
            sits[who, "wakes"] += st.get("wake_requests", 0)
        res = r["result"]
        for team, ms in res["sit_ms"].items():
            who = name if team == r["contender_team"] else r["baseline"]
            sits[who, "sit_ms"] += ms
    for who, v in side_lat.items():
        print(f"  latency {who}: {lat(v)} (decisions>50ms: {len(v)})")
    print("  sitting:", {f"{a}:{b}": c for (a, b), c in sorted(sits.items())})

    # per-decision coordinator stats
    allsum, per_game = [], []
    for gi, r in enumerate(results):
        decs = []
        for role, games in logs.items():
            if gi < len(games):
                decs += [dict(d, role=role) for d in decisions(games[gi])]
        decs.sort(key=lambda d: d["ply"])
        per_game.append(decs)
        allsum += [d["summary"] for d in decs]
    if allsum:
        cov = coverage(allsum)
        print("  coordinator:", json.dumps(cov))

    # override effect: main-search score change at the same seat's next decision
    deltas = defaultdict(list)
    cost = []
    for decs in per_game:
        by_role = defaultdict(list)
        for d in decs:
            by_role[d["role"]].append(d)
        for seq in by_role.values():
            for a, b in zip(seq, seq[1:]):
                sa, sb = a["summary"].get("main_score_cp"), b["summary"].get("main_score_cp")
                if not sa or not sb or sa == "none" or sb == "none":
                    continue
                kind = a["summary"].get("coord_reason", "coord_off")
                deltas[kind].append(int(sb) - int(sa))
            for a in seq:
                c = a["coord"]
                if c and c["reason"] == "override":
                    cands = c["candidates"]
                    chosen = next(x for x in cands if x["move"] == a["summary"]["decision"])
                    cost.append((chosen["L"] - cands[0]["L"], chosen["S"] - cands[0]["S"],
                                 chosen["source"], chosen["delivery"]))
    for kind, v in sorted(deltas.items()):
        if v:
            clipped = [max(-2000, min(2000, x)) for x in v]
            print(f"  next-decision main score change after {kind}: n={len(v)} mean {statistics.mean(clipped):+.0f} "
                  f"median {sorted(clipped)[len(clipped)//2]:+d} worse-by-200+: {sum(x <= -200 for x in clipped)}")
    if cost:
        print(f"  overrides: n={len(cost)} mean local L cost {statistics.mean(c[0] for c in cost):+.0f} cp, "
              f"mean S gain {statistics.mean(c[1] for c in cost):+.0f}, sources {Counter(c[2] for c in cost)}, "
              f"deliveries {Counter(c[3] or '-' for c in cost)}")

    # losses
    print("  -- losses --")
    for gi, r in enumerate(results):
        res = r["result"]
        if r["contender_score"] >= 0.5 and res["winner"] is not None:
            continue
        if res["winner"] is None and res["termination"] != "error":
            print(f"  game {gi} pair {r['pair']}: draw ({res['termination']})")
            continue
        winner = chess.WHITE if res["winner"] == "white" else chess.BLACK
        loser = not winner
        game = replay(r)
        where = mate_board(game, loser) if res["termination"] == "checkmate" else res["termination"]
        decs = per_game[gi]
        ov = [d for d in decs if d["summary"].get("override") == "1"]
        last_ov = [d["ply"] for d in ov if d["ply"] >= len(res["moves"]) - 12]
        print(f"  game {gi} pair {r['pair']} we={r['contender_team']} lost by {res['termination']} [{where}] "
              f"plies={len(res['moves'])} t={res['duration_ms']/1000:.0f}s clocks={res['clocks_ms']} "
              f"overrides={len(ov)} (in last 12 plies: {last_ov}) sits={res['sits']}")
        for n in feeding(r, winner):
            print("      ", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
