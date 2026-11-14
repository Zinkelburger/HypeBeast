#!/usr/bin/env python3
"""Timeline of every game the candidate lost: both seats of the losing team, walked back from the end.

Writes timeline.json (one record per lost game) and prints one block per game.
"""
import collections
import json
import os
import sys

import chess

from common import (HERE, MATE, PARTNER, load, replay_boards, seat_board, seat_team, seat_white, team_seats)

PV = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5}


def sc(r):
    return r["score"] if r["score"] is not None else None


def fmt(s):
    if s is None:
        return "?"
    if s <= -MATE:
        return "M-"
    if s >= MATE:
        return "M+"
    return str(s)


def for_good(rows, thr=-300):
    """index of the first row from which every later scored row is < thr (None if the last is not)"""
    idx = None
    for i in range(len(rows) - 1, -1, -1):
        s = rows[i]["score"]
        if s is None:
            continue
        if s < thr:
            idx = i
        else:
            break
    return idx


def end_board(g, snaps=None):
    """-> (board '1'/'2', loser seat) for the board that decided the game. A mate can be completed by a move on
    the other board (the partner can no longer provide a blocker), so the mated board is the one where the
    loser's seat is checkmated in the final position; the last move's board only when neither is."""
    term = g["termination"]
    winner = g["winner"]
    loser_team = "black" if winner == "white" else "white"
    if term == "flag":
        c = g["clocks_end"]   # aW aB bW bB
        i = min(range(4), key=lambda k: c[k])
        seat = ["Awhite", "Ablack", "Bwhite", "Bblack"][i]
        return seat_board(seat), seat
    b = g["toks"][-1][0]
    if snaps is not None:
        fa, fb = snaps[-1]
        for s in team_seats(loser_team):
            bd = fa if s[0] == "A" else fb
            if bd.turn == (chess.WHITE if seat_white(s) else chess.BLACK) and bd.is_checkmate():
                b = seat_board(s)
                break
    for s in team_seats(loser_team):
        if seat_board(s) == b:
            return b, s
    return None, None


def captures_to(g, seat, lo, hi):
    """pieces that reached seat's opponent ('-') or seat ('+') hand from captures with token index in [lo, hi)"""
    out = []
    ours = seat_board(seat)
    white = seat_white(seat)
    for i, b, mover_white, t in g["caps"]:
        if lo <= i < hi and b != ours:
            sign = "-" if mover_white == white else "+"
            out.append({"idx": i, "k": sign + t, "uci": g["toks"][i][1:]})
    return out


def world_of(row, k):
    ws = [w for w in row["worlds"] if k in w["arrival"].replace("+", " +").replace("-", " -").split()]
    if not ws:
        return None
    w = max(ws, key=lambda w: w["p"])
    return w


def partner_view(g, prow_list, cap):
    """the partner's last decision before the capture at token cap['idx']: score, pass, was the capture in its pv"""
    prs = [x for x in prow_list if x["n"] <= cap["idx"]]
    if not prs:
        return {"known": "no partner decision"}
    pr = prs[-1]
    board = g["toks"][cap["idx"]][0]
    between = [t[1:] for t in g["toks"][pr["n"]:cap["idx"]] if t[0] == board]
    pv = pr.get("pvfull") or pr["pv"]
    j = len(between)
    if pr["decision"] == "pass":
        known = "sitting"
    elif len(pv) > j and pv[:j] == between and pv[j] == cap["uci"]:
        known = "in its line"
    elif cap["uci"] in pv[1::2]:
        known = "in its line later/elsewhere"
    else:
        known = "not in its line"
    return {"n": pr["n"], "score": pr["score"], "decision": pr["decision"], "known": known, "plies_after": j,
            "pv": pv[:8], "reason": pr["reason"]}


