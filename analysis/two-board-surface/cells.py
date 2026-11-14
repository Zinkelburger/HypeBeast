#!/usr/bin/env python3
"""Data summary and the empirical surface (team win rate per (own, partner) cell), intervals by resampling games.

    nice -n 19 python3 logs/loss-analysis/surface/cells.py

Writes surface/cells_own_partner.csv, surface/cells_weak_strong.csv (150 cp bins, mates separate) and
surface/cells.md (data summary + 300 cp tables for the report).
"""
import collections
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

B = 300


def bin150(s, f):
    if f > 0:
        return "M+"
    if f < 0:
        return "M-"
    if s < -1500:
        return "<-1500"
    if s >= 1500:
        return ">=1500"
    lo = -1500 + 150 * int((s + 1500) // 150)
    return f"{lo}..{lo + 150}"


BINS150 = ["M-", "<-1500"] + [f"{lo}..{lo + 150}" for lo in range(-1500, 1500, 150)] + [">=1500", "M+"]


def bin300(s, f):
    if f > 0 or s >= 1500:
        return ">=1500"
    if f < 0 or s < -1500:
        return "<-1500"
    lo = -1500 + 300 * int((s + 1500) // 300)
    return f"{lo}..{lo + 300}"


BINS300 = ["<-1500"] + [f"{lo}..{lo + 300}" for lo in range(-1500, 1500, 300)] + [">=1500"]


def grid(pairs, gidx, G, key, rng):
    cell = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0]))
    for p, g in zip(pairs, gidx):
        k = key(p)
        if k is None:
            continue
        c = cell[k][g]
        c[0] += p["y"]
        c[1] += 1
    res = {}
    boots = collections.defaultdict(list)
    cs = [boot_counts(G, rng) for _ in range(B)]
    for k, d in cell.items():
        items = list(d.items())
        n = sum(v[1] for _, v in items)
        wsum = sum(v[0] for _, v in items)
        for c in cs:
            nn = sum(v[1] * c[g] for g, v in items)
            if nn:
                boots[k].append(sum(v[0] * c[g] for g, v in items) / nn)
        res[k] = (n, len(items), wsum / n, pctl(boots[k], .025), pctl(boots[k], .975))
    return res


def main():
    pairs = load_pairs()
    games, gidx = game_index(pairs)
    G = len(games)
    rng = random.Random(20261111)
    out = []
    # ---- summary
    out.append("## Data")
    out.append("")
    out.append("| match | games | paired decisions | engines | mate score on own board | draws (games) |")
    out.append("|---|---|---|---|---|---|")
    bym = collections.defaultdict(list)
    for p in pairs:
        bym[p["m"]].append(p)
    for m in MATCHES:
        ps = bym[m]
        gs = {p["g"] for p in ps}
        dr = len({p["g"] for p in ps if p["y"] == 0.5})
        eng = sorted({p["e"] for p in ps})
        out.append(f"| {m} | {len(gs)} | {len(ps)} | {', '.join(eng)} | {100 * sum(1 for p in ps if p['fa']) / len(ps):.1f}% | {dr} |")
    nm = sum(1 for p in pairs if p["fa"] or p["fb"])
    gaps = sorted(abs(p["gap"]) for p in pairs)
    out.append(f"| **all** | {G} | {len(pairs)} | | {100 * sum(1 for p in pairs if p['fa']) / len(pairs):.1f}% | "
               f"{len({(p['m'], p['g']) for p in pairs if p['y'] == 0.5})} |")
    out.append("")
    out.append(f"Pairs with a forced mate on at least one board: {nm} ({100 * nm / len(pairs):.1f}%). "
               f"Time between a decision and the partner decision it is paired with: median {pctl(gaps, .5) / 1000:.1f} s, "
               f"90th percentile {pctl(gaps, .9) / 1000:.1f} s. Decisions per game: median "
               f"{pctl(list(collections.Counter(gidx).values()), .5):.0f}.")
    # consistency of mates with results
    mf = [p for p in pairs if p["fa"] > 0]
    ma = [p for p in pairs if p["fa"] < 0]
    out.append(f"Own board shows a forced mate FOR the seat: {len(mf)} decisions, team won {100 * sum(p['y'] for p in mf) / len(mf):.1f}%; "
               f"AGAINST: {len(ma)} decisions, team won {100 * sum(p['y'] for p in ma) / len(ma):.1f}%.")
    out.append("")
    # ---- grids
    op = grid(pairs, gidx, G, lambda p: (bin150(p["a"], p["fa"]), bin150(p["b"], p["fb"])), rng)
    with open(os.path.join(HERE, "cells_own_partner.csv"), "w") as f:
        f.write("own_bin,partner_bin,decisions,games,win_rate,lo95,hi95\n")
        for a in BINS150:
            for b in BINS150:
                if (a, b) in op:
                    n, g, w, lo, hi = op[(a, b)]
                    f.write(f"{a},{b},{n},{g},{w:.4f},{lo:.4f},{hi:.4f}\n")
    order = {b: i for i, b in enumerate(BINS150)}

    def ws(p):
        x, y = (bin150(p["a"], p["fa"]), bin150(p["b"], p["fb"]))
        return (x, y) if order[x] <= order[y] else (y, x)
    wsg = grid(pairs, gidx, G, ws, rng)
    with open(os.path.join(HERE, "cells_weak_strong.csv"), "w") as f:
        f.write("weaker_bin,stronger_bin,decisions,games,win_rate,lo95,hi95\n")
        for a in BINS150:
            for b in BINS150:
                if (a, b) in wsg:
                    n, g, w, lo, hi = wsg[(a, b)]
                    f.write(f"{a},{b},{n},{g},{w:.4f},{lo:.4f},{hi:.4f}\n")
    # coarse tables
    o3 = {b: i for i, b in enumerate(BINS300)}
    op3 = grid(pairs, gidx, G, lambda p: (bin300(p["a"], p["fa"]), bin300(p["b"], p["fb"])), rng)

    def ws3(p):
        x, y = bin300(p["a"], p["fa"]), bin300(p["b"], p["fb"])
        return (x, y) if o3[x] <= o3[y] else (y, x)
    ws3g = grid(pairs, gidx, G, ws3, rng)
    for title, g3, tri in (("own (across) x partner (down, top = partner far ahead)", op3, False),
                           ("weaker board (across) x stronger board (down)", ws3g, True)):
        out.append(f"### Team win rate, 300 cp cells: {title}")
        out.append("")
        out.append("Each cell: win % [95% interval] (games). Tails include forced mates. Empty: no data.")
        out.append("")
        out.append("| | " + " | ".join(BINS300) + " |")
        out.append("|---" * (len(BINS300) + 1) + "|")
        for b in reversed(BINS300):
            row = [f"**{b}**"]
            for a in BINS300:
                if tri and o3[a] > o3[b]:
                    row.append("")
                    continue
                if (a, b) in g3:
                    n, gg, w, lo, hi = g3[(a, b)]
                    row.append(f"{100 * w:.0f} [{100 * lo:.0f}-{100 * hi:.0f}] ({gg})")
                else:
                    row.append("")
            out.append("| " + " | ".join(row) + " |")
        out.append("")
    thin = sum(1 for v in op.values() if v[1] < 20)
    out.append(f"150 cp grid (own x partner): {len(op)} non-empty cells of {len(BINS150) ** 2}; {thin} have fewer than 20 games. "
               f"Weaker x stronger: {len(wsg)} non-empty cells, {sum(1 for v in wsg.values() if v[1] < 20)} with fewer than 20 games.")
    open(os.path.join(HERE, "cells.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
