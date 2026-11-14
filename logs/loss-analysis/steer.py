"""Did the partner's told line (HBTell=plan) steer decisions, and were those right?
For every hb-plan decision that heard a line: the worlds as logged against the worlds its own
lines alone would have made, which switches away from the main move only the told line explains,
whether the worlds it raised came true, and how the games won differ between the two engines."""
import json, sys, math, collections, statistics
d = sys.argv[1]
rows = [json.loads(l) for l in open(f"{d}/postmortem.jsonl")]
TRUST, LATE, MINP, MAXW, SCALE = 0.85, 0.5, 0.04, 4, 1000.0
ORDER = "QRBNP"

def key(caps):
    us = collections.Counter(c[2] for c in caps if c[1] == "+"); th = collections.Counter(c[2] for c in caps if c[1] == "-")
    s = "".join(("+" + t) * us[t] for t in ORDER) + "".join(("-" + t) * th[t] for t in ORDER)
    return s or "none"

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
    e = p.get("none", 0) * win(min(w0[which], w0["v_main"]))
    rest = 0.0
    for w in r["worlds"]:
        if w["arrival"] == "none": continue
        pw = p.get(w["arrival"], 0.0)
        if w[which] is None: e += 0; rest += pw; continue
        e += pw * win(w[which])
    # a world with no value counts as "nothing arrives"
    return e + rest * win(min(w0[which], w0["v_main"]))

plan = [r for r in rows if r["engine"] == "hb-plan" and r.get("talk") == "plan" and r["lines"]]
base = [r for r in rows if r["engine"] == "hb-l50"]
chk = n_chk = 0
recs = []
for r in plan:
    own = [l for l in r["lines"] if l["src"] != "told"]
    told = [l for l in r["lines"] if l["src"] == "told"]
    if not own or not told: continue
    logged = {w["arrival"]: w["p"] for w in r["worlds"]}
    mine = worlds(r["lines"])
    n_chk += 1; chk += set(mine) == set(logged) and all(abs(mine[k] - logged[k]) < 0.01 for k in mine)
    alone = worlds(own)
    tk = {key(told[0]["caps"]), key([c for c in told[0]["caps"] if int(c[0]) < 2])} - {"none"}
    ownkeys = set()
    for l in own:
        ownkeys |= {key(l["caps"]), key([c for c in l["caps"] if int(c[0]) < 2])}
    top_own = max(own, key=lambda l: l["w"])
    recs.append({"r": r, "logged": logged, "alone": alone, "told_keys": tk, "new": bool(tk - ownkeys), "nocap": not tk,
                 "same_move": told[0]["move"] == top_own["move"]})
print(f"decisions that heard a line: {len(recs)} of {sum(1 for r in rows if r['engine']=='hb-plan' and r.get('talk'))} hb-plan decisions with a forecast")
print(f"worlds recomputed from the logged lines equal the logged worlds in {chk} of {n_chk} (check of this script)")
print(f"told line's first move = own search's heaviest line's move: {sum(x['same_move'] for x in recs)} ({100*sum(x['same_move'] for x in recs)/len(recs):.0f}%)")
print(f"told line has no capture: {sum(x['nocap'] for x in recs)} ({100*sum(x['nocap'] for x in recs)/len(recs):.0f}%); a capture package no own line had: {sum(x['new'] for x in recs)} ({100*sum(x['new'] for x in recs)/len(recs):.0f}%)")

# worlds raised or lowered by the told line, and whether they came true
def came(w, Q): return w["q_all"] is not None and w["q_all"] <= Q
bins = collections.defaultdict(list)
for x in recs:
    r = x["r"]
    if r["left"] < 6: continue
    for w in r["worlds"]:
        if w["arrival"] == "none": continue
        dp = w["p"] - x["alone"].get(w["arrival"], 0.0)
        b = "raised by 0.15+" if dp >= 0.15 else "lowered by 0.15+" if dp <= -0.15 else "about the same"
        bins[b].append((w, x["alone"].get(w["arrival"], 0.0)))
print("\nworlds of hb-plan (6+ plies left) by what the told line did to their probability:")
print("change | worlds | p with the told line | p from own lines alone | arrived by q<=2 | by q<=4")
for b in ("raised by 0.15+", "about the same", "lowered by 0.15+"):
    ws = bins[b]
    if ws: print(f"{b} | {len(ws)} | {statistics.mean(w['p'] for w, _ in ws):.2f} | {statistics.mean(a for _, a in ws):.2f} | {100*sum(came(w,2) for w,_ in ws)/len(ws):.0f}% | {100*sum(came(w,4) for w,_ in ws)/len(ws):.0f}%")
# nothing-arrives raised
nn = [(x["logged"].get("none", 1) - x["alone"].get("none", 1), x["r"]) for x in recs if x["r"]["left"] >= 6]
for name, sel in (("told line raised 'nothing arrives' by 0.15+", [r for dp, r in nn if dp >= 0.15]), ("lowered it by 0.15+", [r for dp, r in nn if dp <= -0.15])):
    if sel: print(f"{name}: {len(sel)} decisions; nothing arrived by q<=2 in {100*sum(not any(f[0]<=2 for f in r['future']) for r in sel)/len(sel):.0f}%, by q<=4 in {100*sum(not any(f[0]<=4 for f in r['future']) for r in sel)/len(sel):.0f}%")

