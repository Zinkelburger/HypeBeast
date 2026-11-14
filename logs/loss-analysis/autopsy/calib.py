#!/usr/bin/env python3
"""Evaluation check: where is the stated winning chance 1/(1+exp(-cp/1000)) wrong?

Rows: every decision of both matches with a non-mate main score (all engines: they share the net and the
evaluation; the candidate alone as a second column). Outcome: the team's result (1, 0.5, 0).
For each feature group: n, mean stated, mean result, bias = result - stated, with a 95% interval from
resampling whole games (2000 resamples). Then a joint linear model of (result - stated) on all the
indicators at once, with the same game resampling, so that each feature's bias is net of the others.
"""
import collections
import math
import random
import sys

from common import MATE, PARTNER, load, MATCHES

random.seed(1)
B = 2000


def wc(cp):
    return 1.0 / (1.0 + math.exp(-cp / 1000.0))


def build_rows():
    data = load()
    out = []
    for m, d in data.items():
        rows = d["rows"]
        by_seat = collections.defaultdict(list)
        for r in rows:
            by_seat[(r["game"], r["seat"])].append(r)
        for k in by_seat:
            by_seat[k].sort(key=lambda r: (r["n"], r["t"]))
        for r in rows:
            if r["score"] is None or abs(r["score"]) >= MATE:
                continue
            f = r["feat"]
            if "krank" not in f:
                continue
            prs = [x for x in by_seat[(r["game"], PARTNER[r["seat"]])] if x["n"] <= r["n"] and x["score"] is not None]
            ps = prs[-1]["score"] if prs else None
            seat_i = ["Awhite", "Ablack", "Bwhite", "Bblack"].index(r["seat"])
            opp_i = seat_i ^ 1
            clk = r["clocks"]
            out.append({"g": (m, r["game"]), "cand": r["engine"] == d["cand"], "stated": wc(r["score"]), "won": r["won"],
                        "score": r["score"], "f": f, "ps": ps, "tadv": r["tadv"],
                        "clkdiff": (clk[seat_i] - clk[opp_i]) / 1000.0 if clk else None,
                        "own_clk": clk[seat_i] / 1000.0 if clk else None, "sitting": r["decision"] == "pass"})
    return out


GROUPS = [
    ("opponent hand 0", lambda x: x["f"]["hand_opp"] == 0),
    ("opponent hand 1-3", lambda x: 1 <= x["f"]["hand_opp"] <= 3),
    ("opponent hand 4-8", lambda x: 4 <= x["f"]["hand_opp"] <= 8),
    ("opponent hand 9+", lambda x: x["f"]["hand_opp"] >= 9),
    ("opponent hand holds a queen", lambda x: x["f"]["opp_q_in_hand"] > 0),
    ("own hand 0", lambda x: x["f"]["hand_own"] == 0),
    ("own hand 1-3", lambda x: 1 <= x["f"]["hand_own"] <= 3),
    ("own hand 4-8", lambda x: 4 <= x["f"]["hand_own"] <= 8),
    ("own hand 9+", lambda x: x["f"]["hand_own"] >= 9),
    ("king on home rank", lambda x: x["f"]["krank"] == 0),
    ("king 1 rank up", lambda x: x["f"]["krank"] == 1),
    ("king 2+ ranks up", lambda x: x["f"]["krank"] >= 2),
    ("shelter 0-1 pawns", lambda x: x["f"]["shelter"] <= 1),
    ("shelter 2-3 pawns", lambda x: x["f"]["shelter"] >= 2),
    ("3+ king-zone squares attacked", lambda x: x["f"]["kzone_att"] >= 3),
    ("partner mated (score <= -90000)", lambda x: x["ps"] is not None and x["ps"] <= -MATE),
    ("partner behind (-90000 < score < -300)", lambda x: x["ps"] is not None and -MATE < x["ps"] < -300),
    ("partner level", lambda x: x["ps"] is not None and -300 <= x["ps"] <= 300),
    ("partner ahead (300 < score < 90000)", lambda x: x["ps"] is not None and 300 < x["ps"] < MATE),
    ("partner mating (score >= 90000)", lambda x: x["ps"] is not None and x["ps"] >= MATE),
    ("team has time advantage", lambda x: x["tadv"] is True),
    ("team has no time advantage", lambda x: x["tadv"] is False),
    ("own clock 10+ s behind opponent", lambda x: x["clkdiff"] is not None and x["clkdiff"] <= -10),
    ("own clock within 10 s", lambda x: x["clkdiff"] is not None and -10 < x["clkdiff"] < 10),
    ("own clock 10+ s ahead", lambda x: x["clkdiff"] is not None and x["clkdiff"] >= 10),
    ("own clock under 15 s", lambda x: x["own_clk"] is not None and x["own_clk"] < 15),
    ("sitting (decision = pass)", lambda x: x["sitting"]),
]


