#!/usr/bin/env python3
"""Per-class details from timeline.json, classes.json and the cache: what the seat knew, how far back, the partner.

For the mated seat's fall into lost-for-good (classes a, a2, a3, a4, b, b2 by s_kind):
  - the fatal piece, its world at the decision before (p, v_chosen, v_best), the seat's E
  - walking back up to 6 own decisions: the first decision where a world holding that piece type had the
    chosen move at <= -90000 ('first fatal sight'), and whether at that decision some candidate was not mated there
  - the partner's last decision before the capture: sitting, the capture in its line, its score, taken back
  - the seat's own sitting between the two decisions and its clock
For class d: the partner's fall, and what flowed.
For class f and w: the decisions.
"""
import collections
import json
import os

from common import HERE, MATE, PARTNER, load


def key_has(arrival, k):
    return k in arrival.replace("+", " +").replace("-", " -").split()


def main():
    data = load()
    T = {(r["match"], r["game"]): r for r in json.load(open(os.path.join(HERE, "timeline.json")))}
    C = json.load(open(os.path.join(HERE, "classes.json")))
    rows = collections.defaultdict(list)
    for m in data:
        for r in data[m]["rows"]:
            rows[(m, r["game"], r["seat"])].append(r)
    for k in rows:
        rows[k].sort(key=lambda r: (r["n"], r["t"]))
    out = []
    for c in C:
        t = T[(c["match"], c["game"])]
        S, P = t["S"], t["P"]
        s = t[S]
        rs = rows[(c["match"], c["game"], S)]
        rec = {"match": c["match"], "game": c["game"], "cls": c["cls"], "s_kind": c["s_kind"], "S": S}
        f = c.get("fatal")
        if f and s.get("pre"):
            pre_n = s["pre"]["n"]
            k = f["k"]
            back = [r for r in rs if r["n"] <= pre_n][-6:]
            sight = []
            for r in back:
                ws = [w for w in r["worlds"] if key_has(w["arrival"], k)]
                if ws:
                    w = max(ws, key=lambda w: w["p"])
                    sight.append({"n": r["n"], "p": round(w["p"], 3), "v_chosen": w["v_chosen"], "v_best": w["v_best"],
                                  "score": r["score"], "decision": r["decision"], "reason": r["reason"]})
                else:
                    sight.append({"n": r["n"], "p": 0, "score": r["score"], "decision": r["decision"], "reason": r["reason"]})
            first_fatal = next((x for x in sight if x.get("v_chosen") is not None and x["v_chosen"] <= -MATE), None)
            first_escape = next((x for x in sight if x.get("v_chosen") is not None and x["v_chosen"] <= -MATE
                                 and x.get("v_best") is not None and x["v_best"] > -MATE), None)
            rec.update({"piece": k, "p_pre": f.get("world_p"), "v_chosen_pre": f.get("v_chosen"), "v_best_pre": f.get("v_best"),
                        "pre_score": s.get("pre_bad_score"), "bad_score": s.get("bad_score"),
                        "pre_decision": s["pre"]["decision"], "pre_main": s["pre"]["main"], "pre_reason": s["pre"]["reason"],
                        "E_pre": s["pre"]["E_chosen"], "sight": sight,
                        "first_fatal_n": first_fatal["n"] if first_fatal else None,
                        "decisions_before_fatal_seen": (len([x for x in sight if x["n"] >= first_fatal["n"]]) if first_fatal else 0),
                        "escape_seen_n": first_escape["n"] if first_escape else None,
                        "partner": f.get("partner"), "taken_back": f.get("taken_back"),
                        "pre_clocks": s["pre"]["clocks"], "pre_tadv": s["pre"]["tadv"],
                        "sat_between": s.get("passes_pre_to_bad"), "bad_n": s.get("bad_n"), "pre_n": pre_n,
                        "capture_idx": f["idx"], "capture_uci": f["uci"]})
        rec["S_passes"] = s["passes"]
        rec["S_pass_reasons"] = s["pass_reasons"]
        rec["clocks_end"] = t["clocks_end"]
        rec["own_first_mate_n"] = t["own_first_mate_n"]
        rec["own_mate_at_end"] = t["own_mate_at_end"]
        rec["P_bad_n"] = t[P]["bad_n"]
        rec["S_bad_n"] = s["bad_n"]
        rec["P_last"] = t[P].get("last")
        rec["missed"] = [x for x in t["missed"] if x.get("legal") and not x.get("made")]
        out.append(rec)
    json.dump(out, open(os.path.join(HERE, "detail.json"), "w"), indent=1, default=str)

    def fm(v):
        return "?" if v is None else "M-" if v <= -MATE else "M+" if v >= MATE else str(v)

    # ---- the fall of the mated seat after an arrival (a*, b*)
    for kinds, title in ((("a", "a2", "a3", "b"), "sudden mates"), (("a4", "b2"), "decisive drops")):
        sel = [x for x in out if x["s_kind"] in kinds and "piece" in x]
        print(f"\n## {title} (by the mated seat's own fall, whatever came first): {len(sel)}")
        print("match game cls kind piece p_pre v_ch/v_best pre->bad E_pre decision(main) first_fatal_back escape partner(known, score) back sat clockS")
        for x in sel:
            pv = x.get("partner") or {}
            seat_i = ["Awhite", "Ablack", "Bwhite", "Bblack"].index(x["S"])
            clk = x["pre_clocks"][seat_i] if x["pre_clocks"] else None
            print(f"{x['match'][:7]} {x['game']:>2} {x['cls']:3} {x['s_kind']:3} {x['piece']} {x['p_pre']} {fm(x['v_chosen_pre'])}/{fm(x['v_best_pre'])} "
                  f"{fm(x['pre_score'])}->{fm(x['bad_score'])} E={x['E_pre']} {x['pre_decision']}({x['pre_main']},{x['pre_reason']}) "
                  f"fatal_seen_decisions={x['decisions_before_fatal_seen']} escape@{x['escape_seen_n']} "
                  f"partner=({pv.get('known')},{fm(pv.get('score'))},{pv.get('reason')}) back={x['taken_back']} sat={x['sat_between']} clk={clk}")
        # summaries
        known = collections.Counter((x.get("partner") or {}).get("known") for x in sel)
        pscore = collections.Counter(("ahead" if (x.get("partner") or {}).get("score", 0) is not None and ((x.get("partner") or {}).get("score") or 0) > 300
                                      else "behind" if ((x.get("partner") or {}).get("score") or 0) < -300 else "level") for x in sel)
        pieces = collections.Counter(x["piece"] for x in sel)
        traded = sum(1 for x in sel if x.get("taken_back"))
        esc = sum(1 for x in sel if x.get("escape_seen_n") is not None)
        fatal_earlier = sum(1 for x in sel if x.get("decisions_before_fatal_seen", 0) >= 2)
        print(f"pieces {dict(pieces)}; partner {dict(known)}; partner score {dict(pscore)}; our side took a piece on that board the ply before or after: {traded}; "
              f"a decision (within 6 back) where that world was fatal for the chosen move but some candidate escaped: {esc}; "
              f"fatal seen at 2+ decisions: {fatal_earlier}")




