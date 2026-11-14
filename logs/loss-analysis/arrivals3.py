#!/usr/bin/env python3
"""When does a forecast piece arrive? Only pieces the forecast names at one ply and no earlier one.
usage: arrivals3.py ARRIVALS_JSON"""
import collections, json, sys
rows = [r for r in json.load(open(sys.argv[1])) if r["left"] >= 6]
QS = (1, 2, 3, 4, 5, 6)
print("piece (side and type) first named at ply k of a forecast line, in a line of weight w:")
print("  share that reached that hand before ply q of our board     " + " ".join(f" q<={q}" for q in QS) + "   | of those within 6: at q=1..6")
for side in "-+":
    for k in range(4):
        for lo, hi in ((0, .15), (.15, .4), (.4, 1.01)):
            n = 0; hits = [0]*len(QS); dist = collections.Counter()
            for r in rows:
                first = {}   # key -> (smallest ply, largest weight at that ply)
                for l in r["lines"]:
                    for c in l["caps"]:
                        kk, key = int(c[0]), c[1:]
                        if key not in first or kk < first[key][0] or (kk == first[key][0] and l["w"] > first[key][1]):
                            first[key] = (kk, l["w"])
                for key, (kk, w) in first.items():
                    if kk != k or key[0] != side or not (lo <= w < hi): continue
                    n += 1
                    fq = next((q for q, kx, _ in r["future"] if kx == key), None)
                    for i, Q in enumerate(QS):
                        hits[i] += fq is not None and fq <= Q
                    if fq is not None and 1 <= fq <= 6: dist[fq] += 1
            tot = sum(dist.values()) or 1
            print(f"  {'to them' if side == '-' else 'to us  '} k={k} w {lo:.2f}-{hi:.2f} n={n:<6}" + "".join(f" {100*h/n if n else 0:5.1f}%" for h in hits)
                  + "   | " + " ".join(f"{100*dist[q]/tot:3.0f}" for q in range(1, 7)))
