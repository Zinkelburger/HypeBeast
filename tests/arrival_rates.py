#!/usr/bin/env python3
"""How often a forecast capture really arrives: calibration data for the
in-tree chance search.

Reads arena match directories played with --engine-logs. Every HypeBeast
decision prints `info string hb_forecast {json}`: up to a few partner-board
lines, each with a weight and `captures` entries such as "0-N" or "3+Q"
(partner-board ply, + for a capture by our partner, which sends the piece to
us, - for one by our partner's opponent, which sends it to our opponent, and
the captured type). Each decision is joined with the game's real move list
(results.jsonl) to see what arrived afterwards.

Arrival windows, counted in moves on our own board after the decision (our
move is the first):

  receiver us,   k=0: before our next move (own-board moves 1-2 done)
  receiver us,   k=1: before the move after that (moves 1-4)
  receiver them, k=0: before the opponent's reply (move 1)
  receiver them, k=1: before the opponent's next reply (moves 1-3)

A window still open when the game ended counts as "did not arrive" (the
piece can no longer matter); the number of such windows is printed. Sits are
not moves, so a seat that sits gets a longer window in game time.

Forecast quantities per decision, receiver side s and piece type t:
  W01  sum of weights of lines with an s-t capture at plies 0-1
  W23  sum of weights of lines with an s-t capture at plies 2-3 and none at 0-1
Tables:
  (a) k=0 calibration of trust * W01 for trust 0.7/0.85/1.0
  (b) events with W01 = 0 and W23 > 0: arrival by k=1 (and k=0) by W23 bucket
  (c) events with no s-t capture anywhere in the forecast: base rates by
      k=0 and k=1, per type and side
  (d) all of the above per group (self-play, against HiveMind)
and fitted models
  k=0: p = floor + (1 - floor) * trust * W01
  k=1: p = floor + (1 - floor) * min(1, trust * W01 + trustLate * W23)
by grid search on mean log loss (p clipped to [0.001, 0.999]), with a
bootstrap over games for the spread of the fitted values.

Usage:
  arrival_rates.py MATCH_DIR [MATCH_DIR ...] [--json OUT] [--bootstrap N]

A match counts as "hivemind" when either side's kind is hivemind in its
manifest, else "selfplay". Identical decisions (same move list, seat and
budget, as happen in the mirrored games of a deterministic self-play pair)
are counted once.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import chess

import hbutil  # noqa: F401  (puts the arena on sys.path)
from bughouse_arena.referee import Bughouse

TYPES = "PNBRQ"
SIDES = ("us", "them")
WINDOW = {("us", 0): 2, ("us", 1): 4, ("them", 0): 1, ("them", 1): 3}
CLIP = 0.001
CAPTURE = re.compile(r"^(\d+)([+-])([PNBRQK])$")


# ------------------------------------------------------------------ games

def load_games(match: Path) -> list[dict]:
    games = []
    for line in (match / "results.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        result = record["result"]
        if result["termination"] == "error":
            continue
        opening = record.get("opening") or {}
        game = (Bughouse.from_dual_fen(opening["dual_fen"]) if opening.get("dual_fen")
                else Bughouse())
        trace = []      # (board, mover colour, captured letter or None) per token
        for token in result["moves"]:
            board, uci = int(token[0]) - 1, token[1:]
            position = game.boards[board]
            kind = Bughouse._captured_type(position, chess.Move.from_uci(uci))
            trace.append((board, position.turn,
                          None if kind is None else chess.piece_symbol(kind).upper()))
            game.push(board, uci)
        games.append({"id": f"{match.name}:{record['game']}", "tokens": result["moves"],
                      "contender_team": record["contender_team"],
                      "trace": trace, "dual_fen": opening.get("dual_fen")})
    return games


def outcomes(game: dict, n: int, board: int, color: chess.Color) -> tuple[dict, bool]:
    """For a decision before token n by seat (board, colour): for each
    (side, type), the number of own-board moves played when it first
    arrived (None if never). Also whether the game ended inside the longest
    window."""
    partner_color = not color          # our partner's colour on the other board
    first: dict = {}
    own = 0
    trace = game["trace"]
    for j in range(n, len(trace)):
        b, mover, captured = trace[j]
        if b == board:
            own += 1
            if own > 4:
                return first, False
            continue
        if captured is None:
            continue
        side = "us" if mover == partner_color else "them"
        first.setdefault((side, captured), own)
    return first, True


# ------------------------------------------------------------- engine logs

def split_decisions(log: Path):
    """Yield (seat, moves tuple, dual fen or None, budget, forecast, bestmove)."""
    seat = None
    moves = fen = budget = forecast = None
    for line in log.read_text(errors="replace").splitlines():
        if line.startswith(">>> "):
            cmd = line[4:]
            if cmd == "uci":
                seat = None
            elif cmd.startswith("setoption name Seat value "):
                seat = cmd.split()[-1]
            elif cmd.startswith("position "):
                body, _, tail = cmd.partition(" moves ")
                moves = tuple(tail.split()) if tail else ()
                fen = body[len("position fen "):] if body.startswith("position fen ") else None
                forecast = None
            elif cmd.startswith("go "):
                budget = cmd[3:]
            continue
        if line.startswith("info string hb_forecast "):
            try:
                forecast = json.loads(line[len("info string hb_forecast "):])
            except json.JSONDecodeError:
                forecast = None
        elif line.startswith("bestmove") and moves is not None:
            yield seat, moves, fen, budget, forecast, line.split(None, 1)[1].strip()
            moves = forecast = None


def features(forecast: dict) -> dict:
    """(side, type) -> (W01, W23-only, seen anywhere)."""
    w01: dict = defaultdict(float)
    w23: dict = defaultdict(float)
    seen = set()
    for line in forecast["lines"]:
        early, late = set(), set()
        for entry in line.get("captures", []):
            m = CAPTURE.match(entry)
            if not m:
                continue
            ply, sign, t = int(m.group(1)), m.group(2), m.group(3)
            key = ("us" if sign == "+" else "them", t)
            seen.add(key)
            (early if ply <= 1 else late).add(key)
        for key in early:
            w01[key] += line["weight"]
        for key in late - early:
            w23[key] += line["weight"]
    return {key: (w01.get(key, 0.0), w23.get(key, 0.0), key in seen)
            for key in seen}


def collect(match: Path, stats: dict) -> list[dict]:
    manifest = json.loads((match / "manifest.json").read_text())
    kinds = {manifest["sides"][r]["kind"] for r in ("contender", "baseline")}
    group = "hivemind" if "hivemind" in kinds else "selfplay"
    games = load_games(match)
    by_prefix: dict = defaultdict(list)
    for gi, game in enumerate(games):
        tokens = tuple(game["tokens"])
        for n in range(len(tokens)):
            by_prefix[(game["dual_fen"], tokens[:n])].append(gi)
    rows = []
    seen = set()
    logs = sorted((match / "engine_logs").glob("w*-*.log"))
    for log in logs:
        role = "contender" if "-contender-" in log.name else "baseline"
        for seat, moves, fen, budget, forecast, best in split_decisions(log):
            if forecast is None:
                continue
            stats["decisions_logged"] += 1
            if not forecast.get("ready") or not forecast.get("lines"):
                stats["forecast_not_ready"] += 1
                continue
            board = 0 if seat[0] == "A" else 1
            color = chess.WHITE if seat[1:] == "white" else chess.BLACK
            pair = best.strip("()").split(",")
            mine = pair[board] if len(pair) == 2 else "pass"
            if mine == "pass":
                stats["sits"] += 1
                continue
            key = (fen, moves, seat, budget)
            if key in seen:
                stats["duplicates"] += 1
                continue
            seen.add(key)
            candidates = [gi for gi in by_prefix.get((fen, moves), ())
                          if games[gi]["tokens"][len(moves)] == f"{board + 1}{mine}"]
            # The log's side must hold this seat in the game (both games of a
            # pair start from the same opening with the teams swapped).
            team = "white" if (color == chess.WHITE) == (board == 0) else "black"
            candidates = [gi for gi in candidates
                          if (games[gi]["contender_team"] == team) == (role == "contender")]
            if not candidates:
                stats["unmatched"] += 1
                continue
            conts = {tuple(games[gi]["tokens"][len(moves):len(moves) + 12]) for gi in candidates}
            if len(conts) > 1:
                stats["ambiguous_continuation"] += 1
            game = games[candidates[0]]
            first, censored = outcomes(game, len(moves), board, color)
            stats["censored"] += censored
            rows.append({"group": group, "match": match.name, "game": game["id"],
                         "seat": seat, "ply": len(moves), "budget": budget,
                         "features": features(forecast), "first": first})
    stats["games_" + group] += len(games)
    return rows


# ---------------------------------------------------------------- analysis

def events(rows: list[dict]):
    """One event per (decision, side, type): (row, side, t, W01, W23, seen,
    hit0, hit1)."""
    for row in rows:
        feats, first = row["features"], row["first"]
        for side in SIDES:
            for t in TYPES:
                w01, w23, seen = feats.get((side, t), (0.0, 0.0, False))
                when = first.get((side, t))
                hit0 = when is not None and when <= WINDOW[(side, 0)]
                hit1 = when is not None and when <= WINDOW[(side, 1)]
                yield row, side, t, w01, w23, seen, hit0, hit1


def clip(p: float) -> float:
    return min(max(p, CLIP), 1 - CLIP)


def nll(p: float, hit: bool) -> float:
    p = clip(p)
    return -math.log(p if hit else 1 - p)


def wilson(hits: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    z = 1.96
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def pct(x: float) -> str:
    return "  n/a" if x != x else f"{100 * x:5.1f}"


BUCKETS = (0.0, 0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.0001)


def bucket(p: float) -> int:
    for i in range(len(BUCKETS) - 1):
        if p < BUCKETS[i + 1]:
            return i
    return len(BUCKETS) - 2


def bucket_label(i: int) -> str:
    lo, hi = BUCKETS[i], min(BUCKETS[i + 1], 1.0)
    return f"[{lo:.2f},{hi:.2f}{']' if hi >= 1 else ')'}"


def table_a(evs: list, out: list) -> None:
    out.append("(a) k=0 calibration of p = trust * W01 (all events; p=0 rows are events "
               "with no plies-0-1 capture of that side/type)")
    for trust in (0.7, 0.85, 1.0):
        cells = defaultdict(lambda: [0, 0.0, 0])
        loss = 0.0
        for _, _, _, w01, _, _, hit0, _ in evs:
            p = trust * w01
            loss += nll(p, hit0)
            c = cells[-1 if p == 0 else bucket(p)]
            c[0] += 1
            c[1] += p
            c[2] += hit0
        loss_pos = [nll(trust * e[3], e[6]) for e in evs if e[3] > 0]
        out.append(f"  trust={trust}: mean log loss {loss / max(1, len(evs)):.4f} over "
                   f"{len(evs)} events (clip {CLIP}); on the {len(loss_pos)} events with "
                   f"W01>0: {sum(loss_pos) / max(1, len(loss_pos)):.4f}")
        out.append("    predicted bucket        n   mean pred  observed  95% CI")
        for key in sorted(cells):
            n, sp, hits = cells[key]
            lo, hi = wilson(hits, n)
            label = "p=0 (none at 0-1)" if key == -1 else bucket_label(key)
            out.append(f"    {label:20} {n:7}   {pct(sp / n)}%    {pct(hits / n)}%   "
                       f"[{pct(lo)}, {pct(hi)}]")


def table_b(evs: list, out: list) -> None:
    out.append("(b) captures first seen at plies 2-3 (W01=0, W23>0): arrival by weight bucket")
    cells = defaultdict(lambda: [0, 0, 0, 0.0])
    for _, _, _, w01, w23, _, hit0, hit1 in evs:
        if w01 == 0 and w23 > 0:
            c = cells[bucket(w23)]
            c[0] += 1
            c[1] += hit0
            c[2] += hit1
            c[3] += w23
    out.append("    W23 bucket            n   mean W23  by k=0   by k=1  95% CI (k=1)")
    for key in sorted(cells):
        n, h0, h1, sw = cells[key]
        lo, hi = wilson(h1, n)
        out.append(f"    {bucket_label(key):18} {n:6}   {pct(sw / n)}%   {pct(h0 / n)}%   "
                   f"{pct(h1 / n)}%  [{pct(lo)}, {pct(hi)}]")
    tot = [sum(c[i] for c in cells.values()) for i in range(3)]
    if tot[0]:
        out.append(f"    all {tot[0]}: by k=0 {pct(tot[1] / tot[0])}%, by k=1 {pct(tot[2] / tot[0])}%")


def table_c(evs: list, out: list) -> dict:
    out.append("(c) base rate when the forecast shows no capture of that side/type in its 4 plies")
    cells = defaultdict(lambda: [0, 0, 0])
    for _, side, t, _, _, seen, hit0, hit1 in evs:
        if not seen:
            for key in ((side, t), (side, "*")):
                c = cells[key]
                c[0] += 1
                c[1] += hit0
                c[2] += hit1
    out.append("    side  type       n    by k=0  95% CI           by k=1  95% CI")
    rates = {}
    for side in SIDES:
        for t in TYPES + "*":
            n, h0, h1 = cells[(side, t)]
            if not n:
                continue
            l0, u0 = wilson(h0, n)
            l1, u1 = wilson(h1, n)
            rates[(side, t)] = (h0 / n, h1 / n)
            out.append(f"    {side:5} {t:4} {n:7}   {pct(h0 / n)}%  [{pct(l0)}, {pct(u0)}]   "
                       f"{pct(h1 / n)}%  [{pct(l1)}, {pct(u1)}]")
    return rates


# ---- fitting on aggregated cells, so the grid search stays cheap

def cells_k0(evs: list) -> dict:
    agg = defaultdict(lambda: [0, 0])
    for _, _, _, w01, _, _, hit0, _ in evs:
        c = agg[round(w01, 3)]
        c[0] += 1
        c[1] += hit0
    return agg


def cells_k1(evs: list) -> dict:
    agg = defaultdict(lambda: [0, 0])
    for _, _, _, w01, w23, _, _, hit1 in evs:
        c = agg[(round(w01 / 2, 2) * 2, round(w23 / 2, 2) * 2)]   # 0.02 steps
        c[0] += 1
        c[1] += hit1
    return agg


def cell_loss(p: float, n: int, hits: int) -> float:
    p = clip(p)
    return -(hits * math.log(p) + (n - hits) * math.log(1 - p))


TRUSTS = [round(0.3 + 0.05 * i, 2) for i in range(15)]           # 0.30 .. 1.00
LATES = [round(0.05 * i, 2) for i in range(21)]                    # 0.00 .. 1.00
FLOORS = [round(0.0025 * i, 4) for i in range(41)]                 # 0 .. 0.10


def fit_k0(agg: dict) -> tuple[float, float, float]:
    total = sum(c[0] for c in agg.values())
    best = None
    for trust in TRUSTS:
        for floor in FLOORS:
            loss = sum(cell_loss(floor + (1 - floor) * trust * w, n, h)
                       for w, (n, h) in agg.items())
            if best is None or loss < best[0]:
                best = (loss, trust, floor)
    return best[0] / max(1, total), best[1], best[2]


def fit_k1(agg: dict) -> tuple[float, float, float, float]:
    """Coarse grid (0.1, 0.1, 0.01), then the fine grid (0.05, 0.05, 0.0025)
    within one coarse step of the coarse optimum."""
    total = sum(c[0] for c in agg.values())
    items = list(agg.items())

    def loss_of(trust, late, floor):
        return sum(cell_loss(floor + (1 - floor) * min(1.0, trust * a + late * b), n, h)
                   for (a, b), (n, h) in items)
    best = min((loss_of(t, l, f), t, l, f)
               for t in TRUSTS[::2] for l in LATES[::2] for f in FLOORS[::4])
    _, t0, l0, f0 = best
    for t in TRUSTS:
        if abs(t - t0) > 0.1001:
            continue
        for l in LATES:
            if abs(l - l0) > 0.1001:
                continue
            for f in FLOORS:
                if abs(f - f0) > 0.01001:
                    continue
                cand = (loss_of(t, l, f), t, l, f)
                if cand < best:
                    best = cand
    return best[0] / max(1, total), best[1], best[2], best[3]


def base_loss(evs: list, which: int) -> float:
    hits = sum(e[6 + which] for e in evs)
    rate = hits / max(1, len(evs))
    return -(rate * math.log(clip(rate)) + (1 - rate) * math.log(clip(1 - rate)))


def per_type_floor_loss(evs: list, rates: dict, trust: float, which: int,
                        late: float = 0.0) -> float:
    loss = 0.0
    for _, side, t, w01, w23, _, hit0, hit1 in evs:
        floor = rates.get((side, t), (0.0, 0.0))[which]
        p = floor + (1 - floor) * min(1.0, trust * w01 + late * w23)
        loss += nll(p, hit1 if which else hit0)
    return loss / max(1, len(evs))


def bootstrap(rows: list[dict], n: int, seed: int = 7) -> dict:
    by_game: dict = defaultdict(list)
    for row in rows:
        by_game[row["game"]].append(row)
    keys = sorted(by_game)
    rng = random.Random(seed)
    fits0, fits1 = [], []
    for _ in range(n):
        sample = [r for _ in keys for r in by_game[rng.choice(keys)]]
        evs = list(events(sample))
        fits0.append(fit_k0(cells_k0(evs))[1:])
        fits1.append(fit_k1(cells_k1(evs))[1:])

    def spread(values):
        values = sorted(values)
        return values[int(0.025 * len(values))], values[min(len(values) - 1, int(0.975 * len(values)))]
    return {"k0_trust": spread([f[0] for f in fits0]), "k0_floor": spread([f[1] for f in fits0]),
            "k1_trust": spread([f[0] for f in fits1]), "k1_late": spread([f[1] for f in fits1]),
            "k1_floor": spread([f[2] for f in fits1]), "n": n}


def analyse(name: str, rows: list[dict], boot: int) -> tuple[list[str], dict]:
    out = []
    evs = list(events(rows))
    games = len({r["game"] for r in rows})
    out.append(f"===== {name}: {len(rows)} decisions with a ready forecast, {games} games, "
               f"{len(evs)} (decision, side, type) events")
    if not rows:
        return out, {}
    budgets = defaultdict(int)
    for r in rows:
        budgets[r["budget"]] += 1
    out.append(f"  budgets: {dict(budgets)}")
    for which, label in ((0, "k=0"), (1, "k=1")):
        hits = sum(e[6 + which] for e in evs)
        out.append(f"  any arrival {label}: {hits}/{len(evs)} events ({pct(hits / len(evs))}%); "
                   f"log loss of the constant base rate {base_loss(evs, which):.4f}")
    table_a(evs, out)
    table_b(evs, out)
    rates = table_c(evs, out)
    l0, trust0, floor0 = fit_k0(cells_k0(evs))
    l1, trust1, late1, floor1 = fit_k1(cells_k1(evs))
    out.append("  fitted (grid: trust 0.30-1.00 by 0.05, trustLate 0-1 by 0.05, floor 0-0.10 by 0.0025)")
    out.append(f"    k=0: trust={trust0} floor={floor0}  log loss {l0:.4f}")
    out.append(f"    k=1: trust={trust1} trustLate={late1} floor={floor1}  log loss {l1:.4f}")
    for trust in (0.7, 0.85, 1.0):
        out.append(f"    k=0 with trust={trust}, floor=0: "
                   f"{sum(cell_loss(trust * w, n, h) for w, (n, h) in cells_k0(evs).items()) / len(evs):.4f}"
                   f"; per-type floors from (c): {per_type_floor_loss(evs, rates, trust, 0):.4f}")
    out.append(f"    k=1 with fitted trust/trustLate and per-type floors from (c): "
               f"{per_type_floor_loss(evs, rates, trust1, 1, late1):.4f}")
    by_side = {}
    for side in SIDES:
        sub = [e for e in evs if e[1] == side]
        s0 = fit_k0(cells_k0(sub))
        s1 = fit_k1(cells_k1(sub))
        by_side[side] = {"k0": {"trust": s0[1], "floor": s0[2], "log_loss": s0[0]},
                         "k1": {"trust": s1[1], "trustLate": s1[2], "floor": s1[3],
                                "log_loss": s1[0]}, "events": len(sub)}
        out.append(f"    receiver {side:4} ({len(sub)} events): k=0 trust={s0[1]} floor={s0[2]} "
                   f"({s0[0]:.4f}); k=1 trust={s1[1]} trustLate={s1[2]} floor={s1[3]} ({s1[0]:.4f})")
    result = {"decisions": len(rows), "games": games, "events": len(evs),
              "k0": {"trust": trust0, "floor": floor0, "log_loss": l0},
              "k1": {"trust": trust1, "trustLate": late1, "floor": floor1, "log_loss": l1},
              "base_rates": {f"{s}{t}": v for (s, t), v in rates.items()},
              "by_side": by_side}
    if boot:
        spread = bootstrap(rows, boot)
        result["bootstrap"] = spread
        out.append(f"    bootstrap over games ({boot} resamples, 2.5-97.5%): "
                   + ", ".join(f"{k} {v[0]}-{v[1]}" for k, v in spread.items() if k != "n"))
    return out, result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("matches", nargs="+", type=Path)
    parser.add_argument("--json", type=Path, help="write the fitted values and counts here")
    parser.add_argument("--bootstrap", type=int, default=0,
                        help="resamples over games for the fitted values (default 0)")
    args = parser.parse_args()
    stats: dict = defaultdict(int)
    rows = []
    for match in args.matches:
        rows += collect(match, stats)
    print("collection:", json.dumps(dict(stats)))
    report = {"stats": dict(stats)}
    groups = [(g, [r for r in rows if r["group"] == g]) for g in ("selfplay", "hivemind")]
    if all(subset for _, subset in groups):
        groups = [("all", rows)] + groups
    for name, subset in groups:
        if not subset:
            continue
        lines, result = analyse(name, subset, args.bootstrap)
        print("\n".join(lines) + "\n")
        report[name] = result
    if args.json:
        args.json.write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
