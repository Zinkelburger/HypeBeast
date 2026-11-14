#!/usr/bin/env python3
"""Markdown tables from cv_simple.json, cv_flex.json, cv_extra.json and questions_boot.json.

    nice -n 19 python3 logs/loss-analysis/surface/summarise.py > logs/loss-analysis/surface/tables.md
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HERE, pctl  # noqa


def load(n):
    p = os.path.join(HERE, n)
    return json.load(open(p)) if os.path.exists(p) else None


def sd(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def cv_tables():
    s, f, e = load("cv_simple.json"), load("cv_flex.json"), load("cv_extra.json")
    rows = []
    fn = None
    if f:
        fn = f["fold_n"]
        N = sum(fn)
        for lam in f["lams"]:
            fl = f["fold_loss_sum"].get(str(lam))
            if fl:
                rows.append((f"f. flexible 2-D surface, lambda={lam:g}" + (" (chosen)" if lam == f.get("best_lam") else ""), fl))
        ref = f["fold_loss_sum"][str(f["best_lam"])] if f.get("best_lam") is not None else None
    for name, v in (s or {}).items():
        fn = v["fold_n"]
        rows.append((name + (f" (p={v['p']:.2f})" if v["p"] else ""), v["fold_loss_sum"]))
    if e:
        for vn, v in e["variants"].items():
            rows.append((f"g. {e['base']} {vn}" + (f" (p={v['p']:.2f})" if v["p"] else ""), v["fold_loss_sum"]))
    N = sum(fn)
    print("| model | CV log loss | SD across folds | minus flexible, x1000: pooled | per-fold SD | better than flexible in folds |")
    print("|---|---|---|---|---|---|")
    for name, fl in rows:
        per = [a / b for a, b in zip(fl, fn)]
        line = f"| {name} | {sum(fl) / N:.4f} | {sd(per):.4f} |"
        if f and ref:
            d = [(a - r) / b for a, r, b in zip(fl, ref, fn)]
            line += f" {1000 * (sum(fl) - sum(ref)) / N:+.2f} | {1000 * sd(d):.2f} | {sum(1 for x in d if x < 0)}/10 |"
        else:
            line += " | | |"
        print(line)
    print()
    if s:
        print("Full-data coefficients (scores in units of 1000 cp; the first coefficient is the intercept):")
        print()
        for name, v in s.items():
            fp = v.get("fold_p") or []
            fps = f", p across folds {min(fp):.2f}..{max(fp):.2f}" if v["p"] else ""
            print(f"- {name}: beta = [{', '.join('%.4f' % b for b in v['beta'])}]" + (f", p = {v['p']:.3f}{fps}" if v["p"] else ""))
        print()
    if e:
        print(f"Phase and mate variants of {e['base']} (full data):")
        print()
        for vn, v in e["variants"].items():
            print(f"- {vn}: beta = [{', '.join('%.4f' % b for b in v['beta'])}]" + (f", p = {v['p']:.3f}" if v["p"] else ""))
        t = e["terciles"]
        print(f"- terciles of plies played (cuts at {t['cuts_plies'][0]:.0f} and {t['cuts_plies'][1]:.0f} move tokens): " +
              "; ".join(f"{k}: beta = [{', '.join('%.4f' % b for b in v['beta'])}]" + (f", p = {v['p']:.3f}" if v["p"] else "") + f" (n={v['n']})"
                        for k, v in t["fits"].items()))
        v = e["no_mate_rows"]
        print(f"- rows with no forced mate on either board only (n={v['n']}): beta = [{', '.join('%.4f' % b for b in v['beta'])}]"
              + (f", p = {v['p']:.3f}" if v["p"] else ""))
        print()


def ci(full, bs, scale=100, fmt="{:.1f}"):
    bs = [b for b in bs if b is not None]
    if full is None or not bs:
        return "-"
    return (fmt.format(scale * full) + " [" + fmt.format(scale * pctl(bs, .025)) + ", " + fmt.format(scale * pctl(bs, .975))
            + "]")


def questions():
    q = load("questions_boot.json")
    if not q:
        return
    raw, models = q["raw"], q["models"]
    mnames = list(models)

    def mcell(m, key):
        M = models[m]
        return ci(M["full"][key], [b[key] for b in M["boot"]])

    def rcell(key):
        r = raw.get(key)
        if not r or r["p"] is None:
            return "-"
        return ci(r["p"], r["boot"]) + f" ({r['games']} g)"

    def rdiff(k1, k2):
        r1, r2 = raw[k1], raw[k2]
        if r1["p"] is None or r2["p"] is None:
            return "-"
        d = [a - b for a, b in zip(r1["boot"], r2["boot"]) if a is not None and b is not None]
        return ci(r1["p"] - r2["p"], d) + f" (better in {100 * sum(1 for x in d if x > 0) / len(d):.0f}%)"
    print("### Points and comparisons (win %, 95% interval from resampling games)")
    print()
    print("| | raw cells (both boards within 100 cp, either order) | " + " | ".join(mnames) + " |")
    print("|---" * (len(mnames) + 2) + "|")
    for k in ("(0,+600)", "(+300,+300)", "(-100,+700)"):
        print(f"| {k} | {rcell(k)} | " + " | ".join(mcell(m, k) for m in mnames) + " |")
    for a, b in (("(0,+600)", "(+300,+300)"), ("(-100,+700)", "(+300,+300)"), ("(-100,+700)", "(0,+600)")):
        key = f"{a} - {b}"
        cells = []
        for m in mnames:
            bs = [x[key] for x in models[m]["boot"]]
            cells.append(mcell(m, key) + f" (better in {100 * sum(1 for x in bs if x > 0) / len(bs):.0f}%)")
        print(f"| {key}, points | {rdiff(a, b)} | " + " | ".join(cells) + " |")
    print()
    print("### Along fixed totals: boards (T/2 - d, T/2 + d), win % [95%]")
    print()
    for T in (600, 300, 0, -300):
        print(f"**Total {T:+d}**")
        print()
        print("| d | boards | raw (sum within 150, half-gap within 75) | " + " | ".join(mnames) + " | " +
              " | ".join(f"{m}: change from d=0, pts" for m in mnames) + " |")
        print("|---" * (3 + 2 * len(mnames)) + "|")
        for d in (0, 100, 200, 300, 500, 800, 1200):
            k = f"T{T} d{d}"
            print(f"| {d} | ({T / 2 - d:+.0f}, {T / 2 + d:+.0f}) | {rcell(k)} | " + " | ".join(mcell(m, k) for m in mnames) + " | "
                  + " | ".join(mcell(m, k + " - d0") for m in mnames) + " |")
        print()
    print("### Behind on one board by x, ahead on the other by x, minus level (0,0): win-rate points [95%]")
    print()
    print("| x | raw (-x,+x) win % | " + " | ".join(mnames) + " |")
    print("|---" * (2 + len(mnames)) + "|")
    for x in (100, 200, 300, 400, 500, 600, 800, 1000, 1200, 1500, 2000, 2500, 3000):
        k = f"(-{x},+{x}) - (0,0)"
        print(f"| {x} | {rcell(f'(-{x},+{x})')} | " + " | ".join(mcell(m, k) for m in mnames) + " |")
    print(f"\nRaw (0,0) (sum within 150, half-gap within 75): {rcell('(0,0)')}.")
    print()
    for m, M in models.items():
        if "coefs" in M:
            ks = len(M["beta"])
            print(f"Coefficient intervals, {m}: " + ", ".join(
                f"beta{i} {M['beta'][i]:.4f} [{pctl([c['beta'][i] for c in M['coefs']], .025):.4f}, {pctl([c['beta'][i] for c in M['coefs']], .975):.4f}]"
                for i in range(ks)) + (f", p {M['p']:.3f} [{pctl([c['p'] for c in M['coefs']], .025):.3f}, {pctl([c['p'] for c in M['coefs']], .975):.3f}]" if M["p"] else ""))
            print()


def model_tables():
    import common as C
    from models import SIMPLE
    s, ff = load("cv_simple.json"), load("flex_full.json")
    AXT = [-1500, -1200, -900, -600, -300, 0, 300, 600, 900, 1200, 1500, 2200]
    models = []
    if ff:
        models.append(("flexible surface (lambda=%g)" % ff["lam"], lambda a, b, fa=0, fb=0: C.sigmoid(C.flex_eval(ff["theta"], a, b, fa, fb))))
    for pre in sys.argv[1:]:
        name, feat, haspow = [m for m in SIMPLE if m[0].startswith(pre)][0]
        v = s[name]
        models.append((name, (lambda feat, beta, p: lambda a, b, fa=0, fb=0: C.sigmoid(sum(u * w for u, w in zip(beta, feat(a / 1000, b / 1000, p, fa, fb)))))(feat, v["beta"], v["p"])))
    for name, P in models:
        print(f"### Model surface: {name}, team win % (own across, partner down)")
        print()
        print("| partner \\ own | " + " | ".join(f"{a:+d}" for a in AXT) + " | mate for |")
        print("|---" * (len(AXT) + 2) + "|")
        for b in [3000] + list(reversed(AXT)) + [-3000]:
            fb = 1 if b == 3000 else -1 if b == -3000 else 0
            lab = "mate for" if fb > 0 else "mate against" if fb < 0 else f"{b:+d}"
            row = [f"{100 * P(a, b, 0, fb):.0f}" for a in AXT] + [f"{100 * P(3000, b, 1, fb):.0f}"]
            print(f"| **{lab}** | " + " | ".join(row) + " |")
        print()
    if s:
        for key in s:
            if key.startswith("m4") or key.startswith("x4"):
                b = s[key]["beta"]
                print(f"Per-board h (logit units) from {key}: " + ", ".join(f"{k:+d}: {v:+.2f}" for k, v in zip(C.KNOTS, b[:C.NK]))
                      + (f"; mate for: {b[C.NK]:+.2f}, mate against: {b[C.NK + 1]:+.2f}" if len(b) > C.NK else ""))
                print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        model_tables()
    else:
        cv_tables()
        questions()
