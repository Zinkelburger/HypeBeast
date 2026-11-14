"""How many earlier gos of the seat must be replayed before a decision for the replay to give the logged answer?
    nice -n 10 python3 prefix_test.py P N   (P earlier gos, first N told decisions of the losses)"""
import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/logs/loss-analysis/minimal")
from seqreplay import Seat, seat_gos, K
P, N = int(sys.argv[1]), int(sys.argv[2])
ds = [json.loads(l) for l in open("/home/anbernal/Projects/HypeBeast-v5/logs/loss-analysis/minimal/decisions.jsonl")]
LOSSES = {1, 2, 3, 4, 6, 9, 10, 11, 12, 13, 16}
todo = sorted([d for d in ds if d["role"] == "contender" and d["game"] in LOSSES and (d.get("fc") or {}).get("talk") == "told"],
              key=lambda d: (d["game"], d["n"], d["seat"]))[:N]
mv = key = 0
out = open(f"/home/anbernal/Projects/HypeBeast-v5/logs/loss-analysis/minimal/prefix{P}.jsonl", "w")
for d in todo:
    gos = seat_gos(ds, d["game"], d["seat"])
    i = [g["n"] for g in gos].index(d["n"])
    s = Seat(gos[0])
    for g in gos[max(0, i - P):i]:
        s.ask(g)
    r = s.ask(d)
    s.close()
    a, b = [d["sum"].get(x) for x in K], [r["sum"].get(x) for x in K]
    mv += a[0] == b[0]; key += a == b
    out.write(json.dumps({"game": d["game"], "seat": d["seat"], "n": d["n"], "logged": a, "replay": b}) + "\n")
print(f"prefix {P}: move {mv}/{len(todo)} key {key}/{len(todo)}")