def alarm_timing():
    """For every fall after an arrival: did the mated seat's world searches mark that piece fatal (or say what it
    costs) at a decision BEFORE the partner's decision that let it go? That is when a message could have helped."""
    X = json.load(open(os.path.join(HERE, "detail.json")))
    data = load()
    rows = collections.defaultdict(list)
    for m in data:
        for r in data[m]["rows"]:
            rows[(m, r["game"], r["seat"])].append(r)
    res = collections.Counter()
    lines = []
    for x in X:
        if "piece" not in x or x["s_kind"] not in ("a", "a2", "a3", "b", "a4", "b2"):
            continue
        pv = x.get("partner") or {}
        pn = pv.get("n")
        if pn is None:
            continue
        rs = sorted(rows[(x["match"], x["game"], x["S"])], key=lambda r: (r["n"], r["t"]))
        before = [r for r in rs if r["n"] <= pn]
        told = None
        for r in reversed(before[-1:]):   # the seat's last decision before the partner's: what a message would carry
            ws = [w for w in r["worlds"] if key_has(w["arrival"], x["piece"])]
            none = next((w for w in r["worlds"] if w["arrival"] == "none"), None)
            if ws:
                w = min(ws, key=lambda w: w["v_chosen"] if w["v_chosen"] is not None else 10 ** 6)
                told = {"n": r["n"], "p": w["p"], "v": w["v_chosen"], "none": none["v_chosen"] if none else None}
        if told is None:
            tag = "no world with that piece at the seat's last decision before the partner's"
        elif told["v"] is None:
            tag = "a world, move not scored"
        elif told["v"] <= -MATE and (told["none"] is None or told["none"] > -MATE):
            tag = "marked fatal (alarm '-T=#') before the partner's decision"
        elif told["v"] <= -MATE:
            tag = "already mated without the piece"
        else:
            cost = (told["none"] - told["v"]) if told["none"] is not None else None
            tag = f"not fatal; worth said {'>=' if cost is not None and cost >= 300 else '<'}300 cp"
        grp = "sudden" if x["s_kind"] in ("a", "a2", "a3", "b") else "drop"
        res[(grp, tag, pv.get("known"))] += 1
        lines.append((x["match"][:7], x["game"], x["cls"], x["s_kind"], x["piece"], tag, pv.get("known"), told))
    print("\n## What a message from the mated seat could have said before the partner's decision that let the piece go")
    for k, v in sorted(res.items()):
        print(f"  {k[0]:6} | {k[1]:75} | partner: {k[2]:28} | {v}")
    for l in lines:
        print("   ", l)


if __name__ == "__main__":
    main()
    alarm_timing()
