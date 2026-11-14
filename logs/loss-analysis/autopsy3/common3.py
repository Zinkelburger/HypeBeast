#!/usr/bin/env python3
"""Shared loading for AUTOPSY3 (what loses a board first). Logs only: no engine is run.

    nice -n 19 python3 common3.py MATCH [MATCH ...]     rebuild cache_<MATCH>.pkl

load(match) -> {"games": [...], "rows": [...]} where
  games: postmortem.load_games plus events, clocks_end, sits, seat_stats, sit intervals per seat
  rows:  postmortem.collect rows (one per decision, every field of postmortem.jsonl) plus
         mainpv    the exact line at the main depth
         sumd      every key=value of hb_summary
         dscores   [(depth, score)] of the main search's exact multipv-1 lines, in order (mate = +-(100000 - plies))
         coord     {"worlds": [{arrival, p, depth, scored, values}], "cands": [{move, source, L, S, E, tier,
                    probe_fatal, exposed, mating, delivery}], "common_depth", "reason"} or None
         fc_prices the forecast's measured price of one arriving piece {"-N": 384, ...} or {}
         team_mate the forecast's forced mate on the partner board (plies; >0 our partner mates)
         clocks    [aW, aB, bW, bB] ms sent before that go
         prices    hb_prices of that go ({base, ours, theirs}) or None
         fen_own, fen_other   crazyhouse FENs (with pockets) of the seat's board and the other board
         feat      autopsy2's features of the position (king, hands, drop checks, ...)
"""
import collections
import glob
import json
import os
import pickle
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "autopsy2"))
import postmortem as pm  # noqa: E402
import common2 as c2  # noqa: E402

MATE = 90000
PARTNER = c2.PARTNER
L50_MATCHES = ["plan-vs-l50", "plan-vs-l50-b", "plan-c", "kd60-vs-l50", "matefree", "matekeep"]


def score_of(fields):
    """fields of an 'info depth' line -> cp, or +-(100000 - plies) for a mate"""
    if "score" not in fields:
        return None
    i = fields.index("score")
    kind, v = fields[i + 1], int(fields[i + 2])
    if kind == "cp":
        return v
    plies = 2 * v - 1 if v > 0 else -2 * v
    return 100000 - plies if v > 0 else -(100000 - plies)


def parse_logs3(d):
    out = collections.defaultdict(list)
    for path in sorted(glob.glob(f"{d}/engine_logs/w*-*.log")):
        role = "contender" if "-contender-" in path else "baseline"
        seat = moves = clocks = None
        block = None
        for line in open(path, errors="replace"):
            if line.startswith(">>> setoption name Seat value "):
                seat = line.split()[-1]
            elif line.startswith(">>> setoption name Clocks value "):
                try:
                    clocks = [int(x) for x in line.split()[-1].split(",")]
                except ValueError:
                    clocks = None
            elif line.startswith(">>> position startpos moves "):
                moves = line.split()[4:]
            elif line.startswith(">>> go"):
                block = {"ds": [], "coord_seen": False}
            elif block is None:
                continue
            elif line.startswith("info depth ") and " pv " in line and not block["coord_seen"]:
                f = line.split(" pv ", 1)[0].split()
                if "lowerbound" in f or "upperbound" in f:
                    continue
                if "multipv" in f and f[f.index("multipv") + 1] != "1":
                    continue
                block["ds"].append((int(f[2]), score_of(f)))
            elif line.startswith("info string hb_forecast "):
                try:
                    fc = json.loads(line.split("hb_forecast ", 1)[1])
                    block["fc_prices"] = fc.get("prices") or {}
                    block["team_mate"] = fc.get("team_mate", 0)
                except ValueError:
                    pass
            elif line.startswith("info string hb_coord "):
                block["coord_seen"] = True
                try:
                    co = json.loads(line.split("hb_coord ", 1)[1])
                    block["coord"] = {
                        "reason": co.get("reason"), "common_depth": co.get("common_depth"),
                        "partner_base": co.get("partner_base"),
                        "worlds": [{"arrival": w.get("arrival"), "p": w.get("p"), "depth": w.get("depth"),
                                    "scored": w.get("scored"), "values": w.get("values", {})}
                                   for w in (co.get("worlds") or [])],
                        "cands": [{k: c.get(k) for k in ("move", "source", "L", "S", "E", "tier", "probe_fatal",
                                                         "exposed", "mating", "delivery", "blocking")}
                                  for c in co.get("candidates", [])]}
                except ValueError:
                    pass
            elif line.startswith("info string hb_summary "):
                block["sumd"] = dict(p.split("=", 1) for p in line.split()[3:] if "=" in p)
            elif line.startswith("bestmove"):
                b, block = block, None
                if not b.get("sumd") or moves is None or seat is None:
                    continue
                out[(role, seat, tuple(moves))].append({
                    "clocks": clocks, "sumd": b["sumd"], "dscores": b["ds"], "coord": b.get("coord"),
                    "fc_prices": b.get("fc_prices", {}), "team_mate": b.get("team_mate", 0)})
    return out


