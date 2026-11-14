#!/usr/bin/env python3
"""Per-engine figures of a guard match, as in EXPERIMENTS.md's 23:05 table. Logs only.
    nice -n 19 python3 guardstats.py MATCH [MATCH ...]
Per engine: decisions; guard below the floor ("low"); guard probed, with the mean number of types; a mate price
set (price_mates >= 1); rescue= or partner_held= logged; main-search nodes (mean); the seat's own main score
over decisions at plies 40 to 80 with no mate price set (clipped to +-3000; mean); sudden mates (a decision at
-300 or better followed by a forced mate against at the seat's next); first to see itself mated (games)."""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common3 as c3  # noqa: E402

for m in sys.argv[1:]:
    d = c3.load(m)
    by = collections.defaultdict(list)
    for r in d["rows"]:
        by[r["engine"]].append(r)
    seq = c3.by_seat(d["rows"])
    first = collections.Counter()
    for g in d["games"]:
        seen = [r for (gg, s), rs in seq.items() if gg == g["game"] for r in rs if r["score"] is not None and r["score"] <= -90000]
        if seen:
            first[min(seen, key=lambda r: (r["n"], r["t"]))["engine"]] += 1
    print(f"## {m}")
    print("| engine | decisions | guard low | guard probed (mean types) | mate price set | rescue/held logged | main nodes (mean) | own score, plies 40-80, no mate price (mean) | sudden mates | first to see itself mated |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for e, rs in sorted(by.items()):
        n = len(rs)
        gl = sum((r.get("sumd") or {}).get("guard") == "low" for r in rs)
        gp = [r for r in rs if (r.get("sumd") or {}).get("guard") not in (None, "low")]
        types = sum(len(r["sumd"]["guard"]) for r in gp) / len(gp) if gp else 0
        mp = sum(int((r.get("sumd") or {}).get("price_mates", 0) or 0) > 0 for r in rs)
        rh = sum(bool((r.get("sumd") or {}).get("rescue") or (r.get("sumd") or {}).get("partner_held")) for r in rs)
        nodes = [r["main_nodes"] for r in rs if r.get("main_nodes")]
        own = [c3.clip(r["score"]) for r in rs if r["score"] is not None and 40 <= r["n"] <= 80
               and int((r.get("sumd") or {}).get("price_mates", 0) or 0) == 0]
        sud = 0
        for (gg, s), xs in seq.items():
            xs = [x for x in xs if x["engine"] == e and x["score"] is not None]
            for a, b in zip(xs, xs[1:]):
                if a["score"] > -300 and b["score"] <= -90000:
                    sud += 1
        print(f"| {e} | {n} | {gl} ({100 * gl / n:.1f}%) | {len(gp)} ({100 * len(gp) / n:.1f}%, {types:.1f}) | {mp} ({100 * mp / n:.1f}%) | {rh} | "
              f"{sum(nodes) / len(nodes) / 1000:.0f}k | {sum(own) / len(own):+.0f} ({len(own)}) | {sud} | {first[e]} |")
    print()
