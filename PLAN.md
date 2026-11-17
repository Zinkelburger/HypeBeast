# HypeBeast: implement the new architecture, then measure it

Revision 7 — 2026-11-06. Replaces revision 6 and its phase ordering.

## Revision 12 (engine v7, 2026-11-17): holds on, four ideas removed, fewer listed options

Where this section and the text below disagree, this section wins.

**Holds are on by default** (`HBHoldWhenMated`, `HBHoldRace=250`), and a
second hold is new (`HBHoldPartnerMate`, on). Decided by the user on the
argument, without a 100-game match: a seat that is mated whatever it plays
loses nothing by sitting, and a seat whose partner has a forced mate can only
spoil it by moving.

- **Hold when mated**, as built in revision 11 with the clock race: a mate
  against us within `HBHoldFreePlies` (2) plies is held while we lead the
  diagonal seat, or through one partner move without a lead; a longer mate
  is held only when our partner has a forced mate our lead covers, and
  otherwise the seat plays the longest defence and holds at the end. Sitting
  early buys nothing that sitting at the last move does not, and playing on
  keeps the chance that the opponent misses the mate. One case still moves
  into a mate in one: the diagonal seat on turn with its team up on time,
  where sitting loses on the flag instead.
- **Hold on a partner mate** (`HBHoldPartnerMate`). Not mated, no mate of
  our own (then we play it: two seats waiting for each other only burn the
  lead), and the forecast's best line is a forced mate for our partner in
  `pm` moves. While we sit on turn our opponent cannot capture, so the seat
  being mated gets no piece, and without its team's time advantage no
  blocker either: the mate stands. That seat can only sit too, and loses the
  race when our lead is at least `HBHoldRace + (pm - 1) * 2500` ms: its last
  turn comes before our partner's mating move. (A hold when mated allows
  for `pm` moves; losing that race is a lost game, losing this one only
  ends the hold.) The guard,
  timers and wake rules are the hold's (`hold_guard`); the hold ends at any
  wake where the lead no longer covers it, and after every partner move the
  position is searched again. Reason `hold_partner_mate`.
  `tests/test_hold_partner.py`: 7 of 7.
