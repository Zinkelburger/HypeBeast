#!/usr/bin/env python3
"""Question 2: where was the evaluation wrong, and what do those positions have in common?

    nice -n 19 python3 calib2.py [--more]       (--more adds the hb-l50 / hb-late50 decisions of other matches)

Rows: decisions with a non-mate main score (sits included: their score is the main search's).
  stated    1/(1+exp(-score/1000)), the engine's HBWinScale
  won       the team's result
  ps        the partner's most recent score (its last decision at or before this one)
  col3      within the seat's next 3 decisions, a forced mate against it, or a score at least 600 cp lower
            that is also below -300 ("collapse")
Two targets, each checked against every feature:
  A. result:  bias = won - stated, by feature bin, 95% interval from 2000 resamples of GAMES
  B. collapse: P(col3) by feature, inside score bands (score -300..+300, +300..+1000, > +1000), and a linear
     probability model of col3 on score-band dummies + all features (net of the score), resampled by game.
Plus a joint linear model of (won - stated) on the features with the partner's score bands (as AUTOPSY.md).
And the "most wrong" decisions of the losing team in lost games.
"""
import collections
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from common2 import MATE, PARTNER, SEATS, by_seat, fm, load  # noqa: E402

random.seed(3)
B = 2000
MORE = "--more" in sys.argv
SETS = [("plan-vs-l50", None)]
if MORE:
    SETS += [("alarm-vs-l50", {"hb-l50"}), ("worlds5-vs-l50", {"hb-l50"}), ("late50-vs-np-b", {"hb-late50"})]


def wc(cp):
    return 1.0 / (1.0 + math.exp(-cp / 1000.0))


def build_rows():
    out = []
    for m, keep in SETS:
        data = load(m)
        rbs = by_seat(data["rows"])
        for (gid, seat), rs in rbs.items():
            prs = rbs.get((gid, PARTNER[seat]), [])
            for i, r in enumerate(rs):
                if keep and r["engine"] not in keep:
                    continue
                if r["score"] is None or abs(r["score"]) >= MATE or "krank" not in r["feat"]:
                    continue
                pp = [x for x in prs if x["n"] <= r["n"] and x["score"] is not None]
                ps = pp[-1]["score"] if pp else None
                nxt = [x["score"] for x in rs[i + 1:i + 4] if x["score"] is not None]
                mated3 = any(s <= -MATE for s in nxt)
                low = min([max(s, -100000) for s in nxt], default=None)
                col3 = mated3 or (low is not None and low <= r["score"] - 600 and low < -300)
                si = SEATS.index(seat)
                clk = r.get("clocks")
                f = dict(r["feat"])
                out.append({"g": (m, gid), "match": m, "engine": r["engine"], "seat": seat, "n": r["n"], "score": r["score"],
                            "stated": wc(r["score"]), "won": r["won"], "ps": ps, "col3": col3, "mated3": mated3, "low3": low,
                            "has_next": bool(nxt), "f": f, "drop_move": "@" in (r["decision"] or ""),
                            "sit": r["decision"] == "pass", "talk": r.get("talk"),
                            "own_clk": clk[si] / 1000 if clk else None,
                            "clkdiff": (clk[si] - clk[si ^ 1]) / 1000 if clk else None, "tadv": r.get("tadv")})
    return out


