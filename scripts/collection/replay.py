#!/usr/bin/env python3
"""Replay the engine processes of the picked games (build_game.py's first step).

    python3 scripts/collection/replay.py [--check] [ID ...]

Each engine process of a game is replayed in a fresh process with every
command the arena sent it, so every go starts from the same search history
(a fresh process per decision reproduces only a process's first decision:
the main thread's move-ordering history carries over between searches).
Replays are cached in logs/collection/cache/. --check also replays the
v1.1.1 seats with bin/hypebeast-v7 (the binary that played) and compares
every printed line with the reports build's, masking time, nps, hashfull,
the report lines themselves and the lines Stockfish prints only after 3 s of
wall time (currmove, and fail-high/low bound lines). Prints how many decisions reproduced the
logged move, score, depth and node count.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("hb_collection_common", HERE / "common.py")
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)
import re  # noqa: E402


def mask(lines):
    out = []
    for l in lines:
        if "NNUE evaluation" in l or l.startswith("info string hb_fed") or l.startswith("info string hb_values"):
            continue
        # printed only after 3 s of wall time (Stockfish's UCI::pv / currmove rule): timing, not search
        if " currmove " in l or " lowerbound " in l or " upperbound " in l:
            continue
        l = re.sub(r" (time|nps|hashfull) \d+", "", l)
        l = re.sub(r"(elapsed_ms|child_ms|clear_ms)=\d+", "", l)
        out.append(l)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv
    sel = json.loads((c.OUT / "selection.json").read_text())
    ids = args or sel["picked"]
    games = {x["id"]: x for x in sel["games"]}
    loaded = {}
    total = same = 0
    for gid in ids:
        x = games[gid]
        m = loaded.get(x["match"]) or loaded.setdefault(x["match"], c.load_match(x["match"]))
        rep = c.replay_sessions(m, x["game"])
        n = ok = 0
        for d in m["decisions"][x["game"]]:
            r = rep[d["seat"]]["gos"][d["k"]]
            n += 1
            ok += c.same_decision(d["out"], r)
        total += n
        same += ok
        line = f"{gid}: {ok}/{n} decisions reproduced, " + ", ".join(
            f"{s} {v['seconds']:.0f}s" for s, v in rep.items())
        if check:
            for seat in c.SEATS:
                role = next(d["role"] for d in m["decisions"][x["game"]] if d["seat"] == seat)
                if c.MATCHES[x["match"]]["binaries"][role] != c.BIN_V111:
                    continue
                a = c.SessionReplay(c.BIN_V111, m["sessions"][(x["game"], seat)]).run()
                b = c.SessionReplay(c.BIN_REPORTS, m["sessions"][(x["game"], seat)]).run()
                eq = sum(mask(p) == mask(q) for p, q in zip(a["gos"], b["gos"]))
                line += f" | {seat} v7 vs reports: {eq}/{len(a['gos'])} gos print the same"
        print(line, flush=True)
    print(f"total: {same}/{total} decisions reproduced")


if __name__ == "__main__":
    main()
