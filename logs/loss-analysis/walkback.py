#!/usr/bin/env python3
"""Walk each sudden loss backwards: when was it last escapable, could the partner
have kept the piece, and was the capture visible at the decision?

usage: walkback.py MATCH_DIR SUDDEN_JSON ROWS_JSON OUT_JSON
One engine at a time, one thread. Reads logs only.
"""
import json
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")

import chess  # noqa: E402
from hbutil import ROOT, Bughouse, Engine, parse_bestmove  # noqa: E402

BIN = ROOT / "bin/hypebeast-v6h"
PLAIN = {"Coordination": "false", "HBFeedPrices": "false", "Hash": 64, "Threads": 1}
BACK = 6
NAME = {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q"}
sn = lambda s: s.replace("-", "")  # noqa: E731


def replay(tokens):
    g = Bughouse()
    for t in tokens:
        g.push(int(t[0]) - 1, t[1:])
    return g


def val(score):
    if score is None:
        return None
    return (30000 if score[1] > 0 else -30000) if score[0] == "mate" else score[1]


class Plain:
    def __init__(self):
        self.e = Engine(BIN, options=PLAIN)

    def search(self, g, seat, team, nodes):
        self.e.setoption("Seat", seat)
        self.e.setoption("Team", team)
        self.e.send("ucinewgame")
        self.e.sync()
        self.e.send(f"position fen {g.dual_fen()}")
        lines = self.e.go(f"go nodes {nodes}", timeout=300)
        sc = [l for l in lines if l.startswith("info depth") and " score " in l]
        last = sc[-1] if sc else ""
        score = None
        if " score mate " in last:
            score = ("mate", int(last.split(" score mate ")[1].split()[0]))
        elif " score cp " in last:
            score = ("cp", int(last.split(" score cp ")[1].split()[0]))
        return score, parse_bestmove(lines)


def main():
    d, sudden_path, rows_path, out_path = sys.argv[1:5]
    sudden = json.load(open(sudden_path))
    rows = {r["game"]: r for r in json.load(open(rows_path))}
    results = {}
    for l in open(f"{d}/results.jsonl"):
        r = json.loads(l)
        results[r["game"]] = r
    plain = Plain()
    out = []
    for s in sudden:
        game_id = s["game"]
        row = rows[game_id]
        res = results[game_id]["result"]
        ev, tokens = res["events"], res["moves"]
        M, W, P, WP = row["M"], row["W"], row["P"], row["WP"]
        bd = 0 if M[0] == "A" else 1
        ob = 1 - bd
        w_team = "white" if W in ("A-white", "B-black") else "black"
        m_team = "black" if w_team == "white" else "white"
        mev = [e for e in ev if e["kind"] == "move"]
        offset = len(tokens) - len(mev)
        idx_of = lambda i: offset + sum(1 for e in ev[:i] if e["kind"] == "move")  # noqa: E731
        item = {"game": game_id, "seat": M}

        # the decision the sudden test looked at
        i_prev = next(i for i, e in enumerate(ev)
                      if e.get("seat") == M and e["kind"] == s["kind"] and idx_of(i) == len(s["prefix"]))
        # 1. walk back over this seat's moves, with every piece that really came
        m_idx = [i for i, e in enumerate(ev) if e.get("seat") == M and e["kind"] == "move" and i <= i_prev][-BACK:][::-1]
        walk = []
        for back, i in enumerate(m_idx):
            prefix = tokens[:idx_of(i)]
            later = [f"{ob + 1}{e['uci']}" for e in ev[i + 1:] if e["kind"] == "move" and e["board"] != M[0]]
            base = replay(prefix)
            legal = len(base.legal_moves(bd))
            untold, ub = plain.search(base, sn(M), m_team, 500_000)
            told_g = replay(prefix)
            for t in later:
                b, uci = int(t[0]) - 1, t[1:]
                if told_g.is_legal(b, uci):
                    told_g.push(b, uci)
            told, tb = plain.search(told_g, sn(M), m_team, 500_000)
            walk.append({"back": back, "t": ev[i]["t"], "legal": legal, "played": ev[i]["uci"],
                         "logged": ev[i]["eval"], "untold": untold, "untold_move": ub[bd],
                         "told": told, "told_move": tb[bd]})
        item["walk"] = walk

        # 2. the capture that fed the attack, inside the sudden window
        window = [(i, e) for i, e in enumerate(ev) if i_prev < i and e["kind"] == "move"
                  and e["t"] <= s["seen_t"]]
        feeds = []
        for i, e in window:
            if e.get("seat") != WP:
                continue
            g = replay(tokens[:idx_of(i)])
            cap = Bughouse._captured_type(g.boards[ob], chess.Move.from_uci(e["uci"]))
            if cap:
                feeds.append((i, e, cap))
        item["feeds"] = [f"{NAME[c]} by {e['uci']}" for _, e, c in feeds]
        if feeds:
            i, e, cap = feeds[-1]
            at_decision = replay(s["prefix"])
            item["capture_legal_at_decision"] = at_decision.is_legal(ob, e["uci"])
            item["wp_on_turn_at_decision"] = at_decision.turn(ob) == (chess.WHITE if WP.endswith("white") else chess.BLACK)
            pm = [(j, x) for j, x in enumerate(ev[:i]) if x.get("seat") == P and x["kind"] == "move"]
            if pm:
                j, x = pm[-1]
                prefix_p = tokens[:idx_of(j)]
                gp = replay(prefix_p)
                to_sq = chess.Move.from_uci(e["uci"]).to_square
                was_capture = Bughouse._captured_type(gp.boards[ob], chess.Move.from_uci(x["uci"]))
                part = {"partner_move": x["uci"], "partner_logged": x["eval"], "legal": 0,
                        "partner_captured": NAME.get(was_capture),
                        "same_square": chess.Move.from_uci(x["uci"]).to_square == to_sq}
                scored = []
                for m in gp.legal_moves(ob):
                    g2 = replay(prefix_p)
                    g2.push(ob, m)
                    feeding = g2.is_legal(ob, e["uci"]) and Bughouse._captured_type(
                        g2.boards[ob], chess.Move.from_uci(e["uci"])) == cap
                    part["legal"] += 1
                    if m == x["uci"] or not feeding:
                        sc, _ = plain.search(g2, sn(WP), w_team, 50_000)
                        v = val(sc)
                        scored.append((m, None if v is None else -v, feeding))
                played = next((v for m, v, _ in scored if m == x["uci"]), None)
                alts = [(m, v) for m, v, f in scored if not f and v is not None]
                part["nonfeeding"] = len(alts)
                part["played_value"] = played
                if alts:
                    best = max(alts, key=lambda a: a[1])
                    part["best_nonfeeding"] = best
                    part["cost"] = None if played is None else played - best[1]
                item["partner"] = part
        out.append(item)
        print(json.dumps(item), flush=True)
        json.dump(out, open(out_path, "w"), indent=1)
    plain.e.close()

    # 3. replay each decision through the real coordinator
    for s, item in zip(sudden, out):
        rec = results[s["game"]]
        e = Engine(BIN, options={"HBFeedPrices": "false", "Hash": 64})
        try:
            M = s["seat"]
            team = "white" if M in ("A-white", "B-black") else "black"
            e.setoption("Seat", sn(M))
            e.setoption("Team", team)
            e.setoption("Clocks", ",".join(map(str, s["clocks"])))
            e.send("position startpos moves " + " ".join(s["prefix"]))
            lines = e.go("go nodes 500000", timeout=300)
        finally:
            e.close()
        summary = next((l for l in lines if l.startswith("info string hb_summary")), "")
        item["coord_summary"] = summary
        item["coord_strings"] = [l for l in lines if l.startswith("info string") and "hb_summary" not in l][:30]
        item["coord_move"] = lines[-1]
        print(s["game"], lines[-1], summary[:400], flush=True)
        json.dump(out, open(out_path, "w"), indent=1)
    print("DONE", len(out))


main()
