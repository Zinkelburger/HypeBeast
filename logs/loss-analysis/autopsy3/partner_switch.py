#!/usr/bin/env python3
"""AUTOPSY3: was the partner's move that let the fatal piece go a switch away from its main move?
Against the partner's switch rate over all its decisions. -> partner_switch.txt
    nice -n 19 python3 partner_switch.py"""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import common3 as c3
R = json.load(open(os.path.join(HERE, "falls_l50.json")))
want = collections.defaultdict(list)
for r in R:
    if r["cls"] in ("A1", "A2", "A3", "A4", "A5") and r.get("partner_n") is not None:
        want[r["match"]].append(r)
base = collections.Counter()
res = []
for m in c3.L50_MATCHES:
    d = c3.load(m)
    seq = c3.by_seat(d["rows"])
    for r in d["rows"]:
        if r["engine"] == "hb-l50":
            base["all"] += 1
            base["override"] += r["override"]
            base[r["reason"]] += 1
    for r in want.get(m, []):
        P = next((x for x in seq[(r["game"], c3.PARTNER[r["seat"]])] if x["n"] == r["partner_n"]), None)
        if P is None:
            continue
        # world values of the partner's main move against the move it played, in the partner's own worlds
        co = P.get("coord") or {}
        none = next((w for w in co.get("worlds", []) if w["arrival"] == "none" and w.get("scored")), None)
        gap = None
        if P["override"] and none and P["main"] in none["values"] and P["decision"] in none["values"]:
            gap = c3.clip(none["values"][P["main"]]) - c3.clip(none["values"][P["decision"]])
        res.append({"cls": r["cls"], "override": P["override"], "reason": P["reason"], "gap_none": gap,
                    "partner_line": r.get("partner_line"), "won": r["won"], "E_main": P["E_main"], "E_chosen": P["E_chosen"]})
    del d
lines = ["# The partner's feeding move: a switch?", ""]
lines.append(f"hb-l50 decisions overall: {base['all']}, switched away from the main move {base['override']} "
             f"({100 * base['override'] / base['all']:.1f}%): world_switch {base['world_switch']}, exposure_veto {base['exposure_veto']}, "
             f"soft_switch {base['soft_switch']}.")
lines.append("")
n = len(res)
sw = [x for x in res if x["override"]]
lines.append(f"Arrival falls with the partner's decision found: {n}. The partner's move there was a switch in {len(sw)} "
             f"({100 * len(sw) / n:.1f}%). Reasons: {dict(collections.Counter(x['reason'] for x in sw).most_common())}.")
lines.append("")
gaps = sorted(x["gap_none"] for x in sw if x["gap_none"] is not None)
if gaps:
    lines.append(f"In the partner's own \"none\" world its main move scored above the move played by a median of "
                 f"{gaps[len(gaps) // 2]:+d} cp (quartiles {gaps[len(gaps) // 4]:+d} and {gaps[3 * len(gaps) // 4]:+d}; {len(gaps)} with both scored).")
lines.append("")
lines.append("| class | n | partner switched | partner's own line had the capture |")
lines.append("|---|---|---|---|")
for k in ("A1", "A3", "A4", "A5"):
    s = [x for x in res if x["cls"] == k]
    lines.append(f"| {k} | {len(s)} | {sum(x['override'] for x in s)} | {sum(bool(x['partner_line']) for x in s)} |")
lines.append("")
lines.append("Of the switches, the capture was in the partner's own main line (from its main move, not the move played) "
             "in none by construction; the partner's line had it, the partner kept its main move: "
             f"{sum(bool(x['partner_line']) for x in res)}; neither: {sum(not x['partner_line'] and not x['override'] for x in res)}.")
text = "\n".join(lines)
open(os.path.join(HERE, "partner_switch.txt"), "w").write(text + "\n")
print(text)
