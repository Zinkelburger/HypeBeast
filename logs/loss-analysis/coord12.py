"""v8i: HBMateGuardQuiet and the three limits on a partner's message (HBTellFloor, HBTellMin, HBTellLossesOnly).

    python3 coord12.py bin/hypebeast-v8h bin/hypebeast-v8i

1. Everything off: the same decision, score, reason, node count and depth as the old binary.
2. HBTell=worth with a message "base=50 worth +R=600 -Q=800 -N=300" at scale 100, cap 1000:
   limits off -> ours R 600, theirs Q 800 and N 300; with HBTellMin=500 and HBTellLossesOnly -> only theirs Q 800;
   the same message with base=-900 and HBTellFloor=-300 -> heard=low and no prices.
3. The quiet guard runs without an error line.
Exit 0 and a file NEW.ok when all of it holds.
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
    prices = next((json.loads(l.split("hb_prices ", 1)[1]) for l in lines if "hb_prices " in l), None)
    return {"kv": kv, "errs": [l for l in lines if "hb_error" in l], "prices": prices,
            "key": tuple(kv.get(k) for k in ("decision", "main_score_cp", "coord_reason", "total_nodes", "main_depth"))}


ok = True
same = n = 0
for gi, cut in ((3, 40), (11, 61), (35, 72), (16, 83), (7, 96)):
    g, toks = game_at(res[gi], cut)
    for seat in SEATS:
        if not on_turn(g, seat):
            continue
        a, b = ask(OLD, {}, g, seat), ask(NEW, {}, g, seat)
        n += 1; same += a["key"] == b["key"]
        q = ask(NEW, {"HBMateGuard": "true", "HBMateGuardFloor": -300, "HBMateGuardQuiet": "true"}, g, seat)
        ok &= not b["errs"] and not q["errs"]
        print(f"game {gi} ply {cut} {seat}: off {'same' if a['key'] == b['key'] else 'DIFFERENT'} | quiet guard: probed {q['kv'].get('guard')} "
              f"prices line {'yes' if q['prices'] else 'no'} move {q['kv'].get('decision')} main nodes {q['kv'].get('main_nodes')} | no prices: {b['kv'].get('decision')} {b['kv'].get('main_nodes')}", flush=True)
print(f"all off: {same} of {n} decisions as {OLD}")
ok &= same == n

g, toks = game_at(res[11], 61)
seat = next(s for s in SEATS if on_turn(g, s))
pb = "2" if seat[0] == "A" else "1"
plies = sum(t[0] == pb for t in toks)
msg = "v1 n={} base={} worth +R=600 -Q=800 -N=300"
W = {"HBTell": "worth", "HBPriceScale": 100, "HBPriceCap": 1000}
LIM = {"HBTellMin": 500, "HBTellLossesOnly": "true", "HBTellFloor": -300}
def priced(p, side):
    return {t: v for t, v in (p or {}).get(side, {}).items() if v}
x = ask(NEW, {**W, "HBPartnerTell": msg.format(plies, 50)}, g, seat)
y = ask(NEW, {**W, **LIM, "HBPartnerTell": msg.format(plies, 50)}, g, seat)
z = ask(NEW, {**W, **LIM, "HBPartnerTell": msg.format(plies, -900)}, g, seat)
print(f"{seat}, message heard with limits off: heard={x['kv'].get('heard')} ours {priced(x['prices'], 'ours')} theirs {priced(x['prices'], 'theirs')} move {x['kv'].get('decision')}")
print(f"with the limits: heard={y['kv'].get('heard')} ours {priced(y['prices'], 'ours')} theirs {priced(y['prices'], 'theirs')} move {y['kv'].get('decision')}")
print(f"teller at -900, floor -300: heard={z['kv'].get('heard')} prices line {'yes' if z['prices'] else 'no'} move {z['kv'].get('decision')}")
ok &= priced(x["prices"], "ours") == {"R": 600} and priced(x["prices"], "theirs") == {"Q": 800, "N": 300}
ok &= priced(y["prices"], "ours") == {} and priced(y["prices"], "theirs") == {"Q": 800}
ok &= z["kv"].get("heard") == "low" and not z["prices"]
ok &= not (x["errs"] or y["errs"] or z["errs"])
print("PASS" if ok else "FAIL")
if ok:
    open(str(ROOT / NEW) + ".ok", "w").write("coord12\n")
sys.exit(0 if ok else 1)
