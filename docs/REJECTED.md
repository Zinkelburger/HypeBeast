# Tried and removed

Ideas that were built, measured and taken out of the engine. Read this before
building one of them again. The code of all four is in the tag `v1.1.0`
(commit 7c0b187), behind the options named here, each off by default there;
`git show v1.1.0:engine/src/<file>` gets it back. The match logs named below
are on the machine that played them (`logs/` is not in the repository); the
results are also in `PLAN.md`, revisions 10 and 11.

All matches: fixed node budgets per move, openings played twice with the teams
swapped, 95% intervals as the arena prints them. 100 games is about ±9 points.

| Idea | Options in v1.1.0 | Result | Verdict |
|---|---|---|---|
| Feed pricing by deep probes | `HBFeedPriceNodes`, `HBFeedPriceDiv`, `HBFeedPriceCap`, `HBFeedMatePrice`, `HBFeedPriceLost` | 46-53-1 and 28-32 against off; 56.2% against HiveMind where off scored 73.8% | worse |
| Verify a drop over a fail-low | `HBChanceVerify` | 51-49 against off, 1.44x to 2.63x the nodes to the same depth | no gain, slower |
| Threefold inside the search | `HBTreeRepetition` | 50-50 against off | no gain |
| Castle penalty at the root | `HBCastlePenalty` | 49-51 and 48-51-1 against off; 31-9 against HiveMind with and without | no effect |

## Feed pricing by deep probes

**What it was.** A capture on our board hands the captured piece to our
opponent's partner. The engine prices that by probing the partner board with
the piece in their hand: half the measured loss, at most 500 cp, 1500 cp when
it lets them mate our partner, nothing when our partner already looks lost.
That rule (v3) is still in the engine. Feed pricing replaced the depth-3
probes with searches of 1% of the move's budget each, and raised the prices:
cap 2000 cp, 4500 cp for a mate (a 1% winning chance instead of 18%), and half
the piece's value when the partner already looked lost (every price used to be
0 there: 41 of 41 such decisions in logs/c4all-vs-hm-n1500).

**Why it looked right.** Seven lost games against HiveMind turned on one move
that handed over the mating piece (`tests/feed_set.py`). With
`HBFeedPriceNodes=10 HBFeedPriceCap=2000 HBFeedMatePrice=4500
HBFeedPriceLost=50` the engine declined 5 of the 7 (v4: 2, chance without it:
1).

**What happened in play.**

| Match | Result | Log |
|---|---|---|
| on against off, 500k nodes | 46-53-1, 46.5% (37.2 to 55.8) | logs/c6-feed-vs-off |
| on against off, 4.5M nodes, held-out openings | 28-32, 46.7% (34.3 to 59.4) | logs/c6-feed-vs-off-n4500k |
| v5 settings with it against HiveMind 1500 | 22-17-1, 56.2% (38.9 to 73.6) | logs/c6feed-vs-hm-n1500 |
| v5 settings without it, same openings | 28-9-3, 73.8% (62.2 to 85.3) | logs/c4all-vs-hm-n1500 |

**Why, as far as is known.** In logs/c6feed-vs-hm-n1500 the mate price fired
in 14% of decisions, on two piece types at a time, and the main search had 11%
fewer nodes. The reading, never tested: it refused too many ordinary trades.

**Before trying again.** Passing the seven positions is not evidence; it did
that and lost. A new version has to show that the trades it refuses are bad
ones, on decisions from games that were not lost, before a match.

## Verify a drop over a fail-low (`HBChanceVerify`)

**What it was.** The chance search mixes the value of a likely drop with the
value of the real moves. When the real moves failed low, their value is only
an upper bound, and the mix uses it as if it were exact. Verify re-searched
the real moves (same node, same depth, drop pass off, salted table key)
before trusting a drop that relied on that bound.

**What happened.** It is sound, and it cost 1.44x the nodes to the same depth
at 500k and 2.63x at 4.5M.

| Match | Result | Log |
|---|---|---|
| on against off, 500k | 51-49 | logs/c3-verify-vs-noverify |
| on against base, 500k | 62-37-1, 62.5% (65% without it) | logs/c3-verify-100 |
| with `HBChanceHold`, against off, 500k | 49-51, 49.0% (38.4 to 59.7) | logs/c11-holdverify-vs-off |

**Before trying again.** The approximation it removes does not cost games at
these budgets. It would need a position set where the unverified mix picks a
losing move, and a much cheaper check.

## Threefold inside the search (`HBTreeRepetition`)

**What it was.** The referee draws on the third occurrence of a board with
the pockets ignored. The search hashes the pockets and does not see it. This
counted the rule exactly inside the tree: the real game's board keys plus the
line from the root, a draw score at the third occurrence.

**What happened.** 50-50 against off at 500k (logs/c5-treerep-vs-off). The
root checks (`HBAvoidDraw`, `HBSeekDraw`, both on) already catch the draws
that were thrown away in real games: every move is checked for a draw at once
or after one reply. `tests/test_draw.py` covers them.

**Before trying again.** It needs games lost or drawn through a repetition
more than one reply deep, which the root checks miss. None is on record.

## Castle penalty at the root (`HBCastlePenalty`)

**What it was.** A fixed number of centipawns taken off castling moves at the
root of our own board's searches, after games where HypeBeast castled into
HiveMind's pawn-drop storm (the `castle` items of `openings/hold_set.json`).

**What happened.** The first version read search bounds the wrong way (353 of
812 root evaluations at penalty 200); the second translated the windows and
was correct. Neither moved a result.

| Match | Result | Log |
|---|---|---|
| 200 cp, first version, against v5, 500k | 49-51, 49.0% (39.8 to 58.3) | logs/c8-castle200-vs-v5 |
| 200 cp, fixed, against none, 500k | 48-51-1, 48.5% (38.6 to 58.6) | logs/c9-fix-castle200-vs-fix |
| against HiveMind 1500, with it | 31-9, 77.5% | logs/c9hold-fix-castle200-vs-hm-n1500 |
| against HiveMind 1500, without it | 31-9, 77.5% | logs/c9hold-fix-vs-hm-n1500 |

Part of what it was meant to fix turned out to be a bug: castling was being
credited as a rook fed to the partner, so the engine castled too readily.
`HBFeedCastleFix` (on) removed that, and it is the change that gained.

**Before trying again.** A flat penalty knows nothing about the position. If
castling into a storm still loses games after the feed fix, the evidence
should come first: the castling decisions of lost games, and what the search
thought of the alternatives.

## Never merged

- **Pawn-drop danger in the evaluation** (branch `pawn-danger`). Its measure
  did not separate won and lost games 10 to 20 plies before mate (AUC 0.35 to
  0.73), and our own evaluation already read those positions as bad.
- **Chance without the worlds.** The chance search alone, without v4's choice
  over weighted worlds at the root: 14-26 against base (logs/chance-noworlds-n500k).
  It gives up v4's gain; the two are used together.
- **`HBChanceTrustThem0` 65 instead of 50.** Stopped at 17-17 after 34 games.

## Still in the engine, off, not decided

Kept for now; see `docs/OPTIONS.md`. Inside the noise at 100 games each: `HBChanceCondition` (52-47-1), `HBChanceHold` (49-51),
`HBFeedEpFix` (53-47). `HBFeedTieBreak` and `HBChanceAspiration` have no
finished match on record.
