#!/usr/bin/env python3
"""How well does the forecast predict what arrives, and when?

usage: arrivals.py OUT_JSON MATCH_DIR [MATCH_DIR ...]

For every logged decision with a forecast, replays the rest of the game and
records, for each capture the forecast named and for each world, whether it
happened and after how many plies of OUR board (q). q=0: before the move we
were deciding; q=1: before the opponent's reply; q=2: before our next move.
"""
import collections
import glob
import json
import re
import sys

import chess
import chess.variant

NAMES = {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q"}


def replay(tokens):
    """-> list of (token index, board, mover is white, captured type letter)."""
    b = {"1": chess.variant.CrazyhouseBoard(), "2": chess.variant.CrazyhouseBoard()}
    caps = []
    for i, t in enumerate(tokens):
        board = b[t[0]]
        mover = board.turn
        move = chess.Move.from_uci(t[1:])
        before = {p: board.pockets[mover].count(p) for p in NAMES}
        board.push(move)
        for p in NAMES:
            if board.pockets[mover].count(p) > before[p]:
                board.pockets[mover].remove(p)
                b["2" if t[0] == "1" else "1"].pockets[not mover].add(p)
                caps.append((i, t[0], mover, NAMES[p]))
    return caps


def parse_key(key):
    """'+N-B' -> Counter({'+N':1,'-B':1})"""
    c = collections.Counter()
    if key == "none":
        return c
    for sign, t in re.findall(r"([+-])([PNBRQ])", key):
        c[sign + t] += 1
    return c


def main():
    out, dirs = sys.argv[1], sys.argv[2:]
    rows = []
    for d in dirs:
        tag = d.rstrip("/").split("/")[-1]
        games = []
        for l in open(f"{d}/results.jsonl"):
            r = json.loads(l)
            toks = list(r["opening"]["moves"])
            for e in r["result"]["events"]:
                if e["kind"] == "move":
                    toks.append(("1" if e["board"] == "A" else "2") + e["uci"])
            games.append({"game": r["game"], "toks": toks, "caps": replay(toks), "seats": r["seats"],
                          "contender": r["contender"]})
        index = collections.defaultdict(list)
        for g in games:
            index[tuple(g["toks"][:12])].append(g)
        unmatched = 0
        for path in sorted(glob.glob(f"{d}/engine_logs/w*-*.log")):
            role = "contender" if "-contender-" in path else "baseline"
            seat = None
            moves = None
            for line in open(path, errors="replace"):
                if line.startswith(">>> setoption name Seat value "):
                    seat = line.split()[-1]
                elif line.startswith(">>> position startpos moves "):
                    moves = line.split()[4:]
                elif line.startswith("info string hb_forecast "):
                    fc = json.loads(line[len("info string hb_forecast "):])
                    if not fc.get("ready") or moves is None:
                        continue
                    g = next((g for g in index.get(tuple(moves[:12]), []) if g["toks"][:len(moves)] == moves), None)
                    if g is None:
                        unmatched += 1
                        continue
                    n = len(moves)
                    ours = "1" if seat[0] == "A" else "2"
                    white = seat.endswith("white")
                    # captures on the partner board after this decision, with q
                    q = 0
                    future = []           # (q, key like '+N', partner-board ply index from now)
                    ci = 0
                    caps = [c for c in g["caps"] if c[0] >= n and c[1] != ours]
                    pply = 0
                    for i in range(n, len(g["toks"])):
                        t = g["toks"][i]
                        if t[0] == ours:
                            q += 1
                            continue
                        while ci < len(caps) and caps[ci][0] == i:
                            # partner has the other colour on the other board
                            to_us = caps[ci][2] != white
                            future.append((q, ("+" if to_us else "-") + caps[ci][3], pply))
                            ci += 1
                        pply += 1
                    left_ours = sum(1 for t in g["toks"][n:] if t[0] == ours)
                    rows.append({"tag": tag, "role": role, "game": g["game"], "seat": seat, "n": n,
                                 "mover": fc["mover"], "left": left_ours, "future": future,
                                 "lines": [{"w": l["weight"], "caps": l.get("captures", []), "src": l["source"]}
                                           for l in fc["lines"]],
                                 "worlds": fc["worlds"]})
        print(f"{tag}: games={len(games)} unmatched_decisions={unmatched}", file=sys.stderr)
    json.dump(rows, open(out, "w"))
    print(f"rows={len(rows)}", file=sys.stderr)


if __name__ == "__main__":
    main()
