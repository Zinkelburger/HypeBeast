#!/usr/bin/env python3
"""Replay decided bughouse games from results.jsonl and describe how the loser lost.

usage: losses.py MATCH_DIR [OUT_JSON]
Reads logs only. Every game is analysed from the losing team's side, then grouped
by which engine lost, so each engine's losses act as the control for the other's.
"""
import collections
import json
import statistics
import sys

import chess
import chess.variant

TEAM = {"white": ("A-white", "B-black"), "black": ("A-black", "B-white")}
NAMES = {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q"}


def seat_of(board, color):
    return f"{board}-{'white' if color else 'black'}"


def pocket(b, color):
    return {p: b.pockets[color].count(p) for p in NAMES}


class Replay:
    """Two crazyhouse boards, with captures sent to the partner's hand."""

    def __init__(self, dual_fen):
        assert dual_fen is None, "only standard starts handled"
        self.b = {"A": chess.variant.CrazyhouseBoard(), "B": chess.variant.CrazyhouseBoard()}

    def push(self, bd, uci):
        board = self.b[bd]
        other = self.b["B" if bd == "A" else "A"]
        mover = board.turn
        move = chess.Move.from_uci(uci)
        before = pocket(board, mover)
        victim = board.piece_at(move.to_square) if not move.drop else None
        ep = board.is_en_passant(move) if not move.drop else False
        board.push(move)
        after = pocket(board, mover)
        captured = None
        for p in NAMES:
            gained = after[p] - before[p]
            if gained > 0:
                captured = p
                board.pockets[mover].remove(p)
                # the captured piece has the victim's colour, which the partner plays
                other.pockets[not mover].add(p)
        return {"mover": mover, "drop": move.drop, "captured": captured,
                "victim": victim, "ep": ep, "to": move.to_square}


def bad(ev):
    return ev is not None and "mate" in ev and ev["mate"] < 0


def good(ev):
    return ev is not None and "mate" in ev and ev["mate"] > 0


def cp(ev):
    if ev is None:
        return None
    if "mate" in ev:
        return 30000 if ev["mate"] > 0 else -30000
    return ev["cp"]


def analyse(r):
    res = r["result"]
    winner = res["winner"]
    if winner not in TEAM:
        return None
    loser_team = "black" if winner == "white" else "white"
    loser_seats = TEAM[loser_team]
    loser_engine = r["seats"][loser_seats[0]]
    rp = Replay(r["opening"]["dual_fen"])
    opening = r["opening"]["moves"]
    for m in opening:
        rp.push("A" if m[0] == "1" else "B", m[1:])

    events = res["events"]
    timeline = []  # every event, with the state after it
    for e in events:
        rec = dict(e)
        if e["kind"] == "move":
            info = rp.push(e["board"], e["uci"])
            rec.update(info)
            rec["hands"] = {bd: {c: pocket(rp.b[bd], c) for c in (True, False)} for bd in "AB"}
            rec["mated_now"] = rp.b[e["board"]].is_checkmate()
        timeline.append(rec)

    moves = [t for t in timeline if t["kind"] == "move"]
    out = {"game": r["game"], "pair": r["pair"], "loser": loser_engine, "termination": res["termination"],
           "loser_team": loser_team, "duration_ms": res["duration_ms"]}

    if res["termination"] == "flag":
        flag = next(t for t in timeline if t["kind"] == "flag")
        out["flag_seat"] = flag["seat"]
        out["flag_is_loser"] = flag["seat"] in loser_seats
        M = flag["seat"]
        out["mating"] = None
    else:
        last = moves[-1]
        if not last["mated_now"]:
            out["replay_mismatch"] = True
        bd = last["board"]
        M = seat_of(bd, not last["mover"])
        out["mating"] = {"seat": last["seat"], "uci": last["uci"],
                         "drop": NAMES.get(last["drop"]) if last["drop"] else None}
    out["mated_seat"] = M
    bd = M[0]
    other_bd = "B" if bd == "A" else "A"
    P = next(s for s in loser_seats if s != M)
    W = seat_of(bd, M.endswith("black"))  # opponent on the same board
    WP = next(s for s in TEAM[winner] if s != W)
    out.update(M=M, P=P, W=W, WP=WP)

    # decisions of the mated seat (moves and sits that carry an evaluation)
    dec = [(i, t) for i, t in enumerate(timeline)
           if t.get("seat") == M and t["kind"] in ("move", "sit") and t.get("eval") is not None]
    # final streak of "mated by force" on that seat
    k = len(dec)
    while k > 0 and bad(dec[k - 1][1]["eval"]):
        k -= 1
    out["mated_decisions"] = len(dec) - k
    if k < len(dec):
        i_seen, seen = dec[k]
        out["seen_t"] = seen["t"]
        out["seen_mate"] = seen["eval"]["mate"]
        out["seen_clocks"] = seen["clocks"]
        out["seen_ply"] = sum(1 for t in timeline[:i_seen] if t["kind"] == "move")
        out["sec_seen_to_end"] = (res["duration_ms"] - seen["t"]) / 1000
        if k > 0:
            i_prev, prev = dec[k - 1]
            out["prev_eval"] = cp(prev["eval"])
            out["prev_kind"] = prev["kind"]
            out["prev_uci"] = prev.get("uci")
            between = timeline[i_prev + 1:i_seen]
            bm = [t for t in between if t["kind"] == "move"]
            on_board = [t for t in bm if t["board"] == bd and t["seat"] == W]
            caps_other = [t for t in bm if t["board"] == other_bd and t["seat"] == WP and t["captured"]]
            out["between_opp_moves"] = [t["uci"] for t in on_board]
            out["between_opp_drop"] = any(t["drop"] for t in on_board)
            out["between_feed_captures"] = [NAMES[t["captured"]] for t in caps_other]
        else:
            out["prev_eval"] = None
        # who saw the mate first on this board
        w_dec = [(i, t) for i, t in enumerate(timeline)
                 if t.get("seat") == W and t["kind"] in ("move", "sit") and t.get("eval") is not None]
        j = len(w_dec)
        while j > 0 and good(w_dec[j - 1][1]["eval"]):
            j -= 1
        if j < len(w_dec):
            out["w_seen_t"] = w_dec[j][1]["t"]
            out["w_seen_mate"] = w_dec[j][1]["eval"]["mate"]
            out["w_saw_first"] = w_dec[j][1]["t"] < seen["t"]
            out["m_decisions_after_w_saw"] = sum(
                1 for _, t in dec if w_dec[j][1]["t"] <= t["t"] < seen["t"])
        # partner's standing when the mate was first seen
        pe = [t for t in timeline[:i_seen + 1]
              if t.get("seat") == P and t.get("eval") is not None]
        out["partner_eval_at_seen"] = cp(pe[-1]["eval"]) if pe else None
        # clock: seen_clocks order is A-white, A-black, B-white, B-black
        order = ["A-white", "A-black", "B-white", "B-black"]
        c = dict(zip(order, seen["clocks"]))
        out["clock_M_minus_W_s"] = (c[M] - c[W]) / 1000
        out["clock_P_minus_WP_s"] = (c[P] - c[WP]) / 1000

    # the loser ever winning
    loser_ev = [t for t in timeline if t.get("seat") in loser_seats and t.get("eval") is not None]
    out["loser_ever_mate"] = any(good(t["eval"]) for t in loser_ev)
    out["loser_max_cp"] = max((cp(t["eval"]) for t in loser_ev), default=None)
    out["loser_had_mate_seats"] = sorted({t["seat"] for t in loser_ev if good(t["eval"])})
    # a mate claimed, then lost: last claim of a forced mate and how the game then went
    claims = [t for t in loser_ev if good(t["eval"])]
    if claims:
        out["last_claim_mate"] = claims[-1]["eval"]["mate"]
        out["last_claim_sec_before_end"] = (res["duration_ms"] - claims[-1]["t"]) / 1000

    # the mating piece: was it in hand at the mated seat's last decision?
    if out["mating"] and out["mating"]["drop"]:
        last = moves[-1]
        piece = last["drop"]
        wcolor = last["mover"]
        m_moves = [t for t in moves if t["seat"] == M]
        if m_moves:
            hand = m_moves[-1]["hands"][bd][wcolor]
            out["piece_in_hand_at_last_move"] = hand[piece] > 0
        # the capture that supplied it: latest capture of this piece type by WP
        feeds = [(n, t) for n, t in enumerate(moves[:-1])
                 if t["seat"] == WP and t["captured"] == piece]
        if feeds:
            n, f = feeds[-1]
            out["feed"] = {"uci": f["uci"], "t": f["t"], "piece": NAMES[piece],
                           "sec_before_end": (res["duration_ms"] - f["t"]) / 1000}
            p_prior = [t for t in moves[:n] if t["seat"] == P]
            p_after = [t for t in moves[n + 1:] if t["seat"] == P]
            if p_prior:
                out["feed"]["partner_prior_uci"] = p_prior[-1]["uci"]
                out["feed"]["partner_prior_eval"] = cp(p_prior[-1]["eval"])
            if p_after:
                out["feed"]["recaptured"] = (p_after[0]["to"] == f["to"] and p_after[0]["captured"] is not None)
            # the piece that was taken: did the partner just move it there?
            if p_prior:
                out["feed"]["took_piece_partner_just_moved"] = p_prior[-1]["to"] == f["to"]
                out["feed"]["took_piece_partner_just_dropped"] = (
                    p_prior[-1]["to"] == f["to"] and p_prior[-1]["drop"] is not None)
    # sitting
    out["loser_sit_ms"] = res["sit_ms"][loser_team]
    out["winner_sit_ms"] = res["sit_ms"][winner]
    out["clocks_end"] = res["clocks_ms"]
    return out


def pct(n, d):
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "0/0"


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def report(name, g):
    print(f"\n=== {name} lost {len(g)} games ===")
    term = collections.Counter(x["termination"] for x in g)
    print("termination:", dict(term))
    mate = [x for x in g if x["mating"]]
    drops = [x for x in mate if x["mating"]["drop"]]
    print("mate by drop:", pct(len(drops), len(mate)), collections.Counter(x["mating"]["drop"] for x in drops))
    inhand = [x for x in drops if "piece_in_hand_at_last_move" in x]
    print("  piece already in hand at mated seat's last move:",
          pct(sum(x["piece_in_hand_at_last_move"] for x in inhand), len(inhand)))
    print("  mismatches:", sum(1 for x in g if x.get("replay_mismatch")))
    seen = [x for x in g if "seen_t" in x]
    print("mated seat saw a forced mate before the end:", pct(len(seen), len(g)))
    print("  mate length when first seen:", sorted(collections.Counter(-x["seen_mate"] for x in seen).items()))
    print("  median seconds of game from seen to end:", med([x["sec_seen_to_end"] for x in seen]))
    print("  median ply when seen:", med([x["seen_ply"] for x in seen]))
    prev = [x for x in seen if x.get("prev_eval") is not None]
    print("eval at the seat's decision just before it saw mate:")
    for lo, hi, lab in [(200, 40000, ">= +200 (thought it was better)"), (-200, 200, "-200..+200 (level)"),
                        (-800, -200, "-800..-200 (worse)"), (-40000, -800, "<= -800 (already lost)")]:
        n = sum(1 for x in prev if lo <= x["prev_eval"] < hi)
        print(f"  {lab}: {pct(n, len(prev))}")
    sudden = [x for x in prev if x["prev_eval"] >= -200]
    print("of those at >= -200, what arrived between the two decisions:")
    print("  opponent fed a capture on the other board:",
          pct(sum(1 for x in sudden if x["between_feed_captures"]), len(sudden)))
    print("  opponent dropped on this board:",
          pct(sum(1 for x in sudden if x["between_opp_drop"]), len(sudden)))
    print("  neither (same information, search did not see it):",
          pct(sum(1 for x in sudden if not x["between_feed_captures"] and not x["between_opp_drop"]), len(sudden)))
    ws = [x for x in seen if "w_saw_first" in x]
    print("the mating side saw the mate first:", pct(sum(x["w_saw_first"] for x in ws), len(ws)))
    print("  median of the mated seat's decisions made after the opponent saw it, before it did:",
          med([x["m_decisions_after_w_saw"] for x in ws]))
    pe = [x for x in seen if x.get("partner_eval_at_seen") is not None]
    print("partner's own eval when the mate was first seen:")
    for lo, hi, lab in [(800, 40000, ">= +800 or mating"), (200, 800, "+200..+800"), (-200, 200, "level"),
                        (-800, -200, "worse"), (-40000, -800, "lost or mated")]:
        n = sum(1 for x in pe if lo <= x["partner_eval_at_seen"] < hi)
        print(f"  {lab}: {pct(n, len(pe))}")
    print("clock when seen, median seconds: mated seat minus its opponent",
          med([x["clock_M_minus_W_s"] for x in seen]),
          "| partner minus its opponent", med([x["clock_P_minus_WP_s"] for x in seen]))
    print("loser's team ever claimed a forced mate:", pct(sum(x["loser_ever_mate"] for x in g), len(g)))
    print("  loser's best eval >= +500 at some point:",
          pct(sum(1 for x in g if (x["loser_max_cp"] or -1e9) >= 500), len(g)))
    claim = [x for x in g if "last_claim_sec_before_end" in x]
    print("  median seconds before the end of the last such claim:", med([x["last_claim_sec_before_end"] for x in claim]))
    feeds = [x["feed"] for x in drops if "feed" in x]
    print("supply capture of the mating piece:", len(feeds))
    print("  median seconds before the end:", med([f["sec_before_end"] for f in feeds]))
    print("  partner recaptured on that square next:", pct(sum(1 for f in feeds if f.get("recaptured")), len(feeds)))
    print("  took a piece the partner had just moved/dropped there:",
          pct(sum(1 for f in feeds if f.get("took_piece_partner_just_moved")), len(feeds)),
          "dropped:", pct(sum(1 for f in feeds if f.get("took_piece_partner_just_dropped")), len(feeds)))
    print("  partner's eval on the move before the capture, median:", med([f.get("partner_prior_eval") for f in feeds]))
    print("sit ms, median: loser", med([x["loser_sit_ms"] for x in g]), "winner", med([x["winner_sit_ms"] for x in g]))
    print("duration s, median:", med([x["duration_ms"] / 1000 for x in g]))


def main():
    d = sys.argv[1]
    rs = [json.loads(l) for l in open(f"{d}/results.jsonl")]
    rows = []
    for r in rs:
        try:
            a = analyse(r)
        except Exception as exc:  # report, never hide, a game that will not replay
            print("REPLAY FAILED game", r["game"], repr(exc))
            continue
        if a:
            rows.append(a)
    print("games", len(rs), "analysed", len(rows))
    by = collections.defaultdict(list)
    for a in rows:
        by[a["loser"]].append(a)
    for name, g in sorted(by.items()):
        report(name, g)
    if len(sys.argv) > 2:
        json.dump(rows, open(sys.argv[2], "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
