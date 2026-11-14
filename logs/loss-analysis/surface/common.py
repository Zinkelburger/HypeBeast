"""Shared code for the two-board surface analysis (pure Python: no numpy on this machine).

Pairs: every decision of a seat with its partner seat's most recent decision in the same game (partner n <= own n),
both scores present. Scores beyond +/-90000 are forced mates -> +/-3000 with a flag; all clamped to +/-3000.
"""
import json
import math
import os
import random
import operator
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MATCHES = ["late25-vs-np", "late25-vs-np-b", "late50-vs-late25", "late50-vs-np-b", "late85-vs-late50",
           "worlds5-vs-l50", "timing2-vs-l50", "gap0-vs-np", "np-woff-vs-np"]
CLAMP = 3000
MATE = 90000
PARTNER = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
CACHE = os.path.join(HERE, "pairs.json")


def clampm(s):
    """-> (clamped score, mate flag +1/-1/0)"""
    if s >= MATE:
        return CLAMP, 1
    if s <= -MATE:
        return -CLAMP, -1
    return max(-CLAMP, min(CLAMP, s)), 0


def build_pairs():
    pairs = []
    for m in MATCHES:
        by = collections.defaultdict(list)
        for l in open(os.path.join(ROOT, "logs", m, "postmortem.jsonl")):
            r = json.loads(l)
            by[(r["game"], r["seat"])].append((r["n"], r["t"], r["score"], r["won"], r["engine"]))
        for v in by.values():
            v.sort(key=lambda x: (x[0], x[1]))
        for (g, seat), v in by.items():
            pv = by.get((g, PARTNER[seat]), [])
            j = -1
            for n, t, s, won, e in v:
                while j + 1 < len(pv) and pv[j + 1][0] <= n:
                    j += 1
                if j < 0 or s is None or pv[j][2] is None:
                    continue
                a, fa = clampm(s)
                b, fb = clampm(pv[j][2])
                pairs.append({"m": m, "g": g, "e": e, "seat": seat, "n": n, "t": t, "a": a, "b": b, "fa": fa, "fb": fb,
                              "y": won, "gap": t - pv[j][1]})
    json.dump(pairs, open(CACHE, "w"))
    return pairs


def load_pairs():
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    return build_pairs()


def game_index(pairs):
    games = sorted({(p["m"], p["g"]) for p in pairs})
    gi = {g: i for i, g in enumerate(games)}
    return games, [gi[(p["m"], p["g"])] for p in pairs]


def folds_by_game(G, k=10, seed=1):
    order = list(range(G))
    random.Random(seed).shuffle(order)
    f = [0] * G
    for r, g in enumerate(order):
        f[g] = r % k
    return f


def boot_counts(G, rng):
    c = [0] * G
    for _ in range(G):
        c[rng.randrange(G)] += 1
    return c


def pctl(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    i = q * (len(xs) - 1)
    lo = int(math.floor(i))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def sigmoid(z):
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)
    return e / (1 + e)


def ll(z, y):
    """log loss of target y (0..1) at logit z"""
    if z >= 0:
        l1 = math.log1p(math.exp(-z))
        return y * l1 + (1 - y) * (z + l1)
    l1 = math.log1p(math.exp(z))
    return y * (l1 - z) + (1 - y) * l1


# ---------- dense linear algebra (small) ----------