def taken_back(g, cap, window=1):
    """did the partner's side capture something on that board within `window` plies of that board around it (1: the ply just before or just after)"""
    board = g["toks"][cap["idx"]][0]
    mover = next(c[2] for c in g["caps"] if c[0] == cap["idx"])
    btoks = [i for i, t in enumerate(g["toks"]) if t[0] == board]
    pos = btoks.index(cap["idx"])
    near = set(btoks[max(0, pos - window):pos + window + 1])
    return [c[3] for c in g["caps"] if c[0] in near and c[0] != cap["idx"] and c[2] != mover]


def sits_of(g, seat):
    key = seat[0] + "-" + seat[1:]
    return [e for e in g["events"] if e["kind"] == "sit" and e["seat"] == key]


def missed_supplies(g, rows_by_seat, team, snaps):
    """decisions of the team where a world of '+T' alone (T arriving to that seat) made the move mate for us
    (or turned a mate against us into none) and the 'none' world did not, with what the partner did."""
    out = []
    for seat in team_seats(team):
        for r in rows_by_seat[seat]:
            none = next((w for w in r["worlds"] if w["arrival"] == "none"), None)
            base = none["v_best"] if none and none["v_best"] is not None else r["score"]
            if base is None:
                continue
            for w in r["worlds"]:
                a = w["arrival"]
                if a == "none" or a.count("+") != 1 or "-" in a or w["v_best"] is None:
                    continue
                t = a[1]
                kind = None
                if w["v_best"] >= MATE and base < MATE:
                    kind = "win"
                elif w["v_best"] > -MATE and base <= -MATE:
                    kind = "save"
                if not kind:
                    continue
                # the partner's next decision at or after this one
                p = PARTNER[seat]
                nxt = [x for x in rows_by_seat[p] if x["n"] >= r["n"]]
                own_next = [x for x in rows_by_seat[seat] if x["n"] > r["n"]]
                limit = own_next[0]["n"] if own_next else len(g["toks"])
                if not nxt or nxt[0]["n"] >= limit:
                    out.append({"seat": seat, "n": r["n"], "t": t, "kind": kind, "p": w["p"], "partner": "no decision before our next"})
                    continue
                pr = nxt[0]
                bA, bB = snaps[pr["n"]]
                pb = bA if p[0] == "A" else bB
                legal = []
                if pb.turn == (chess.WHITE if seat_white(p) else chess.BLACK):
                    for mv in pb.legal_moves:
                        if pb.is_capture(mv) and not pb.is_en_passant(mv):
                            pc = pb.piece_at(mv.to_square)
                            tt = "P" if mv.to_square in chess.SquareSet(pb.promoted) else chess.piece_symbol(pc.piece_type).upper()
                            if tt == t:
                                legal.append(mv.uci())
                        elif pb.is_en_passant(mv) and t == "P":
                            legal.append(mv.uci())
                made = [c for c in captures_to(g, seat, pr["n"], limit) if c["k"] == "+" + t]
                out.append({"seat": seat, "n": r["n"], "t": t, "kind": kind, "p": w["p"], "v_best": w["v_best"],
                            "base": base, "partner_n": pr["n"], "partner_decision": pr["decision"],
                            "partner_score": pr["score"], "legal": legal, "made": bool(made)})
    return out


