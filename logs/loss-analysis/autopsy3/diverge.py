#!/usr/bin/env python3
"""Job 3 of the night of 2026-11-11: two matches with the same baseline on the same openings play identical games
until the first decision where their contenders differ. For each opening pair and colour: that decision, what was
active there on each side, and the two results. Logs only.

    nice -n 19 python3 diverge.py MATCH_A MATCH_B [--out NAME]   -> diverge_<A>_vs_<B>.md and .json

Games are matched by (pair, contender_team) and must have the same opening. The parting decision is the earliest
decision of a contender seat (by plies played) whose move, or whether it sat, differs between A and B. Fields shown
for each side there: guard (types probed, "low" = the partner's board below the floor, nothing probed), price_mates
(mate prices set), the 1500 entries of hb_prices (theirs: losing our T mates the partner; ours: taking a T mates for
the partner), rescue, partner_held, the reason, main move and decision, main score, main nodes.

The parting move is not always where the engines first behaved differently: a probe made by one side only, with
the same move played, already changes its hash and its kept price table. So two more things are recorded per game:
  first difference - the earliest contender decision (same position on both sides) whose logged guard or
                     price_mates differ, and how ("A probed, B did not", ...)
  mate price before - a mate price on either side at any contender decision before the parting one

Cause, first that applies:
  mate price here    - either side had a mate price set at the parting decision (price_mates >= 1)
  mate price earlier - none there, but one was set on either side at an earlier decision of the game
  no mate price      - none at or before the parting decision; split by what differed at the parting decision:
                       "probe here" (one side probed, the other did not), "both probed" (same or different types),
                       "neither probed" (the search differed through earlier state: hash, kept table)
  baseline/timing    - no contender decision differs before the games part (the baseline or the timing differed)
rescue= or partner_held= at the parting decision is reported beside the cause.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common3 as c3  # noqa: E402

SITS = {"hold_partner", "hold_feed", "stall_deny", "voluntary_wait", "hold_mated", "mated_play_on"}


def key_of(g):
    return (g["pair"], g["contender_team"])


def sat(r):
    return r["reason"] in SITS


def info(r):
    s = r.get("sumd") or {}
    pr = r.get("prices") or {}
    mates = {"theirs": [t for t, v in (pr.get("theirs") or {}).items() if v >= 1500],
             "ours": [t for t, v in (pr.get("ours") or {}).items() if v >= 1500]}
    return {"seat": r["seat"], "n": r["n"], "decision": r["decision"], "main": r["main"], "reason": r["reason"],
            "sat": sat(r), "score": r["score"], "guard": s.get("guard"), "price_mates": int(s.get("price_mates", 0) or 0),
            "mate_prices": mates, "rescue": s.get("rescue"), "partner_held": s.get("partner_held"),
            "main_nodes": r.get("main_nodes"), "override": r["override"], "prices_on": s.get("prices") == "1"}


def contender_rows(data):
    out = collections.defaultdict(list)
    names = {}
    for g in data["games"]:
        names[g["game"]] = g["names"]["contender"]
    for r in data["rows"]:
        if r["engine"] == names[r["game"]]:
            out[r["game"]].append(r)
    for k in out:
        out[k].sort(key=lambda r: (r["n"], r["t"], r["seat"]))
    return out


def probed(x):
    """guard=<types>, or (engines without the guard, e.g. matekeep) prices=1: the price probes ran"""
    if x["guard"] is not None:
        return x["guard"] != "low"
    return x.get("prices_on", False)


def part(gA, gB, rA, rB):
    ta, tb = gA["toks"], gB["toks"]
    i = next((k for k in range(min(len(ta), len(tb))) if ta[k] != tb[k]), None)
    identical = i is None and len(ta) == len(tb)
    if i is None:
        i = min(len(ta), len(tb))
    best, first_diff = None, None
    for seat in {r["seat"] for r in rA} | {r["seat"] for r in rB}:
        sa = [r for r in rA if r["seat"] == seat]
        sb = [r for r in rB if r["seat"] == seat]
        for j in range(min(len(sa), len(sb))):
            a, b = sa[j], sb[j]
            if a["n"] != b["n"]:
                break
            ia, ib = info(a), info(b)
            if (probed(ia) != probed(ib) or ia["price_mates"] != ib["price_mates"]) and (first_diff is None or a["n"] < first_diff["n"]):
                how = ("A probed, B did not" if probed(ia) and not probed(ib) else "B probed, A did not" if probed(ib) and not probed(ia)
                       else "mate prices differ")
                first_diff = {"n": a["n"], "seat": seat, "how": how}
            if a["decision"] != b["decision"] or sat(a) != sat(b):
                if best is None or a["n"] < best[0]["n"]:
                    best = (a, b)
                break
    if identical:
        return {"identical": True, "first_diff": first_diff}
    if best is None or best[0]["n"] > i:
        return {"identical": False, "ply": i, "cause": "baseline/timing", "a": None, "b": None, "first_diff": first_diff,
                "mate_before": None}
    a, b = info(best[0]), info(best[1])
    n0 = best[0]["n"]
    earlier = any(int((r.get("sumd") or {}).get("price_mates", 0) or 0) > 0 for r in rA + rB if r["n"] < n0)
    if a["price_mates"] or b["price_mates"]:
        cause = "mate price here"
    elif earlier:
        cause = "mate price earlier"
    elif probed(a) != probed(b):
        cause = "no mate price: probe here"
    elif probed(a) and probed(b):
        cause = "no mate price: both probed"
    else:
        cause = "no mate price: neither probed"
    return {"identical": False, "ply": i, "cause": cause, "a": a, "b": b, "first_diff": first_diff, "mate_before": earlier,
            "rescue": bool(a["rescue"] or b["rescue"] or a["partner_held"] or b["partner_held"])}


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    A, B = args[0], args[1]
    dA, dB = c3.load(A), c3.load(B)
    gA = {key_of(g): g for g in dA["games"]}
    gB = {key_of(g): g for g in dB["games"]}
    rA, rB = contender_rows(dA), contender_rows(dB)
    nameA = dA["games"][0]["names"]["contender"]
    nameB = dB["games"][0]["names"]["contender"]
    recs = []
    for k in sorted(set(gA) & set(gB)):
        a, b = gA[k], gB[k]
        if a["toks"][:8] != b["toks"][:8]:
            recs.append({"pair": k[0], "team": k[1], "error": "different opening"})
            continue
        p = part(a, b, rA.get(a["game"], []), rB.get(b["game"], []))
        sa = 1.0 if a["winner"] == k[1] else 0.0 if a["winner"] in ("white", "black") else 0.5
        sb = 1.0 if b["winner"] == k[1] else 0.0 if b["winner"] in ("white", "black") else 0.5
        p.update({"pair": k[0], "team": k[1], "game_a": a["game"], "game_b": b["game"], "score_a": sa, "score_b": sb})
        recs.append(p)
    tag = f"{A}_vs_{B}"
    json.dump(recs, open(os.path.join(HERE, f"diverge_{tag}.json"), "w"))
    ok = [r for r in recs if "error" not in r]
    out = [f"# Where {A} ({nameA}) and {B} ({nameB}) part", ""]
    out.append(f"Games matched by opening pair and colour: {len(ok)} (only in {A}: {len(set(gA) - set(gB))}, only in {B}: "
               f"{len(set(gB) - set(gA))}, opening mismatch: {len(recs) - len(ok)}).")
    ident = [r for r in ok if r["identical"]]
    out.append(f"Identical games: {len(ident)}. Score of {nameA} {sum(r['score_a'] for r in ok):g}, of {nameB} {sum(r['score_b'] for r in ok):g} "
               f"(out of {len(ok)}).")
    out.append("")
    flips = [r for r in ok if r["score_a"] != r["score_b"]]
    out.append(f"Results that differ: {len(flips)}; {nameA} better in {sum(r['score_a'] > r['score_b'] for r in flips)}, "
               f"{nameB} better in {sum(r['score_b'] > r['score_a'] for r in flips)}.")
    out.append("")
    out.append(f"| cause at the parting decision | games | results differ | {nameA} better | {nameB} better | ply parted (median) |")
    out.append("|---|---|---|---|---|---|")
    for cause in ("mate price here", "mate price earlier", "no mate price: probe here", "no mate price: both probed",
                  "no mate price: neither probed", "baseline/timing"):
        s = [r for r in ok if not r["identical"] and r["cause"] == cause]
        if not s:
            continue
        f = [r for r in s if r["score_a"] != r["score_b"]]
        pl = sorted(r["ply"] for r in s)
        out.append(f"| {cause} | {len(s)} | {len(f)} | {sum(r['score_a'] > r['score_b'] for r in f)} | "
                   f"{sum(r['score_b'] > r['score_a'] for r in f)} | {pl[len(pl) // 2]} |")
    out.append("")
    # mate price: which side had it
    mp = [r for r in ok if not r["identical"] and r["cause"] == "mate price here"]
    if mp:
        out.append(f"Mate price at the parting decision: on {nameA}'s side {sum(r['a']['price_mates'] > 0 for r in mp)}, "
                   f"on {nameB}'s side {sum(r['b']['price_mates'] > 0 for r in mp)}.")
        out.append("")
    # guard state on each side at the parting decision
    for side, nm in (("a", nameA), ("b", nameB)):
        c = collections.Counter()
        for r in ok:
            if r["identical"] or r[side] is None:
                continue
            gv = r[side]["guard"]
            c[("no guard; price probes ran" if r[side].get("prices_on") else "no guard, no price probes") if gv is None
              else "low (below the floor)" if gv == "low" else "probed"] += 1
        if c:
            out.append(f"{nm}'s guard at the parting decision: " + ", ".join(f"{k} {v}" for k, v in c.most_common()) + ".")
    fd = collections.Counter((r["first_diff"] or {}).get("how", "none") for r in ok if not r["identical"])
    out.append("First difference in logged guard or mate prices (same position): " + ", ".join(f"{k} {v}" for k, v in fd.most_common()) + ".")
    pl = [r["ply"] - (r["first_diff"] or {}).get("n", r["ply"]) for r in ok if not r["identical"] and r.get("first_diff")]
    if pl:
        pl.sort()
        out.append(f"Plies from that first difference to the parting move: median {pl[len(pl) // 2]} (0 in {sum(x <= 0 for x in pl)} of {len(pl)}).")
    out.append(f"rescue= or partner_held= at the parting decision: {sum(bool(r.get('rescue')) for r in ok if not r['identical'])}.")
    out.append("")
    out.append("Per game (pair, contender colour): parting ply, seat, cause; each side's decision (reason; guard; mate prices); result A-B.")
    out.append("")
    out.append("| pair | colour | ply | seat | cause | " + nameA + " | " + nameB + " | result |")
    out.append("|---|---|---|---|---|---|---|---|")

    def side(x):
        if x is None:
            return "-"
        mp_ = "/".join(f"{k}:{''.join(v)}" for k, v in x["mate_prices"].items() if v)
        return (f"`{'sit' if x['sat'] else x['decision']}` ({x['reason']}; guard {x['guard']}; "
                f"{('mates ' + mp_) if mp_ else 'no mate price'}{'; rescue ' + x['rescue'] if x['rescue'] else ''}"
                f"{'; held ' + x['partner_held'] if x['partner_held'] else ''}; score {x['score']})")
    for r in ok:
        if r["identical"]:
            out.append(f"| {r['pair']} | {r['team']} | - | - | identical | | | {r['score_a']:g}-{r['score_b']:g} |")
            continue
        seat = r["a"]["seat"] if r["a"] else "-"
        out.append(f"| {r['pair']} | {r['team']} | {r['ply']} | {seat} | {r['cause']} | {side(r['a'])} | {side(r['b'])} | "
                   f"{r['score_a']:g}-{r['score_b']:g} |")
    text = "\n".join(out)
    open(os.path.join(HERE, f"diverge_{tag}.md"), "w").write(text + "\n")
    print("\n".join(out[:30]))


if __name__ == "__main__":
    main()
