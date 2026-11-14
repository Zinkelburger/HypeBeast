"""v8j: HBTellRoot, the partner's message used at the choice among the candidates.

    python3 coord13.py bin/hypebeast-v8i bin/hypebeast-v8j

1. Everything off: the same decision, score, reason, node count and depth as the old binary.
2. HBTell=worth,HBTellRoot=true with a message heard: no hb_prices line (nothing priced in the search),
   heard_root=fresh, each candidate's feed printed; with the teller at -900 and HBTellFloor=-300: heard_root=low
   and the decision of the same binary with HBTell=worth and nothing heard.
Exit 0 and a file NEW.ok when all of it holds and no hb_error line appears.
"""
import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")
import chess
from hbutil import ROOT, Bughouse, Engine, parse_bestmove, position_command
OLD, NEW = sys.argv[1], sys.argv[2]
res = [json.loads(l) for l in open(ROOT / "logs/late50-vs-np-b/results.jsonl")]
SEATS = ("Awhite", "Ablack", "Bwhite", "Bblack")
BASE = {"Hash": 64, "HBFeedPrices": "false", "HBForecastTrustLate": 50}
ROOTOPT = {"HBTell": "worth", "HBTellRoot": "true", "HBPriceScale": 100, "HBPriceCap": 1500, "HBTellMin": 150, "HBTellFloor": -300}


def game_at(r, cut):
    g = Bughouse()
    toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
    for t in toks[:cut]:
        g.push(int(t[0]) - 1, t[1:])
    return g, toks[:cut]


def on_turn(g, seat):
    return g.turn(0 if seat[0] == "A" else 1) == (chess.WHITE if seat.endswith("white") else chess.BLACK)


def ask(binary, opts, g, seat):
    e = Engine(ROOT / binary, options={**BASE, **opts})
    e.setoption("Seat", seat); e.setoption("Team", "white" if seat in ("Awhite", "Bblack") else "black")
    e.setoption("Clocks", "90000,88000,91000,87000"); e.send("ucinewgame"); e.sync()
    e.send(position_command(g))
    lines = e.go("go nodes 500000", timeout=900)
    e.close()
    summ = [l for l in lines if "hb_summary" in l]
    kv = dict(p.split("=", 1) for p in summ[-1].split() if "=" in p) if summ else {}
    co = next((json.loads(l.split("hb_coord ", 1)[1]) for l in lines if "hb_coord " in l), {})
    return {"kv": kv, "errs": [l for l in lines if "hb_error" in l], "prices": any("hb_prices " in l for l in lines),
            "cands": [(c["move"], c.get("feed"), c.get("S")) for c in co.get("candidates", [])],
            "key": tuple(kv.get(k) for k in ("decision", "main_score_cp", "coord_reason", "total_nodes", "main_depth"))}


ok = True
same = n = fed = 0
msg = "v1 n={} base={} worth +Q=450 +R=300 +B=200 +N=220 +P=110 -Q=900 -R=500 -B=250 -N=300 -P=120"
for gi, cut in ((3, 40), (11, 61), (35, 72), (16, 83), (7, 96), (22, 60), (28, 52)):
    g, toks = game_at(res[gi], cut)
    for seat in SEATS:
        if not on_turn(g, seat):
            continue
        a, b = ask(OLD, {}, g, seat), ask(NEW, {}, g, seat)
        n += 1; same += a["key"] == b["key"]
        plies = sum(t[0] == ("2" if seat[0] == "A" else "1") for t in toks)
        quiet = ask(NEW, {**ROOTOPT}, g, seat)
        x = ask(NEW, {**ROOTOPT, "HBPartnerTell": msg.format(plies, 50)}, g, seat)
        z = ask(NEW, {**ROOTOPT, "HBPartnerTell": msg.format(plies, -900)}, g, seat)
        fed += any(f for _, f, _ in x["cands"])
        searched = bool(x["cands"])
        good = not (b["errs"] or x["errs"] or z["errs"] or quiet["errs"]) and not x["prices"] and not z["prices"]
        # a decision that never reaches the choice over the worlds (a sit, an only move) has no heard_root
        good &= x["kv"].get("heard_root") in (None, "fresh") and z["kv"].get("heard_root") in (None, "low") and z["key"] == quiet["key"]
        ok &= good
        print(f"game {gi} ply {cut} {seat}: off {'same' if a['key'] == b['key'] else 'DIFFERENT'} | heard: {x['kv'].get('heard_root')} reason {x['kv'].get('coord_reason')} move {x['kv'].get('decision')} "
              f"candidates (move, feed, S) {x['cands']} | nothing heard: {quiet['kv'].get('decision')} | below the floor: {z['kv'].get('heard_root')} {z['kv'].get('decision')} {'ok' if good else 'NOT OK'}", flush=True)
print(f"all off: {same} of {n} decisions as {OLD}; decisions with a candidate that hands something over: {fed}")
ok &= same == n
print("PASS" if ok else "FAIL")
if ok:
    open(str(ROOT / NEW) + ".ok", "w").write("coord13\n")
sys.exit(0 if ok else 1)
