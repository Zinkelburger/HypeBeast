#!/usr/bin/env python3
"""Model comparison by 10-fold cross-validation holding out whole games.

    nice -n 19 python3 logs/loss-analysis/surface/models.py simple    -> surface/cv_simple.json
    nice -n 19 python3 logs/loss-analysis/surface/models.py flex      -> surface/cv_flex.json, surface/flex_full.json
    nice -n 19 python3 logs/loss-analysis/surface/models.py extra F   -> surface/cv_extra.json (phase and mate flags on formula F)

Scores in units of 1000 cp inside the fits. Every model has an intercept (or spans constants).
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa
from common import *  # noqa

K = 10


def gpow(s, p):
    return math.copysign(abs(s) ** p, s)


def tent_feats(a, b):
    f = [0.0] * C.NK
    for i, w in C.tent(a * 1000):
        f[i] += w
    for i, w in C.tent(b * 1000):
        f[i] += w
    return tuple(f)


def tent_feats_m(a, b, fa, fb):
    """per-board free h on the score knots, forced mates as their own categories (mate for, mate against)"""
    f = [0.0] * (C.NK + 2)
    for s, fl in ((a, fa), (b, fb)):
        if fl > 0:
            f[C.NK] += 1
        elif fl < 0:
            f[C.NK + 1] += 1
        else:
            for i, w in C.tent(s * 1000):
                f[i] += w
    return tuple(f)


def regimes(a, b, fa, fb):
    """no mate: (1, a+b); exactly one mate for / against: its own level and slope in the other board's score;
    two mates: one level each for (for, for), (against, against), (for, against)"""
    mf, ma = (fa > 0) + (fb > 0), (fa < 0) + (fb < 0)
    nm = float(mf + ma == 0)
    o1 = float(mf == 1 and ma == 0)
    a1 = float(ma == 1 and mf == 0)
    other = b if fa else a
    return (nm, nm * (a + b), o1, o1 * other, a1, a1 * other, float(mf == 2), float(ma == 2), float(mf == 1 and ma == 1))


def clipm(s, f, L):
    return L if f > 0 else -L if f < 0 else max(-L, min(L, s))


def tanhm(s, f, L):
    return 1.0 if f > 0 else -1.0 if f < 0 else math.tanh(s / L)


# each simple model: (name, features(a, b, p) with a, b in 1000 cp; True if it has a power parameter)
SIMPLE = [
    ("a. sum", lambda a, b, p, fa=0, fb=0: (1.0, a + b), False),
    ("b. power g(a)+g(b)", lambda a, b, p, fa=0, fb=0: (1.0, gpow(a, p) + gpow(b, p)), True),
    ("c. weaker, stronger", lambda a, b, p, fa=0, fb=0: (1.0, min(a, b), max(a, b)), False),
    ("d. sum + a*b", lambda a, b, p, fa=0, fb=0: (1.0, a + b, a * b), False),
    ("e. sum + |a-b|", lambda a, b, p, fa=0, fb=0: (1.0, a + b, abs(a - b)), False),
    ("x1. own, partner (two weights)", lambda a, b, p, fa=0, fb=0: (1.0, a, b), False),
    ("x2. power + |a-b|", lambda a, b, p, fa=0, fb=0: (1.0, gpow(a, p) + gpow(b, p), abs(a - b)), True),
    ("x3. sum + sum of cubes", lambda a, b, p, fa=0, fb=0: (1.0, a + b, a ** 3 + b ** 3), False),
    ("x4. additive h(a)+h(b), h free (21-knot piecewise linear)", lambda a, b, p, fa=0, fb=0: tent_feats(a, b), False),
    # mate-aware: fa, fb = +1 forced mate for, -1 against, 0 none
    ("m1. sum + mate counts", lambda a, b, p, fa=0, fb=0: (1.0, a + b, float((fa > 0) + (fb > 0)), float((fa < 0) + (fb < 0))), False),
    ("m2. clipped sum (clip at L) + mate counts", lambda a, b, p, fa=0, fb=0: (1.0, clipm(a, fa, p) + clipm(b, fb, p), float((fa > 0) + (fb > 0)), float((fa < 0) + (fb < 0))), True),
    ("m3. tanh sum, L*[tanh(a/L)+tanh(b/L)], + mate counts", lambda a, b, p, fa=0, fb=0: (1.0, p * (tanhm(a, fa, p) + tanhm(b, fb, p)), float((fa > 0) + (fb > 0)), float((fa < 0) + (fb < 0))), True),
    ("m4. additive h(a)+h(b), h free, mates own categories", lambda a, b, p, fa=0, fb=0: tent_feats_m(a, b, fa, fb), False),
    ("m7. sum + a*b + mate counts", lambda a, b, p, fa=0, fb=0: (1.0, a + b, a * b, float((fa > 0) + (fb > 0)), float((fa < 0) + (fb < 0))), False),
    ("m8. sum + |a-b| + mate counts", lambda a, b, p, fa=0, fb=0: (1.0, a + b, abs(a - b), float((fa > 0) + (fb > 0)), float((fa < 0) + (fb < 0))), False),
    ("m9. weaker, stronger + mate counts", lambda a, b, p, fa=0, fb=0: (1.0, min(a, b), max(a, b), float((fa > 0) + (fb > 0)), float((fa < 0) + (fb < 0))), False),
    ("m10. own, partner + mate flags by board", lambda a, b, p, fa=0, fb=0: (1.0, a, b, float(fa > 0), float(fa < 0), float(fb > 0), float(fb < 0)), False),
    ("m11. sum shrunk by imbalance, (a+b)/(1+|a-b|/M), + mate counts", lambda a, b, p, fa=0, fb=0: (1.0, (a + b) / (1 + abs(a - b) / p), float((fa > 0) + (fb > 0)), float((fa < 0) + (fb < 0))), True),
    ("m12. sum when no mate; a mate sets its own level (slope in the other board)", lambda a, b, p, fa=0, fb=0: regimes(a, b, fa, fb), False),
    ("m5. clipped sum + |a-b| + mate counts", lambda a, b, p, fa=0, fb=0: (1.0, clipm(a, fa, p) + clipm(b, fb, p), abs(clipm(a, fa, p) - clipm(b, fb, p)), float((fa > 0) + (fb > 0)), float((fa < 0) + (fb < 0))), True),
    ("m6. clipped sum + clipped product + mate counts", lambda a, b, p, fa=0, fb=0: (1.0, clipm(a, fa, p) + clipm(b, fb, p), clipm(a, fa, p) * clipm(b, fb, p), float((fa > 0) + (fb > 0)), float((fa < 0) + (fb < 0))), True),
]


def fit_model(feat, haspow, A, Bv, y, w, p0=1.25, beta0=None, FA=None, FB=None, lo=0.4, hi=3.0):
    FA = FA or [0] * len(A)
    FB = FB or [0] * len(A)
    if not haspow:
        X = [feat(a, b, None, fa, fb) for a, b, fa, fb in zip(A, Bv, FA, FB)]
        beta, l = fit_logistic(X, y, w, beta=beta0)
        return beta, None, l
    cache = {}

    def f(p):
        X = [feat(a, b, p, fa, fb) for a, b, fa, fb in zip(A, Bv, FA, FB)]
        beta, l = fit_logistic(X, y, w, beta=cache.get("beta"))
        cache["beta"] = beta
        cache[p] = (beta, l)
        return l
    p = golden(f, lo, hi, tol=0.01)
    f(p)
    return cache[p][0], p, cache[p][1]


def heldout(feat, beta, p, A, Bv, y, idx, FA, FB):
    s = 0.0
    for i in idx:
        s += ll(sum(map(lambda u, v: u * v, beta, feat(A[i], Bv[i], p, FA[i], FB[i]))), y[i])
    return s


def main():
    stage = sys.argv[1]
    pairs = load_pairs()
    games, gidx = game_index(pairs)
    G = len(games)
    fold = folds_by_game(G, K, seed=7)
    rf = [fold[g] for g in gidx]
    A = [p["a"] / 1000 for p in pairs]
    Bv = [p["b"] / 1000 for p in pairs]
    y = [p["y"] for p in pairs]
    FA = [p["fa"] for p in pairs]
    FB = [p["fb"] for p in pairs]
    N = len(pairs)
    fidx = [[i for i in range(N) if rf[i] == k] for k in range(K)]
    if stage == "simple":
        path = os.path.join(HERE, "cv_simple.json")
        only = sys.argv[2].split(",") if len(sys.argv) > 2 else None
        res = json.load(open(path)) if only and os.path.exists(path) else {}
        for name, feat, haspow in SIMPLE:
            if only and not any(name.startswith(o) for o in only):
                continue
            t0 = time.time()
            rng_ = (0.3, 20.0) if name.startswith("m11") else (0.3, 3.0) if name.startswith("m") else (0.4, 3.0)
            beta, p, l = fit_model(feat, haspow, A, Bv, y, None, FA=FA, FB=FB, lo=rng_[0], hi=rng_[1])
            fl = []
            fp = []
            for k in range(K):
                w = [0.0 if rf[i] == k else 1.0 for i in range(N)]
                b_, p_, _ = fit_model(feat, haspow, A, Bv, y, w, beta0=beta if not haspow else None, FA=FA, FB=FB,
                                      lo=max(rng_[0], p * 0.6) if p else rng_[0], hi=min(rng_[1], p * 1.6) if p else rng_[1])
                fl.append(heldout(feat, b_, p_, A, Bv, y, fidx[k], FA, FB))
                fp.append(p_)
            res[name] = {"beta": beta, "p": p, "train_loss": l, "fold_loss_sum": fl, "fold_n": [len(x) for x in fidx],
                         "fold_p": fp}
            print(f"{name}: beta={['%.4f' % b for b in beta]} p={p} train={l:.5f} cv={sum(fl) / N:.5f} "
                  f"({time.time() - t0:.0f} s)", flush=True)
            json.dump(res, open(path, "w"), indent=1)
    elif stage == "flex":
        R = [C.flex_row(p["a"], p["b"], p["fa"], p["fb"]) for p in pairs]
        lams = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1, 3, 10, 30, 100, 300, 1000]
        res = {"lams": lams, "fold_n": [len(x) for x in fidx], "fold_loss_sum": {}}
        prev = {}
        for lam in lams:
            t0 = time.time()
            fl = []
            for k in range(K):
                w = [0.0 if rf[i] == k else 1.0 for i in range(N)]
                th = C.fit_flex(R, y, w, lam, th=prev.get(k))
                prev[k] = th
                s = 0.0
                for i in fidx[k]:
                    z = 0.0
                    for kk, v in R[i]:
                        z += th[kk] * v
                    s += ll(z, y[i])
                fl.append(s)
            res["fold_loss_sum"][str(lam)] = fl
            print(f"flex lam={lam}: cv={sum(fl) / N:.5f} ({time.time() - t0:.0f} s)", flush=True)
            json.dump(res, open(os.path.join(HERE, "cv_flex.json"), "w"), indent=1)
        best = min(lams, key=lambda l: sum(res["fold_loss_sum"][str(l)]))
        th = C.fit_flex(R, y, [1.0] * N, best)
        res["best_lam"] = best
        json.dump(res, open(os.path.join(HERE, "cv_flex.json"), "w"), indent=1)
        json.dump({"lam": best, "knots": C.KNOTS, "theta": th}, open(os.path.join(HERE, "flex_full.json"), "w"))
        print("best lam", best)
    elif stage == "extra":
        # phase and mate flags on the chosen simple formula (name prefix in argv[2])
        base = [m for m in SIMPLE if m[0].startswith(sys.argv[2])][0]
        name, feat, haspow = base
        simple = json.load(open(os.path.join(HERE, "cv_simple.json")))
        p_full = simple[name]["p"]
        ply = [p["n"] / 100 for p in pairs]           # move tokens played (both boards) / 100
        tm = [p["t"] / 60000 for p in pairs]          # game clock, minutes
        mf = [(p["fa"] > 0) + (p["fb"] > 0) for p in pairs]
        ma = [(p["fa"] < 0) + (p["fb"] < 0) for p in pairs]
        mfo = [float(p["fa"] > 0) for p in pairs]
        mao = [float(p["fa"] < 0) for p in pairs]
        mfp = [float(p["fb"] > 0) for p in pairs]
        map_ = [float(p["fb"] < 0) for p in pairs]

        def F(i, p):
            return feat(A[i], Bv[i], p, FA[i], FB[i])
        variants = {
            "base": lambda i, p: F(i, p),
            "+ plies x formula": lambda i, p: F(i, p) + tuple(v * ply[i] for v in F(i, p)[1:]),
            "+ clock x formula": lambda i, p: F(i, p) + tuple(v * tm[i] for v in F(i, p)[1:]),
            "+ mate counts (for, against)": lambda i, p: F(i, p) + (mf[i], ma[i]),
            "+ mate flags by board (own for/against, partner for/against)": lambda i, p: F(i, p) + (mfo[i], mao[i], mfp[i], map_[i]),
            "+ mate counts + plies x formula": lambda i, p: F(i, p) + (mf[i], ma[i]) + tuple(v * ply[i] for v in F(i, p)[1:]),
        }
        if name.startswith("m"):     # base already has the mate terms
            variants = {
                "base": lambda i, p: F(i, p),
                "+ plies x score term only": lambda i, p: F(i, p) + (F(i, p)[1] * ply[i],),
                "+ plies x every term (score and mates)": lambda i, p: F(i, p) + tuple(v * ply[i] for v in F(i, p)[1:]),
                "+ clock x every term": lambda i, p: F(i, p) + tuple(v * tm[i] for v in F(i, p)[1:]),
                "+ plies main effect + plies x every term": lambda i, p: F(i, p) + (ply[i],) + tuple(v * ply[i] for v in F(i, p)[1:]),
            }
        res = {"base": name, "variants": {}}
        idx_all = list(range(N))
        for vn, vf in variants.items():
            t0 = time.time()

            def fitw(w, p0):
                if not haspow:
                    X = [vf(i, None) for i in idx_all]
                    b, l = fit_logistic(X, y, w)
                    return b, None, l
                cache = {}

                def f(p):
                    X = [vf(i, p) for i in idx_all]
                    b, l = fit_logistic(X, y, w, beta=cache.get("b"))
                    cache["b"] = b
                    cache[p] = (b, l)
                    return l
                p = golden(f, max(0.4, p0 - 0.8), p0 + 0.8, tol=0.01)
                f(p)
                return cache[p][0], p, cache[p][1]
            beta, p, l = fitw(None, p_full)
            fl = []
            for k in range(K):
                w = [0.0 if rf[i] == k else 1.0 for i in range(N)]
                b_, p_, _ = fitw(w, p_full)
                s = 0.0
                for i in fidx[k]:
                    s += ll(sum(map(lambda u, v: u * v, b_, vf(i, p_))), y[i])
                fl.append(s)
            res["variants"][vn] = {"beta": beta, "p": p, "train_loss": l, "fold_loss_sum": fl}
            print(f"{vn}: beta={['%.4f' % b for b in beta]} p={p} cv={sum(fl) / N:.5f} ({time.time() - t0:.0f} s)", flush=True)
        # shape by phase tercile (refit the base formula within each tercile of plies)
        cuts = sorted(ply)
        q1, q2 = cuts[N // 3], cuts[2 * N // 3]
        terc = {}
        for lab, sel in (("early", lambda v: v < q1), ("middle", lambda v: q1 <= v < q2), ("late", lambda v: v >= q2)):
            w = [1.0 if sel(ply[i]) else 0.0 for i in range(N)]
            b_, p_, l_ = fit_model(feat, haspow, A, Bv, y, w, FA=FA, FB=FB, lo=max(0.3, p_full - 1) if p_full else 0.4, hi=p_full + 1 if p_full else 3)
            terc[lab] = {"beta": b_, "p": p_, "loss": l_, "n": int(sum(w))}
            print(f"tercile {lab}: beta={['%.4f' % b for b in b_]} p={p_}", flush=True)
        res["terciles"] = {"cuts_plies": [q1 * 100, q2 * 100], "fits": terc}
        # without any mate rows
        w = [0.0 if (p["fa"] or p["fb"]) else 1.0 for p in pairs]
        b_, p_, l_ = fit_model(feat, haspow, A, Bv, y, w, FA=FA, FB=FB, lo=max(0.3, p_full - 1) if p_full else 0.4, hi=p_full + 1 if p_full else 3)
        res["no_mate_rows"] = {"beta": b_, "p": p_, "loss": l_, "n": int(sum(w))}
        print(f"no mate rows: beta={['%.4f' % b for b in b_]} p={p_}", flush=True)
        json.dump(res, open(os.path.join(HERE, "cv_extra.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
