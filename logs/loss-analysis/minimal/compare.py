"""Told against own: what hb-minimal played with the partner's message and what it would have played without.

Reads decisions.jsonl (logged gos), replay.jsonl (fresh-process replays: told / own),
judge.jsonl (neutral values of both moves, when present), branch.jsonl (own with the
seat's history replayed, when present) and the post-mortem rows; writes compare.json
and prints the counts.

    python3 logs/loss-analysis/minimal/compare.py
"""
import collections
import json
import os
import sys

sys.dont_write_bytecode = True
ROOT = "/home/anbernal/Projects/HypeBeast-v5"
HERE = ROOT + "/logs/loss-analysis/minimal"
LOSSES = {1, 2, 3, 4, 6, 9, 10, 11, 12, 13, 16}
K = ("decision", "main_score_cp", "coord_reason", "total_nodes", "main_depth")


def load(p):
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def worlds(fc):
    return " ".join(f"{w['arrival']}={w['p']:.2f}" for w in (fc or {}).get("worlds", []))


def main():
    ds = {(d["game"], d["seat"], d["n"]): d for d in load(HERE + "/decisions.jsonl") if d["role"] == "contender"}
    pm = {(r["game"], r["seat"], r["n"]): r for r in load(ROOT + "/logs/minimal-vs-l50/postmortem.jsonl")
          if r["engine"] == "hb-minimal"}
    rep = collections.defaultdict(dict)
    for r in load(HERE + "/replay.jsonl"):
        rep[(r["game"], r["seat"], r["n"])][r["mode"]] = r
    judge = {(r["game"], r["seat"], r["n"]): r for r in load(HERE + "/judge.jsonl")}
    branch = {(r["game"], r["seat"], r["n"]): r for r in load(HERE + "/branch.jsonl")}
    out = []
    for k, m in sorted(rep.items()):
        if "told" not in m or "own" not in m:
            continue
        d, t, o = ds[k], m["told"], m["own"]
        p = pm.get(k, {})
        row = {"game": k[0], "seat": k[1], "n": k[2], "loss": k[0] in LOSSES,
               "logged": d["sum"].get("decision"), "logged_reason": d["sum"].get("coord_reason"),
               "logged_score": d["sum"].get("main_score_cp"),
               "move_reproduced": t["sum"].get("decision") == d["sum"].get("decision"),
               "key_reproduced": [t["sum"].get(x) for x in K] == [d["sum"].get(x) for x in K],
               "told": t["sum"].get("decision"), "told_reason": t["sum"].get("coord_reason"),
               "own": o["sum"].get("decision"), "own_reason": o["sum"].get("coord_reason"),
               "own_talk": (o.get("fc") or {}).get("talk"),
               "told_worlds": worlds(d.get("fc")), "own_worlds": worlds(o.get("fc")),
               "own_lines": [(l["source"], round(l["weight"], 2), l["pv"][:4], l["captures"]) for l in (o.get("fc") or {}).get("lines", [])],
               "told_lines": [(l["source"], round(l["weight"], 2), l["pv"][:4], l["captures"]) for l in (d.get("fc") or {}).get("lines", [])],
               "told_score": t["sum"].get("main_score_cp"), "own_score": o["sum"].get("main_score_cp"),
               "own_main": o["coord"].get("candidates", [{}])[0].get("move") if o.get("coord") and o["coord"].get("candidates") else None,
               "next_score": p.get("next_score"), "score": p.get("score"), "future": p.get("future"), "won": p.get("won")}
        row["differ"] = row["told"] != row["own"]
        j = judge.get(k)
        if j and j["told_move"] == row["told"] and j["own_move"] == row["own"]:
            row["v_told"], row["v_own"] = j["told"]["v"], j["own"]["v"]
        b = branch.get(k)
        if b:
            row["branch_own"] = b["sum"].get("decision")
            row["branch_own_reason"] = b["sum"].get("coord_reason")
        out.append(row)
    json.dump(out, open(HERE + "/compare.json", "w"), indent=0)

    for name, sel in (("losses", [r for r in out if r["loss"]]), ("wins", [r for r in out if not r["loss"]])):
        n = len(sel)
        print(f"== {name}: {n} told decisions replayed")
        print("  fresh told replay reproduces logged move:", sum(r["move_reproduced"] for r in sel),
              " full key (move,score,reason,nodes,depth):", sum(r["key_reproduced"] for r in sel))
        dif = [r for r in sel if r["differ"]]
        print("  own (nothing heard) differs from told (fresh both):", len(dif))
        dl = [r for r in sel if r["logged"] != r["own"]]
        print("  own differs from the LOGGED move:", len(dl))
        c = collections.Counter((r["told_reason"], r["own_reason"]) for r in dif)
        for (a, b), v in c.most_common():
            print(f"    {a} -> {b}: {v}")
        js = [r for r in dif if r.get("v_told") is not None and r.get("v_own") is not None]
        if js:
            diffs = sorted(r["v_told"] - r["v_own"] for r in js)
            print("  judged:", len(js), "told worse by >=50cp:", sum(x <= -50 for x in diffs),
                  "within 50:", sum(-50 < x < 50 for x in diffs), "told better by >=50:", sum(x >= 50 for x in diffs))


if __name__ == "__main__":
    main()
