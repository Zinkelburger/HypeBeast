#!/usr/bin/env python3
"""Every lost game of plan-vs-l50, for BOTH sides: timeline, turning point and first cause.

    nice -n 19 python3 classify2.py [MATCH]      -> lost_<MATCH>.json, classes_<MATCH>.txt

Reuses autopsy/timeline.py (for_good, end_board, captures_to, world_of, partner_view, taken_back,
missed_supplies) and autopsy/classify.py's s_kind, unchanged. Definitions are AUTOPSY.md's:
  mated seat S (the losing seat on the board that decided the game; the flagged seat for a flag), partner P;
  lost for good at decision i: the seat's main score < -300 there and at every later decision;
  its fall: the step from the last decision at -300 or better ("pre") to the first lost-for-good decision ("bad").
First-cause rules, in this order (written down before looking at the counts):
  1. events: S_bad (S's fall), P_bad (P's fall), W (the losing team's first forced mate FOR itself, score >= 90000),
     F (first missed supply: a single +T world mated for us, nothing arriving did not, the partner had a legal
     capture of a T at its next decision before ours and did not take one). The earliest wins; ties S, P, W, F.
  2. a flag where the flagged seat was not yet lost for good: "clock".
  3. W first: "e" (lost the mating race); F first: "f" (missed supply).
  4. S or P first: the seat that fell first is the "falling seat" and its decision "pre" is the turning point.
     a. pre was a sit (decision pass) whose reason is not hold_mated: "h" (a sit that went wrong).
     b. pre switched away from the main move (override) and, in the world that really came (the pieces that
        reached either hand on that board between pre and bad, matched to a scored coord world), the main move
        scored >= 300 cp more than the move played, or survived where the move played was mated: "g" (a switch
        that went wrong).
     c. otherwise the fall's kind (autopsy s_kind): a, a2, a3, b (sudden mate after an arrival in a world known
        fatal / scored survivable / move not scored / in no world), c2 (sudden mate, nothing arrived),
        a4, b2 (drop >= 400 cp after an arrival in a world / in no world), c (slow loss on its own board).
        If the falling seat is P the class is "d" (partner's board lost first) with that kind as sub-kind.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "autopsy"))
from common2 import (MATE, PARTNER, by_seat, fm, load, replay_boards, seat_board, seat_white, team_seats)  # noqa: E402
import timeline as TL  # noqa: E402  (autopsy)
from classify import s_kind, fatal_piece  # noqa: E402  (autopsy)

MATCH = sys.argv[1] if len(sys.argv) > 1 else "plan-vs-l50"


def key_counter(key):
    import re
    c = collections.Counter()
    for s, t in re.findall(r"([+-])([PNBRQ])", key):
        c[s + t] += 1
    return c


def realised_world(pre, arrivals):
    """the coord world of decision `pre` whose package equals what arrived (list of {'k':...}); its values"""
    got = collections.Counter(c["k"] for c in arrivals)
    co = pre.get("coord") or {}
    for w in co.get("worlds") or []:
        a = w["arrival"]
        if (a == "none" and not got) or (a != "none" and key_counter(a) == got):
            return w
    return None


def fall_info(g, rs, prs, seat, snaps):
    """lost-for-good, fall, arrivals and world sightings for one seat (rows rs sorted; prs: its partner's rows)"""
    ib = TL.for_good(rs)
    im = next((i for i, r in enumerate(rs) if r["score"] is not None and r["score"] <= -MATE), None)
    info = {"decisions": len(rs), "i_bad": ib, "i_mate": im,
            "bad_n": rs[ib]["n"] if ib is not None else None,
            "mate_n": rs[im]["n"] if im is not None else None,
            "mate_score": rs[im]["score"] if im is not None else None,
            "last_score": rs[-1]["score"] if rs else None,
            "passes": sum(1 for r in rs if r["decision"] == "pass"),
            "pass_reasons": dict(collections.Counter(r["reason"] for r in rs if r["decision"] == "pass"))}
    return ib, im, info


def analyse_seat(g, rbs, seat, is_S, snaps):
    rs = rbs[seat]
    ib, im, info = fall_info(g, rs, rbs[PARTNER[seat]], seat, snaps)
    unwarned = ib is None and is_S and g["termination"] == "checkmate" and rs
    info["unwarned"] = bool(unwarned)
    if unwarned:
        ib = len(rs)
        info["bad_n"] = len(g["toks"])
    if ib is None:
        return info
    info["pre_bad_score"] = rs[ib - 1]["score"] if ib > 0 else None
    info["bad_score"] = rs[ib]["score"] if ib < len(rs) else -100000
    info["sudden"] = info["bad_score"] <= -MATE and (ib == 0 or (rs[ib - 1]["score"] or 0) >= -300)
    lo = rs[ib - 1]["n"] if ib > 0 else 0
    info["arrivals_into_bad"] = TL.captures_to(g, seat, lo, info["bad_n"])
    if ib > 0:
        pre = rs[ib - 1]
        for c in info["arrivals_into_bad"]:
            w = TL.world_of(pre, c["k"])
            c["world_p"] = w["p"] if w else 0
            c["world"] = w["arrival"] if w else None
            c["v_chosen"] = w["v_chosen"] if w else None
            c["v_best"] = w["v_best"] if w else None
            c["v_main"] = w["v_main"] if w else None
            if c["k"][0] == "-":
                c["partner"] = TL.partner_view(g, rbs[PARTNER[seat]], c)
                c["taken_back"] = TL.taken_back(g, c)
        rw = realised_world(pre, info["arrivals_into_bad"])
        vm = vc = None
        if rw:
            vm = rw["values"].get(pre["main"])
            vc = rw["values"].get(pre["decision"])
        none = next((w for w in pre["worlds"] if w["arrival"] == "none"), None)
        info["pre"] = {"n": pre["n"], "t": pre["t"], "score": pre["score"], "decision": pre["decision"], "main": pre["main"],
                       "reason": pre["reason"], "override": pre["override"], "E_chosen": pre["E_chosen"],
                       "E_main": pre["E_main"], "none_v": none["v_chosen"] if none else None,
                       "worlds": [(w["arrival"], w["p"], w["v_chosen"], w["v_best"], w.get("depth")) for w in pre["worlds"]],
                       "realised": rw["arrival"] if rw else None, "realised_v_main": vm, "realised_v_chosen": vc,
                       "feat": pre["feat"], "clocks": pre["clocks"], "tadv": pre["tadv"], "talk": pre.get("talk"),
                       "depth": pre["depth"], "fc_depth": pre.get("fc_depth"), "told": pre.get("told"),
                       "pv": (pre.get("pvfull") or pre["pv"])[:8]}
    return info


def classify_fall(info):
    """rule 4 for the falling seat: (class letter, kind, why)"""
    kind, c, why = s_kind(info)
    pre = info.get("pre")
    if pre:
        if pre["decision"] == "pass" and pre["reason"] != "hold_mated":
            return "h", kind, c, f"sat ({pre['reason']}) at the turning point; fall kind {kind}"
        if pre["override"] and pre["decision"] != "pass":
            vm, vc = pre["realised_v_main"], pre["realised_v_chosen"]
            if vm is not None and vc is not None and (vm - vc >= 300 or (vc <= -MATE < vm)):
                return "g", kind, c, f"switched {pre['main']}->{pre['decision']} ({pre['reason']}); in the world that came main {fm(vm)} vs played {fm(vc)}"
    return kind, kind, c, why


def analyse(match, data):
    games, rows = data["games"], data["rows"]
    rg = by_seat(rows)
    recs = []
    for g in games:
        if g["winner"] not in ("white", "black"):
            continue
        team = "black" if g["winner"] == "white" else "white"
        loser = g["seats"]["A-" + team]
        snaps = replay_boards(g["toks"])
        board, S = TL.end_board(g, snaps)
        P = PARTNER[S]
        rbs = {s: rg[(g["game"], s)] for s in team_seats(team)}
        opp = "black" if team == "white" else "white"
        rbs_opp = {s: rg[(g["game"], s)] for s in team_seats(opp)}
        rec = {"match": match, "game": g["game"], "loser": loser, "team": team, "termination": g["termination"],
               "S": S, "P": P, "plies": len(g["toks"]), "clocks_end": g["clocks_end"],
               "end_t": g["events"][-1]["t"] if g["events"] else None}
        rec[S] = analyse_seat(g, rbs, S, True, snaps)
        rec[P] = analyse_seat(g, rbs, P, False, snaps)
        rec["missed"] = TL.missed_supplies(g, rbs, team, snaps)
        own = [r for s in rbs for r in rbs[s] if r["score"] is not None and r["score"] >= MATE]
        rec["own_first_mate_n"] = min((r["n"] for r in own), default=None)
        rec["own_first_mate_seat"] = min(own, key=lambda r: r["n"])["seat"] if own else None
        om = [r for s in rbs_opp for r in rbs_opp[s] if r["score"] is not None and r["score"] >= MATE]
        rec["opp_first_mate_n"] = min((r["n"] for r in om), default=None)
        # ---- first cause
        s, p = rec[S], rec[P]
        ev = []
        if s.get("bad_n") is not None:
            ev.append((s["bad_n"], 0, "S"))
        if p.get("bad_n") is not None:
            ev.append((p["bad_n"], 1, "P"))
        if rec["own_first_mate_n"] is not None:
            ev.append((rec["own_first_mate_n"], 2, "W"))
        miss = [x for x in rec["missed"] if x.get("legal") and not x.get("made")]
        if miss:
            ev.append((min(x["n"] for x in miss), 3, "F"))
        ev.sort()
        rec["events"] = ev
        rec["flag"] = g["termination"] == "flag"
        cls = sub = None
        fall_seat = None
        if rec["flag"] and (s.get("bad_n") is None or s["bad_n"] >= rec["plies"]):
            cls = "clock"
        elif not ev:
            cls = "?"
        else:
            first = ev[0][2]
            if first == "W":
                cls = "e"
            elif first == "F":
                cls = "f"
            else:
                fall_seat = S if first == "S" else P
                letter, kind, c, why = classify_fall(rec[fall_seat])
                rec["fall_why"] = why
                rec["fatal"] = c
                if first == "S":
                    cls, sub = letter, kind
                else:
                    cls, sub = "d", letter
        # S's own fall kind (whatever came first) and P's
        for seat in (S, P):
            if rec[seat].get("bad_n") is not None:
                letter, kind, c, why = classify_fall(rec[seat])
                rec[seat]["fall_class"] = letter
                rec[seat]["fall_kind"] = kind
                rec[seat]["fatal"] = c
        rec["cls"], rec["sub"], rec["fall_seat"] = cls, sub, fall_seat
        # turning point: the falling seat's pre decision; for e the team's first mate; f the missed supply
        tp = None
        if fall_seat and rec[fall_seat].get("pre"):
            tp = {"seat": fall_seat, "n": rec[fall_seat]["pre"]["n"]}
        elif fall_seat:
            tp = {"seat": fall_seat, "n": rec[fall_seat].get("bad_n")}
        elif cls == "e":
            tp = {"seat": rec["own_first_mate_seat"], "n": rec["own_first_mate_n"]}
        elif cls == "f":
            x = min(miss, key=lambda x: x["n"])
            tp = {"seat": PARTNER[x["seat"]], "n": x["partner_n"], "supply": x}
        elif cls == "clock":
            tp = {"seat": S, "n": rec["plies"]}
        rec["tp"] = tp
        recs.append(rec)
    return recs


def evidence(rec):
    S, P = rec["S"], rec["P"]
    cls = rec["cls"]
    if cls == "e":
        return (f"{rec['own_first_mate_seat']} reported a forced mate at n={rec['own_first_mate_n']}; "
                f"{S} fell at n={rec[S].get('bad_n')} ({fm(rec[S].get('pre_bad_score'))}->{fm(rec[S].get('bad_score'))})")
    if cls == "f":
        x = rec["tp"]["supply"]
        return (f"{x['seat']} n={x['n']}: +{x['t']} world {fm(x['v_best'])} (p {x['p']:.2f}), {PARTNER[x['seat']]} n={x['partner_n']} "
                f"could take {x['legal'][:3]} and played {x['partner_decision']}")
    if cls == "clock":
        return f"{S} flagged, clocks at end {rec['clocks_end']}"
    fs = rec["fall_seat"]
    if fs is None:
        return "?"
    s = rec[fs]
    pre = s.get("pre") or {}
    c = rec.get("fatal")
    piece = "nothing arrived"
    if c:
        pv = c.get("partner") or {}
        piece = (f"{c['k']} (world p {c.get('world_p', 0):.2f}, move {fm(c.get('v_chosen'))}; partner {pv.get('known')}, "
                 f"score {fm(pv.get('score'))})")
    play = pre.get("decision", "?")
    if pre.get("override"):
        play += f" (main {pre.get('main')}, {pre.get('reason')})"
    elif pre.get("decision") == "pass":
        play += f" ({pre.get('reason')})"
    return (f"{fs} n={pre.get('n')}: {fm(s.get('pre_bad_score'))} -> {fm(s.get('bad_score'))} at n={s.get('bad_n')}; "
            f"played {play}; {piece}")


NAMES = {"a": "sudden mate, arrival in a world where the move was mated", "a2": "sudden mate, arrival in a world scored survivable",
         "a3": "sudden mate, arrival in a world, move not scored there", "b": "sudden mate, arrival in no world",
         "c2": "sudden mate, nothing arrived", "a4": "decisive drop (>=400) after an arrival in a world",
         "b2": "decisive drop after an arrival in no world", "c": "slow loss on its own board",
         "d": "partner's board lost first", "e": "lost a mating race", "f": "missed supply first",
         "g": "a switch away from the main move went wrong", "h": "a sit went wrong", "clock": "flag while not lost", "?": "?"}


def main():
    data = load(MATCH)
    recs = analyse(MATCH, data)
    for r in recs:
        r["evidence"] = evidence(r)
    json.dump(recs, open(os.path.join(HERE, f"lost_{MATCH}.json"), "w"), indent=1, default=str)
    out = []
    engines = sorted({r["loser"] for r in recs})
    out.append(f"{MATCH}: {len(data['games'])} games, lost: " + ", ".join(f"{e} {sum(r['loser'] == e for r in recs)}" for e in engines))
    out.append("")
    out.append("| class | " + " | ".join(engines) + " |")
    out.append("|---|" + "---|" * len(engines))
    keys = sorted({r["cls"] for r in recs}, key=lambda k: -len([r for r in recs if r["cls"] == k]))
    for k in keys:
        cells = []
        for e in engines:
            gs = sorted(r["game"] for r in recs if r["cls"] == k and r["loser"] == e)
            cells.append(f"{len(gs)}: " + ", ".join(map(str, gs)) if gs else "0")
        out.append(f"| ({k}) {NAMES.get(k, k)} | " + " | ".join(cells) + " |")
    out.append("")
    out.append("d sub-kinds (the partner's fall): " + ", ".join(
        f"{e}: " + str(dict(collections.Counter(r['sub'] for r in recs if r['cls'] == 'd' and r['loser'] == e))) for e in engines))
    out.append("S's own fall kind, whatever came first: " + ", ".join(
        f"{e}: " + str(dict(collections.Counter(r[r['S']].get('fall_class') for r in recs if r['loser'] == e))) for e in engines))
    out.append("")
    out.append("| loser | game | class | turning point (seat, n) | evidence |")
    out.append("|---|---|---|---|---|")
    for r in sorted(recs, key=lambda r: (r["loser"], r["game"])):
        tp = r["tp"] or {}
        c = r["cls"] + (f"/{r['sub']}" if r["cls"] == "d" else "")
        out.append(f"| {r['loser']} | {r['game']} | {c} | {tp.get('seat')} {tp.get('n')} | {r['evidence']} |")
    txt = "\n".join(out)
    open(os.path.join(HERE, f"classes_{MATCH}.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
