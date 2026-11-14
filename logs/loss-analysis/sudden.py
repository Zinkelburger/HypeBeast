#!/usr/bin/env python3
"""For each sudden loss, test the last decision before the seat saw forced mate.

usage: sudden.py MATCH_DIR ROWS_JSON LOSER_NAME OUT_JSON
One engine process, one thread. Reads logs only.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")

import chess  # noqa: E402
from hbutil import ROOT, Bughouse, Engine, parse_bestmove  # noqa: E402

JUDGE = ROOT / "bin/hypebeast-v6h"
FAST, FULL, SEARCH = 50_000, 400_000, 500_000
SEATNAME = lambda s: s.replace("-", "")  # noqa: E731


def bad(ev):
    return ev is not None and "mate" in ev and ev["mate"] < 0


def replay(tokens):
    game = Bughouse()
    for t in tokens:
        game.push(int(t[0]) - 1, t[1:])
    return game


class Judge:
    def __init__(self):
        self.e = Engine(JUDGE, options={"Coordination": "false", "HBFeedPrices": "false", "Hash": 64, "Threads": 1})

    def search(self, game, seat, team, nodes):
        self.e.setoption("Seat", seat)
        self.e.setoption("Team", team)
        self.e.send("ucinewgame")
        self.e.sync()
        self.e.send(f"position fen {game.dual_fen()}")
        lines = self.e.go(f"go nodes {nodes}", timeout=300)
        scores = [l for l in lines if l.startswith("info depth") and " score " in l]
        last = scores[-1] if scores else ""
        score = None
        if " score mate " in last:
            score = ("mate", int(last.split(" score mate ")[1].split()[0]))
        elif " score cp " in last:
            score = ("cp", int(last.split(" score cp ")[1].split()[0]))
        return score, parse_bestmove(lines)

    def mates(self, game, seat, team, nodes):
        """Does the side to move, sitting at `seat`, have a forced mate?"""
        s, _ = self.search(game, seat, team, nodes)
        return s is not None and s[0] == "mate" and s[1] > 0


def main():
    d, rows_path, loser, out_path = sys.argv[1:5]
    rows = [r for r in json.load(open(rows_path))
            if r["loser"] == loser and r.get("prev_eval") is not None and r["prev_eval"] >= -200]
    results = {json.loads(l)["game"]: json.loads(l) for l in open(f"{d}/results.jsonl")}
    judge = Judge()
    report = []
    for row in rows:
        rec = results[row["game"]]
        res = rec["result"]
        ev = res["events"]
        tokens = res["moves"]
        M, W, P, WP = row["M"], row["W"], row["P"], row["WP"]
        dec = [(i, e) for i, e in enumerate(ev)
               if e.get("seat") == M and e["kind"] in ("move", "sit") and e.get("eval") is not None]
        k = len(dec)
        while k > 0 and bad(dec[k - 1][1]["eval"]):
            k -= 1
        i_prev, prev = dec[k - 1]
        i_seen, seen = dec[k]
        move_events = [e for e in ev if e["kind"] == "move"]
        offset = len(tokens) - len(move_events)
        before = sum(1 for e in ev[:i_prev] if e["kind"] == "move")
        prefix = tokens[:offset + before]
        bd = 0 if M[0] == "A" else 1
        other = 1 - bd
        window = [e for e in ev[i_prev + 1:i_seen] if e["kind"] == "move"]
        between = [f"{other + 1}{e['uci']}" for e in window if e["board"] != M[0]]
        w_team = "white" if W in ("A-white", "B-black") else "black"
        m_team = "black" if w_team == "white" else "white"
        item = {"game": row["game"], "seat": M, "kind": prev["kind"], "played": prev.get("uci"),
                "eval_before": prev["eval"], "seen_mate": seen["eval"]["mate"],
                "window": [f"{e['seat']} {e['uci']}" for e in window], "prefix": prefix, "between": between,
                "clocks": prev["clocks"], "seen_t": seen["t"], "end_t": res["duration_ms"]}

        base = replay(prefix)
        if base.turn(bd) != (chess.WHITE if M.endswith("white") else chess.BLACK):
            item["error"] = "seat not on turn at the decision"
            report.append(item)
            print(json.dumps({k2: v for k2, v in item.items() if k2 != "prefix"}), flush=True)
            continue
        legal = list(base.legal_moves(bd))
        item["legal"] = len(legal)

        def after(move, feed):
            g = replay(prefix)
            if move:
                g.push(bd, move)
            if feed:
                for t in between:
                    b, uci = int(t[0]) - 1, t[1:]
                    if g.is_legal(b, uci):
                        g.push(b, uci)
            return g

        def forced(move, feed):
            g = after(move, feed)
            if not g.legal_moves(bd):
                return False
            if judge.mates(g, SEATNAME(W), w_team, FAST):
                return True
            return judge.mates(g, SEATNAME(W), w_team, FULL)

        if prev["kind"] == "move":
            item["played_mated_without_arrival"] = forced(prev["uci"], False)
            item["played_mated_with_arrival"] = forced(prev["uci"], True)
        survivors = [m for m in legal if not forced(m, True)]
        item["survivors_with_arrival"] = survivors
        # told what arrives: the same seat, on turn, after the partner-board moves
        told = after(None, True)
        score, best = judge.search(told, SEATNAME(M), m_team, SEARCH)
        move = best[bd]
        item["told_score"] = score
        item["told_move"] = move
        item["told_survives"] = move in survivors
        # not told: what a plain search picks from the decision position itself
        score0, best0 = judge.search(base, SEATNAME(M), m_team, SEARCH)
        item["untold_score"] = score0
        item["untold_move"] = best0[bd]
        item["untold_survives"] = best0[bd] in survivors
        report.append(item)
        print(json.dumps({k2: v for k2, v in item.items() if k2 not in ("prefix", "between")}), flush=True)
        json.dump(report, open(out_path, "w"), indent=1)
    judge.e.close()
    print("DONE", len(report))


main()
