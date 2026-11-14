"""feed-b: did the partner's board gain what the message said it would?

For every hb-feed decision with a feed term: the move played and the main search's move, their feed values,
and what followed on both boards: the seat's own score at its next decision minus now, and the partner's score
at its first decision after ours minus its last before ours. Logs only.
    python3 feedtruth.py logs/feed-b
"""
import json, sys, glob, collections, statistics
d = sys.argv[1].rstrip("/")
rows = [json.loads(l) for l in open(f"{d}/postmortem.jsonl")]
res = [json.loads(l) for l in open(f"{d}/results.jsonl")]
con = res[0]["contender"]
PARTNER = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
by = collections.defaultdict(list)
for r in rows: by[(r["game"], r["seat"])].append(r)
for v in by.values(): v.sort(key=lambda r: r["n"])
pm = {(r["game"], r["seat"], r["n"]): r for r in rows}
index = collections.defaultdict(list)
for r in res:
    toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
    index[tuple(toks[:12])].append((r, toks))
ok = lambda s: s is not None and abs(s) < 90000
recs = []
for path in sorted(glob.glob(f"{d}/engine_logs/w*-contender-*.log")):
    seat = moves = None; block = None
    for line in open(path, errors="replace"):
        if line.startswith(">>> setoption name Seat value "): seat = line.split()[-1]
        elif line.startswith(">>> position startpos moves "): moves = line.split()[4:]
        elif line.startswith(">>> go"): block = {}
        elif block is None: continue
        elif line.startswith("info string hb_coord "): block["co"] = json.loads(line.split("hb_coord ", 1)[1])
        elif line.startswith("info string hb_summary "): block["s"] = dict(p.split("=", 1) for p in line.split()[3:] if "=" in p)
        elif line.startswith("bestmove"):
            b, block = block, None
            co, s = b.get("co"), b.get("s")
            if not co or not s or moves is None or seat is None: continue
            cs = {c["move"]: c for c in co.get("candidates", [])}
            if not any(c.get("feed") for c in cs.values()): continue
            g0 = next(((r, t) for r, t in index.get(tuple(moves[:12]), []) if t[:len(moves)] == moves and r["seats"][seat[0] + "-" + seat[1:]] == con), None)
            row = pm.get((g0[0]["game"], seat, len(moves))) if g0 else None
            if not row or row["decision"] not in cs: continue
            main = co["candidates"][0]["move"]
            pr = by[(row["game"], PARTNER[seat])]
            before = [r for r in pr if r["n"] < row["n"]]; after = [r for r in pr if r["n"] > row["n"]]
            own = row["next_score"] - row["score"] if ok(row["next_score"]) and ok(row["score"]) else None
            par = after[0]["score"] - before[-1]["score"] if before and after and ok(after[0]["score"]) and ok(before[-1]["score"]) else None
            recs.append({"reason": s.get("reason"), "feed_played": cs[row["decision"]].get("feed", 0), "feed_main": cs[main].get("feed", 0),
                         "own": own, "par": par, "kept": s.get("feed_kept") == "1", "won": row["won"],
                         "L_played": cs[row["decision"]].get("L"), "L_main": cs[main].get("L")})
def line(name, rs):
    o = [r["own"] for r in rs if r["own"] is not None]; p = [r["par"] for r in rs if r["par"] is not None]
    both = [r["own"] + r["par"] for r in rs if r["own"] is not None and r["par"] is not None]
    gap = [r["L_played"] - r["L_main"] for r in rs if r["L_played"] is not None and r["L_main"] is not None]
    if not rs: return f"{name} | 0"
    return (f"{name} | {len(rs)} | {statistics.mean(r['feed_played'] - r['feed_main'] for r in rs):+.0f} | {statistics.mean(gap) if gap else 0:+.0f} | "
            f"{statistics.mean(o) if o else 0:+.0f} | {statistics.mean(p) if p else 0:+.0f} | {statistics.mean(both) if both else 0:+.0f} | {100*statistics.mean(r['won'] for r in rs):.0f}%")
print(f"{d}: {len(recs)} decisions of {con} with a feed term on some candidate")
print("group | n | feed of the move played minus the main move's | its own-board value minus the main move's (nothing arrives) | own score, next decision minus now | partner's score, after minus before | both | games won")
print(line("feed_switch (the message changed the move)", [r for r in recs if r["reason"] == "feed_switch"]))
fs = [r for r in recs if r["reason"] == "feed_switch"]
print(line("   ... to gain for the partner (played move's feed above 0)", [r for r in fs if r["feed_played"] > 0]))
print(line("   ... to avoid a cost (main move's feed below 0)", [r for r in fs if r["feed_main"] < 0 and r["feed_played"] >= 0]))
print(line("world_switch, a feed term present", [r for r in recs if r["reason"] == "world_switch"]))
print(line("kept the main move, its feed above 0", [r for r in recs if r["reason"] == "kept_main" and r["feed_played"] > 0]))
print(line("kept the main move, its feed below 0", [r for r in recs if r["reason"] == "kept_main" and r["feed_played"] < 0]))
print(line("kept the main move, its feed 0 (another candidate had one)", [r for r in recs if r["reason"] == "kept_main" and r["feed_played"] == 0]))
# does a told gain show on the partner's board at all? played move's feed against the partner's drift
for lo, hi in ((-2000, -500), (-500, -150), (150, 300), (300, 500), (500, 2000)):
    rs = [r for r in recs if lo <= r["feed_played"] < hi and r["par"] is not None]
    if rs: print(f"move played had feed {lo} to {hi}: n {len(rs)}, mean feed {statistics.mean(r['feed_played'] for r in rs):+.0f}, partner's score change {statistics.mean(r['par'] for r in rs):+.0f} (median {statistics.median(r['par'] for r in rs):+.0f})")
