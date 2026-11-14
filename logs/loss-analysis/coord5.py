"""v8a against v7e: identical with HBArrivalTiming off? And what timing 1 and 2 do on the same decisions."""
import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")
from hbutil import ROOT, Bughouse, Engine, parse_bestmove
OLD, NEW = sys.argv[1], sys.argv[2]
res = [json.loads(l) for l in open(ROOT / "logs/late50-vs-np-b/results.jsonl")]
def key(s):
    kv = dict(p.split("=", 1) for p in s.split() if "=" in p)
    return tuple(kv.get(k) for k in ("decision", "main_score_cp", "coord_reason", "total_nodes", "main_depth"))
def run(binary, opts, r, cut):
    g = Bughouse()
    toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
    for t in toks[:cut]: g.push(int(t[0]) - 1, t[1:])
    out = []
    for seat in ("Awhite", "Ablack", "Bwhite", "Bblack"):
        e = Engine(ROOT / binary, options={"Hash": 64, "HBFeedPrices": "false", "HBForecastTrustLate": 50, **opts})
        e.setoption("Seat", seat); e.setoption("Team", "white" if seat in ("Awhite", "Bblack") else "black")
        e.setoption("Clocks", "90000,88000,91000,87000"); e.send("ucinewgame"); e.sync()
        e.send(f"position fen {g.dual_fen()}")
        lines = e.go("go nodes 500000", timeout=600)
        errs = [l for l in lines if "hb_error" in l or "hb_warn" in l]
        summ = [l for l in lines if "hb_summary" in l]
        coord = [l for l in lines if "hb_coord " in l]
        worlds = []
        if coord:
            try:
                j = json.loads(coord[-1].split("hb_coord ", 1)[1])
                worlds = [(w["arrival"], round(w["p"], 2), w.get("arrives", ""), w.get("depth"), w.get("best")) for w in j.get("worlds", [])]
            except Exception as ex:
                worlds = [("unparsed", str(ex))]
        out.append((seat, parse_bestmove(lines), errs, key(summ[-1]) if summ else None, worlds))
        e.close()
    return out
same = diff = 0
for gi, cut in ((3, 40), (11, 61), (35, 72)):
    a = run(OLD, {}, res[gi], cut)
    b = run(NEW, {}, res[gi], cut)
    for x, y in zip(a, b):
        ok = (x[1], x[3]) == (y[1], y[3]); same += ok; diff += not ok
        print(gi, cut, x[0], "old", x[1], x[3], "| new", "IDENTICAL" if ok else f"DIFFERENT {y[1]} {y[3]}", "errors:", y[2], flush=True)
    for mode in (1, 2):
        c = run(NEW, {"HBArrivalTiming": mode}, res[gi], cut)
        for x, z in zip(b, c):
            print("   timing", mode, z[0], "move", z[1], "(off:", x[1], ")", z[3][2] if z[3] else None, "errors:", z[2], flush=True)
            for w in z[4]: print("        ", w, flush=True)
print("identical", same, "different", diff)
