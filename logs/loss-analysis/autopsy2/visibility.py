#!/usr/bin/env python3
"""Sudden collapses (every decision, both engines): who could have seen the mate, and was it depth?

    nice -n 19 python3 visibility.py [MATCH]    -> collapses_<MATCH>.json, prints tables

A collapse: a decision at -300 cp or better whose seat's NEXT decision is a forced mate against it.
For each, the pieces that reached the opponent's hand before that next decision ("fatal": the most valuable),
and:
  seat_pre    what the seat's own worlds said at the decision: fatal piece in no world / in a world where the
              move played was mated / not mated / not scored
  seat_early  the seat's worlds had the move played mated with that piece, while "none" was not, at a decision
              no later than the partner's decision that let it go (AUTOPSY's alarm-in-time test)
  partner     the partner's last decision before the capture: the capture was in its main line at that ply
              (pvfull), elsewhere in its line, not in its line, or the partner was sitting
  who         seat (seat_early or seat_pre mated) > partner (in its line) > nobody
  depth       mate length at the next decision (plies), against the depth of the world that held the piece
              (when one did) and the main depth at the decision
Also a per-game, per-side count with a game-resampled interval.
"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "autopsy"))
from common2 import MATE, PARTNER, by_seat, fm, load  # noqa: E402
import timeline as TL  # noqa: E402

MATCH = sys.argv[1] if len(sys.argv) > 1 else "plan-vs-l50"
random.seed(7)


def key_has(arrival, k):
    return k in arrival.replace("+", " +").replace("-", " -").split()


def analyse(data):
    games = {g["game"]: g for g in data["games"]}
    rows = data["rows"]
    rbs = by_seat(rows)
    out = []
    for (gid, seat), rs in rbs.items():
        g = games[gid]
        for i, r in enumerate(rs[:-1]):
            nx = rs[i + 1]
            if r["score"] is None or nx["score"] is None or r["score"] <= -300 or nx["score"] > -MATE:
                continue
            got = TL.captures_to(g, seat, r["n"], nx["n"])
            neg = [c for c in got if c["k"][0] == "-"]
            rec = {"game": gid, "seat": seat, "engine": r["engine"], "n": r["n"], "next_n": nx["n"], "score": r["score"],
                   "next_score": nx["score"], "mate_plies": 100000 + nx["score"], "won": r["won"], "talk": r.get("talk"),
                   "main_depth": r["depth"], "decision": r["decision"], "main": r["main"], "reason": r["reason"],
                   "override": r["override"], "fatal": None}
            if not neg:
                rec["seat_pre"] = "nothing arrived"
                rec["who"] = "nobody (nothing arrived)"
                out.append(rec)
                continue
            c = max(neg, key=lambda c: "PNBRQ".index(c["k"][1]))
            rec["fatal"] = c["k"]
            ws = [w for w in r["worlds"] if key_has(w["arrival"], c["k"])]
            if not ws:
                rec["seat_pre"] = "in no world"
                rec["world_p"] = 0
            else:
                w = min(ws, key=lambda w: w["v_chosen"] if w["v_chosen"] is not None else 10 ** 7)
                rec["world_p"] = max(x["p"] for x in ws)
                rec["world_depth"] = w.get("depth")
                if w["v_chosen"] is None:
                    rec["seat_pre"] = "in a world, move not scored"
                elif w["v_chosen"] <= -MATE:
                    rec["seat_pre"] = "in a world, move mated"
                    rec["escape_pre"] = w["v_best"] is not None and w["v_best"] > -MATE
                else:
                    rec["seat_pre"] = "in a world, move not mated"
                    rec["world_v"] = w["v_chosen"]
            pv = TL.partner_view(g, rbs[(gid, PARTNER[seat])], c)
            rec["partner"] = pv.get("known")
            rec["partner_score"] = pv.get("score")
            rec["partner_n"] = pv.get("n")
            rec["partner_plies_after"] = pv.get("plies_after")
            # seat_early: the seat's decisions at or before the partner's decision
            early = None
            if pv.get("n") is not None:
                for x in rs:
                    if x["n"] > pv["n"] or x["n"] > r["n"]:
                        break
                    none = next((w for w in x["worlds"] if w["arrival"] == "none"), None)
                    for w in x["worlds"]:
                        if key_has(w["arrival"], c["k"]) and w["v_chosen"] is not None and w["v_chosen"] <= -MATE \
                                and (none is None or none["v_chosen"] is None or none["v_chosen"] > -MATE):
                            early = x["n"]
                            break
            rec["seat_early"] = early
            if early is not None or rec["seat_pre"] == "in a world, move mated":
                rec["who"] = "seat's worlds"
            elif rec["partner"] in ("in its line", "in its line later/elsewhere"):
                rec["who"] = "partner's line only"
            else:
                rec["who"] = "nobody"
            out.append(rec)
    return out


def depth_class(x):
    sp = x.get("seat_pre")
    if sp == "nothing arrived":
        return "main search missed a mate with nothing arriving: " + ("beyond main depth" if x["mate_plies"] + 2 > x["main_depth"] else "within main depth")
    if sp == "in no world":
        return "forecast miss (piece in no world): no depth of the seat's own search helps"
    if sp == "in a world, move mated":
        return "seen: the world search had the mate (depth was enough)"
    if sp == "in a world, move not scored":
        return "in a world but the move was not scored there"
    d = x.get("world_depth") or 0
    return "world search scored it survivable: " + ("mate longer than the world depth (more depth could find it)"
                                                    if x["mate_plies"] + 2 > d else "mate within the world depth (not depth: timing/assumption)")


def boot_rate(xs, games, B=2000):
    """xs: per-game counts dict; returns mean per game and 95% CI by game resampling"""
    gl = sorted(games)
    m = sum(xs.get(g, 0) for g in gl) / len(gl)
    bs = []
    for _ in range(B):
        s = random.choices(gl, k=len(gl))
        bs.append(sum(xs.get(g, 0) for g in s) / len(s))
    bs.sort()
    return m, bs[int(.025 * B)], bs[int(.975 * B) - 1]


def main():
    data = load(MATCH)
    C = analyse(data)
    for x in C:
        x["depth_class"] = depth_class(x)
    json.dump(C, open(os.path.join(HERE, f"collapses_{MATCH}.json"), "w"), indent=1, default=str)
    engines = sorted({x["engine"] for x in C} | {r["engine"] for r in data["rows"]})
    games = {g["game"] for g in data["games"]}
    print(f"{MATCH}: {len(games)} games, {len(C)} collapses")
    for e in engines:
        xe = [x for x in C if x["engine"] == e]
        per = collections.Counter(x["game"] for x in xe)
        m, lo, hi = boot_rate(per, games)
        lost = [x for x in xe if x["won"] == 0]
        print(f"\n## {e}: {len(xe)} collapses in {len(per)} games ({m:.2f} per game, 95% {lo:.2f}-{hi:.2f}); in lost games {len(lost)}")
        for k, v in collections.Counter(x["seat_pre"] for x in xe).most_common():
            print(f"   seat_pre: {k}: {v}")
        for k, v in collections.Counter(x["who"] for x in xe).most_common():
            print(f"   who could see it: {k}: {v}")
        for k, v in collections.Counter(x["partner"] for x in xe if x["fatal"]).most_common():
            print(f"   partner: {k}: {v}")
        for k, v in collections.Counter(x["depth_class"] for x in xe).most_common():
            print(f"   depth: {k}: {v}")
        print("   fatal pieces:", dict(collections.Counter(x["fatal"] for x in xe)))
        ms = sorted(x["mate_plies"] for x in xe)
        if ms:
            print(f"   mate length at the next decision (plies): median {ms[len(ms) // 2]}, range {ms[0]}-{ms[-1]}")
        esc = sum(1 for x in xe if x.get("escape_pre"))
        print(f"   a candidate survived the fatal world at the decision: {esc} of {sum(1 for x in xe if x['seat_pre'] == 'in a world, move mated')}")
        if e == "hb-plan":
            for k, v in collections.Counter(x["talk"] for x in xe).most_common():
                print(f"   talk at the collapse decision: {k}: {v}")
        for x in sorted(xe, key=lambda x: (x["game"], x["n"])):
            print(f"     g{x['game']} {x['seat']} n={x['n']} {fm(x['score'])}->{fm(x['next_score'])} {x['fatal']} "
                  f"seat_pre={x['seat_pre']} p={x.get('world_p', '-')} early={x.get('seat_early')} partner={x.get('partner')} "
                  f"({fm(x.get('partner_score'))}) who={x['who']} won={x['won']} talk={x['talk']}")


if __name__ == "__main__":
    main()
