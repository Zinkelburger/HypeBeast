#!/usr/bin/env python3
"""Which engine won a match, counted the way a small match has to be counted.

    scripts/match_report.py logs/NAME            # one match
    scripts/match_report.py logs/NAME logs/NAME-repeat   # the same two engines, pooled

Every opening is played twice with the teams swapped, so the unit is the
pair. A pair that splits 1-1 says nothing about which engine is better: only
the decisive pairs do, and the headline is how many of them each side won.
p is the exact sign test on those: the chance that two equal engines would
split the decisive pairs at least this unevenly. Below 0.05 is the usual
bar. A game whose partner game is missing (a stopped match) is left out.

What a result needs when about half the pairs are decisive (two builds
that differ in something rare split far more pairs than that):

  20 games (10 pairs):   ~5 decisive   p < 0.05 only at 6-0 or better
  50 games (25 pairs):  ~13 decisive   10-3 is p 0.09, 11-2 is p 0.02
  100 games (50 pairs): ~27 decisive   19-8 is p 0.05, 20-7 is p 0.02
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "openings"))
from measure import ROOT, sha256, sign_test  # noqa: E402


def known_sets() -> dict[str, str]:
    return {sha256(p): p.name for p in (ROOT / "openings").glob("*.txt")}


def read(match_dir: Path) -> dict:
    by_pair: dict[int, dict[str, float]] = defaultdict(dict)
    names, errors = None, 0
    for line in (match_dir / "results.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "contender_score" not in r:
            continue
        if (r.get("result") or {}).get("error"):
            errors += 1
            continue
        names = names or (r["contender"], r["baseline"])
        by_pair[r["pair"]][r["contender_team"]] = r["contender_score"]
    pairs = [sum(v.values()) for v in by_pair.values() if len(v) == 2]
    games = [s for v in by_pair.values() if len(v) == 2 for s in v.values()]
    sha, declared = None, None
    manifest = match_dir / "manifest.json"
    if manifest.exists():
        m = json.loads(manifest.read_text())
        sha = ((m.get("pins") or {}).get("openings") or {}).get("sha256")
        declared = m.get("pairs")
    return {"dir": match_dir, "names": names, "pairs": pairs, "games": games, "errors": errors,
            "unpaired": sum(len(v) == 1 for v in by_pair.values()), "openings": sha, "declared": declared}


def line(label: str, pairs: list[float], games: list[float]) -> str:
    won, lost = sum(s > 1 for s in pairs), sum(s < 1 for s in pairs)
    split = len(pairs) - won - lost
    w, l = sum(g == 1 for g in games), sum(g == 0 for g in games)
    text = (f"{label}: decisive pairs {won}-{lost} (p {sign_test(won, lost):.3f}), {split} split 1-1, "
            f"{len(pairs)} pairs; games {w}-{l}-{len(games) - w - l}")
    if games:
        text += f" ({100 * sum(games) / len(games):.1f}%)"
    return text


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    sets = known_sets()
    matches = [read(Path(a.rstrip("/"))) for a in argv]
    matches = [m for m in matches if m["names"]]
    if not matches:
        print("no finished game")
        return 1
    contender, baseline = matches[0]["names"]
    print(f"{contender} against {baseline} (pairs counted for {contender})")
    for m in matches:
        notes = [f"openings {sets.get(m['openings'], 'not a set in openings/')}" if m["openings"] else "openings unknown"]
        if m["declared"] and len(m["pairs"]) != m["declared"]:
            notes.append(f"INCOMPLETE: {len(m['pairs'])} of {m['declared']} pairs")
        if m["unpaired"]:
            notes.append(f"{m['unpaired']} unpaired game(s) left out")
        if m["errors"]:
            notes.append(f"{m['errors']} game(s) with an engine error left out")
        if m["names"] != (contender, baseline):
            notes.append(f"DIFFERENT ENGINES: {m['names'][0]} against {m['names'][1]}")
        print("  " + line(m["dir"].name, m["pairs"], m["games"]) + "; " + "; ".join(notes))
    if len(matches) > 1:
        if len({m["names"] for m in matches}) > 1:
            print("  not pooled: the matches are not between the same two engines")
            return 1
        if len({m["openings"] for m in matches}) < len(matches):
            print("  note: two of these matches used the same openings; pooling them counts those positions twice")
        print("  " + line("pooled", [s for m in matches for s in m["pairs"]], [g for m in matches for g in m["games"]]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