FEATS = [
    ("king off its home rank", lambda x: x["f"]["krank"] >= 1),
    ("king 2+ ranks up", lambda x: x["f"]["krank"] >= 2),
    ("king on d/e file", lambda x: x["f"].get("kfile") in (3, 4)),
    ("0-1 shelter pawns", lambda x: x["f"]["shelter"] <= 1),
    ("3+ king-zone squares attacked", lambda x: x["f"]["kzone_att"] >= 3),
    ("in check", lambda x: x["f"].get("in_check")),
    ("opponent hand 0", lambda x: x["f"]["hand_opp"] == 0),
    ("opponent hand 4+ points", lambda x: x["f"]["hand_opp"] >= 4),
    ("opponent hand 9+ points", lambda x: x["f"]["hand_opp"] >= 9),
    ("opponent holds a queen", lambda x: x["f"]["opp_q"] > 0),
    ("opponent holds a knight", lambda x: x["f"]["opp_n"] > 0),
    ("opponent has a drop check", lambda x: x["f"]["opp_drop_checks"] >= 1),
    ("opponent has 3+ safe drop checks", lambda x: x["f"]["opp_safe_drop_checks"] >= 3),
    ("a queen would have 3+ safe drop checks", lambda x: x["f"]["q_safe_drop_checks"] >= 3),
    ("own hand 4+ points", lambda x: x["f"]["hand_own"] >= 4),
    ("own hand 4+ and the move is not a drop", lambda x: x["f"]["hand_own"] >= 4 and not x["drop_move"] and not x["sit"]),
    ("own hand 9+ points", lambda x: x["f"]["hand_own"] >= 9),
    ("we have a drop check", lambda x: x["f"]["own_drop_checks"] >= 1),
    ("board material 50+ (both sides)", lambda x: x["f"]["mat_own"] + x["f"]["mat_opp"] >= 50),
    ("board material under 30", lambda x: x["f"]["mat_own"] + x["f"]["mat_opp"] < 30),
    ("board material own - opp <= -3", lambda x: x["f"]["mat_own"] - x["f"]["mat_opp"] <= -3),
    ("board material own - opp >= +3", lambda x: x["f"]["mat_own"] - x["f"]["mat_opp"] >= 3),
    ("partner to move on the other board", lambda x: x["f"]["other_partner_to_move"]),
    ("own clock under 20 s", lambda x: x["own_clk"] is not None and x["own_clk"] < 20),
    ("own clock 5+ s behind its opponent", lambda x: x["clkdiff"] is not None and x["clkdiff"] <= -5),
    ("own clock 5+ s ahead of its opponent", lambda x: x["clkdiff"] is not None and x["clkdiff"] >= 5),
    ("team has the time advantage", lambda x: x["tadv"] is True),
    ("partner behind (< -300, not mated)", lambda x: x["ps"] is not None and -MATE < x["ps"] < -300),
    ("partner ahead (> 300, not mating)", lambda x: x["ps"] is not None and 300 < x["ps"] < MATE),
    ("partner mated", lambda x: x["ps"] is not None and x["ps"] <= -MATE),
    ("partner mating", lambda x: x["ps"] is not None and x["ps"] >= MATE),
    ("sitting (pass)", lambda x: x["sit"]),
]


def per_game(rows, pred, yfn, sfn):
    per = collections.defaultdict(lambda: [0, 0.0, 0.0])
    for x in rows:
        if pred(x):
            p = per[x["g"]]
            p[0] += 1
            p[1] += sfn(x)
            p[2] += yfn(x)
    return per


def boot(per, B=B):
    gl = sorted(per)
    n = sum(p[0] for p in per.values())
    if not n:
        return None
    st = sum(p[1] for p in per.values()) / n
    y = sum(p[2] for p in per.values()) / n
    allg = sorted({g for g in ALLG})
    bs = []
    for _ in range(B):
        nn = s = w = 0
        for g in random.choices(allg, k=len(allg)):
            p = per.get(g)
            if p:
                nn += p[0]
                s += p[1]
                w += p[2]
        if nn:
            bs.append((w - s) / nn)
    bs.sort()
    return n, len(gl), st, y, y - st, bs[int(.025 * len(bs))], bs[int(.975 * len(bs)) - 1]


ALLG = set()


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-9:
            return None
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                if f:
                    for k in range(c, n + 1):
                        M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def linmodel(rows, terms, yfn, nb=400):
    k = len(terms)
    per = {}
    for x in rows:
        v = [1.0 if fn(x) else 0.0 for _, fn in terms]
        y = yfn(x)
        A, bb = per.setdefault(x["g"], ([[0.0] * k for _ in range(k)], [0.0] * k))
        nz = [i for i in range(k) if v[i]]
        for i in nz:
            bb[i] += y
            for j in nz:
                A[i][j] += 1.0
    games = sorted(per)

    def fit(sample):
        A = [[0.0] * k for _ in range(k)]
        bb = [0.0] * k
        for g in sample:
            a, b2 = per[g]
            for i in range(k):
                bb[i] += b2[i]
                ai, Ai = a[i], A[i]
                for j in range(k):
                    Ai[j] += ai[j]
        for i in range(k):
            A[i][i] += 1.0          # one pseudo-observation of ridge: keeps empty indicators solvable
        return solve(A, bb)
    est = fit(games)
    bs = [b for b in (fit(random.choices(games, k=len(games))) for _ in range(nb)) if b]
    ci = []
    for i in range(k):
        v = sorted(b[i] for b in bs)
        ci.append((v[int(.025 * len(v))], v[int(.975 * len(v)) - 1]))
    return est, ci


BANDS = [("score -300..+300", lambda x: -300 <= x["score"] <= 300), ("score +300..+1000", lambda x: 300 < x["score"] <= 1000),
         ("score > +1000", lambda x: x["score"] > 1000), ("score < -300", lambda x: x["score"] < -300)]


