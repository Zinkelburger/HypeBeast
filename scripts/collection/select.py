#!/usr/bin/env python3
"""Rank the games of the three v1.1.1 matches by how much there is to explain,
and pick ten, spread over the matches and over which team won.

    python3 scripts/collection/select.py [--pick 10]

Writes logs/collection/selection.json: every game with its signals, its
score, the near-copy group it belongs to, and whether it was picked (and if
not, why). Signals come from the logs only (results.jsonl, the engine
transcripts and the post-mortem rows), never from a judgement of the play:

  overrides        moves where coordination changed the move: hb_summary
                   override=1 (the move played differs from the board's own
                   search move), with the reason code
  sits_won         sit episodes of the team that went on to win (one episode:
                   a seat's sits within one turn on its board)
  fed_heavy        moves whose main line's score was at least half feed price:
                   |fed| >= 150 cp and |fed| >= |score - fed|, fed estimated by
                   the post-mortem's fed_in_scores (hb_prices summed over the
                   captures of the main line; within 2 cp of the engine's own
                   hb_fed wherever both exist)
  forecast_used    a world with "+T" (a T for the mover) had p >= 0.25, a T did
                   reach the mover's hand before its next move, and that next
                   move dropped a T
  swings           consecutive decisions of one seat whose main score moved by
                   1000 cp or more (mates clipped to 2000; bughouse scores move
                   a lot: the median swing of 300 cp or more is 574 cp)
  drop_mate        the game ended by checkmate and the mating move was a drop,
                   or two of the winner's last three moves on that board were

Each signal's count is turned into its percentile among the 124 games (ties
share the mean rank), so no signal saturates, and
score = 1.5*sits_won + 1.5*forecast_used + overrides + fed_heavy + swings + drop_mate
in percentiles (the two rarest, most two-board signals weigh more).
Two games are near copies when they share their first 40 half-moves (the
opening is 16): the two games of an opening pair in the v1.1.0 matches, and
v7 against v7b, which differ only in the partner-mate hold.
"""
from __future__ import annotations

import sys
from pathlib import Path

# This file shares its name with the standard library's `select`: keep its
# directory off the import path and load common.py by file name.
HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("hb_collection_common", HERE / "common.py")
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)

import argparse  # noqa: E402
import collections  # noqa: E402
import itertools  # noqa: E402

QUOTA = {"v7-selfplay-flags": 4, "v7b-vs-v110-sanity": 3, "v7-vs-v110-sanity": 3}
NEAR_COPY = 40


def clip(cp):
    return None if cp is None else max(-2000, min(2000, cp))


def game_signals(m: dict, g: int) -> dict:
    rec = m["records"][g]
    ds = m["decisions"][g]
    winner = rec["result"]["winner"]           # "white" / "black" / None
    win_team = None if winner is None else (0 if winner == "white" else 1)
    sig = collections.defaultdict(list)
    by_seat = collections.defaultdict(list)
    for d in ds:
        by_seat[d["seat"]].append(d)
    for seat, sd in by_seat.items():
        moved = [d for d in sd if d["event"]["kind"] == "move"]
        for d in moved:
            pm = d["pm"] or {}
            if pm.get("override"):
                sig["overrides"].append({"n": d["n"], "seat": seat, "reason": pm.get("reason"),
                                         "played": d["event"]["uci"], "main": pm.get("main")})
            fed, score = pm.get("_fed_estimate"), pm.get("score")
            if fed is not None and score is not None and abs(score) < c.MATE:
                if abs(fed) >= 150 and abs(fed) >= abs(score - fed):
                    sig["fed_heavy"].append({"n": d["n"], "seat": seat, "fed": fed, "score": score})
        for a, b in zip(moved, moved[1:]):
            pm = a["pm"] or {}
            want = set()
            for w in pm.get("worlds", []):
                if w["arrival"] != "none" and w["p"] >= 0.25:
                    want |= {k[1] for k in postmortem_keys(w["arrival"]) if k[0] == "+"}
            got = {f[1][1] for f in pm.get("future", []) if f[1][0] == "+" and f[0] <= 2}
            u = b["event"]["uci"]
            if "@" in u and u[0] in want and u[0] in got:
                p = max(w["p"] for w in pm["worlds"] if "+" + u[0] in w["arrival"])
                sig["forecast_used"].append({"n": b["n"], "forecast_n": a["n"], "seat": seat,
                                             "piece": u[0], "p": round(p, 3), "drop": u})
        scored = [d for d in sd if (d["pm"] or {}).get("score") is not None]
        for a, b in zip(scored, scored[1:]):
            delta = clip(b["pm"]["score"]) - clip(a["pm"]["score"])
            if abs(delta) >= 1000:
                sig["swings"].append({"n": a["n"], "next_n": b["n"], "seat": seat, "delta": delta})
        if win_team is not None and seat in c.TEAMS[win_team]:
            episode = None
            for d in sd:
                if d["event"]["kind"] == "sit":
                    key = (d["n"],)
                    if key != episode:
                        sig["sits_won"].append({"n": d["n"], "seat": seat,
                                                "reason": d["out"]["summary"].get("reason")})
                    episode = key
                else:
                    episode = None
    # mating finish
    drop_mate = False
    if rec["result"]["termination"] == "checkmate":
        moves = [e for e in rec["result"]["events"] if e["kind"] == "move"]
        last = moves[-1]
        if "@" in last["uci"]:
            drop_mate = True
        else:
            mine = [e for e in moves if e["seat"] == last["seat"]][-3:]
            drop_mate = sum("@" in e["uci"] for e in mine) >= 2
    out = {k: v for k, v in sig.items()}
    counts = {k: len(out.get(k, [])) for k in ("overrides", "sits_won", "fed_heavy", "forecast_used", "swings")}
    counts["drop_mate"] = int(drop_mate)
    return {"counts": counts, "details": out, "winner": win_team,
            "termination": rec["result"]["termination"], "plies": len(c.game_tokens(rec)),
            "pair": rec["pair"], "seats": {c.SEAT_OF_ARENA[k]: v for k, v in rec["seats"].items()},
            "contender_team": rec["contender_team"]}


