#!/usr/bin/env python3
"""How should the two boards' scores be combined to predict the team's result?

    nice -n 19 python3 logs/loss-analysis/team/combine.py logs/late50-vs-np-b logs/late50-vs-late25 logs/worlds5-vs-l50

Reads MATCH/postmortem.jsonl. Every decision of a seat is paired with its partner seat's most recent decision in
the same game (partner n <= own n); pairs with a missing score are skipped. Scores beyond +/-90000 become +/-3000,
then every score is clamped to +/-3000. Result: the seat's team's `won` (draw 0.5).

One-parameter models p = 1/(1+exp(-x/scale)), x = own, partner, sum, min, max, mean; scale by least log loss on a
log grid. Two-parameter model p = 1/(1+exp(-(a*min + b*max))) on a grid around the full-data Newton fit.
Intervals: 500 resamples of games (match, game), each model refitted on each resample.
Pure Python (no numpy here). Writes the report to stdout.
"""
import json
import math
import random
import sys
import operator
import collections

CLAMP = 3000
MATE = 90000
B = 500
CANDIDATES = ("hb-late50", "hb-l50")


def clamp(s):
    if s >= MATE:
        s = CLAMP
    elif s <= -MATE:
        s = -CLAMP
    return max(-CLAMP, min(CLAMP, s))


def load(dirs):
    pairs = []          # (gamekey, engine, own, partner, won, gap_ms)
    partner = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
    for d in dirs:
        tag = d.rstrip("/").split("/")[-1]
        by = collections.defaultdict(list)
        for l in open(f"{d}/postmortem.jsonl"):
            r = json.loads(l)
            by[(r["game"], r["seat"])].append((r["n"], r["t"], r["score"], r["won"], r["engine"]))
        for v in by.values():
            v.sort(key=lambda x: (x[0], x[1]))   # stable: same n keeps log order
        for (g, seat), v in by.items():
            pv = by.get((g, partner[seat]), [])
            j = -1
            for n, t, s, won, e in v:
                while j + 1 < len(pv) and pv[j + 1][0] <= n:
                    j += 1
                if j < 0 or s is None or pv[j][2] is None:
                    continue
                pairs.append(((tag, g), e, clamp(s), clamp(pv[j][2]), won, t - pv[j][1]))
    return pairs


def logloss_terms(x, y, scale):
    z = x / scale
    # -[y log p + (1-y) log(1-p)], p = sigmoid(z)
    if z >= 0:
        lp, lq = -math.log1p(math.exp(-z)), -z - math.log1p(math.exp(-z))
    else:
        lp, lq = z - math.log1p(math.exp(z)), -math.log1p(math.exp(z))
    return -(y * lp + (1 - y) * lq)


def loss2(a, b, mn, mx, y):
    return logloss_terms(a * mn + b * mx, y, 1.0)


def newton2(rows):
    """logistic regression without intercept on (min, max), in units of 1/1000 cp for conditioning"""
    a = b = 0.0
    for _ in range(25):
        ga = gb = haa = hab = hbb = 0.0
        for mn, mx, y in rows:
            u, v = mn / 1000, mx / 1000
            p = 1 / (1 + math.exp(-(a * u + b * v)))
            ga += (p - y) * u
            gb += (p - y) * v
            w = p * (1 - p)
            haa += w * u * u
            hab += w * u * v
            hbb += w * v * v
        det = haa * hbb - hab * hab
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a, b = a - da, b - db
        if abs(da) + abs(db) < 1e-9:
            break
    return a / 1000, b / 1000


