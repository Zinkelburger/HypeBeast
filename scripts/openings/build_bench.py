#!/usr/bin/env python3
"""Build a frozen opening set for version-against-version matches.

    scripts/openings/build_bench.py v1            # writes openings/bench-v1*.txt
    scripts/openings/build_bench.py v2 --dry-run  # prints the choice, writes nothing

The set is chosen from the openings the engine has already played, by what
the games showed (scripts/openings/measure.py):

  1. An opening is a candidate with at least MIN_PAIRS complete pairs on
     record and a side score between SIDE_LOW and SIDE_HIGH (neither team
     keeps winning it whoever plays it).
  2. Candidates are ranked by usefulness: how much more often than an average
     opening its pair came out decisive, in the matches it was played in.
     What the opening's moves look like is not judged: a queen lost on move
     3 is fine if the games it leads to still separate engines.
  3. Going down that ranking, an opening is skipped when one already taken
     starts the same way on both boards (the same first SAME_PLIES half-moves
     of each board, boards in either order).
  4. The first 50 are bench-vN.txt, the next 50 bench-vN-repeat.txt.

bench-vN.txt is ordered best first, so its first 10, 25 and 50 openings are
the 20, 50 and 100 game matches: a shorter match is the start of a longer
one. Move lists are copied unchanged from the source sets, so an opening is
the same position it was in every earlier match.

A version is never rebuilt: the script refuses to overwrite one. When the
ledger (scripts/openings/ledger.py) shows openings that stopped being useful,
build the next version.
"""

from __future__ import annotations

import argparse
import datetime
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure  # noqa: E402

MIN_PAIRS = 6
SIDE_LOW, SIDE_HIGH = 0.35, 0.65
SAME_PLIES = 6
MAIN, REPEAT = 50, 50
PREFIXES = (10, 25, 50)
HALVINGS = 200

_sans: dict[str, tuple[list[str], list[str]]] = {}


def sans(opening: str) -> tuple[list[str], list[str]]:
    if opening not in _sans:
        _sans[opening] = measure.board_sans(opening)
    return _sans[opening]


def choose(stats: dict[str, dict], min_pairs: int = MIN_PAIRS) -> tuple[list[dict], dict[str, int]]:
    left = {"too few pairs": 0, "one side keeps winning": 0, "same start as one taken": 0, "ranked below the cut": 0}
    candidates = []
    for opening, s in stats.items():
        if s["pairs"] < min_pairs:
            left["too few pairs"] += 1
        elif not SIDE_LOW <= s["side"] <= SIDE_HIGH:
            left["one side keeps winning"] += 1
        else:
            candidates.append({"opening": opening, **s})
    candidates.sort(key=lambda c: (-c["usefulness"], -c["pairs"], c["opening"]))
    chosen, starts = [], set()
    for c in candidates:
        a, b = sans(c["opening"])
        c["san"] = (a, b)
        start = frozenset((" ".join(a[:SAME_PLIES]), " ".join(b[:SAME_PLIES])))
        if start in starts:
            left["same start as one taken"] += 1
        elif len(chosen) >= MAIN + REPEAT:
            left["ranked below the cut"] += 1
        else:
            starts.add(start)
            chosen.append(c)
    return chosen, left