def postmortem_keys(key: str):
    import re
    return re.findall(r"[+-][PNBRQ]", key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", type=int, default=10)
    args = ap.parse_args()
    games = []
    toks = {}
    for match in c.MATCHES:
        m = c.load_match(match)
        for g in sorted(m["records"]):
            s = game_signals(m, g)
            gid = f"{c.MATCHES[match]['short']}-g{g + 1:02d}"
            rec = m["records"][g]
            role_of_team = {rec["contender_team"]: "contender",
                            ("black" if rec["contender_team"] == "white" else "white"): "baseline"}
            s.update({"id": gid, "match": match, "game": g,
                      "winner_engine": None if s["winner"] is None else
                      c.MATCHES[match]["names"][role_of_team["white" if s["winner"] == 0 else "black"]]})
            games.append(s)
            toks[gid] = c.game_tokens(rec)
    # percentile scores
    weights = {"sits_won": 1.5, "forecast_used": 1.5, "overrides": 1, "fed_heavy": 1, "swings": 1, "drop_mate": 1}
    for k, w in weights.items():
        vals = sorted(x["counts"][k] for x in games)
        for x in games:
            v = x["counts"][k]
            lo = vals.index(v)
            hi = len(vals) - 1 - vals[::-1].index(v)
            x.setdefault("percentiles", {})[k] = round(((lo + hi) / 2) / (len(vals) - 1), 3)
    for x in games:
        x["score"] = round(sum(weights[k] * x["percentiles"][k] for k in weights), 3)
    # near-copy groups (union-find over shared prefixes)
    parent = {x["id"]: x["id"] for x in games}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b in itertools.combinations(toks, 2):
        ta, tb = toks[a], toks[b]
        k = 0
        while k < min(len(ta), len(tb)) and ta[k] == tb[k]:
            k += 1
        if k >= NEAR_COPY:
            parent[find(a)] = find(b)
    for x in games:
        x["group"] = find(x["id"])
    games.sort(key=lambda x: (-x["score"], x["id"]))
    for r, x in enumerate(games, 1):
        x["rank"] = r

    picked, used_groups = [], set()
    take = collections.Counter()
    wins = collections.Counter()
    sanity_wins = collections.Counter()
    for x in games:
        why = None
        if x["group"] in used_groups:
            why = "near copy of a picked game"
        elif take[x["match"]] >= QUOTA[x["match"]]:
            why = "match quota full"
        elif x["winner"] is None:
            why = "draw"
        elif wins[x["winner"]] >= (args.pick + 1) // 2 + 1:
            why = "too many wins for that team"
        elif x["match"] != "v7-selfplay-flags" and sanity_wins[x["winner_engine"].split(" (")[0]] >= 4:
            why = "too many sanity-match wins for that version"
        if why or len(picked) >= args.pick:
            x["picked"] = False
            x["not_picked_because"] = why or "ten picked"
            continue
        x["picked"] = True
        picked.append(x)
        used_groups.add(x["group"])
        take[x["match"]] += 1
        wins[x["winner"]] += 1
        if x["match"] != "v7-selfplay-flags":
            sanity_wins[x["winner_engine"].split(" (")[0]] += 1
    out = {"rule": __doc__.split("\n\n", 2)[2].strip(), "quota": QUOTA, "near_copy_plies": NEAR_COPY,
           "picked": [x["id"] for x in picked], "games": games}
    c.write_json(c.OUT / "selection.json", out)
    for x in picked:
        print(f"{x['rank']:3d} {x['id']:22s} score {x['score']:5.1f} winner team {x['winner']} "
              f"({x['winner_engine']}) {x['counts']}")


if __name__ == "__main__":
    main()
