#!/usr/bin/env python3
"""How each opening of a set has done in every match on record.

    scripts/openings/ledger.py                      # openings/bench-v1.txt
    scripts/openings/ledger.py openings/bench-v1-repeat.txt

Prints the set's openings in file order with the counts of
scripts/openings/measure.py (all games ever played on the opening, including
those before the set was frozen), and how the set did in the matches played
on the file itself. An opening is marked when it no longer meets what it was
chosen for:

  SIDE    its side score left 0.30 to 0.70: one team wins it whoever plays
  SPLITS  its usefulness fell below 0.85: its pairs split more than average

Marks are advice for the next version. The frozen file is never edited:
when several openings are marked, build bench-v(N+1).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure  # noqa: E402

SIDE_LOW, SIDE_HIGH = 0.30, 0.70
MIN_USEFULNESS = 0.85


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    path = Path(argv[0]) if argv else measure.ROOT / "openings/bench-v1.txt"
    openings = measure.read_set(path)
    matches = measure.load_matches(measure.default_log_roots())
    stats = measure.measure(matches)
    sha = measure.sha256(path)
    on_set = {n: m for n, m in matches.items() if m["openings_sha256"] == sha}

    print(f"{path.name}  sha256 {sha[:16]}  {len(openings)} openings")
    if on_set:
        pairs = [p for m in on_set.values() for p in m["pairs"]]
        print(f"played on this file: {len(on_set)} match(es), {len(pairs)} pairs, "
              f"{sum(p['decisive'] for p in pairs)} decisive ({100 * sum(p['decisive'] for p in pairs) / len(pairs):.0f}%)")
        for name, m in sorted(on_set.items()):
            d = sum(p["decisive"] for p in m["pairs"])
            print(f"  {name}: {d} of {len(m['pairs'])} pairs decisive")
    else:
        print("played on this file: no match yet")
    print("line  pairs decisive expected usefulness  games white  side  mark  source")
    marked = 0
    for i, (opening, source) in enumerate(openings, 1):
        s = stats.get(opening)
        if not s:
            print(f"{i:4}  no game on record  {source.split()[0] if source else ''}")
            continue
        marks = []
        if not SIDE_LOW <= s["side"] <= SIDE_HIGH:
            marks.append("SIDE")
        if s["usefulness"] < MIN_USEFULNESS:
            marks.append("SPLITS")
        marked += bool(marks)
        print(f"{i:4}  {s['pairs']:5} {s['decisive']:8} {s['expected']:8.1f} {s['usefulness']:10.2f}  "
              f"{s['games']:5} {s['white']:5}  {s['side']:.2f}  {'+'.join(marks) or '-':6}{source.split()[0] if source else ''}")
    print(f"{marked} of {len(openings)} marked")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
