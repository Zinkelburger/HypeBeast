#!/usr/bin/env python3
"""Clock state in the lost games: the mated seat's clock at the end, its sits after seeing mate, time advantage at
its decision before the fall, and who was ahead on the clock on the mated board at that decision."""
import collections, json, os, statistics
from common import HERE
T = json.load(open(os.path.join(HERE, "timeline.json")))
idx = {"Awhite": 0, "Ablack": 1, "Bwhite": 2, "Bblack": 3}
low = sum(1 for t in T if t["clocks_end"][idx[t["S"]]] <= 500)
print(f"lost games {len(T)}; mated seat's clock <= 500 ms at the end: {low}")
hm = sum(1 for t in T if t[t["S"]]["pass_reasons"].get("hold_mated"))
print(f"mated seat sat with reason hold_mated at least once: {hm}")
tadv = collections.Counter(); diffs = []
for t in T:
    pre = t[t["S"]].get("pre")
    if pre and pre.get("clocks"):
        tadv[pre["tadv"]] += 1
        i = idx[t["S"]]
        diffs.append((pre["clocks"][i] - pre["clocks"][i ^ 1]) / 1000)
print("team time advantage at the mated seat's decision before its fall:", dict(tadv))
print(f"own minus opponent clock on that board at that decision: median {statistics.median(diffs):+.1f} s, "
      f"min {min(diffs):+.1f}, max {max(diffs):+.1f}, |diff| > 5 s in {sum(1 for d in diffs if abs(d) > 5)} of {len(diffs)}")
print("own clock at that decision: median", statistics.median(t[t["S"]]["pre"]["clocks"][idx[t["S"]]] / 1000 for t in T if t[t["S"]].get("pre") and t[t["S"]]["pre"].get("clocks")), "s")
