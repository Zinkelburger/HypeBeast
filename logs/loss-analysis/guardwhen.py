"""When a mate price is set (a piece of ours would mate our partner), how is the partner's board doing already?
    python3 guardwhen.py logs/matefree logs/mateprice-vs-np
Per contender decision with a mate price on a type on our board: the partner board's score in our team's view
(the probe's base), in bands, with the share of those games won; and the first such decision of each game.
"""
import json, sys, glob, collections, statistics
for d in sys.argv[1:]:
    d = d.rstrip("/")
    res = [json.loads(l) for l in open(f"{d}/results.jsonl")]
    con = res[0]["contender"]
    index = collections.defaultdict(list)
    for r in res:
        toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
        index[tuple(toks[:12])].append((r, toks))
    recs = []
    for path in sorted(glob.glob(f"{d}/engine_logs/w*-contender-*.log")):
        seat = moves = None; block = None
        for line in open(path, errors="replace"):
            if line.startswith(">>> setoption name Seat value "): seat = line.split()[-1]
            elif line.startswith(">>> position startpos moves "): moves = line.split()[4:]
            elif line.startswith(">>> go"): block = {}
            elif block is None: continue
            elif line.startswith("info string hb_prices "): block["p"] = json.loads(line.split("hb_prices ", 1)[1])
            elif line.startswith("info string hb_summary "): block["s"] = dict(p.split("=", 1) for p in line.split()[3:] if "=" in p)
            elif line.startswith("bestmove"):
                b, block = block, None
                p, s = b.get("p"), b.get("s", {})
                if not p or moves is None or seat is None: continue
                g0 = next(((r, t) for r, t in index.get(tuple(moves[:12]), []) if t[:len(moves)] == moves and r["seats"][seat[0] + "-" + seat[1:]] == con), None)
                if not g0: continue
                team = "white" if seat in ("Awhite", "Bblack") else "black"
                won = g0[0]["result"]["winner"] == team
                own = int(s["main_score_cp"]) if s.get("main_score_cp", "").lstrip("-").isdigit() else None
                recs.append({"game": g0[0]["game"], "seat": seat, "n": len(moves), "flag": any(v == 1500 for v in p["theirs"].values()),
                             "base": p["base"], "won": won, "own": own})
    print(f"\n{d}: {con}, {len(recs)} decisions, {sum(r['flag'] for r in recs)} with a mate price")
    print("partner's board (our team's view) when a mate price is set | decisions | games | games won")
    for lo, hi, name in ((-10**9, -1000, "below -1000 (lost or being mated)"), (-1000, -300, "-1000 to -300"), (-300, 300, "-300 to +300 (level)"), (300, 10**9, "above +300")):
        rs = [r for r in recs if r["flag"] and lo <= r["base"] < hi]
        gs = {(r["game"], r["seat"]): r["won"] for r in rs}
        print(f"{name} | {len(rs)} | {len(gs)} | {100*sum(gs.values())/max(1,len(gs)):.0f}%")
    first = {}
    for r in sorted(recs, key=lambda r: r["n"]):
        if r["flag"] and (r["game"], r["seat"]) not in first: first[(r["game"], r["seat"])] = r
    fs = list(first.values())
    print(f"first mate price of a seat in a game: {len(fs)} seats in {len({r['game'] for r in fs})} games; partner's board then: median {statistics.median(r['base'] for r in fs):+.0f}, "
          f"level or better (-300+) in {sum(r['base'] >= -300 for r in fs)}; those games won {100*statistics.mean(r['won'] for r in fs if r['base'] >= -300):.0f}%, the others {100*statistics.mean(r['won'] for r in fs if r['base'] < -300):.0f}%")
    noflag_games = {r["game"] for r in recs} - {r["game"] for r in fs}
    print(f"games with no mate price at all: {len(noflag_games)}, won {100*statistics.mean(next(x['won'] for x in recs if x['game']==g) for g in noflag_games):.0f}%")
