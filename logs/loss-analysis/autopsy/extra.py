#!/usr/bin/env python3
"""Details for classes d, e-race and f, and the counts used for upper bounds."""
import collections, json, os
from common import HERE, MATE
from classify import s_kind
T = {(r["match"], r["game"]): r for r in json.load(open(os.path.join(HERE, "timeline.json")))}
C = json.load(open(os.path.join(HERE, "classes.json")))
print("## class d: the partner's own fall, by the same rules")
kinds = collections.Counter()
for c in C:
    if c["cls"] != "d":
        continue
    t = T[(c["match"], c["game"])]
    p = t[t["P"]]
    k, f, why = s_kind(p)
    kinds[k] += 1
    print(f"  {c['match'][:7]} g{c['game']} P={t['P']} P_bad@{p['bad_n']} ({p.get('pre_bad_score')}->{p.get('bad_score')}) S_bad@{t[t['S']]['bad_n']} "
          f"gap {c['gap_P_before_S']} plies; P kind {k}; piece {f and f['k']} p={f and f.get('world_p')} v={f and f.get('v_chosen')}; S kind {c['s_kind']}")
print("  partner fall kinds:", dict(kinds))
print("\n## class e-race and f")
for c in C:
    if c["cls"] not in ("e-race", "f"):
        continue
    t = T[(c["match"], c["game"])]
    print(f"  {c['match'][:7]} g{c['game']} {c['cls']} S={t['S']} S_bad@{t[t['S']]['bad_n']} own first mate @{t['own_first_mate_n']} by {t['own_first_mate_seat']}, "
          f"mate at end {t['own_mate_at_end']}; S kind {c['s_kind']}")
    for x in t["missed"]:
        if x.get("legal") and not x.get("made"):
            print(f"      missed: {x['seat']} n={x['n']} +{x['t']} {x['kind']} p={x['p']:.2f} base={x['base']} partner n={x['partner_n']} decided {x['partner_decision']} "
                  f"(score {x['partner_score']}) legal captures {x['legal']}")
print("\n## missed supplies over all lost games (any time)")
allm = [(k, x) for k, t in T.items() for x in t["missed"]]
cnt = collections.Counter()
for k, x in allm:
    if "legal" not in x:
        cnt["partner had no decision before our next"] += 1
    elif not x["legal"]:
        cnt["no legal capture of that type"] += 1
    elif x["made"]:
        cnt["captured"] += 1
    else:
        cnt["legal, not taken"] += 1
print("  decisions:", dict(cnt), "games with a legal one not taken:", sorted({(k[0][:7], k[1]) for k, x in allm if x.get('legal') and not x.get('made')}))
