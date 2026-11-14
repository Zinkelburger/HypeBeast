#!/usr/bin/env python3
"""Post-mortem of an arena match: every engine decision beside what happened next.

    scripts/postmortem.py MATCH_DIR [MATCH_DIR ...]

For each match directory (results.jsonl and engine_logs/ from run_match.sh) it writes

  MATCH_DIR/postmortem.jsonl   one row per decision: the score, the chosen and the
                               main move, every forecast world with its stated
                               probability and each candidate's value in it, what
                               really arrived and when, the score at the seat's
                               next decision, and who won
  MATCH_DIR/postmortem.md      the report (also printed)

The report says, per engine: whether stated winning chances and world
probabilities came true, when forecast pieces arrived, how often an arrival was
in no world, what switching away from the main move was followed by, who saw
itself mated first, and the decisions followed by the largest drops.
"""
import collections
import glob
import json
import math
import re
import sys

import chess
import chess.variant

NAMES = {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q"}
MATE = 90000
WIN_SCALE = 1000.0   # HBWinScale's default: cp per logistic unit


def replay(tokens):
    """-> [(token index, board '1'/'2', mover is white, captured type letter)]"""
    b = {"1": chess.variant.CrazyhouseBoard(), "2": chess.variant.CrazyhouseBoard()}
    caps = []
    for i, t in enumerate(tokens):
        board = b[t[0]]
        mover = board.turn
        before = {p: board.pockets[mover].count(p) for p in NAMES}
        board.push(chess.Move.from_uci(t[1:]))
        for p in NAMES:
            if board.pockets[mover].count(p) > before[p]:
                board.pockets[mover].remove(p)
                b["2" if t[0] == "1" else "1"].pockets[not mover].add(p)
                caps.append((i, t[0], mover, NAMES[p]))
    return caps


def key_counter(key):
    c = collections.Counter()
    for s, t in re.findall(r"([+-])([PNBRQ])", key):
        c[s + t] += 1
    return c


def win_chance(cp):
    if cp >= MATE:
        return 1.0
    if cp <= -MATE:
        return 0.0
    return 1.0 / (1.0 + math.exp(-cp / WIN_SCALE))


def load_games(d):
    games = []
    for l in open(f"{d}/results.jsonl"):
        r = json.loads(l)
        toks = list(r["opening"]["moves"])
        times = [0] * len(toks)
        for e in r["result"]["events"]:
            if e["kind"] == "move":
                toks.append(("1" if e["board"] == "A" else "2") + e["uci"])
                times.append(e["t"])
        games.append({"game": r["game"], "pair": r["pair"], "toks": toks, "times": times, "caps": replay(toks),
                      "seats": r["seats"], "names": {"contender": r["contender"], "baseline": r["baseline"]},
                      "winner": r["result"]["winner"], "termination": r["result"]["termination"]})
    return games


def collect(d):
    tag = d.rstrip("/").split("/")[-1]
    games = load_games(d)
    index = collections.defaultdict(list)
    for g in games:
        index[tuple(g["toks"][:12])].append(g)
    rows, unmatched = [], 0
    for path in sorted(glob.glob(f"{d}/engine_logs/w*-*.log")):
        role = "contender" if "-contender-" in path else "baseline"
        seat = moves = None
        block = None
        last = {}          # (game, seat) -> previous row, to fill next_score
        for line in open(path, errors="replace"):
            if line.startswith(">>> setoption name Seat value "):
                seat = line.split()[-1]
            elif line.startswith(">>> position startpos moves "):
                moves = line.split()[4:]
            elif line.startswith(">>> go"):
                block = {}
            elif block is None:
                continue
            elif line.startswith("info string hb_forecast "):
                block["fc"] = json.loads(line.split("hb_forecast ", 1)[1])
            elif line.startswith("info depth ") and " pv " in line and "coord" not in block:
                block["pv"] = line.split(" pv ", 1)[1].split()[:6]
            elif line.startswith("info string hb_coord "):
                block["coord"] = json.loads(line.split("hb_coord ", 1)[1])
            elif line.startswith("info string hb_summary "):
                block["sum"] = dict(p.split("=", 1) for p in line.split()[3:] if "=" in p)
            elif line.startswith("bestmove"):
                b, block = block, None
                s = b.get("sum")
                if not s or moves is None or seat is None:
                    continue
                seat_key = seat[0] + "-" + seat[1:]
                g = next((g for g in index.get(tuple(moves[:12]), [])
                          if g["toks"][:len(moves)] == moves and g["seats"][seat_key] == g["names"][role]), None)
                if g is None:
                    unmatched += 1
                    continue
                n = len(moves)
                ours = "1" if seat[0] == "A" else "2"
                white = seat.endswith("white")
                team = "white" if seat in ("Awhite", "Bblack") else "black"
                # what reached either hand on our board afterwards, and before which ply q of ours
                q, ci, future = 0, 0, []
                caps = [c for c in g["caps"] if c[0] >= n and c[1] != ours]
                for i in range(n, len(g["toks"])):
                    if g["toks"][i][0] == ours:
                        q += 1
                        continue
                    while ci < len(caps) and caps[ci][0] == i:
                        future.append((q, ("+" if caps[ci][2] != white else "-") + caps[ci][3], i))
                        ci += 1
                fc, co = b.get("fc"), b.get("coord") or {}
                cands = co.get("candidates", [])
                decision = s.get("decision", "")
                main = cands[0]["move"] if cands else decision
                chosen = next((c for c in cands if c["move"] == decision), None)
                worlds = []
                fworlds = {w["arrival"]: w for w in (co.get("worlds") or [])}
                for w in (fc or {}).get("worlds", []):
                    cw = fworlds.get(w["arrival"], {})
                    want = key_counter(w["arrival"])
                    got, q_all = collections.Counter(), None
                    for fq, k, _ in future:
                        got[k] += 1
                        if want and all(got[x] >= m for x, m in want.items()):
                            q_all = fq
                            break
                    vals = cw.get("values", {})
                    worlds.append({"arrival": w["arrival"], "p": w["p"], "arrives": cw.get("arrives", ""),
                                   "depth": cw.get("depth"), "v_main": vals.get(main), "v_chosen": vals.get(decision),
                                   "v_best": max(vals.values()) if vals else None, "q_all": q_all})
                row = {"match": tag, "game": g["game"], "pair": g["pair"], "engine": g["names"][role], "seat": seat,
                       "team": team, "n": n, "t": g["times"][n - 1] if n else 0,
                       "left": sum(1 for t in g["toks"][n:] if t[0] == ours),
                       "won": 1.0 if g["winner"] == team else 0.0 if g["winner"] in ("white", "black") else 0.5,
                       "termination": g["termination"],
                       "score": int(s["main_score_cp"]) if s.get("main_score_cp", "").lstrip("-").isdigit() else None,
                       "depth": int(s.get("main_depth", 0) or 0), "decision": decision, "main": main,
                       "override": s.get("override") == "1", "reason": s.get("reason", ""),
                       "E_main": cands[0].get("E") if cands else None, "E_chosen": chosen.get("E") if chosen else None,
                       "mover": (fc or {}).get("mover"), "worlds": worlds,
                       "lines": [{"w": l["weight"], "caps": l.get("captures", [])} for l in (fc or {}).get("lines", [])],
                       "future": [f for f in future if f[0] <= 8], "pv": b.get("pv", []), "next_score": None}
                prev = last.get((g["game"], seat))
                if prev is not None and row["score"] is not None:
                    prev["next_score"] = row["score"]
                last[(g["game"], seat)] = row
                rows.append(row)
    return tag, games, rows, unmatched


# ------------------------------------------------------------------- report

def table(out, head, lines):
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "---|" * len(head))
    for l in lines:
        out.append("| " + " | ".join(str(x) for x in l) + " |")
    out.append("")


