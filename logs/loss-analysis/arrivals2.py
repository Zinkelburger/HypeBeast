#!/usr/bin/env python3
"""Tables from arrivals.json. usage: arrivals2.py ARRIVALS_JSON"""
import collections, json, re, sys
rows = json.load(open(sys.argv[1]))
QS = (0, 1, 2, 3, 4, 6)

def first_q(future, key):
    for q, k, _ in future:
        if k == key:
            return q
    return None

def has_all(future, want, Q):
    got = collections.Counter(k for q, k, _ in future if q <= Q)
    return all(got[k] >= n for k, n in want.items())

def key_counter(key):
    c = collections.Counter()
    for s, t in re.findall(r"([+-])([PNBRQ])", key):
        c[s + t] += 1
    return c

def pr(label, hits, n):
    print(f"  {label:<34} n={n:<7}" + "".join(f" {100*h/n if n else 0:5.1f}%" for h in hits))

full = [r for r in rows if r["left"] >= 6]
print(f"decisions {len(rows)}, with 6+ of our-board plies left {len(full)}")
print("\n=== A capture named in a forecast line: did that piece go to that side, by ply q of our board? ===")
print("  (q=1: before the opponent's reply, q=2: before our next move)   " + " ".join(f"q<={q}" for q in QS))
for mover in ("partner", "opponent"):
    for j in range(4):
        for lo, hi in ((0, .1), (.1, .25), (.25, .5), (.5, 1.01)):
            hits = [0]*len(QS); n = 0
            for r in full:
                if r["mover"] != mover: continue
                for l in r["lines"]:
                    if not (lo <= l["w"] < hi): continue
                    for c in l["caps"]:
                        if int(c[0]) != j: continue
                        n += 1
                        fq = first_q(r["future"], c[1:])
                        for i, Q in enumerate(QS):
                            hits[i] += fq is not None and fq <= Q
            pr(f"{mover} to move, ply {j}, w {lo:.2f}-{hi:.2f}", hits, n)

print("\n=== When a named capture does happen within 6 plies, at which q? (share) ===")
for mover in ("partner", "opponent"):
    for j in range(4):
        dist = collections.Counter()
        for r in full:
            if r["mover"] != mover: continue
            for l in r["lines"]:
                for c in l["caps"]:
                    if int(c[0]) != j: continue
                    fq = first_q(r["future"], c[1:])
                    if fq is not None and fq <= 6: dist[fq] += 1
        tot = sum(dist.values())
        print(f"  {mover:<8} ply {j}: n={tot:<6} " + " ".join(f"q{q}:{100*dist[q]/tot:4.1f}%" for q in range(7)) if tot else "")

print("\n=== Worlds (hb-late50 seats only): whole package arrived by q, by stated probability ===")
late50 = [r for r in full if r["role"] == "contender"]
for kind in ("early", "late"):
    for lo, hi in ((0, .05), (.05, .1), (.1, .2), (.2, .35), (.35, .6), (.6, 1.01)):
        hits = [0]*len(QS); n = 0; psum = 0
        for r in late50:
            early_keys = set()
            for l in r["lines"]:
                e = collections.Counter(c[1:] for c in l["caps"] if int(c[0]) <= 1)
                early_keys.add(tuple(sorted(e.items())))
            for w in r["worlds"]:
                if w["arrival"] == "none" or not (lo <= w["p"] < hi): continue
                want = key_counter(w["arrival"])
                is_early = tuple(sorted(want.items())) in early_keys
                if (kind == "early") != is_early: continue
                n += 1; psum += w["p"]
                for i, Q in enumerate(QS):
                    hits[i] += has_all(r["future"], want, Q)
        pr(f"{kind} world, p {lo:.2f}-{hi:.2f} (mean {psum/n if n else 0:.2f})", hits, n)

print("\n=== 'Nothing arrives' world: no capture at all on the partner board by q ===")
for lo, hi in ((0, .3), (.3, .5), (.5, .7), (.7, .9), (.9, 1.01)):
    hits = [0]*len(QS); n = 0
    for r in late50:
        p = r["worlds"][0]["p"]
        if not (lo <= p < hi): continue
        n += 1
        for i, Q in enumerate(QS):
            hits[i] += not any(q <= Q for q, _, _ in r["future"])
    pr(f"p_none {lo:.2f}-{hi:.2f}", hits, n)

print("\n=== A piece type reaching the OPPONENT's hand by q: in some world, or in none ===")
for t in "PNBRQ":
    for inw in (True, False):
        hits = [0]*len(QS); n = 0
        for r in late50:
            named = any(("-" + t) in w["arrival"] for w in r["worlds"])
            if named != inw: continue
            n += 1
            fq = first_q(r["future"], "-" + t)
            for i, Q in enumerate(QS):
                hits[i] += fq is not None and fq <= Q
        pr(f"-{t} {'in a world' if inw else 'in no world'}", hits, n)
print("\n=== The same for OUR hand ===")
for t in "PNBRQ":
    for inw in (True, False):
        hits = [0]*len(QS); n = 0
        for r in late50:
            named = any(("+" + t) in w["arrival"] for w in r["worlds"])
            if named != inw: continue
            n += 1
            fq = first_q(r["future"], "+" + t)
            for i, Q in enumerate(QS):
                hits[i] += fq is not None and fq <= Q
        pr(f"+{t} {'in a world' if inw else 'in no world'}", hits, n)
