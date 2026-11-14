#!/usr/bin/env python3
"""Tables from hazard.json. usage: hazard2.py HAZARD_JSON MATCH_DIR [MATCH_DIR ...]"""
import collections
import json
import statistics
import sys

sys.dont_write_bytecode = True
from losses import NAMES, TEAM, Replay  # noqa: E402

SOON = 20_000
rows = json.load(open(sys.argv[1]))

# captures by seat and type, per game
caps = collections.defaultdict(list)
for d in sys.argv[2:]:
    tag = d.rstrip("/").split("/")[-1]
    for l in open(f"{d}/results.jsonl"):
        r = json.loads(l)
        rp = Replay(r["opening"]["dual_fen"])
        for m in r["opening"]["moves"]:
            rp.push("A" if m[0] == "1" else "B", m[1:])
        for e in r["result"]["events"]:
            if e["kind"] == "move":
                info = rp.push(e["board"], e["uci"])
                if info["captured"]:
                    caps[f"{tag}:{r['game']}"].append((e["t"], e["seat"], NAMES[info["captured"]]))

OPP_PARTNER = {"A-white": "B-white", "A-black": "B-black", "B-white": "A-white", "B-black": "A-black"}


def ev_cp(e):
    if "mate" in e:
        return 30000 if e["mate"] > 0 else -30000
    return e["cp"]


for r in rows:
    r["soon"] = r["seen"] is not None and r["seen"] - r["t"] <= SOON
    r["cp"] = ev_cp(r["eval"]) if r["eval"] else None
    s = r["short"]
    r["mating_types"] = [p for p, n in s.items() if n > 0]
    r["flag"] = bool(r["mating_types"])
    r["flag_in_hand"] = any(r["opp_hand"][p] > 0 for p in r["mating_types"])
    r["flag_cap_now"] = r["wp_on_turn"] and any(r["partner_caps"].get(p) for p in r["mating_types"])
    r["n_types"] = len(r["mating_types"])
    arrive = [c for c in caps[r["game"]] if c[1] == OPP_PARTNER[r["seat"]] and r["t"] < c[0] <= r["t"] + 10_000]
    r["arrived10"] = any(c[2] in r["mating_types"] for c in arrive)
    r["any_cap10"] = bool(arrive)


def rate(sel, label):
    n = len(sel)
    k = sum(r["soon"] for r in sel)
    print(f"  {label:<46} {k:>5}/{n:<6} {100 * k / n if n else 0:5.1f}%")


def table(sub, name):
    print(f"\n=== {name}: chance the seat sees forced mate within 20 s, by the position it just left ===")
    rate(sub, "all decisions")
    print(" hypothetical drop mates (any piece, in hand or not):")
    rate([r for r in sub if not r["flag"]], "no piece would mate")
    for n in (1, 2, 3, 4, 5):
        rate([r for r in sub if r["n_types"] == n], f"{n} piece types would mate")
    rate([r for r in sub if r["flag"] and r["flag_cap_now"]], "...and that piece is capturable right now")
    print(" king:")
    for v in range(0, 5):
        rate([r for r in sub if r["off_home"] == v], f"king {v} ranks from home")
    rate([r for r in sub if r["off_home"] >= 5], "king 5+ ranks from home")
    for v in range(0, 4):
        rate([r for r in sub if r["shield"] == v], f"{v} pawns in front of king")
    for v in range(0, 6):
        rate([r for r in sub if r["escapes"] == v], f"{v} safe squares next to king")
    rate([r for r in sub if r["escapes"] >= 6], "6+ safe squares next to king")
    print(" within positions the seat itself rated -200 or better:")
    ok = [r for r in sub if r["cp"] is not None and r["cp"] >= -200]
    rate(ok, "all")
    rate([r for r in ok if not r["flag"]], "no piece would mate")
    rate([r for r in ok if r["flag"]], "some piece would mate")
    rate([r for r in ok if r["n_types"] >= 3], "3+ piece types would mate")
    rate([r for r in ok if r["flag_cap_now"]], "a mating piece capturable right now")
    rate([r for r in ok if r["escapes"] <= 1], "0-1 safe squares next to king")
    rate([r for r in ok if r["escapes"] >= 3], "3+ safe squares next to king")


for name in sorted({r["engine"] for r in rows}):
    table([r for r in rows if r["engine"] == name], name)

print("\n=== warning: of the seats that first saw forced mate and lost ===")
games = collections.defaultdict(list)
for r in rows:
    games[(r["game"], r["seat"])].append(r)
for name in sorted({r["engine"] for r in rows}):
    lead, n, flagged, free = [], 0, 0, []
    mated_flagged_any = 0
    for (g, s), rs in games.items():
        if rs[0]["engine"] != name or rs[0]["won"] or rs[0]["seen"] is None:
            continue
        n += 1
        fl = [r for r in rs if r["flag"]]
        # the last unbroken run of flagged decisions before the mate was seen
        k = len(rs)
        while k > 0 and rs[k - 1]["flag"]:
            k -= 1
        if k < len(rs):
            flagged += 1
            lead.append((rs[-1]["seen"] - rs[k]["t"]) / 1000)
        if fl:
            mated_flagged_any += 1
    print(f"{name}: {n} seats; flagged at the last decision before mate {flagged} ({100 * flagged / n:.0f}%); "
          f"flagged at any time {mated_flagged_any}; median unbroken warning {statistics.median(lead) if lead else None} s")
    won = [r for r in rows if r["engine"] == name and r["won"]]
    print(f"  false alarm base: decisions in won games with a flag: {sum(r['flag'] for r in won)}/{len(won)} "
          f"({100 * sum(r['flag'] for r in won) / len(won):.0f}%)")

print("\n=== does the attacker's partner bring the piece? captures by the opponent's partner within 10 s ===")
for name in sorted({r["engine"] for r in rows}):
    sub = [r for r in rows if r["engine"] == name]
    a = [r for r in sub if r["flag"]]
    b = [r for r in sub if not r["flag"]]
    print(f"{name}: any capture: flagged {100 * sum(r['any_cap10'] for r in a) / len(a):.1f}% vs unflagged "
          f"{100 * sum(r['any_cap10'] for r in b) / len(b):.1f}%; the mating type arrived {100 * sum(r['arrived10'] for r in a) / len(a):.1f}%")

print("\n=== at the last decision before the seat saw forced mate, losing seats ===")
for name in sorted({r["engine"] for r in rows}):
    last = []
    for (g, s), rs in games.items():
        if rs[0]["engine"] == name and not rs[0]["won"] and rs[0]["seen"] is not None:
            last.append(rs[-1])
    print(name, len(last))
    print("  ranks from home:", sorted(collections.Counter(min(r["off_home"], 5) for r in last).items()))
    print("  pawn shield:", sorted(collections.Counter(r["shield"] for r in last).items()))
    print("  safe squares:", sorted(collections.Counter(min(r["escapes"], 6) for r in last).items()))
    print("  in check after own move (impossible unless drop rules):", sum(r["in_check"] for r in last))
    print("  game time of first sight, s, quartiles:",
          [round(x / 1000) for x in statistics.quantiles([r["seen"] for r in last], n=4)])
    print("  attacker hand value, median:", statistics.median(r["opp_hand_val"] for r in last),
          "own hand value, median:", statistics.median(r["my_hand_val"] for r in last))
    print("  piece types that would mate: ", sorted(collections.Counter(r["n_types"] for r in last).items()))
