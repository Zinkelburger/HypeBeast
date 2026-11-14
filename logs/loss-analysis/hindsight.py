"""Were the switches away from the main search's move right, in hindsight?

For every world_switch of a match: the move played and the main search's move, each valued in
the world that really came: the position after the move, with the pieces that reached either
hand on that board before the seat's next move (q<=2) added to the hands, searched by a plain
engine (Coordination=false) from the opponent's seat. Value for the seat = minus that score.

    python3 hindsight.py logs/plan-vs-l50 bin/hypebeast-v8d [jobs] [nodes]

Groups: hb-plan switches that only the told line explains ("steered"), hb-plan switches its own
lines would have made too, hb-plan switches with no line heard, and the baseline's switches.
"""
import json, sys, math, collections, statistics, concurrent.futures as cf
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")
from hbutil import ROOT, Bughouse, Engine
D, BIN = sys.argv[1], sys.argv[2]
JOBS = int(sys.argv[3]) if len(sys.argv) > 3 else 4
NODES = int(sys.argv[4]) if len(sys.argv) > 4 else 1000000
rows = [json.loads(l) for l in open(f"{D}/postmortem.jsonl")]
res = {r["game"]: r for r in (json.loads(l) for l in open(f"{D}/results.jsonl"))}
TRUST, LATE, MINP, MAXW, SCALE = 0.85, 0.5, 0.04, 4, 1000.0
ORDER = "QRBNP"


def key(caps):
    us = collections.Counter(c[2] for c in caps if c[1] == "+"); th = collections.Counter(c[2] for c in caps if c[1] == "-")
    return "".join(("+" + t) * us[t] for t in ORDER) + "".join(("-" + t) * th[t] for t in ORDER) or "none"


def worlds(lines):
    tot = sum(l["w"] for l in lines)
    by = collections.defaultdict(float)
    for l in lines:
        w = l["w"] / tot
        early = [c for c in l["caps"] if int(c[0]) < 2]
        deeper = len(l["caps"]) > len(early)
        late = LATE if deeper else 0.0
        if deeper and late > 0: by[key(l["caps"])] += w * late
        if early: by[key(early)] += w * (TRUST - late)
    ws = sorted(((p, k) for k, p in by.items() if p >= MINP and k != "none"), key=lambda x: (-x[0], x[1]))[:MAXW - 1]
    out = {k: p for p, k in ws}
    out["none"] = 1 - sum(out.values())
    return out


def win(cp): return 1.0 if cp >= 90000 else 0.0 if cp <= -90000 else 1 / (1 + math.exp(-cp / SCALE))
def S(e):
    q = min(max(e, 1e-4), 1 - 1e-4); return SCALE * math.log(q / (1 - q))
def E(r, p, which):
    w0 = next(w for w in r["worlds"] if w["arrival"] == "none")
    if w0["v_main"] is None or w0[which] is None: return None
    base = win(min(w0[which], w0["v_main"]))
    e = p.get("none", 0) * base
    for w in r["worlds"]:
        if w["arrival"] != "none":
            e += p.get(w["arrival"], 0.0) * (win(w[which]) if w[which] is not None else base)
    return e


def group(r):
    if r["reason"] != "world_switch" or r["decision"] == r["main"] or not r["worlds"]:
        return None
    if r["engine"] != "hb-plan":
        return "baseline"
    if r.get("talk") != "plan":
        return "plan, no line heard"
    own = [l for l in r["lines"] if l["src"] != "told"]
    if not own:
        return None
    alone = worlds(own)
    em, ec = E(r, alone, "v_main"), E(r, alone, "v_chosen")
    if em is None or ec is None:
        return None
    return "plan, own lines would switch too" if S(ec) >= S(em) + 25 else "plan, steered by the told line"


