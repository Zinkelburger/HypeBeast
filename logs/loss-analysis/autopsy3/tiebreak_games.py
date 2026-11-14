#!/usr/bin/env python3
"""Cap matches (v8k HBTellRootMaxCost): a contender game with no feed_switch plays as hb-l50 would, so a pair
with none in either game splits 1-1. Split the games by whether the contender switched for the feed; score,
pairs, sudden mates in each part. Logs only.   nice -n 19 python3 tiebreak_games.py MATCH [MATCH ...]"""
import collections, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import common3 as c3  # noqa: E402
for m in sys.argv[1:]:
    d = c3.load(m)
    name = {g["game"]: g["names"]["contender"] for g in d["games"]}
    fs = collections.Counter(); dec = collections.Counter()
    for r in d["rows"]:
        if r["engine"] == name[r["game"]]:
            dec[r["game"]] += 1
            if r["reason"] == "feed_switch":
                fs[r["game"]] += 1
    sc = {}
    pairs = collections.defaultdict(list)
    for g in d["games"]:
        s = 1.0 if g["winner"] == g["contender_team"] else 0.0 if g["winner"] in ("white", "black") else 0.5
        sc[g["game"]] = s; pairs[g["pair"]].append(g["game"])
    w = [g for g in sc if fs[g]]; wo = [g for g in sc if not fs[g]]
    print(f"## {m}: feed_switch decisions {sum(fs.values())} of {sum(dec.values())} ({100*sum(fs.values())/sum(dec.values()):.1f}%)")
    print(f"games with a feed switch: {len(w)}, contender scored {sum(sc[g] for g in w):g} ({100*sum(sc[g] for g in w)/max(1,len(w)):.1f}%); "
          f"switches per such game: median {sorted(fs[g] for g in w)[len(w)//2] if w else 0}")
    print(f"games without: {len(wo)}, contender scored {sum(sc[g] for g in wo):g} ({100*sum(sc[g] for g in wo)/max(1,len(wo)):.1f}%)")
    pc = collections.Counter()
    for p, gs in pairs.items():
        t = sum(sc[g] for g in gs); any_fs = any(fs[g] for g in gs)
        pc[(any_fs, "won" if t > 1 else "lost" if t < 1 else "split")] += 1
    for a in (True, False):
        print(f"pairs {'with' if a else 'without'} a feed switch: won {pc[(a,'won')]}, split {pc[(a,'split')]}, lost {pc[(a,'lost')]}")
    print()
