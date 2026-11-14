#!/usr/bin/env python3
"""AUTOPSY3: for falls whose key step was an arrival (A1-A5), the partner's move that let the piece go:
its own score at that decision and at its next, beside our drop. Team change = partner's change + our drop
(both clipped to +-3000), the measure the two-board fit (SURFACE.md) says the result follows.
    nice -n 19 python3 partner_net.py  -> partner_net.txt"""
import collections, json, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import common3 as c3
clip = c3.clip
R = json.load(open(os.path.join(HERE, "falls_l50.json")))
want = collections.defaultdict(list)
for r in R:
    if r["cls"] in ("A1", "A2", "A3", "A4", "A5") and r.get("partner_n") is not None:
        want[r["match"]].append(r)
out = []
for m, rs in want.items():
    d = c3.load(m)
    seq = c3.by_seat(d["rows"])
    for r in rs:
        P = [x for x in seq[(r["game"], c3.PARTNER[r["seat"]])] if x["score"] is not None]
        i = next((k for k, x in enumerate(P) if x["n"] == r["partner_n"]), None)
        if i is None or i + 1 >= len(P):
            r["p_delta"] = None
            continue
        r["p_before"], r["p_after"] = P[i]["score"], P[i + 1]["score"]
        r["p_delta"] = clip(P[i + 1]["score"]) - clip(P[i]["score"])
        r["team_delta"] = r["p_delta"] + r["drop"]
        r["p_line"] = (P[i].get("mainpv") or [])[:4]
        out.append(r)
    del d
lines = ["# The partner's move that let the fatal piece go", "",
         "Falls whose key step was an arrival. Partner before/after: its main score at that decision and at its next "
         "(clipped to +-3000). Team change: the partner's change plus our drop.", ""]
lines.append("| class | n | partner before (median) | partner change (median) | our drop (median) | team change (median) | team change < -300 | partner change >= our loss |")
lines.append("|---|---|---|---|---|---|---|---|")
def med(xs): return f"{st.median(xs):+.0f}" if xs else "-"
groups = [(k, [r for r in out if r["cls"] == k]) for k in ("A1", "A3", "A4", "A5")] + [("all", out)]
for k, s in groups:
    if not s: continue
    lines.append(f"| {k} | {len(s)} | {med([r['p_before'] for r in s])} | {med([r['p_delta'] for r in s])} | {med([r['drop'] for r in s])} | "
                 f"{med([r['team_delta'] for r in s])} | {sum(r['team_delta'] < -300 for r in s)} | {sum(r['p_delta'] >= -r['drop'] for r in s)} |")
lines.append("")
lines.append("By whether the partner's own line had the capture (partner_line):")
lines.append("")
lines.append("| partner's line had it | n | partner change (median) | team change (median) | team change < -300 | team won |")
lines.append("|---|---|---|---|---|---|")
for name, s in (("yes", [r for r in out if r.get("partner_line")]), ("no", [r for r in out if not r.get("partner_line")])):
    lines.append(f"| {name} | {len(s)} | {med([r['p_delta'] for r in s])} | {med([r['team_delta'] for r in s])} | {sum(r['team_delta'] < -300 for r in s)} | {sum(r['won'] == 1 for r in s)} |")
lines.append("")
lines.append("By the partner's score before (its board):")
lines.append("")
lines.append("| partner before | n | partner change (median) | team change (median) | team change < -300 | team won |")
lines.append("|---|---|---|---|---|---|")
for name, fn in (("below -300", lambda x: x < -300), ("-300 to +300", lambda x: -300 <= x <= 300), ("above +300", lambda x: x > 300)):
    s = [r for r in out if fn(r["p_before"])]
    lines.append(f"| {name} | {len(s)} | {med([r['p_delta'] for r in s])} | {med([r['team_delta'] for r in s])} | {sum(r['team_delta'] < -300 for r in s)} | {sum(r['won'] == 1 for r in s)} |")
lines.append("")
lines.append("By the fatal piece:")
lines.append("")
lines.append("| piece | n | partner change (median) | our drop (median) | team change (median) | team change < -300 |")
lines.append("|---|---|---|---|---|---|")
for t in "QRBNP":
    s = [r for r in out if max(r["arr_minus"], key="PNBRQ".index) == t]
    if s:
        lines.append(f"| {t} | {len(s)} | {med([r['p_delta'] for r in s])} | {med([r['drop'] for r in s])} | {med([r['team_delta'] for r in s])} | {sum(r['team_delta'] < -300 for r in s)} |")
text = "\n".join(lines)
open(os.path.join(HERE, "partner_net.txt"), "w").write(text + "\n")
json.dump({f"{r['match']}/{r['game']}/{r['seat']}": {k: r.get(k) for k in ("p_before", "p_after", "p_delta", "team_delta", "p_line")} for r in out},
          open(os.path.join(HERE, "partner_net.json"), "w"))
print(text)
