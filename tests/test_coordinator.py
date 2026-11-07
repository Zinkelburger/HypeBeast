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


def main() -> int:
    e = Engine(options={"Seat": "Awhite", "Team": "white"})

    # 1. Delivery outside the local top three: Rxa6 loses the exchange
    # locally but gives the partner N@f2 mate on board B.
    A1 = "4k3/1p6/n7/8/8/R7/5PPP/4K3[] w - - 0 1"
    B1 = "k7/8/8/8/8/8/6PP/6RK[] b - - 0 1"
    lines, rep, s, _ = coord(e, A1, B1)
    c = cand(rep, "a3a6")
    check(c is not None and c["source"] == "delivery" and c["delivery"] == "N" and c["mating"]
          and c["F"] is not None and c["F"] > 0,
          "delivery outside the root top three is a candidate (verified mating delivery)",
          f"{c and {k: c[k] for k in ('source', 'L', 'F', 'S')}} reason={rep['reason']}")
    check(c is not None and c["S"] == c["L"] + max(-150, min(0, c["R"])) + max(-100, min(100, c["F"])),
          "S = L + clamp(R) + clamp(F) as written")
    main_c = rep["candidates"][0]
    check(main_c["source"] == "main" and rep["reason"] in ("kept_main", "override")
          and (rep["reason"] == "override") == (max(x["S"] for x in rep["candidates"][1:]) >= main_c["S"] + 20),
          "20 cp switch rule applied", f"reason={rep['reason']} S_main={main_c['S']}")

    # 2/4. Enemy arrival threats and mutually exclusive donor outcomes.
    # White to move on B (the opponents' partner) can take a rook (Kxd2)
    # or a knight (bxa3 / bxc3: identical hand addition, deduplicated).
    A2 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R[] w KQkq - 2 3"
    B2 = "k7/8/8/8/8/n1n5/1P1r4/4K3[] w - - 0 1"
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
    B3 = "4k3/1p1R4/N1N5/8/8/8/8/K7[] b - - 0 1"
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
        check(not fed_mate and rep["reason"] == "exposure_veto" and int(s["exposed"]) > 0,
              "v2 exposure veto avoids feeding a mating queen", f"{move} reason={rep['reason']} veto={s.get('veto')}")
    e.setoption("Seat", "Awhite")
    e.setoption("Team", "white")

    # 7. Voluntary waiting. A: white (us) in check by Rh1, king can move,
    # a queen would block. B: black (partner) to move, only Kxg7 (a queen).
    AW = "7k/8/8/8/8/8/8/K6r[] w - - 0 1"
    BW = "7k/6Q1/8/8/8/8/8/K7[] b - - 0 1"
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
            ("no time advantage", AW, BW, (40000, 50000, 50000, 60000), False, "skip_no_time_advantage"),
            ("not in check: arrival not needed", "7k/8/8/8/8/8/7r/K7[] w - - 0 1", BW, good, True, "skip_arrival_not_needed")):
        e.send("ucinewgame")
        lines, rep, s, wake = coord(e, fa, fb, "go movetime 200", clocks, adv)
        check(parse_bestmove(lines)[0] != "pass" and not wake and s.get("wait") == why,
              f"no wait: {name}", f"wait={s.get('wait')} move={parse_bestmove(lines)[0]}")
    e.close()

    # Waiting needs Clocks: a fresh process without them never waits.
    e = Engine(options={"Seat": "Awhite", "Team": "white"})
    lines, rep, s, wake = coord(e, AW, BW, "go movetime 200", None, True)
    check(parse_bestmove(lines)[0] != "pass" and s.get("wait") == "skip_no_clocks", "no wait without Clocks",
          f"wait={s.get('wait')}")
    # Coordination off never waits voluntarily.
    e.setoption("Coordination", "false")
    lines, rep, s, wake = coord(e, AW, BW, "go movetime 200", good, True)
    check(parse_bestmove(lines)[0] != "pass" and "wait" not in s, "Coordination=false never waits")
    e.close()

    print("RESULT", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