def pctl(xs, q):
    xs = sorted(xs)
    i = q * (len(xs) - 1)
    lo = int(math.floor(i))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def analyse(pairs, label, rng, out):
    games = sorted({p[0] for p in pairs})
    gi = {g: i for i, g in enumerate(games)}
    G = len(games)
    ndec = [0] * G
    for p in pairs:
        ndec[gi[p[0]]] += 1
    feats = {
        "own": lambda o, q: o, "partner": lambda o, q: q, "sum": lambda o, q: o + q,
        "smaller": lambda o, q: min(o, q), "larger": lambda o, q: max(o, q), "mean": lambda o, q: (o + q) / 2,
    }
    scales = [50 * (20000 / 50) ** (k / 119) for k in range(120)]
    # per-model, per-scale, per-game summed loss
    agg = {}
    for name, f in feats.items():
        xs = [(gi[p[0]], f(p[2], p[3]), p[4]) for p in pairs]
        m = []
        for s in scales:
            row = [0.0] * G
            for g, x, y in xs:
                row[g] += logloss_terms(x, y, s)
            m.append(row)
        agg[name] = m
    # two-parameter: Newton on all data, then a grid around it
    a0, b0 = newton2([(min(p[2], p[3]), max(p[2], p[3]), p[4]) for p in pairs])
    grid2 = [(a0 * fa, b0 * fb) for fa in [0.4 + 0.05 * k for k in range(25)] for fb in [0.4 + 0.05 * k for k in range(25)]]
    xs2 = [(gi[p[0]], min(p[2], p[3]), max(p[2], p[3]), p[4]) for p in pairs]
    m2 = []
    for a, b in grid2:
        row = [0.0] * G
        for g, mn, mx, y in xs2:
            row[g] += loss2(a, b, mn, mx, y)
        m2.append(row)
    full2 = sum(loss2(a0, b0, mn, mx, y) for _, mn, mx, y in xs2) / len(xs2)

    def fit(m, c, nd):
        best = None
        for k, row in enumerate(m):
            v = sum(map(operator.mul, row, c)) / nd
            if best is None or v < best[0]:
                best = (v, k)
        return best

    ones = [1] * G
    full = {name: fit(agg[name], ones, len(pairs)) for name in feats}
    boot = collections.defaultdict(list)
    for _ in range(B):
        c = [0] * G
        for _ in range(G):
            c[rng.randrange(G)] += 1
        nd = sum(map(operator.mul, ndec, c))
        res = {name: fit(agg[name], c, nd) for name in feats}
        v2, k2 = fit(m2, c, nd)
        res["min+max"] = (v2, k2)
        for name, (v, k) in res.items():
            boot[name].append((v, k))
    names = list(feats) + ["min+max"]
    out.append(f"### {label}: {len(pairs)} paired decisions, {G} games")
    out.append("")
    out.append("| model | best scale (cp per logistic unit) | 95% interval | log loss | 95% interval | beats the sum in |")
    out.append("|---|---|---|---|---|---|")
    sumv = [v for v, _ in boot["sum"]]
    for name in names:
        bv = [v for v, _ in boot[name]]
        beats = sum(1 for v, s in zip(bv, sumv) if v < s - 1e-12) / B
        if name == "min+max":
            ka = [grid2[k] for _, k in boot[name]]
            edge = sum(1 for _, k in boot[name] if k // 25 in (0, 24) or k % 25 in (0, 24))
            sc = (f"min x {a0 * 1000:.3f}, max x {b0 * 1000:.3f} per 1000 cp (scales {1 / a0:.0f} and {1 / b0:.0f} cp)"
                  if a0 > 0 and b0 > 0 else f"min x {a0 * 1000:.3f}, max x {b0 * 1000:.3f} per 1000 cp")
            ci = (f"min {pctl([x[0] * 1000 for x in ka], .025):.3f}..{pctl([x[0] * 1000 for x in ka], .975):.3f}, "
                  f"max {pctl([x[1] * 1000 for x in ka], .025):.3f}..{pctl([x[1] * 1000 for x in ka], .975):.3f}"
                  + (f" ({edge} resamples at the grid edge)" if edge else ""))
            out.append(f"| {name} (two weights) | {sc} | {ci} | {full2:.4f} | {pctl(bv, .025):.4f}..{pctl(bv, .975):.4f} | {pct(beats)} |")
        else:
            v, k = full[name]
            ks = [scales[k] for _, k in boot[name]]
            edge = sum(1 for _, k in boot[name] if k in (0, len(scales) - 1))
            out.append(f"| {name} | {scales[k]:.0f} | {pctl(ks, .025):.0f}..{pctl(ks, .975):.0f}"
                       + (f" ({edge} at the grid edge)" if edge else "")
                       + f" | {v:.4f} | {pctl(bv, .025):.4f}..{pctl(bv, .975):.4f} | "
                       + ("-" if name == "sum" else pct(beats)) + " |")
    # paired differences against the sum
    out.append("")
    diffs = []
    for name in names:
        if name == "sum":
            continue
        d = [v - s for (v, _), s in zip(boot[name], sumv)]
        diffs.append(f"{name} {1000 * (sum(d) / B):+.2f} ({1000 * pctl(d, .025):+.2f}..{1000 * pctl(d, .975):+.2f})")
    out.append("Log loss minus the sum's, x1000, resampled mean (95%): " + "; ".join(diffs) + ".")
    out.append("")
    return games, gi


def pct(x):
    return f"{100 * x:.1f}%"


def direct(pairs, label, rng, out):
    games = sorted({p[0] for p in pairs})
    G = len(games)
    gi = {g: i for i, g in enumerate(games)}

    def one_and_zero(lo, hi, zlo, zhi):
        return lambda o, q: (lo <= o <= hi and zlo <= q <= zhi) or (lo <= q <= hi and zlo <= o <= zhi)

    def both(lo, hi):
        return lambda o, q: lo <= o <= hi and lo <= q <= hi

    comps = [
        ("(+300, 0): one 200..400, other -100..100", one_and_zero(200, 400, -100, 100),
         "(+150, +150): both 50..250", both(50, 250)),
        ("(+600, 0): one 500..700, other -100..100", one_and_zero(500, 700, -100, 100),
         "(+300, +300): both 200..400", both(200, 400)),
        ("(0, -300): one -100..100, other -400..-200", one_and_zero(-400, -200, -100, 100),
         "(-150, -150): both -250..-50", both(-250, -50)),
    ]
    out.append(f"### Direct comparison, {label}")
    out.append("")
    out.append("| cell | paired decisions | games | team win rate | 95% interval | | other cell | paired decisions | games | team win rate | 95% interval | difference (first - second), 95% | first better in |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for la, fa, lb, fb in comps:
        sa = [[0.0, 0] for _ in range(G)]
        sb = [[0.0, 0] for _ in range(G)]
        for p in pairs:
            if fa(p[2], p[3]):
                sa[gi[p[0]]][0] += p[4]
                sa[gi[p[0]]][1] += 1
            if fb(p[2], p[3]):
                sb[gi[p[0]]][0] += p[4]
                sb[gi[p[0]]][1] += 1
        na, nb = sum(x[1] for x in sa), sum(x[1] for x in sb)
        ga, gb = sum(1 for x in sa if x[1]), sum(1 for x in sb if x[1])
        wa = sum(x[0] for x in sa) / na if na else float("nan")
        wb = sum(x[0] for x in sb) / nb if nb else float("nan")
        ra, rb, rd = [], [], []
        for _ in range(B):
            c = [0] * G
            for _ in range(G):
                c[rng.randrange(G)] += 1
            wa_ = sum(x[0] * k for x, k in zip(sa, c)); na_ = sum(x[1] * k for x, k in zip(sa, c))
            wb_ = sum(x[0] * k for x, k in zip(sb, c)); nb_ = sum(x[1] * k for x, k in zip(sb, c))
            if na_ and nb_:
                ra.append(wa_ / na_); rb.append(wb_ / nb_); rd.append(wa_ / na_ - wb_ / nb_)
        if not rd:
            out.append(f"| {la} | {na} | {ga} | - | - | | {lb} | {nb} | {gb} | - | - | - | - |")
            continue
        out.append(f"| {la} | {na} | {ga} | {pct(wa)} | {pct(pctl(ra, .025))}..{pct(pctl(ra, .975))} | | {lb} | {nb} | {gb} | "
                   f"{pct(wb)} | {pct(pctl(rb, .025))}..{pct(pctl(rb, .975))} | {100 * (wa - wb):+.1f} pts "
                   f"({100 * pctl(rd, .025):+.1f}..{100 * pctl(rd, .975):+.1f}) | {pct(sum(1 for d in rd if d > 0) / len(rd))} |")
    out.append("")


def main():
    dirs = sys.argv[1:]
    rng = random.Random(20261111)
    pairs = load(dirs)
    out = ["# Combining the two boards' scores", "", "Matches: " + ", ".join(d.rstrip("/").split("/")[-1] for d in dirs) + ".", ""]
    gaps = sorted(abs(p[5]) for p in pairs)
    out.append(f"Pairs: {len(pairs)}; time between a decision and its partner's paired decision: median {pctl(gaps, .5) / 1000:.1f} s, "
               f"90th percentile {pctl(gaps, .9) / 1000:.1f} s. Draws count 0.5.")
    out.append("")
    cand = [p for p in pairs if p[1] in CANDIDATES]
    for label, sel in (("candidates (" + ", ".join(CANDIDATES) + ")", cand), ("all engines", pairs)):
        analyse(sel, label, rng, out)
    for label, sel in (("candidates", cand), ("all engines", pairs)):
        direct(sel, label, rng, out)
    print("\n".join(out))


if __name__ == "__main__":
    main()
