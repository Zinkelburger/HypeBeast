#!/usr/bin/env python3
"""Question 3 on the lost games: for the fall at each game's turning point, who could have seen it, and depth.

    nice -n 19 python3 losses_q3.py [MATCH]     (reads lost_<MATCH>.json from classify2.py and the cache)

For the falling seat's fall (S's, or P's in class d; for e/f/clock the mated seat S's fall):
  piece       the fatal piece (autopsy rule: lowest value of the move played in its world, then most valuable)
  seat_pre    at the decision before the fall: in no world / in a world where the move was mated / not mated /
              not scored
  seat_early  at a decision of the seat no later than the partner's decision that let the piece go, a world with
              that piece had the move played mated while "none" did not (alarm in time), or, for a non-mate fall,
              300+ cp worse than "none" (worth in time)
  partner     the capture was in the partner's own main line (pvfull) at that ply / elsewhere / not / sitting
  told        hb-plan only: the forecast group at the decision before the fall, and whether the partner's told
              line (the line added to the forecast) contained that piece going to the opponent
  depth       sudden mates: mate length (plies) at the first lost decision, against the depth of the world that held
              the piece at the decision before
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from common2 import MATE, PARTNER, by_seat, fm, load  # noqa: E402

MATCH = sys.argv[1] if len(sys.argv) > 1 else "plan-vs-l50"


def key_has(arrival, k):
    return k in arrival.replace("+", " +").replace("-", " -").split()


def main():
    data = load(MATCH)
    rbs = by_seat(data["rows"])
    L = json.load(open(os.path.join(HERE, f"lost_{MATCH}.json")))
    out = []
    for r in L:
        seat = r["fall_seat"] or r["S"]
        info = r[seat]
        c = info.get("fatal")
        kind = info.get("fall_kind")
        rec = {"game": r["game"], "loser": r["loser"], "cls": r["cls"], "seat": seat, "kind": kind,
               "pre_n": (info.get("pre") or {}).get("n"), "piece": c["k"] if c else None}
        rs = rbs[(r["game"], seat)]
        pre = info.get("pre")
        if not c or c["k"][0] != "-" or not pre:
            rec["who"] = "no arrival to the opponent" if pre else "no decision before"
            out.append(rec)
            continue
        rec["world_p"] = c.get("world_p")
        v = c.get("v_chosen")
        rec["seat_pre"] = ("in no world" if c.get("world") is None else "move not scored" if v is None
                           else "move mated" if v <= -MATE else "move not mated")
        pv = c.get("partner") or {}
        rec["partner"] = pv.get("known")
        rec["partner_score"] = pv.get("score")
        pn = pv.get("n")
        sudden = kind in ("a", "a2", "a3", "b", "c2")
        rec["sudden"] = sudden
        early = None
        if pn is not None:
            # the seat's last two decisions at or before the partner's decision (and not after the turning point)
            for x in [x for x in rs if x["n"] <= min(pn, pre["n"])][-2:]:
                none = next((w for w in x["worlds"] if w["arrival"] == "none"), None)
                nv = none["v_chosen"] if none else None
                for w in x["worlds"]:
                    if not key_has(w["arrival"], c["k"]) or w["v_chosen"] is None:
                        continue
                    if w["v_chosen"] <= -MATE and (nv is None or nv > -MATE):
                        early = (x["n"], "mate")
                        break
                    if not sudden and nv is not None and nv > -MATE and w["v_chosen"] > -MATE and nv - w["v_chosen"] >= 300:
                        early = early or (x["n"], "worth")
                if early and early[1] == "mate":
                    break
        rec["seat_early"] = early
        # could the seat itself have dodged? the best candidate against the move played in the fatal world at pre
        vb = c.get("v_best")
        rec["escape_gain"] = (max(min(vb, 2000), -2000) - max(min(v, 2000), -2000)) if (vb is not None and v is not None) else None
        if early or rec["seat_pre"] == "move mated":
            rec["who"] = "seat's worlds"
        elif rec["partner"] in ("in its line", "in its line later/elsewhere"):
            rec["who"] = "partner's line only"
        else:
            rec["who"] = "nobody"
        if r["loser"] == "hb-plan":
            rec["talk"] = pre.get("talk")
            t = pre.get("told") or {}
            rec["told_has_piece"] = any(cc.endswith(c["k"]) for cc in t.get("caps", [])) if t else None
        if sudden:
            ms = info.get("bad_score")
            rec["mate_plies"] = 100000 + ms if ms is not None and ms <= -MATE else None
            wd = [w[4] for w in pre["worlds"] if key_has(w[0], c["k"]) and w[4] and w[4] < 100]
            rec["world_depth"] = max(wd) if wd else None
            if rec["seat_pre"] == "move mated":
                rec["depth"] = "seen (depth enough)"
            elif rec["seat_pre"] == "in no world":
                rec["depth"] = "forecast miss: no depth helps the seat"
            elif rec["seat_pre"] == "move not scored":
                rec["depth"] = "not scored"
            else:
                rec["depth"] = ("beyond the world depth" if rec["mate_plies"] and rec["world_depth"] and rec["mate_plies"] + 2 > rec["world_depth"]
                                else "within the world depth")
        out.append(rec)
    json.dump(out, open(os.path.join(HERE, f"q3_{MATCH}.json"), "w"), indent=1, default=str)
    for e in sorted({x["loser"] for x in out}):
        xe = [x for x in out if x["loser"] == e]
        print(f"\n## {e}: {len(xe)} lost games")
        for grp, sel in (("sudden mates", [x for x in xe if x.get("sudden")]),
                         ("drops (a4/b2/c/g/h with an arrival, not sudden)", [x for x in xe if x.get("sudden") is False]),
                         ("no arrival", [x for x in xe if x.get("sudden") is None])):
            print(f"  {grp}: {len(sel)}")
            eg = [x["escape_gain"] for x in sel if x.get("escape_gain") is not None]
            if eg:
                print(f"     escape gain (best candidate minus move played in the fatal world at pre): >=200 in {sum(e >= 200 for e in eg)} of {len(eg)}, median {sorted(eg)[len(eg) // 2]}")
            for k in ("who", "seat_pre", "partner", "depth", "talk", "told_has_piece"):
                cnt = collections.Counter(x.get(k) for x in sel if k in x)
                if cnt:
                    print(f"     {k}: {dict(cnt)}")
            if grp != "no arrival":
                print("     pieces:", dict(collections.Counter(x["piece"] for x in sel)))
                pa = collections.Counter("ahead" if (x.get("partner_score") or 0) > 300 else "behind" if (x.get("partner_score") or 0) < -300 else "level" for x in sel)
                print("     partner score at its decision:", dict(pa))
        for x in sorted(xe, key=lambda x: x["game"]):
            print(f"    g{x['game']} {x['cls']} {x['seat']} n={x.get('pre_n')} {x.get('kind')} {x.get('piece')} p={x.get('world_p')} "
                  f"pre={x.get('seat_pre')} early={x.get('seat_early')} partner={x.get('partner')}({fm(x.get('partner_score'))}) "
                  f"who={x['who']} esc={x.get('escape_gain')} talk={x.get('talk')} told_has={x.get('told_has_piece')} mate={x.get('mate_plies')} wdepth={x.get('world_depth')}")


if __name__ == "__main__":
    main()
