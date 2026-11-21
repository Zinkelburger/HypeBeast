# Tried and removed

Ideas that were built, measured and taken out of the engine. Read this before
building one of them again. The code of the first four is in the tag `v1.1.0`
(commit 7c0b187), behind the options named here, each off by default there;
`git show v1.1.0:engine/src/<file>` gets it back. The mate search and the
quiet opening were never merged: their code is
`docs/patches/mate-search-quiet-plies.patch`, which applies to commit cc47c8a
(with both options off that build gave v7's move, score and node counts on 40
of 40 positions). The match logs named below are on the machine that
played them (`logs/` is not in the repository); the results of the first four
are also in `PLAN.md`, revisions 10 and 11.

All matches: fixed node budgets per move, openings played twice with the teams
swapped, 95% intervals as the arena prints them. 100 games is about ±9 points.

| Idea | Options in v1.1.0 | Result | Verdict |
|---|---|---|---|
| Feed pricing by deep probes | `HBFeedPriceNodes`, `HBFeedPriceDiv`, `HBFeedPriceCap`, `HBFeedMatePrice`, `HBFeedPriceLost` | 46-53-1 and 28-32 against off; 56.2% against HiveMind where off scored 73.8% | worse |
| Verify a drop over a fail-low | `HBChanceVerify` | 51-49 against off, 1.44x to 2.63x the nodes to the same depth | no gain, slower |
| Threefold inside the search | `HBTreeRepetition` | 50-50 against off | no gain |
| Castle penalty at the root | `HBCastlePenalty` | 49-51 and 48-51-1 against off; 31-9 against HiveMind with and without | no effect |
| Mate search (2026-11-20) | `HBMateSearch`, in the patch | 50-50 against off, decisive pairs 12-12 | no gain |
| Quiet opening (2026-11-20) | `HBQuietPlies`, in the patch | 36-63-1 against off, decisive pairs 7-21 (p 0.013) | worse |

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

## Mate search (`HBMateSearch`, 2026-11-20)

**What it was.** A proof-number search (df-pn) of one board in which the
attacker plays only checks and the defender every legal reply, with the
pieces each side holds now. It ran at the root, at 2% of the move's nodes a
search. A mate it proved for us was played at once. If the main search's move
allowed one that the main search had not seen, the main search was run again
over the moves with no proof against them, and a move chosen later (a
world's, a draw rule's) that allowed one gave way to the main search's move.

**Why it looked right.** In the v7 self-play games the first seat to see
itself mated lost 54 of 55 games, so seeing a mate sooner seemed worth a lot.

**What the positions said before the match.** The search works and is cheap:
it found 51 to 55 of 60 mates the main search had announced, in a median of
41 nodes, and claimed none in 60 level positions. But it proved a mate the
main search had not announced in only 1 of 240 positions scored +300 to
+2000, and in 9 of 120 scored above +2000. And in 71 games, a search of 4M
nodes on the position before the seat's last move ahead of its first mate
sighting found it already mated in 14 and at -600 cp or worse in 53; the
position could still be held in 2.

**What happened in play.**

| Match | Result | Log |
|---|---|---|
| on against off, 500k nodes, 50 pairs of bench-v1 | 50-50, decisive pairs 12-12 (p 1.0), 26 split | logs/x1-mate |

It played a proved mate in 52 games and won 50 of them. The guard fired in 12
games, at scores of -900 to -6800, and 11 were lost.

**Why, as far as is known.** The main search already finds the mates that
decide games, and by the time a seat is being mated its position was lost
several moves earlier. The mate is how a lost game ends, not where it is lost.

**Before trying again.** A mate search has to act where the game is still
level. That needs positions where a search of checks alone finds a mate, or
the only defence to one, that a main search of the same budget misses, at a
score between -600 and +600. This set found one such position in 240.

## Quiet opening (`HBQuietPlies`, 2026-11-20)

**What it was.** While fewer than 70 moves had been played on the two boards
together: no feed prices, no forecast, no worlds and no chance nodes. The
main search had about 90% of the move's nodes (450k of 500k against 238k),
and the team rules still checked its move.

