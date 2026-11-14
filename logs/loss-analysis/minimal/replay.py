"""Re-ask hb-minimal's told decisions, with and without the partner's message.

For each contender go with talk "told" (decisions.jsonl), two fresh v8c
processes, one at a time, under nice -n 10, with the logged base options and the
logged Team, Seat, TimeAdvantage, Clocks and position:
  told: HBPartnerTell = the logged message   (must reproduce the logged decision)
  own:  HBPartnerTell left at none            (what it would have played alone)
Results are appended to replay.jsonl (resumable: done keys are skipped).

    nice -n 10 python3 logs/loss-analysis/minimal/replay.py [--limit N] [--games 1,2]
"""
import argparse
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
LOSSES = {1, 2, 3, 4, 6, 9, 10, 11, 12, 13, 16}


def ask(d, tell):
    e = Engine(BIN, hypebeast=False, net=NET, options=BASE)
    try:
        e.send("ucinewgame")
        o = d["opts"]
        e.setoption("Team", o["Team"])
        e.setoption("Seat", o["Seat"])
        e.setoption("HBPartnerTell", tell)
        e.sync()
        if "TimeAdvantage" in o:
            e.setoption("TimeAdvantage", o["TimeAdvantage"])
        e.setoption("Clocks", o["Clocks"])
        e.send(d["pos"])
        lines = e.go(d["go"], timeout=900)
    finally:
        e.close()
    out = {"bestmove": lines[-1].split()[1]}
    for l in lines:
        if l.startswith("info string hb_summary "):
            out["sum"] = dict(p.split("=", 1) for p in l.split()[3:] if "=" in p)
        elif l.startswith("info string hb_forecast "):
            out["fc"] = json.loads(l.split("hb_forecast ", 1)[1])
        elif l.startswith("info string hb_coord "):
            out["coord"] = json.loads(l.split("hb_coord ", 1)[1])
        elif l.startswith("info string hb_tell "):
            out["tell"] = l.split("hb_tell ", 1)[1]
        elif "hb_error" in l:
            out.setdefault("errs", []).append(l)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--games", default="")
    ap.add_argument("--modes", default="told,own")
    ap.add_argument("--out", default=HERE + "/replay.jsonl")
    a = ap.parse_args()
    games = {int(x) for x in a.games.split(",") if x}
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            r = json.loads(l)
            done.add((r["game"], r["seat"], r["n"], r["mode"]))
    ds = [json.loads(l) for l in open(HERE + "/decisions.jsonl")]
    ds = [d for d in ds if d["role"] == "contender" and (d.get("fc") or {}).get("talk") == "told"]
    if games:
        ds = [d for d in ds if d["game"] in games]
    # losses first, then wins
    ds.sort(key=lambda d: (d["game"] not in LOSSES, d["game"], d["n"], d["seat"]))
    k = 0
    with open(a.out, "a") as f:
        for d in ds:
            for mode in a.modes.split(","):
                key = (d["game"], d["seat"], d["n"], mode)
                if key in done:
                    continue
                r = ask(d, d["opts"]["HBPartnerTell"] if mode == "told" else "none")
                r.update(game=d["game"], seat=d["seat"], n=d["n"], mode=mode)
                f.write(json.dumps(r) + "\n")
                f.flush()
            k += 1
            if a.limit and k >= a.limit:
                break


if __name__ == "__main__":
    main()