def pct(k, n):
    return f"{100 * k / n:.1f}%" if n else "-"


def report(tag, games, rows, unmatched):
    out = [f"# Post-mortem: {tag}", ""]
    engines = sorted({r["engine"] for r in rows})
    by = {e: [r for r in rows if r["engine"] == e] for e in engines}
    wins = collections.Counter()
    for g in games:
        for team in ("white", "black"):
            name = g["seats"]["A-white" if team == "white" else "A-black"]
            wins[name] += 1.0 if g["winner"] == team else 0.0 if g["winner"] in ("white", "black") else 0.5
    out.append(f"{len(games)} games, {len(rows)} decisions"
               + (f", {unmatched} decisions not matched to a game" if unmatched else "") + ". Score: "
               + ", ".join(f"{e} {wins[e]:g}" for e in engines) + ".")
    out.append("")

    # ---- stated winning chances
    out.append("## Did the stated winning chances come true?")
    out.append("")
    out.append(f"From the main search's score (logistic, {WIN_SCALE:g} cp per unit; a mate is 0% or 100%). "
               "Decisions of one game are not independent, so read the columns as a shape, not to the digit.")
    out.append("")
    bins = ((0, .1), (.1, .25), (.25, .4), (.4, .6), (.6, .75), (.75, .9), (.9, 1.01))
    lines = []
    for lo, hi in bins:
        l = [f"{int(lo * 100)}-{min(int(hi * 100), 100)}%"]
        for e in engines:
            sel = [r for r in by[e] if r["score"] is not None and lo <= win_chance(r["score"]) < hi]
            l += [len(sel), pct(sum(win_chance(r["score"]) for r in sel), len(sel)), pct(sum(r["won"] for r in sel), len(sel))]
        lines.append(l)
    table(out, ["stated"] + [f"{e}: {c}" for e in engines for c in ("n", "mean stated", "won")], lines)

    # ---- world probabilities
    out.append("## Did the forecast worlds come true?")
    out.append("")
    out.append("An arrival world counts as true when its whole package had reached the hands before ply q of our "
               "board (q=1: the opponent's reply, q=2: our next move). Only decisions with 6 or more plies of our "
               "board left.")
    out.append("")
    wb = ((0, .1), (.1, .2), (.2, .35), (.35, .6), (.6, 1.01))
    for e in engines:
        sel = [r for r in by[e] if r["left"] >= 6]
        lines, brier, nb = [], 0.0, 0
        for lo, hi in wb:
            ws = [w for r in sel for w in r["worlds"] if w["arrival"] != "none" and lo <= w["p"] < hi]
            n = len(ws)
            lines.append([f"{lo:.2f}-{min(hi, 1):.2f}", n, f"{sum(w['p'] for w in ws) / n:.2f}" if n else "-"]
                         + [pct(sum(w["q_all"] is not None and w["q_all"] <= Q for w in ws), n) for Q in (1, 2, 4, 6)])
        for r in sel:
            for w in r["worlds"]:
                if w["arrival"] != "none":
                    brier += (w["p"] - (w["q_all"] is not None and w["q_all"] <= 4)) ** 2
                    nb += 1
        out.append(f"**{e}** (Brier score against \"arrived by q<=4\": {brier / nb:.3f} over {nb} worlds)" if nb else f"**{e}**: no worlds")
        out.append("")
        if nb:
            table(out, ["stated p", "worlds", "mean p", "by q<=1", "by q<=2", "by q<=4", "by q<=6"], lines)
        nl = []
        for lo, hi in ((0, .3), (.3, .5), (.5, .7), (.7, .9), (.9, 1.01)):
            ds = [r for r in sel if r["worlds"] and lo <= r["worlds"][0]["p"] < hi]
            nl.append([f"{lo:.1f}-{min(hi, 1):.1f}", len(ds)]
                      + [pct(sum(not any(f[0] <= Q for f in r["future"]) for r in ds), len(ds)) for Q in (1, 2, 4)])
        if nb:
            table(out, ["stated \"nothing arrives\"", "decisions", "nothing by q<=1", "by q<=2", "by q<=4"], nl)

    # ---- timing
    out.append("## When did a forecast piece arrive?")
    out.append("")
    out.append("A piece (side and type) by the earliest ply k at which any forecast line names it, all engines, "
               "decisions with 6 or more plies left: share in that hand before ply q of our board.")
    out.append("")
    lines = []
    for k in range(8):
        n, hits = 0, [0] * 6
        for r in rows:
            if r["left"] < 6:
                continue
            first = {}
            for l in r["lines"]:
                for c in l["caps"]:
                    m = re.match(r"(\d+)(.+)", c)
                    kk, key = int(m.group(1)), m.group(2)
                    first[key] = min(first.get(key, 99), kk)
            for key, kk in first.items():
                if kk != k:
                    continue
                n += 1
                fq = next((f[0] for f in r["future"] if f[1] == key), None)
                for i in range(6):
                    hits[i] += fq is not None and fq <= i + 1
        if n:
            lines.append([k, n] + [pct(h, n) for h in hits])
    table(out, ["named at ply k", "pieces"] + [f"q<={q}" for q in range(1, 7)], lines)

    # ---- surprises
    out.append("## Arrivals nobody forecast")
    out.append("")
    out.append("What reached the OPPONENT's hand before our next move (q<=2), and the main score at the seat's next "
               "decision minus the score now (mates left out).")
    out.append("")
    lines = []
    for e in engines:
        groups = collections.defaultdict(list)
        for r in by[e]:
            if r["left"] < 2 or not r["worlds"]:
                continue
            named = set()
            for w in r["worlds"]:
                named |= {k for k in key_counter(w["arrival"]) if k[0] == "-"}
            got = {f[1] for f in r["future"] if f[0] <= 2 and f[1][0] == "-"}
            kind = "nothing arrived" if not got else "all of it was in a world" if got <= named else "a piece in no world"
            groups[kind].append(r)
        tot = sum(len(v) for v in groups.values())
        for kind in ("nothing arrived", "all of it was in a world", "a piece in no world"):
            sel = groups[kind]
            sw = [r["next_score"] - r["score"] for r in sel
                  if r["next_score"] is not None and r["score"] is not None and abs(r["score"]) < MATE and abs(r["next_score"]) < MATE]
            mated = sum(1 for r in sel if r["next_score"] is not None and r["score"] is not None
                        and r["score"] > -MATE and r["next_score"] <= -MATE)
            lines.append([e, kind, len(sel), pct(len(sel), tot), f"{sum(sw) / len(sw):+.0f}" if sw else "-", mated])
    table(out, ["engine", "to the opponent by q<=2", "decisions", "share", "mean change in score (cp)", "then saw itself mated"], lines)

    # ---- switches
    out.append("## Switching away from the main search's move")
    out.append("")
    lines = []
    for e in engines:
        for name, sel in (("kept", [r for r in by[e] if not r["override"]]), ("switched", [r for r in by[e] if r["override"]])):
            sw = [r["next_score"] - r["score"] for r in sel
                  if r["next_score"] is not None and r["score"] is not None and abs(r["score"]) < MATE and abs(r["next_score"]) < MATE]
            lines.append([e, name, len(sel), pct(len(sel), len(by[e])), f"{sum(sw) / len(sw):+.0f}" if sw else "-",
                          pct(sum(r["won"] for r in sel), len(sel))])
    table(out, ["engine", "decision", "n", "share", "mean change in score by the next decision (cp)", "games won"], lines)
    reasons = collections.Counter((r["engine"], r["reason"]) for r in rows if r["override"])
    if reasons:
        table(out, ["engine", "reason for the switch", "n"], [[e, why, n] for (e, why), n in reasons.most_common(12)])

    # ---- first to see itself mated
    out.append("## First to see itself mated")
    out.append("")
    first = collections.Counter()
    lost_after = collections.Counter()
    for g in games:
        seen = [r for r in rows if r["game"] == g["game"] and r["score"] is not None and r["score"] <= -MATE]
        if seen:
            r = min(seen, key=lambda r: r["n"])
            first[r["engine"]] += 1
            lost_after[r["engine"]] += r["won"] == 0.0
    table(out, ["engine", "games in which it was first", "of those lost"], [[e, first[e], lost_after[e]] for e in engines])

    # ---- sudden collapses, and what the partner knew
    out.append("## Sudden collapses")
    out.append("")
    out.append("Decisions at -300 cp or better whose next decision was a forced mate against the seat. \"Fatal piece\": "
               "what reached the opponent's hand before our next move. For the partner: its last decision before that "
               "capture, and whether the capture was the reply its own main line expected.")
    out.append("")
    partner_of = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
    by_seat = collections.defaultdict(list)
    for r in rows:
        by_seat[(r["game"], r["seat"])].append(r)
    toks_of = {g["game"]: g["toks"] for g in games}
    caps_of = {g["game"]: g["caps"] for g in games}
    lines, plines = [], []
    for e in engines:
        sel = [r for r in by[e] if r["score"] is not None and r["next_score"] is not None
               and r["score"] > -300 and r["next_score"] <= -MATE]
        cause, types, partner = collections.Counter(), collections.Counter(), collections.Counter()
        for r in sel:
            got = [f for f in r["future"] if f[0] <= 2 and f[1][0] == "-"]
            if not got:
                cause["nothing reached the opponent"] += 1
                continue
            for k in {f[1] for f in got}:
                types[k] += 1
            ws = [w for w in r["worlds"] if any(f[1] in key_counter(w["arrival"]) for f in got)]
            if not ws:
                cause["the piece was in no world"] += 1
            else:
                w = max(ws, key=lambda w: w["p"])
                if w["v_chosen"] is None:
                    cause["in a world, but the move was not scored there"] += 1
                elif w["v_chosen"] > -MATE:
                    cause["in a world, where the move played was not mated"] += 1
                elif w["v_best"] is not None and w["v_best"] > -MATE:
                    cause["in a world, where another candidate was not mated"] += 1
                else:
                    cause["in a world, where every candidate was mated"] += 1
            # the partner's side of it, for the most valuable piece that came
            f = max(got, key=lambda f: "PNBRQ".index(f[1][1]))
            idx, toks = f[2], toks_of[r["game"]]
            prs = [x for x in by_seat[(r["game"], partner_of[r["seat"]])] if x["n"] <= idx]
            if not prs:
                partner["no partner decision before it"] += 1
                continue
            pr = prs[-1]
            board = toks[idx][0]
            # did our team take a piece on that board just before or just after?
            near = [c for c in caps_of[r["game"]] if c[1] == board and c[0] != idx and abs(c[0] - idx) <= 3
                    and c[2] != caps_of[r["game"]][[c2[0] for c2 in caps_of[r["game"]]].index(idx)][2]
                    and sum(1 for t in toks[min(c[0], idx) + 1:max(c[0], idx)] if t[0] == board) == 0]
            trade = ("a trade for " + "/".join(sorted({c[3] for c in near}))) if near else "nothing taken back"
            if pr["decision"] in ("pass", ""):
                know = "the partner was sitting"
            elif len(pr["pv"]) >= 2 and pr["pv"][0] == pr["decision"] and pr["pv"][1] == toks[idx][1:]:
                know = "the partner's own line had that capture"
            elif pr["n"] < len(toks) and toks[pr["n"]][0] == board and idx > pr["n"] + 1 and any(t[0] == board for t in toks[pr["n"] + 1:idx]):
                know = "the capture came later than the reply to that decision"
            else:
                know = "the partner's line expected another reply"
            state = "ahead" if (pr["score"] or 0) > 300 else "behind" if (pr["score"] or 0) < -300 else "level"
            partner[(know, trade, state)] += 1
        for k, v in cause.most_common():
            lines.append([e, len(sel), k, v])
        lines.append([e, len(sel), "fatal pieces: " + ", ".join(f"{k} {v}" for k, v in types.most_common()), ""])
        knows = collections.Counter()
        for k, v in partner.items():
            knows[k[0] if isinstance(k, tuple) else k] += v
        for know, v in knows.most_common():
            sub = {st: sum(n for k, n in partner.items() if isinstance(k, tuple) and k[0] == know and k[2] == st)
                   for st in ("ahead", "level", "behind")}
            traded = sum(n for k, n in partner.items() if isinstance(k, tuple) and k[0] == know and k[1] != "nothing taken back")
            plines.append([e, know, v, sub["ahead"], sub["level"], sub["behind"], traded])
    table(out, ["engine", "collapses", "what the seat knew", "n"], lines)
    table(out, ["engine", "the partner's last decision before the capture", "n", "partner ahead (>300)", "level", "behind (<-300)",
                "our team took a piece there too"], plines)

    # ---- largest drops
    out.append("## The 15 decisions followed by the largest drop")
    out.append("")
    out.append("Score now and at the seat's next decision (mate = -100000). \"to them\" is what reached the opponent's "
               "hand before our next move, with the largest stated probability of a world holding it (0: in none).")
    out.append("")
    drops = [r for r in rows if r["score"] is not None and r["next_score"] is not None and r["score"] > -MATE]
    drops.sort(key=lambda r: max(r["next_score"], -100000) - r["score"])
    lines = []
    for r in drops[:15]:
        got = []
        for q, k, _ in r["future"]:
            if q <= 2 and k[0] == "-":
                p = max([w["p"] for w in r["worlds"] if k in key_counter(w["arrival"])] or [0])
                got.append(f"{k} (p {p:.2f})")
        lines.append([r["engine"], r["game"], r["seat"], r["n"], r["score"], max(r["next_score"], -100000),
                      r["decision"] + (" (main " + r["main"] + ")" if r["override"] else ""),
                      ", ".join(got) or "nothing", "won" if r["won"] == 1 else "lost" if r["won"] == 0 else "drew"])
    table(out, ["engine", "game", "seat", "moves played", "score", "next", "played", "to them", "game"], lines)
    return "\n".join(out)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for d in sys.argv[1:]:
        tag, games, rows, unmatched = collect(d)
        with open(f"{d.rstrip('/')}/postmortem.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        text = report(tag, games, rows, unmatched)
        open(f"{d.rstrip('/')}/postmortem.md", "w").write(text + "\n")
        print(text)
        print()


if __name__ == "__main__":
    main()
