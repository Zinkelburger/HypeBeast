"""Decisions where hb-plan heard a line and KEPT the main move although its own lines alone would have switched."""
import json, sys, glob, math, collections, statistics
d = sys.argv[1]
TRUST, LATE, MINP, MAXW, SCALE = 0.85, 0.5, 0.04, 4, 1000.0
ORDER = "QRBNP"
def key(caps):
    us = collections.Counter(c[2] for c in caps if c[1] == "+"); th = collections.Counter(c[2] for c in caps if c[1] == "-")
    return "".join(("+" + t) * us[t] for t in ORDER) + "".join(("-" + t) * th[t] for t in ORDER) or "none"
def worlds(lines):
    tot = sum(l["weight"] for l in lines); by = collections.defaultdict(float)
    for l in lines:
        w = l["weight"] / tot; caps = l.get("captures", [])
        early = [c for c in caps if int(c[0]) < 2]; deeper = len(caps) > len(early)
        late = LATE if deeper else 0.0
        if deeper and late > 0: by[key(caps)] += w * late
        if early: by[key(early)] += w * (TRUST - late)
    ws = sorted(((p, k) for k, p in by.items() if p >= MINP and k != "none"), key=lambda x: (-x[0], x[1]))[:MAXW - 1]
    out = {k: p for p, k in ws}; out["none"] = 1 - sum(out.values()); return out
def win(cp): return 1.0 if cp >= 90000 else 0.0 if cp <= -90000 else 1 / (1 + math.exp(-cp / SCALE))
def S(e):
    q = min(max(e, 1e-4), 1 - 1e-4); return SCALE * math.log(q / (1 - q))
def E(cw, p, c, main):
    w0 = cw.get("none")
    if not w0 or c not in w0["values"] or main not in w0["values"]: return None
    base = win(min(w0["values"][c], w0["values"][main])); e = p.get("none", 0) * base
    for k, w in cw.items():
        if k != "none":
            e += p.get(k, 0.0) * (win(w["values"][c]) if c in w["values"] else base)
    return e
pm = {(r["game"], r["seat"], r["n"]): r for r in map(json.loads, open(f"{d}/postmortem.jsonl"))}
games = [json.loads(l) for l in open(f"{d}/results.jsonl")]
index = collections.defaultdict(list)
for r in games:
    toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
    index[tuple(toks[:12])].append((r, toks))
stat = collections.Counter(); errE = []; un = []; sw_alone_too = 0
for path in sorted(glob.glob(f"{d}/engine_logs/w*-contender-*.log")):
    seat = moves = None; block = None
    for line in open(path, errors="replace"):
        if line.startswith(">>> setoption name Seat value "): seat = line.split()[-1]
        elif line.startswith(">>> position startpos moves "): moves = line.split()[4:]
        elif line.startswith(">>> go"): block = {}
        elif block is None: continue
        elif line.startswith("info string hb_forecast "): block["fc"] = json.loads(line.split("hb_forecast ", 1)[1])
        elif line.startswith("info string hb_coord "): block["co"] = json.loads(line.split("hb_coord ", 1)[1])
        elif line.startswith("info string hb_summary "): block["sum"] = dict(p.split("=", 1) for p in line.split()[3:] if "=" in p)
        elif line.startswith("bestmove"):
            b, block = block, None
            fc, co, s = b.get("fc"), b.get("co"), b.get("sum")
            if not (fc and co and s) or s.get("reason") not in ("kept_main", "world_switch"): continue
            lines = fc.get("lines", [])
            told = [l for l in lines if l.get("source") == "told"]; own = [l for l in lines if l.get("source") != "told"]
            if fc.get("talk") != "plan" or not told or not own: continue
            cands = co.get("candidates", [])
            if len(cands) < 2: stat["one candidate"] += 1; continue
            main = cands[0]["move"]; cw = {w["arrival"]: w for w in co["worlds"] if w.get("scored", True) and w.get("values")}
            logged = {w["arrival"]: w["p"] for w in fc.get("worlds", [])}
            alone = worlds(own)
            stat["heard, kept or switched, 2+ candidates"] += 1
            # check of the rule on the logged probabilities
            es = {c["move"]: E(cw, logged, c["move"], main) for c in cands}
            if any(v is None for v in es.values()): stat["no value"] += 1; continue
            for c in cands: errE.append(abs(es[c["move"]] - c["E"]))
            best = max((c["move"] for c in cands[1:]), key=lambda m: S(es[m]))
            pred = S(es[best]) >= S(es[main]) + 25
            actual = s["reason"] == "world_switch"
            stat[f"rule check: predicted {'switch' if pred else 'keep'}, engine {'switched' if actual else 'kept'}"] += 1
            covered = set(alone) <= set(cw) | {"none"}
            ea = {c["move"]: E(cw, alone, c["move"], main) for c in cands}
            besta = max((c["move"] for c in cands[1:]), key=lambda m: S(ea[m]))
            preda = S(ea[besta]) >= S(ea[main]) + 25
            if not actual and preda:
                g = next(((r, t) for r, t in index.get(tuple(moves[:12]), []) if t[:len(moves)] == moves), None)
                row = pm.get((g[0]["game"], seat, len(moves))) if g else None
                un.append({"covered": covered, "row": row, "alt": besta, "gap": S(ea[besta]) - S(ea[main]), "pred_logged": pred})
            if actual and preda: sw_alone_too += 1
for k, v in sorted(stat.items()): print(v, k)
print("recomputed E against logged E: mean abs diff %.4f, share within 0.01: %.0f%%" % (statistics.mean(errE), 100 * sum(e < 0.01 for e in errE) / len(errE)))
print("switches its own lines would also make (by this rule):", sw_alone_too)
print("\nUN-SWITCHES: kept the main move with the told line; own lines alone would have switched:", len(un))
for name, sel in (("all", un), ("own worlds all scored (clean)", [u for u in un if u["covered"]]), ("clean and rule agrees with engine on logged p", [u for u in un if u["covered"] and not u["pred_logged"]])):
    rs = [u["row"] for u in sel if u["row"]]
    if not rs: print(name, len(sel)); continue
    noth = [r for r in rs if r["left"] >= 2 and not any(f[0] <= 2 for f in r["future"])]
    some = [r for r in rs if r["left"] >= 2 and any(f[0] <= 2 for f in r["future"])]
    ds = [r["next_score"] - r["score"] for r in rs if r["next_score"] is not None and r["score"] is not None and abs(r["score"]) < 90000 and abs(r["next_score"]) < 90000]
    print(f"{name}: {len(sel)} (matched {len(rs)}); nothing arrived before next move {len(noth)}, something arrived {len(some)}; next-decision score change mean {statistics.mean(ds):+.0f} median {statistics.median(ds):+.0f}; then mated {sum(1 for r in rs if r['next_score'] is not None and r['next_score'] <= -90000)}; games {len({r['game'] for r in rs})}; won {100*statistics.mean(r['won'] for r in rs):.0f}%")
    print("   gap own lines saw for the other move (S, cp): median %.0f" % statistics.median(u["gap"] for u in sel))
