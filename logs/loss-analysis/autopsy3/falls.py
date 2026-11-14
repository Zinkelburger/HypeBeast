#!/usr/bin/env python3
"""AUTOPSY3: the first fall of each hb-l50 seat, classified by what happened. Logs only.

    nice -n 19 python3 falls.py [ENGINE] [MATCH ...]   -> falls_<ENGINE>.json, falls_<ENGINE>.txt

Rules, fixed before any count was looked at:

Seat sequence S: the seat's decisions with a main score, in order. Mates are +-(100000 - plies);
scores are clipped to +-3000 wherever two are subtracted.

F, the first lost-for-good decision: the first index whose score and every later score is below -300.
  No such index: the seat never fell. F = 0: the seat was below -300 at all its decisions ("opening").

Key step: among the (up to) three steps into F, S[F-3]->S[F-2], S[F-2]->S[F-1], S[F-1]->S[F],
  the one with the largest drop (ties: the later). K is its first decision, N its second.
  Drop = clip(N) - clip(K).

What happened in the key step (between K's decision and N's):
  arrivals to the opponent: pieces captured on the other board by the opponent's partner (they reach the
    opponent's hand), from K's "future"; to us: the same for our partner.
  matching world: among K's scored coordinator worlds whose "-" pieces include all the "-" pieces that
    arrived, the one whose whole package is closest to what arrived (both signs), then the largest p ("exact";
    revised after the first run, see matching_world); else the worlds holding the most valuable "-" piece that arrived
    ("partial"); else none.
  arrival cost: v_none(played) - v_world(played) in the matching world (clipped); without a world, or with
    the move played not scored there, the forecast's measured price of those pieces (fc_prices) summed;
    else unknown.
  The arrival explains the step when its cost is unknown or at least min(300, |Drop| / 2).

Primary class of the key step, first rule that applies:
  O  opening: F = 0.
  S  slide: Drop > -200 (no step of 200 cp or more among the three).
  H  a sit: K was a sit (reason hold_partner, hold_feed, stall_deny or voluntary_wait; hold_mated is not
     counted: that seat already saw itself mated).
  G  a switch that went wrong: K overrode the main move, and in the world that came true (the matching
     world, or "none" when nothing arrived) the main move scored 300 cp or more above the move played, or
     was not mated where the move played was.
  A  an arrival explains the step:
     A1 no world held it;  A2 a world held it but the move played was not scored there;
     A3 the world had the move played at -300 or better (the world did not foresee the fall);
     A4 the world had the move played below -300 and another candidate at -300 or better;
     A5 the world had every scored candidate below -300.
  C  the seat's own board (no arrival to the opponent, or one that does not explain the step):
     C1 N is a forced mate against the seat;
     C2 the opponent's reply on our board was the second move of K's main line (the line's own score fell);
     C3 the opponent's reply was another move;
     C4 no opponent reply on our board before N (we sat, or the opponent sat);
     C5 K played a move other than its main line's first move (switch, not counted as G): no line to compare.

Flags at K, kept beside the class: in check; king off its home rank; the partner sat during the step;
the partner's board below -300 (its last score before K) or mated; K overrode the main move; the opponent's
hand worth 6 or more; clocks; whether the fall ended in a forced mate; whether this was its team's first fall.

Information that existed (per key step):
  worlds_better: in the world that came true, a K candidate scored 200 cp or more above the move played;
    its cost in "none" and its E beside the played move's.
  seen_before: how many of the seat's two decisions before K had a scored world holding the "-" piece that
    then arrived, with p >= 0.10.
  partner_line: the partner's last decision before the capture that fed the opponent had that capture as
    the reply in its own main line (it played its line's first move); partner_alt: it had another candidate
    within 150 cp of its choice (L, the "none" world).
  depth_seen: at N, the first main-search depth whose score was below -300 (or a mate); fell_with_depth at
    K: the last depth's score 100 cp or more below the best of the three depths before it.
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common3 as c3  # noqa: E402
import postmortem as pm  # noqa: E402

MATE = 90000
LOST = -300
SIT_REASONS = {"hold_partner", "hold_feed", "stall_deny", "voluntary_wait"}
PV = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}
clip = c3.clip


def minus_counter(key):
    c = collections.Counter()
    for s, t in re.findall(r"([+-])([PNBRQ])", key or ""):
        if s == "-":
            c[t] += 1
    return c


def world_vals(r):
    co = r.get("coord") or {}
    return {w["arrival"]: w for w in co.get("worlds", []) if w.get("scored")}


def cands(r):
    return (r.get("coord") or {}).get("cands", [])


def is_sit(r):
    return r["reason"] in SIT_REASONS


def signed_counter(key):
    c = collections.Counter()
    for s, t in re.findall(r"([+-])([PNBRQ])", key or ""):
        c[s + t] += 1
    return c


def matching_world(r, arrived_minus, arrived_plus=()):
    """Revised rule (2026-11-12 01:30, after the first run matched plan-vs-l50-b 66 Ablack to "+Q-R-P" when only
    -R came): among the worlds holding every "-" piece that arrived, the one whose whole package is closest to
    what arrived (both signs: sum of count differences), then the largest p."""
    ws = world_vals(r)
    if not arrived_minus:
        return ws.get("none"), "none" if "none" in ws else None
    need = collections.Counter(arrived_minus)
    got = collections.Counter(["-" + t for t in arrived_minus] + ["+" + t for t in arrived_plus])
    exact = [w for k, w in ws.items() if k != "none" and all(minus_counter(k)[t] >= m for t, m in need.items())]
    if exact:
        def dist(w):
            wc = signed_counter(w["arrival"])
            return sum(abs(wc[x] - got[x]) for x in set(wc) | set(got))
        return min(exact, key=lambda w: (dist(w), -w["p"])), "exact"
    top = max(arrived_minus, key=lambda t: PV[t])
    part = [w for k, w in ws.items() if k != "none" and minus_counter(k)[top] >= 1]
    if part:
        return max(part, key=lambda w: w["p"]), "partial"
    return None, None


def first_reply(g, K, ours, our_white):
    """index and move of the first opponent ply on our board after K.n, and whether K's move was played first"""
    count = sum(1 for t in g["toks"][:K["n"]] if t[0] == ours)   # plies played on our board before K
    our_move_first = None
    for i in range(K["n"], len(g["toks"])):
        t = g["toks"][i]
        if t[0] != ours:
            continue
        white_to_move = count % 2 == 0
        count += 1
        if white_to_move == our_white:
            if our_move_first is None:
                our_move_first = t[1:] == K["decision"]
            continue
        return i, t[1:], our_move_first
    return None, None, our_move_first