def value(job):
    game, n, seat, move, arrived = job
    r = res[game]
    toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
    g = Bughouse()
    for t in toks[:n]:
        g.push(int(t[0]) - 1, t[1:])
    b = 0 if seat[0] == "A" else 1
    white = seat.endswith("white")
    if not g.is_legal(b, move):
        return None
    g.push(b, move)
    if not g.has_legal_move(b):
        return 100000       # the opponent has no move: mate (a fed blocker is not looked for)
    fens = g.dual_fen().split("|")
    add = "".join((t.upper() if (sign == "+") == white else t.lower()) for sign, t in arrived)
    i = fens[b].index("]")
    fens[b] = fens[b][:i] + add + fens[b][i:]
    opp = seat[0] + ("black" if white else "white")
    e = Engine(ROOT / BIN, options={"Hash": 64, "Coordination": "false", "HBFeedPrices": "false"})
    try:
        e.setoption("Seat", opp); e.setoption("Team", "white" if opp in ("Awhite", "Bblack") else "black")
        e.setoption("Clocks", "90000,90000,90000,90000"); e.send("ucinewgame"); e.sync()
        e.send("position fen " + "|".join(fens))
        lines = e.go(f"go nodes {NODES}", timeout=900)
    finally:
        e.close()
    summ = [l for l in lines if "hb_summary" in l]
    kv = dict(p.split("=", 1) for p in summ[-1].split() if "=" in p) if summ else {}
    sc = kv.get("main_score_cp", "")
    return -int(sc) if sc.lstrip("-").isdigit() else None


jobs, meta = [], []
for r in rows:
    gname = group(r)
    if not gname or r["left"] < 2:
        continue
    arrived = tuple((k[0], k[1]) for q, k, _ in r["future"] if q <= 2)
    meta.append((gname, r, arrived))
    for mv in (r["decision"], r["main"]):
        jobs.append((r["game"], r["n"], r["seat"], mv, arrived))
LIMIT = int(sys.argv[5]) if len(sys.argv) > 5 else 0
if LIMIT:
    meta, jobs = meta[:LIMIT], jobs[:2 * LIMIT]
print(f"{len(meta)} switches, {len(jobs)} searches of {NODES} nodes, {JOBS} at once", flush=True)
with cf.ThreadPoolExecutor(JOBS) as ex:
    vals = list(ex.map(value, jobs))
out = []
for i, (gname, r, arrived) in enumerate(meta):
    vp, vm = vals[2 * i], vals[2 * i + 1]
    out.append({"group": gname, "game": r["game"], "seat": r["seat"], "n": r["n"], "played": r["decision"], "main": r["main"],
                "arrived": ["".join(a) for a in arrived], "v_played": vp, "v_main": vm, "score": r["score"], "won": r["won"]})
json.dump(out, open(f"{D}/../loss-analysis/hindsight.json", "w"), indent=0)


def clip(v): return max(-2000, min(2000, v))
print("\ngroup | switches | judged | played better by 50+ | within 50 | main better by 50+ | mean gain of the switch (cp, each value clipped at +/-2000) | median | switch avoided a mate | switch walked into one")
for gname in ("plan, steered by the told line", "plan, own lines would switch too", "plan, no line heard", "baseline"):
    xs = [x for x in out if x["group"] == gname]
    ok = [x for x in xs if x["v_played"] is not None and x["v_main"] is not None]
    if not ok:
        print(f"{gname} | {len(xs)} | 0"); continue
    dd = [clip(x["v_played"]) - clip(x["v_main"]) for x in ok]
    n = len(ok)
    print(f"{gname} | {len(xs)} | {n} | {100*sum(d >= 50 for d in dd)/n:.0f}% | {100*sum(abs(d) < 50 for d in dd)/n:.0f}% | {100*sum(d <= -50 for d in dd)/n:.0f}% | {statistics.mean(dd):+.0f} | {statistics.median(dd):+.0f} | "
          f"{sum(x['v_main'] <= -90000 and x['v_played'] > -90000 for x in ok)} | {sum(x['v_played'] <= -90000 and x['v_main'] > -90000 for x in ok)}")
    for label, sel in (("something arrived", [x for x in ok if x["arrived"]]), ("nothing arrived", [x for x in ok if not x["arrived"]])):
        if sel:
            d2 = [clip(x["v_played"]) - clip(x["v_main"]) for x in sel]
            print(f"   {label}: {len(sel)}, mean gain {statistics.mean(d2):+.0f}, played better {100*sum(d >= 50 for d in d2)/len(sel):.0f}%, main better {100*sum(d <= -50 for d in d2)/len(sel):.0f}%")
