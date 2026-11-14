#!/usr/bin/env python3
"""AUTOPSY3, base rates: how often a seat at -300 or better falls for good at its next decision, by feature,
and whether its own worlds forecast the fall. Logs only.

    nice -n 19 python3 hazard3.py [ENGINE] [MATCH ...]   -> hazard_<ENGINE>.txt (also printed)

Unit: a decision of ENGINE with a score of -300 or better that has a later decision. Event "falls": the
seat's next decision is its first lost-for-good decision (falls.py's F). Event "drops": the next score is
below -300 (whether or not it recovers).

forecast fall p: sum of p over the decision's scored worlds where the move played scored below -300
("none" included). Intervals: 95%, 2000 resamples of whole games.

Partner feeds: at each decision of the seat's partner that plays its line's first move, if the line's
second move (the opponent's reply on the partner board) captures a T, that T would reach our opponent.
The seat's measured price of one -T on its board (fc_prices of its last decision before) and whether the
seat fell for good within its next two decisions.
"""
import collections
import os
import random
import sys

import chess
import chess.variant

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common3 as c3  # noqa: E402

MATE = 90000
LOST = -300
clip = c3.clip
LET = {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q"}


def boot(per, B=2000, seed=7):
    rnd = random.Random(seed)
    gl = sorted(per)
    if not gl:
        return None, None, None
    n = sum(per[g][0] for g in gl)
    d = sum(per[g][1] for g in gl)
    if not d:
        return None, None, None
    bs = []
    for _ in range(B):
        s = rnd.choices(gl, k=len(gl))
        dd = sum(per[g][1] for g in s)
        if dd:
            bs.append(sum(per[g][0] for g in s) / dd)
    bs.sort()
    return n / d, bs[int(.025 * len(bs))], bs[int(.975 * len(bs)) - 1]


def fmt(est):
    e, lo, hi = est
    if e is None:
        return "-"
    return f"{100 * e:.1f}% ({100 * lo:.1f} to {100 * hi:.1f})"


def captured(fen, uci1, uci2):
    """type letter captured by uci2 after uci1 in the crazyhouse position fen, or None"""
    try:
        b = chess.variant.CrazyhouseBoard(fen)
        b.push(chess.Move.from_uci(uci1))
        m = chess.Move.from_uci(uci2)
        if m not in b.legal_moves or m.drop or not b.is_capture(m):
            return None
        if b.is_en_passant(m) or b.promoted & chess.BB_SQUARES[m.to_square]:
            return "P"
        return LET[b.piece_type_at(m.to_square)]
    except (ValueError, AssertionError, IndexError):
        return None


def units(match, data, engine):
    seq = c3.by_seat(data["rows"])
    out, feeds = [], []
    for g in data["games"]:
        for seat_key, name in g["seats"].items():
            if name != engine:
                continue
            seat = seat_key.replace("-", "")
            S = [r for r in seq.get((g["game"], seat), []) if r["score"] is not None]
            F = None
            for i in range(len(S) - 1, -1, -1):
                if S[i]["score"] < LOST:
                    F = i
                else:
                    break
            p_seat = c3.PARTNER[seat]
            P = [r for r in seq.get((g["game"], p_seat), []) if r["score"] is not None]
            pi = 0
            for i, r in enumerate(S[:-1]):
                if r["score"] < LOST:
                    continue
                while pi < len(P) and P[pi]["n"] <= r["n"]:
                    pi += 1
                pr = P[pi - 1] if pi else None
                co = r.get("coord") or {}
                ws = [w for w in co.get("worlds", []) if w.get("scored")]
                fp = sum(w["p"] for w in ws if w["values"].get(r["decision"]) is not None and w["values"][r["decision"]] < LOST)
                pq = max([w["p"] for w in ws if "-Q" in (w["arrival"] or "")] or [0.0])
                pany = sum(w["p"] for w in ws if "-" in (w["arrival"] or ""))
                f = r["feat"]
                out.append({"game": (match, g["game"]), "falls": F is not None and i + 1 == F,
                            "drops": S[i + 1]["score"] < LOST, "fp": fp, "has_worlds": bool(ws),
                            "in_check": bool(f.get("in_check")), "koff": f.get("krank", 0) >= 1,
                            "kzone3": (f.get("kzone_att") or 0) >= 3, "opp_hand6": (f.get("hand_opp") or 0) >= 6,
                            "opp_q": (f.get("opp_q") or 0) >= 1, "pq": pq, "pany": pany,
                            "partner_lost": pr is not None and pr["score"] < LOST,
                            "partner_won": pr is not None and pr["score"] > 300,
                            "switch": r["override"], "only": r["reason"] == "only_move",
                            "score": r["score"], "won": g["winner"] == c3.c2.seat_team(seat)})
            # partner feeds: decisions of the partner whose line's reply captures on the partner board
            si = 0
            for pr in P:
                ppv = pr.get("mainpv") or pr.get("pv") or []
                if len(ppv) < 2 or ppv[0] != pr["decision"] or pr["reason"] in ("hold_partner", "hold_feed", "stall_deny",
                                                                                  "voluntary_wait", "hold_mated"):
                    continue
                t = captured(pr["fen_own"], ppv[0], ppv[1])
                if not t:
                    continue
                while si < len(S) and S[si]["n"] <= pr["n"]:
                    si += 1
                if not si:
                    continue
                me = S[si - 1]
                if me["score"] < LOST:
                    continue
                price = (me.get("fc_prices") or {}).get("-" + t)
                # did the reply happen? next two plies on the partner board after pr.n
                pb = c3.c2.seat_board(p_seat)
                nxt = [x for x in g["toks"][pr["n"]:] if x[0] == pb][:2]
                happened = len(nxt) == 2 and nxt[0][1:] == ppv[0] and nxt[1][1:] == ppv[1]
                fell = F is not None and si - 1 < F <= si + 1
                # what the partner's line gains on its own board: its score (clipped)
                feeds.append({"game": (match, g["game"]), "T": t, "price": price, "happened": happened, "fell": fell,
                              "partner_score": pr["score"], "me_score": me["score"]})
    return out, feeds


def main():
    args = sys.argv[1:]
    engine = "hb-l50"
    if args and args[0].startswith("hb-"):
        engine, args = args[0], args[1:]
    matches = args or c3.L50_MATCHES
    U, FD = [], []
    for m in matches:
        d = c3.load(m)
        u, fd = units(m, d, engine)
        U += u
        FD += fd
        del d
    lines = [f"# Base rates for {engine}: {len(U)} decisions at -300 or better, {len({u['game'] for u in U})} games", ""]

    def rate(sel, key="falls"):
        per = collections.defaultdict(lambda: [0, 0])
        for u in sel:
            per[u["game"]][0] += u[key]
            per[u["game"]][1] += 1
        return {g: tuple(v) for g, v in per.items()}

    lines.append(f"all: n {len(U)}, falls for good next {fmt(boot(rate(U)))}, drops below -300 next {fmt(boot(rate(U, 'drops')))}")
    lines.append("")
    lines.append("| feature at the decision | n | falls for good at the next decision | without the feature |")
    lines.append("|---|---|---|---|")
    feats = [("in check", lambda u: u["in_check"]), ("king off its home rank", lambda u: u["koff"]),
             ("3+ king-zone squares attacked", lambda u: u["kzone3"]), ("opponent's hand worth 6+", lambda u: u["opp_hand6"]),
             ("opponent holds a queen", lambda u: u["opp_q"]), ("a world with -Q at p>=0.2", lambda u: u["pq"] >= 0.2),
             ("worlds giving the opponent a piece, p sum >= 0.5", lambda u: u["pany"] >= 0.5),
             ("partner's board below -300", lambda u: u["partner_lost"]), ("partner's board above +300", lambda u: u["partner_won"]),
             ("switched away from the main move", lambda u: u["switch"]), ("only move", lambda u: u["only"]),
             ("score -300 to -100", lambda u: u["score"] < -100), ("score -100 to +100", lambda u: -100 <= u["score"] <= 100),
             ("score above +100", lambda u: u["score"] > 100)]
    for name, fn in feats:
        a = [u for u in U if fn(u)]
        b = [u for u in U if not fn(u)]
        lines.append(f"| {name} | {len(a)} | {fmt(boot(rate(a)))} | {fmt(boot(rate(b)))} |")
    lines.append("")
    lines.append("## Does the seat's own forecast of a fall come true?")
    lines.append("")
    lines.append("forecast fall p: the sum of p of its scored worlds in which the move played is below -300. Decisions with scored worlds.")
    lines.append("")
    lines.append("| forecast fall p | n | mean forecast | drops below -300 at the next decision | falls for good |")
    lines.append("|---|---|---|---|---|")
    W = [u for u in U if u["has_worlds"]]
    for lo, hi in ((0, .001), (.001, .1), (.1, .2), (.2, .35), (.35, .5), (.5, .75), (.75, 1.01)):
        s = [u for u in W if lo <= u["fp"] < hi]
        mf = sum(u["fp"] for u in s) / len(s) if s else 0
        lines.append(f"| {lo:.3f}-{min(hi, 1):.2f} | {len(s)} | {mf:.3f} | {fmt(boot(rate(s, 'drops')))} | {fmt(boot(rate(s)))} |")
    lines.append("")
    lines.append(f"Decisions without scored worlds: {len(U) - len(W)}, falls for good next {fmt(boot(rate([u for u in U if not u['has_worlds']])))}")
    lines.append("")
    lines.append("## Partner feeds: the partner's line hands a piece to our opponent")
    lines.append("")
    lines.append("Partner decisions that played their line's first move with a capture as the line's reply, while our seat "
                 "was at -300 or better. Price: our seat's measured cost of one more such piece in its opponent's hand "
                 "(fc_prices; missing when our forecast did not measure it). Fell: our seat fell for good within its next "
                 "two decisions.")
    lines.append("")
    lines.append("| piece | our price | n | the reply was played | fell, when played | fell, when not played |")
    lines.append("|---|---|---|---|---|---|")
    for t in "QRBNP":
        for name, fn in (("missing", lambda x: x["price"] is None), ("< 200", lambda x: x["price"] is not None and x["price"] < 200),
                         ("200-499", lambda x: x["price"] is not None and 200 <= x["price"] < 500),
                         (">= 500", lambda x: x["price"] is not None and x["price"] >= 500)):
            s = [x for x in FD if x["T"] == t and fn(x)]
            if not s:
                continue
            hp = [x for x in s if x["happened"]]
            nh = [x for x in s if not x["happened"]]

            def r_(sel):
                per = collections.defaultdict(lambda: [0, 0])
                for x in sel:
                    per[x["game"]][0] += x["fell"]
                    per[x["game"]][1] += 1
                return fmt(boot({g: tuple(v) for g, v in per.items()}))
            lines.append(f"| {t} | {name} | {len(s)} | {len(hp)} | {r_(hp)} | {r_(nh)} |")
    text = "\n".join(lines)
    tag = engine.replace("hb-", "")
    suffix = "" if matches == c3.L50_MATCHES else "_" + "+".join(matches)
    open(os.path.join(HERE, f"hazard_{tag}{suffix}.txt"), "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
