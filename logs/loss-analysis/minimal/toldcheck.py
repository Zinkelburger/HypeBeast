"""Hand checks of the told path: how old each accepted message is, which lines fit, and whether the
forecast lines are the told lines from the current partner position.

    python3 logs/loss-analysis/minimal/toldcheck.py
"""
import collections, json, re, sys
sys.dont_write_bytecode = True
HERE = "/home/anbernal/Projects/HypeBeast-v5/logs/loss-analysis/minimal"
ds = [json.loads(l) for l in open(HERE + "/decisions.jsonl")]
LOSSES = {1, 2, 3, 4, 6, 9, 10, 11, 12, 13, 16}

def parse(t):
    m = dict(re.findall(r"(\w+)=(\S+)", t.split(" lines ")[0]))
    lines = []
    if " lines " in t:
        for tok in t.split(" lines ", 1)[1].split():
            w, mv = tok.split(":", 1)
            lines.append((int(w), mv.split(",")))
    return m, lines

skips = collections.Counter(); fitc = collections.Counter(); out = []
for d in ds:
    if d["role"] != "contender" or (d.get("fc") or {}).get("talk") != "told":
        continue
    t = d["opts"]["HBPartnerTell"]
    m, lines = parse(t)
    pb = "2" if d["seat"][0] == "A" else "1"
    moves = d["pos"].split()[3:] if " moves " in d["pos"] else []
    played = [x[1:] for x in moves if x[0] == pb]
    skip = len(played) - int(m["at"])
    fit = [(w, l) for w, l in lines if len(l) > skip and l[:skip] == played[int(m["at"]):]]
    tw = sum(w for w, _ in lines); fw = sum(w for w, _ in fit)
    skips[skip] += 1
    fitc[(skip, len(lines), len(fit))] += 1
    fc = d["fc"]
    # forecast lines should be the fitting lines minus the first `skip` moves
    exp = [l[skip:] for _, l in fit]
    got = [x["pv"] for x in fc["lines"]]
    ok = all(g == e[:len(g)] for g, e in zip(got, exp)) and len(got) == len(exp)
    out.append({"game": d["game"], "seat": d["seat"], "n": d["n"], "skip": skip, "lines": len(lines), "fit": len(fit),
                "fit_share": fw / tw, "ok": ok, "mover": fc["mover"], "worlds": fc["worlds"], "team_mate": fc["team_mate"],
                "told_mate": int(m["mate"]), "told_n": int(m["n"]), "partner_plies": len(played)})
print("skip (partner-board plies since the lines' first move):", dict(sorted(skips.items())))
print("(skip, told lines, fitting lines):", dict(sorted(fitc.items())))
print("forecast lines == fitting told lines from now:", collections.Counter(o["ok"] for o in out))
print("teller's n vs partner plies now (n - plies):", collections.Counter(o["told_n"] - o["partner_plies"] for o in out))
print("fit share when skip>=2:", sorted(round(o["fit_share"], 2) for o in out if o["skip"] >= 2)[:60])
print("one world only (none):", sum(len(o["worlds"]) == 1 for o in out), "of", len(out))
print("mover:", collections.Counter((o["skip"], o["mover"]) for o in out))
json.dump(out, open(HERE + "/toldcheck.json", "w"))