def main():
    rows = build_rows()
    ALLG.update(x["g"] for x in rows)
    print(f"sets: {SETS}")
    print(f"{len(rows)} decisions with a non-mate score, {len(ALLG)} games; by engine "
          + str(dict(collections.Counter(x['engine'] for x in rows))))
    subsets = [("all", rows)] + [(e, [x for x in rows if x["engine"] == e]) for e in sorted({x["engine"] for x in rows})]

    # ---------- A: result bias by feature
    for name, sel in subsets:
        print(f"\n## A. Result minus stated chance, {name}; 95% interval by game resampling")
        print("| feature | decisions | games | stated | won | bias | 95% interval |")
        print("|---|---|---|---|---|---|---|")
        r = boot(per_game(sel, lambda x: True, lambda x: x["won"], lambda x: x["stated"]))
        print(f"| all | {r[0]} | {r[1]} | {r[2]:.3f} | {r[3]:.3f} | {r[4]:+.3f} | {r[5]:+.3f} to {r[6]:+.3f} |")
        for fname, fn in FEATS:
            r = boot(per_game(sel, lambda x, fn=fn: bool(fn(x)), lambda x: x["won"], lambda x: x["stated"]))
            if r and r[0] >= 30:
                print(f"| {fname} | {r[0]} | {r[1]} | {r[2]:.3f} | {r[3]:.3f} | {r[4]:+.3f} | {r[5]:+.3f} to {r[6]:+.3f} |")

    # ---------- calibration by stated band
    print("\n## Calibration of the stated chance by band (all rows), with game-resampled interval of won")
    for lo, hi in ((0, .1), (.1, .25), (.25, .4), (.4, .6), (.6, .75), (.75, .9), (.9, 1.01)):
        for name, sel in subsets:
            r = boot(per_game(sel, lambda x: lo <= x["stated"] < hi, lambda x: x["won"], lambda x: x["stated"]))
            if r:
                print(f"  {lo:.2f}-{min(hi, 1):.2f} {name:8}: n={r[0]:5} stated {r[2]:.3f} won {r[3]:.3f} bias {r[4]:+.3f} [{r[5]:+.3f}, {r[6]:+.3f}]")

    # ---------- B: collapse rate by feature within score bands
    rows_b = [x for x in rows if x["has_next"] and not x["sit"]]
    print(f"\n## B. Collapse within 3 decisions (forced mate, or 600+ cp lower and below -300); {len(rows_b)} moving decisions")
    for bname, bfn in BANDS[:3]:
        for name, sel in subsets:
            sb = [x for x in rows_b if (name == "all" or x["engine"] == name) and bfn(x)]
            base = per_game(sb, lambda x: True, lambda x: 1.0 if x["col3"] else 0.0, lambda x: 0.0)
            r0 = boot(base)
            if not r0:
                continue
            print(f"\n### {bname}, {name}: {r0[0]} decisions, collapse rate {r0[3]:.3f} [{r0[5]:.3f}, {r0[6]:.3f}]")
            print("| feature | with: n | rate | 95% | without: rate | diff |")
            print("|---|---|---|---|---|---|")
            for fname, fn in FEATS:
                w = per_game(sb, lambda x, fn=fn: bool(fn(x)), lambda x: 1.0 if x["col3"] else 0.0, lambda x: 0.0)
                wo = per_game(sb, lambda x, fn=fn: not fn(x), lambda x: 1.0 if x["col3"] else 0.0, lambda x: 0.0)
                rw, rwo = boot(w, 500), boot(wo, 500)
                if rw and rwo and rw[0] >= 30:
                    print(f"| {fname} | {rw[0]} | {rw[3]:.3f} | {rw[5]:.3f}-{rw[6]:.3f} | {rwo[3]:.3f} | {rw[3] - rwo[3]:+.3f} |")

    # ---------- joint models
    JT = [("intercept", lambda x: True)] + [(n, fn) for n, fn in FEATS if n not in (
        "king 2+ ranks up", "opponent hand 4+ points", "own hand 4+ points", "partner mated", "partner mating", "opponent hand 0",
        "sitting (pass)", "own hand 9+ points", "in check")] + [
        ("partner mated", lambda x: x["ps"] is not None and x["ps"] <= -MATE),
        ("partner mating", lambda x: x["ps"] is not None and x["ps"] >= MATE),
        ("stated above 0.5", lambda x: x["stated"] > 0.5)]
    for name, sel in subsets:
        est, ci = linmodel(sel, JT, lambda x: x["won"] - x["stated"])
        print(f"\n## Joint linear model of (won - stated), {name}: {len(sel)} decisions; 95% by game resampling (400)")
        print("| term | coefficient | 95% interval |")
        print("|---|---|---|")
        for (t, _), e, c in zip(JT, est, ci):
            star = " *" if c[0] > 0 or c[1] < 0 else ""
            print(f"| {t} | {e:+.3f} | {c[0]:+.3f} to {c[1]:+.3f}{star} |")
    JB = [("score -300..+300", BANDS[0][1]), ("score +300..+1000", BANDS[1][1]), ("score > +1000", BANDS[2][1]),
          ("score < -300", BANDS[3][1])] + [(n, fn) for n, fn in FEATS if n not in (
              "king 2+ ranks up", "opponent hand 4+ points", "own hand 4+ points", "opponent hand 0", "sitting (pass)",
              "own hand 9+ points", "partner mated", "partner mating")]
    for name, sel in subsets:
        sb = [x for x in rows_b if x["engine"] == name] if name != "all" else rows_b
        est, ci = linmodel(sb, JB, lambda x: 1.0 if x["col3"] else 0.0)
        print(f"\n## Joint linear model of collapse-within-3 (score bands as intercepts), {name}: {len(sb)} decisions")
        print("| term | coefficient | 95% interval |")
        print("|---|---|---|")
        for (t, _), e, c in zip(JB, est, ci):
            star = " *" if c[0] > 0 or c[1] < 0 else ""
            print(f"| {t} | {e:+.3f} | {c[0]:+.3f} to {c[1]:+.3f}{star} |")

    # ---------- the most wrong decisions in lost games
    if not MORE:
        print("\n## Most wrong: the losing team's decisions at >= 0 followed within 3 decisions by a mate or a score <= -800")
        wrong = [x for x in rows if x["won"] == 0 and x["score"] >= 0 and x["has_next"] and (x["mated3"] or (x["low3"] is not None and x["low3"] <= -800))]
        wrong.sort(key=lambda x: -(x["score"] - max(x["low3"], -3000)))
        seen = set()
        print("| engine | game | seat | n | score | worst of next 3 | king rank/shelter/zone | hands own/opp | opp drop checks (safe) | queen drop checks (safe) | partner |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for x in wrong:
            if (x["g"], x["seat"]) in seen:
                continue
            seen.add((x["g"], x["seat"]))
            f = x["f"]
            print(f"| {x['engine']} | {x['g'][1]} | {x['seat']} | {x['n']} | {x['score']} | {fm(x['low3'])} | {f['krank']}/{f['shelter']}/{f['kzone_att']} | "
                  f"{f['hand_own']}/{f['hand_opp']} | {f['opp_drop_checks']} ({f['opp_safe_drop_checks']}) | {f['q_drop_checks']} ({f['q_safe_drop_checks']}) | {fm(x['ps'])} |")
        print(f"\n{len(seen)} seat-games with such a decision; by engine "
              + str(dict(collections.Counter(e for e in [next(x['engine'] for x in wrong if (x['g'], x['seat']) == k) for k in seen]))))
        # wrong vs right: feature prevalence, decisions at >= 0 that moved
        sel0 = [x for x in rows_b if x["score"] >= 0]
        print(f"\n## Wrong vs right at score >= 0 (moving decisions, all games): wrong = collapse within 3 ({sum(x['col3'] for x in sel0)}), right = not ({sum(not x['col3'] for x in sel0)})")
        print("| feature | share among wrong | share among right | ratio |")
        print("|---|---|---|---|")
        W = [x for x in sel0 if x["col3"]]
        R = [x for x in sel0 if not x["col3"]]
        for fname, fn in FEATS:
            a = sum(1 for x in W if fn(x)) / max(1, len(W))
            b = sum(1 for x in R if fn(x)) / max(1, len(R))
            print(f"| {fname} | {a:.3f} | {b:.3f} | {a / b if b else float('inf'):.2f} |")
        # scored a win and lost
        print("\n## Lost games in which a seat of the losing team had scored +500 or more / a forced mate for itself")
        for e in sorted({x["engine"] for x in rows}):
            gs = {x["g"] for x in rows if x["engine"] == e and x["won"] == 0}
            g500 = {x["g"] for x in rows if x["engine"] == e and x["won"] == 0 and x["score"] >= 500}
            print(f"  {e}: {len(g500)} of {len(gs)} lost games had a decision at +500 or more")


if __name__ == "__main__":
    main()
