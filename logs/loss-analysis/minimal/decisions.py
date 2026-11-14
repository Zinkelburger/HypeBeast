"""Every go of hb-minimal in logs/minimal-vs-l50, with the exact UCI state it was asked in.

Matches each go to its game the way scripts/postmortem.py collect() does, and
writes decisions.jsonl: one row per go with game, seat, n, the options in effect
(Team, Seat, TimeAdvantage, Clocks, HBPartnerTell), the position command, the
logged bestmove, hb_summary, hb_forecast, hb_coord and hb_tell.

    python3 logs/loss-analysis/minimal/decisions.py
"""
import glob
import json
import sys

sys.dont_write_bytecode = True
ROOT = "/home/anbernal/Projects/HypeBeast-v5"
sys.path.insert(0, ROOT + "/scripts")
from postmortem import load_games  # noqa: E402

D = ROOT + "/logs/minimal-vs-l50"
OUT = ROOT + "/logs/loss-analysis/minimal/decisions.jsonl"


def main():
    games = load_games(D)
    index = {}
    for g in games:
        index.setdefault(tuple(g["toks"][:12]), []).append(g)
    rows = []
    for path in sorted(glob.glob(f"{D}/engine_logs/w*-*.log")):
        role = "contender" if "-contender-" in path else "baseline"
        opts, block, moves, poscmd = {}, None, None, None
        for ln, line in enumerate(open(path, errors="replace")):
            line = line.rstrip("\n")
            if line.startswith(">>> setoption name "):
                name, _, value = line[len(">>> setoption name "):].partition(" value ")
                opts[name] = value
            elif line.startswith(">>> position "):
                poscmd = line[4:]
                moves = line.split()[4:] if " moves " in line else []
            elif line.startswith(">>> go"):
                block = {"opts": dict(opts), "pos": poscmd, "go": line[4:], "line": ln + 1, "path": path}
            elif block is None:
                continue
            elif line.startswith("info string hb_forecast "):
                block["fc"] = json.loads(line.split("hb_forecast ", 1)[1])
            elif line.startswith("info string hb_coord "):
                block["coord"] = json.loads(line.split("hb_coord ", 1)[1])
            elif line.startswith("info string hb_tell "):
                block["tell"] = line.split("hb_tell ", 1)[1]
            elif line.startswith("info string hb_summary "):
                block["sum"] = dict(p.split("=", 1) for p in line.split()[3:] if "=" in p)
            elif line.startswith("bestmove"):
                b, block = block, None
                b["bestmove"] = line.split()[1]
                seat = b["opts"].get("Seat")
                if "sum" not in b or moves is None or seat is None:
                    continue
                sk = seat[0] + "-" + seat[1:]
                g = next((g for g in index.get(tuple(moves[:12]), [])
                          if g["toks"][:len(moves)] == moves and g["seats"][sk] == g["names"][role]), None)
                if g is None:
                    continue
                b.update(game=g["game"], seat=seat, n=len(moves), role=role, engine=g["names"][role],
                         winner=g["winner"], team="white" if seat in ("Awhite", "Bblack") else "black")
                rows.append(b)
    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(len(rows), "decisions written to", OUT)


if __name__ == "__main__":
    main()
