#!/usr/bin/env python3
"""Checks on the missed-supplies records: examples, the lost games, and whether an arrival was followed by our mate."""
import collections
import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/scripts")
import chess  # noqa: E402
import chess.variant  # noqa: E402
import postmortem as pm  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

for d in sys.argv[1:]:
    tag = d.rstrip("/").split("/")[-1]
    games = pm.load_games(d)
    gm = {g["game"]: g for g in games}
    rows = [json.loads(l) for l in open(f"{HERE}/{tag}.postmortem.before.jsonl")]
    recs = pm.missed_supplies(games, rows)
    seat_rows = collections.defaultdict(list)
    for r in rows:
        seat_rows[(r["game"], r["seat"])].append(r)
    print(f"# {tag}")
    # lost games per engine, by group (distinct games)
    for e in sorted({x["row"]["engine"] for x in recs}):
        xs = [x for x in recs if x["row"]["engine"] == e]
        def lost(sel):
            return sorted({x["row"]["game"] for x in sel if x["won"] == 0})
        ep = collections.defaultdict(list)
        for x in xs:
            ep[x["episode"]].append(x)
        cdn = [x for v in ep.values() if any(y["could"] for y in v) and not any(y["could"] and y["did"] for y in v) for x in v]
        print(f"{e}: games with an episode {len({x['row']['game'] for x in xs})}, lost {lost(xs)}; "
              f"lost with could-but-did-not episodes {lost(cdn)}; drawn {sorted({x['row']['game'] for x in xs if x['won'] == 0.5})}")
    # arrival then our mate on our board?
    arr = [x for x in recs if x["arrived"]]
    ended = collections.Counter()
    for x in arr:
        r, g = x["row"], gm[x["row"]["game"]]
        ours = "1" if r["seat"][0] == "A" else "2"
        last = g["toks"][-1][0]
        ours_after = sum(1 for t in g["toks"][r["n"]:] if t[0] == ours)
        k = (g["termination"], "our board" if last == ours else "other board",
             "our team won" if x["won"] == 1 else "lost" if x["won"] == 0 else "draw", "<=4 plies of ours left" if ours_after <= 4 else ">4 left")
        ended[k] += 1
    for k, v in ended.most_common():
        print("  arrived:", k, v)
    # examples: could but did not, with partner's capture set and move, partner's score
    for x in [x for x in recs if x["could"] and not x["did"]][:40]:
        r, g = x["row"], gm[x["row"]["game"]]
        j = x["js"][0]
        ps = pm.PARTNER[r["seat"]]
        pr = [p for p in seat_rows[(r["game"], ps)] if p["n"] <= j]
        pr = pr[-1] if pr else None
        b = {"1": chess.variant.CrazyhouseBoard(), "2": chess.variant.CrazyhouseBoard()}
        for t in g["toks"][:j]:
            board = b[t[0]]
            mover = board.turn
            before = {p: board.pockets[mover].count(p) for p in pm.NAMES}
            board.push(chess.Move.from_uci(t[1:]))
            for p in pm.NAMES:
                if board.pockets[mover].count(p) > before[p]:
                    board.pockets[mover].remove(p)
                    b["2" if t[0] == "1" else "1"].pockets[not mover].add(p)
        pb = b[g["toks"][j][0]]
        capm = [pb.san(m) for m in pb.legal_moves if pm.captured_type(pb, m) == x["T"]]
        print(f"  g{r['game']} {r['seat']} n={r['n']} {r['engine']} T={x['T']} score={r['score']} won={r['won']} | partner {ps} "
              f"tok {j} played {pb.san(chess.Move.from_uci(g['toks'][j][1:]))}, could {capm}; partner decision n={pr and pr['n']} "
              f"score={pr and pr['score']} played={pr and pr['decision']} | next partner toks {[g['toks'][i] for i in x['js'][1:]]}")
    print()
