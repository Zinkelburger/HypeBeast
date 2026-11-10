#!/usr/bin/env python3
"""Check the arrival forecast against what happened in played games.

`collect` replays arena games (results.jsonl), asks the engine for its forecast
at every decision (`hbforecast`), and records it beside what actually arrived
from the partner board afterwards. `report` scores those forecasts for a grid
of settings, so the three forecast numbers are fitted to data, not guessed:

  temp    how sharply better partner-board lines are favoured (HBForecastTemp)
  trust   share of a forecast arrival that is believed (HBForecastTrust)
  price   how much of a capture's value on our board counts (HBForecastPrice)

Usage:
  forecast_check.py collect --out FILE.jsonl RESULTS.jsonl [RESULTS.jsonl ...]
  forecast_check.py report FILE.jsonl [FILE.jsonl ...]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import chess

from hbutil import ROOT, Bughouse, Engine

BIN = Path(os.environ.get("HB_BIN", ROOT / "engine/src/stockfish"))
TYPES = "QRBNP"
DEFAULT_PRICE = {"P": 40, "N": 100, "B": 100, "R": 130, "Q": 200}
SEAT = {(0, chess.WHITE): "Awhite", (0, chess.BLACK): "Ablack",
        (1, chess.WHITE): "Bwhite", (1, chess.BLACK): "Bblack"}


def captured_letter(game: Bughouse, board: int, uci: str) -> str | None:
    position = game.boards[board]
    move = chess.Move.from_uci(uci)
    kind = Bughouse._captured_type(position, move)
    return None if kind is None else chess.piece_symbol(kind).upper()


def collect_game(job: tuple[str, int, dict, int]) -> list[dict]:
    source, line_no, record, nodes = job
    result = record["result"]
    tokens = result["moves"]
    played = sum(1 for e in result["events"] if e["kind"] == "move")
    first = len(tokens) - played            # the opening prefix is not a decision
    game = Bughouse()
    # (board, mover colour, captured letter or None) for every move
    trace = []
    for token in tokens:
        board, uci = int(token[0]) - 1, token[1:]
        trace.append((board, game.turn(board), captured_letter(game, board, uci)))
        game.push(board, uci)

    engine = Engine(BIN)
    out = []
    try:
        for k in range(first, len(tokens)):
            board, color, _ = trace[k]
            team = color if board == 0 else (not color)
            engine.setoption("Seat", SEAT[(board, color)])
            engine.setoption("Team", "white" if team == chess.WHITE else "black")
            prefix = " ".join(tokens[:k])
            engine.send(f"position startpos moves {prefix}" if prefix else "position startpos")
            engine.send(f"hbforecast nodes {nodes}")
            lines = engine.read_until("hbforecast done", 60)
            forecast = None
            for line in lines:
                if line.startswith("hbforecast {"):
                    forecast = json.loads(line[len("hbforecast "):])
            if forecast is None:
                continue
            # What happened next: partner-board moves over our next two turns,
            # with how many moves had been played on our own board by then
            # (1: after our move, 2: after their reply, 3 and 4: the turn after).
            after = []
            own = 0
            for j in range(k, len(tokens)):
                b, c, cap = trace[j]
                if b == board:
                    if own == 4:
                        break
                    own += 1
                    continue
                after.append({"by_partner": c != color, "captured": cap, "own_moves": own})
            out.append({"source": source, "game": line_no, "ply": k,
                        "seat": SEAT[(board, color)],
                        "contender_seat": (team == chess.WHITE) == (record["contender_team"] == "white"),
                        "forecast": forecast, "after": after})
    finally:
        engine.close()
    return out


def collect(args) -> int:
    jobs = []
    for path in args.results:
        with open(path) as handle:
            for line_no, line in enumerate(handle):
                record = json.loads(line)
                if record["result"]["termination"] == "error":
                    continue
                jobs.append((str(path), line_no, record, args.nodes))
    if args.games:
        jobs = jobs[:args.games]
    rows = 0
    with ProcessPoolExecutor(args.workers) as pool, open(args.out, "w") as sink:
        for done, batch in enumerate(pool.map(collect_game, jobs), 1):
            for row in batch:
                sink.write(json.dumps(row) + "\n")
                rows += 1
            print(f"game {done}/{len(jobs)}: {rows} decisions", flush=True)
    return 0


# ------------------------------------------------------------------ scoring

def parse_arrival(key: str) -> tuple[frozenset, frozenset]:
    """'+N-B' -> (types we get, types they get)."""
    if key == "none":
        return frozenset(), frozenset()
    ours, theirs = set(), set()
    for sign, letter in zip(key[::2], key[1::2]):
        (ours if sign == "+" else theirs).add(letter)
    return frozenset(ours), frozenset(theirs)


def predict(forecast: dict, temp: float, trust: float, price: float) -> dict:
    """Chance that each (side, type) arrives; same arithmetic as weigh()."""
    lines = forecast["lines"]
    if not forecast["ready"] or not lines:
        return {}
    prices = forecast["prices"]
    mover_partner = forecast["mover"] == "partner"
    adjusted = []
    for line in lines:
        ours, theirs = parse_arrival(line["arrival"])
        gain_ours = sum(prices.get("+" + t, DEFAULT_PRICE[t]) for t in ours)
        gain_theirs = sum(prices.get("-" + t, DEFAULT_PRICE[t]) for t in theirs)
        gain = gain_ours - gain_theirs if mover_partner else gain_theirs - gain_ours
        adjusted.append(line["score"] + price * gain)
    best = max(adjusted)
    weights = [math.exp((a - best) / temp) for a in adjusted]
    total = sum(weights)
    chance: dict = {}
    for line, weight in zip(lines, weights):
        ours, theirs = parse_arrival(line["arrival"])
        for t in ours:
            chance[("us", t)] = chance.get(("us", t), 0.0) + trust * weight / total
        for t in theirs:
            chance[("them", t)] = chance.get(("them", t), 0.0) + trust * weight / total
    return chance


def realized(row: dict, window: str) -> set:
    """What arrived. 'two': the first two partner-board moves. 'turn': pieces
    our opponent had by their reply and pieces we had by our next move."""
    got = set()
    for index, move in enumerate(row["after"]):
        if move["captured"] is None or move["own_moves"] > 2:
            continue
        side = "us" if move["by_partner"] else "them"
        if window == "two":
            if index < 2:
                got.add((side, move["captured"]))
        elif side == "us" or move["own_moves"] <= 1:
            got.add((side, move["captured"]))
    return got


def score(rows: list[dict], temp: float, trust: float, price: float, window: str):
    """Mean log loss per (decision, side, type) event, and the reliability table."""
    loss = 0.0
    count = 0
    bins = [[0, 0.0, 0] for _ in range(6)]     # n, sum predicted, hits
    edges = (0.02, 0.1, 0.25, 0.5, 0.75)
    for row in rows:
        chance = predict(row["forecast"], temp, trust, price)
        got = realized(row, window)
        for side in ("us", "them"):
            for t in TYPES:
                p = min(max(chance.get((side, t), 0.0), 0.005), 0.995)
                hit = (side, t) in got
                loss -= math.log(p if hit else 1.0 - p)
                count += 1
                slot = sum(1 for e in edges if p >= e)
                bins[slot][0] += 1
                bins[slot][1] += p
                bins[slot][2] += hit
    return loss / count, bins


def report(args) -> int:
    rows = []
    for path in args.files:
        with open(path) as handle:
            rows.extend(json.loads(line) for line in handle)
    rows = [r for r in rows if r["forecast"]["ready"]]
    print(f"{len(rows)} decisions with a forecast")
    for window in ("turn", "two"):
        base = {}
        for row in rows:
            for event in realized(row, window):
                base[event] = base.get(event, 0) + 1
        rate = sum(base.values()) / (len(rows) * 10)
        floor = -(rate * math.log(rate) + (1 - rate) * math.log(1 - rate))
        print(f"\nwindow={window}: an arrival event happens {100 * rate:.1f}% of the time; "
              f"log loss of always saying that rate = {floor:.4f}")
        results = []
        for temp in (50, 100, 150, 250, 400, 700):
            for trust in (0.4, 0.55, 0.7, 0.85, 1.0):
                for price in (0.0, 0.25, 0.5, 1.0):
                    results.append((score(rows, temp, trust, price, window)[0], temp, trust, price))
        results.sort()
        print("  best settings (log loss, lower is better):")
        for loss, temp, trust, price in results[:6]:
            print(f"    {loss:.4f}  temp={temp} trust={trust} price={price}")
        chosen = (args.temp, args.trust, args.price)
        loss, bins = score(rows, *chosen, window)
        print(f"  chosen temp={chosen[0]} trust={chosen[1]} price={chosen[2]}: log loss {loss:.4f}")
        print("    said      n      mean said   happened")
        labels = ("<2%", "2-10%", "10-25%", "25-50%", "50-75%", ">=75%")
        for label, (n, total, hits) in zip(labels, bins):
            if n:
                print(f"    {label:7} {n:6}   {100 * total / n:6.1f}%    {100 * hits / n:6.1f}%")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("collect")
    c.add_argument("results", nargs="+", type=Path)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--nodes", type=int, default=500_000, help="go budget the forecast takes its shares from")
    c.add_argument("--workers", type=int, default=6)
    c.add_argument("--games", type=int, default=0, help="first N games only")
    c.set_defaults(run=collect)
    r = sub.add_parser("report")
    r.add_argument("files", nargs="+", type=Path)
    r.add_argument("--temp", type=float, default=150)
    r.add_argument("--trust", type=float, default=0.7)
    r.add_argument("--price", type=float, default=0.5)
    r.set_defaults(run=report)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
