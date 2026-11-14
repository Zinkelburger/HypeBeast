"""v8h, HBMateGuard: off, the old binary's decisions; on, what it probes and what it costs.

    python3 coord11.py bin/hypebeast-v8g bin/hypebeast-v8h

1. Guard off: the same decision, score, reason, node count and depth as the old binary.
2. Guard on, beside the full mate prices (F13: HBFeedPrices=true,HBPriceScale=0,HBPriceKeepTable=true):
   the types probed, the mates priced, the main search's nodes. No hb_error line.
Exit 0 and a file NEW.ok when part 1 holds on every decision and part 2 has no error.
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
F13 = {"HBFeedPrices": "true", "HBPriceScale": 0, "HBPriceKeepTable": "true"}


def game_at(r, cut):
    g = Bughouse()
    toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
    for t in toks[:cut]:
        g.push(int(t[0]) - 1, t[1:])
    return g


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
    return {"move": parse_bestmove(lines), "kv": kv, "errs": [l for l in lines if "hb_error" in l], "prices": prices,
            "key": tuple(kv.get(k) for k in ("decision", "main_score_cp", "coord_reason", "total_nodes", "main_depth"))}


same = n = errs = 0
for gi, cut in ((3, 40), (11, 61), (35, 72), (22, 139), (16, 83), (7, 96), (28, 110)):
    g = game_at(res[gi], cut)
    for seat in SEATS:
        if not on_turn(g, seat):
            continue
        a, b = ask(OLD, {}, g, seat), ask(NEW, {}, g, seat)
        n += 1; same += a["key"] == b["key"]
        on, full = ask(NEW, {"HBMateGuard": "true"}, g, seat), ask(NEW, F13, g, seat)
        errs += len(b["errs"]) + len(on["errs"])
        mate = lambda p: "".join(t for t, v in (p or {}).get("theirs", {}).items() if v == 1500) or "-"
        print(f"game {gi} ply {cut} {seat}: off {'same' if a['key'] == b['key'] else 'DIFFERENT ' + str(a['key']) + ' ' + str(b['key'])}"
              f" | guard: probed {on['kv'].get('guard')} mates {mate(on['prices'])} move {on['kv'].get('decision')} main nodes {on['kv'].get('main_nodes')} depth {on['kv'].get('main_depth')}"
              f" | full mate prices: mates {mate(full['prices'])} move {full['kv'].get('decision')} main nodes {full['kv'].get('main_nodes')}"
              f" | no prices: move {b['kv'].get('decision')} main nodes {b['kv'].get('main_nodes')}", flush=True)
print(f"guard off: {same} of {n} decisions as {OLD}; hb_error lines: {errs}")
if same == n and not errs:
    open(str(ROOT / NEW) + ".ok", "w").write("coord11\n")
    sys.exit(0)
sys.exit(1)
