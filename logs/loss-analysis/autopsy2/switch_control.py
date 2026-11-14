#!/usr/bin/env python3
"""Was the turning point more often a switch than comparable decisions? Control: every moving decision at -300 or
better whose seat's next decision was 400+ cp lower (or mated), in all games, per engine; and by talk for hb-plan.
Also the switch rate among decisions NOT followed by such a drop."""
import collections
from common2 import MATE, load
d = load("plan-vs-l50")
for e in ("hb-l50", "hb-plan"):
    for name, keep in (("all", lambda r: True), ("plan", lambda r: r.get("talk") == "plan"), ("own", lambda r: (r.get("talk") or "").startswith("own"))):
        if e == "hb-l50" and name != "all":
            continue
        rs = [r for r in d["rows"] if r["engine"] == e and keep(r) and r["decision"] != "pass" and r["score"] is not None
              and r["score"] >= -300 and abs(r["score"]) < MATE and r["next_score"] is not None]
        drop = [r for r in rs if max(r["next_score"], -100000) - r["score"] <= -400]
        nod = [r for r in rs if max(r["next_score"], -100000) - r["score"] > -400]
        f = lambda xs: (sum(r["override"] for r in xs), len(xs))
        a, b = f(drop), f(nod)
        print(f"{e} {name}: switched before a 400+ drop {a[0]}/{a[1]} = {a[0] / a[1]:.3f}; otherwise {b[0]}/{b[1]} = {b[0] / b[1]:.3f}")
