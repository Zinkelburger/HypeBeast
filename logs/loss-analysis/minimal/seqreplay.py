"""History-faithful replay: one process per (game, seat), every go of that seat in order, as the arena sent it.

The main search keeps its hash between the gos of a game (only ucinewgame
clears it), so a fresh process per decision does not give the logged score to
the centipawn. This replays a seat's whole game in one process and compares
each go with the log. With --branch, at the listed decisions it instead asks
a second process that has replayed the same prefix, then asks the decision
without the partner's message (the "own" answer with the same history).

    nice -n 10 python3 logs/loss-analysis/minimal/seqreplay.py verify 1:Ablack 4:Awhite ...
    nice -n 10 python3 logs/loss-analysis/minimal/seqreplay.py branch   (the decisions in branch_todo.json)
"""
import json
import os
import sys

sys.dont_write_bytecode = True
ROOT = "/home/anbernal/Projects/HypeBeast-v5"
sys.path.insert(0, ROOT + "/tests")
from hbutil import Engine  # noqa: E402

HERE = ROOT + "/logs/loss-analysis/minimal"
BIN = ROOT + "/bin/hypebeast-v8c"
NET = ROOT + "/nets/bughouse-cd8cceab93fe.nnue"
BASE = {"Ponder": "false", "HypeBeast": "true", "Hash": 64, "HBFeedPrices": "false",
        "HBForecastTrustLate": 50, "HBTell": "minimal", "Coordination": "true"}
K = ("decision", "main_score_cp", "coord_reason", "total_nodes", "main_depth")


def parse(lines):
    out = {"bestmove": lines[-1].split()[1]}
    for l in lines:
        if l.startswith("info string hb_summary "):
            out["sum"] = dict(p.split("=", 1) for p in l.split()[3:] if "=" in p)
        elif l.startswith("info string hb_forecast "):
            out["fc"] = json.loads(l.split("hb_forecast ", 1)[1])
        elif l.startswith("info string hb_coord "):
            out["coord"] = json.loads(l.split("hb_coord ", 1)[1])
    return out


class Seat:
    def __init__(self, first):
        self.e = Engine(BIN, hypebeast=False, net=NET, options=BASE)
        self.e.send("ucinewgame")
        self.e.setoption("Team", first["opts"]["Team"])
        self.e.setoption("Seat", first["opts"]["Seat"])
        self.e.sync()

    def ask(self, d, tell=None):
        o = d["opts"]
        self.e.setoption("HBPartnerTell", o.get("HBPartnerTell", "none") if tell is None else tell)
        if "TimeAdvantage" in o:
            self.e.setoption("TimeAdvantage", o["TimeAdvantage"])
        self.e.setoption("Clocks", o["Clocks"])
        self.e.send(d["pos"])
        return parse(self.e.go(d["go"], timeout=900))

    def close(self):
        self.e.close()


def seat_gos(ds, game, seat):
    return sorted([d for d in ds if d["role"] == "contender" and d["game"] == game and d["seat"] == seat],
                  key=lambda d: d["n"])


def main():
    ds = [json.loads(l) for l in open(HERE + "/decisions.jsonl")]
    mode = sys.argv[1]
    if mode == "verify":
        out = open(HERE + "/seqverify.jsonl", "a")
        for gs in sys.argv[2:]:
            g, seat = gs.split(":")
            gos = seat_gos(ds, int(g), seat)
            s = Seat(gos[0])
            for d in gos:
                r = s.ask(d)
                same = [d["sum"].get(k) for k in K] == [r["sum"].get(k) for k in K]
                out.write(json.dumps({"game": d["game"], "seat": seat, "n": d["n"], "same": same,
                                      "logged": [d["sum"].get(k) for k in K],
                                      "replay": [r["sum"].get(k) for k in K]}) + "\n")
                out.flush()
            s.close()
    elif mode == "branch":
        todo = json.load(open(HERE + "/branch_todo.json"))   # [[game, seat, n], ...]
        path = HERE + "/branch.jsonl"
        done = {(r["game"], r["seat"], r["n"]) for r in map(json.loads, open(path))} if os.path.exists(path) else set()
        out = open(path, "a")
        for g, seat, n in todo:
            if (g, seat, n) in done:
                continue
            gos = seat_gos(ds, g, seat)
            s = Seat(gos[0])
            for d in gos:
                if d["n"] < n:
                    s.ask(d)
                elif d["n"] == n:
                    r = s.ask(d, tell="none")
                    r.update(game=g, seat=seat, n=n)
                    out.write(json.dumps(r) + "\n")
                    out.flush()
                    break
            s.close()


if __name__ == "__main__":
    main()
