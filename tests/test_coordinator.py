"""Coordinator (PLAN.md 5.1-5.4) fixtures on crafted two-board positions.

    python3 tests/test_coordinator.py
"""

from __future__ import annotations

import json
import sys

import chess

from hbutil import Bughouse, Engine, parse_bestmove, summary_fields

failures = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"[{'ok' if ok else 'FAIL'}] {what}" + (f": {detail}" if detail else ""))


def coord(e: Engine, fen_a: str, fen_b: str, go: str = "go movetime 1000", clocks=None, adv=False):
    if clocks:
        e.setoption("Clocks", ",".join(map(str, clocks)))
    e.setoption("TimeAdvantage", "true" if adv else "false")
    e.send(f"position fen {fen_a}|{fen_b}")
    lines = e.go(go)
    report = None
    for l in lines:
        if l.startswith("info string hb_coord "):
            report = json.loads(l[len("info string hb_coord "):])
    wake = [l for l in lines if l.startswith("info string hb_wake_after_ms=")]
    return lines, report, summary_fields(lines), wake


def cand(report: dict, move: str) -> dict | None:
    return next((c for c in report.get("candidates", []) if c["move"] == move), None)


def stm(fen: str) -> str:
    return fen.split()[1]


def pocket(fen: str) -> str:
    return fen.split("[", 1)[1].split("]", 1)[0]