def overlap(ivs, t0, t1):
    return any(a < t1 and b > t0 for a, b in ivs)


def analyse(match, data, engine):
    games = {g["game"]: g for g in data["games"]}
    seq = c3.by_seat(data["rows"])
    out = []
    for g in data["games"]:
        for seat_key, name in g["seats"].items():
            if name != engine:
                continue
            seat = seat_key.replace("-", "")
            S = [r for r in seq.get((g["game"], seat), []) if r["score"] is not None]
            if not S:
                continue
            team = c3.c2.seat_team(seat)
            rec = {"match": match, "game": g["game"], "pair": g["pair"], "seat": seat, "team": team,
                   "won": 1.0 if g["winner"] == team else 0.0 if g["winner"] in ("white", "black") else 0.5,
                   "termination": g["termination"], "decisions": len(S)}
            F = None
            for i in range(len(S) - 1, -1, -1):
                if S[i]["score"] < LOST:
                    F = i
                else:
                    break
            if F is None:
                rec["cls"] = "none"
                out.append(rec)
                continue
            rec["F"] = F
            rec["F_n"] = S[F]["n"]
            rec["F_t"] = S[F]["t"]
            rec["fall_is_last"] = F == len(S) - 1
            rec["ends_mated"] = S[-1]["score"] <= -MATE
            rec["fall_score"] = S[F]["score"]
            if F == 0:
                rec["cls"] = "O"
                out.append(rec)
                continue
            steps = [(j, clip(S[j]["score"]) - clip(S[j - 1]["score"])) for j in range(max(1, F - 2), F + 1)]
            j, drop = min(steps, key=lambda x: (x[1], -x[0]))
            K, N = S[j - 1], S[j]
            rec.update({"K_n": K["n"], "N_n": N["n"], "K_t": K["t"], "N_t": N["t"], "K_score": K["score"],
                        "N_score": N["score"], "drop": drop, "key_pos": F - j, "trail": [r["score"] for r in S[max(0, F - 3):F + 1]],
                        "K_decision": K["decision"], "K_main": K["main"], "K_reason": K["reason"],
                        "K_override": K["override"], "K_depth": K["depth"], "N_depth": N["depth"]})
            ours = c3.c2.seat_board(seat)
            white = c3.c2.seat_white(seat)
            arrived = [(q, k, i) for q, k, i in K["future"] if i < N["n"]]
            minus = [k[1] for q, k, i in arrived if k[0] == "-"]
            plus = [k[1] for q, k, i in arrived if k[0] == "+"]
            rec["arr_minus"] = minus
            rec["arr_plus"] = plus
            # captures on our board in the step
            ours_caps = [c for c in g["caps"] if c[1] == ours and K["n"] <= c[0] < N["n"]]
            rec["we_took"] = [c[3] for c in ours_caps if c[2] == white]
            rec["they_took"] = [c[3] for c in ours_caps if c[2] != white]
            # worlds
            ws = world_vals(K)
            none_w = ws.get("none")
            mw, mkind = matching_world(K, minus, plus)
            rec["world_kind"] = mkind if minus else ("none" if none_w else None)
            rec["world_key"] = mw["arrival"] if mw else None
            rec["world_p"] = mw["p"] if mw else None
            dec, main = K["decision"], K["main"]
            v_play = mw["values"].get(dec) if mw else None
            v_main = mw["values"].get(main) if mw else None
            v_best_move, v_best = None, None
            if mw and mw["values"]:
                v_best_move, v_best = max(mw["values"].items(), key=lambda kv: kv[1])
            rec.update({"v_play": v_play, "v_main": v_main, "v_best": v_best, "v_best_move": v_best_move,
                        "v_none_play": none_w["values"].get(dec) if none_w else None,
                        "n_cands": len(cands(K)), "worlds_scored": len(ws)})
            # arrival cost
            cost, cost_src = None, None
            if minus:
                if mw is not None and v_play is not None and none_w and none_w["values"].get(dec) is not None:
                    cost = clip(none_w["values"][dec]) - clip(v_play)
                    cost_src = "world"
                else:
                    pr = K.get("fc_prices") or {}
                    vals = [pr.get("-" + t) for t in minus]
                    if vals and all(v is not None for v in vals):
                        cost = sum(vals)
                        cost_src = "price"
            rec["arr_cost"] = cost
            rec["arr_cost_src"] = cost_src
            explains = bool(minus) and (cost is None or cost >= min(300, abs(drop) / 2))
            rec["arr_explains"] = explains
            # reply on our board
            ri, reply, our_first = first_reply(g, K, ours, white)
            ri = ri if ri is not None and ri < N["n"] else None
            rec["reply"] = reply if ri is not None else None
            mpv = K.get("mainpv") or K.get("pv") or []
            rec["pv_reply"] = mpv[1] if len(mpv) > 1 else None
            rec["played_line_first"] = bool(mpv) and mpv[0] == dec
            # classification
            true_w = mw if minus else none_w
            g_wrong = False
            if K["override"] and true_w is not None:
                a, b = true_w["values"].get(main), true_w["values"].get(dec)
                if a is not None and b is not None:
                    g_wrong = clip(a) - clip(b) >= 300 or (a > -MATE and b <= -MATE)
            if drop > -200:
                cls = "S"
            elif is_sit(K):
                cls = "H"
            elif g_wrong:
                cls = "G"
            elif explains:
                if mw is None:
                    cls = "A1"
                elif v_play is None:
                    cls = "A2"
                elif v_play >= LOST:
                    cls = "A3"
                elif any(v >= LOST for m, v in mw["values"].items() if m != dec):
                    cls = "A4"
                else:
                    cls = "A5"
            else:
                if N["score"] <= -MATE:
                    cls = "C1"
                elif not rec["played_line_first"]:
                    cls = "C5"
                elif rec["reply"] is None:
                    cls = "C4"
                elif rec["reply"] == rec["pv_reply"]:
                    cls = "C2"
                else:
                    cls = "C3"
            rec["cls"] = cls
            rec["g_wrong"] = g_wrong
            # flags
            f = K["feat"]
            rec["in_check"] = bool(f.get("in_check"))
            rec["king_off_home"] = f.get("krank", 0) >= 1
            rec["krank"] = f.get("krank")
            rec["kzone_att"] = f.get("kzone_att")
            rec["opp_hand"] = f.get("hand_opp")
            rec["opp_q"] = f.get("opp_q")
            rec["own_hand"] = f.get("hand_own")
            rec["opp_safe_drop_checks"] = f.get("opp_safe_drop_checks")
            p_seat = c3.PARTNER[seat]
            rec["partner_sat"] = overlap(g["sit_iv"].get(p_seat, []), K["t"], N["t"] + 1)
            rec["self_sat_in_step"] = overlap(g["sit_iv"].get(seat, []), K["t"], N["t"] + 1)
            prs = [r for r in seq.get((g["game"], p_seat), []) if r["n"] <= K["n"] and r["score"] is not None]
            rec["partner_score"] = prs[-1]["score"] if prs else None
            rec["partner_lost"] = prs[-1]["score"] < LOST if prs else None
            rec["partner_mated"] = prs[-1]["score"] <= -MATE if prs else None
            if K.get("clocks"):
                ck = K["clocks"]
                idx = {"Awhite": 0, "Ablack": 1, "Bwhite": 2, "Bblack": 3}
                opp = {"Awhite": "Ablack", "Ablack": "Awhite", "Bwhite": "Bblack", "Bblack": "Bwhite"}[seat]
                rec["clock_own"] = ck[idx[seat]]
                rec["clock_gap"] = ck[idx[seat]] - ck[idx[opp]]
            # team's first fall is filled in after all seats are done
            # information that existed
            wb = None
            if true_w is not None:
                vp = true_w["values"].get(dec)
                if vp is not None:
                    better = [(m, v) for m, v in true_w["values"].items() if m != dec and clip(v) - clip(vp) >= 200]
                    if better:
                        m, v = max(better, key=lambda x: x[1])
                        cn = {c["move"]: c for c in cands(K)}
                        wb = {"move": m, "gain": clip(v) - clip(vp),
                              "cost_none": (clip(none_w["values"][dec]) - clip(none_w["values"][m]))
                              if none_w and m in none_w["values"] and dec in none_w["values"] else None,
                              "E_alt": cn.get(m, {}).get("E"), "E_play": cn.get(dec, {}).get("E"),
                              "is_main": m == main}
            rec["worlds_better"] = wb
            # seen before
            seen = 0
            if minus:
                top = max(minus, key=lambda t: PV[t])
                idxK = S.index(K)
                for r in S[max(0, idxK - 2):idxK]:
                    if any(minus_counter(k)[top] >= 1 and w["p"] >= 0.10 for k, w in world_vals(r).items()):
                        seen += 1
                rec["seen_before"] = seen
                rec["seen_before_of"] = len(S[max(0, idxK - 2):idxK])
                # world p at K for that piece (largest of any world holding it)
                rec["p_piece"] = max([w["p"] for k, w in world_vals(K).items() if minus_counter(k)[top] >= 1] or [0.0])
                # the partner's side of the capture that fed the opponent (most valuable piece)
                fi = max([x for x in arrived if x[1][0] == "-"], key=lambda x: PV[x[1][1]])[2]
                pr = [r for r in seq.get((g["game"], p_seat), []) if r["n"] <= fi]
                if pr:
                    P = pr[-1]
                    ppv = P.get("mainpv") or P.get("pv") or []
                    plays_line = bool(ppv) and ppv[0] == P["decision"] and not is_sit(P) and P["reason"] != "hold_mated"
                    # was the capture the reply to the partner's move? (next opponent ply on the partner board)
                    pboard = c3.c2.seat_board(p_seat)
                    nxt = [i for i in range(P["n"], len(g["toks"])) if g["toks"][i][0] == pboard]
                    reply_idx = nxt[1] if len(nxt) > 1 and g["toks"][nxt[0]][1:] == P["decision"] else (nxt[0] if nxt and is_sit(P) else None)
                    rec["partner_line"] = plays_line and len(ppv) > 1 and fi == reply_idx and ppv[1] == g["toks"][fi][1:]
                    rec["partner_capture_was_reply"] = fi == reply_idx
                    rec["partner_sat_then"] = is_sit(P) or P["reason"] == "hold_mated"
                    rec["partner_score_then"] = P["score"]
                    pc = cands(P)
                    chosen = next((c for c in pc if c["move"] == P["decision"]), None)
                    rec["partner_alt"] = bool(chosen and chosen.get("L") is not None and any(
                        c["move"] != P["decision"] and c.get("L") is not None and c["L"] >= chosen["L"] - 150 for c in pc))
                    rec["partner_decision"] = P["decision"]
                    rec["partner_n"] = P["n"]
                    rec["fatal_idx"] = fi
                    rec["fatal_move"] = g["toks"][fi]
                # a trade: our partner also took a piece in the step (it reached our hand)
                rec["trade_same"] = top in plus
                # could the seat have dodged at its two decisions before K? (the world holding that piece, max p)
                early = []
                for r in S[max(0, idxK - 2):idxK]:
                    wsr = [w for k, w in world_vals(r).items() if minus_counter(k)[top] >= 1]
                    if not wsr:
                        early.append(None)
                        continue
                    w = max(wsr, key=lambda w: w["p"])
                    vp = w["values"].get(r["decision"])
                    vb = max(w["values"].values()) if w["values"] else None
                    nw = world_vals(r).get("none")
                    alt = max(((m, v) for m, v in w["values"].items() if m != r["decision"]), key=lambda x: x[1], default=(None, None))
                    early.append({"p": w["p"], "v_play": vp, "v_best": vb, "alt": alt[0],
                                  "alt_cost_none": (clip(nw["values"][r["decision"]]) - clip(nw["values"][alt[0]]))
                                  if nw and alt[0] in nw["values"] and r["decision"] in nw["values"] else None})
                rec["early"] = early
            # switch gaps: main against played in "none" and in the world that came true
            if K["override"]:
                rec["sw_gap_none"] = (clip(none_w["values"][main]) - clip(none_w["values"][dec])
                                      if none_w and main in none_w["values"] and dec in none_w["values"] else None)
                rec["sw_gap_true"] = (clip(true_w["values"][main]) - clip(true_w["values"][dec])
                                      if true_w and main in true_w["values"] and dec in true_w["values"] else None)
            rec["legal"] = int(K["sumd"].get("legal", 0) or 0)
            rec["K_fc_prices"] = K.get("fc_prices") or {}
            # depth
            ds = N.get("dscores") or []
            rec["depth_seen"] = next((d for d, s in ds if s is not None and s < LOST), None)
            dk = [s for d, s in (K.get("dscores") or []) if s is not None]
            rec["fell_with_depth"] = len(dk) >= 4 and clip(dk[-1]) <= max(clip(x) for x in dk[-4:-1]) - 100
            rec["K_dscores"] = (K.get("dscores") or [])[-6:]
            rec["N_dscores"] = ds[-8:]
            out.append(rec)
    # the team's first fall in each game
    by_team = collections.defaultdict(list)
    for r in out:
        by_team[(r["match"], r["game"], r["team"])].append(r)
    for rs in by_team.values():
        fallen = [r for r in rs if r["cls"] != "none"]
        first = min(fallen, key=lambda r: (r["F_n"], r["F_t"])) if fallen else None
        for r in rs:
            r["team_first"] = r is first
            r["team_falls"] = len(fallen)
    return out


def main():
    args = sys.argv[1:]
    engine = "hb-l50"
    if args and args[0].startswith("hb-"):
        engine, args = args[0], args[1:]
    matches = args or c3.L50_MATCHES
    allrecs = []
    for m in matches:
        data = c3.load(m)
        recs = analyse(m, data, engine)
        allrecs += recs
        print(m, len(recs), "seats", sum(r["cls"] != "none" for r in recs), "falls", file=sys.stderr)
        del data
    tag = engine.replace("hb-", "")
    suffix = "" if matches == c3.L50_MATCHES else "_" + "+".join(matches)
    with open(os.path.join(HERE, f"falls_{tag}{suffix}.json"), "w") as f:
        json.dump(allrecs, f)


if __name__ == "__main__":
    main()
