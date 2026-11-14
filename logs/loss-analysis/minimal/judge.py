"""Neutral judge of two moves at one decision: the seat's own board only, no talk, no coordination.

For every told decision whose replay without the message chose another move
(replay.jsonl: told and own differ, both moves), each move is played on the
seat's board and the position after it is searched by v8c with
Coordination=false from the opponent's seat, `go nodes 2000000` (4x the match
budget), fresh process, empty hash. The move's value is minus that score (cp
for the seat; mates as +-(100000 - plies)). HypeBeast's go has no searchmoves,
so "play the move, search the reply" stands in for searchmoves.

    nice -n 10 python3 logs/loss-analysis/minimal/judge.py
"""
import json
import os
import sys

sys.dont_write_bytecode = True
ROOT = "/home/anbernal/Projects/HypeBeast-v5"
sys.path.insert(0, ROOT + "/tests")
from hbutil import Engine  # noqa: E402

HERE = ROOT + "/logs/loss-analysis/minimal"
BIN = ROOT + "/bin/hypebeast-v8c"
NET = ROOT + "/nets/bughouse-cd8cceab93fe.nnue"
NODES = 2000000
OPP = {"Awhite": "Ablack", "Ablack": "Awhite", "Bwhite": "Bblack", "Bblack": "Bwhite"}
TEAM = {"Awhite": "white", "Bblack": "white", "Ablack": "black", "Bwhite": "black"}


def score_of(lines):
    for l in reversed(lines):
        f = l.split()
        if l.startswith("info depth") and "score" in f:
            i = f.index("score")
            if f[i + 1] == "cp":
                return int(f[i + 2]), int(f[2])
            if f[i + 1] == "mate":
                m = int(f[i + 2])
                return (100000 - abs(m) * 2) * (1 if m > 0 else -1), int(f[2])
    return None, None


def value(d, move):
    seat = d["seat"]
    opp = OPP[seat]
    board = "1" if seat[0] == "A" else "2"
    e = Engine(BIN, hypebeast=False, net=NET,
               options={"Ponder": "false", "HypeBeast": "true", "Hash": 64, "Coordination": "false"})
    try:
        e.send("ucinewgame")
        e.setoption("Team", TEAM[opp])
        e.setoption("Seat", opp)
        e.sync()
        e.setoption("Clocks", d["opts"]["Clocks"])
        pos = d["pos"] + ("" if " moves " in d["pos"] else " moves") + " " + board + move
        e.send(pos)
        lines = e.go(f"go nodes {NODES}", timeout=900)
    finally:
        e.close()
    s, depth = score_of(lines)
    if s is None:
        # no legal reply: mate or stalemate after our move
        return {"v": None, "depth": 0, "bm": lines[-1]}
    return {"v": -s, "depth": depth}


def main():
    out = HERE + "/judge.jsonl"
    done = set()
    if os.path.exists(out):
        done = {(r["game"], r["seat"], r["n"]) for r in map(json.loads, open(out))}
    ds = {(d["game"], d["seat"], d["n"]): d for d in map(json.loads, open(HERE + "/decisions.jsonl"))}
    rep = {}
    for r in map(json.loads, open(HERE + "/replay.jsonl")):
        rep.setdefault((r["game"], r["seat"], r["n"]), {})[r["mode"]] = r
    with open(out, "a") as f:
        for k, m in rep.items():
            if k in done or "told" not in m or "own" not in m:
                continue
            a, b = m["told"]["sum"]["decision"], m["own"]["sum"]["decision"]
            if a == b or a == "pass" or b == "pass":
                continue
            d = ds[k]
            r = {"game": k[0], "seat": k[1], "n": k[2], "told_move": a, "own_move": b,
                 "told": value(d, a), "own": value(d, b)}
            f.write(json.dumps(r) + "\n")
            f.flush()


if __name__ == "__main__":
    main()