def analyse(m, data):
    games, rows, cand = data["games"], data["rows"], data["cand"]
    rg = collections.defaultdict(list)
    for r in rows:
        rg[(r["game"], r["seat"])].append(r)
    recs = []
    for g in games:
        team = g["cand_team"]
        if g["winner"] == team or g["winner"] not in ("white", "black"):
            continue
        snaps = replay_boards(g["toks"])
        board, S = end_board(g, snaps)
        last_board = g["toks"][-1][0]
        P = PARTNER[S]
        rbs = {s: sorted(rg[(g["game"], s)], key=lambda r: r["n"]) for s in team_seats(team)}
        opp_team = "black" if team == "white" else "white"
        rbs_opp = {s: sorted(rg[(g["game"], s)], key=lambda r: r["n"]) for s in team_seats(opp_team)}
        rec = {"match": m, "game": g["game"], "team": team, "termination": g["termination"], "S": S, "P": P,
               "plies": len(g["toks"]), "mate_by_other_board": board != last_board, "end_t": g["events"][-1]["t"], "clocks_end": g["clocks_end"],
               "sits": {s: len(sits_of(g, s)) for s in ("Awhite", "Ablack", "Bwhite", "Bblack")},
               "sit_ms": g["sit_ms"]}
        for seat in (S, P):
            rs = rbs[seat]
            ib = for_good(rs)
            im = next((i for i, r in enumerate(rs) if r["score"] is not None and r["score"] <= -MATE), None)
            info = {"decisions": len(rs), "i_bad": ib, "i_mate": im,
                    "bad_n": rs[ib]["n"] if ib is not None else None, "bad_t": rs[ib]["t"] if ib is not None else None,
                    "mate_n": rs[im]["n"] if im is not None else None, "mate_t": rs[im]["t"] if im is not None else None,
                    "last_score": rs[-1]["score"] if rs else None,
                    "max_score": max((r["score"] for r in rs if r["score"] is not None), default=None),
                    "won_at_some_point": any(r["score"] is not None and r["score"] >= MATE for r in rs),
                    "passes": sum(1 for r in rs if r["decision"] == "pass"),
                    "pass_reasons": dict(collections.Counter(r["reason"] for r in rs if r["decision"] == "pass"))}
            unwarned = ib is None and seat == S and g["termination"] == "checkmate" and rs
            info["unwarned"] = bool(unwarned)
            if unwarned:
                # mated with every decision at -300 or better: the "bad" point is the end of the game
                ib = len(rs)
                info["bad_n"] = len(g["toks"])
                info["bad_t"] = g["events"][-1]["t"]
            if ib is not None:
                info["pre_bad_score"] = rs[ib - 1]["score"] if ib > 0 else None
                info["bad_score"] = rs[ib]["score"] if ib < len(rs) else -100000
                info["sudden"] = info["bad_score"] <= -MATE and (ib == 0 or (rs[ib - 1]["score"] or 0) >= -300)
                lo = rs[ib - 1]["n"] if ib > 0 else 0
                info["arrivals_into_bad"] = captures_to(g, seat, lo, info["bad_n"])
                if ib > 0:
                    pre = rs[ib - 1]
                    for c in info["arrivals_into_bad"]:
                        w = world_of(pre, c["k"])
                        c["world_p"] = w["p"] if w else 0
                        c["world"] = w["arrival"] if w else None
                        c["v_chosen"] = w["v_chosen"] if w else None
                        c["v_best"] = w["v_best"] if w else None
                        c["v_main"] = w["v_main"] if w else None
                        if c["k"][0] == "-":
                            c["partner"] = partner_view(g, rbs[PARTNER[seat]], c)
                            c["taken_back"] = taken_back(g, c)
                    info["passes_pre_to_bad"] = [(r["n"], r["reason"]) for r in rs[ib - 1:ib + 1] if r["decision"] == "pass"]
                    none =next((w for w in pre["worlds"] if w["arrival"] == "none"), None)
                    info["pre"] = {"n": pre["n"], "score": pre["score"], "decision": pre["decision"], "main": pre["main"],
                                   "reason": pre["reason"], "E_chosen": pre["E_chosen"], "E_main": pre["E_main"],
                                   "none_v": none["v_chosen"] if none else None,
                                   "worlds": [(w["arrival"], w["p"], w["v_chosen"], w["v_best"]) for w in pre["worlds"]],
                                   "feat": pre["feat"], "clocks": pre["clocks"], "tadv": pre["tadv"]}
            if im is not None:
                lo_i = max(0, im - 3)
                lo = rs[lo_i]["n"]
                info["arrivals_before_mate"] = captures_to(g, seat, lo, rs[im]["n"])
                for c in info["arrivals_before_mate"]:
                    seen = []
                    for r in rs[lo_i:im]:
                        if r["n"] <= c["idx"]:
                            w = world_of(r, c["k"])
                            seen.append({"n": r["n"], "p": w["p"] if w else 0, "v_chosen": w["v_chosen"] if w else None,
                                         "v_best": w["v_best"] if w else None, "score": r["score"]})
                    c["seen"] = seen
                    if c["k"][0] == "-":
                        c["partner"] = partner_view(g, rbs[PARTNER[seat]], c)
                        c["taken_back"] = taken_back(g, c)
                info["window_partner"] = [(r["n"], r["score"], r["decision"], r["reason"]) for r in rbs[PARTNER[seat]]
                                          if lo <= r["n"] <= rs[im]["n"]]
            rec[seat] = info
        rec["S_role"] = "S"
        rec["missed"] = missed_supplies(g, rbs, team, snaps)
        # the opponents: did the winning team see a forced mate, when
        om = [r for s in rbs_opp for r in rbs_opp[s] if r["score"] is not None and r["score"] >= MATE]
        rec["opp_first_mate_n"] = min((r["n"] for r in om), default=None)
        own = [r for s in rbs for r in rbs[s] if r["score"] is not None and r["score"] >= MATE]
        rec["own_first_mate_n"] = min((r["n"] for r in own), default=None)
        rec["own_first_mate_seat"] = min(own, key=lambda r: r["n"])["seat"] if own else None
        rec["own_mate_at_end"] = [s for s in rbs if rbs[s] and rbs[s][-1]["score"] is not None and rbs[s][-1]["score"] >= MATE]
        # last decision of each own seat: score, clocks
        for seat in (S, P):
            rs = rbs[seat]
            if rs:
                rec[seat]["last"] = {"n": rs[-1]["n"], "score": rs[-1]["score"], "decision": rs[-1]["decision"],
                                     "reason": rs[-1]["reason"], "clocks": rs[-1]["clocks"], "tadv": rs[-1]["tadv"]}
        recs.append(rec)
    return recs


