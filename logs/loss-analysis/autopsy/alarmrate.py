#!/usr/bin/env python3
"""How often would an alarm '-T=#' fire (a scored world mates the move chosen, nothing arriving does not), in all
candidate decisions of both matches, and what followed: did a T reach the opponent before the seat's next move
(q<=2), and was the seat then mated at its next decision?"""
import collections, re
from common import load, MATE
data = load()
for m, d in data.items():
    fired = arrived = mated = 0
    games = set(); won_games = set()
    types = collections.Counter()
    tot = 0
    for r in d["rows"]:
        if r["engine"] != d["cand"] or not r["worlds"] or r["decision"] == "pass":
            continue
        tot += 1
        none = next((w for w in r["worlds"] if w["arrival"] == "none"), None)
        if not none or none["v_chosen"] is None or none["v_chosen"] <= -MATE:
            continue
        ts = set()
        for w in r["worlds"]:
            if w["arrival"] != "none" and w["v_chosen"] is not None and w["v_chosen"] <= -MATE:
                ts |= {"-" + t for t in re.findall(r"-([PNBRQ])", w["arrival"])}
        if not ts:
            continue
        fired += 1; games.add(r["game"])
        if r["won"] == 1: won_games.add(r["game"])
        for t in ts: types[t] += 1
        got = {f[1] for f in r["future"] if f[0] <= 2}
        if got & ts:
            arrived += 1
            if r["next_score"] is not None and r["next_score"] <= -MATE:
                mated += 1
    print(f"{m}: candidate decisions with worlds {tot}; alarm would fire {fired} ({100*fired/tot:.1f}%) in {len(games)} games "
          f"({len(won_games)} of them won); types {dict(types)}; the piece reached the opponent by q<=2 in {arrived}; then mated at the next decision {mated}")