- With `HBHoldRace` above 0, Stall and Wait also respect the arena's one
  timer per turn (revision 11). So v6's play is `HBHoldWhenMated=false
  HBHoldPartnerMate=false HBHoldRace=0`.

**Removed** (measured in revisions 10 and 11, no gain or worse): feed
pricing by deep probes (`HBFeedPriceNodes`, `Div`, `Cap`, `HBFeedMatePrice`,
`HBFeedPriceLost`), `HBChanceVerify`, `HBTreeRepetition`, `HBCastlePenalty`,
and what only they used (`Position::board_key`, the board-key history, the
verify counters). `docs/REJECTED.md` records what each was, its results, the
reading and where the code is (tag v1.1.0), so they are not built twice.
The feed prices of v3 (depth-3 probes, cap 500, mate 1500) are unchanged.

**Listed options.** `uci` lists the arena's options and one switch per
version's rules (9 `HB*` options instead of 46). The fitted values and the
experiments that are off (`HBChanceCondition`, `HBChanceHold`, `HBFeedEpFix`,
`HBFeedTieBreak`, `HBChanceAspiration`) can be set but are listed only with
`HB_EXPERIMENTAL=1` in the environment, which the match scripts and
`tests/hbutil.py` set: the arena refuses to send an option that is not
listed. `docs/OPTIONS.md` describes all of them.

**Checks.**

- The removal changes nothing: with the three hold settings off, this build
  prints the same output as the v1.1.0 binary (every info line, score, node
  count and move; time, nps and hashfull masked) on 232 of 232 fixed-node
  decisions at 500k nodes: the 94 positions of `openings/*.json` at the
  defaults, and slices of them under v4's and v5's settings, hold without
  and with the race, `HBChanceHold`, `HBChanceCondition`, and the tie-break
  with the en passant fix and aspiration. Two runs of v1.1.0 agree with each
  other the same way.
- The new defaults on those 94 positions (all from lost games): 11 decisions
  change, every one a mate in one against us that is now held; 19 longer
  mates play on (no partner mate), 8 mates in one move (race lost). No
  partner-mate hold arises there.
- `openings/hold_race_set.json` at the defaults: 28 of 28. `hold_set.json`:
  hold 2 of 3 (game 10 idx 40 moves by design, revision 11), feed 2 of 2.
- `tests/test_hold_race.py`, `test_hold_timer_arena.py`, `test_chance.py`,
  `test_draw.py` (without its tree-repetition cases), `test_coordinator.py`,
  `test_probe.py --long`, `test_terminal_fixtures.py`,
  `test_upstream_parity.py`, replay fuzz (400 games), smoke games (16): pass.
- A sanity match, not a measurement (32 games is about ±16 points): v7
  against the v1.1.0 binary, 16 opening pairs, 500k nodes:
  17-15, 53.1% (44.7 to 61.4), 15 pairs split and one won 2-0, every game
  ended in checkmate, no flag, no error (logs/v7b-vs-v110-sanity; the build
  before the `pm - 1` change scored the same, logs/v7-vs-v110-sanity). v7
  sat 14 times on a mate against it and 5 times on a partner mate, all five
  with the mate one move away. It declined the partner hold 34 times for
  the race: in arena self-play every move costs 1.5 to 2.5 s, the lead over
  the diagonal seat stayed between -4.3 and +2.2 s, and a mate two or more
  partner moves away needs 2.75 s or more. So this rule seldom fires here.
  Post-mortem: decisions where v7 stated a winning chance under 10% were
  won 13.1% of the time (107 decisions), v1.1.0's 0.0% (95).

| Match | Result | Log |
|---|---|---|
| v7 vs v1.1.0, 16 pairs, 500k | 17-15, 53.1% (44.7 to 61.4), Elo +22 (-37 to +80), no flags | logs/v7b-vs-v110-sanity |
| v7 at 500k vs v7 at 450k, 30 pairs (the holds on both teams) | 32-28, all 60 by checkmate, no flag, no error | logs/v7-selfplay-flags |

The second match puts the holds on both teams, so a seat that holds can meet
a seat that sits back; the node budgets differ only so that the two games of
a pair are not mirror images. Partner-mate holds: 19 decisions in 15 games,
and the holding team won all 15. Holds when mated: 45 decisions in 24
games, one of them won. No game ended on the clock.

Not done: a match against HiveMind with the holds on (revision 11's queued
`HBHoldRace` matches). HiveMind sits when its team is up on time, which is
where the first hold flagged, so that match is the one that tests the race
guard in play.

## Revision 11 (engine v6, 2026-11-16): review fixes and their matches

Where this section and the text below disagree, this section wins. v6 is v5
with `HBFeedCastleFix` on by default (`HBFeedCastleFix=false` plays as v5);
every other change here is behind an option that is off. `bin/hypebeast-v6`
gives the same search output as the build that played the matches
(bin/hypebeast-chance13 with the fix on) on 14 of 14 fixed-node searches.

A second reviewer (GPT-6.1-Sol through Codex, read-only) reviewed the engine;
each claim was then checked in the code before anything changed.

- **Castling was priced as a feed** (`HBFeedCastleFix`, b6f5083). Castling is
  encoded as king takes own rook, and `do_move` added the rook's feed price
  before the castling branch cleared the capture, so every castle in the tree
  counted as a rook sent to the partner. Live in every go over 200k nodes
  since v3. On a crafted position castling scored +944 cp with the old rule
  and +116 cp with the fix.
- **Castle penalty** (a831828): the penalty was subtracted after a search with
  untranslated windows; 353 of 812 root evaluations of a castling move read a
  bound the wrong way at penalty 200. Windows are now translated, finite
  values stay finite, the root key is salted. logs/c8-castle200-vs-v5 used
  the old code.
- **Stale hold** (6f53e37): a hold or stall continued when the position was
  replaced by a FEN snapshot. Cannot happen in the arena (it sends moves).
- **Tie-break** (b8dc491): never trades a found mate for a clipped score.
- **`HBChanceCondition`** (9da371d): a second chance on a line where the first
  was not taken uses (p1 - p0) / (1 - p0). The old rule counted one arrival
  twice (crafted case 0.875 against an exact 0.750). 1.14x nodes to depth.
- **`HBChanceHold`** (de71b9d): an arrival goes into the real pocket and the
  search chooses between dropping and holding it; the arrived branch runs at
  reduced depth. Matches the three crafted cases.
- **`HBFeedEpFix`** (1cd316d): quiescence prices en passant as a pawn capture.

| Match | Result | Log |
|---|---|---|
| v5 settings vs HiveMind 5000, screen20, 4.5M | 13-7, 65.0% (48.0 to 78.9) | logs/c6all-vs-hm-n5000 |
| base (v4 source) vs HiveMind 5000, same openings | 11-6-3, 62.5% (41.8 to 79.5) | logs/basefix-vs-hm-n5000 |
| castle penalty 200 (old code) vs v5, 500k | 49-51, 49.0% (39.8 to 58.3) | logs/c8-castle200-vs-v5 |
| hold when mated vs v5, 500k | 53-47, 53.0% (48.3 to 57.7), 5 flags | logs/c8-hold-vs-v5 |
| castle feed fix on vs off, 500k | 57-43, 57.0% (46.9 to 66.5) | logs/c9-castlefix-vs-off |
| same, held-out openings, 500k | 61-38-1, 61.5% (51.7 to 70.4), Elo +81 (+12 to +151) | logs/c9-castlefix-vs-off-heldout50 |
| same, held-out openings, 4.5M | 33-27, 55.0% (42.5 to 66.9) | logs/c9-castlefix-vs-off-n4500k |
| castle penalty 200 (fixed) vs none, both with the feed fix, 500k | 48-51-1, 48.5% (38.6 to 58.6) | logs/c9-fix-castle200-vs-fix |
| HBChanceCondition on vs off, 500k | 52-47-1, 52.5% (42.8 to 62.0) | logs/c10-condition-vs-off |
| HBChanceHold on vs off, 500k | 49-51, 49.0% (38.8 to 59.3) | logs/c11-hold-vs-off |
| hold when mated vs HiveMind 1500 | 27-11-2, 70.0% (54.5 to 82.0), 7 flags, all ours | logs/c8hold-vs-hm-n1500 |
| hold + castle feed fix vs HiveMind 1500 | 31-9, 77.5% (62.2 to 87.8), 8 flags, 7 ours | logs/c9hold-fix-vs-hm-n1500 |
| hold + castle feed fix + castle penalty 200 vs HiveMind 1500 | 31-9, 77.5% (62.2 to 87.8), 8 flags, 7 ours | logs/c9hold-fix-castle200-vs-hm-n1500 |
| HBFeedEpFix on vs off, 500k | 53-47, 53.0% (45.4 to 60.5) | logs/c11-epfix-vs-off |
| HBChanceHold + Verify on vs off, 500k | 49-51, 49.0% (38.4 to 59.7) | logs/c11-holdverify-vs-off |
| HBChanceTrustThem0 65 vs 50, 500k | stopped at 17-17 after 34 of 100 | logs/c11-trustthem65-vs-50 |
| hold + race + feed fix + castle penalty vs HiveMind 1500 | stopped at 2-0 after 2 of 40 | logs/c13race-fix-castle200-vs-hm-n1500 |

Reading: the castle feed fix is ahead in all three self-play runs (151-108-1
together) and is the one change with evidence. The castle penalty shows
nothing in self-play in either version. Condition and Hold are inside the
noise at 100 games each. Against HiveMind, hold when mated did not beat v5's
73.8% (logs/c4all-vs-hm-n1500) and HypeBeast's seat flagged in 14 games of
the two matches, four of them with a positive last eval.

The flags (diagnosed on those 14 games): every one was a hold-when-mated sit
that lost the clock race. A sitting seat's clock races the opposing seat on
turn on the partner board, and HiveMind's seat there sat only once its team
was ahead on time; the rule compared our clock with the mate length only.
Of 19 games with a hold, one was won. `HBHoldRace` (ac66576, f01c287; ms
margin, 0 = off) holds only when the partner has a forced mate and the lead
covers it, shares the arena's one wake timer per board turn between wait,
stall and hold, and ends a hold when the lead is gone; otherwise the seat
plays the longest defence. It passes the 28 replayed flag positions and an
arena-driven test; no match has finished with it. Until one has,
`HBHoldWhenMated` stays off.

Not supported by the data: a pawn-drop danger term in the evaluation (branch
pawn-danger, not merged). Its measure did not separate our won and lost
games 10-20 plies before mate (AUC 0.35 to 0.73), our own eval already read
-1100 to -2600 cp there, and castling lowers the measure.

Next: the queued `HBHoldRace` matches against HiveMind (1500 nodes with and
without the castle penalty, then 5000 nodes).

## Revision 10 (engine v5, 2026-11-15): chance inside the tree, referee draws

Where this section and the text below disagree, this section wins.

Why: v4's worlds let pieces arrive only at the first move. Most losses to
HiveMind were drop mates with a piece that arrived from the other board a few
moves later, and one move before the mate there was often no escape. Three
of the 40 games against HiveMind at 1500 nodes (logs/basefix-vs-hm-n1500)
were also thrown away as draws: HiveMind, lost, repeated the board with a
drop/capture cycle, which the referee's threefold counts while our search,
hashing the pockets, never saw it.

- **Chance inside the tree** (`HBChance`, on). The forecast becomes a table:
  for each side and piece type, the chance it has arrived by that side's
  first turn in the search and by its second. At `search()` nodes in plies
  1-4 (depth >= 2, not the root), after the real moves, the side to move may
  drop a likely piece it does not hold (a virtual piece: the hand count goes
  to -1; one per side per line). The node's value is the mix, in winning
  chances, of the best drop and the best real move; a drop is tested with a
  null window at the value it would need, exactly at PV nodes. TT keys of
  those plies carry the ply, so values from different contexts never mix.
  Under HypeBeast a mate with a virtual piece is a real mate, and NNUE stays
  on with negative hand counts (incremental equals refresh). Only main-pool
  searches use it, and only when the forecast ran.
- **Calibration.** k=0: `p = floor0 + (1 - floor0) * min(1, trust0 * W01)`;
  k=1: `p = floor1 + (1 - floor1) * min(1, trust1 * W01 + late1 * W23)`, W01
  the weight of forecast lines with that capture in partner plies 0-1 and W23
  in plies 2-3 only. Fitted on 5,130 self-play decisions
  (tests/arrival_rates.py): for us 85% / floor 1% and 95%, late 45% / floor
  3.75%; for them 50% / 0 and 90%, late 30% / floor 2%. These are the
  defaults (`HBChanceTrust{Us,Them}{0,1}`, `HBChanceLate{Us,Them}1`,
  `HBChanceFloor{Us,Them}{0,1}`, floors in basis points). Floors go only to
  types the giving side has on the partner board.
- **Horizon** (`HBChanceHorizon=1`, on): a move that gives check and its
  evasion do not advance the chance ply (at most 6 plies of a line), so spite
  checks cannot push an arrival past the last chance ply.
- **Stability** (`HBChanceStable`, on): no singular extension at chance plies
  where the mover could drop. The excluded-move search has no drop pass, so
  it found nearly every TT move singular; on a position where the opponent's
  queen arrived with 79% the tree to depth 11 fell from 210k to 57k nodes.
- **Draw policy** (`HBAvoidDraw`, `HBSeekDraw`, on). The referee draws on the
  third occurrence of a board with the pockets ignored, or at 100 half-moves.
  When a board position has been seen twice or the clock is at 98, the root
  checks every move: does it draw, or can an opponent reply draw (with the
  pieces they hold, or one their partner, on turn, can capture at once)? Not
  losing (main score >= -100 cp and partner forecast > -600 cp): such a move
  is replaced by a root search over the moves that do neither, in a 12% budget
  reserved up front, if that move scores >= -100 cp. Clearly losing (<= -600
  cp, no forecast mate for our partner): a move that draws at once is played.
  Referee wins and moves the exposure tiers or stalling require stand. The
  exposure, delivery and wait checks now stop at a drawn state.
- **Kept off:** `HBTreeRepetition` (the threefold inside the search, exact
  rule, real-game history included: 50-50 against off), `HBChanceVerify`
  (re-searches the real moves before trusting a drop over a fail-low: sound,
  1.44x nodes to the same depth at 500k and 2.63x at 4.5M, 51-49 against
  off), `HBChanceAspiration`, and feed pricing (`HBFeedPriceNodes`,
  `HBFeedPriceDiv`, `HBFeedPriceCap`, `HBFeedMatePrice`, `HBFeedPriceLost`:
  defaults are the v4 rule).

How the numbers were measured (fixed node budgets; 95% intervals as the arena
prints them, opening pairs as the unit):

| Match | Result | Log |
|---|---|---|
| chance + worlds (first version) vs base, 500k | 24-16, 60.0% (46.5 to 73.5) | logs/chance-worlds-n500k |
| chance without worlds vs base, 500k | 14-26, 35.0% (22.5 to 47.5) | logs/chance-noworlds-n500k |
| v3 rule (neither) vs base, 500k | 10-30, 25.0% (11.7 to 38.3) | logs/control-v3rule-n500k |
| chance, stable, horizon, calibrated vs base, 500k | 70-30, Elo +147 (+82 to +224) | logs/c2-all-100 |
| same, held-out openings, 500k | 67-31-2, Elo +131 (+73 to +197) | logs/c2-all-heldout50 |
| same, held-out, 4.5M | 24-15-1, Elo +80 (-28 to +205) | logs/c2-all-n4500k |
| chance3 config vs base, 500k | 65-35, Elo +108 (+42 to +181) | logs/c3-all-100 |
| chance5 + tree repetition vs base, held-out, 4.5M | 43-16-1, Elo +168 (+67 to +307) | logs/c5-treerep-n4500k |
| tree repetition on vs off, 500k | 50-50 | logs/c5-treerep-vs-off |
| Verify on vs off, 500k | 51-49 | logs/c3-verify-vs-noverify |
| Verify on vs base, 500k | 62-37-1, 62.5% (against 65% without it, c3-all-100) | logs/c3-verify-100 |
| v5 settings (chance4 build) vs HiveMind 1500, screen20 | 28-9-3, 73.8% (62.2 to 85.3) | logs/c4all-vs-hm-n1500 |
| base (v4 source) vs HiveMind 1500, same openings | 20-17-3, 53.7% (35.2 to 72.3) | logs/basefix-vs-hm-n1500 |
| v5 settings + feed pricing (chance6) vs HiveMind 1500 | 22-17-1, 56.2% (38.9 to 73.6) | logs/c6feed-vs-hm-n1500 |
| feed pricing on vs off, 500k | 46-53-1, 46.5% (37.2 to 55.8) | logs/c6-feed-vs-off |
| feed pricing on vs off, 4.5M, held-out openings | 28-32-0, 46.7% (34.3 to 59.4) | logs/c6-feed-vs-off-n4500k |
| v5 settings vs HiveMind 5000; base vs HiveMind 5000 | 13-7 (65.0%); 11-6-3 (62.5%), see revision 11 | logs/c6all-vs-hm-n5000, logs/basefix-vs-hm-n5000 |

What did not work: chance without the root-level worlds (it gives up v4's
gain), Verify (sound but slower, no gain), and feed pricing. Feed pricing
searched the partner board deeper (1% of the budget per probe), charged
4500 cp for a piece that lets them mate our partner (1% winning chance
instead of 18%) and half a piece's value when the partner already looked
lost (every price used to be 0 then: 41 of 41 such decisions in
logs/c4all-vs-hm-n1500). It declined 5 of the 7 decisive feeds in
tests/feed_set.py (v4: 2, chance without it: 1) and lost in play. In
logs/c6feed-vs-hm-n1500 the mate price fired in 14% of decisions, on two
piece types at a time, and the main search had 11% fewer nodes; untested
hypothesis: it refused too many ordinary trades.

Tools added: tests/test_chance.py (chance fixtures, injected and real
forecasts), tests/test_draw.py (the three drawn games, avoid and seek),
tests/feed_set.py with openings/feed_set.json (seven decisive feeding
mistakes against HiveMind, replayable), tests/flag_report.py (classifies
games that ended on the clock by both sides' last evals), loss_set.py
`--nodes` and `HB_JUDGE`, terminal fixtures and a replay fuzz that reach the
threefold through drop/capture cycles.

HiveMind adapter: the arena clone (upstream/cap-dev, gitignored) carries an
uncommitted patch in `TeamEngineSeat.decide` (tools/bughouse_arena/players.py).
HiveMind engine-v0.2.0 can answer `bestmove (none)` after reusing its tree in a
position where it has legal moves; the patch then counts a null output, sends
`ucinewgame`, sets Team and TimeAdvantage again, resends the position and
searches once more, instead of letting the seat sit until its flag falls.

Known residuals: the engine's board key carries no promoted markers and keys a
pseudo-legal rather than legal en-passant square, so in rare positions two
referee keys merge (tree repetition only; the root check uses the referee's
strings). The 16 GiB memory cap on this machine's session limits match
concurrency. bin/fsf-ref hashes to 6ff36f0f... while manifests/pins.json
records 6ef2fbb6...; unexplained (upstream parity tests pass against it).

Next: feeding the opponent's partner is still the main loss cause against
HiveMind (diagnosed positions in openings/feed_set.json). HiveMind's own
arrivals fit a trust of 0.65 against our `HBChanceTrustThem0` of 0.50.

## Revision 9 (engine v4, 2026-11-09): forecast the arrivals, choose over worlds

Where this section and the text below disagree, this section wins.

Why: v3's simulated hands looked only at captures the opponent could make on
the partner board that instant, took the worst one, ignored pieces coming to
us, and ran in 40% of decisions. v3 scored 12-12 against v2.

- **Forecast.** Before the main search, a 4-line search of the partner board
  (plus up to 4 captures outside those lines, searched on request) gives the
  likely moves there. The captures in the first two plies of each line are a
  package of arrivals on our board: pieces for us from our partner's captures,
  pieces for our opponent from the other side's. Lines are weighted by score
  (softmax, `HBForecastTemp` 250 cp), after adding half of what the line's
  captures are worth on our board (`HBForecastPrice` 50), measured by depth-5
  paired searches with and without the piece. 85% of an arrival is believed
  (`HBForecastTrust`); the rest counts as nothing arriving.
- **Worlds.** "Nothing arrives" plus up to three packages, each with a
  probability. Each arrival world is searched on our board with the pieces in
  hand (ours not droppable on the first move); its best move joins the
  candidates. Every candidate is then scored in every world, and the move with
  the best probability-weighted winning chance is played if it leads the main
  choice by 25 cp-equivalent. Winning chance is logistic in the score
  (`HBWinScale` 1000 cp) and a mate is 0 or 1. With nothing arriving, no move
  may outrank the main search's choice, because that search is deeper.
- **Kept from v3:** feed prices in the main search, exposure tiers, stalling,
  delivery wins and waits. `HBWorlds=false`, or a search under 500 ms or
  200k nodes, gives the v3 rule unchanged.
- **Budget.** Forecast about 13% before the main search, main about 45%,
  worlds the rest. Child hash 16 MB, cleared three times per go.

How the numbers were set (tests/forecast_check.py, on the v3-vs-v2 and
HypeBeast-vs-HiveMind game logs): temp, trust and price by log loss of the
forecast against what arrived in the next turn (0.154 against 0.242 for the
base rate on the HiveMind games); the win scale from 3,205 logged scores
against results (+600 cp on one board won 56%).

Measured: v4 against v3, 50 pairs of `openings/dev100.txt`, movetime 1000:
69-31, Elo +139 (95% +68 to +210), pentanomial 4/0/23/0/23, no errors.
`bin/hypebeast-v4` (sha256 20481d0d...) is the binary that played.

v4 against HiveMind CPU (400 nodes), first 5 pairs of screen20, movetime 9652:
8-2 (7 mates and 1 flag for, 2 mates against), 95% interval on the score 49.5%
to 94.2%, no errors. v1 scored 2.5 of 10 on the same ten games. Ten games is a
screen, not a strength report.

**The HiveMind benchmark from 2026-11-10** (`scripts/run_hivemind_benchmark.sh`):
HiveMind searches 1500 nodes a move, because 400 was weak. HypeBeast searches
4,500,000 nodes a move, the mean of what v4 searched in 9652 ms in the match
above (325 searches), so a busy machine slows the match without weakening
either side. The clock is unchanged and virtual: a move costs 1.5-2.5 s of
clock whatever the search took. Runs are a few pairs of screen20 at a time.
Results at 400 nodes, including the 8-2 above, are not comparable with these.

First run, 2026-11-10: v4 won game 1 (pair 1, as white) by checkmate at 90 s of
game clock; the game took 46 minutes to run. Stopped there at the user's
request, so this is one game and not a measurement.

Found on the way, not yet used (`HBForecastTrustLate`, default 0): in 16 of 20
drop mates against v1 the mating piece arrived during our last turn. One move
earlier the 2-ply forecast gave that piece 5% or more in 4 of 20 games, a 4-ply
reading in 15 of 20. But a capture seen only at plies 3-4 arrived within two
turns 15-29% of the time, whatever its weight. On the lost-game sets
(tests/loss_set.py) v4 closes the hole at its last move in 8 of 9 avoidable
cases, 7 by a move and 1 by sitting (v1: 1, v3: 6); one move earlier nothing tested does better than 11 of
24, and in 9 of those 24 no move escapes.

## Revision 8 (engine v3, 2026-11-09): what the first matches changed

The v1 match against HiveMind (+17 -22 =1) and its logs overrode these parts of
revision 7. Where this section and the text below disagree, this section wins.

Why: in 20 of 22 losses the mate was a drop of a piece captured on the other
board, and the main search could not see that. In 9 of those 20 the seat's own
probe scored the arriving piece as mate, and the -150 cap on R let it play on.
Waiting was reached on 12 of 1156 decisions and HypeBeast never sat.

- **Feed prices (replaces F in S).** Before the main search, partner probes
  measure what each piece type is worth to each team on the other board. The
  eval adds that at every capture in main and comparison searches (half the
  gain, capped at 500 cp; 800 or 1500 cp when a probe sees mate). L therefore
  includes cross-board value, so S = L + max(R/2, -400). Prices reset per go, so
  the main TT is cleared per go. Searches under 500 ms or up to 200k nodes skip
  prices and keep the old F term. `HBFeedPrices=false` turns this off.
- **Exposure tiers (replaces the capped-R treatment of mate and v2's veto).**
  CERTAIN: a referee-verified capture then mating drop, in either direction,
  including the seat whose move hands over the turn on the mating board. SOFT:
  the same but assuming our partner fails to move away, or a probe scores the
  arrival as mate. A CERTAIN main choice yields to any safer move that is not
  itself mated. A SOFT one yields only to a safe move within 600 cp.
- **Stalling (new).** If a CERTAIN main choice has no safe alternative, or only
  one more than 600 cp worse, the seat sits, because an opponent cannot capture
  or drop until we move. This needs at least 8 s on our clock and a 0.5 s lead
  over the same-colour seat on the other board (3 s if our partner must move
  first). `HBStall=false` turns this off.
- **Delivery wins and waiting (replaces section 5.4's voluntary rule).** A
  capture that lets our on-turn partner mate at once is played, unless the
  opponent can win first. Both seats run the same check, so the other seat may
  wait 3 s for it with no clock lead. The old every-partner-move-captures wait
  remains only for needing a block while in check. The time-advantage gate is
  gone: for a board B seat it measured the wrong clocks.
- **Budget and hash.** Slices are 72/6/20/2 rather than 60/10/25/5. HypeBeast
  mode raises the default 16 MB hash to 256 MB.

These coefficients are engineering defaults, not tuned values. Their test is the
match on `debug.txt` against v2, then a fresh held-out sample.

## 1. What to build

Build a CPU bughouse team engine using Fairy-Stockfish's existing search and
published bughouse NNUE. The first complete HypeBeast version must include
partner-board analysis, simulated incoming hands, and team-aware move selection.
Test it against **unmodified Fairy-Stockfish bughouse** and **HiveMind CPU**.

Keep existing NNUE weights, feature definitions, training tools, and datasets
unchanged. No retraining, new piece values, general pruning changes, probability
model, or full two-board search tree in this first implementation. The experiment
is whether the new controller improves team play using the existing evaluation.

Reliable operation is an acceptance requirement. Beating either opponent is an
experimental result, not a promise. Deliver losses and inconclusive results
honestly. Do not stop after building the stock baseline and call that HypeBeast.

## 2. Reuse and pin the components

- Fairy-Stockfish: resolve revision 6's `4e3d014` to a full upstream SHA and record
  it. Build an untouched reference binary and a separate HypeBeast fork with the
  same compiler and architecture flags. Freeze upstream during the experiment.
- NNUE: start with the published `bughouse-cd8cceab93fe.nnue`; verify compatibility
  and active loading. Use identical weight bytes in all FSF-based arms. Record
  filename and SHA-256. No silent classical-eval fallback or crazyhouse-net swap.
- Arena: reuse `~/Projects/Chess-Auto-Prep/tools/bughouse_arena` and
  `tools/test_bughouse_arena.py`: independent referee, virtual clocks, opening
  pairs, JSONL events, and BPGN. Read that repository's AGENTS.md before editing.
- HiveMind: pin the installed CPU binary/model used by the arena, including runtime
  backend. The checkout at `~/Projects/hivemind` may differ from the installed
  binary. Record both identities; do not modify the opponent.
- Keep engine code here and only necessary adapter/timing/reporting changes in
  Chess-Auto-Prep. No changes to the training pipeline.

Correction to revision 6: upstream training-data generation explicitly simulates
incoming pocket pieces for two-board variants. The published net's exact training
run is unverified; do not claim its pocket features were never trained.
`nnueAlias` selects a network; it does not add partner-board inputs.

## 3. Actual state and protocol

Keep the arena's one process per seat. Each HypeBeast process sees both boards;
no background search or shared-memory service is needed.

Add these options in HypeBeast arena mode:

- `HypeBeast` (default false): enables the adapter/controller. With it off, retain
  normal upstream protocols, search, and bench behavior.
- `Coordination` (default true when HypeBeast is enabled): enables the new controller.
- `Seat`: `Awhite`, `Ablack`, `Bwhite`, or `Bblack`.
- Existing `Team` and `TimeAdvantage`, plus `Clocks` in `aW,aB,bW,bB` milliseconds.

Extend the arena to send Seat and Clocks only to engines advertising them. Team
alone does not identify which board to search. Validate that Seat agrees with
Team (`white` means White A / Black B).

Accept the arena's dual FEN or start position followed by interleaved board-prefixed
moves. Replay both boards with correct transfers: a capture feeds the partner's
opposite color; a captured promoted piece becomes a pawn; en passant sends a pawn.
Preserve promotion markers, castling, en passant, counters, and actual history.
Start both actual boards with empty pockets, not pocketknight's extra knights.

Return `bestmove (moveA,moveB)` with the selected seat's move and `pass` in the unused
half. Waiting returns `pass` for the selected seat too. Handle stop/newgame/shutdown
cleanly and emit exactly one answer per go. Waiting is a returned action, never a
sleep inside the engine. Disable pondering and all computation between calls.

The pinned arena referee is authoritative. Port its exact root terminal conditions
and verify against its Python implementation, including its no-legal-moves team
condition, pockets-ignored repetition, and fifty-move rule. These are this arena's
conventions, not universal bughouse rules. If the actual game is nonterminal and
our seat has no legal move, return pass even if a local search calls it mate.

Do not port asynchronous play into every alpha-beta node in v1. Deep local terminal
scores remain approximations. A local mate is conditional; call a team win proven
only after applying the concrete moves/transfers and checking the joint referee.
Never change the referee or the unmodified opponent to favor HypeBeast.

## 4. Local searches and one total budget

Use bughouse movement and existing NNUE mapping, with captures leaving the local
board. In coordinated mode, disable upstream virtual drops of pieces not actually
in hand: explicit scenarios will supply those pieces. Add one search-context gate
covering generation and legality, including quiescence. Preserve physical drops
and upstream virtual-drop bookkeeping for normal mode. Do not replace bughouse
with another variant whose starting position or rules differ.

Use sequential, single-threaded child searches initially. Every child shares the
original go deadline/node budget. Initial allocation: 60% main search, 10% partner
and candidate discovery, 25% comparison probes, 5% response reserve. Unused budget
can flow forward. The absolute deadline and total node count override all slices.
Count controller overhead in timed runs and all child nodes in node-limited runs.
These allocations are initial engineering defaults, not measured optimal values.

Select a deterministic legal fallback before searching. Interrupted or incomplete
comparisons retain the main-search best move (or fallback if no iteration finished).
Never grant a fresh full movetime to each probe. Report aggregate nodes and time.

## 5. The coordination algorithm

### 5.1 Candidate moves

Obtain up to three main-search root candidates. Add up to two legal captures that
supply useful pieces to our partner, for at most five candidates. Test each distinct
available captured type in the partner's pocket using the paired partner probes
below. Prefer a verified immediate mating/blocking delivery, then the largest
measured gain. Break ties by upstream capture ordering and then UCI lexical order.
Promoted captures supply pawns. Include these delivery candidates even when absent
from the local top three; otherwise useful sacrifices can never be discovered.

If discovery expires, retain completed main candidates and log partial coverage.
Extra candidates need a root-restricted main search before numerical comparison.
Use scores at a common completed main-search depth. An extra candidate without
such a score is ineligible for numerical re-ranking.

### 5.2 Simulated hands

V1 examines immediate legal captures on the partner board for its actual side to
move. No invented arrival probabilities or assumed cooperative two-ply trades.
For each candidate on our board:

1. Apply our candidate and its outgoing transfer to a fresh joint-state copy.
2. Enumerate immediate captures on the resulting partner board.
3. Each donor capture creates one scenario: update that donor board and add the
   captured piece to the correct receiving pocket. Preserve the receiver's turn.
4. Probe our resulting local board. Always include a no-arrival scenario.

The modeled ordering is our move, then one donor capture, then the opponent's
local reply. This is a vulnerability stress test, not a claim that every local ply
corresponds to one partner ply. The no-arrival case represents waiting or choosing
another move. Deduplicate identical hand additions for local probes, retaining
donor provenance for verification. Never combine mutually exclusive captures into
one hand, count the same piece twice, or forget promoted-piece demotion.

Optional friendly arrivals supply no guaranteed numerical upside. Enemy arrivals
can expose vulnerabilities. Friendly scenarios inform waiting and diagnostics.
Multiple successive arrivals and two-ply forecasts are deferred.

### 5.3 Probe contract and selection rule

Start with three local plies after our candidate, plus normal quiescence. This
covers their reply, our possible drop, and a response to that drop. Compare each
scenario with a no-arrival probe at the same completed depth and resource cap.
Partner probes likewise compare the same board/turn with and without the delivered
piece at equal depth. Require completed exact root scores; interrupted searches
and fail-high/fail-low bounds are not exact values.

Normalize every score to our team's perspective, including board B. Convert
upstream internal values consistently to UCI centipawns. Let `finite(x)` clip to
[-2000, 2000], mapping local mate reports to the corresponding endpoint. These
are heuristic scores, not calibrated win probabilities or proven team mates.

For each candidate m:

```
L(m) = finite(main local-search score)
P0(m) = finite(no-arrival local probe after m)
Pe(m) = finite(local probe after enemy arrival e)
R(m) = min(0, min_e(Pe(m) - P0(m)))   # zero if no enemy scenarios
F(m) = finite(partner probe with m's outgoing delivery)
       - finite(partner probe without that delivery)
       # zero for a non-capture
S(m) = L(m) + clamp(R(m), -150, 0) + clamp(F(m), -100, 100)
```

Use shallow probe differences to adjust deep scores, not shallow absolute scores
to replace them. The caps prevent an uncertain scenario from buying an arbitrary
sacrifice. Friendly hypothetical arrivals do not add speculative upside to S.

Replace the main choice only if another candidate exceeds its S by at least 20 cp.
Ties retain the main choice, then use UCI order. A verified immediate team win can
override numerical ranking, but a local mate score alone cannot. For such a proof,
apply the candidate and check the actual joint referee immediately; do not assume
an unplayed future partner move happens before an opponent response.

Use deterministic round-robin scheduling across candidates and scenarios. If the
eligible comparison set lacks any required completed probe, keep the main choice
for that decision. Log coverage and fallback. Freeze coefficients for the first
matches; do not quietly tune on the reported test games.

This is intentionally limited: later opponent captures feeding their partner,
longer transfer chains, and mating races can defeat it. Preserve such losses for
the next iteration rather than claiming v1 implements complete joint search.

### 5.4 Waiting

Mandatory waiting: return pass when our seat has no legal move and the actual joint
state is nonterminal. Do not incorrectly require TimeAdvantage for this case.

Voluntary waiting is restricted in v1. Require all of:

- Partner is on turn and EVERY legal partner move captures a piece that enables
  the needed legal local block or an immediate winning drop. Enumerate the moves;
  a good PV is not proof of a forced delivery. Verify the resulting joint states.
- No currently legal local move already wins the actual game immediately.
- Partner does not lose in the proposed continuation; a bounded tactical safety
  check finds no immediate opposing team win. Incomplete checks disallow sitting.
- Full clocks are supplied and TimeAdvantage is true. Our clock exceeds a 3000 ms
  wait plus 1000 ms reserve, and exceeds the opposing seat's clock on the partner
  board by that same 4000 ms margin. This is a conservative policy, not an exact
  solution to four-clock timing.

Allow at most one voluntary 3000 ms wait per own-board turn. Add an opt-in output
`info string hb_wake_after_ms=3000`; the seat adapter exposes it as a virtual wake
deadline. The arena wakes at the earliest of that deadline, its existing reaction
event, or an advantage flip. Keep the original expiry through intervening wakes;
do not renew indefinitely. At expiry play the legal fallback if one exists.
Mandatory waiting can continue if no legal move exists. No real-time sleep and no
new waiting policy for FSF or HiveMind. Test the timer with no other-board events.

## 6. Isolation and safeguards

- Hypothetical material never enters authoritative game state. Each probe owns
  valid Position/StateInfo storage; never shallow-copy pointer-linked state.
- Rebuilding probes from validated FEN is acceptable. Its missing pre-root
  repetition history is an explicit approximation used consistently for paired
  probes. Actual referee history remains intact outside those probes.
- Refresh NNUE state after pocket changes. Compare incremental and fresh evaluation
  through drops, captures, promotions, and undo. Check keys and pockets restore.
- Initially clear TT and search heuristics between distinct child searches. A
  sequential reusable worker is sufficient. Include clearing overhead in budgets.
  Do not share bounds between different hands, contexts, or modes.
- Never store combined S scores in the alpha-beta TT; they are root heuristics.
- Fixed-node determinism requires identical build/net/options, full game and wait
  state, and clean search state. Timed search is not necessarily reproduced by
  replaying the observed node count. Log each child request/result for diagnosis.
- Retain upstream bench behavior with HypeBeast off. Also test bughouse positions;
  a standard chess bench alone does not verify variant-specific hooks.

## 7. Required opponents and controls

### A. Unmodified Fairy-Stockfish bughouse

Build the untouched upstream source. Use UCI_Variant=bughouse, the pinned bughouse
NNUE, normal virtual drops, and upstream search/evaluation without HypeBeast patches.

Add a plain-FSF arena Player that launches its normal UCI binary without HiveMind's
--model argument. Send the seat's actual FEN including transferred pockets and
counters via normal `position fen`, then `go`. Parse ordinary `bestmove`, not a
joint response. If the referee says play continues but the seat has no legal move,
return a sit as necessary protocol plumbing. Unexpected null/illegal output with
legal moves available is a failure, not an invitation to invent a replacement.

Label it **unmodified FSF bughouse via UCI snapshot adapter**. It receives actual
hands but no pre-root repetition history or CECP partner messages. Disclose these
limitations; this is not a measurement of every native CECP team-play feature.
Do not change the binary or add a custom advisor to strengthen/weaken this control.
A native CECP comparison can be a later experiment.

### B. HypeBeast coordination off

Same HypeBeast binary, net, actual-state handling, and frozen-hand local search,
but Coordination=false: no partner analysis, simulated hands, delivery re-ranking,
or voluntary waiting. Give the main search the full budget. This ablation tests
whether coordination earns its computation; a win against A alone cannot show that.

### C. HiveMind CPU

Use the installed arena opponent and model unchanged. Preserve its existing
ponder/permanent-brain disabling and stop-after-bestmove compatibility behavior.
Use concurrency 1 initially to avoid CPU backend oversubscription.

Generalize engine specs to explicit fsf/hypebeast/hivemind player kinds while
preserving existing CLI compatibility. Model/runtime-library arguments apply only
to engines needing them. Record all binary/model/net hashes and settings.

## 8. Verification and matches

Before measured games, automate real-binary checks for:

- Default upstream bench and bughouse fixed-node agreement with HypeBeast off;
  active NNUE loading and identical static NNUE scores on identical real positions.
- Both-board replay against the referee: all seats, promotions, en passant,
  transfers, drops, counters, and repetition. Randomized make/undo restoration.
- Root terminal/wait fixtures: blockable/unblockable/double checks, pawn blocks on
  back ranks, no moves on both boards, clock advantage changes, and draw cases.
- Delivery outside the local top three; enemy arrival threats; unavailable friendly
  supply; exclusive donor outcomes; correct score perspective and unchanged turn.
- Probes leave actual state untouched; cancellation, stale output, budget exhaustion,
  incomplete scores, and fixed-node determinism. Always return a legal fallback.
- Voluntary wait expiry, repeated wakeups, missing supply, low clocks, and mandatory
  waiting. An ordinary upstream-versus-upstream adapter symmetry smoke test.

Use the existing virtual timing initially: 120 s per seat, seeded 1.5–2.5 s move
cost, 0.5 s reaction cost. Same timing for every arm. Virtual-clock results are
separate from real-time latency claims.

Preflight HiveMind on fixed representative positions at its existing 400-node
budget. If movetime is reliably honored, use the same movetime for all arms.
Otherwise pin that HiveMind node budget and give FSF/HypeBeast its measured mean
preflight latency as TOTAL movetime. Label this matched mean compute, and report
median/p95/total latency and overruns. Do not infer the budget from old NPS figures.
Record hardware, cores, thread counts, hash, backend, and warmup. NPS across these
architectures is not a direct playing-strength comparison.

Use held-out legal openings with real pockets from existing games where available.
Each opening plays twice with teams swapped and matching seeded move costs.
Balance board roles across the set. Pin the opening file/hash before testing;
keep debug/tuning positions separate. Each engine controls both seats of its team.

Run all three comparisons with one frozen HypeBeast configuration:

| Match | Contender | Opponent | Question |
|---|---|---|---|
| 1 | HypeBeast coordination on | Unmodified FSF bughouse (A) | Does it beat upstream? |
| 2 | HypeBeast coordination on | HiveMind CPU (C) | Does it beat the target? |
| 3 | HypeBeast coordination on | HypeBeast coordination off (B) | Does coordination help? |

Start with 20 opening pairs per match for screening. After correctness fixes,
freeze again and run a fresh held-out 200 pairs per match for the first strength
report. Complete the declared sample; never stop when results look favorable.
An inconclusive result remains inconclusive. Declare any additional sample before
running it. Test HiveMind GPU separately if a working installation is available;
missing GPU access does not block the required CPU comparisons or count as passed.

Disable the arena's current SPRT stopping rule: although it records pentanomial
counts, its stopping calculation uses total points rather than their distribution.
For these fixed-size runs report W/D/L, score, paired outcome distribution, and a
95% interval treating opening pairs as the sampling unit. Use a tested pair-aware
interval with sensible boundary behavior: identical/all-winning pair scores must
not imply zero uncertainty. Elo is secondary; do not print finite Elo at 0%/100%.

Crashes, timeouts, and illegal moves invalidate a reliability claim. Report them;
do not silently drop those games and promote the remaining score. Preserve old
runs, fix the cause, and start a new frozen run. Infrastructure-error replays need
a documented cause and policy.

Retain JSONL, protocol logs, BPGN, manifests, and representative losses. Report
flags, waiting time, overrides, completed-probe fraction, fallback rate, search
and probe depths, aggregate nodes/latency, and realized versus simulated transfers.
If comparisons seldom finish, say the new architecture was mostly bypassed.

## 9. Implementation order and deliverables for Opus

1. Pin sources/net/opponents; build unchanged FSF and the fork. Add player kinds,
   Seat/Clocks, and baseline smoke tests.
2. Implement joint replay, root rules, frozen-hand search context, isolated child
   state, aggregate budgets, and fallback.
3. Implement candidate discovery, incoming scenarios, the specified probe/score
   rule, and bounded waiting. This is required for the first complete build.
4. Finish fixtures and smoke games, then run all three comparison matches and
   deliver results even if they are negative.

Suggested modules: arena, team_state, coordinator, probe, decisionlog. Combine
files where clearer. Keep upstream hooks narrow without promising they are only
a few lines. Follow each repository's integration/test requirements.

Deliver exact build/match commands, commits, binary/net/model hashes, configuration,
checks, match artifacts, and a concise strength/reliability report with limitations.
Do not describe this plan edit as an implementation or completed match.

Deferred: retraining, partner NNUE inputs, probabilistic arrival trees, longer
forecasts, deep transfer eval terms, general search tuning, custom piece values,
a new mate solver, and native CECP team benchmarking. Select later work from
observed losses rather than a mandatory training phase.

## Later: chance inside the tree (agreed 2026-11-09; implemented in revision 10)

Do this only after the root-level version shows a measured gain over v3.
Revision 10 implements it as virtual drops at search nodes in the first four
plies, mixed in winning chances; it describes what was built and measured.

The root-level version (v4) forecasts arrivals from the partner board's top
lines, searches our board once per arrival package ("world"), and picks the move
with the best probability-weighted result. Its limit: pieces arrive only at the
first move. A piece that would arrive several moves into a line is not modelled.

The later version puts the arrival inside the search:

- At a node where a forecast arrival is due, the search branches on "it arrives"
  and "it does not", and the node's value is the probability-weighted average of
  the two, taken in winning chances, not centipawns.
- The damage or benefit of a piece is never a fixed number. It comes from
  searching with the piece actually in hand, so it shrinks when a line closes
  the weakness and grows when a line opens one.
- Arrivals cost a tempo and are limited to pieces the forecast says can be
  captured on the other board, with the forecast's probability. This is the
  difference from upstream virtual drops, which allow any piece and count a line
  only if it ends in mate.
- Open problems to solve then: averaging breaks plain alpha-beta cutoffs, the
  transposition table must not mix values from different hands, and the cost
  has to be bounded (depth gate, node cap, at most one or two arrivals per line).

## Sources and entry points

- https://github.com/fairy-stockfish/Fairy-Stockfish
- https://fairy-stockfish.github.io/nnue/
- https://github.com/fairy-stockfish/variant-nnue-tools/blob/master/src/tools/training_data_generator.cpp
- https://github.com/aminwoo/hivemind
- https://github.com/fairy-stockfish/fairyfishtest
- ~/Projects/Chess-Auto-Prep/tools/bughouse_arena/{players,sim,referee,match,stats}.py
- ~/Projects/Chess-Auto-Prep/tools/test_bughouse_arena.py

Verify interfaces against the pinned sources; revision 6's line numbers are not
a compatibility contract. This document is the implementation scope.
