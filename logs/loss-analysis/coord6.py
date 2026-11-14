"""v8b against v8a: identical with HBTell off and with alarm and nothing heard? What table says, and what the partner makes of it."""
import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")
from hbutil import ROOT, Bughouse, Engine, parse_bestmove
OLD, NEW = sys.argv[1], sys.argv[2]
res = [json.loads(l) for l in open(ROOT / "logs/late50-vs-np-b/results.jsonl")]
PARTNER = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
def key(s):
    kv = dict(p.split("=", 1) for p in s.split() if "=" in p)
    return tuple(kv.get(k) for k in ("decision", "main_score_cp", "coord_reason", "total_nodes", "main_depth"))
def run(binary, opts, r, cut, only=None):
    g = Bughouse()
    toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
    for t in toks[:cut]: g.push(int(t[0]) - 1, t[1:])
    out = {}
    for seat in ("Awhite", "Ablack", "Bwhite", "Bblack"):
        if only and seat not in only: continue
        e = Engine(ROOT / binary, options={"Hash": 64, "HBFeedPrices": "false", "HBForecastTrustLate": 50, **(opts(seat) if callable(opts) else opts)})
        e.setoption("Seat", seat); e.setoption("Team", "white" if seat in ("Awhite", "Bblack") else "black")
        e.setoption("Clocks", "90000,88000,91000,87000"); e.send("ucinewgame"); e.sync()
        e.send(f"position fen {g.dual_fen()}")
        lines = e.go("go nodes 500000", timeout=600)
        summ = [l for l in lines if "hb_summary" in l]
        kv = dict(p.split("=", 1) for p in summ[-1].split() if "=" in p) if summ else {}
        out[seat] = {"move": parse_bestmove(lines), "key": key(summ[-1]) if summ else None,
                     "errs": [l for l in lines if "hb_error" in l],
                     "tell": next((l.split("hb_tell ", 1)[1] for l in lines if "hb_tell " in l), None),
                     "prices": next((l.split("hb_prices ", 1)[1] for l in lines if "hb_prices " in l), None),
                     "heard": kv.get("heard"), "main_nodes": kv.get("main_nodes"), "probe_nodes": kv.get("probe_nodes")}
        e.close()
    return out
same = diff = 0
for gi, cut in ((3, 40), (11, 61), (35, 72), (22, 139), (16, 83)):
    a = run(OLD, {}, res[gi], cut)
    b = run(NEW, {}, res[gi], cut)
    c = run(NEW, {"HBTell": "alarm"}, res[gi], cut)
    d = run(NEW, {"HBTell": "table"}, res[gi], cut)
    for seat in a:
        ok = (a[seat]["move"], a[seat]["key"]) == (b[seat]["move"], b[seat]["key"]); same += ok; diff += not ok
        ok2 = (a[seat]["move"], a[seat]["key"]) == (c[seat]["move"], c[seat]["key"])
        print(gi, cut, seat, a[seat]["move"], a[seat]["key"], "| off:", "IDENTICAL" if ok else f"DIFFERENT {b[seat]['key']}",
              "| alarm, nothing heard:", "IDENTICAL" if ok2 else f"DIFFERENT {c[seat]['move']} {c[seat]['key']}", "tell off:", b[seat]["tell"], "errs", b[seat]["errs"] + c[seat]["errs"] + d[seat]["errs"], flush=True)
        print("     alarm says:", c[seat]["tell"], flush=True)
        print("     table says:", d[seat]["tell"], "| move", d[seat]["move"], "main_nodes", d[seat]["main_nodes"], "(off:", b[seat]["main_nodes"], ") heard", d[seat]["heard"], flush=True)
    # the partner hears the table
    told = {s: d[s]["tell"] for s in d if d[s]["tell"] and " worth" in d[s]["tell"]}
    for teller, text in told.items():
        h = run(NEW, lambda seat: {"HBTell": "table", "HBPartnerTell": text}, res[gi], cut, only=[PARTNER[teller]])[PARTNER[teller]]
        print("     ", PARTNER[teller], "hears", teller, "->", h["heard"], "prices", h["prices"], "move", h["move"], "(without:", d[PARTNER[teller]]["move"], ")", flush=True)
print("identical with HBTell off:", same, "different:", diff)
