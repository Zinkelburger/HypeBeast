# Opening sets

A match starts each game from the first 16 half-moves of a real bughouse game
(FICS 2014, rated, all four players 1800 or above). The engine does not
choose these moves, and nobody tidied them: some contain a human blunder.
Every opening is played twice with the teams swapped, so each engine plays all
four seats of it and a lopsided opening cannot favour one engine. What a bad
opening costs is information: when the same side wins it whoever plays, the
pair splits 1-1 and says nothing.

| File | Use |
|---|---|
| `bench-v1.txt` | The standard set for version-against-version matches. 50 openings, best first: the first 10, 25 and 50 are the 20, 50 and 100 game matches. Frozen 2026-11-20. |
| `bench-v1-repeat.txt` | 50 other openings, for playing a match a second time on fresh positions and pooling. They rank below the standard set's, so fewer of their pairs are decisive. |
| `bench-v1.measured.tsv` | What the logs said about each of those 100 openings on the day the set was frozen, and the matches that were read. |
| `dev100.txt` | The set the matches before 2026-11-20 were played on (its first lines, up to 50). Kept so those matches can be replayed. Not for new matches. |

These are development sets: tuning on them is allowed and a result on them is
never a strength claim. Matches against HiveMind use the arena's own
`screen20.txt` and `heldout200.txt`.

## How bench-v1 was chosen

From what the engine's own games showed, not from how the moves look
(`scripts/openings/build_bench.py`, counts defined in
`scripts/openings/measure.py`):

1. 8,363 HypeBeast against HypeBeast games on 625 openings were read
   (4,174 complete pairs, 65 matches). 200 openings had at least 6 pairs.
2. 13 of those were dropped because one team keeps winning them whoever
   plays (side score outside 0.35 to 0.65). The opening with the queen lost
   on move 3 (`fics=2889544`) is one: the team that won the queen won 39 of
   53 distinct games, and its pairs were only as decisive as average.
3. The rest were ranked by usefulness: how often the opening's pair was
   decisive, against how often pairs were decisive in the same matches.
   This predicted decisive pairs in matches it had not seen better than the
   side score did, so the side score is only the guard in step 2. A material
   gap is not held against an opening: three of the 50 start with a board
   three or more points apart, because their games still separate engines.
4. An opening was skipped when one already taken starts the same way on both
   boards (1 case).

On matches the choice had not seen (the matches halved at random 200 times,
chosen on one half, counted on the other), openings chosen this way were
1.19 times as decisive as the average opening, and the first ten 1.23
times. The first 10, 25 and 50 lines of `dev100.txt`, which were the matches
until now, were 0.96, 0.98 and 1.00 times as decisive as average. So expect
about a fifth to a quarter more decisive pairs from the same number of
games. How many that is depends mostly on the two builds: across the 65
matches, between 4% and 72% of pairs were decisive (45% overall), the fewest
when the builds differ in something that rarely fires.

The first match on the file (`logs/bench-v1-check`, v1.1.1 at 500,000 nodes
against itself at 450,000) had 24 of 50 pairs decisive, 15 of the first 25
and 7 of the first 10. The same two engines had 14 of 30 on `dev100.txt`.
One match cannot tell 48% from 54%: the ledger keeps the count as matches
are played.

## Running a match

```
scripts/ab_match.sh NAME SPEC_A SPEC_B [PAIRS]      # PAIRS 10, 25 or 50
OPENINGS=openings/bench-v1-repeat.txt scripts/ab_match.sh NAME-repeat SPEC_A SPEC_B [PAIRS]
scripts/match_report.py logs/NAME [logs/NAME-repeat]
```

The report's headline is the decisive pairs each side won and the exact
sign-test p on them. When about half the pairs are decisive:

| Match | Decisive pairs | Smallest result with p < 0.05 |
|---|---|---|
| 20 games | about 5 | 6-0 (5-0 is p 0.06) |
| 50 games | about 13 | 11-2 |
| 100 games | about 27 | 20-7 |

So 20 games can confirm that nothing is broken and can show a large gain;
it cannot show a small one on any set of openings.

Two matches on the same file compare game by game: a game that is move for
move the same in both was not touched by the change.

## Keeping the set honest

`scripts/openings/ledger.py [FILE]` prints every opening of a set with all
its games on record and marks the ones that stopped doing their job: `SIDE`
(side score outside 0.30 to 0.70) or `SPLITS` (usefulness below 0.85). It
also prints how decisive the matches played on the file itself have been.

A frozen file is never edited or reordered: every match records the file's
sha256, and a changed file would break the comparison with earlier matches.
When several openings are marked, or the engine has changed enough that the
set's decisive share has fallen back toward 45%, build the next version with
`scripts/openings/build_bench.py v2`. It reads all logs again, including
every match played on v1.