def unseen(matches: dict[str, dict]) -> dict[tuple[int, int], float]:
    """How a choice made this way does on matches it has not seen.

    The matches are halved at random HALVINGS times. Each time the choice is
    made from one half (with half the pairs required) and its openings are
    counted in the other half: decisive pairs over the decisive pairs average
    openings would have had there. Returns that ratio, averaged, for the
    first 10, 25 and 50 and for the repeat set. It is a little pessimistic:
    the real choice is made from all the matches, not half.
    """
    slices = [(0, n) for n in PREFIXES] + [(MAIN, MAIN + REPEAT)]
    sums = {s: [0.0, 0] for s in slices}
    rng = random.Random(1)
    names = sorted(matches)
    for _ in range(HALVINGS):
        rng.shuffle(names)
        half = len(names) // 2
        chosen, _left = choose(measure.measure({n: matches[n] for n in names[:half]}), MIN_PAIRS // 2)
        test = measure.measure({n: matches[n] for n in names[half:]})
        for (a, b), acc in sums.items():
            rows = [test[c["opening"]] for c in chosen[a:b] if c["opening"] in test]
            expected = sum(r["expected"] for r in rows)
            if len(chosen) >= b and expected:
                acc[0] += sum(r["decisive"] for r in rows) / expected
                acc[1] += 1
    return {s: acc[0] / acc[1] for s, acc in sums.items() if acc[1]}


def summary(rows: list[dict], overall: float, ratio: float | None) -> str:
    decisive = sum(r["decisive"] for r in rows)
    expected = sum(r["expected"] for r in rows)
    text = (f"{len(rows)} openings, {sum(r['pairs'] for r in rows)} pairs on record, "
            f"{decisive} decisive against {expected:.0f} for average openings in the same matches")
    if ratio:
        text += (f"; on matches the choice had not seen, a choice made this way was {ratio:.2f} times as decisive "
                 f"as average: about {100 * overall * ratio:.0f}% of pairs against {100 * overall:.0f}%")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("version", help="e.g. v1")
    parser.add_argument("--logs", type=Path, nargs="*", help="log roots (default: this checkout's and its sibling worktrees')")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    roots = args.logs or measure.default_log_roots()
    matches = measure.load_matches(roots)
    stats = measure.measure(matches)
    all_pairs = [p for m in matches.values() for p in m["pairs"]]
    overall = sum(p["decisive"] for p in all_pairs) / len(all_pairs)
    chosen, left = choose(stats)
    if len(chosen) < MAIN:
        print(f"only {len(chosen)} openings qualify; a set needs {MAIN}", file=sys.stderr)
        return 1
    main_rows, repeat_rows = chosen[:MAIN], chosen[MAIN:MAIN + REPEAT]
    games = sum(len(m["games"]) for m in matches.values())
    today = datetime.date.today().isoformat()

    print(f"{len(matches)} matches, {games} games, {len(all_pairs)} complete pairs, {len(stats)} openings")
    print("left out: " + ", ".join(f"{n} {why}" for why, n in left.items()))
    ratios = unseen(matches)
    for n in PREFIXES:
        print(f"first {n}: {summary(main_rows[:n], overall, ratios.get((0, n)))}")
    if repeat_rows:
        print(f"repeat:   {summary(repeat_rows, overall, ratios.get((MAIN, MAIN + REPEAT)))}")

    out_dir = measure.ROOT / "openings"
    files = [(out_dir / f"bench-{args.version}.txt", main_rows,
              "the standard set: the first 10, 25 and 50 openings are the 20, 50 and 100 game matches")]
    if repeat_rows:
        files.append((out_dir / f"bench-{args.version}-repeat.txt", repeat_rows,
                      f"a second sample for repeating a match already played on bench-{args.version}.txt; "
                      "its openings rank below that set's, so expect fewer decisive pairs"))
    table = out_dir / f"bench-{args.version}.measured.tsv"
    if args.dry_run:
        return 0
    existing = [p for p in [f for f, _, _ in files] + [table] if p.exists()]
    if existing:
        print("frozen, not overwritten: " + ", ".join(p.name for p in existing) + " (build the next version)", file=sys.stderr)
        return 1

    for path, rows, purpose in files:
        lines = [
            f"# bench-{args.version}, frozen {today}: {purpose}",
            "# DEV: version-against-version HypeBeast matches; tuning allowed, never a strength report",
            f"# chosen by scripts/openings/build_bench.py from {games} HypeBeast games ({len(matches)} matches): "
            f"at least {MIN_PAIRS} pairs on record, side score {SIDE_LOW} to {SIDE_HIGH}, ranked by how often the pair was decisive",
            f"# {summary(rows, overall, ratios.get((0, MAIN) if rows is main_rows else (MAIN, MAIN + REPEAT)))}",
            f"# measurements per opening: {table.name}; do not edit or reorder: build the next version instead",
            "# each line: the first 16 half-moves in played order (engine tokens), then provenance",
        ]
        lines += [f"{r['opening']}\t{r['source']}" for r in rows]
        path.write_text("\n".join(lines) + "\n")
        print(f"wrote {path.relative_to(measure.ROOT)}  sha256 {measure.sha256(path)}")

    header = ["file", "line", "source", "pairs", "decisive", "expected", "usefulness", "matches",
              "games", "white_team_wins", "side", "board_a", "board_b"]
    out = [f"# bench-{args.version}: what the logs said about each opening on {today} "
           f"({games} games, {len(matches)} matches; columns as in scripts/openings/measure.py)", "\t".join(header)]
    for path, rows, _ in files:
        for i, r in enumerate(rows, 1):
            out.append("\t".join(str(x) for x in (
                path.name, i, r["source"].split()[0], r["pairs"], r["decisive"], f"{r['expected']:.2f}",
                f"{r['usefulness']:.3f}", r["matches"], r["games"], r["white"], f"{r['side']:.3f}",
                " ".join(r["san"][0]), " ".join(r["san"][1]))))
    out.append("# matches read: " + ", ".join(f"{name} ({len(m['games'])})" for name, m in sorted(matches.items())))
    table.write_text("\n".join(out) + "\n")
    print(f"wrote {table.relative_to(measure.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