def run(worlds: bool) -> None:
    """worlds=False checks the v3 rule (HBWorlds off); worlds=True the v4 one."""
    mode = {"HBWorlds": "true" if worlds else "false"}
    print(f"--- HBWorlds={mode['HBWorlds']}")
    e = Engine(options={"Seat": "Awhite", "Team": "white", **mode})

    # 1. Delivery outside the local top three: Rxa6 loses the exchange
    # locally but gives the partner N@f2 mate on board B.
    A1 = "4k3/1p6/n7/8/8/R7/5PPP/4K3[] w - - 0 1"
    B1 = "k7/8/8/8/8/8/6PP/6RK[] b - - 0 1"
    lines, rep, s, _ = coord(e, A1, B1)
    check(parse_bestmove(lines)[0] == "a3a6" and rep["reason"].startswith("delivery_win"),
          "verified delivery win is played at once", f"{parse_bestmove(lines)} reason={rep['reason']}")
    if not worlds:
        # The same capture with the partner not on turn is not a verified win: it
        # is only a candidate, and prices put its value into L (S has no F term).
        B1w = "k7/8/8/8/8/8/6PP/6RK[] w - - 0 1"
        lines, rep, s, _ = coord(e, A1, B1w)
        c = cand(rep, "a3a6")
        check(c is not None and c["delivery"] == "N" and c["F"] is not None and c["F"] > 0,
              "delivery is a candidate when the partner is not on turn",
              f"{c and {k: c[k] for k in ('source', 'L', 'F', 'S')}} reason={rep['reason']}")
        check(c is not None and s.get("prices") == "1" and c["S"] == c["L"] + max(-400, int(c["R"] / 2)),
              "S = L + bounded R/2 with prices on", f"{c and (c['L'], c['R'], c['S'])}")
        main_c = rep["candidates"][0]
        check(main_c["source"] == "main" and rep["reason"] in ("kept_main", "override")
              and (rep["reason"] == "override") == (max(x["S"] for x in rep["candidates"][1:]) >= main_c["S"] + 20),
              "20 cp switch rule applied", f"reason={rep['reason']} S_main={main_c['S']}")

    A2 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R[] w KQkq - 2 3"
    B2 = "k7/8/8/8/8/n1n5/1P1r4/4K3[] w - - 0 1"
    B3 = "4k3/1p1R4/N1N5/8/8/8/8/K7[] b - - 0 1"
    if not worlds:
        # 2/4. Enemy arrival threats and mutually exclusive donor outcomes.
        # White to move on B (the opponents' partner) can take a rook (Kxd2)
        # or a knight (bxa3 / bxc3: identical hand addition, deduplicated).
        lines, rep, s, _ = coord(e, A2, B2)
        ok_excl = True
        ok_turn = True
        detail = ""
        any_threat = False
        for c in rep["candidates"]:
            sc = c["scenarios"]
            arrivals = [x["arrival"] for x in sc]
            if not c["enemy_donor"] or arrivals != ["none", "r", "n"]:
                ok_excl = False
                detail = f"{c['move']} arrivals={arrivals}"
            base = pocket(sc[0]["fen"])
            for x in sc[1:]:
                # exactly one piece added to the no-arrival hand, never combined
                if sorted(pocket(x["fen"])) != sorted(base + x["arrival"]):
                    ok_excl = False
                    detail = f"{c['move']} pocket {pocket(x['fen'])!r} vs {base!r}+{x['arrival']}"
            knight = next((x for x in sc if x["arrival"] == "n"), None)
            if not knight or sorted(knight["donors"]) != ["b2a3", "b2c3"]:
                ok_excl = False
                detail = f"{c['move']} knight donors={knight and knight['donors']}"
            ok_turn &= all(stm(x["fen"]) == "b" for x in sc)
            any_threat |= c["R"] is not None and c["R"] < 0
        check(ok_excl, "exclusive donor outcomes: one scenario per distinct arrival, deduped donors", detail)
        check(ok_turn, "scenario probes keep the receiver's turn (opponent to move)")
        check(any_threat and all(c["R"] is None or c["R"] <= 0 for c in rep["candidates"]),
              "enemy arrival threats give R <= 0 (some < 0)",
              str([(c["move"], c["R"]) for c in rep["candidates"]]))
        check(int(s["scen_dedup"]) == len(rep["candidates"]), "dedup counter", s["scen_dedup"])

        # 3. Unavailable friendly supply: the partner (black on B) is to move and
        # can capture; friendly scenarios are counted but add no upside.
        lines, rep, s, _ = coord(e, A2, B3)
        ok = all(not c["enemy_donor"] and c["friendly_scenarios"] == 3 and c["scenarios"] == [] and c["R"] == 0
                 for c in rep["candidates"])
        check(ok and int(s["scen_friendly"]) == 3 * len(rep["candidates"]) and s["scen_enemy"] == "0",
              "friendly supply: no probes, R=0, no speculative upside",
              f"friendly={s['scen_friendly']} enemy={s['scen_enemy']}")

        # 5. Score perspective on both boards, partner or opponent to move.
        A5 = "4k3/8/8/7q/5N2/8/8/4K3[] w - - 0 1"         # Nxh5 sends a queen
        for name, fb in (("partner to move", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR[] b KQkq - 0 1"),
                         ("opponent to move", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1")):
            lines, rep, s, _ = coord(e, A5, fb)
            f = rep.get("partner_probes", {}).get("Q")
            check(f is not None and f > 300, f"board A seat, partner board {name}: F(Q) > 0 for our team",
                  f"F(Q)={f} base={rep.get('partner_base')}")
        e.setoption("Seat", "Bblack")
        e.setoption("Team", "white")
        B5 = "4k3/8/8/7Q/5n2/8/8/4K3[] b - - 0 1"         # Nxh5 sends a queen to white on A
        for name, fa in (("partner to move", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1"),
                         ("opponent to move", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR[] b KQkq - 0 1")):
            lines, rep, s, _ = coord(e, fa, B5)
            f = rep.get("partner_probes", {}).get("Q")
            main_l = rep["candidates"][0]["L"]
            check(f is not None and f > 300 and main_l is not None and main_l > 0,
                  f"board B seat, partner board {name}: F(Q) > 0 and L from our side",
                  f"F(Q)={f} L(main)={main_l} move={rep['candidates'][0]['move']}")
        e.setoption("Seat", "Awhite")
        e.setoption("Team", "white")

    # 6. Partial coverage / expiry keeps the main choice (no override).
    for go in ("go nodes 2500", "go movetime 15", "go nodes 1"):
        lines, rep, s, _ = coord(e, A2, B2, go)
        a, b = parse_bestmove(lines)
        legal = a in Bughouse(A2, B2).legal_moves(0)
        check(legal and s.get("override") == "0" and rep["reason"] in
              ("partial_coverage", "compare_incomplete", "single_candidate", "main_incomplete", "kept_main"),
              f"{go}: falls back to the main choice", f"{a} reason={rep['reason']} "
              f"probes={s.get('probes_completed')}/{s.get('probes_required')} depth={s.get('main_depth')}")

    # 8 (v2). Exposure veto: trading queens on B (Qxd1+ Kxd1) feeds black
    # on A a queen for Q@g1/Q@a1 mate; v2 must pick a move that does not.
    AX = "6rk/8/8/8/8/8/7P/7K[] b - - 0 1"
    BX = "4k3/8/8/8/8/8/3q4/3QK3[] b - - 0 1"
    e.setoption("Seat", "Bblack")
    e.setoption("Team", "white")
    lines, rep, s, _ = coord(e, AX, BX)
    if "exposed" not in s:
        print("[skip] exposure veto (binary predates v2)")
    else:
        move = parse_bestmove(lines)[1]
        g = Bughouse(AX, BX)
        g.push(1, move)
        fed_mate = False
        for r in g.legal_moves(1):
            t = Bughouse._captured_type(g.boards[1], chess.Move.from_uci(r))
            if not t:
                continue
            g2 = g.copy()
            g2.push(1, r)
            for d in g2.legal_moves(0):
                if d.startswith(chess.piece_symbol(t).upper() + "@"):
                    g3 = g2.copy()
                    g3.push(0, d)
                    fed_mate |= g3.is_checkmate(chess.WHITE, False)
        main_safe = rep["candidates"][0]["exposed"] == ""
        check(not fed_mate and (rep["reason"] == "exposure_veto" or main_safe),
              "v2 exposure veto avoids feeding a mating queen", f"{move} reason={rep['reason']} veto={s.get('veto')}")
        prices = next((json.loads(l[len("info string hb_prices "):]) for l in lines
                       if l.startswith("info string hb_prices ")), None)
        check(prices is not None and prices["theirs"]["Q"] == 1500 and prices["ours"]["Q"] < 1500,
              "feed prices: a queen that mates the partner board is priced as fatal", str(prices))
        # Upstream only prints hashfull on searches over 3 seconds.
        e.setoption("Seat", "Awhite")
        long_lines, *_ = coord(e, A2, B2, "go movetime 4500")
        full = [int(l.split(" hashfull ")[1].split()[0]) for l in long_lines if " hashfull " in l]
        check(bool(full) and max(full) < 500, "hash is not overloaded on a long search", f"max hashfull {max(full, default=None)}")

    def fed_mate_after(fa: str, fb: str, move: str) -> bool:
        """Our A move, then an opponent capture on B, then a mating drop on A."""
        g = Bughouse(fa, fb)
        g.push(0, move)
        for r in g.legal_moves(1):
            t = Bughouse._captured_type(g.boards[1], chess.Move.from_uci(r))
            if not t:
                continue
            g2 = g.copy()
            g2.push(1, r)
            for d in g2.legal_moves(0):
                if d.startswith(chess.piece_symbol(t).upper() + "@"):
                    g3 = g2.copy()
                    g3.push(0, d)
                    if g3.is_checkmate(chess.WHITE, False):
                        return True
        return False

    # 9. Direction 2: white on B is on turn and can take our queen. Black on A
    # can use it as soon as our A move hands black the turn: only moves that
    # keep the rook on the second rank stop Q@g2 mate.
    e.setoption("Seat", "Awhite")
    e.setoption("Team", "white")
    e.send("ucinewgame")
    BD = "4k3/8/8/8/8/8/3q4/3QK3[] w - - 0 1"
    AD = "6rk/8/8/8/8/8/R6P/7K[] w - - 0 1"
    lines, rep, s, _ = coord(e, AD, BD)
    move = parse_bestmove(lines)[0]
    check(not fed_mate_after(AD, BD, move), "direction 2: avoids the partner-board feed",
          f"{move} reason={rep['reason']} tiers={[(c['move'], c['tier']) for c in rep.get('candidates', [])]}")

    # 10. Stalling. Both legal moves allow the fed mate. Our clock beats the
    # white seat on B by 10 s, so we sit; black on A cannot drop until we move.
    # White is also mated on A by force, so with HBHold on it would sit for
    # that reason first: these check the stall rule on its own.
    AS = "6rk/8/8/8/8/8/7P/7K[] w - - 0 1"
    ahead = (60000, 60000, 50000, 60000)
    e.setoption("HBHold", "false")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AS, BD, "go movetime 1000", ahead, adv=True)
    check(parse_bestmove(lines)[0] == "pass" and s.get("reason") == "stall_deny"
          and wake == ["info string hb_wake_after_ms=52000"],
          "stall: sits with a clock lead when every move allows the fed mate",
          f"{parse_bestmove(lines)} reason={s.get('reason')} wake={wake}")
    lines, rep, s, wake = coord(e, AS, BD, "go movetime 1000", (55000, 60000, 45000, 60000), adv=True)
    check(parse_bestmove(lines)[0] == "pass" and s.get("wait") == "stall_continue",
          "stall: holds without a new search while nothing has moved", f"wait={s.get('wait')}")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AS, BD, "go movetime 1000", (50000, 60000, 50000, 60000), adv=False)
    check(parse_bestmove(lines)[0] != "pass", "stall: no lead, no stall", f"{parse_bestmove(lines)} reason={s.get('reason')}")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AS, BD, "go movetime 1000", (7000, 60000, 1000, 60000), adv=True)
    check(parse_bestmove(lines)[0] != "pass", "stall: keeps a clock reserve", f"{parse_bestmove(lines)} reason={s.get('reason')}")
    e.setoption("HBStall", "false")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AS, BD, "go movetime 1000", ahead, adv=True)
    check(parse_bestmove(lines)[0] != "pass", "stall: HBStall=false never sits", f"{parse_bestmove(lines)}")
    e.setoption("HBStall", "true")
    e.setoption("HBHold", "true")

    # 12. Holding (v5). Every white move on A allows Qxd2 on B and Q@g2 mate,
    # and white is not otherwise lost. With no move to play, sitting needs no
    # clock lead; a lead is still needed when a poorer move is available.
    AX = "6rk/8/8/8/8/8/PPP4P/N6K[] w - - 0 1"
    level = (50000, 60000, 50000, 60000)
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AX, BD, "go movetime 1000", level, adv=False)
    check(parse_bestmove(lines)[0] == "pass" and s.get("reason") == "stall_deny",
          "hold: every move loses to the fed mate, so sit without a clock lead",
          f"{parse_bestmove(lines)} reason={s.get('reason')}")
    e.setoption("HBHold", "false")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AX, BD, "go movetime 1000", level, adv=False)
    check(parse_bestmove(lines)[0] != "pass", "hold: HBHold=false keeps the v4 lead rule",
          f"{parse_bestmove(lines)} reason={s.get('reason')}")
    e.setoption("HBHold", "true")

    # Mated by force on A (rook against a bare king and pawn), nothing wrong
    # on B: sit until the clock only covers the moves left, then play.
    BQ = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1"
    even = (60000, 60000, 60000, 60000)
    # The seat it races on the other board (same colour) is 30 s ahead: it
    # can stop that board whatever we do, so sitting gives nothing away.
    behind = (30000, 60000, 60000, 60000)
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AS, BQ, "go movetime 1000", behind, adv=False)
    floor = 30000 - int(wake[0].split("=")[1]) if wake else None
    check(parse_bestmove(lines)[0] == "pass" and s.get("reason") == "hold_mated"
          and floor is not None and 400 <= floor <= 15000,
          "hold: a seat mated by force sits", f"{parse_bestmove(lines)} reason={s.get('reason')} wake={wake}")
    lines, rep, s, wake = coord(e, AS, BQ, "go movetime 1000", (25000, 60000, 60000, 60000), adv=False)
    check(parse_bestmove(lines)[0] == "pass" and s.get("wait") == "hold_continue" and s.get("main_nodes") == "0",
          "hold: goes on without a new search while its board is the same",
          f"wait={s.get('wait')} main_nodes={s.get('main_nodes')}")
    # v6: level clocks. Sitting is what would give that seat its lead, so a
    # seat with more than one move left plays the mate out. A lead of 2 s is
    # gone after one move of ours, and this mate is longer than that.
    for name, clocks in (("level clocks", even), ("2 s behind", (60000, 60000, 62000, 60000))):
        e.send("ucinewgame")
        lines, rep, s, wake = coord(e, AS, BQ, "go movetime 1000", clocks, adv=False)
        check(parse_bestmove(lines)[0] != "pass" and s.get("reason") == "mated_play_on",
              f"hold: {name}, a mated seat plays on", f"{parse_bestmove(lines)} reason={s.get('reason')}")
    e.setoption("HBPlayOn", "false")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AS, BQ, "go movetime 1000", even, adv=False)
    check(parse_bestmove(lines)[0] == "pass" and s.get("reason") == "hold_mated",
          "hold: HBPlayOn=false sits as v5 did", f"{parse_bestmove(lines)} reason={s.get('reason')}")
    e.setoption("HBPlayOn", "true")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AS, BQ, "go movetime 1000", (60000, 60000, 15000, 60000), adv=False)
    check(parse_bestmove(lines)[0] == "pass" and s.get("reason") == "hold_mated",
          "hold: sits when that seat is too short of time to wait", f"{parse_bestmove(lines)} reason={s.get('reason')}")
    lines, rep, s, wake = coord(e, AS, BQ, "go movetime 1000", (3500, 60000, 60000, 60000), adv=False)
    check(parse_bestmove(lines)[0] != "pass", "hold: plays when the clock is down to the floor",
          f"{parse_bestmove(lines)} reason={s.get('reason')}")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AS.replace("[]", "[QQ]"), BQ, "go movetime 1000", even, adv=False)
    check(parse_bestmove(lines)[0] != "pass", "hold: a seat that can defend plays",
          f"{parse_bestmove(lines)} reason={s.get('reason')}")
    e.setoption("HBHold", "false")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AS, BQ, "go movetime 1000", even, adv=False)
    check(parse_bestmove(lines)[0] != "pass", "hold: HBHold=false never sits when mated",
          f"{parse_bestmove(lines)} reason={s.get('reason')}")
    e.setoption("HBHold", "true")

    if worlds:
        # Our partner (black on B) mates by force. We sit only ahead on the
        # clock of the seat being mated (white on B), which may sit as well:
        # until our partner has moved, or for as long as the mated seat sits.
        AQ = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1"
        BP = "r5k1/8/8/8/8/8/5PPP/6K1[] b - - 0 1"       # partner to move
        BO = "1r4k1/8/8/8/8/8/q5PP/7K[] w - - 0 1"       # the mated seat to move
        lead = (60000, 60000, 50000, 60000)
        e.send("ucinewgame")
        lines, rep, s, wake = coord(e, AQ, BP, "go movetime 1000", lead, adv=True)
        check(parse_bestmove(lines)[0] == "pass" and s.get("reason") == "hold_partner"
              and wake == ["info string hb_wake_after_ms=3500"],
              "hold: sits while the partner, on turn, mates", f"{parse_bestmove(lines)} reason={s.get('reason')} wake={wake}")
        lines, rep, s, wake = coord(e, AQ, BP, "go movetime 1000", (58000, 60000, 50000, 60000), adv=True)
        check(parse_bestmove(lines)[0] == "pass" and wake == ["info string hb_wake_after_ms=1500"]
              and s.get("wait") == "hold_continue",
              "hold: a wake with nothing moved keeps the booked wake", f"{wake} wait={s.get('wait')}")
        lines, rep, s, wake = coord(e, AQ, BP, "go movetime 1000", (56500, 60000, 50000, 60000), adv=True)
        check(parse_bestmove(lines)[0] != "pass", "hold: plays when the partner has not moved in time",
              f"{parse_bestmove(lines)} reason={s.get('reason')}")
        lines, rep, s, wake = coord(e, AQ, BP, "go movetime 1000", (56000, 60000, 50000, 60000), adv=True)
        check(parse_bestmove(lines)[0] != "pass", "hold: one wait for a partner on turn per turn of ours",
              f"{parse_bestmove(lines)} reason={s.get('reason')}")
        e.send("ucinewgame")
        lines, rep, s, wake = coord(e, AQ, BO, "go movetime 1000", lead, adv=True)
        check(parse_bestmove(lines)[0] == "pass" and s.get("reason") == "hold_partner" and not wake,
              "hold: out-sits the seat being mated, with no wake", f"{parse_bestmove(lines)} reason={s.get('reason')} wake={wake}")
        lines, rep, s, wake = coord(e, AQ, BO, "go movetime 1000", (30000, 60000, 20000, 60000), adv=True)
        check(parse_bestmove(lines)[0] == "pass" and s.get("wait") == "hold_continue",
              "hold: sits on while the mated seat sits", f"{parse_bestmove(lines)} wait={s.get('wait')}")
        for name, fb, clocks in (("level clocks, partner to move", BP, even),
                                 ("level clocks, mated seat to move", BO, even),
                                 ("behind on the clock", BO, (50000, 60000, 60000, 60000)),
                                 ("short clock", BO, (15000, 60000, 5000, 60000))):
            e.send("ucinewgame")
            lines, rep, s, wake = coord(e, AQ, fb, "go movetime 1000", clocks, adv=False)
            check(parse_bestmove(lines)[0] != "pass", f"hold: no wait for the partner's mate: {name}",
                  f"{parse_bestmove(lines)} reason={s.get('reason')}")
        e.send("ucinewgame")
        lines, rep, s, wake = coord(e, "rnb1kbnr/pppp1ppp/8/4p3/7q/5P2/PPPPP1PP/RNBQKBNR[] w KQkq - 0 1", BO,
                                    "go movetime 1000", lead, adv=True)
        check(parse_bestmove(lines)[0] != "pass", "hold: a seat in check does not wait for the partner",
              f"{parse_bestmove(lines)} reason={s.get('reason')}")
        e.send("ucinewgame")
        lines, rep, s, wake = coord(e, "6k1/5ppp/8/8/8/8/8/R5K1[] w - - 0 1", BO, "go movetime 1000", lead, adv=True)
        check(parse_bestmove(lines)[0] == "a1a8", "hold: a seat with its own mate plays it",
              f"{parse_bestmove(lines)} reason={s.get('reason')}")

        # Rescue. Our partner (black on B) is mated next move by the two rooks
        # and sits. A knight in its hand guards b8; a pawn only delays the
        # mate, which the depth-5 feed price does not see.
        BR = "7k/R7/8/8/8/8/5PPP/1R4K1[] b - - 0 1"
        e.send("ucinewgame")
        lines, rep, s, wake = coord(e, AQ, BR, "go nodes 500000", even, adv=False)
        rescue = dict(kv.split(":") for kv in s.get("rescue", "").split(",") if ":" in kv)
        check(s.get("partner_held") == "-2" and rescue.get("P") == "0" and int(rescue.get("N", "0")) > 0,
              "rescue: only a piece that ends the sitting partner's mate is priced",
              f"held={s.get('partner_held')} rescue={s.get('rescue')}")
        e.setoption("HBRescue", "false")
        e.send("ucinewgame")
        lines, rep, s, wake = coord(e, AQ, BR, "go nodes 500000", even, adv=False)
        check(s.get("partner_held") == "-2" and "rescue" not in s, "rescue: HBRescue=false keeps the feed prices",
              f"held={s.get('partner_held')} rescue={s.get('rescue')}")
        e.setoption("HBRescue", "true")
        e.send("ucinewgame")
        lines, rep, s, wake = coord(e, AQ, BQ.replace(" w ", " b "), "go nodes 500000", even, adv=False)
        check("partner_held" not in s and "rescue" not in s, "rescue: nothing to do for a partner that is not mated",
              f"held={s.get('partner_held')} rescue={s.get('rescue')}")

    # 11. Shared convention: our partner (black on B) can take a knight that
    # gives us N@f7 mate. It takes it, and we wait for it, with no clock lead.
    AK = "6rk/6pp/8/8/8/8/8/K7[] w - - 0 1"
    BK = "r3k3/8/8/8/8/8/8/N3K3[] b - - 0 1"
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AK, BK, "go movetime 300", (60000, 60000, 70000, 60000), adv=False)
    check(parse_bestmove(lines)[0] == "pass" and s.get("wait") == "start",
          "wait: partner's verified winning delivery, no lead needed", f"{parse_bestmove(lines)} wait={s.get('wait')}")
    e.send("ucinewgame")
    e.setoption("Seat", "Bblack")
    lines, rep, s, _ = coord(e, AK, BK, "go movetime 1000", (60000, 60000, 70000, 60000), adv=False)
    check(parse_bestmove(lines)[1] == "a8a1" and rep["reason"].startswith("delivery_win"),
          "delivery: the partner takes the same conclusion", f"{parse_bestmove(lines)} reason={rep['reason']}")
    e.setoption("Seat", "Awhite")
    e.setoption("Team", "white")
    e.send("ucinewgame")

    # 7. Voluntary waiting. A: white (us) in check by Rh1, king can move,
    # a queen would block. B: black (partner) to move, only Kxg7 (a queen).
    # A bare king against a rook is also mated by force, which a deep enough
    # search sees: HBHold is off so that only the waiting rule is checked.
    AW = "7k/8/8/8/8/8/8/K6r[] w - - 0 1"
    BW = "7k/6Q1/8/8/8/8/8/K7[] b - - 0 1"
    e.setoption("HBHold", "false")
    good = (60000, 50000, 50000, 60000)                 # white team up on time
    lines, rep, s, wake = coord(e, AW, BW, "go movetime 300", good, adv=True)
    check(parse_bestmove(lines) == ("pass", "pass") and wake == ["info string hb_wake_after_ms=3000"]
          and s.get("wait") == "start", "voluntary wait starts (3000 ms)", f"{lines[-1]} wait={s.get('wait')}")
    lines, rep, s, wake = coord(e, AW, BW, "go movetime 300", (59000, 50000, 50000, 60000), adv=True)
    check(parse_bestmove(lines) == ("pass", "pass") and wake == ["info string hb_wake_after_ms=2000"],
          "repeated wakeup keeps the original expiry", f"{wake} wait={s.get('wait')}")
    lines, rep, s, wake = coord(e, AW, BW, "go movetime 300", (58500, 50000, 50000, 60000), adv=True)
    check(wake == ["info string hb_wake_after_ms=1500"], "second wakeup", str(wake))
    lines, rep, s, wake = coord(e, AW, BW, "go movetime 300", (57000, 50000, 50000, 60000), adv=True)
    a, _ = parse_bestmove(lines)
    check(a != "pass" and not wake and s.get("wait") == "expired", "expiry plays a move",
          f"{a} wait={s.get('wait')}")
    lines, rep, s, wake = coord(e, AW, BW, "go movetime 300", (56000, 50000, 50000, 60000), adv=True)
    check(parse_bestmove(lines)[0] != "pass" and s.get("wait") == "used", "one wait per own-board turn",
          f"wait={s.get('wait')}")
    e.send("ucinewgame")
    for name, fa, fb, clocks, adv, why in (
            ("missing supply (partner has a non-capture)", AW, "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR[] b KQkq - 0 1", good, True, "skip_partner_noncapture"),
            ("partner not on turn", AW, "7k/6Q1/8/8/8/8/8/K7[] w - - 0 1", good, True, "skip_partner_not_on_turn"),
            ("low own clock", AW, BW, (3900, 50000, 1000, 60000), True, "skip_low_clock"),
            ("partner-board opponent clock too close", AW, BW, (60000, 50000, 57000, 60000), True, "skip_partner_opponent_clock"),
            ("behind on the clock race", AW, BW, (40000, 50000, 50000, 60000), False, "skip_partner_opponent_clock"),
            ("not in check, no winning delivery", "7k/8/8/8/8/8/7r/K7[] w - - 0 1", BW, good, True, "skip_no_winning_delivery")):
        e.send("ucinewgame")
        lines, rep, s, wake = coord(e, fa, fb, "go movetime 200", clocks, adv)
        check(parse_bestmove(lines)[0] != "pass" and not wake and s.get("wait") == why,
              f"no wait: {name}", f"wait={s.get('wait')} move={parse_bestmove(lines)[0]}")
    e.close()

    # Waiting needs Clocks: a fresh process without them never waits.
    e = Engine(options={"Seat": "Awhite", "Team": "white", **mode})
    lines, rep, s, wake = coord(e, AW, BW, "go movetime 200", None, True)
    check(parse_bestmove(lines)[0] != "pass" and s.get("wait") == "skip_no_clocks", "no wait without Clocks",
          f"wait={s.get('wait')}")
    # Coordination off never waits voluntarily.
    e.setoption("Coordination", "false")
    lines, rep, s, wake = coord(e, AW, BW, "go movetime 200", good, True)
    check(parse_bestmove(lines)[0] != "pass" and "wait" not in s, "Coordination=false never waits")
    e.close()

    if worlds:
        worlds_cases(A2, B2, B3)


