#!/usr/bin/env python3
"""Question 4: does hearing the partner's line (hb-plan) change forecasts, surprises, switches, sits, collapses?

    nice -n 19 python3 sides.py [MATCH]

Every number is per engine (hb-plan, hb-l50) and, for hb-plan, per forecast group: "plan" (the told line was
added) against "own_*" (refused: own_hands, own_reply, own_none, own_no_lines). Intervals: 95%, 2000 resamples of
games; "diff" resamples the same games for both engines (they play the same games).

  Brier          arrival worlds, against "the whole package arrived by q<=4" (decisions with 6+ plies left)
  realised p     the p the forecast gave to what really reached either hand by q<=2 (an exact world, else 0)
  surprise       a piece in no world reached the opponent's hand by q<=2 (decisions with worlds, 2+ plies left)
  switch         decision != main search move and not a sit
  switch gain    in the coord world matching what really arrived before the next decision, value of the move
                 played minus the main move (mates clipped to +-2000): > 0 the switch was right by the engine's own
                 world search of the world that came
  sit            decision pass, by reason
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from common2 import MATE, boot_diff, boot_ratio, by_seat, clip, fm, load  # noqa: E402

MATCH = next((a for a in sys.argv[1:] if not a.startswith("--")), "plan-vs-l50")


def key_counter(key):
    c = collections.Counter()
    for s, t in re.findall(r"([+-])([PNBRQ])", key):
        c[s + t] += 1
    return c


def realised(r, qmax=2):
    got = collections.Counter(f[1] for f in r["future"] if f[0] <= qmax)
    return got


def coord_world(r, got):
    co = r.get("coord") or {}
    for w in co.get("worlds") or []:
        a = w["arrival"]
        if (a == "none" and not got) or (a != "none" and key_counter(a) == got):
            return w
    return None


def group(r):
    if r["engine"] != "hb-plan":
        return r["engine"]
    t = r.get("talk") or "none"
    return "hb-plan:plan" if t == "plan" else "hb-plan:own"


def metrics(rows):
    """-> dict metric -> group -> game -> (num, den)"""
    M = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0])))

    def add(name, r, num, den=1.0):
        for gname in {r["engine"], group(r)}:
            c = M[name][gname][r["game"]]
            c[0] += num
            c[1] += den
    for r in rows:
        add("decisions", r, 1, 1)
        if r["left"] >= 6:
            for w in r["worlds"]:
                if w["arrival"] != "none":
                    add("Brier", r, (w["p"] - (w["q_all"] is not None and w["q_all"] <= 4)) ** 2)
            if r["worlds"]:
                got = realised(r)
                p = 0.0
                for w in r["worlds"]:
                    a = w["arrival"]
                    if (a == "none" and not got) or (a != "none" and key_counter(a) == got):
                        p = w["p"]
                add("realised p", r, p)
                add("realised in no world", r, 1.0 if p == 0 else 0.0)
                add("worlds per decision", r, sum(1 for w in r["worlds"] if w["arrival"] != "none"))
                add("heaviest world p", r, max(w["p"] for w in r["worlds"]))
        if r["left"] >= 2 and r["worlds"]:
            named = set()
            for w in r["worlds"]:
                named |= {k for k in key_counter(w["arrival"]) if k[0] == "-"}
            got = {f[1] for f in r["future"] if f[0] <= 2 and f[1][0] == "-"}
            add("surprise", r, 1.0 if got - named else 0.0)
            add("surprise: a queen in no world", r, 1.0 if "-Q" in got - named else 0.0)
        if r["decision"] != "pass" and r["next_score"] is not None and abs(r["next_score"]) < MATE:
            gw = realised(r)
            w = coord_world(r, gw)
            if w and w["values"].get(r["decision"]) is not None and abs(w["values"][r["decision"]]) < MATE:
                err = w["values"][r["decision"]] - r["next_score"]
                add("world value of the move minus next score: nothing arrived" if not gw else
                    "world value of the move minus next score: pieces arrived", r, err)
                if any(k[0] == "-" for k in gw):
                    add("world value of the move minus next score: a piece to the opponent", r, err)
        sw = r["override"] and r["decision"] != "pass"
        add("switch", r, 1.0 if sw else 0.0)
        if sw:
            if r["score"] is not None and r["next_score"] is not None and abs(r["score"]) < MATE and abs(r["next_score"]) < MATE:
                add("switch: next score change", r, r["next_score"] - r["score"])
            w = coord_world(r, realised(r))
            if w:
                vm, vc = w["values"].get(r["main"]), w["values"].get(r["decision"])
                if vm is not None and vc is not None:
                    add("switch gain in the world that came", r, clip(vc) - clip(vm))
                    add("switch: played mated, main not", r, 1.0 if vc <= -MATE < vm else 0.0)
                    add("switch: main mated, played not", r, 1.0 if vm <= -MATE < vc else 0.0)
                    add("switch: gain <= -300", r, 1.0 if clip(vc) - clip(vm) <= -300 else 0.0)
                    add("switch: gain >= +300", r, 1.0 if clip(vc) - clip(vm) >= 300 else 0.0)
            add("switch: game won", r, r["won"])
            wn = coord_world(r, collections.Counter())
            if wn and wn["values"].get(r["main"]) is not None and wn["values"].get(r["decision"]) is not None:
                add("switch: cost if nothing arrives (main - played, none world)", r,
                    clip(wn["values"][r["main"]]) - clip(wn["values"][r["decision"]]))
        elif r["decision"] != "pass":
            if r["score"] is not None and r["next_score"] is not None and abs(r["score"]) < MATE and abs(r["next_score"]) < MATE:
                add("kept: next score change", r, r["next_score"] - r["score"])
        add("sit", r, 1.0 if r["decision"] == "pass" else 0.0)
        add("sit while not mated", r, 1.0 if r["decision"] == "pass" and r["reason"] != "hold_mated" else 0.0)
        if r["score"] is not None and r["next_score"] is not None:
            add("collapse (>-300 then mated)", r, 1.0 if r["score"] > -300 and r["next_score"] <= -MATE else 0.0)
            if abs(r["score"]) < MATE:
                add("drop >= 400 by next decision (or mated)", r,
                    1.0 if max(r["next_score"], -100000) - r["score"] <= -400 else 0.0)
        if r["decision"] != "pass" and r["score"] is not None and abs(r["score"]) < MATE:
            add("main depth (moves, non-mate)", r, r["depth"])
        if r.get("main_nodes"):
            add("main nodes (k)", r, r["main_nodes"] / 1000)
    return M


def main():
    data = load(MATCH)
    rows = data["rows"]
    games = {g["game"] for g in data["games"]}
    M = metrics(rows)
    groups = ["hb-plan", "hb-l50", "hb-plan:plan", "hb-plan:own"]
    print(f"{MATCH}: {len(games)} games, {len(rows)} decisions")
    # score
    wins = collections.Counter()
    for g in data["games"]:
        for team in ("white", "black"):
            wins[g["seats"]["A-" + team]] += 1.0 if g["winner"] == team else 0.5 if g["winner"] not in ("white", "black") else 0
    print("score:", dict(wins), "terminations:", dict(collections.Counter(g["termination"] for g in data["games"])))
    print()
    print("| metric | " + " | ".join(groups) + " | diff hb-plan - hb-l50 (95%) |")
    print("|---|" + "---|" * (len(groups) + 1))
    for name in M:
        cells = []
        for gname in groups:
            per = {g: tuple(v) for g, v in M[name][gname].items()}
            if not per or not sum(v[1] for v in per.values()):
                cells.append("-")
                continue
            e, lo, hi = boot_ratio(per)
            den = sum(v[1] for v in per.values())
            cells.append(f"{e:.3f} [{lo:.3f}, {hi:.3f}] (n {den:.0f})" if abs(e) < 10 else f"{e:.0f} [{lo:.0f}, {hi:.0f}] (n {den:.0f})")
        pa = {g: tuple(v) for g, v in M[name]["hb-plan"].items()}
        pb = {g: tuple(v) for g, v in M[name]["hb-l50"].items()}
        if pa and pb and sum(v[1] for v in pa.values()) and sum(v[1] for v in pb.values()):
            d, lo, hi = boot_diff(pa, pb, games)
            dd = f"{d:+.3f} [{lo:+.3f}, {hi:+.3f}]" if abs(d) < 10 else f"{d:+.0f} [{lo:+.0f}, {hi:+.0f}]"
        else:
            dd = "-"
        print(f"| {name} | " + " | ".join(cells) + f" | {dd} |")
    # talk breakdown
    print()
    print("hb-plan forecast groups:", dict(collections.Counter(r.get("talk") for r in rows if r["engine"] == "hb-plan")))
    # sits by reason
    print()
    print("| engine | sit reason | decisions | games | team won |")
    print("|---|---|---|---|---|")
    for e in ("hb-plan", "hb-l50"):
        c = collections.defaultdict(list)
        for r in rows:
            if r["engine"] == e and r["decision"] == "pass":
                c[r["reason"]].append(r)
        for k, v in sorted(c.items(), key=lambda kv: -len(kv[1])):
            gs = {r["game"]: r["won"] for r in v}
            print(f"| {e} | {k} | {len(v)} | {len(gs)} | {sum(gs.values()):.0f} of {len(gs)} |")
    # switch reasons
    print()
    print("| engine | switch reason | n | mean gain in the world that came | n scored | played mated & main not | team won |")
    print("|---|---|---|---|---|---|---|")
    for e in ("hb-plan", "hb-l50"):
        c = collections.defaultdict(list)
        for r in rows:
            if r["engine"] == e and r["override"] and r["decision"] != "pass":
                c[r["reason"]].append(r)
        for k, v in sorted(c.items(), key=lambda kv: -len(kv[1])):
            gains, worse = [], 0
            for r in v:
                w = coord_world(r, realised(r))
                if w:
                    vm, vc = w["values"].get(r["main"]), w["values"].get(r["decision"])
                    if vm is not None and vc is not None:
                        gains.append(clip(vc) - clip(vm))
                        worse += vc <= -MATE < vm
            print(f"| {e} | {k} | {len(v)} | {sum(gains) / len(gains):+.0f} | {len(gains)} | {worse} | {sum(r['won'] for r in v) / len(v):.3f} |"
                  if gains else f"| {e} | {k} | {len(v)} | - | 0 | 0 | {sum(r['won'] for r in v) / len(v):.3f} |")


if __name__ == "__main__":
    main()


def world_calibration():
    """arrival worlds by stated p: share whose package arrived by q<=2 / q<=4 (6+ plies left), per group; and for
    hb-plan's plan decisions, the world equal to the told line's whole capture package ("told world")"""
    data = load(MATCH)
    rows = [r for r in data["rows"] if r["left"] >= 6]
    bins = ((0, .1), (.1, .2), (.2, .35), (.35, .5), (.5, .7), (.7, 1.01))
    print("\n| group | p bin | worlds | mean p | arrived by q<=2 | by q<=4 |")
    print("|---|---|---|---|---|---|")
    for gname in ("hb-l50", "hb-plan:plan", "hb-plan:own", "told world (hb-plan:plan)", "told world, first told capture at ply 0-1",
                  "told world, first told capture at ply 2+", "other worlds (hb-plan:plan)"):
        for lo, hi in bins:
            ws = []
            for r in rows:
                gr = group(r)
                if gname.startswith("told") or gname.startswith("other"):
                    if gr != "hb-plan:plan" or not r.get("told"):
                        continue
                    tk = collections.Counter(re.sub(r"^\d+", "", c) for c in r["told"]["caps"])
                    first = min((int(re.match(r"\d+", c).group()) for c in r["told"]["caps"]), default=99)
                    if "ply 0-1" in gname and first > 1 or "ply 2+" in gname and first <= 1:
                        continue
                    sel = [w for w in r["worlds"] if w["arrival"] != "none" and (key_counter(w["arrival"]) == tk) == gname.startswith("told")]
                elif gr != gname:
                    continue
                else:
                    sel = [w for w in r["worlds"] if w["arrival"] != "none"]
                ws += [w for w in sel if lo <= w["p"] < hi]
            if ws:
                print(f"| {gname} | {lo:.2f}-{min(hi, 1):.2f} | {len(ws)} | {sum(w['p'] for w in ws) / len(ws):.2f} | "
                      f"{sum(1 for w in ws if w['q_all'] is not None and w['q_all'] <= 2) / len(ws):.3f} | "
                      f"{sum(1 for w in ws if w['q_all'] is not None and w['q_all'] <= 4) / len(ws):.3f} |")


if __name__ == "__main__" and "--worlds" in sys.argv:
    world_calibration()