# switches only the told line explains
def delta(r): return None if r["next_score"] is None or r["score"] is None or abs(r["score"]) >= 90000 or abs(r["next_score"]) >= 90000 else r["next_score"] - r["score"]
sw = [x for x in recs if x["r"]["reason"] == "world_switch" and x["r"]["decision"] != x["r"]["main"]]
steered, also = [], []
for x in sw:
    r = x["r"]
    em, ec = E(r, x["alone"], "v_main"), E(r, x["alone"], "v_chosen")
    if em is None or ec is None: continue
    (also if S(ec) >= S(em) + 25 else steered).append(x)
def line(name, rs):
    ds = [delta(r) for r in rs if delta(r) is not None]
    mated = sum(1 for r in rs if r["next_score"] is not None and r["next_score"] <= -90000)
    if not rs: return f"{name} | 0"
    return f"{name} | {len(rs)} | {statistics.mean(ds):+.0f} | {statistics.median(ds):+.0f} | {100*sum(d<=-200 for d in ds)/len(ds):.0f}% | {100*sum(d>=200 for d in ds)/len(ds):.0f}% | {mated} | {100*statistics.mean(r['won'] for r in rs):.0f}%"
print("\nswitches away from the main search's move, and the seat's own score at its next decision minus now:")
print("group | n | mean change (cp) | median | 200+ worse | 200+ better | then mated | games won")
print(line("hb-plan, only the told line explains the switch", [x["r"] for x in steered]))
print(line("hb-plan, its own lines would have switched too", [x["r"] for x in also]))
print(line("hb-plan, switch with no line heard", [r for r in rows if r["engine"]=="hb-plan" and r["reason"]=="world_switch" and r.get("talk")!="plan"]))
print(line("hb-l50, every switch", [r for r in base if r["reason"]=="world_switch"]))
print(line("hb-plan, kept the main move, line heard", [x["r"] for x in recs if x["r"]["decision"]==x["r"]["main"]]))
print(line("hb-l50, kept the main move", [r for r in base if r["decision"]==r["main"]]))
# did the world behind a steered switch come true?
hit = tot = 0
for x in steered:
    r = x["r"]
    best = max((w for w in r["worlds"] if w["arrival"] != "none" and w["v_chosen"] is not None and w["v_main"] is not None),
               key=lambda w: w["p"] * (win(w["v_chosen"]) - win(w["v_main"])), default=None)
    if best: tot += 1; hit += came(best, 4)
print(f"the world that most favoured a steered switch had arrived by q<=4 in {hit} of {tot}")
json.dump([{"game": x["r"]["game"], "seat": x["r"]["seat"], "n": x["r"]["n"], "main": x["r"]["main"], "played": x["r"]["decision"],
            "score": x["r"]["score"], "next": x["r"]["next_score"], "won": x["r"]["won"], "worlds": x["logged"], "own_alone": x["alone"]} for x in steered],
          open(f"{d}/../loss-analysis/steered.json", "w"), indent=0)

# how the games won differ
games = collections.defaultdict(lambda: collections.defaultdict(list))
for r in rows: games[r["game"]][r["engine"]].append(r)
steer_by_game = collections.Counter((x["r"]["game"]) for x in steered)
print("\ngames by winner:")
print("winner | games | mean plies of the game | winner's switches a game | loser's | winner first led by 300+ at ply (median) | loser was level or better one decision before it saw mate | loser's partner's line had... n/a")
for eng in ("hb-plan", "hb-l50"):
    gs = [g for g, by in games.items() if by[eng] and by[eng][0]["won"] == 1.0]
    if not gs: continue
    other = "hb-l50" if eng == "hb-plan" else "hb-plan"
    plies = [max(r["n"] for e in games[g].values() for r in e) for g in gs]
    wsw = [sum(r["reason"] == "world_switch" for r in games[g][eng]) for g in gs]
    lsw = [sum(r["reason"] == "world_switch" for r in games[g][other]) for g in gs]
    lead = []
    sudden = 0
    for g in gs:
        first = next((r["n"] for r in sorted(games[g][eng], key=lambda r: r["n"]) if r["score"] is not None and r["score"] >= 300), None)
        if first is not None: lead.append(first)
        ls = sorted(games[g][other], key=lambda r: r["n"])
        for a in ls:
            if a["next_score"] is not None and a["next_score"] <= -90000 and a["score"] is not None and a["score"] > -90000:
                sudden += a["score"] >= -300
                break
    print(f"{eng} | {len(gs)} | {statistics.mean(plies):.0f} | {statistics.mean(wsw):.1f} | {statistics.mean(lsw):.1f} | {statistics.median(lead) if lead else '-'} | {sudden} of {len(gs)}")
pw = [g for g, by in games.items() if by["hb-plan"] and by["hb-plan"][0]["won"] == 1.0]
pl = [g for g, by in games.items() if by["hb-plan"] and by["hb-plan"][0]["won"] == 0.0]
print(f"steered switches a game: in hb-plan's wins {sum(steer_by_game[g] for g in pw)/max(1,len(pw)):.1f}, in its losses {sum(steer_by_game[g] for g in pl)/max(1,len(pl)):.1f}")