def forecast_of(lines: list[str]) -> dict | None:
    return next((json.loads(l[len("info string hb_forecast "):]) for l in lines
                 if l.startswith("info string hb_forecast ")), None)


def worlds_cases(A2: str, B2: str, B3: str) -> None:
    """v4: arrivals are forecast from the partner board's lines, both ways."""
    e = Engine(options={"Seat": "Awhite", "Team": "white", "HBStall": "false"})

    # Enemy arrivals: white on B (our opponents' partner) is on turn and can
    # take a rook or a knight. Both reach black's hand on our board.
    lines, rep, s, _ = coord(e, A2, B2)
    fc = forecast_of(lines)
    keys = [w["arrival"] for w in fc["worlds"]]
    total = sum(w["p"] for w in fc["worlds"])
    check(fc["ready"] and fc["mover"] == "opponent" and keys[0] == "none" and "-R" in keys
          and abs(total - 1.0) < 1e-4 and all(w["p"] > 0 for w in fc["worlds"]),
          "forecast: enemy captures become worlds, probabilities sum to 1", f"{[(w['arrival'], round(w['p'], 2)) for w in fc['worlds']]}")
    check(all(k == "none" or k.startswith("-") for k in keys),
          "forecast: an opponent capture feeds our opponent, never us", str(keys))
    moves = [c["move"] for c in rep["candidates"]]
    scored = [w for w in rep["worlds"] if w["scored"]]
    check(len(scored) == len(rep["worlds"]) and all(sorted(w["values"]) == sorted(moves) for w in scored),
          "worlds: every candidate is scored in every world", f"{len(scored)}/{len(rep['worlds'])} worlds, {len(moves)} candidates")
    best = max(rep["candidates"][1:], key=lambda c: c["S"], default=None)
    main_c = rep["candidates"][0]
    switched = rep["reason"] == "world_switch"
    check(rep["reason"] in ("kept_main", "world_switch")
          and switched == (best is not None and best["S"] >= main_c["S"] + 25),
          "worlds: the main choice is replaced only by a clear lead", f"reason={rep['reason']} S_main={main_c['S']} best={best and best['S']}")
    none_world = rep["worlds"][0]["values"]
    check(all(c["E"] <= main_c["E"] + 1e-9 or
              any(w["values"][c["move"]] > w["values"][main_c["move"]] for w in rep["worlds"][1:])
              for c in rep["candidates"][1:]),
          "worlds: with nothing arriving, no move outranks the main search's choice",
          f"none={none_world}")

    # Friendly arrivals: our partner (black on B) is on turn and can capture.
    lines, rep, s, _ = coord(e, A2, B3)
    fc = forecast_of(lines)
    keys = [w["arrival"] for w in fc["worlds"]]
    check(fc["mover"] == "partner" and any(k.startswith("+") for k in keys),
          "forecast: our partner's captures are simulated too", f"{[(w['arrival'], round(w['p'], 2)) for w in fc['worlds']]}")
    check("+R" in fc["prices"] or "+N" in fc["prices"], "forecast: arriving pieces are priced on our board", str(fc["prices"]))

    # A world search sees what the main search cannot. White's queen can take
    # a rook, but if black gets the knight that white on B is about to win,
    # N@f2 is mate. The knight world must score Qxa1 as mate and the engine
    # must not play it.
    AM = "2r1kb1r/ppp2ppp/8/8/8/8/6PP/r2Q2RK[] w k - 0 1"
    BM = "4k3/8/8/8/8/2n5/1P6/4K3[] w - - 0 1"
    lines, rep, s, _ = coord(e, AM, BM)
    fc = forecast_of(lines)
    knight = next((w for w in fc["worlds"] if w["arrival"] == "-N"), None)
    check(knight is not None and knight["p"] > 0.3, "forecast: a free knight is likely to be taken",
          f"{[(w['arrival'], round(w['p'], 2)) for w in fc['worlds']]}")
    move = parse_bestmove(lines)[0]
    g = Bughouse(AM, BM)
    g.push(0, move)
    g.push(1, "b2c3")
    mated = False
    for d in g.legal_moves(0):
        if d.startswith("N@"):
            g2 = g.copy()
            g2.push(0, d)
            mated |= g2.is_checkmate(chess.WHITE, False)
    check(move != "d1a1" and not mated, "worlds: does not walk into the mate the arriving knight gives",
          f"{move} reason={rep['reason']}")
    world = next((w for w in rep.get("worlds", []) if w["arrival"] == "-N"), None)
    if world and "d1a1" in world["values"]:
        check(world["values"]["d1a1"] <= -90000, "worlds: the knight world scores Qxa1 as mate", str(world["values"]))
    e.close()