def sit_intervals(events):
    """seat ('Awhite' style) -> [(t_start, t_end)] while that seat sat (until its next move, wake or the end)"""
    out = collections.defaultdict(list)
    open_ = {}
    for e in events:
        s = (e.get("seat") or "").replace("-", "")
        if e["kind"] == "sit":
            open_.setdefault(s, e["t"])
        elif e["kind"] in ("move", "wake") and s in open_:
            out[s].append((open_.pop(s), e["t"]))
        elif e["kind"] == "end":
            for s2, t0 in open_.items():
                out[s2].append((t0, e["t"]))
            open_ = {}
    return dict(out)


def build(match):
    d = os.path.join(REPO, "logs", match)
    tag, games, rows, unmatched = pm.collect(d)
    raw = {}
    for l in open(f"{d}/results.jsonl"):
        r = json.loads(l)
        raw[r["game"]] = r
    for g in games:
        r = raw[g["game"]]
        g["events"] = [{k: e.get(k) for k in ("t", "kind", "seat", "board", "uci", "clocks", "reason")}
                       for e in r["result"]["events"]]
        g["clocks_end"] = r["result"]["clocks_ms"]
        g["sits"] = r["result"]["sits"]
        g["seat_stats"] = {k: {kk: v for kk, v in s.items() if kk != "latency_ms"} for k, s in r["seat_stats"].items()}
        g["contender_team"] = r.get("contender_team")
        g["sit_iv"] = sit_intervals(r["result"]["events"])
        g["match"] = match
    extras = parse_logs3(d)
    gby = {g["game"]: g for g in games}
    snaps = {}
    used = collections.Counter()
    missing = 0
    for r in rows:
        r["mainpv"] = r.pop("_mainpv", None)
        r["prices"] = r.pop("_prices", None)
        r.pop("_next", None)
        g = gby[r["game"]]
        role = "contender" if g["names"]["contender"] == r["engine"] else "baseline"
        key = (role, r["seat"], tuple(g["toks"][:r["n"]]))
        i = used[key]
        used[key] += 1
        ex = extras.get(key, [])
        if i < len(ex):
            r.update(ex[i])
        else:
            missing += 1
            r.update({"clocks": None, "sumd": {}, "dscores": [], "coord": None, "fc_prices": {}, "team_mate": 0})
        if r["game"] not in snaps:
            snaps[r["game"]] = c2.replay_boards(g["toks"])
        bA, bB = snaps[r["game"]][r["n"]]
        board = bA if r["seat"][0] == "A" else bB
        other = bB if r["seat"][0] == "A" else bA
        r["fen_own"] = board.fen()
        r["fen_other"] = other.fen()
        r["feat"] = c2.features(board, other, c2.seat_white(r["seat"]), c2.seat_white(PARTNER[r["seat"]]))
    data = {"games": games, "rows": rows, "unmatched": unmatched, "missing_extras": missing}
    with open(os.path.join(HERE, f"cache_{match}.pkl"), "wb") as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(match, len(games), "games", len(rows), "rows; unmatched", unmatched, "extras missing", missing, file=sys.stderr)
    return data


def load(match):
    p = os.path.join(HERE, f"cache_{match}.pkl")
    if not os.path.exists(p):
        return build(match)
    with open(p, "rb") as f:
        return pickle.load(f)


def by_seat(rows):
    out = collections.defaultdict(list)
    for r in rows:
        out[(r["game"], r["seat"])].append(r)
    for k in out:
        out[k].sort(key=lambda r: (r["n"], r["t"]))
    return out


def clip(v, cap=3000):
    return max(-cap, min(cap, v))


if __name__ == "__main__":
    for m in (sys.argv[1:] or L50_MATCHES):
        build(m)