def main():
    data = load()
    allrecs = []
    for m in data:
        allrecs += analyse(m, data[m])
    json.dump(allrecs, open(os.path.join(HERE, "timeline.json"), "w"), indent=1, default=str)
    for r in allrecs:
        S, P = r["S"], r["P"]
        s, p = r[S], r[P]
        print(f"{r['match'][:8]} g{r['game']:>2} {r['termination']:9} S={S:6} P={P:6} plies={r['plies']} "
              f"S: bad@{s['bad_n']} ({fmt(s.get('pre_bad_score'))}->{fmt(s.get('bad_score'))}) mate@{s['mate_n']} "
              f"P: bad@{p['bad_n']} mate@{p['mate_n']} last={fmt(p['last_score'])} max={fmt(p['max_score'])} "
              f"oppM@{r['opp_first_mate_n']} sits={r['sits']} clocks={r['clocks_end']}")
        for c in s.get("arrivals_into_bad", []):
            print(f"     into bad: {c['k']} idx={c['idx']} world_p={c.get('world_p')} v_chosen={fmt(c.get('v_chosen'))} v_best={fmt(c.get('v_best'))}")
        for c in s.get("arrivals_before_mate", []):
            pv = c.get("partner", {})
            print(f"     before mate: {c['k']} idx={c['idx']} seen={[(x['p'], fmt(x['v_chosen'])) for x in c['seen']]} "
                  f"partner={pv.get('known')} pscore={fmt(pv.get('score'))} back={c.get('taken_back')}")
        ms = [x for x in r["missed"] if x.get("legal") and not x.get("made")]
        if ms:
            print(f"     missed supplies: {[(x['seat'], x['n'], x['t'], x['kind'], round(x['p'], 2)) for x in ms]}")


if __name__ == "__main__":
    main()