def v6_cases() -> None:
    """v6: price probes deepened to a node cap, and the referee's repetition draw."""
    print("--- v6")
    # From v5c against v4, game 4. White's queen on board A is trapped in a
    # trade (Qxg4 hxg4, or ...Qxf3). On board B a queen in White's hand mates
    # in four (Bxg7+ Kxg7, Q@h6+ ...), which a depth-3 probe does not see.
    AQ = "3r1r1k/p1p2ppp/2pb3n/4p3/4Ppq1/2PP1Q2/PP2NPP1/R1B2RK1[RNbp] w - - 0 23"
    BQ4 = "r2q1r1k/pppb1ppB/2n2b1B/5p1Q/3P2p1/3B4/P1P2nPP/R3N1K1[NPPPn] w - - 0 23"
    clocks = (84000, 84000, 87000, 81000)

    def prices_of(lines):
        for l in lines:
            if l.startswith("info string hb_prices "):
                return json.loads(l[len("info string hb_prices "):])
        return None

    e = Engine(options={"Seat": "Awhite", "Team": "white"})
    lines, rep, s, wake = coord(e, AQ, BQ4, "go nodes 500000", clocks)
    pr = prices_of(lines)
    check(pr is not None and pr["theirs"]["Q"] == 1500 and int(s.get("price_depth", "0")) > 3,
          "deep prices: the queen that mates in four on the partner board is priced as a mate",
          f"theirs={pr and pr['theirs']} depth={s.get('price_depth')}")
    check(parse_bestmove(lines)[0] != "pass", "feed hold is off by default", f"{parse_bestmove(lines)} reason={s.get('reason')}")
    e.setoption("HBPriceShare", "0")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AQ, BQ4, "go nodes 500000", clocks)
    pr = prices_of(lines)
    check(pr is not None and pr["theirs"]["Q"] < 1500 and "price_depth" not in s,
          "deep prices: HBPriceShare=0 gives the depth-3 probes, which miss it",
          f"theirs={pr and pr['theirs']}")
    e.setoption("HBPriceShare", "10")
    e.setoption("HBFeedHold", "true")
    e.send("ucinewgame")
    lines, rep, s, wake = coord(e, AQ, BQ4, "go nodes 500000", clocks)
    check(parse_bestmove(lines)[0] == "pass" and s.get("reason") == "hold_feed" and s.get("hold_piece") == "Q"
          and wake == ["info string hb_wake_after_ms=7000"],
          "feed hold: HBFeedHold=true sits for 7 s instead of trading the queen",
          f"{parse_bestmove(lines)} reason={s.get('reason')} wake={wake}")
    e.close()

    # From v6b against v5e, game 57. Black mates on board A, and Kxf7 would
    # bring the same board position for the third time: the referee's draw,
    # which the search cannot see because it counts the hands.
    G57 = ("1e2e4 1e7e5 2d2d4 2g8f6 1d2d4 1b8c6 2g1f3 1g1f3 2a7a6 1e5d4 1f1c4 2b1c3 2b7b5 1f8c5 2c1g5 1c2c3 "
           "1g8f6 2b5b4 1c4f7 2c3a4 1e8f7 2c8b7 1e1g1 2a4c5 1d7d5 2b7c6 2e2e4 1c3d4 2e7e6 1d5e4 2P@e5 1d1b3 "
           "2f8c5 1f7f8 2d4c5 1f3e5 2f6e4 1B@d5 2g5d8 1e5c6 2e8g8 1b7c6 2N@e7 1d4c5 2g8h8 1d5b3 2B@f6 1a2b3 "
           "2B@h6 1d8e8 2f1d3 1c1f4 2P@e3 1f6d5 2e1g1 2e3f2 1f4g3 2g1h1 1h7h5 2P@e2 1b1c3 2Q@h4 1d5c3 2e2d1q "
           "1b2c3 2a1d1 1P@f3 2B@f4 1g2f3 2N@e2 1e4f3 2f8d8 1N@h4 2e2f4 2P@g5 1B@g2 2h4h6 1B@d6 2N@g3 1f8g8 "
           "2h2g3 1P@f7 1e8f7 1Q@d8 1B@e8 1d8e8 2e4g3 1f7e8 2h1h2 2g3f1 1P@f7 2d1f1 1e8f7 1R@d8 2B@g1 2h2h3 "
           "1N@f8 1d8f8 2g5g4 1f7f8 2h3h4 2N@f5 1P@f7 2e7f5")

    def play57(options):
        e = Engine(options={"Seat": "Ablack", "Team": "black", **options})
        e.setoption("Clocks", "7900,70472,75262,3110")
        e.setoption("TimeAdvantage", "false")
        e.send("position startpos moves " + G57)
        lines = e.go("go nodes 500000")
        e.close()
        return parse_bestmove(lines)[0], summary_fields(lines)

    move, s = play57({})
    check(move != "f8f7" and move != "pass" and s.get("draw_avoided") == "1",
          "draws: the mating seat does not repeat the position a third time",
          f"{move} draw_moves={s.get('draw_moves')}")
    move, s = play57({"HBDraws": "false"})
    check(move == "f8f7" and "draw_avoided" not in s, "draws: HBDraws=false plays into the repetition", move)


def main() -> int:
    run(False)
    run(True)
    v6_cases()
    print("RESULT", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
