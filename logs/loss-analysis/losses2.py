#!/usr/bin/env python3
"""Second pass: eval collapses with base rates, the turning point, thrown wins.

usage: losses2.py MATCH_DIR
"""
import collections
import json
import statistics
import sys

from losses import NAMES, TEAM, Replay, bad, cp, good, pocket, seat_of

ORDER = ["A-white", "A-black", "B-white", "B-black"]


def timeline_of(r):
    rp = Replay(r["opening"]["dual_fen"])
    for m in r["opening"]["moves"]:
        rp.push("A" if m[0] == "1" else "B", m[1:])
    tl = []
    for e in r["result"]["events"]:
        rec = dict(e)
        if e["kind"] == "move":
            rec.update(rp.push(e["board"], e["uci"]))
            rec["mated_now"] = rp.b[e["board"]].is_checkmate()
        rec["hands"] = {bd: {c: pocket(rp.b[bd], c) for c in (True, False)} for bd in "AB"}
        tl.append(rec)
    return tl


def value(hand):
    return hand[1] * 1 + hand[2] * 3 + hand[3] * 3 + hand[4] * 5 + hand[5] * 9


def steps(tl, seat):
    """Consecutive evaluated decisions of a seat, with what changed between them."""
    bd = seat[0]
    white = seat.endswith("white")
    opp_color = not white
    dec = [(i, t) for i, t in enumerate(tl)
           if t.get("seat") == seat and t["kind"] in ("move", "sit") and t.get("eval") is not None]
    out = []
    for (i, a), (j, b) in zip(dec, dec[1:]):
        # hand the opponent held when this seat decided at a, and at b
        h0 = tl[i]["hands"][bd][opp_color]
        h1 = tl[j]["hands"][bd][opp_color]
        between = tl[i + 1:j]
        opp_moves = [t for t in between if t["kind"] == "move" and t["board"] == bd]
        dropped = [t for t in opp_moves if t.get("drop")]
        # pieces that reached the opponent's hand in the window: hand after, plus drops, minus hand before
        arrived = {p: h1[p] - h0[p] + sum(1 for t in dropped if t["drop"] == p) for p in NAMES}
        out.append({"a": cp(a["eval"]), "b": cp(b["eval"]), "t0": a["t"], "t1": b["t"],
                    "move": a.get("uci"), "kind": a["kind"], "arrived": sum(1 for p in NAMES if arrived[p] > 0),
                    "arrived_value": sum(arrived[p] * {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}[p] for p in NAMES),
                    "opp_replies": [t["uci"] for t in opp_moves], "mate_b": b["eval"].get("mate")})
    return out


def pct(n, d):
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "0/0"


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def main():
    d = sys.argv[1]
    rs = [json.loads(l) for l in open(f"{d}/results.jsonl")]
    stats = collections.defaultdict(lambda: collections.defaultdict(list))
    thrown = []
    for r in rs:
        res = r["result"]
        tl = timeline_of(r)
        winner = res["winner"]
        for team, seats in TEAM.items():
            eng = r["seats"][seats[0]]
            won = team == winner
            for seat in seats:
                for s in steps(tl, seat):
                    s["game"] = r["game"]
                    s["seat"] = seat
                    stats[eng]["won" if won else "lost"].append(s)
        # thrown wins: the losing team's seat claimed mate
        lt = "black" if winner == "white" else "white"
        for seat in TEAM[lt]:
            ev = [t for t in tl if t.get("seat") == seat and t.get("eval") is not None]
            k = len(ev)
            while k > 0 and good(ev[k - 1]["eval"]):
                k -= 1
            if k < len(ev):
                # the claim stood until this seat's last decision
                first = ev[k]
                c = dict(zip(ORDER, tl[-1]["clocks"]))
                thrown.append({"game": r["game"], "loser": r["seats"][seat], "seat": seat,
                               "claim_t": first["t"], "mate": first["eval"]["mate"],
                               "last_mate": ev[-1]["eval"]["mate"], "last_kind": ev[-1]["kind"],
                               "last_t": ev[-1]["t"], "end_t": res["duration_ms"], "termination": res["termination"],
                               "clocks": tl[-1]["clocks"]})
    for eng, by in sorted(stats.items()):
        print(f"\n=== {eng} ===")
        for outcome, ss in sorted(by.items()):
            print(f"-- in games it {outcome}: {len(ss)} decision pairs")
            arr = sum(1 for s in ss if s["arrived"])
            print("   a piece reached the opponent's hand in the window:", pct(arr, len(ss)))
            big = [s for s in ss if s["a"] >= -300 and s["b"] <= s["a"] - 500]
            print("   collapses (from >= -300, fell by 500+):", pct(len(big), len(ss)))
            print("     with a piece arriving:", pct(sum(1 for s in big if s["arrived"]), len(big)))
            print("     with no new piece (same information):", pct(sum(1 for s in big if not s["arrived"]), len(big)))
            print("     into a forced mate:", pct(sum(1 for s in big if s["mate_b"] is not None and s["mate_b"] < 0), len(big)))
            noarr = [s for s in ss if not s["arrived"] and s["a"] >= -300]
            yesarr = [s for s in ss if s["arrived"] and s["a"] >= -300]
            print("   rate of collapse given no arrival:", pct(sum(1 for s in noarr if s["b"] <= s["a"] - 500), len(noarr)))
            print("   rate of collapse given arrival:   ", pct(sum(1 for s in yesarr if s["b"] <= s["a"] - 500), len(yesarr)))
    print("\n=== forced mate still claimed by a seat of the losing team at its last decision ===")
    for t in thrown:
        print(t)
    print("\ncount by loser:", collections.Counter(t["loser"] for t in thrown))


main()
