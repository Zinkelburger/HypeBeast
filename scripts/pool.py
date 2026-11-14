#!/usr/bin/env python3
"""Is the contender really better? One match, or several matches of the same pair of engines pooled.

    scripts/pool.py logs/plan-vs-l50 logs/plan-vs-l50-b ...

Counts by opening pair (the two games of one opening, teams swapped), because the two
games of a pair are not independent. Prints the score with its 95% interval, the
chance that two equal engines would be this far apart (p), and how many more pairs
a result of this size would need to be believed. With a post-mortem present it also
compares sudden mates: decisions at -300 cp or better whose next decision is a forced
mate against the seat. That count moves with far fewer games than the score does.
"""
import json, math, os, sys, collections
from math import comb


def binom_two_sided(a, b):
    """Chance of a split at least as uneven as a against b from a fair coin."""
    n, k = a + b, max(a, b)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n) if n else 1.0


def main(dirs):
    pair_scores, games = [], collections.Counter()
    collapses, decisions, seen_pm = collections.Counter(), collections.Counter(), 0
    print("match | games | contender | score | pairs won-split-lost")
    for d in dirs:
        d = d.rstrip("/")
        rs = [json.loads(l) for l in open(f"{d}/results.jsonl")]
        by = collections.defaultdict(list)
        for r in rs:
            by[r["pair"]].append(r["contender_score"])
        full = [sum(v) for v in by.values() if len(v) == 2]
        pair_scores += full
        w = sum(r["contender_score"] == 1 for r in rs); l = sum(r["contender_score"] == 0 for r in rs)
        games.update(w=w, l=l, d=len(rs) - w - l)
        print(f"{os.path.basename(d)} | {len(rs)} | {rs[0]['contender']} against {rs[0]['baseline']} | {w}-{l}-{len(rs) - w - l} | "
              f"{sum(s > 1 for s in full)}-{sum(s == 1 for s in full)}-{sum(s < 1 for s in full)}")
        pm = f"{d}/postmortem.jsonl"
        if os.path.exists(pm):
            seen_pm += 1
            role = {rs[0]["contender"]: "contender", rs[0]["baseline"]: "baseline"}
            for l_ in open(pm):
                r = json.loads(l_)
                who = role.get(r["engine"])
                if not who or r["score"] is None:
                    continue
                decisions[who] += 1
                if -300 <= r["score"] < 90000 and r["next_score"] is not None and r["next_score"] <= -90000:
                    collapses[who] += 1
    n = len(pair_scores)
    if not n:
        print("no finished pair"); return
    mean = sum(pair_scores) / (2 * n)
    var = sum((s / 2 - mean) ** 2 for s in pair_scores) / max(1, n - 1)
    se = math.sqrt(var / n)
    z = (mean - 0.5) / se if se else 0.0
    p = math.erfc(abs(z) / math.sqrt(2))
    won, lost = sum(s > 1 for s in pair_scores), sum(s < 1 for s in pair_scores)
    print(f"\npooled: {games['w']}-{games['l']}-{games['d']} in {2 * n} games of finished pairs ({n} pairs)")
    print(f"score {100 * mean:.1f}%, 95% interval {100 * (mean - 1.96 * se):.1f}% to {100 * (mean + 1.96 * se):.1f}%")
    print(f"chance of a gap this large between equal engines: p = {p:.3f} (pairs won {won}, lost {lost}: sign test p = {binom_two_sided(won, lost):.3f})")
    if p < 0.05:
        print("verdict: different from level at the usual 5% line")
    else:
        need = math.ceil(var * (1.96 / (mean - 0.5)) ** 2) if abs(mean - 0.5) > 1e-9 else None
        more = f"; if the true score is the {100 * mean:.1f}% seen, about {max(0, need - n)} more pairs ({2 * max(0, need - n)} games) would show it" if need else ""
        print(f"verdict: not yet different from level{more}")
    if seen_pm:
        a, b = collapses["contender"], collapses["baseline"]
        print(f"\nsudden mates (from -300 or better to a forced mate against, one decision later): contender {a}, baseline {b}"
              f" (decisions {decisions['contender']}, {decisions['baseline']}); p = {binom_two_sided(a, b):.3f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
