#!/usr/bin/env python3
"""Missed supplies (PARTNER_TALK.md, "What to measure before any code", first bullet).

usage: nice -n 19 python3 logs/loss-analysis/missed/missed.py MATCH_DIR [MATCH_DIR ...]
Reads results.jsonl and the postmortem.jsonl saved before this change (missed/<tag>.postmortem.before.jsonl).
"""
import collections
import json
import os
import sys

sys.dont_write_bytecode = True
ROOT = "/home/anbernal/Projects/HypeBeast-v5"
sys.path.insert(0, ROOT + "/scripts")
import postmortem as pm  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def show(title, head, lines):
    print(title)
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for l in lines:
        print("| " + " | ".join(str(x) for x in l) + " |")
    print()


pooled = collections.defaultdict(list)   # (level, engine) -> units
for d in sys.argv[1:]:
    tag = d.rstrip("/").split("/")[-1]
    games = pm.load_games(d)
    rows = [json.loads(l) for l in open(f"{HERE}/{tag}.postmortem.before.jsonl")]
    recs = pm.missed_supplies(games, rows)
    engines = sorted({r["engine"] for r in rows})
    print(f"# {tag}: {len(games)} games, {len(rows)} decisions")
    print()
    for level in ("decision", "episode"):
        units = pm.supply_units(recs, level)
        lines = []
        for e in engines:
            ue = [u for u in units if u["engine"] == e]
            pooled[(level, e)] += ue
            lines.append([e] + pm.supply_line(ue))
        show(f"{level}s", ["engine"] + pm.SUPPLY_HEAD, lines)
        lines = []
        for t in "PNBRQ":
            ut = [u for u in units if t in u["types"]]
            if ut:
                lines.append([t] + pm.supply_line(ut))
        show(f"{level}s by piece (both engines)", ["T"] + pm.SUPPLY_HEAD, lines)
    # diagnostics
    multi = collections.Counter(len({x['T'] for x in recs if x['row'] is r}) for r in {id(x['row']): x['row'] for x in recs}.values())
    print("decisions by number of mating types:", dict(multi))
    print("(decision,T) records:", len(recs), " partner had no later move:", sum(1 for x in recs if not x["js"]),
          " took a T within 3 moves though it could not at once:", sum(1 for x in recs if x["did"] and not x["could"]))
    sits = [r for r in rows if r["decision"] in ("pass", "")]
    print("sit decisions:", len(sits), " of which some +T world has any value:",
          sum(1 for r in sits if any(w["v_chosen"] is not None or w["v_main"] is not None for w in r["worlds"])))
    alt = sum(1 for r in rows if not pm.mating_pieces(r) and any(
        w["arrival"].startswith("+") and len(w["arrival"]) == 2 and (w["v_best"] or 0) >= pm.MATE for w in r["worlds"])
        and any(w["arrival"] == "none" and w["v_best"] is not None and w["v_best"] < pm.MATE for w in r["worlds"]))
    print("decisions where only another candidate (not the move played) mates with a single +T:", alt)
    nonemate = sum(1 for r in rows if any(w["arrival"] == "none" and (w["v_chosen"] or 0) >= pm.MATE for w in r["worlds"]))
    print("decisions where the move already mates with nothing arriving:", nonemate)
    lefts = collections.Counter(min(x["row"]["left"], 9) for x in recs)
    print("plies of our board left at the decision (9 = 9+):", dict(sorted(lefts.items())))
    print()

print("# pooled over the three matches")
print()
for level in ("decision", "episode"):
    es = sorted({e for (lv, e) in pooled if lv == level})
    show(f"{level}s", ["engine"] + pm.SUPPLY_HEAD, [[e] + pm.supply_line(pooled[(level, e)]) for e in es])
    allu = [u for e in es for u in pooled[(level, e)]]
    show(f"{level}s by piece (all engines, all matches)", ["T"] + pm.SUPPLY_HEAD,
         [[t] + pm.supply_line([u for u in allu if t in u["types"]]) for t in "PNBRQ" if any(t in u["types"] for u in allu)])