def boot_bias(rows, pred):
    per = collections.defaultdict(lambda: [0, 0.0, 0.0])
    for x in rows:
        if pred(x):
            p = per[x["g"]]
            p[0] += 1
            p[1] += x["stated"]
            p[2] += x["won"]
    games = sorted({x["g"] for x in rows})
    n = sum(p[0] for p in per.values())
    if n == 0:
        return None
    st = sum(p[1] for p in per.values()) / n
    wo = sum(p[2] for p in per.values()) / n
    bs = []
    for _ in range(B):
        nn = s = w = 0
        for g in random.choices(games, k=len(games)):
            p = per.get(g)
            if p:
                nn += p[0]
                s += p[1]
                w += p[2]
        if nn:
            bs.append((w - s) / nn)
    bs.sort()
    return n, len(per), st, wo, wo - st, bs[int(0.025 * len(bs))], bs[int(0.975 * len(bs)) - 1]


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            return None
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


JOINT = [
    ("intercept", lambda x: 1),
    ("opponent hand >= 4", lambda x: x["f"]["hand_opp"] >= 4),
    ("opponent hand >= 9", lambda x: x["f"]["hand_opp"] >= 9),
    ("own hand >= 4", lambda x: x["f"]["hand_own"] >= 4),
    ("king off home rank", lambda x: x["f"]["krank"] >= 1),
    ("shelter 0-1 pawns", lambda x: x["f"]["shelter"] <= 1),
    ("partner mated", lambda x: x["ps"] is not None and x["ps"] <= -MATE),
    ("partner behind (< -300, not mated)", lambda x: x["ps"] is not None and -MATE < x["ps"] < -300),
    ("partner ahead (> 300, not mating)", lambda x: x["ps"] is not None and 300 < x["ps"] < MATE),
    ("partner mating", lambda x: x["ps"] is not None and x["ps"] >= MATE),
    ("own clock 10+ s behind opponent", lambda x: x["clkdiff"] is not None and x["clkdiff"] <= -10),
    ("own clock 10+ s ahead", lambda x: x["clkdiff"] is not None and x["clkdiff"] >= 10),
    ("stated chance above 0.5", lambda x: x["stated"] > 0.5),
]


def joint(rows):
    k = len(JOINT)
    per = {}
    for x in rows:
        v = [1.0 if fn(x) else 0.0 for _, fn in JOINT]
        y = x["won"] - x["stated"]
        A, bb = per.setdefault(x["g"], ([[0.0] * k for _ in range(k)], [0.0] * k))
        for i in range(k):
            if v[i]:
                bb[i] += v[i] * y
                for j in range(k):
                    A[i][j] += v[i] * v[j]
    games = sorted(per)

    def fit(sample):
        A = [[0.0] * k for _ in range(k)]
        bb = [0.0] * k
        for g in sample:
            a, b2 = per[g]
            for i in range(k):
                bb[i] += b2[i]
                for j in range(k):
                    A[i][j] += a[i][j]
        return solve(A, bb)
    est = fit(games)
    bs = [fit(random.choices(games, k=len(games))) for _ in range(B // 4)]
    bs = [b for b in bs if b]
    ci = []
    for i in range(k):
        v = sorted(b[i] for b in bs)
        ci.append((v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]))
    return est, ci


def bins_table(rows, pred, label):
    lines = []
    for lo, hi in ((0, .25), (.25, .4), (.4, .6), (.6, .75), (.75, 1.01)):
        sel = [x for x in rows if pred(x) and lo <= x["stated"] < hi]
        if sel:
            lines.append(f"{lo:.2f}-{min(hi, 1):.2f}: n={len(sel)} stated {sum(x['stated'] for x in sel) / len(sel):.3f} won {sum(x['won'] for x in sel) / len(sel):.3f}")
    print(f"  {label}: " + " | ".join(lines))


def main():
    rows = build_rows()
    print(f"{len(rows)} decisions with a non-mate score, {len({x['g'] for x in rows})} games; candidate seats {sum(x['cand'] for x in rows)}")
    for subset, sel in (("all engines", rows), ("candidate only", [x for x in rows if x["cand"]])):
        print(f"\n## Marginal bias (result - stated), {subset}; 95% interval by game resampling")
        print("| feature | decisions | games | mean stated | won | bias | 95% interval |")
        print("|---|---|---|---|---|---|---|")
        r = boot_bias(sel, lambda x: True)
        print(f"| all | {r[0]} | {r[1]} | {r[2]:.3f} | {r[3]:.3f} | {r[4]:+.3f} | {r[5]:+.3f} to {r[6]:+.3f} |")
        for name, fn in GROUPS:
            r = boot_bias(sel, fn)
            if r:
                print(f"| {name} | {r[0]} | {r[1]} | {r[2]:.3f} | {r[3]:.3f} | {r[4]:+.3f} | {r[5]:+.3f} to {r[6]:+.3f} |")
    print("\n## Joint linear model of (result - stated) on indicators, all engines; 95% interval by game resampling (500)")
    est, ci = joint(rows)
    print("| term | coefficient | 95% interval |")
    print("|---|---|---|")
    for (name, _), e, c in zip(JOINT, est, ci):
        print(f"| {name} | {e:+.3f} | {c[0]:+.3f} to {c[1]:+.3f} |")
    print("\n## Calibration by stated band for selected groups (all engines)")
    for name, fn in GROUPS:
        if name in ("opponent hand 9+", "opponent hand 0", "king 2+ ranks up", "king on home rank", "partner behind (-90000 < score < -300)",
                    "partner ahead (300 < score < 90000)", "own clock 10+ s behind opponent", "own clock 10+ s ahead", "shelter 0-1 pawns"):
            bins_table(rows, fn, name)


if __name__ == "__main__":
    main()
