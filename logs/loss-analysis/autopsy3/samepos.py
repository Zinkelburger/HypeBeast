#!/usr/bin/env python3
"""The two games of an opening pair start from the same position with colours swapped, so until they part the
contender in one game and the baseline in the other face the same positions at the same seats. At each such
position (same seat, same ply, same two FENs): do the two engines choose the same move, and how do their logged
budgets compare (main nodes, main depth, discovery nodes, delivery candidates)? Logs only.
    nice -n 19 python3 samepos.py MATCH [MATCH ...]   -> samepos.txt (appended per run, printed)"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common3 as c3  # noqa: E402


def num(r, k):
    try:
        return int((r.get("sumd") or {}).get(k))
    except (TypeError, ValueError):
        return None


out = []
for m in sys.argv[1:]:
    d = c3.load(m)
    games = {g["game"]: g for g in d["games"]}
    cname = d["games"][0]["names"]["contender"]
    bypair = collections.defaultdict(list)
    for g in d["games"]:
        bypair[g["pair"]].append(g["game"])
    rows = collections.defaultdict(dict)
    for r in d["rows"]:
        rows[r["game"]][(r["seat"], r["n"], r["fen_own"], r["fen_other"])] = r
    same = diff = 0
    first_diff_reason = collections.Counter()
    agg = collections.defaultdict(lambda: [0, 0, 0])  # key -> [sum_c, sum_b, n]
    deliv = collections.Counter()
    pairs_parted_at = []
    for p, gs in bypair.items():
        if len(gs) != 2:
            continue
        a, b = gs
        ra, rb = rows[a], rows[b]
        common = sorted(set(ra) & set(rb), key=lambda k: k[1])
        firstd = None
        for k in common:
            x, y = ra[k], rb[k]
            if x["engine"] == y["engine"]:
                continue
            c, bl = (x, y) if x["engine"] == cname else (y, x)
            if c["decision"] == bl["decision"]:
                same += 1
            else:
                diff += 1
                if firstd is None:
                    firstd = (k[1], c, bl)
            for key in ("main_nodes", "main_depth", "discovery_nodes", "probe_nodes", "deliveries", "common_depth"):
                vc = c["main_nodes"] if key == "main_nodes" else num(c, key)
                vb = bl["main_nodes"] if key == "main_nodes" else num(bl, key)
                if vc is not None and vb is not None:
                    agg[key][0] += vc
                    agg[key][1] += vb
                    agg[key][2] += 1
            deliv[(num(c, "deliveries") or 0, num(bl, "deliveries") or 0)] += 1
        if firstd:
            n, c, bl = firstd
            pairs_parted_at.append(n)
            first_diff_reason[(c["reason"], bl["reason"], "same main" if c["main"] == bl["main"] else "main differs")] += 1
    out.append(f"## {m}: {cname} and hb-l50 at the same position")
    out.append(f"Positions met by both (contender seat in one game of a pair, baseline seat in the other): {same + diff}; "
               f"same move {same}, different {diff} ({100 * diff / max(1, same + diff):.1f}%).")
    for key, (sc, sb, n) in agg.items():
        out.append(f"  {key}: {cname} {sc / n:.1f}, hb-l50 {sb / n:.1f} (n {n})")
    out.append(f"  delivery candidates (contender, baseline) counts: " + ", ".join(f"{k}: {v}" for k, v in sorted(deliv.items())))
    pp = sorted(pairs_parted_at)
    if pp:
        out.append(f"Pairs where the two engines chose differently at a shared position: {len(pp)}; ply of the first such (median) {pp[len(pp) // 2]}.")
    out.append("First different choice, by (contender reason, baseline reason, main move): " +
               "; ".join(f"{k}: {v}" for k, v in first_diff_reason.most_common(8)))
    out.append("")
    del d
text = "\n".join(out)
open(os.path.join(HERE, "samepos.txt"), "a").write(text + "\n")
print(text)