def cholesky_solve(A, b):
    """solve A x = b for symmetric positive definite A (list of lists); returns x"""
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        Li = L[i]
        Ai = A[i]
        for j in range(i + 1):
            Lj = L[j]
            s = Ai[j] - sum(map(operator.mul, Li[:j], Lj[:j]))
            if i == j:
                if s <= 0:
                    s = 1e-12
                Li[i] = math.sqrt(s)
            else:
                Li[j] = s / Lj[j]
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(map(operator.mul, L[i][:i], y[:i]))) / L[i][i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = y[i]
        for k in range(i + 1, n):
            s -= L[k][i] * x[k]
        x[i] = s / L[i][i]
    return x


# ---------- logistic regression on dense features ----------

def fit_logistic(X, y, w=None, beta=None, ridge=1e-6, iters=50, tol=1e-9):
    """X: list of feature tuples (include a 1.0 column for an intercept). w: row weights. Returns (beta, mean loss)."""
    k = len(X[0])
    if beta is None:
        beta = [0.0] * k
    if w is None:
        w = [1.0] * len(X)
    for _ in range(iters):
        g = [0.0] * k
        H = [[0.0] * k for _ in range(k)]
        for x, yy, ww in zip(X, y, w):
            if not ww:
                continue
            z = sum(map(operator.mul, beta, x))
            p = sigmoid(z)
            r = ww * (p - yy)
            q = ww * p * (1 - p)
            for i in range(k):
                xi = x[i]
                g[i] += r * xi
                qi = q * xi
                Hi = H[i]
                for j in range(i + 1):
                    Hi[j] += qi * x[j]
        for i in range(k):
            for j in range(i):
                H[j][i] = H[i][j]
            H[i][i] += ridge
            g[i] += ridge * beta[i]
        d = cholesky_solve(H, g)
        step = 1.0
        old = loss_logistic(X, y, w, beta, ridge)
        while True:
            nb = [b - step * di for b, di in zip(beta, d)]
            new = loss_logistic(X, y, w, nb, ridge)
            if new <= old + 1e-12 or step < 1e-4:
                break
            step /= 2
        beta = nb
        if max(abs(step * di) for di in d) < tol:
            break
    sw = sum(w)
    return beta, loss_logistic(X, y, w, beta, 0) / sw


def loss_logistic(X, y, w, beta, ridge=0.0):
    s = 0.0
    for x, yy, ww in zip(X, y, w):
        if ww:
            s += ww * ll(sum(map(operator.mul, beta, x)), yy)
    return s + 0.5 * ridge * sum(b * b for b in beta)


def golden(f, lo, hi, tol=0.01):
    gr = (math.sqrt(5) - 1) / 2
    c, d = hi - gr * (hi - lo), lo + gr * (hi - lo)
    fc, fd = f(c), f(d)
    while hi - lo > tol:
        if fc < fd:
            hi, d, fd = d, c, fc
            c = hi - gr * (hi - lo)
            fc = f(c)
        else:
            lo, c, fc = c, d, fd
            d = lo + gr * (hi - lo)
            fd = f(d)
    return (lo + hi) / 2


# ---------- flexible model: symmetric bilinear (tent) surface with a second-difference penalty ----------

KNOTS = [-3000, -2200, -1700, -1300, -1000, -800, -600, -450, -300, -150, 0,
         150, 300, 450, 600, 800, 1000, 1300, 1700, 2200, 3000]
NK = len(KNOTS)


NP = NK + 2      # positions: 0 = forced mate against, 1..NK = score knots, NK+1 = forced mate for


def sym_index():
    idx = {}
    k = 0
    for i in range(NP):
        for j in range(i, NP):
            idx[(i, j)] = idx[(j, i)] = k
            k += 1
    return idx, k


SYM, NSYM = sym_index()


def tent(s):
    """-> [(knot index, weight)]"""
    if s <= KNOTS[0]:
        return [(0, 1.0)]
    if s >= KNOTS[-1]:
        return [(NK - 1, 1.0)]
    k = 0
    while KNOTS[k + 1] < s:
        k += 1
    u = (s - KNOTS[k]) / (KNOTS[k + 1] - KNOTS[k])
    if u <= 0:
        return [(k, 1.0)]
    if u >= 1:
        return [(k + 1, 1.0)]
    return [(k, 1 - u), (k + 1, u)]


def pos(s, f):
    if f < 0:
        return [(0, 1.0)]
    if f > 0:
        return [(NP - 1, 1.0)]
    return [(i + 1, w) for i, w in tent(s)]


def flex_row(a, b, fa=0, fb=0):
    d = collections.defaultdict(float)
    for i, wi in pos(a, fa):
        for j, wj in pos(b, fb):
            d[SYM[(i, j)]] += wi * wj
    return list(d.items())


def penalty_matrix():
    """second differences IN KNOT-INDEX SPACE (the knots are unevenly spaced; a centipawn-curvature penalty was also
    tried, cv_flex_cppen.json, and cross-validated slightly worse) along the score knots (positions 1..NK) in each direction, for every value of the other
    coordinate (mate positions included there); a small ridge on the three mate x mate cells"""
    P = [[0.0] * NSYM for _ in range(NSYM)]
    rows = []
    for i in range(2, NK):
        for j in range(NP):
            rows.append([(SYM[(i - 1, j)], 1.0), (SYM[(i, j)], -2.0), (SYM[(i + 1, j)], 1.0)])
            rows.append([(SYM[(j, i - 1)], 1.0), (SYM[(j, i)], -2.0), (SYM[(j, i + 1)], 1.0)])
    for r in rows:
        dd = collections.defaultdict(float)
        for k, v in r:
            dd[k] += v
        it = list(dd.items())
        for k1, v1 in it:
            for k2, v2 in it:
                P[k1][k2] += v1 * v2
    for i, j in ((0, 0), (0, NP - 1), (NP - 1, NP - 1)):
        P[SYM[(i, j)]][SYM[(i, j)]] += 0.01
    return P


PEN = None


def flex_loss(R, y, w, th, lam):
    s = 0.0
    for r, yy, ww in zip(R, y, w):
        if ww:
            z = 0.0
            for k, v in r:
                z += th[k] * v
            s += ww * ll(z, yy)
    pt = 0.0
    for i in range(NSYM):
        Pi = PEN[i]
        pt += th[i] * sum(map(operator.mul, Pi, th))
    return s + 0.5 * lam * pt


def fit_flex(R, y, w, lam, th=None, iters=30, tol=1e-6):
    global PEN
    if PEN is None:
        PEN = penalty_matrix()
    if th is None:
        th = [0.0] * NSYM
    for _ in range(iters):
        g = [0.0] * NSYM
        H = [[0.0] * NSYM for _ in range(NSYM)]
        for r, yy, ww in zip(R, y, w):
            if not ww:
                continue
            z = 0.0
            for k, v in r:
                z += th[k] * v
            p = sigmoid(z)
            res = ww * (p - yy)
            q = ww * p * (1 - p)
            for k1, v1 in r:
                g[k1] += res * v1
                qv = q * v1
                Hk = H[k1]
                for k2, v2 in r:
                    Hk[k2] += qv * v2
        for i in range(NSYM):
            Pi = PEN[i]
            g[i] += lam * sum(map(operator.mul, Pi, th))
            Hi = H[i]
            for j in range(NSYM):
                Hi[j] += lam * Pi[j]
            Hi[i] += 1e-6
        d = cholesky_solve(H, g)
        old = flex_loss(R, y, w, th, lam)
        step = 1.0
        while True:
            nt = [t - step * di for t, di in zip(th, d)]
            new = flex_loss(R, y, w, nt, lam)
            if new <= old + 1e-9 or step < 1e-3:
                break
            step /= 2
        th = nt
        if max(abs(step * di) for di in d) < tol:
            break
    return th


def flex_eval(th, a, b, fa=0, fb=0):
    z = 0.0
    for k, v in flex_row(a, b, fa, fb):
        z += th[k] * v
    return z
