#!/usr/bin/env python3
"""Search with an imaginary extra piece in the attacker's hand.

usage: phantom.py HAZARD_JSON OUT_JSON MATCH_DIR [MATCH_DIR ...]
Positions are those a seat just left, the seat having rated them -200 or better.
Positive: the seat's last decision before it saw forced mate in a lost game, and
the decision two before that. Negative: decisions of seats in won games that never
saw mate. Two engine processes, one thread each, nice 19.
"""
import collections
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")
import chess  # noqa: E402
from hbutil import ROOT, Bughouse, Engine  # noqa: E402

BIN = ROOT / "bin/hypebeast-v6h"
NODES = 100_000
TYPES = {"P": chess.PAWN, "N": chess.KNIGHT, "B": chess.BISHOP, "R": chess.ROOK, "Q": chess.QUEEN}
E = None
RESULTS = {}


def load(dirs):
    out = {}
    for d in dirs:
        tag = d.rstrip("/").split("/")[-1]
        for l in open(f"{d}/results.jsonl"):
            r = json.loads(l)
            out[f"{tag}:{r['game']}"] = r["result"]
    return out


def init(dirs):
    global E, RESULTS
    RESULTS = load(dirs)
    E = Engine(BIN, options={"Coordination": "false", "HBFeedPrices": "false", "Hash": 64, "Threads": 1})


def mate_for_attacker(g, seat, team):
    E.setoption("Seat", seat)
    E.setoption("Team", team)
    E.send("ucinewgame")
    E.sync()
    E.send(f"position fen {g.dual_fen()}")
    lines = E.go(f"go nodes {NODES}", timeout=300)
    sc = [l for l in lines if l.startswith("info depth") and " score " in l]
    last = sc[-1] if sc else ""
    if " score mate " in last:
        v = int(last.split(" score mate ")[1].split()[0])
        return v if v > 0 else None
    return None


def job(item):
    res = RESULTS[item["game"]]
    ev, tokens = res["events"], res["moves"]
    moves = [e for e in ev if e["kind"] == "move"]
    offset = len(tokens) - len(moves)
    n = next(i for i, e in enumerate(moves) if e["t"] == item["t"] and e["seat"] == item["seat"] and e["uci"] == item["uci"])
    prefix = tokens[:offset + n + 1]
    seat = item["seat"]
    board = 0 if seat[0] == "A" else 1
    white = seat.endswith("white")
    att_seat = f"{seat[0]}{'black' if white else 'white'}"
    att_color = not white
    att_team = "white" if att_seat in ("Awhite", "Bblack") else "black"

    def build(extra):
        g = Bughouse()
        for t in prefix:
            g.push(int(t[0]) - 1, t[1:])
        if extra:
            g.boards[board].pockets[att_color].add(TYPES[extra])
        return g

    out = dict(item)
    out["none"] = mate_for_attacker(build(None), att_seat, att_team)
    out["with"] = {p: mate_for_attacker(build(p), att_seat, att_team) for p in TYPES}
    return out


def main():
    rows = json.load(open(sys.argv[1]))
    out_path, dirs = sys.argv[2], sys.argv[3:]
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["game"], r["seat"])].append(r)
    cp = lambda r: (30000 if r["eval"]["mate"] > 0 else -30000) if "mate" in r["eval"] else r["eval"]["cp"]  # noqa: E731
    items = []
    for key, rs in by.items():
        if rs[0]["won"] or rs[0]["seen"] is None:
            continue
        for label, k in (("last", 1), ("two_before", 3)):
            if len(rs) >= k and cp(rs[-k]) >= -200:
                r = rs[-k]
                items.append({"label": label, "game": r["game"], "seat": r["seat"], "t": r["t"], "uci": r["uci"],
                              "engine": r["engine"], "cp": cp(r), "seen": r["seen"]})
    neg = [r for rs in by.values() if rs[0]["won"] and rs[0]["seen"] is None for r in rs
           if r["t"] >= 40_000 and cp(r) >= -200]
    random.seed(20261110)
    for r in random.sample(neg, 200):
        items.append({"label": "safe", "game": r["game"], "seat": r["seat"], "t": r["t"], "uci": r["uci"],
                      "engine": r["engine"], "cp": cp(r), "seen": None})
    print(collections.Counter(i["label"] for i in items), flush=True)
    with ProcessPoolExecutor(2, initializer=init, initargs=(dirs,)) as pool:
        done = list(pool.map(job, items, chunksize=4))
    json.dump(done, open(out_path, "w"), indent=1)
    for label in ("last", "two_before", "safe"):
        sub = [d for d in done if d["label"] == label]
        n = len(sub)
        real = sum(d["none"] is not None for d in sub)
        print(f"\n{label}: {n} positions; forced mate with the real hand: {real} ({100 * real / n:.0f}%)")
        clean = [d for d in sub if d["none"] is None]
        anyp = sum(any(v is not None for v in d["with"].values()) for d in clean)
        print(f"  of the {len(clean)} with no real mate, some extra piece mates: {anyp} ({100 * anyp / max(1, len(clean)):.0f}%)")
        for p in TYPES:
            k = sum(d["with"][p] is not None for d in clean)
            print(f"    extra {p}: {k} ({100 * k / max(1, len(clean)):.0f}%)")
        two = sum(sum(v is not None for v in d["with"].values()) >= 3 for d in clean)
        print(f"  3 or more piece types mate: {two} ({100 * two / max(1, len(clean)):.0f}%)")
    print("DONE")


if __name__ == "__main__":
    main()
