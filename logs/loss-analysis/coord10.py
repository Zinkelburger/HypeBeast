"""v8f: what HBTeamScore and HBKingDanger do to one decision."""
import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")
from hbutil import ROOT, Bughouse, Engine, parse_bestmove, position_command
BIN = sys.argv[1]
res = [json.loads(l) for l in open(ROOT / "logs/late50-vs-np-b/results.jsonl")]
def game_at(r, cut, more=()):
    g = Bughouse()
    toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
    for t in toks[:cut]: g.push(int(t[0]) - 1, t[1:])
    for b, m in more: g.push(b, m)
    return g
def ask(opts, g, seat):
    e = Engine(ROOT / BIN, options={"Hash": 64, "HBFeedPrices": "false", "HBForecastTrustLate": 50, **opts})
    e.setoption("Seat", seat); e.setoption("Team", "white" if seat in ("Awhite", "Bblack") else "black")
    e.setoption("Clocks", "90000,88000,91000,87000"); e.send("ucinewgame"); e.sync()
    e.send(position_command(g)); lines = e.go("go nodes 500000", timeout=900); e.close()
    kv = dict(p.split("=", 1) for p in [l for l in lines if "hb_summary" in l][-1].split() if "=" in p)
    co = next((json.loads(l.split("hb_coord ", 1)[1]) for l in lines if "hb_coord " in l), {})
    return parse_bestmove(lines), kv.get("main_score_cp"), kv.get("coord_reason"), kv.get("main_depth"), co.get("team_shift"), \
        [(c["move"], round(c["E"], 3), c.get("S")) for c in co.get("candidates", [])], [(w["arrival"], round(w["p"], 2)) for w in co.get("worlds", [])]
g = game_at(res[11], 61)
text = "v1 n=33 at=32 d=14 score={} mate={} hands=NP/NP lines 4:h4e7,d8e7,N@d5,e7e8,P@h6,c8f5"
for label, opts in (("plan only", {"HBTell": "plan", "HBPartnerTell": text.format(577, 0)}),
                    ("team score, partner +577", {"HBTell": "plan", "HBTeamScore": 100, "HBPartnerTell": text.format(577, 0)}),
                    ("team score, partner +2500", {"HBTell": "plan", "HBTeamScore": 100, "HBPartnerTell": text.format(2500, 0)}),
                    ("team score, partner -2500", {"HBTell": "plan", "HBTeamScore": 100, "HBPartnerTell": text.format(-2500, 0)}),
                    ("team score, partner mates", {"HBTell": "plan", "HBTeamScore": 100, "HBPartnerTell": text.format(99990, 9)}),
                    ("no talk, king danger 0", {}), ("no talk, king danger 60", {"HBKingDanger": 60}), ("no talk, king danger 150", {"HBKingDanger": 150})):
    print(label, "->", ask(opts, g, "Ablack"), flush=True)
