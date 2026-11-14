#!/usr/bin/env python3
"""Classify every lost game of the candidate by its first cause, from timeline.json.

Events, by token index n (both boards counted):
  S_bad  the mated seat's score is below -300 from here to the end (or the mate itself if it never was)
  P_bad  the same for its partner (None if the partner was not lost at the end)
  W      the first decision where the losing team reported a forced mate FOR itself (score >= 90000)
  F      the first "missed supply": a world of one '+T' had the seat mating, nothing arriving did not, the partner
         had a legal capture of a T at its next decision before the seat's next, and did not take one
The first cause is the earliest of these; a flag is its own class. Ties: S_bad, then P_bad, W, F.
"""
import collections
import json
import os
import sys

from common import HERE, MATE

ORDER = "PNBRQ"


def fatal_piece(arr):
    """the '-' arrival that matters most: lowest v_chosen in its world, then most valuable"""
    neg = [c for c in arr if c["k"][0] == "-"]
    if not neg:
        return None

    def key(c):
        v = c.get("v_chosen")
        return (v if v is not None else 10 ** 6, -ORDER.index(c["k"][1]))
    return min(neg, key=key)


def s_kind(s):
    """kind of the mated seat's own fall"""
    arr = s.get("arrivals_into_bad", [])
    c = fatal_piece(arr)
    sudden = s.get("sudden")
    drop = (s.get("pre_bad_score") or 0) - max(s.get("bad_score") or 0, -100000)
    if sudden:
        if c is None:
            return "c2", c, "sudden mate, nothing reached the opponent's hand"
        if c.get("world_p", 0) == 0 and c.get("world") is None:
            return "b", c, "sudden mate after an arrival in no world"
        if c.get("v_chosen") is None:
            return "a3", c, "sudden mate after a forecast arrival, move not scored in that world"
        if c["v_chosen"] <= -MATE:
            return "a", c, "sudden mate after a forecast arrival the seat knew was fatal"
        return "a2", c, "sudden mate after a forecast arrival the world search scored as survivable"
    if c is not None and drop >= 400:
        if c.get("world") is None:
            return "b2", c, "decisive drop (>=400 cp, no mate yet) after an arrival in no world"
        return "a4", c, "decisive drop (>=400 cp, no mate yet) after a forecast arrival"
    return "c", c, "slow loss on its own board, no decisive arrival"


def main():
    R = json.load(open(os.path.join(HERE, "timeline.json")))
    out = []
    for r in R:
        S, P = r["S"], r["P"]
        s, p = r[S], r[P]
        ev = []
        if s.get("bad_n") is not None:
            ev.append((s["bad_n"], 0, "S"))
        if p.get("bad_n") is not None:
            ev.append((p["bad_n"], 1, "P"))
        rec = {"match": r["match"], "game": r["game"], "S": S, "termination": r["termination"]}
        # first forced mate for the losing team
        w = r.get("own_first_mate_n")
        if w is not None:
            ev.append((w, 2, "W"))
        miss = [x for x in r["missed"] if x.get("legal") and not x.get("made")]
        if miss:
            ev.append((min(x["n"] for x in miss), 3, "F"))
        ev.sort()
        rec["events"] = ev
        kind, c, why = s_kind(s)
        rec["s_kind"], rec["s_why"] = kind, why
        rec["fatal"] = c
        rec["flag"] = r["termination"] == "flag"
        # a flag is its own cause only when the flagged seat had not yet been lost on its board
        if rec["flag"] and (s.get("bad_n") is None or s["bad_n"] >= r["plies"]):
            rec["cls"] = "e-flag"
        elif not ev:
            rec["cls"] = "?"
        else:
            first = ev[0][2]
            rec["cls"] = {"S": kind, "P": "d", "W": "e-race", "F": "f"}[first]
        rec["gap_P_before_S"] = (s["bad_n"] - p["bad_n"]) if (s.get("bad_n") is not None and p.get("bad_n") is not None) else None
        out.append(rec)
    json.dump(out, open(os.path.join(HERE, "classes.json"), "w"), indent=1)
    names = {"a": "(a) sudden mate, forecast arrival known fatal",
             "a2": "(a2) sudden mate, forecast arrival scored survivable",
             "a3": "(a3) sudden mate, forecast arrival, move not scored there",
             "a4": "(a4) decisive drop after a forecast arrival",
             "b": "(b) sudden mate, arrival in no world",
             "b2": "(b2) decisive drop after an arrival in no world",
             "c": "(c) slow loss on own board",
             "c2": "(c2) sudden mate, nothing arrived",
             "d": "(d) partner's board lost first",
             "e-flag": "(e) flag while not yet lost on the board",
             "e-race": "(e) race: the team reported a forced mate first and lost",
             "f": "(f) partner could have supplied a mating piece first"}
    for m in ("worlds5-vs-l50", "late50-vs-np-b"):
        sel = [x for x in out if x["match"] == m]
        print(f"## {m}: {len(sel)} lost games")
        cnt = collections.defaultdict(list)
        for x in sel:
            cnt[x["cls"]].append(x["game"])
        for k in sorted(cnt, key=lambda k: -len(cnt[k])):
            print(f"  {names.get(k, k):60} {len(cnt[k]):3}  games {sorted(cnt[k])}")
        print(f"  ended by a flag: {sorted(x['game'] for x in sel if x['flag'])} (classes {[x['cls'] for x in sel if x['flag']]})")
        print("  own-board kind of the mated seat's fall, whatever came first:")
        cnt2 = collections.defaultdict(list)
        for x in sel:
            cnt2[x["s_kind"]].append(x["game"])
        for k in sorted(cnt2, key=lambda k: -len(cnt2[k])):
            print(f"    {names.get(k, k):58} {len(cnt2[k]):3}  games {sorted(cnt2[k])}")


if __name__ == "__main__":
    main()
