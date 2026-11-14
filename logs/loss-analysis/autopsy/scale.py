#!/usr/bin/env python3
"""Which logistic scale fits, and how much does the partner's score add?

Model 1: P(team wins) = 1/(1+exp(-cp/k)), k on a grid (the engine uses k = 1000).
Model 2: P = 1/(1+exp(-(cp/k1 + pcp/k2))), pcp = the partner's latest score (clipped at +-3000), on rows where
that score exists and is not a mate (own mates are excluded too, so the two terms are treated alike).
Log loss per decision on rows with non-mate scores (cp clipped at +-3000). Intervals for the best k: the grid
value minimising the loss in each of 1000 resamples of whole games.
"""
import collections
import math
import random

from calib import build_rows

random.seed(2)


def ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def main():
    rows = build_rows()
    for subset, sel in (("all engines", rows), ("candidate only", [x for x in rows if x["cand"]])):
        ks = [400, 600, 800, 1000, 1200, 1500, 1800, 2200, 2700, 3300, 4000, 5000]
        per = collections.defaultdict(lambda: [0.0] * len(ks))
        cnt = collections.Counter()
        for x in sel:
            cp = max(-3000, min(3000, x["score"]))
            cnt[x["g"]] += 1
            for i, k in enumerate(ks):
                per[x["g"]][i] += ll(1 / (1 + math.exp(-cp / k)), x["won"])
        games = sorted(per)
        N = sum(cnt.values())
        tot = [sum(per[g][i] for g in games) / N for i in range(len(ks))]
        best = min(range(len(ks)), key=lambda i: tot[i])
        bk = collections.Counter()
        for _ in range(1000):
            s = random.choices(games, k=len(games))
            t = [sum(per[g][i] for g in s) for i in range(len(ks))]
            bk[ks[min(range(len(ks)), key=lambda i: t[i])]] += 1
        print(f"## {subset}: {N} decisions")
        print("  own score only, log loss by k: " + ", ".join(f"{k}: {v:.4f}" for k, v in zip(ks, tot)))
        print(f"  best k {ks[best]}; best k across 1000 game resamples: {dict(sorted(bk.items()))}")
        # model 2
        k1s = [800, 1000, 1500, 2000, 3000, 5000, 10 ** 9]
        k2s = [500, 800, 1000, 1500, 2000, 3000, 10 ** 9]
        per2 = collections.defaultdict(lambda: [[0.0] * len(k2s) for _ in k1s])
        both = [x for x in sel if x["ps"] is not None and abs(x["ps"]) < 90000]
        N2 = len(both)
        for x in both:
            cp = max(-3000, min(3000, x["score"]))
            pcp = max(-3000, min(3000, x["ps"]))
            for i, k1 in enumerate(k1s):
                for j, k2 in enumerate(k2s):
                    per2[x["g"]][i][j] += ll(1 / (1 + math.exp(-(cp / k1 + pcp / k2))), x["won"])
        games2 = sorted(per2)
        tot2 = [[sum(per2[g][i][j] for g in games2) / N2 for j in range(len(k2s))] for i in range(len(k1s))]
        bi, bj = min(((i, j) for i in range(len(k1s)) for j in range(len(k2s))), key=lambda ij: tot2[ij[0]][ij[1]])
        name = lambda k: "inf" if k >= 10 ** 9 else str(k)
        print(f"  rows where the partner's latest score is known and not a mate: {N2}")
        print(f"  own + partner: best k1 {name(k1s[bi])}, k2 {name(k2s[bj])}, log loss {tot2[bi][bj]:.4f} "
              f"(own only at k=1000 on these rows: {tot2[k1s.index(1000)][len(k2s) - 1]:.4f}; own only best: {min(tot2[i][len(k2s) - 1] for i in range(len(k1s))):.4f}; partner only best: "
              f"{min(tot2[len(k1s) - 1]):.4f}; constant 0.5: {math.log(2):.4f})")
        bb = collections.Counter()
        for _ in range(300):
            s = random.choices(games2, k=len(games2))
            t = {(i, j): sum(per2[g][i][j] for g in s) for i in range(len(k1s)) for j in range(len(k2s))}
            i, j = min(t, key=t.get)
            bb[(name(k1s[i]), name(k2s[j]))] += 1
        print(f"  best (k1, k2) across 300 game resamples: {dict(bb.most_common(6))}")


if __name__ == "__main__":
    main()
