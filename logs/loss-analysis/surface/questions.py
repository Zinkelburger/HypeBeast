#!/usr/bin/env python3
"""The owner's direct questions, from the raw cells and from fitted surfaces, intervals by resampling games.

    nice -n 19 python3 logs/loss-analysis/surface/questions.py "MODEL PREFIX,MODEL PREFIX,..." B_SIMPLE B_FLEX

Models: prefixes of names in models.SIMPLE, plus "flex" (the penalised 2-D surface at the CV-chosen lambda).
Writes surface/questions.md and surface/questions_boot.json.
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa
from common import *  # noqa
from models import SIMPLE, fit_model

TOTALS = [600, 300, 0, -300]
SPLITS = [0, 100, 200, 300, 500, 800, 1200]
POINTS = {"(0,+600)": (0, 600), "(+300,+300)": (300, 300), "(-100,+700)": (-100, 700)}
COMPARE = [("(0,+600)", "(+300,+300)"), ("(-100,+700)", "(+300,+300)"), ("(-100,+700)", "(0,+600)")]
XS = [100, 200, 300, 400, 500, 600, 800, 1000, 1200, 1500, 2000, 2500, 3000]


def quantities(P):
    """P(a, b) -> win prob. Returns dict of named numbers."""
    q = {}
    for k, (a, b) in POINTS.items():
        q[k] = P(a, b)
    for x, y in COMPARE:
        q[f"{x} - {y}"] = q[x] - q[y]
    for T in TOTALS:
        for d in SPLITS:
            q[f"T{T} d{d}"] = P(T / 2 - d, T / 2 + d)
            q[f"T{T} d{d} - d0"] = q[f"T{T} d{d}"] - P(T / 2, T / 2)
    for x in XS:
        q[f"(-{x},+{x}) - (0,0)"] = P(-x, x) - P(0, 0)
    return q


def raw_windows():
    """name -> predicate on (a, b, fa, fb), symmetric in the two boards"""
    w = {}

    def near(a, b, pa, pb, h=100):
        return (abs(a - pa) <= h and abs(b - pb) <= h) or (abs(b - pa) <= h and abs(a - pb) <= h)
    for k, (pa, pb) in POINTS.items():
        w[k] = (lambda pa, pb: lambda a, b, fa, fb: not fa and not fb and near(a, b, pa, pb))(pa, pb)
    for T in TOTALS:
        for d in SPLITS:
            w[f"T{T} d{d}"] = (lambda T, d: lambda a, b, fa, fb: not fa and not fb and abs(a + b - T) <= 150
                               and abs(abs(b - a) / 2 - d) <= 75)(T, d)
    for x in XS[:9]:
        w[f"(-{x},+{x})"] = (lambda x: lambda a, b, fa, fb: not fa and not fb and abs(a + b) <= 150
                             and abs(abs(b - a) / 2 - x) <= max(75, x / 6))(x)
    w["(0,0)"] = lambda a, b, fa, fb: not fa and not fb and abs(a + b) <= 150 and abs(b - a) / 2 <= 75
    return w


def main():
    names = sys.argv[1].split(",")
    BS, BF = int(sys.argv[2]), int(sys.argv[3])
    pairs = load_pairs()
    games, gidx = game_index(pairs)
    G = len(games)
    N = len(pairs)
    A = [p["a"] / 1000 for p in pairs]
    Bv = [p["b"] / 1000 for p in pairs]
    y = [p["y"] for p in pairs]
    FA = [p["fa"] for p in pairs]
    FB = [p["fb"] for p in pairs]
    rng = random.Random(424242)
    counts = [boot_counts(G, rng) for _ in range(max(BS, BF))]
    out = {"raw": {}, "models": {}}
    # ---- raw windows
    W = raw_windows()
    for k, pred in W.items():
        per = {}
        for p, g in zip(pairs, gidx):
            if pred(p["a"], p["b"], p["fa"], p["fb"]):
                v = per.setdefault(g, [0.0, 0])
                v[0] += p["y"]
                v[1] += 1
        items = list(per.items())
        n = sum(v[1] for _, v in items)
        bs = []
        for c in counts[:BS]:
            nn = sum(v[1] * c[g] for g, v in items)
            bs.append(sum(v[0] * c[g] for g, v in items) / nn if nn else None)
        out["raw"][k] = {"n": n, "games": len(items), "p": sum(v[0] for _, v in items) / n if n else None, "boot": bs}
    print("raw done", flush=True)
    # ---- models
    simple = json.load(open(os.path.join(HERE, "cv_simple.json")))
    for nm in names:
        t0 = time.time()
        if nm == "flex":
            ff = json.load(open(os.path.join(HERE, "flex_full.json")))
            th0, lam = ff["theta"], ff["lam"]
            R = [C.flex_row(p["a"], p["b"], p["fa"], p["fb"]) for p in pairs]
            full = quantities(lambda a, b: sigmoid(C.flex_eval(th0, a, b)))
            bs = []
            for bi, c in enumerate(counts[:BF]):
                w = [float(c[g]) for g in gidx]
                th = C.fit_flex(R, y, w, lam, th=th0)
                bs.append(quantities(lambda a, b: sigmoid(C.flex_eval(th, a, b))))
                if bi % 10 == 9:
                    print(f"  flex boot {bi + 1} ({time.time() - t0:.0f} s)", flush=True)
            out["models"]["flex"] = {"full": full, "boot": bs}
        else:
            name, feat, haspow = [m for m in SIMPLE if m[0].startswith(nm)][0]
            beta, p = simple[name]["beta"], simple[name]["p"]

            def mk(beta, p):
                return lambda a, b: sigmoid(sum(map(lambda u, v: u * v, beta, feat(a / 1000, b / 1000, p))))
            full = quantities(mk(beta, p))
            bs, coefs = [], []
            for c in counts[:BS]:
                w = [float(c[g]) for g in gidx]
                b_, p_, _ = fit_model(feat, haspow, A, Bv, y, w, beta0=beta if not haspow else None, FA=FA, FB=FB,
                                      lo=max(0.3, p - 0.6) if p else 0.4, hi=p + 0.6 if p else 3.0)
                bs.append(quantities(mk(b_, p_)))
                coefs.append({"beta": b_, "p": p_})
            out["models"][name] = {"full": full, "boot": bs, "coefs": coefs, "beta": beta, "p": p}
        print(f"{nm} done ({time.time() - t0:.0f} s)", flush=True)
        json.dump(out, open(os.path.join(HERE, "questions_boot.json"), "w"))


if __name__ == "__main__":
    main()