**Why it looked right.** On 150 positions, each setting's move was judged by
a search of 4M nodes on the reply position. Before 80 plies, turning chance,
worlds or the whole coordinator off changed the judged value by less than
its error; every measured difference came later.

**What happened in play.**

| Match | Result | Log |
|---|---|---|
| 70 plies quiet against off, 500k nodes, 50 pairs of bench-v1 | 36-63-1, decisive pairs 7-21 (p 0.013), 22 split | logs/x1-quiet70 |

**Why, as far as is known.** The forecast, worlds and chance nodes matter in
the first 70 plies as well. The position check was too coarse to see it: it
could not see a doubling of the nodes either (-1 +/- 9 cp). The extra nodes
also bought no depth: with nearly twice the main-search nodes the quiet mode
reached the same or a lower depth than the default on the positions tried.

**Before trying again.** Do not take "no difference on judged positions" as
grounds to remove a part. That check also put worlds at -15 +/- 16 cp, and
without worlds the engine scored 31-69 (below).

## What the v7 parts are worth (matches of 2026-11-20)

Each is the v7 engine with one switch off against the same build with it on:
500k nodes, 50 pairs of `openings/bench-v1.txt`, no errors or illegal moves.

| Switched off | Result | Reading |
|---|---|---|
| `HBWorlds` | 31-69, decisive pairs 5-24 (p 0.001), 21 split (logs/x1-noworlds) | worlds are worth a great deal with the chance search on; keep |
| `HBFeedPrices` | 50-50, decisive pairs 9-9 (p 1.0), 32 split (logs/x1-noprices) | no measured gain from feed prices; not decided |

Feed prices also feed the piece-value report (`hb_values`) that the website
shows, so taking them out of the search is a separate step from dropping the
probes.

## Never merged

- **Pawn-drop danger in the evaluation** (branch `pawn-danger`). Its measure
  did not separate won and lost games 10 to 20 plies before mate (AUC 0.35 to
  0.73), and our own evaluation already read those positions as bad.
- **Chance without the worlds.** The chance search alone, without v4's choice
  over weighted worlds at the root: 14-26 against base (logs/chance-noworlds-n500k).
  It gives up v4's gain; the two are used together.
- **`HBChanceTrustThem0` 65 instead of 50.** Stopped at 17-17 after 34 games.

## Explored on logs and positions, not built (2026-11-20)

- **Return table.** Arrival odds that depend on our own capture ("if I give a
  knight, a rook comes back 50%"). In 8,088 logged games something came back
  within the partner's next two moves 60% of the time after giving nothing
  and 63% to 67% after giving a piece, with the same mix of pieces; after the
  first 40 plies there was no difference. The forecast already expected what
  came back after a capture (0.705 piece types predicted, 0.703 observed,
  7,718 decisions).
- **Reweighting the worlds.** The worlds choice can be replayed exactly from
  the logged `hb_coord` lines (7,875 of 7,875 decisions), so each rule's move
  was scored in the world that then happened (5,390 decisions). The shipped
  rule gains 20.7 cp over the main search's move. Opponent arrivals at their
  calibrated weight: 19.3. All arrival worlds at half weight: 15.2. Switch
  margin 0: 21.1. Capturing moves given 10 or 20 more points of "a piece
  comes back": 20.8 and 20.6. Knowing exactly what will arrive: 40.7. No
  better forecast, from a partner's message or otherwise, can add more than
  about 20 cp a decision at this step.
- **Telling the partner what we need.** Tried nine ways on the
  `v5-coordination` branch, 11 to 13 November (`PARTNER_TALK.md` and
  `EXPERIMENTS.md` there): none adopted. Replacing our own search of the
  partner board with the partner's lines lost 4-11; the partner's line added
  on top of our own was level over 400 games (210-190); prices from the
  partner's told values lost at every share tried except a third, gains only
  (159-141, never repeated).

## Still in the engine, off, not decided

Kept for now; see `docs/OPTIONS.md`. Inside the noise at 100 games each: `HBChanceCondition` (52-47-1), `HBChanceHold` (49-51),
`HBFeedEpFix` (53-47). `HBFeedTieBreak` and `HBChanceAspiration` have no
finished match on record.
