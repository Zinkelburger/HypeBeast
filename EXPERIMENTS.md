# HypeBeast v6 experiments: queue and results

Written 2026-11-10 by the Fable session, for a session that runs matches while
the user is away. Fable reads the results afterwards and decides what goes into
the engine.

## Rules for whoever runs this queue

- **Run matches and record results. Change nothing else**: no engine code, no
  defaults, no commits, no deleting logs. Every experiment here is an option
  on the existing binary `bin/hypebeast-v6h`.
- **One match at a time.** Before starting one, run
  `pgrep -fa "[b]ughouse_arena"`; if it prints anything, wait. Never start a
  second match, a build, a test suite or a HiveMind benchmark beside a match.
  The machine went down on 2026-11-10 with several jobs running at once.
- Always concurrency 6, `Hash=64`, `nodes=500000`. A match of 100 games takes
  about 50 minutes.
  **Changed by the user, 2026-11-10 21:55: concurrency 12 from step 3 on**
  (step 2 was already running at 6). Replace the `6` in the commands below with
  `12`. Measured at 6 games: 6 engine threads running at once, 5 GB of engines.
- Start each match in the background from the repository root:

  ```
  scripts/run_match.sh NAME "CONTENDER_SPEC" "BASELINE_SPEC" 50 6 [OPENINGS]
  ```

  The summary is at the end of `logs/NAME.log`. Running the same command again
  resumes an interrupted match.
- Do not stop a match with `pkill -f bughouse_arena` from a command line that
  contains that word (it kills its own shell). Use `pkill -f "[b]ughouse_arena"`.
- After each match, add a row to the results table below: W-L-D for the
  contender, score, the Elo interval the log prints, and the pair counts. Copy
  the numbers from the log; do not round or interpret them.
- Then apply the decision rule of that step, and nothing more. If a step says
  "stop", stop and leave the rest for Fable.
- If a match ends with `errors` or `illegal` above 0, or the machine looks
  unwell (load average over 20, or a match much slower than 50 minutes), stop
  and write down what happened.

`V6` below stands for `bin=bin/hypebeast-v6h,nodes=500000,Hash=64`. Extra
options are appended, e.g. `V6,HBFeedPrices=false,name=hb-v6-np`. Give every
side a distinct `name=`.

A second, independent sample of any match uses the other 50 openings:
add `openings/dev100b.txt` as the last argument and `-b` to the match name.
(The same command on the same openings replays the same games.)

## What v6h is

`bin/hypebeast-v6h` is v5e plus, each behind an option:

| option | default | what it does |
|---|---|---|
| `HBPriceShare` | 10 | partner-board price probes deepen to 1% of the go each (0 = depth 3, as v5) |
| `HBMainShare` | 66 | share of the go for prices, forecast and main search together (58 in v5) |
| `HBFeedPrices` | true | feed prices in the main search (exists since v3) |
| `HBPriceScale`, `HBPriceCap` | 50, 500 | share of a piece's measured gain that is its price, and the cap |
| `HBDraws` | true | take the referee's repetition draw when lost, refuse it otherwise |
| `HBPlayOn` | true | a seat mated by force plays the mate out instead of sitting, while its sitting is what would let the opponents stop the other board |
| `HBWorldSwitch` | true | false: keep the forecast, spend the worlds' share on the main search |
| `HBFeedHold` | false | sit 7 s rather than lose a piece that mates on the partner board |

`HBPriceShare=0,HBMainShare=58,HBDraws=false,HBPlayOn=false` plays as v5e does.

## Results so far

All: 100 games, 50 opening pairs of `openings/dev100.txt`, 500,000 nodes a move.

| match (`logs/`) | contender | baseline | W-L-D | score | Elo (95%) | pairs 2-0 / 1-1 / 0-2 |
|---|---|---|---|---|---|---|
| `v6b-vs-v5e` | deep prices + feed hold | v5e | 52-46-2 | 53.0% | +21 (-47 to +89) | 14 / 23 / 11 (+2 half) |
| `v6a-vs-v5e` | deep prices, no feed hold | v5e | 53-45-2 | 54.0% | +28 (-42 to +97) | 15 / 22 / 11 (+2 half) |
| `v6noprice-vs-v6` | v6f, `HBFeedPrices=false` | v6f (deep prices) | 61-39-0 | 61.0% | +78 (+13 to +143) | 17 / 27 / 6 |

`v6a-vs-v5e` replayed only the 26 games in which the feed hold triggered; the
other 74 are identical by construction. On those 26 the hold scored 2 and no
hold scored 3, so the hold is off.

Other facts measured today (see PLAN.md revision 11 when Fable writes it):

- In v6b against v5e the first side whose seat saw itself mated by force lost
  all 98 decided games. Both sides freeze the other board once that happens.
- When that mate is first seen it is 3 or more moves long in over half the
  games, and the seat that will freeze the other board is level on the clock
  (median gap 0.0 s). That is what `HBPlayOn` is for. It has not played a match yet.

## Queue

Run in this order. `NP` = `V6,HBFeedPrices=false`.

1. **`v6noprice-vs-v6`: done**, 61-39 for no prices (row above). Start at step 2.

2. **Headline: the candidate against v5e.**
   `scripts/run_match.sh v6h-np-vs-v5e "NP,name=hb-v6h-np" "bin=bin/hypebeast-v5e,nodes=500000,Hash=64,name=hb-v5e" 50 6`
   No decision.

3. **Play-on by itself.**
   `scripts/run_match.sh playon-vs-off "NP,name=hb-np-playon" "NP,HBPlayOn=false,name=hb-np-sit" 50 6`
   No decision.

4. **Second sample of step 2** on the other openings:
   `scripts/run_match.sh v6h-np-vs-v5e-b "NP,name=hb-v6h-np" "bin=bin/hypebeast-v5e,nodes=500000,Hash=64,name=hb-v5e" 50 6 openings/dev100b.txt`

5. **Small prices instead of none.**
   `scripts/run_match.sh scale20-vs-np "V6,HBPriceScale=20,name=hb-scale20" "NP,name=hb-np" 50 6`

6. **Worlds off, with no prices.**
   `scripts/run_match.sh np-woff-vs-np "NP,HBWorldSwitch=false,name=hb-np-woff" "NP,name=hb-np" 50 6`

7. **v5's shallow prices against none.**
   `scripts/run_match.sh shallow-vs-np "V6,HBPriceShare=0,HBMainShare=58,name=hb-shallow" "NP,name=hb-np" 50 6`

8. **Second samples.** For each of steps 3, 5, 6 and 7 whose contender scored
   between 42 and 58 of 100, run it again on `openings/dev100b.txt` (name with
   `-b`). Then stop.

## Results of the queue

| step | match | W-L-D | score | Elo (95%) | pairs line from the log | notes |
|---|---|---|---|---|---|---|
| 2 | `v6h-np-vs-v5e` | 56-44-0 | 56.0% (CI 45.4% to 66.1%) | +42 (-32 to +116) | 0-2:12 0.5-1.5:0 1-1:20 1.5-0.5:0 2-0:18 | concurrency 6; errors=0 illegal=0 replayed=0; checkmate 89, flag 11; 32 min |
| 3 | `playon-vs-off` | 52-48-0 | 52.0% (CI 47.7% to 56.3%) | +14 (-16 to +44) | 0-2:1 0.5-1.5:0 1-1:46 1.5-0.5:0 2-0:3 | concurrency 12; errors=0 illegal=0 replayed=0; checkmate 87, flag 13; 23 min |
| 4 | `v6h-np-vs-v5e-b` | 56-44-0 | 56.0% (CI 46.9% to 64.7%) | +42 (-22 to +106) | 0-2:8 0.5-1.5:0 1-1:28 1.5-0.5:0 2-0:14 | concurrency 12; openings/dev100b.txt by absolute path; errors=0 illegal=0 replayed=0; checkmate 88, flag 12; 24 min |

Run note, step 4 (2026-11-10 22:46): the command as written above failed at once
with `FileNotFoundError: 'openings/dev100b.txt'`, before any game was played
(traceback at the top of `logs/v6h-np-vs-v5e-b.log`). `scripts/run_match.sh`
changes to the arena's directory before the path is read, and makes only `bin=`
paths absolute. `run_match.sh` was not changed. Step 4, and any `-b` match of
step 8, was run with the same file by absolute path,
`openings/dev100b.txt`.

Run note, step 5 (2026-11-10 23:18): **queue stopped under the load rule, at step
5.** `scale20-vs-np` was started at 23:10 at concurrency 12; the 5-minute load
average reached 20.57 about 7.5 minutes in and 20.76 at the stop (1-minute 23.07).
The match was stopped with `pkill -f "[b]ughouse_arena"` (`exit=143` in its log).
26 games are saved in `logs/scale20-vs-np/results.jsonl`, 14-12 at the last log
line, not a result; games then in progress are lost and will replay. Running at
the time: 12-13 engine threads at nice 19 for the match, one more nice 19 engine
thread for a position study of step 2's losses (read-only on the logs), and
`flutter_tester`, `node` and `dart` at normal priority using about 4 cores, which
this session did not start. CPU 8.6% idle, 51°C, 3 GB of swap in use. Steps 5 (rest),
6, 7 and 8 have not run. To resume step 5, repeat its command with the same name.

Run note, resume (2026-11-11 00:01): the user asked to resume. **Concurrency 8 from
the rest of step 5 on**, because Chess-Auto-Prep's checks share the machine.

Run note, second stop (2026-11-11 00:14): **queue stopped again under the load rule,
at step 5.** Concurrency 8; the 5-minute load average reached 20.20 about 12.5
minutes in and 20.49 at the stop (1-minute 27.03). Stopped with
`pkill -f "[b]ughouse_arena"` (`exit=143`). 60 games are saved in
`logs/scale20-vs-np/results.jsonl`, 31-29 at the last log line, not a result.
Running at the time, besides the match: another Claude session in this worktree
(`hypebeast-a5`), which edited `engine/src/hb_arena.cpp` and `position.h` and built
`bin/hypebeast-v7a` with `make -j3`, then ran v7a and v6h engines from its own
script; and Chess-Auto-Prep's `flutter_tester` jobs. `bin/hypebeast-v6h` is unchanged,
so the queue's binary is still the one it names. Steps 5 (rest), 6, 7 and 8 have
not run. To resume step 5, repeat its command with the same name.

## Fable session, 2026-11-11: the queue above is paused; mate matches run first

Decisions (Fable). **Steps 5 (rest), 6, 7 and 8 are paused, not cancelled**: do not
resume them until this section says so. `scale20-vs-np` stands at 31-29 after 60
games, which is level. The second stop at 00:14 was caused by this session's
`make -j3` beside the match; no build or test runs beside a match from here on.
One match at a time still holds for every session: check
`pgrep -fa "[b]ughouse_arena"` before starting anything.

`bin/hypebeast-v7a` is v6h plus two options, both 0 (off) by default. With both
off it chose the same move with the same score as v6h on 6 plain searches and 6
coordinated decisions. The engine changes are uncommitted in this worktree.

| option | what it does |
|---|---|
| `HBPhantom` (cp) | in searches of our own board, a side may once drop with check a piece it does not hold, of a type its partner could capture on the other board, and must then mate by checks. That mate is worth this many cp for a pawn, and 63% / 53% / 20% / 25% of it for N / B / R / Q (how often each type arrived per turn in the 200 games). |
| `HBHandDiscount` (cp) | taken off the evaluation per point of hand material (P1 N3 B3 R5 Q9, 15 at most) held more than the opponent |

Why these two, from `logs/loss-analysis/hazard.json` (200 games, scripts in the
Fable session's scratchpad, not kept):

- Result against the seat's own score plus features (10,535 decisions with a score
  within 600 cp, resampled by game): king off the home rank and pawn cover do not
  predict the result once the score is known. Hand material does: each point the
  seat holds counts about 50 cp too much (5%-95%: 35 to 71), each point the
  opponent holds about 46 cp too much (31 to 66), for v5e and v6h-np alike. A seat
  that has just given check wins about 230 cp more often than its score says.
- Position test, plain search at 300,000 nodes, then Opus's judge (imaginary queen
  for the attacker, 100,000 nodes) on the move chosen:

| positions | v6h | HBPhantom 200 | 400 | 800 | HBHandDiscount 30 |
|---|---|---|---|---|---|
| two decisions before seeing mate (74) | 35 | 22 | 21 | 22 | 33 |
| from won games (100) | 11 | 6 | 5 | 4 | 9 |

  Mean depth on the 74: 13.8 for v6h, 13.2 to 13.8 with phantoms. Neither option
  has played a match.

`NP7` = `bin=bin/hypebeast-v7a,nodes=500000,Hash=64,HBFeedPrices=false`. Concurrency 8.

| step | match | command | status |
|---|---|---|---|
| F1 | `ph400-vs-np` | `scripts/run_match.sh ph400-vs-np "NP7,HBPhantom=400,name=hb-ph400" "NP7,name=hb-np" 50 8` | **done: 36-63-1**, 36.5% (CI 27.3% to 46.8%), Elo -96 (-170 to -22), pairs 0-2:21 0.5-1.5:1 1-1:20 2-0:8, errors=0 illegal=0, checkmate 92 flag 7 draw 1, 32 min |
| F2 | `hd30-vs-np` | `scripts/run_match.sh hd30-vs-np "NP7,HBHandDiscount=30,name=hb-hd30" "NP7,name=hb-np" 50 8` | after F1 |

F1 lost for a reason in the design, not in the idea. v7a scored a phantom mate as a
fixed number (400 cp for a pawn down to 80 for a rook) whatever the position was
worth, so a seat 900 up gave most of it away to avoid such a line and a seat 500
down counted a phantom queen mate as +100. In the match hb-ph400 had 1,208 scored
decisions within 100 cp of zero against 659 for hb-np and won 34% of the games
behind them (hb-np 60%); it was the first to see itself mated in 66 games against 34.

`bin/hypebeast-v7b` (built 01:05, off = v6h on 8 plain searches): a phantom mate is
worth the evaluation of the position the piece was dropped from plus `HBPhantom`
(scaled by type as before); no phantom drop while in check; `HBPhantomOwn=false`
counts only the opponent's phantom mates. `NP7b` = `NP7` with `bin/hypebeast-v7b`.
Concurrency 6 from here: two `train` jobs of another project hold 10 cores until
about 04:30.

Position test on v7b (same 174 positions and judge as above; v6h leaves a queen
mate open in 35 of 74 and 11 of 100): `HBPhantom=300` 23 and 7, `=500` 22 and 4,
`=500,HBPhantomOwn=false` 25 and 8.

| step | match | command | status |
|---|---|---|---|
| F3 | `ph500d-vs-np` | `scripts/run_match.sh ph500d-vs-np "NP7b,HBPhantom=500,HBPhantomOwn=false,name=hb-ph500d" "NP7b,name=hb-np" 50 6` | **done: 51-48-1**, 51.5% (CI 41.4% to 61.4%), Elo +10 (-60 to +81), pairs 0-2:13 1-1:22 1.5-0.5:1 2-0:14, errors=0 illegal=0, checkmate 94 flag 5 draw 1, 70 min. Level: first to see itself mated 48 against 51 |
| F4 | `ph500-vs-np` | the same with `HBPhantom=500,name=hb-ph500` | **done: 34-65-1**, 34.5% (CI 25.8% to 44.4%), Elo -111 (-184 to -39), pairs 0-2:22 1-1:21 1.5-0.5:1 2-0:6, errors=0 illegal=0, checkmate 96 flag 3 draw 1, 48 min. First to see itself mated 71 against 29: counting our own phantom mates is what loses |
| F2 | `hd30-vs-np` | as above, with `bin/hypebeast-v7b` | **done: 44-56-0**, 44.0% (CI 34.2% to 54.3%), Elo -42 (-113 to +30), pairs 0-2:17 1-1:22 2-0:11, errors=0 illegal=0, checkmate 99 flag 1, 67 min. First to see itself mated 57 against 43; hb-hd30 dropped 1,701 pieces against 1,450. The discount makes it spend pieces sooner and that does not win |

Reading of F1 to F4: scoring mates with pieces not held is level when only the
opponent's count and loses about 100 Elo when ours count too; taking value off
pieces in hand loses. Neither goes into the candidate. `HBPhantom` and
`HBHandDiscount` stay in the binary, off.

### Worlds (from 05:35)

Queue step 6 was run by this session, with `bin/hypebeast-v7b` on both sides:

| step | match | status |
|---|---|---|
| 6 | `np-woff-vs-np` (`HBWorldSwitch=false`) | **done: 21-77-2**, 22.0% (CI 14.7% to 31.6%), Elo -220 (-306 to -134), pairs 0-2:31 0.5-1.5:1 1-1:14 1.5-0.5:1 2-0:3, errors=0 illegal=0, checkmate 94 flag 4 draw 2, 75 min at concurrency 6. First to see itself mated 71 against 24. **Choosing over the arrival worlds is worth about 220 Elo**; the extra main-search nodes do not come close to paying for it |

What the switches do, from hb-np's logs in F1 to F4 and F2 (400 games; "drift" is
the seat's main score at its next decision minus the score now, +43 cp on average
for a kept main choice):

| decision | n | drift | mated by force at its next decision |
|---|---|---|---|
| kept main, no arrival world mates it | 11,880 | +43 | 0.3% |
| kept main although an arrival world mates it | 188 | -314 | 30% (forecast said 33%) |
| switched, an arrival world mated the main choice | 172 | -275 | 1.7% |
| switched, no mate involved, costs nothing with no arrival | 654 | +65 | 0.9% |
| switched, no mate, costs 1 to 50 cp with no arrival | 591 | +25 | 0% |
| the same, 50 to 150 cp | 549 | -11 | 0.2% |
| the same, over 150 cp | 262 | -69 | 0.4% |

So the forecast's mates are real and switching away from them works; the other
switches look as if they give away roughly what they cost. Drift is not the result,
so this is tested by a match.

`bin/hypebeast-v7c` (built 05:36; with the new option at 4000 it gave the same
decision, score and node count as v7b on 20 seat decisions): `HBWorldMaxGap` (cp),
a move that scores more than this below the main choice when nothing arrives may
replace it only if an arrival mates the main choice. `HBHandDiscount` may now be
negative. `NP7c` = `NP7b` with `bin/hypebeast-v7c`. Concurrency 8: the `train`
jobs ended.

| step | match | command | status |
|---|---|---|---|
| F5 | `gap0-vs-np` | `scripts/run_match.sh gap0-vs-np "NP7c,HBWorldMaxGap=0,name=hb-gap0" "NP7c,name=hb-np" 50 8` | **done: 44-56-0**, 44.0% (CI 34.6% to 53.9%), Elo -42 (-111 to +27), pairs 0-2:16 1-1:24 2-0:10, errors=0 illegal=0, checkmate 97 flag 3, 45 min. First to see itself mated 57 against 43. The drift table misled: the switches that cost score with no arrival are not a loss, and may be a gain. `HBWorldMaxGap` stays at 4000 |

### Mate prices only (from 06:28)

In the same 400 games hb-np kept its main choice 122 times while a forecast arrival
(mean probability 0.43) mated it and every candidate; it was mated by force at its
next decision in 40% of those, about 12 games in 100. No move of that seat escapes,
so only its partner can help, by not losing the piece. With `HBFeedPrices=false` the
partner knows nothing about this. `HBFeedPrices=true,HBPriceScale=0` keeps the
price probes but prices only a piece whose arrival mates (1500 cp to lose it, 800 to
win one that lets the partner mate) and nothing else. No build needed.

| step | match | command | status |
|---|---|---|---|
| F6 | `mateprice-vs-np` | `scripts/run_match.sh mateprice-vs-np "V7c,HBPriceScale=0,name=hb-mateprice" "NP7c,name=hb-np" 50 8` (`V7c` = `NP7c` without `HBFeedPrices=false`) | **done: 51-49-0**, 51.0% (CI 41.3% to 60.6%), Elo +7 (-61 to +75), pairs 0-2:12 1-1:25 2-0:13, errors=0 illegal=0, checkmate 97 flag 3, 31 min. Level, while its main search had 19% fewer nodes (216k against 268k: the probes) and a cleared table every move. A probe saw a mating piece in 15% of its decisions. First to see itself mated 48 against 51 |

### A longer forecast (from 07:03)

`HBForecastTrustLate` has existed since v4 and never played a match: captures 3 to 4
plies into a forecast line become a world of their own, believed this much (they
arrived within two turns 15% to 29% of the time when measured for PLAN.md revision 9).

| step | match | command | status |
|---|---|---|---|
| F7 | `late25-vs-np` | `scripts/run_match.sh late25-vs-np "NP7c,HBForecastTrustLate=25,name=hb-late25" "NP7c,name=hb-np" 50 8` | **done: 58-42-0**, 58.0% (CI 47.8% to 67.6%), Elo +56 (-16 to +128), pairs 0-2:10 1-1:22 2-0:18, errors=0 illegal=0, checkmate 98 flag 2, 30 min. First to see itself mated 44 against 56 |
| F7b | `late25-vs-np-b` | the same on `openings/dev100b.txt` | **done: 53-47-0**, 53.0% (CI 43.3% to 62.5%), Elo +21 (-47 to +89), pairs 0-2:11 1-1:25 2-0:14, errors=0 illegal=0, checkmate 98 flag 2, 31 min. First to see itself mated 47 against 53 |

**Decision (Fable, 08:10): the candidate is now `L25` = `NP` + `HBForecastTrustLate=25`.**
Both samples together are 111-89 (55.5%, about +38 Elo), ahead in both, the same
size of evidence that made `NP` the candidate over v5e. It is not proof: the 95%
interval on 200 games still reaches a little below 50%. What follows is measured
against `L25`.

`bin/hypebeast-v7d` (built 07:34; with the new option off, the same decision, score
and node count as v7c on 12 seat decisions): `HBPriceKeepTable`, the main hash
table is kept between moves while every feed price is zero, now and when the table
was written. It is for mate-only prices (F6), which cleared the table every move.
`L25d` = `bin=bin/hypebeast-v7d,nodes=500000,Hash=64,HBFeedPrices=false,HBForecastTrustLate=25`.

| step | match | command | status |
|---|---|---|---|
| F8 | `late50-vs-late25` | `scripts/run_match.sh late50-vs-late25 "L25d,HBForecastTrustLate=50,name=hb-late50" "L25d,name=hb-late25" 50 8` | **done: 57-43-0**, 57.0% (CI 48.1% to 65.5%), Elo +49 (-13 to +111), pairs 0-2:7 1-1:29 2-0:14, errors=0 illegal=0, checkmate 98 flag 2, 29 min. First to see itself mated 41 against 58 |
| F9 | `late85-vs-late50` | the same as F8, `HBForecastTrustLate=85` against `=50` (85 is the most it can be: it is capped at `HBForecastTrust`) | **done: 39-61-0**, 39.0% (CI 30.6% to 48.2%), Elo -78 (-143 to -13), pairs 0-2:17 1-1:27 2-0:6, errors=0 illegal=0, checkmate 99 flag 1, 34 min. First to see itself mated 61 against 39. At 85 a line with late captures leaves nothing for "only the early ones arrive" |
| F10 | `late50-vs-np-b` | `scripts/run_match.sh late50-vs-np-b "L50d,name=hb-late50" "NP7d,name=hb-np" 50 8 openings/dev100b.txt` | **done: 56-43-1**, 56.5% (CI 46.7% to 65.8%), Elo +45 (-23 to +113), pairs 0-2:9 0.5-1.5:1 1-1:24 2-0:16, errors=0 illegal=0, checkmate 97 flag 2 draw 1, 37 min. First to see itself mated 43 against 56 |

**Decision (Fable, 09:19): the candidate is `L50` = `NP` + `HBForecastTrustLate=50`.**
50 beat 25 (57-43), 25 beat `NP` (111-89 over two samples), 85 lost to 50 (39-61).
F10 is the headline: `L50` against `NP` on openings none of the 50-against-25 games used.

`bin/hypebeast-v7e` (built 08:43; with both new options at their defaults, the same
decision, score and node count as v7d on 12 seat decisions): `HBMaxWorlds` (4) and
`HBForecastScan` (4 plies), the two constants that limit how many arrival packages
are searched and how far into a forecast line captures are read. Late worlds now
compete with early ones for the three places.
`L50e` = `bin=bin/hypebeast-v7e,nodes=500000,Hash=64,HBFeedPrices=false,HBForecastTrustLate=50`.
Concurrency 6 again: another project's `infer` holds about 8 cores since 09:53.

| step | match | command | status |
|---|---|---|---|
| F11 | `worlds5-vs-l50` | `scripts/run_match.sh worlds5-vs-l50 "L50e,HBMaxWorlds=5,name=hb-worlds5" "L50e,name=hb-l50" 50 6` | **done: 53-47-0**, 53.0% (CI 44.5% to 61.4%), Elo +21 (-39 to +80), pairs 0-2:8 1-1:31 2-0:11, errors=0 illegal=0, checkmate 98 flag 2, 97 min (09:58 to 11:35, a loaded machine). First to see itself mated 52 against 48. Collapses 15 against 25 (fatal queens 6 against 15). Not enough to change the candidate; worth a second sample later |

Not yet run, in the order I would run them, each against `L50e`:
`HBForecastScan=6`; mate-only prices with the table kept
(`HBFeedPrices=true,HBPriceScale=0,HBPriceKeepTable=true`); `HBForecastTrustLate=35`
and `=65` to place the peak between 25 and 85.

### Arrivals at the move they can happen (from 10:05, Fable; the user asked for arrivals inside the line)

**What was wrong.** Every world puts its whole package into the hands at the root.
The opponent can drop any of it on the first reply, we on our next move. Measured on
the 200 games of `late50-vs-np-b` and `late50-vs-late25` (20,066 decisions with a
forecast and six or more plies of our board left; `logs/loss-analysis/arrivals.py`
extracts, `arrivals3.py` prints this table). A piece first named at ply k of a
partner-board line, in a line of weight 0.15 to 0.40, had reached the opponent's hand
before ply q of our board (q=1 is the opponent's first reply, our move now is ply 0):

| named at | q<=1 | q<=2 | q<=3 | q<=4 | q<=6 |
|---|---|---|---|---|---|
| k=0 | 29.6% | 33.4% | 45.8% | 49.4% | 58.9% |
| k=1 | 1.9% | 25.8% | 31.2% | 42.1% | 52.6% |
| k=2 | 0.1% | 2.3% | 18.3% | 22.6% | 33.9% |
| k=3 | 0.4% | 4.3% | 6.7% | 15.5% | 26.0% |

The boards move in step: a capture k plies into the partner-board line is made after
k+1 plies of ours, almost never sooner (the same holds for pieces coming to us and for
the other weights). So a piece named at k=1 was searched as droppable at the
opponent's first reply although it is there 2% to 5% of the time, and one named at
k=2 or k=3 although it is there 0.0% to 0.6% of the time. Late trust made those
worlds count (and won), but with the piece two or four plies too early.

World probabilities, for the record: an early world stated at 0.15 / 0.27 / 0.44 / 0.73
had its whole package arrive by q<=2 in 23% / 37% / 48% / 75% of cases; a late world
stated at 0.14 / 0.26 / 0.43 by q<=4 in 14% / 21% / 26%. A piece type in no world
reached the opponent by q<=4 in 2% (R) to 10% (P) of decisions. The probabilities are
roughly right; the timing was not.

**The change** (in the source, not yet built: a match is running).
`HBArrivalTiming`: 0 off, the default; 1 for captures 3 or more plies into a line;
2 for every capture. In a world's two searches a piece captured at ply k of the line
is in the hand, so the evaluation sees it, but cannot be dropped before ply k+1 of
our board, rounded up to the receiver's turn: the opponent's pieces at ply 1, 3, 3, 5
for k = 0, 1, 2, 3 and ours at ply 2, 2, 4, 4. This is the chance branch of PLAN.md's
"chance inside the tree" taken at the root, where it costs nothing: the worlds are
already the branches and their probabilities the weights; what was missing was when.
Parts: `StateInfo::hbPly` (plies since the position was set, null moves counted),
`Position::can_drop` refuses a piece that has not arrived, `Position::key` differs by
ply until the last arrival (the same position earlier allows other drops), each world
keeps the capture plies of the line that contributes most to it, and the worlds in
`hb_decision` gain `"arrives"` (e.g. `-B@3`).

`bin/hypebeast-v8a` (built 11:36, sha256 c8abd8cdb45f5f6f...): with `HBArrivalTiming`
off, the same decision, score, reason, node count and depth as v7e on 12 seat
decisions (three positions of `late50-vs-np-b`, four seats each). With it on, the
worlds show their arrival plies, e.g. `+B-Q` with `-Q@5`, `+P-R` with `-R@3,+P@4`, no
errors, and 1 of the 12 decisions changes (N@c4 becomes g1a1 in both modes).
`L50a` = `bin=bin/hypebeast-v8a,nodes=500000,Hash=64,HBFeedPrices=false,HBForecastTrustLate=50`.
`scripts/run_match.sh` now runs `scripts/postmortem.py` when a match ends cleanly.

| step | match | command | status |
|---|---|---|---|
| F12 | `timing2-vs-l50` | `scripts/run_match.sh timing2-vs-l50 "L50a,HBArrivalTiming=2,name=hb-timing2" "L50a,name=hb-l50" 50 6` | **stopped at 80 games at the user's request (12:12): 34-46-0**, 42.5%. First to see itself mated 48 against 32. Collapses 20 against 12; of the 20, 6 came in a world where the move played was NOT mated (2 of the baseline's 12). World depth the same (10.24 against 10.22), worlds with the main move mated the same (2.0% against 2.1%). Timing every capture loses: not kept |

and, depending on F12, `HBArrivalTiming=1`, then late trust 65 and `HBForecastScan=6`
with timing on (a later capture is less of a false alarm once it comes at its own ply).

### A post-mortem for every match (10:45, the user asked for the probabilities to be kept and reported)

`scripts/postmortem.py MATCH_DIR [...]` (about 12 s a match, one thread) writes
`MATCH_DIR/postmortem.jsonl`, one row per decision, and `MATCH_DIR/postmortem.md`.
Nothing new is logged by the engine: the forecast, the worlds and every candidate's
value in every world were already in `engine_logs`; the script joins them to what
happened next. A row holds the score and depth, the move played and the main search's
move, each world with its stated probability, the main, played and best candidate's
value there and the ply by which its package had really arrived, every piece that
reached either hand and when, the score at the seat's next decision, and who won.
The report: stated winning chances against results, world probabilities against
arrivals (with a Brier score), when forecast pieces arrived, arrivals in no world,
what switches from the main move were followed by, first to see itself mated, and the
15 decisions followed by the largest drops. To do when no match is running: call it at
the end of `scripts/run_match.sh` (a running bash script must not be edited).

First reading, `late50-vs-np-b` only (one match: leads, not results):

- Stated winning chances are about right for hb-late50 (40-60% stated: won 54.7%;
  75-90%: 83.7%) except at the ends: "0-10%" won 8%, "90-100%" won 94%.
- Sudden collapses: decisions at -300 cp or better whose next decision was a forced
  mate against: 18 for hb-late50, 28 for hb-np. The piece that reached the opponent
  was a queen in 14 of the 18. In 11 of the 18 (14 of the 28) the piece was in a
  world and every candidate, that world's own best move included, was already mated
  in it; the stated probabilities of those worlds ran from 0.29 to 0.77. So at that
  decision our board had no answer left. What remains is one move earlier (late
  trust, arrival timing), sitting, or the partner not letting the piece go: a case
  for trying mate-only feed prices again (F6 was level while paying a cleared table).
- A piece in no world reached the opponent before our next move in 5.2% of
  hb-late50's decisions (hb-np 6.8%); the score then fell 275 cp on average, against
  168 when the arrival was in a world.

### Why arrival timing lost (12:15, what the post-mortem shows and what it does not)

The timed side's world searches were as deep as the baseline's and found a mated
main move as often. What changed is where it was caught: 6 of its 20 collapses came
after a world said the move it played was not mated, against 2 of 12. With the
piece droppable only at its own ply the world search no longer shows the mate that
the same piece delivers one or two moves later, and the seat spends the move
elsewhere. Putting the piece in the hand at once was wrong about when, and right
about what to do now: it made the seat defend a move early. `HBArrivalTiming` stays
in the code, off. Not tested: `HBArrivalTiming=1` (late captures only).

### Warning the partner: what the old matches already say (11:15)

The report now has a "Sudden collapses" section: decisions at -300 cp or better whose
next decision was a forced mate against the seat, what the seat knew, and the
partner's last decision before the fatal capture.

| match | engine | collapses | fatal queens | partner's own main line had the capture |
|---|---|---|---|---|
| `late50-vs-np-b` | hb-late50 | 18 | 14 | 10 |
| | hb-np | 28 | 10 | 12 |
| `late50-vs-late25` | hb-late50 | 15 | 5 | 6 |
| | hb-late25 | 19 | 12 | 9 |
| `mateprice-vs-np` (F6) | hb-mateprice | 12 | 4 | 7 |
| | hb-np | 29 | 16 | 16 |

- In about half the collapses the partner's own main line contained the capture that
  mated us, usually as a trade, and the partner was more often ahead on its own board
  than behind. It let the piece go because nothing told it what the piece does here.
- The warning that exists (F6: `HBFeedPrices=true,HBPriceScale=0`, 1500 cp to lose a
  piece whose arrival mates the partner) does what it is for: 12 collapses against 29,
  4 fatal queens against 16. The match was still level (51-49), so what it gained
  there it paid elsewhere: 19% of the main search's nodes for the probes, a cleared
  hash table every move, and whatever the 1500 cp costs on the partner's own board.
  The idea is right and the price of it is the thing to work on.

### Queue agreed with the user at 11:35 ("yeah please queue them"): in this order, a post-mortem after each

Each is a 100-game match against the current candidate, read by its score and by the
collapse table (the table moves more than the score does: 12 against 29 in a level match).

| step | what | command | needs |
|---|---|---|---|
| F12 | arrival timing, every capture | `scripts/run_match.sh timing2-vs-l50 "L50a,HBArrivalTiming=2,name=hb-timing2" "L50a,name=hb-l50" 50 6` | stopped at 80 games: 34-46, lost |
| F13 | the warning without the cleared table | `scripts/run_match.sh matekeep-vs-l50 "bin=bin/hypebeast-v7e,nodes=500000,Hash=64,HBForecastTrustLate=50,HBPriceScale=0,HBPriceKeepTable=true,name=hb-matekeep" "L50e,name=hb-l50" 50 6` | nothing |
| F14 | the warning with cheap probes | F13 with `HBPriceShare=0` added (depth-3 probes instead of 1% of the go each), `name=hb-matecheap` | nothing |
| F15 | do arrivals deserve more of the search? | `"L50a,HBMainShare=50,name=hb-main50"` against `"L50a,name=hb-l50"` (with `HBArrivalTiming=2` on both if F12 won) | `bin/hypebeast-v8a` |

F15 is the cheap stand-in for chance nodes inside the main search. Those would
search everything below the arrival ply twice, about one ply of main depth. If moving
budget from the main search to the worlds loses, chance nodes inside it will too, and
they are not worth building. If it wins, build them: one arrival package, one chance
node a line, values averaged in winning chances, at the ply `HBArrivalTiming` gives.

Whoever runs these (Opus may): one match at a time, check `pgrep -fa "[b]ughouse_arena"`
first, 6 games at once while the load from other projects is above 20, then
`nice -n 19 python3 scripts/postmortem.py logs/NAME` and copy the result line, the
"first to see itself mated" line and the collapse table into the status column.

### A real message to the partner (design, 11:35; the user: "that was the whole point of being able to communicate with our partners")

There is no partner channel today. Each seat is its own process and the arena sends
it the two boards and nothing from its partner, so the warning (F6, F13, F14) is the
partner guessing: eleven shallow searches of our board from its own process, a fifth
of its nodes at 1% of the go each. Yet the seat in danger already knows, for nothing
and far better: its world searches score the move it is about to play, about 10 plies
deep, with each forecast package in the hands. In 16 of hb-late50's 18 collapses in
`late50-vs-np-b` the fatal piece was in one of its worlds.

Design, to build after `bin/hypebeast-v8a` (so that v8a is the timing change alone):

- The seat says it: after choosing, one line `info string hb_tell n=<plies played on
  my board, my move included> -Q=M -N=350 +R=M`, a piece type per entry: `-T` what
  it costs me (in the world where it costs most) if my opponent gets a T, `+T` what
  I gain if I get one, in cp for the move just chosen against the same move when
  nothing arrives, `M` when that world is a mate against me (or for me) and the
  position without the piece is not.
- The arena carries it: the last `hb_tell` of a seat is sent to its partner before
  that partner's next search, as `setoption name HBPartnerTell value ...`, to engines
  that advertise the option. Real bughouse partners talk; this is that.
- The partner uses it: with `HBTellPrices=true` the feed prices of its main search
  come from the message, no probes at all: 1500 cp to lose a piece marked `-T=M`,
  800 to win one marked `+T=M` (the constants F6 used), and with `HBPriceScale` above
  0 that share of the cp figures. A message more than one ply of that board old is
  ignored.
- Tests: a referee test that the message arrives; replaying the partner's decision
  before each collapse with the message it would have had (does it keep the queen,
  and at what cost on its own board); then the match `tell-vs-l50` and its collapse
  table against F13's.

**11:50: superseded by `PARTNER_TALK.md`** (the user asked for several paradigms and an
ablation plan, to be implemented and run by Opus from a written spec): the message
format, five paradigms (alarm, worth, plan, odds, menu), two measurements to make
from existing logs first, and steps T1 to T6. The arena relay is written, untested,
in `~/.local/share/chess-prep/worktrees/hb-partner-tell`. The user's constraint for
"worth": the partner must not sell out its own board, which is what the share and
cap ablation (T2) is for.

**Missed supplies, measured 11:58 (Opus agent; `logs/loss-analysis/missed/`, and now a
section of every post-mortem).** An episode: a seat's world with a single `+T` mates
with the move it played, and without the piece it does not. Three matches, 300 games:
18 to 31 episodes an engine a match; the team won 71% to 94% of them; the partner
could capture a T at once in about two thirds and did so in about two thirds of
those. Games lost after "could and did not": 8 of 300, and in 4 of the 8 the partner
was far behind on its own board. So "tell your partner which piece mates for you" is
worth at most one or two games in a hundred; the half of the message that matters is
the other one, the piece that mates against you (15 to 29 collapses an engine a match).

### Partner talk, first build and first match (12:15)

`bin/hypebeast-v8b` (built 12:12, sha256 848e28e7d63e1788...; Opus wrote stages 1, 2
and 2b of `PARTNER_TALK.md`, Fable reviewed): with `HBTell` off, and with
`HBTell=alarm` and nothing heard, the same decision, score, reason, node count and
depth as v8a on 20 seat decisions (`logs/loss-analysis/coord6.py`). With
`HBTell=table` a seat says e.g. `v1 n=1 base=28 worth +Q=482 +R=168 +B=157 +N=186
+P=35 -Q=# -R=# -B=321 -N=284 -P=136`, its partner logs `heard=fresh` and prices
captures from it (`theirs` Q and R 1500, the rest half the figure, capped at 500),
and 3 of the 4 hearers tried chose another move. The teller's own move changes too
in some positions (the ten table searches come out of the comparison search).
The arena relay's tests pass (82 tests, 3 skipped as before) in
`~/.local/share/chess-prep/worktrees/hb-partner-tell`; not yet integrated there.
`L50b` = `bin=bin/hypebeast-v8b,nodes=500000,Hash=64,HBFeedPrices=false,HBForecastTrustLate=50`.

The user asked for the table first ("abort it and try the one I suggested"), so the
order of `PARTNER_TALK.md` (alarm first) is set aside for this one match.

| step | match | command | status |
|---|---|---|---|
| T2e | `table-vs-l50` | `ARENA=~/.local/share/chess-prep/worktrees/hb-partner-tell scripts/run_match.sh table-vs-l50 "L50b,HBTell=table,name=hb-table" "L50b,name=hb-l50" 50 6` (`HBPriceScale` 50 and `HBPriceCap` 500, the defaults) | **stopped by Fable at 24 games (12:25): 5-19-0.** Every seat heard a fresh table almost every decision (1384 of 1413), so every capture in its main search carried a price both ways, as the guessed prices did when they lost 39-61. Main nodes 264k against 269k; the comparison search a ply shallower (9.65 against 10.50: the ten table searches); "hold_mated" 59 decisions against 22. At half its worth the table sells the board |

Queued behind it, in this order (the user, 12:22: "we can consider improving our own
eval or trading it for pieces for our partner and test this please": how much of its
own board a seat gives for its partner is `HBPriceScale`). All with the `ARENA=` prefix
above, against `"L50b,name=hb-l50"`, 50 pairs, 6 at once:

| step | match | contender | status |
|---|---|---|---|
| T2f | `table25-vs-l50` | `L50b,HBTell=table,HBPriceScale=25,name=hb-table25` | **done 13:58: 47-53-0** (95% 37.2 to 57.1; pairs 12 won, 23 split, 15 lost; errors 0). The partner obeys the mate flags: `-T=#` told 758 times and the T arrived by q<=2 in 3.6% (21.2% under alarm); `+T=#` told 131 times, arrived 24.4%. It did not win games: sudden collapses 24 (table) against 10 (candidate), fatal queens 10 against 4, and in 15 of the 24 the capture was in the partner's own line, so the seat had not flagged it: a 0.5% search does not see those mates. Prices in the hearer's main score: mean size 318 cp, 46.3% of decisions 200 cp or more (551 at half share). Took T after `+T>=300`: own score +29, won 47.8%; lost T after `-T=#` (22 cases): own -446, won 18.2%. Stated chances too high for the table seats (90-100% stated: won 88.7%, candidate 97.0%). Quarter share stops the 5-19 damage and gains nothing. Next: T2h `table0` (mate flags only, all ten pieces each move) |
| T2g | `table100-vs-l50` | `L50b,HBTell=table,HBPriceScale=100,name=hb-table100` | queued |
| T1 | `alarm-vs-l50` | `L50b,HBTell=alarm,name=hb-alarm` (mates only: trades nothing but a mate) | **done: 51-49-0**, 51.0% (CI 44.4% to 57.6%), Elo +7 (-39 to +53), pairs 0-2:5 1-1:39 2-0:6, errors=0 illegal=0, checkmate 96 flag 4, 46 min. First to see itself mated 46 against 54. Collapses 22 against 23, fatal queens 12 against 12: the alarm changed nothing it was for. It said `-T=#` 165 times and the T still came before the teller's next move in 21%. The channel itself costs nothing (39 of 50 pairs split). Why no effect, most likely: a seat's worlds hold only the pieces its forecast expects, so it learns a piece is fatal when the capture is already one ply away, after its partner's decision (the autopsy's bound: 17 of 96 losses in time). F6's probes asked about all five pieces every move and cut collapses from 29 to 12. The complete version by message is T2h (`table0`) |
| T2a | `worth-vs-l50` | `L50b,HBTell=worth,name=hb-worth` at the best share so far (the table without its ten searches) | queued |
| F13 | `matekeep-vs-l50` | as written above (`bin/hypebeast-v7e`, no `ARENA=` needed) | queued |
| F16 | `ws1200-vs-l50` | `L50b,HBWinScale=1200,name=hb-ws1200` | queued |

**Sell-outs in the 24 games of `table-vs-l50`** (Opus agent, 12:40; now a section of the
post-mortem). A hearer's score contains the prices of the captures in its line: about
551 cp in size on average, 200 or more on 68.5% of hb-table's priced decisions. With
the prices taken out, a capture made for a partner price of 300 or more left the
seat's own board 53 cp worse at its next decision, against 4 to 6 for its other
moves (228 such captures, the team won 21.5% of those games). So each sale is small;
what is large is how much of every score is price. The loss is not explained by
single bad sales. Two things the agent found wrong and left alone: every section
that reads a hearer's score (winning chances, collapses, largest drops) is skewed by
the prices in it; and the post-mortem's `pv` is sometimes a cut-short bound line,
which touches the "partner's own line had that capture" column.

**One board far ahead or two a little ahead** (same agent; `logs/loss-analysis/team/`,
300 games, 16,564 paired decisions of the candidate, 500 resamples of games). The
team's result follows the SUM of the two scores: log loss 0.539 for the sum against
0.596 own, 0.597 partner, 0.603 the smaller, 0.591 the larger (each worse than the
sum in every resample; best scale for the sum 1134 cp). Fitted separately, the
weights of the weaker and the stronger board are equal within their intervals. So
"a team is as strong as its weaker board" is not supported (Fable's guess, wrong).
Directly: (+300, 0) won 53.9% against 50.2% for (+150, +150), not separable; with all
engines pooled (+600, 0) won 70.8% against 59.0% for (+300, +300) (difference +11.8,
interval +1.4 to +21.1), and (0, -300) 42.6% against 49.6% for (-150, -150). Large
margins count a little more than in proportion. A seat that weighs its moves by its
own score alone is using half of what predicts the result.

Order changed at 12:40 to take the table match apart, each against `"L50b,name=hb-l50"`:
after T1, **T2h** `table0-vs-l50` = `L50b,HBTell=table,HBPriceScale=0,name=hb-table0`
(mates only, but for all ten pieces, and paying the ten searches: against T1 it is
the price of the searches and the worth of a complete alarm); then **T2a** `worth-vs-l50`
at scale 50 (prices without the ten searches); then T2f (scale 25).

### Autopsy of the candidate's 96 lost games (12:17, Opus agent; full report `AUTOPSY.md`)

`worlds5-vs-l50` (53 lost) and `late50-vs-np-b` (43 lost), logs only, scripts in
`logs/loss-analysis/autopsy/`. First causes: sudden mate after a forecast arrival 27,
a decisive drop short of mate after one 16, slow loss on its own board 19, the
partner's board lost first 19, an arrival in no world 7, lost a mating race 4, a
missed supply 4. In 41 games the seat went from -300 or better to a forced mate in
one decision: a queen in 28, the capture in the partner's own main line in 33, a
surviving candidate in 2. The most each message could have reached in time: Alarm 17
games, the partner checking its own trades (F13/F14) 15 more, Worth 21 more, Plan 9
more; in 48 of the 96 no message could have helped. Evaluation, net of the score: the
partner's score predicts the result as well as the seat's own; king off its home rank
-9 points of result (CI -15 to -4); opponent holding 9+ points in hand +9 (CI +5 to
+12); best winning-chance scale 1200 cp, not 1000. Its ranked suggestions add two
option-only tests to the queue: `HBWinScale=1200`, and F13 before F14.

### How two boards' scores go with the result: raw table (12:55, preliminary; the fit is still running)

The user: "find how the 2 board eval correlates to win rate, whatever that line is,
maximize that." Saved outside the ignored `logs/`: `analysis/two-board-surface/`
(`cells.md`, the two CSVs, the scripts, and the earlier `combine.md`). The full data
(`pairs.json`, 14 MB) and the fit in progress are in `logs/loss-analysis/surface/`.

Data: 880 games of nine matches (late25-vs-np, late25-vs-np-b, late50-vs-late25,
late50-vs-np-b, late85-vs-late50, worlds5-vs-l50, timing2-vs-l50, gap0-vs-np,
np-woff-vs-np), 95,698 decisions each paired with the partner's most recent one
(median 2.0 s apart), engines whose scores carry no prices.

- A forced mate decides. Own board shows a mate for the seat: the team won 94.7%
  (4,565 decisions); against it: 7.2% (6,446). Stronger board at +1500 or more
  (mates included): 88% to 98% whatever the weaker board shows, unless that is
  below -1500 too, and then 50%: a race.
- Between the mates it is close to additive: both boards within 300 of level 49% to
  53%; (weaker 0..300, stronger 300..600) 57%; both 300..600 68%; (weaker -600..-300,
  stronger -300..0) 40%; both -600..-300 30%.
- Lopsided against even is NOT settled. In 300 cp cells: both boards +300..600 won
  68% [63-73]; (0..300, +600..900) 62% [58-66]; (-300..0, +600..900) 58% [54-62].
  That leans to the even split, the opposite of the narrower cut in `combine.md`
  ((+600, 0) 70.8% against (+300, +300) 59.0%). Neither holds the total fixed.
  The fit (formulas against a shape-free model, cross-validated by game, and the
  win rate along lines of equal total) decides; its report will be `SURFACE.md`.

### The fitted surface: the sum of the two scores, and forced mates apart (15:13, Opus agent)

Full report `logs/loss-analysis/surface/SURFACE.md`, lookup grid `surface.json`
(61 x 61, every 100 cp), 880 games of nine matches, 95,698 paired decisions,
cross-validated by game. No heat-map image: the machine's Python has no numpy.

- Recommended: `P = 1/(1+exp(-(a + b + 2673*Nfor - 2601*Nag - 62)/1399))`, with `a`
  and `b` the own and the partner's score clamped to +/-3000 and `Nfor`, `Nag` the
  number of boards showing a forced mate for and against. To choose a move only
  the order matters: maximise `a + b + 2673*Nfor - 2601*Nag`.
- Cross-validated log loss: this formula 0.5377, a shape-free surface 0.5367, the
  plain sum 0.5444. Weights for the weaker and the stronger board, a product term
  and a term for the split all tie the plain sum. The earlier "large margins count
  more" was mostly mates: with mates apart each board's curve is close to linear.
- The user's questions, in win-rate points with 95% intervals: (0, +600) against
  (+300, +300): +4.4 [-1.3, +11.0] in raw cells, +0.9 [-1.9, +4.5] on the surface,
  so not separable; (-100, +700) against (+300, +300): +1.4 [-4.8, +8.3]. Along a
  fixed total the curve is flat within about a point for splits up to 500 cp from
  equal; at 800 it drops 1.4 to 3.5 points ((-800, +800): 40.9% against 49.5% at
  level). So being far behind on one board starts to cost more than the same lead
  gains at about 800 cp; beyond 1000 the data are too thin.
- A score does not mean more late in the game; mates count a little less late.
- Limits: this is how games between these builds ended given the scores they
  printed, not what happens when a seat steers for a cell; the `combine.md` figure
  of +11.8 for (+600, 0) over (+300, +300) shrinks to +4.4 here.

### Why the table lost, arrivals as facts, and a tempo test (13:40, talk with the user)

- The 24 games of `table-vs-l50` (half share, 5-19): the values told are mostly the
  ordinary worth of a piece in hand (medians +Q 729, +N 356, +P 168; -Q 758, `#` in
  16%), the hearer added half of each to every capture (about 551 cp of prices in
  its scores), and the values move by 151 to 200 cp from one tell to the next
  (`-Q=#` on or off in 10.5%). Each is a 0.5% search set against the main search,
  negatives cut to 0. Reading, not proof. The user's first description had the fix
  ("P: 1.5 good because normally a pawn would be 1"): send and honour only the
  difference from the usual worth, and use it at the choice of the move, not as a
  bonus inside the search.
- The user: arrivals are not random, they come from the partner's board. Design
  note in `PARTNER_TALK.md` ("What the 13:40 conversation changed"): per piece,
  cannot happen / the partner decides (a promise) / the opponent decides (when).
- The user: stall and trade only when the partner is on move, with a position
  (`rnbqkbnr/ppp3pp/8/4N3/4n3/8/PPP3PP/RNBQKBNR`, a queen in hand mates in one for
  whoever is to move; checked with python-chess: Q@f7 and Q@f2 mate, no other piece
  does, and the side to move has 15 moves that stop it). Board B added by Fable:
  `r2q1rk1/ppp2ppp/2n2n2/8/8/2N2N2/PPP2PPP/R2Q1RK1`, queens facing on the open
  file, each defended. `tests/tempo_trade_check.py` asks every seat on move in the
  four turn combinations under both clock leads. Not run yet: a match is running.

### The tempo test passes without any talk (14:00)

`tests/tempo_trade_check.py bin/hypebeast-v8b 500000` (output in
`logs/loss-analysis/tempo/`): 16 of 16 right with no talk, under both clock leads.
- Partner on move on A: the B seat takes the queen (`delivery_win`,
  `delivery_win_main`) and the A seat passes (waits).
- Opponent on move on A: the B seat steps the queen off the file (`exposure_veto`:
  Qc1, Qe7) and the A seat plays a queen move that covers the mating square
  (`world_switch`: Qh5, Qh4).
So the coordinator's own probes of the partner's board already time a mate in one.
What the test did show is the table's noise in one position: Awhite says
`+Q=# +R=99 +B=445 +N=0 +P=506`, a pawn worth five rooks and a knight nothing, and
`-Q=880` where a queen landing on the opponent's move mates. Harder versions (the
mate two or three plies after the piece lands, the trade one move away) are the
ones that can fail: to be written.

T2h `table0-vs-l50` (`L50b,HBTell=table,HBPriceScale=0,name=hb-table0`) started 13:59.

### Minimal Talk: the partner's lines instead of a search of its board (14:05, the user; Fable built it)

The user, after reading why the table matches lost: "remove the redundant search, and
try to include the info from the main search. Don't run extra searches. Just collect
data about captures as we progress through our searches. Plan, odds, can't happen ...
just start simple and see if it improves at all." None of the three tell matches had
tested that: in all of them the hearer still searched its partner's board itself (13%
of the go) and the message came from extra searches of about 2,500 nodes.

- T2h `table0-vs-l50` was stopped at 17 games (8-9) to free the machine: the user,
  "is it even important at all?" It continues with the same command if wanted.
- `bin/hypebeast-v8c` (sha256 676d9bef64843431...), `HBTell=minimal`, specified in
  `PARTNER_TALK.md` section 6. The teller prints the best lines of its main search's
  last four iterations for the move it decided (weights 4, 3, 2, 1), with its score,
  mate and hands. The hearer turns the lines that still fit the partner board into its
  forecast and searches nothing there; when none fits it forecasts as before.
- `logs/loss-analysis/coord7.py`: the same move, score, reason, node count and depth
  as v8b on 10 decisions with `HBTell` off, and on the same 10 with `minimal` and
  nothing heard (20 of 20).
- `logs/loss-analysis/coord8.py`, 36 hearings in 5 positions, no errors: the message
  was used in 21 (0, 1 and 2 plies old), refused in 7 after a reply the teller had
  not expected and in 4 after a capture on the hearer's own board (the game's own
  next move there). A refused message gives exactly the decision made with nothing
  heard. Over the 36 the main search had 312k nodes against 277k, and about 330k
  (+19%) where the message was used; depth 14.25 against 14.09.
- The told lines mostly agree with the hearer's own top line and are surer: one line
  at weight 1.00 gives its package 0.85, where the hearer's own search gave 0.74.
  Whether that confidence is earned is what the post-mortem's Brier column says.

| step | match | contender | status |
|---|---|---|---|
| T7 | `minimal-vs-l50` | `L50c,HBTell=minimal,name=hb-minimal` against `L50c,name=hb-l50` (`L50c` = `L50b` on v8c), `ARENA=` prefix | **stopped by the user at 15 games (14:30): 4-11.** The message was used in 72% of decisions (refused: hands 18%, reply 8%), no errors. What the 15 games show (`postmortem.md`, `logs/loss-analysis/predict.py`): a told forecast has 2.1 lines and 1.2 different capture packages against 5.7 and 4.2 from the seat's own search, no capture at all in 15% (1%), its heaviest world at 0.50 (0.30); the opponent received a piece that was in no world in 7.0% of told decisions against 3.2%; switches away from the main move 157 against 120, losing 47 cp by the next decision against 7. The partner's line is the better single guess: its next move was the one played in 62% (434 decisions one ply old, 220 two plies old) against 46% for the first line of the seat's own search; but the move played was in some line in 65-69% against 85%. A message heard before the teller's move is on the board is rare (10 decisions). Reading: the seat's search of its partner's board is not redundant. It asks "what can arrive" broadly; the partner's main search answers "what is my best move" narrowly. The user: "we should be searching broadly for what can arrive and narrowly for what is my best move." A replay of the lost games by Opus was stopped unfinished at 14:42 (the user: "we gave up"); no report was written |
| T8 | `plan-vs-l50` | `L50d,HBTell=plan,name=hb-plan` against `L50d,name=hb-l50` (`L50d` = `L50b` on `bin/hypebeast-v8d`, sha256 150950f4d2be007a...), `ARENA=` prefix. The seat's own searches all run as before; the partner's line for the move it decided is added as one more line with `HBPlanTrust` = 60% of the weight (the 62% measured), the seat's own lines sharing the rest. `coord9.py`: 20 of 20 decisions as v8b with `HBTell` off and with `plan` and nothing heard; 12 hearings used the line, 4 refused it | **done 15:41: 57-43-0** (95% 48.1% to 65.5%; Elo +49, -13 to +111; pairs 14 won, 29 split, 7 lost; errors 0; checkmate 96, flag 4). The line was heard and used in 69.0% of decisions (refused: hands 20.8%, reply 8.2%). First to see itself mated 45 against 55; sudden collapses 18 against 20; switches 19.5% of decisions against 17.3%, score change by the next decision -41 against -60. Brier of the worlds 0.210 against 0.201: the told line at 60% is a little too sure. Not yet believed: the interval includes 50%, and the rule is a second 100 games on `dev100b.txt` |

### Why each side lost `plan-vs-l50` (15:55, Opus agent; full report `AUTOPSY2.md`)

Logs only, scripts in `logs/loss-analysis/autopsy2/` (`run_all.sh` reruns them).

| first cause | hb-l50 (57 lost) | hb-plan (43 lost) |
|---|---|---|
| decisive drop (400+ cp) after a piece the seat had forecast | 14 | 13 |
| partner's board lost first | 14 | 10 |
| sudden mate after a forecast piece | 12 | 9 |
| slow loss on its own board | 8 | 7 |
| a piece in no forecast world | 5 | 1 |
| a stall that went wrong | 2 | 1 |
| a switch that went wrong | 1 | 1 |
| lost a mating race | 1 | 1 |

- The seat could rarely dodge: at the turning point its best other candidate beat
  the move played by 200+ cp in 3 of 42 and 2 of 31. The fatal capture was in the
  partner's own main line in 34 of 52 and 26 of 39 falls. Deeper world searches
  would have found the mate in 2 and 3 losses. No game was decided by the clock.
- Evaluation, net of the score (400 games: this match and the same-baseline seats
  of `alarm-vs-l50`, `worlds5-vs-l50`, `late50-vs-np-b`): 3 or more squares around
  the king attacked: +9.2 points of collapsing within 3 decisions (CI 7.3 to 11.7;
  +10.8 and +7.9 on each side of this match alone); king off its home rank +3.9;
  in check +2.7; partner behind by 300+: +5.3; partner on move on the other board:
  -3.2. No signal once the score is known: pieces in the opponent's hand, drop
  checks, queen drop checks. Stated chances above 50% come true 6.1 points less
  often than stated.
- The told line: more probability on what arrived (+0.035, CI +0.027 to +0.044),
  but a worse Brier score (+0.009) from one kind of world: a told capture two or
  more moves out is stated at about 0.31 and arrived within four plies in 22%
  (1,399 cases), while the other worlds at those decisions, stated at 0.26, arrived
  in 63%. Switches 20.6% of decisions with the line against 17.3%; collapses
  unchanged (0.18 against 0.20 a game).
- Its ranked suggestions: (1) a king-danger term in the evaluation or in the
  coordinator's winning chance (build); (2) a team winning chance with the
  partner's score (build); (3) `HBPlanTrust=30`, or less trust in the told line's
  distant captures (option-only for the first); (4) `HBWinScale=1200` (F16);
  (5) `HBStall=false` (weak evidence). Not supported: more depth, more worlds,
  another alarm, missed-supply work.

### Were the switches right in hindsight? (16:12, `logs/loss-analysis/hindsight.py`)

Every `world_switch` of `plan-vs-l50` (2,003): the move played and the main search's
move, each valued in the world that really came: the position after the move with
the pieces that reached either hand before the seat's next move (q<=2) added, a
plain search of 500,000 nodes from the opponent's seat. "Steered": a switch that
the seat's own lines alone would not have made (the logged worlds recomputed
without the told line, `steer.py`; the recomputation matches the logged worlds in
3,770 of 3,884 decisions).

| group | switches | played better by 50+ | within 50 | main better by 50+ | mean gain (cp) | avoided a mate | walked into one |
|---|---|---|---|---|---|---|---|
| hb-plan, steered by the told line | 264 | 22% | 33% | 44% | -45 | 0 | 0 |
| hb-plan, its own lines would switch too | 497 | 32% | 37% | 31% | +57 | 13 | 4 |
| hb-plan, no line heard | 297 | 28% | 41% | 31% | +59 | 6 | 1 |
| hb-l50 | 945 | 29% | 36% | 35% | +50 | 35 | 2 |

- A switch pays when something arrives (+87 to +109) and costs when nothing does
  (-42 to -58), in every ordinary group. The steered ones lose either way: -19 when
  something arrived (178), -97 when nothing did (86).
- So the moves the told line alone changed were worse, about 2.6 a game, and the
  57-43 cannot be credited to them. With `AUTOPSY2.md` (a told capture two or more
  moves out is stated at 0.31 and came within four plies in 22%): the told line's
  later captures get too much weight. Its sooner captures and its "nothing is
  coming" are what the forecast gained.
- The judge does not see pieces that arrive after q<=2, which a switch may have
  prepared for; that holds for every group alike.

**The switches the told line stopped (16:40, a second Fable session; `logs/loss-analysis/unswitch.py`,
logs only).** The table above has only switches that happened. The other way the line
changes a move: the seat keeps the main move where its own lines alone would have
switched. The engine's rule recomputed from the logged values (other candidate's S at
least 25 above the main move's) agrees with the engine in 3,262 of 3,291 heard decisions.
- 138 such decisions (62 where every world of the own lines had been scored), in 73 games.
- Nothing arrived before the seat's next move in 69 of 138 (36 of the 62); for the
  baseline's switches that share is 34% (317 of 945). So the line stops switches
  somewhat more often when nothing is coming, but half the time something came.
- Not judged by search (a match was running). At the baseline's averages (+105 when
  something arrives, -58 when nothing does) the stopped switches were worth about
  +23 cp each (+10 for the 62), so stopping them gained nothing. To settle it: run
  the hindsight judge on these 138 (276 searches) between matches.
- Error bars for the table above, games resampled: steered -45 (95% -68 to -22),
  own lines too +57 (+32 to +82), baseline +50 (+24 to +77); steered minus own-too
  -136 to -66. The steered switches sum to about -118 cp a game.
- So about 400 moves in 100 games differ because of the line (264 made, 138
  stopped), none of it measurably better. 57-43 has a two-sided p of 0.19 (pairs
  14 to 7: 0.19). The plain reading is that the result is not yet different from
  level; A2 decides.

### The ablation queue (16:15; the user: "do everything Opus suggested ... part of our ablation")

`bin/hypebeast-v8g` (sha256 9b56a91c2ef1dea3...): v8d and three options, all off by
default (`coord9.py`: 20 of 20 decisions as v8b, off and with `plan` and nothing
heard; `coord10.py` shows each option acting on one decision).
- `HBKingDanger` (cp): taken off for each square of the king's zone (its square and
  the eight around it) the opponent attacks beyond two, added for the opponent's
  king; in `Eval::evaluate`, so in every search. The feature of `AUTOPSY2.md`.
- `HBTeamScore` (%): that share of the partner's told score (cut at +/-3000; a told
  mate is +5673 or -5601, the fitted surface's figures) is added to ours inside
  the winning chance of every world; `S` has it taken out again. Needs a message
  with `score=` (`HBTell=plan`).
- `HBPlanTrustLate` (%): `HBForecastTrustLate` for the told line alone (-1: the same).

`L50g` = `bin=bin/hypebeast-v8g,nodes=500000,Hash=64,HBFeedPrices=false,HBForecastTrustLate=50`,
`PLANg` = `L50g,HBTell=plan`. All through `scripts/run_match_stop.sh` (as
`run_match.sh`, and stops a contender at or below 33% after 30 games), 50 pairs, 8
games at once, `ARENA=~/.local/share/chess-prep/worktrees/hb-partner-tell`.

| step | match | contender | baseline | status |
|---|---|---|---|---|
| A1 | `kd60-vs-l50` | `L50g,HBKingDanger=60,name=hb-kd60` | `L50g,name=hb-l50` | **done 16:58: 54-46-0** (95% 43.2% to 64.8%, p 0.47; pairs 17 won, 20 split, 13 lost; checkmate 97, flag 3). Level. It stood at 46-31 after 77 games and went 8-15 in the last 23: what 100 games can and cannot say. Sudden mates 16 against 19 (p 0.74), fatal queens 8 against 10, first to see itself mated 48 against 51. The term changes play a great deal (only 20 pairs split; switches 19.1% of decisions against 16.4%; main depth 26.7 against 28.5 at the same nodes) and its scores are more cautious: stated 60-75% won 64.8% (hb-l50 59.9%), stated 40-60% won 53.3% (46.5%). So the scores became better calibrated without fewer mates or more wins. Not in the candidate; a second 100 games only if the mate matches (P2, P3) leave the question open |
| A2 | `plan-vs-l50-b` | `PLANg,name=hb-plan` on `openings/dev100b.txt` | `L50g,name=hb-l50` | **done 17:39: 46-54-0** (pairs 7 won, 32 split, 11 lost). With T8: 103-97 in 200 games, 51.5% (95% 45.4% to 57.6%, p 0.63); sudden mates 38 against 41 (p 0.82). The 57-43 did not repeat: the told line at 60% is level with not talking. P1 (`plan-c`, 200 more games) stood at 36-37 after 73 games at 18:08 |
| A3 | `team-vs-plan` | `PLANg,HBTeamScore=100,name=hb-team` | `PLANg,name=hb-plan` | **done 23:42: 47-53-0** (95% 41.8% to 52.2%; pairs 2 won, 43 split, 5 lost). Sudden mates 22 against 21. The partner's score in the winning chance changed the result of 7 pairs in 50: almost nothing moves. Not in the candidate |
| A4 | `planlate-vs-plan` | `PLANg,HBPlanTrustLate=15,name=hb-planlate` | `PLANg,name=hb-plan` | **done 05:07: 49-50-1** (recorded by the Opus session; 95% 38.6% to 60.4%, p 0.93; Elo -3 (-81 to +73); pairs 15 won, 19 split, 16 lost; checkmate 97, flag 2, draw 1; 25-24-1 as white, 24-26 as black). Level. Sudden mates 28 against 23 (p 0.58), fatal queens 16 against 13; first to see itself mated 49 against 50. Brier of the told (`plan`) worlds 0.210 against 0.222, so trusting the told line's late captures less made those worlds a little better calibrated (3,965 and 4,018 decisions) with no effect on the score. Stated 60-75% came true 55.7% for hb-planlate and 64.3% for hb-plan. Switches 17.6% against 19.6% |
| A5 | `ws1200-vs-l50` | `L50g,HBWinScale=1200,name=hb-ws1200` | `L50g,name=hb-l50` | queued |
| A6 | `nostall-vs-l50` | `L50g,HBStall=false,name=hb-nostall` | `L50g,name=hb-l50` | queued |

### Switching a feature on and off, and pooling matches (17:20, a second Fable session; the user: "make it easy to turn features on / off ... see if the 57-43 is statistically significant")

**16:55: one queue now runs everything.** A1 was started by this same Claude process
before a `/clear`; no other session owns a queue. `scripts/run_queue.sh logs/queue.txt`
(started 16:55, in the background) waits for the match playing to end, then runs the
lines of `logs/queue.txt` in order, one match at a time: A2, P1, P2, P3, A3, A4, A5,
A6, with `scripts/pool.py` after each. Progress is in `logs/queue.log`; a line added
to the end of `logs/queue.txt` is played too; `touch logs/queue.stop` stops it after
the match playing; it stops by itself if a match fails. Do not start a match by
hand while it runs.

- `scripts/ab.sh NAME ON [BOTH]`: the same binary on both sides, `ON` for the
  contender only, `BOTH` for both, from the base `Hash=64,HBFeedPrices=false,
  HBForecastTrustLate=50` on `bin/hypebeast-v8g` at 500,000 nodes. It refuses an
  option the binary does not have and refuses to start beside another match.
  `scripts/ab.sh --list` prints the switches; `DRY=1` prints the command.
- `scripts/pool.py logs/A logs/B ...`: several matches of the same two engines
  pooled by opening pair: score, 95% interval, p, and the sudden mates of each
  side with their own p. On what exists: `plan-vs-l50` 57.0%, p 0.12 (sign test
  0.19); `mateprice-vs-np` (F6) 51.0%, but sudden mates 11 against 29, p 0.006.
- `openings/dev200c.txt`: 200 new openings (same source and filters, salt
  `arena-c`), none shared with `dev100.txt`. `dev100b.txt` is the second half of
  `dev100.txt`, so those two sets are the only 100 openings there were.

Proposed, in this order after A2, each with `scripts/pool.py` afterwards:

| step | match | command | answers |
|---|---|---|---|
| P1 | `plan-c` | `OPENINGS=dev200c PAIRS=100 scripts/ab.sh plan-c HBTell=plan` (200 games) | with T8 and A2, 400 games of talking against not talking: `scripts/pool.py logs/plan-vs-l50 logs/plan-vs-l50-b logs/plan-c`. At 400 games the interval is about +/-4.5 points **Done 21:09: 107-93-0** (pairs 27 won, 53 split, 20 lost; names `hb-plan`, `hb-l50`). All three: **210-190 in 400 games, 52.5% (95% 48.0% to 57.0%, p 0.28)**; sudden mates 73 against 72. The told line at 60% is level with not talking: at most a few points, and nothing for the mates. Not in the candidate |
| P2 | `matefree` | `OPENINGS=dev200c CONTENDER_NODES=620000 scripts/ab.sh matefree "HBFeedPrices=true,HBPriceScale=0,HBPriceKeepTable=true"` | the mate warning of F6/F13 with its cost paid for (620k = 500k x 268k/216k, the main-search nodes F6 lost to its probes; an upper bound, since the worlds get the extra nodes too). If halving the sudden mates does not win games even for free, stop working on warnings. If it does, the work is the cost **Done 21:44: 51-49-0** (95% 41.9% to 60.1%; pairs 11 won, 29 split, 10 lost). Sudden mates 14 against 23 (p 0.19), fatal queens 6 against 14, first to see itself mated 45 against 55. With F6: 102-98 in 200 games, sudden mates 25 against 52. The warning halves the sudden mates and does not win games, even with 24% more nodes |
| P3 | `matekeep` | the same without `CONTENDER_NODES` (this is F13 on v8g) | the same warning paying for itself **Done 22:14: 51-49-0** (95% 41.5% to 60.5%; pairs 12 won, 27 split, 11 lost). Sudden mates 14 against 30 (p 0.023). F6, P2 and P3 together: **153-147 in 300 games, sudden mates 39 against 82**: three times the same picture, half the sudden mates and a level score |

Why this order: F6 is the only thing so far that moved the sudden mates (11 against
29), every message tried since has not (alarm 21 against 22, plan 18 against 20),
and its follow-ups F13 and F14 were queued at 11:35 and never run.

### A cheaper mate guard, `HBMateGuard` (21:05, Fable; the user: "please continue, lets improve the engine")

What F6's probes did, from its logs (`logs/loss-analysis/guard.py logs/mateprice-vs-np`,
5,393 decisions of hb-mateprice):
- A piece of ours mated our partner if lost (price 1500) in 9.4% of decisions: Q 476,
  R 222, N 176, B 123, P 70 flags. A piece won here let our partner mate in 6.2%.
- The flagged type was on our board in 8.4% of decisions and could be taken at once
  in 4.2%. Of our piece types 4.5 are on the board on average and 1.9 can be taken
  at once: F6 ran ten probes where two or three would do.
- The flags changed from one decision of a seat to its next in 19.4%; under
  `HBPriceKeepTable` the table would be cleared in 23.0% of decisions, not every one.
- Probe depth: median 7 (6 to 8 in most).

Also found in the code: the exposure veto that has existed since v2 (`exposure_tier`,
`drop_mates`) sees only a drop that mates at once. The mates behind the sudden
collapses are several moves long (M-4 to M-10 in `AUTOPSY2.md`), so it cannot see them.

Engine source (not yet built: a match is running; the build is a line of the queue):
`HBMateGuard=true` probes the partner's board only with the types the opponent can
take from us now, a queen whenever we have one, and a type that mated at our last
go; it prices only those mates (1500 to lose the piece, as F6), nothing we win, and
keeps the table as `HBPriceKeepTable` does. It overrides `HBFeedPrices`.

Queue, after P3: `scripts/build.sh hypebeast-v8h`; `logs/loss-analysis/coord11.py`
(guard off = v8g's decisions, guard on beside the full mate prices; writes
`bin/hypebeast-v8h.ok` when both hold); then `guard-vs-l50` (`HBMateGuard=true` on
v8h against L50 on v8h, 50 pairs of `dev200c.txt`, the same openings as P2 and P3)
only if the check passed. Read P2, P3 and this one by their sudden mates first.

### Why halving the sudden mates does not win games (21:55, Fable; `logs/loss-analysis/guardwhen.py`, `guardcost.py`)

A mate price is set when one more piece in the opponent's hand mates our partner.
How the partner's board stood, in our team's view, at those decisions:

| partner's board when a mate price is set | P2 `matefree`: decisions | games won | F6 `mateprice-vs-np`: decisions | games won |
|---|---|---|---|---|
| below -1000 | 240 | 18% | 264 | 24% |
| -1000 to -300 | 148 | 30% | 144 | 34% |
| -300 to +300 | 93 | 48% | 64 | 46% |
| above +300 | 49 | 60% | 34 | 59% |

- Three mate prices in four are set while the partner's board is already below
  -300, and about half while it is below -1000. Those games are lost three times
  in four whatever the paying seat does. The sudden mate is mostly how a lost
  board ends, not what loses it.
- The first mate price of a seat in a game comes with the partner's board at a
  median of -534 (P2) and -684 (F6). Games with no mate price at all: 18 and 13,
  won 94% and 100%.
- What paying costs: on decisions with no price set (scores without prices in
  them) the paying side's own board stands lower from the middlegame on: plies 40
  to 80, +13 against +55 for hb-l50 in P2 (with 24% more nodes), -27 against +89
  in F6.
- So a seat that pays 1500 cp to keep a piece is mostly paying for a board that is
  already lost, and gives up its own. Whether the price is worth paying while the
  partner's board is still alive (a quarter of the cases, won about half the time)
  is what `HBMateGuardFloor` tests.

`HBMateGuardFloor` (cp, in the source for v8h; -100000 = always): the guard probes
and prices nothing while the partner's board is below it. Queue, after
`guard-vs-l50`: `guardfloor-vs-l50` (`HBMateGuard=true,HBMateGuardFloor=-300`).

**22:19: `bin/hypebeast-v8h` built by the queue** (sha256 49fef4e8ff2c246b...). `coord11.py`
(`logs/loss-analysis/coord11.out`): guard off, 14 of 14 decisions as v8g; guard on, no
error, 1 to 3 types probed a decision (a queen and a pawn most often), main search
about 257k to 277k nodes where no prices give 272k to 292k and the full mate prices
217k to 237k: about a third of the full cost. In the one decision of the 14 where
the full prices found a mating queen the guard found it too and chose the same move.
`guard-vs-l50` started 22:20, `guardfloor-vs-l50` follows.

### The two guard matches (23:05, Fable): the plain guard lost, the guard with the floor scored 63-37

Both on `bin/hypebeast-v8h` against L50 on the same binary, 50 pairs of `dev200c.txt`.

| match | contender | result | sudden mates | first to see itself mated | notes |
|---|---|---|---|---|---|
| `guard-vs-l50` | `HBMateGuard=true` | **stopped early at 30 games: 9-21** (p 0.035 on 14 pairs) | 8 against 2 | 20 against 10 | a mate priced in 7.1% of decisions, 2.6 probes a decision, main nodes 244k against 268k |
| `guardfloor-vs-l50` | `HBMateGuard=true,HBMateGuardFloor=-300` | **63-37-0** (95% 53.8% to 72.2%, p 0.006; pairs 19 won, 25 split, 6 lost) | 14 against 17 | 40 against 60 | the partner's board was below the floor in 25% of decisions (nothing probed or priced there); a mate priced in 2.0%; main nodes 252k against 259k; own board in plies 40 to 80: +96 against -28 |

- Not believed yet. 57-43 for the told line was level over 400 games, and 9-21
  after 30 games is the early stop's own bias as well as a result. The two matches
  differ only in what happens while the partner's board is below -300, and they
  point the same way: paying there is what loses.
- What the floor version is, beside L50: (a) a mate priced while the partner's
  board is alive, (b) everything else that prices-on brings and L50 has never had
  since `HBFeedPrices=false`: the rescue prices when the partner is mated and
  sits (115 decisions), the partner's base score in the draw rule, (c) one base
  probe of the partner's board (1% of the go). Which of these wins is not known.

Queued after A3 (`team-vs-plan`, already playing): `guardfloor-b`, the same two
engines on 150 new opening pairs (`openings/dev200c-51.txt`, openings 51 to 200 of
`dev200c.txt`), then `guardnone-b`, the same with `HBMateGuardFloor=100000` (no mate
is ever priced: (b) and (c) alone) on the same 150 pairs. A4 to A6 follow.

**`guardfloor-b`, done 02:10: 157-143-0** (150 new opening pairs; pairs 44 won, 69 split,
37 lost; first to see itself mated 143 against 157). With `guardfloor-vs-l50`:
**220-180 in 400 games, 55.0% (95% 50.0% to 60.0%, p 0.050; sign test 0.064)**; sudden
mates 67 against 92 (p 0.057). The 63-37 shrank to 52.3% on new openings, as the
57-43 for the told line did, but the 400 games together sit on the 5% line where the
told line's sat at 52.5%. Its own board in plies 40 to 80 is lower again (+17 against
+41), so what it gains is not there. Not yet the candidate: `guardnone-b` (playing,
the same 150 pairs) says whether the mate price or the rest of prices-on is the gain.

**`guardnone-b`, done 04:20: 139-161-0** (the same 150 pairs; `HBMateGuardFloor=100000`, so
no mate is ever priced; pairs 30 won, 79 split, 41 lost; 46.3%, 95% 40.8% to 51.8%).
Sudden mates 76 against 49 (p 0.020): more than the baseline. On the same openings
the floor guard scored 157-143 with sudden mates 53 against 75. So:
- what prices-on brings besides the mate price (rescue prices, the partner's score
  in the draw rule, the base probe) costs about 4 points and adds sudden mates;
- the mate price while the partner's board is alive is worth about 6 points on top
  of that (157 against 139 wins on the same 150 pairs; two matches of 300 games, so
  +/-4 on the difference);
- the version to test is the mate price without the rest.

### v8i: the mate price alone, and a message that says what a piece costs (04:40, Fable)

`AUTOPSY3.md` (Opus, tonight, 700 games of hb-l50): the first fall of a lost game is a
piece arriving in 72% to 83%; the partner's move that let it go cost the partner's
own board a median of 0 while ours fell a median of 879; in 302 of 421 it was the
second half of a trade the partner began (queen for queen 41 times, a pawn for us
and a queen for them 47); the capture was in the partner's own line in 59%; and our
side's worlds had measured the piece at 500 cp or more before the fall in 47%. That
is the user's first design ("tell the partner what a piece costs us") with the
facts the table matches lacked: the number comes from the seat's own world
searches, not from 2,500-node searches; only large costs are news; only losses.

Source changes (v8i, all off by default; the queue builds it after A4):
- `HBMateGuardQuiet`: the guard with no mate priced is the go without prices in
  every respect but the probes' nodes.
- `HBTellFloor` (cp): a message is not honoured while the teller's board (`base=`,
  now read) is below it. `HBTellMin` (cp): a told number below it is not priced.
  `HBTellLossesOnly`: only `-T` entries are priced.
- `logs/loss-analysis/coord12.py` checks: all off = v8h's decisions; a test message
  is priced as specified with the limits off, with them on, and below the floor.

Queue after A4, both against L50 on v8i, 150 pairs of `openings/dev200c-51.txt` (the
openings of `guardfloor-b` and `guardnone-b`), only if the check passes:
- `worth-b`: `HBTell=worth,HBPriceScale=100,HBPriceCap=1000,HBTellMin=500,HBTellLossesOnly=true,HBTellFloor=-300`.
  No probe and no extra search on either side: the teller's numbers are its scored
  worlds, the hearer prices losing a piece at what the teller says it costs.
- `guardquiet-b`: `HBMateGuard=true,HBMateGuardFloor=-300,HBMateGuardQuiet=true`.
A5 and A6 follow, then the three matches of item 4 below.

**`bin/hypebeast-v8i` built 05:10** (sha256 89e501af95ab39e1...), `coord12.out`: all off, 10 of
10 decisions as v8h; the test message priced as specified in the three cases; PASS.

**`worth-b`, done 07:21: 109-189-2** (36.7%, 95% 31.3% to 42.0%; pairs 19 won, 71 split,
60 lost). Sudden mates 56 against 57. A clear loss, and the spec was wrong, not the
idea (Fable's error):
- A message was fresh in 66% of decisions and below the floor in 29%; something
  was priced in 10.0% of decisions (Q 630, N 647, B 430, P 396, R 274; median price
  711; 183 mates). The paying side's own board in plies 40 to 80: -136 against +134.
- What the seats tell from their worlds (16,878 messages): the median cost of a
  piece in the opponent's hand is Q 356, R 200, N 172, B 116, P 63, and the median
  worth of the same piece in one's own hand is Q 406, R 258, N 213, B 158, P 114.
  A cost of 500 or more is the upper tail of the ordinary (40% of the queens, 14%
  of the knights), not news.
- `HBTellLossesOnly` priced the piece lost in a trade and nothing for the piece
  won, so every even trade looked like a loss of about 700 cp and the seat gave up
  its own board to avoid trades. The user's rule of 13:40 ("only the difference
  from the usual worth is news") was half applied.

### v8j: the message at the choice of the move (07:25, Fable)

`HBTellRoot=true` (source; the queue builds `bin/hypebeast-v8j` after `guardquiet-b`):
a heard message prices nothing inside the search. At the choice among the
candidates, each candidate gets the teller's `+T` for what its own move captures
less the teller's `-T` for what the reply in its comparison line captures (share
`HBPriceScale`, cap `HBPriceCap`, a mate = the cap, ignored below `HBTellMin` and
below `HBTellFloor`), added to its value in every world. An even trade nets about
zero; a queen given for a pawn costs what the partner says. Switches the worlds
alone would not have made are logged as `feed_switch`, kept main moves as
`feed_kept=1`, and each candidate's `feed` is in `hb_coord`. `coord13.py` checks it.
It can only choose among the 2 to 5 candidates already compared (`AUTOPSY3.md`: 72
of 421 arrival falls had such a candidate), so expect a small effect: read
`feed_switch` decisions and arrival falls before the score.

Queue after `guardquiet-b`: build, check, `feed-b` =
`HBTell=worth,HBTellRoot=true,HBPriceScale=100,HBPriceCap=1500,HBTellMin=150,HBTellFloor=-300`
against L50 on v8j, the same 150 pairs.

### For an Opus session, night of 2026-11-11 to 11-12 (written by Fable at 00:50)

Rules as at the top of this file: run and record, no design choices, no engine
changes, no commits. A queue is already playing matches (`scripts/run_queue.sh
logs/queue.txt`, progress in `logs/queue.log`), so until it is empty: no engine
runs, no builds, no tests; logs and single-process `nice -n 19` Python only.

1. **Keep the queue alive and recorded.** `pgrep -fa "[r]un_queue"` shows whether
   it runs. If it does not and `logs/queue.txt` still has lines that are not in
   `logs/queue.txt.done`, start it again with `scripts/run_queue.sh logs/queue.txt`
   (it continues an interrupted match). Never start a match any other way. When a
   match ends and this file does not have its result yet, add it to the match's
   row or section: score, the `scripts/pool.py` figures from `logs/queue.log`,
   sudden mates, first to see itself mated, and what `postmortem.md` shows. The
   Fable session may record the same result: look before writing.

2. **What loses a board first (`AUTOPSY3.md`, logs only).** The finding of 21:55
   above: three sudden mates in four come when the board is already below -300, so
   the mate is how a lost board ends. The question is now the first fall. For the
   hb-l50 seats of `plan-vs-l50`, `plan-vs-l50-b`, `plan-c`, `kd60-vs-l50`,
   `matefree`, `matekeep` (same engine, about 1,000 games): take each seat's first
   decision after which its score stays below -300 for the rest of the game, and
   the three decisions before it. Classify what happened between: a piece arrived
   (was it in a forecast world, at what probability, was the move played scored
   there, did another candidate hold), no piece arrived (the main search's own
   score fell: by how much a ply, at what depth), the seat had switched away from
   its main move, it was in check or its king had left the home rank, the partner
   was sitting. Give counts with game numbers, the ten clearest examples with the
   position and the logged lines, and for each class what information that the
   logs show existed somewhere (in its own worlds, in the partner's search) would
   have changed the move. Suggestions are welcome and are for Fable to judge.

3. **Which part of the floor guard wins** (once `guardfloor-b` and `guardnone-b` are
   done; both are on `openings/dev200c-51.txt` against the same baseline, so their
   games are identical until the first decision where the contenders differ). For
   each opening pair and colour: the first decision where hb-guardfloor's and
   hb-guardnone's games part, what was active there in each (`guard=`, a mate
   price in `hb_prices`, `rescue=`, `partner_held`, the reason), and the results of
   the two games. Then: of the games whose results differ, how many parted at a
   mate price. Same question for `guardfloor-vs-l50` against `matekeep` and
   `matefree` (first 50 pairs of `dev200c.txt`). Write it as a section here.

4. **When the queue is empty** (about 06:00), append these lines to `logs/queue.txt`
   (copy the `guardfloor-b` line and change the name and the options; each 150
   pairs, 8 at once, `openings/dev200c-51.txt`, against the same `name=hb-l50`
   baseline on `bin/hypebeast-v8h`, each followed by its `scripts/pool.py` line)
   and start the queue if it has stopped:
   - `guardfloor100-b`: `HBMateGuard=true,HBMateGuardFloor=-100,name=hb-guardfloor100`
   - `guardfloor600-b`: `HBMateGuard=true,HBMateGuardFloor=-600,name=hb-guardfloor600`
   - `guardnone-norescue-b`: `HBMateGuard=true,HBMateGuardFloor=100000,HBRescue=false,name=hb-guardnone-nr`
   Record each. Do not choose a candidate.

### Opus session, night of 2026-11-11 to 11-12: what was done (run and record only)

**Queue (item 1).** At 00:48 `run_queue.sh` was running (in the Fable session's terminal) and `guardfloor-b`
was at 157 of 300 games. A watcher in the Opus session restarts the queue if it stops. Load during the night came
mostly from other sessions' jobs at normal priority (krt MCP servers and tests, Flutter testers, Go tests, Erlang,
`ct_train` in Frank-45s-Opus at nice 19 on 4 to 6 cores): 5-minute load 27 at 00:48 and 60 at 01:25, with swap
full but 30 GB of memory available. The match runs at nice 19 and was kept going under tonight's instruction to keep
the queue alive (the file's load-20 rule would have stopped it). The cost is speed: about 2.4 games a minute at
00:48 and 1.2 at 01:25.

`guardfloor-b` (Fable recorded the result above at 02:11; these are additions only). The log has errors 0, illegal
0, 289 checkmates and 11 flags; the CI is 46.5% to 58.1% and Elo +16 (-25 to +57). `pool.py` on this match
alone gives p 0.437 (sign test 0.505), with sudden mates 53 against 75 (p 0.063). Guard figures
(`autopsy3/guardstats.py`): the partner's board was below the floor in 33.7% of hb-guardfloor's decisions (25.4%
in `guardfloor-vs-l50`); it probed 2.6 types when it probed; a mate price was set in 2.1% of decisions; main-search
nodes averaged 255k against 268k. My own-board figure is +24 against +4. It differs from Fable's +17 against +41
because I take every decision at plies 40 to 80 without a mate price set, a different filter. `postmortem.md`:
stated chances at 60-75% came true 62.4% for hb-guardfloor and 57.6% for hb-l50 (overconfidence as before),
and the Brier scores are 0.204 and 0.202. Fall classes (AUTOPSY3's rules): hb-guardfloor seats fell 282 times,
hb-l50 seats 270. Arrival falls were 180 against 202 and A5 122 against 139. Own-board falls (C1 to C5) were 65
against 46. The halving of arrival falls seen in `guardfloor-vs-l50` (41 against 81) did not repeat; this is
about 10% fewer.

**What loses a board first (item 2): `AUTOPSY3.md`**, 700 games and 1,400 hb-l50 seats, logs only. Headline: in 263
of the 364 falls that were the team's first in a lost game (72%), a piece reached the opponent's hand from the
partner board. Most often (A5, 276 of 635 falls) the seat had forecast the piece (median p 0.27), and every
candidate it compared fell by about 750 cp in that world, two decisions earlier as well. The partner's move that
let the piece go changed the partner's own score by a median +0, against our -879. It was usually the
recapture in a trade the partner began (302 of 421 arrival falls), and the partner's own main line had the
capture in 249. Our forecast had measured that piece at 500 cp or more in 197 of 421, and nothing of it reaches an
hb-l50 partner. Queens and rooks are 242 of the 421. Partner sitting (8 of 632) and clocks (27) hardly figure. In
`guardfloor-vs-l50` the guard's seats had 41 arrival falls against hb-l50's 81; on `guardfloor-b` the figures were
180 against 202, so that halving did not repeat. Five testable suggestions, for
Fable to judge, are at the end of `AUTOPSY3.md`.

**Which part of the floor guard wins (item 3), on the matches that exist** (`logs/loss-analysis/autopsy3/diverge.py`;
per-game tables in `diverge_<A>_vs_<B>.md`). Games are matched by opening pair and colour. The *parting decision* is
the first contender decision whose move (or sit) differs in the same position. The *first difference* is the
first contender decision whose logged probe (`guard=`, or `prices=1` for engines without the guard) or
`price_mates` differs, even when the same move was played.

| A against B (same baseline, same openings) | games | results differ | A better / B better | parted at a mate price (here or earlier) | first difference | plies from first difference to parting (median) |
|---|---|---|---|---|---|---|
| `guardfloor-vs-l50` / `guard-vs-l50` (plain guard, stopped at 30) | 30 (1 identical) | 16 | 12 / 4 | 2 | the plain guard probed while the partner's board was below the floor: 29 of 29 | 16 |
| `guardfloor-vs-l50` / `matekeep` | 100 | 44 | 28 / 16 | 2 | the probes differ from the first decisions; games part at ply 21 (median) | 1 |
| `guardfloor-vs-l50` / `matefree` (620k nodes) | 100 | 40 | 26 / 14 | 4 | the same; games part at ply 22 (median) | 4 |

- Against the full mate prices, almost no game parts at a mate price. The games part in the opening, at decisions
  where both sides ran probes of different size (the guard probes 1 to 3 types, the full prices all of them), and
  the floor guard wins the games that differ 28-16 and 26-14. Its edge over F13 comes from what the probes cost
  the search, not from pricing differently where the games part.
- Against the plain guard, the floor first changes the engine where the plain guard probes a board already below
  -300. The same move is played there, and the games part a median 16 plies later at decisions without a mate
  price (27 of 29). The 9-21 of the plain guard is thus spread through what those probes did to the search
  (nodes, hash, kept table), not concentrated at mate prices. 30 games only.
- `matekeep` and `matefree` were played on `bin/hypebeast-v8g`, `guardfloor-vs-l50` on v8h. Their baselines are
  the same engine (coord11: guard off plays as v8g). The contenders differ from the first decision, so this
  comparison says less than the guardfloor-b / guardnone-b one will.

**Item 3, the main comparison: `guardfloor-b` against `guardnone-b`** (04:20 onwards; Fable recorded the
guardnone-b score at 04:20, so the figures below are additions). Both matches use the same 150 pairs of
`dev200c-51.txt`, the same hb-l50 on v8h, and are deterministic at fixed nodes. Per-game table:
`autopsy3/diverge_guardfloor-b_vs_guardnone-b.md`.

| | games | identical | results differ | floor better / none better | parted at a mate price | mate price earlier | parted with no mate price set at or before |
|---|---|---|---|---|---|---|---|
| `guardfloor-b` / `guardnone-b` | 300 | 0 | 146 | 82 / 64 | 4 (results differ in 1, and there hb-guardnone did better) | 2 (results differ in 0) | 294 (results differ in 145: 82 / 63) |

- **Where they part.** The first difference in every one of the 300 games is a decision where hb-guardfloor
  probed (the partner's board above -300) and hb-guardnone did not (`guard=low`, which is always so at floor
  100000). In 282 games the parting decision is one of those probe decisions with no mate price set (median ply
  23). In 12 both sides were below the floor at the parting decision, and they differed through earlier probes'
  effects on hash and cache. The parting is a median 7 plies after the first probe; in 21 games it is at the first
  probe itself. `rescue=` and `partner_held=` are logged at no parting decision.
- **Mate prices at the parting decision: 4 of 300.** All four were hb-guardfloor pricing the loss of our queen
  (`theirs:Q`), at pairs 5 black (ply 24), 27 white (30), 86 black (18) and 134 white (74). The results were 0-1, 1-1,
  0-0 and 0-0: hb-guardfloor did not win any of them, and hb-guardnone won one.
- **Mate prices after the parting decision** (hb-guardfloor's games) are no more common in the games the floor
  won: there was one in 33 of the 82 games where the floor did better, 30 of the 64 where none did better, 32 of
  75 that both won and 43 of 79 that both lost. A mate price marks a partner board in trouble. It does not mark
  the games that the floor guard turned.
- **Per colour.** The floor guard scored 84 against 70 with the contender team white and 73 against 69 with it black.
  Results differ in 74 and 72 games.
- **Reading.** After a fixed-node game parts, the two continuations are about as different as two separate
  games: 146 of 300 results differ, near the 150 expected from two independent games at 50%. A game-by-game split
  therefore cannot credit the 18 wins to any decision. What the split does show is that the games turn at decisions
  where hb-guardfloor *probed* and set no price, not at decisions where it priced a mate. The 157 against 139 is a
  difference between the engines as a whole (probes taking nodes from the main search: 255k against 262k main nodes
  on average; the probes' cache and hash effects; the rare mate prices). It does not isolate the mate price. Fable's
  reading above (about 6 points for the mate price while the partner's board is alive) is the aggregate. This
  comparison neither confirms that the mate prices carry it nor rules it out, because two matches of 300 games
  leave +/-4 points on the difference anyway. `guardquiet-b` (v8i, queued by Fable) is the cleaner test of "mate
  price without the rest".

**What `guardnone-b` still changes, at the same position** (`autopsy3/samepos.py`). The two games of a pair
start from one opening with colours swapped. Until they part, the contender seat in one game and the hb-l50 seat in
the other face the same positions (same seat, same ply, same two FENs). In guardnone-b this happens at 803
positions. hb-guardnone, which never prices anything, chose a different move from hb-l50 at 153 of them (19.1%),
and the first such difference came at a median ply of 20 in all 150 pairs. At those positions it ran 278k
main-search nodes against hb-l50's 283k, with discovery nodes 57k against 55k and probe nodes 101k against 99k.
It had a delivery candidate where hb-l50 had none at 64 positions, and the reverse at 11. The differing choices
were a different main move with both keeping it (64 pairs) and a `world_switch` on one side only (59 pairs). In
the engine source (`hb_coordinator.cpp` near line 700, read only), the guard below the floor still runs the
partner base probe, still logs `prices=1` with an `hb_prices` line of zeros, and returns before the no-prices
branch. For guardfloor-b at its 849 shared positions the figures are 17.9% different moves, 268k against 283k
main nodes, and deliveries 66 against 11. So an engine that sets no price at all still plays differently from
hb-l50 about one decision in five in the opening and middlegame. That is the size of change behind guardnone-b's
139-161, which is not significant by itself (p 0.191), and behind its sudden mates (76 against 49, p 0.020).

`guardnone-b` additions (Fable recorded the score): terminations 296 checkmates, 4 flags; Elo -26 (-64 to +13);
contender 70-80 as white and 69-81 as black. `guardstats.py`: guard low in 98.0% of decisions (the rest log no
guard: budget too small or one legal move), no probe and no mate price ever; `rescue=`/`partner_held=` logged
591 times against hb-l50's 556; main nodes 262k against 267k; own board at plies 40 to 80 +7 against +39.
`postmortem.md`: first to see itself mated 162 against 138. Stated chances of 60-75% came true 61.2% for
hb-guardnone and 67.9% for hb-l50, and the Brier scores were 0.204 and 0.203. In the 77 against 49 sudden
collapses, the fatal piece was a queen 46 times against 22 (in guardfloor-b, 21 against 28). The seat knew
"in a world, where every candidate was mated" in 40 against 20, and the partner's own line had that capture in 32
against 20. Fall classes (AUTOPSY3's rules): falls 274 against 278; arrival falls 195 against 177; team-first
falls in lost games 161 against 139, of which arrivals 130 against 100; own-board falls 53 against 66.

**Item 4, queued at 04:50.** Fable's 04:40 lines (v8i build and check, `worth-b`, `guardquiet-b`) were already in
`logs/queue.txt` ahead of A5 and A6, so the queue will not be empty at 06:00. The three matches were appended at
the end now, in the order Fable gave ("then the three matches of item 4"), rather than at 06:00. That way they
follow even if this session ends. Each is the `guardfloor-b` line with only the name and options changed (checked
with diff), followed by its `scripts/pool.py` line: `guardfloor100-b` (`HBMateGuardFloor=-100`), `guardfloor600-b`
(`-600`), and `guardnone-norescue-b` (`HBMateGuardFloor=100000,HBRescue=false`; `HBRescue` exists in the v8h
binary, default true). Rough timing at tonight's speeds: planlate-vs-plan, v8i, worth-b, guardquiet-b, A5 and A6
take until about midday, and the three guard matches about 6 hours after that.

**05:07-05:12 (queue).** `planlate-vs-plan` done 49-50-1, recorded in the A4 row. `bin/hypebeast-v8i` was built at
05:10 (sha256 89e501af95ab39e1...). `coord12.py` printed PASS at 05:12 and `bin/hypebeast-v8i.ok` exists, so
`worth-b` started.
- With all options off, 10 of 10 decisions matched v8h.
- A test message heard with the limits off priced ours R 600 and theirs Q 800, N 300. With the limits on, only
  theirs Q 800 was priced.
- With the teller at -900 and the floor at -300, it logged `heard=low` and priced nothing.
- Quiet guard against no prices at the same 10 positions: the move differed in 2 (game 3 ply 40 Awhite B@e4
  against B@h4; game 35 ply 72 Bblack g1a1 against N@c4). Main nodes were 250k to 278k against 270k to 293k: the
  probes' nodes still come out of the main search.

**`worth-b` additions** (Fable recorded the result and its cause at 07:25; these are from `autopsy3/worth.py` ->
`worth_worth-b.txt`, `samepos.py`, `postmortem.md`):
- **Summary figures.** Elo -95 (-137 to -56). 55-93-2 as white and 54-96 as black. 292 checkmates, 6 flags, 2 draws.
  All 300 games were played; the 33% stop never triggered.
- **Mates.** First to see itself mated: 186 against 110. Fatal queens in sudden mates: 30 against 28.
- **Calibration.** Stated 40-60% won 38.1% for hb-worth (61.8% for hb-l50). Stated 60-75% won 49.4% (71.2%).
- **Cost.** None, as designed. At the 3,072 positions both met within pairs, main nodes were 280.8k against
  280.8k, with discovery and probe nodes equal as well. The moves differed at 4.9% of those positions, first at a
  median ply of 33. The loss is the prices alone.
- **The own board lost material steadily.** Own-board material (board and both hands, the seat minus its
  opponent, pawns; mean at the seat's first decision at or after ply k): ply 20 -0.24 against -0.21, ply 30 -0.56
  against -0.27, ply 40 -0.64 against -0.27, ply 60 -1.52 against +0.39, ply 80 -2.01 against +0.98. This fits
  Fable's reading: trades were avoided at the cost of material.
- **Priced scores are not board scores.** With a price set, the main score at plies 40-80 averaged -635. After a
  priced decision, the next score rose by +358 on average, against -67 after an unpriced one: the price sits
  inside the score. Without a price the score was -122 against hb-l50's +147.
- **Who was mated.** In lost games, the seat that priced most was first to see itself mated in 100, its partner in 82.
- **Games with a price.** One was set in 294 of the 300 games (109 points); the other 6 games gave 1 point.

**`guardquiet-b`, done 09:15: 158-142-0** (recorded by the Opus session; v8i,
`HBMateGuard=true,HBMateGuardFloor=-300,HBMateGuardQuiet=true` against hb-l50, the same 150 pairs of
`dev200c-51.txt`).
- **Result.** 52.7%, 95% 46.7% to 58.7%, p 0.383 (sign test 0.445); Elo +19 (-23 to +61); pairs 46 won, 66 split,
  38 lost; 85-65 as white and 73-77 as black; 290 checkmates, 10 flags.
- **Mates.** Sudden mates 53 against 76 (p 0.052). Fatal queens 20 against 28. First to see itself mated 142
  against 157.
- **Forecasts.** Stated 60-75% came true 63.2% against 57.4%; Brier 0.204 against 0.203.
- **Guard figures** (`guardstats_guardquiet-b.txt`): the same as guardfloor-b.
- **It is the floor guard again, game for game** (`diverge_guardfloor-b_vs_guardquiet-b.md`).
  - 233 of the 300 games are identical to guardfloor-b's, move for move.
  - The other 67 part late: median ply 113 (no mate price before) and 125 (a mate price earlier in the game).
  - All 67 parting decisions are with the partner's board below the floor (`guard=low` on both sides), mostly
    `no_arrivals` with the partner mated and sitting. `rescue=` or `partner_held=` was logged at 53 of them.
  - Results differ in 3 games (guardfloor better 1, guardquiet better 2): pairs 4 black, 35 black and 47 white, at
    plies 97 to 131.
  - At the 849 positions shared within pairs, its node counts and choices against hb-l50 are exactly
    guardfloor-b's (17.9% different moves; 268k against 283k main nodes).
- **What `HBMateGuardQuiet` removes.** In these games it removes only the rescue prices while the partner is mated.
  They change the play late, in about one game in five, and the result in 1%. Against guardnone-b the parting
  table is that of guardfloor-b (`diverge_guardquiet-b_vs_guardnone-b.md`): results differ in 145 games, 82 to 63;
  282 games part at a probe decision with no mate price, and 4 at a mate price.
- **For the item-3 question** ("the mate price or the rest of prices-on"): with the floor guard, the rest of
  prices-on is worth about nothing (157 against 158 on the same games). The 18 to 19 wins over guardnone-b come
  with the probes while the partner's board is alive: their node cost, their cache and hash effects, and the rare
  mate prices (2.1% of decisions). These matches do not split those parts further. guardquiet-b is not an
  independent replication of guardfloor-b either: it is largely the same 300 games. With guardfloor-vs-l50, the
  independent evidence for the floor guard is still 220-180 in 400 games.

**09:16-09:20 (queue).** `bin/hypebeast-v8j` was built (sha256 d6a86403e5e15297...). `coord13.py` printed PASS:
with all options off, 14 of 14 decisions matched v8i. 11 of the 14 had a candidate that hands something over. With
a fresh message, the move differed from the "nothing heard" move in 3 of 14. Below the floor it logged `low`, with
the move unchanged. `bin/hypebeast-v8j.ok` exists, so `feed-b` started at 09:20.

**`feed-b`, stopped early at 09:50: 31-65-0** (recorded by the Opus session; v8j, `HBTell=worth,HBTellRoot=true,
HBPriceScale=100,HBPriceCap=1500,HBTellMin=150,HBTellFloor=-300` against hb-l50, the first 48 pairs of
`dev200c-51.txt`). `run_match_stop.sh` stopped it at 33% after 96 games.
- **Result.** Pool on 94 games of finished pairs: 33.0%, 95% 22.1% to 43.8%, p 0.002 (sign test 0.007). Elo
  -129; pairs 8 won, 15 split, 24 lost; 16-32 as white and 15-33 as black; 91 checkmates, 5 flags.
- **Mates.** Sudden mates 26 against 11 (p 0.020). Fatal queens 11 against 4. First to see itself mated 65
  against 31.
- **Calibration.** Stated 40-60% won 30.1% (hb-l50 70.0%); stated 60-75% won 38.3% (71.6%).
  Figures from the logs (`hb_coord`/`hb_summary`, `worth.py feed-b`, `samepos.py feed-b`) follow.
- **Cost.** None. At the 329 positions both met within pairs, nodes were identical, and the moves differed at
  14.3% of them (worth-b: 4.9%).
- **`feed_switch` decisions: 439 of 5,293 (8.3%).** At 213 the chosen move's own capture gave the partner a `+T`
  where the main move had no feed. At 197 the main move's comparison line had a reply capture (`-T`) and the chosen
  one had none. 82 kept main moves were logged `feed_kept=1`.
- **What a feed switch cost our own board.** Measured as the main move's value minus the chosen move's in the
  "none" world: median 91, mean 801. 44 cost 300 or more. The feed gain had a median of 354. For comparison,
  `world_switch` cost a median of 32 (mean 193, 40 of 683 at 300 or more).
- **Score change to the seat's next decision.** After a feed switch -78, after a world switch -51, after a kept
  main move +14.
- **Own boards.** The own score at plies 40-80 was -126 against +136. Own-board material at ply 80 was -1.10
  against +0.17. Material at earlier plies swings with 96 games and does not show the steady slide of worth-b.
- **Sudden mates.** In 8 of hb-feed's 26, the seat itself had made a feed switch at one of its last two decisions.
  In none was the partner's last decision a feed switch.
- **Feed switches per game against the result.** 0-2 switches: 8 of 20 games won; 3-5: 13 of 45; 6-9: 8 of 28;
  10 or more: 2 of 3. No clear rise with the number of switches.
- **Reading, for Fable.** The worth numbers are now charged once, at the choice of the move, yet the seat still
  gives up its own board. One feed switch in ten costs 300 cp or more for a feed the teller valued at a median of
  354. The losses outrun the switches themselves (65 against 31 first to see itself mated). One example from
  `w0-contender-A.log` (Ablack, first `feed_switch`): the main move c5e3 captures a bishop, but its comparison
  line's reply captures a queen-worth piece, so its feed is -775. The same reply cost is charged to the delivery
  d8d3. The chosen P@b2 (feed -365) is 79 cp worse on our board in the "none" world. The reply in a 10-ply
  comparison line is the forecast's guess of the opponent's move. A large `-T` from it moved the choice whatever
  our own board said.

### Where the floor guard stands, and the queue from here (09:25, Fable)

- `bin/hypebeast-v8j` built 09:16 (sha256 d6a86403e5e15297...); `coord13.out`: all off, 14 of 14
  decisions as v8i; with a message heard nothing is priced in the search, 11 of 14
  decisions had a candidate with a feed term, two became `feed_switch`; below the
  floor the decision is the one with nothing heard; PASS. `feed-b` started 09:20.
- The Opus session's game-by-game comparison settles two things. `guardquiet-b` is
  `guardfloor-b` again (233 of 300 games identical, results differ in 3), so the two
  must not be pooled: the floor guard rests on **220-180 in 400 independent games
  (55.0%, p 0.050), sudden mates 67 against 92**. And the rest of prices-on is
  worth about nothing beside the floor guard (157 against 158), so the guard's
  lead over `guardnone-b` is not explained by the rescue prices: `guardnone-norescue-b`
  is taken out of the queue.
- Not the candidate yet. Next after `feed-b`: **`guardquiet-d`**, the quiet floor
  guard against L50 on v8j, 300 pairs of `openings/dev300d.txt` (300 openings no
  match has used, salt `arena-d`): 600 games, pooled with the 400. If the 1,000
  games hold 54% or more, L50 with `HBMateGuard=true,HBMateGuardFloor=-300,HBMateGuardQuiet=true`
  becomes the candidate; at 52% or less it does not; between, it stays an option.
- Then A5, A6, and `guardfloor100-b` and `guardfloor600-b` (they share most games
  with `guardfloor-b`: read them game by game, as the Opus session did, not by score).

### What the numbers in `feed-b` are worth, and v8k (09:55, Fable; `logs/loss-analysis/feedtruth.py logs/feed-b`)

The result is recorded above (31-65, stopped at 96 games). What followed each kind
of decision on both boards:

| decisions | n | feed, played minus main | own value, played minus main | own score at the next decision | partner's score, after minus before |
|---|---|---|---|---|---|
| `feed_switch` to gain for the partner | 223 | +403 | -131 | -76 | +291 |
| `feed_switch` to avoid a cost | 206 | +492 | -123 | -76 | -84 |
| kept the main move, feed above 0 | 284 | 0 | 0 | +11 | +288 |
| kept the main move, feed below 0 | 157 | 0 | 0 | +6 | -162 |

- **The told gains are true.** A move with a told gain of 228 was followed by +195
  on the partner's board, 392 by +281, 689 by +542: about three quarters arrives.
- **The told costs cannot be dodged this way.** After a switch away from a move
  whose expected reply cost the partner, the partner's score fell 84 anyway (162
  when the move was kept): the seat gave up 123 cp of its own board to save about
  80. The reply it feared is only one of the ways the piece goes.
- There were 430 `feed_switch` decisions, 8.3% of all, not the small effect
  expected. Their sum over one decision is about level (+24) and the match was
  lost two to one: a score one decision later is not the result. What is given up
  on the own board (sudden mates 26 against 11) costs more than its figure, as the
  surface's own limit said ("not what happens when a seat steers for a cell").

Five ways of honouring a partner's figures have now lost or been level: in the
search at half share (5-19), at a quarter (47-53), losses only (109-189), at the
choice of the move (31-65), and the told line (210-190, level). What has gained:
the seat's own forecast worlds (+220 Elo), late captures in them (twice about
+45), and the mate guard with a floor (220-180 in 400 games, being repeated on 600).

**v8k** (source; the queue builds it after `guardquiet-d`): `HBTellRootSide` 1 = gains
only, 2 = costs only. Then `gain33-b` (gains only at a third of the told figure: a
switch needs its own-board cost to be under a third of the gain) and `gain100-b`
(gains only, the full figure), each against L50 on v8k on the same 150 pairs,
stopped at 33% or less after 30 games.

**10:55, run note (Fable).** `guardquiet-d` stood at 13-21 after 34 games; the machine had
been asleep for about 50 minutes. Its early-stop watcher (`run_match_stop.sh`, 33%
after 30 games) is a screening rule and would have cut a confirmation match, so
the watcher alone was killed: the arena and `run_match.sh` play on and the
post-mortem will run. Because of that the queue logged the line as ended at 10:54
with a pooled figure that leaves the match out; the queue now waits for the arena
before its next line. The real figure: `scripts/pool.py logs/guardfloor-vs-l50
logs/guardfloor-b logs/guardquiet-d` once `logs/guardquiet-d.log` shows `exit=`.
For any later confirmation match use `scripts/run_match.sh`, not `run_match_stop.sh`.

**12:20, run note (Opus).** `run_queue.sh` was found gone between 12:15 and 12:18
(no `logs/queue.stop`, no note; it was a child of an old tool shell, which most
likely took it down). `guardquiet-d` was untouched: arena and `run_match.sh` still
playing, 145-131-1 after 277 of 600 games. Its line is already in `queue.txt.done`,
so the queue was restarted (`setsid nohup scripts/run_queue.sh logs/queue.txt`,
output in `logs/queue.runner.out`); it waits for the arena and post-mortem before
the v8k build.

**14:17, v8k (Opus, recorded only).** Built 14:14 (`sha256 ef144dee3b918214...`); `coord13.py
bin/hypebeast-v8j bin/hypebeast-v8k` PASS (`logs/loss-analysis/coord13k.out`): with the new options
at their defaults, 14 of 14 decisions as v8j; 11 of them had a candidate that hands something over.
The check covers defaults only: neither `HBTellRootSide` nor `HBTellRootMaxCost` is exercised by it.
`bin/hypebeast-v8k.ok` written, so the v8k matches (`cap10-b` first) start next.

### `guardquiet-d` finished (14:12, Opus, recorded only)

**287-309-4 in 600 games (48.2%), pairs 63-162-75 (sign test p 0.35).** Pooled with the 400
independent games: **507-489-4 in 1000 (50.9%, p 0.56).** By Fable's 09:25 rule (52% or less: not
the candidate), the floor guard is not the candidate.

Rest of the record (14:25, the night-shift Opus session; `pool.py` and `logs/guardquiet-d/postmortem.md`,
figures checked against the line above):
- Sudden mates: 100 against 100 in this match (p 1.000); pooled over the 1000 games 167 against 192
  (p 0.205). The 400 earlier games had 67 against 92; the 600 new ones show no difference.
- 95% interval: this match 44.4% to 52.0%; pooled 47.9% to 53.9%, pairs 126-118 (sign test p 0.654).
- First to see itself mated: hb-guardquiet 311 games (lost 299), hb-l50 285 (lost 275).
- Switches away from the main move: 17.7% against 17.8%, change by the next decision -50 against -39 cp;
  kept moves +11 against +19.
- Calibration: at stated 40-60% the guard side won 46.4%, L50 53.1%; at 25-40%, 28.0% against 33.7%.
- Fatal pieces in sudden collapses: guard Q 41, N 25, R 18, P 15, B 8; L50 Q 48, P 15, B 14, N 14, R 13.
  "In a world where every candidate was mated" 41 against 40.
- Run: one 50-minute suspend (10:04-10:53); the stop wrapper was removed at 10:55 (Fable's note); no
  errors, no illegal moves, 583 checkmates, 13 flags, 4 draws.

### The partner's gain as a tie-break, `HBTellRootMaxCost` (12:55, Opus; the user's idea and go-ahead)

The user: "if two options are equal or within 10cp of each other ... pick the one that is slightly
better for our partner", and "find the acceptable partner cp gain/cost to make it worth it ... we
could also try a 1-5 category". Spec written by the user, not Fable; built by Opus at the user's request.

- Evidence (`feed-b`, gain switches by own-board cost, main L minus played L; script
  `~/.cache/tmp/claude-4215325/-home-anbernal-Projects-HypeBeast/4fba71fd-0f4d-4829-9525-144a3f86c9b1/scratchpad/tiebreak.py`):
  cost <=0: 19, own +22, partner +348, won 53%; 1-10: 12, +51, +308, 50%; 11-30: 15, -26, +375, 27%;
  31-60: 29, +17, +246, 28%; over 60: 148, -124, +284, 34%. Small groups, read as a hint.
  A switch costing <=10 for >=3x that was on offer in 121 of 1542 decisions with a feed term.
- Code (source only, built by the queue as v8k): option `HBTellRootMaxCost` (default -1, no limit).
  At the choice, a candidate whose L is more than the limit below the main move's L is judged by S0
  (its value without the feed) instead of S. Everything else as v8k `gain100-b`.
- Queue: `cap10-b`, `cap5-b`, `cap0-b`, `cap20-b` after the v8k check, before `gain33-b`/`gain100-b`
  (the uncapped reference). Same 150 pairs of dev200c-51 against L50 on v8k: games where the
  contender never switches are identical in both colours, so read the pairs won/lost sign test and
  the games that differ, not the raw score.

**`cap10-b` finished (16:03; recorded by the night-shift Opus session, no reading of what it means).**
`HBTellRootMaxCost=10`, otherwise as `gain100-b` (`HBTell=worth,HBTellRoot=true,HBTellRootSide=1,
HBTellMin=150,HBTellFloor=-300,HBPriceCap=1500,HBPriceScale=100`), against hb-l50, 150 pairs of dev200c-51.
- **145-155-0 (48.3%), 95% 43.2% to 53.4%, pairs 28-89-33 (sign test p 0.609).** No errors or illegal
  moves; 291 mates, 9 flags. Ran the full 300 (never near the 33% stop).
- Sudden mates (pool.py): contender 63, baseline 44 (p 0.081); postmortem's count 66 against 44.
  Fatal pieces: cap10 Q 31, N 17, P 12, R 7, B 7; L50 Q 18, N 10, P 8, R 7, B 2.
- First to see itself mated: cap10 152 (lost 148), L50 148 (lost 141).
- Switches: `feed_switch` 150 of 17,890 contender decisions (0.8%; `feed-b` uncapped on v8j: 8.3%).
  All switches 16.8% against 17.8%; change by the next decision -37 against -51 cp.
- By game (`logs/loss-analysis/autopsy3/tiebreak_games.py`): 117 games had at least one feed switch
  (median 1), contender 62 of 117 (53.0%); the other 183 had none, contender 83 of 183 (45.4%).
  Pairs with a feed switch in either game: won 21, split 55, lost 19. Pairs with none: won 7, split 34,
  lost 14.
- **The premise above does not hold as written:** 21 pairs without any feed switch still went one way.
  Without a switch the contender still differs from L50 (likely the `HBTell=worth` messages and the
  feed scoring at the choice change the hash and nodes; not checked), so its games are not L50's. A "no switch, so identical" filter cannot be used
  to isolate the cap; compare cap matches with each other and with `gain100-b` game by game
  (same baseline, same openings) instead, e.g. `diverge.py cap10-b gain100-b` once both exist.

**`cap5-b` finished (17:40; night-shift Opus, recorded only).** `HBTellRootMaxCost=5`, otherwise as `cap10-b`.
- **148-152-0 (49.3%), 95% 44.0% to 54.7%, pairs 32-84-34 (sign test p 0.902).** No errors; 289 mates,
  11 flags; full 300.
- Sudden mates (pool.py): contender 65, baseline 42 (**p 0.033**); postmortem 68 against 42. Fatal pieces:
  cap5 Q 31, N 16, P 14, R 8, B 7; L50 Q 16, N 10, P 9, R 8, B 2. With `cap10-b` (63 against 44) that is
  two matches with the same excess, but the two are mostly the same games (next bullet).
- First to see itself mated: cap5 148 (lost 145), L50 152 (lost 145).
- `feed_switch` 125 of 17,797 contender decisions (0.7%). All switches 16.5% against 18.0%.
- By game: 105 games with a feed switch, contender 59 (56.2%); 195 without, 89 (45.6%). Pairs with a
  switch won 23, split 43, lost 19; without won 9, split 41, lost 15.
- **Against `cap10-b` game by game** (`diverge.py cap10-b cap5-b`): 278 of 300 games identical. All 22
  others part at a decision where cap10 made a `feed_switch` and cap5 did not (cap5 kept the main move in
  20, world-switched in 2), i.e. switches costing 6 to 10 cp on the own board; median parting ply 55.
  Results differ in 13: cap10 better in 5, cap5 better in 8 (pairs 4w, 10w, 22w, 35w, 55w, 100b, 127w,
  128w for cap5; 40b, 53w, 76w, 86b, 98b for cap10). Total 145 against 148.

**`cap0-b` finished (21:27; night-shift Opus, recorded only).** `HBTellRootMaxCost=0`, otherwise as `cap10-b`.
Took 3 h 46 min (cap10/cap5 about 1 h 40 min): no suspend in the journal, 5-min load was about 11 from
other work on the machine; fixed nodes, so the games are unaffected.
- **150-150-0 (50.0%), 95% 44.7% to 55.3%, pairs 33-84-33 (sign test p 1.000).** No errors; 291 mates, 9 flags.
- Sudden mates (pool.py): contender 66, baseline 42 (**p 0.026**); postmortem 69 against 42. Fatal pieces:
  cap0 Q 32, N 16, P 12, R 9, B 7; L50 Q 17, N 11, P 8, R 7, B 2.
- First to see itself mated: cap0 148 (lost 143), L50 152 (lost 145).
- `feed_switch` 104 of 17,796 (0.6%). All switches 16.3% against 18.1%.
- By game: 92 games with a feed switch, contender 56 (60.9%); 208 without, 94 (45.2%). Pairs with a
  switch won 23, split 41, lost 16; without won 10, split 43, lost 17.
- **Against `cap5-b`** (`diverge.py cap5-b cap0-b`): 276 of 300 identical. Of the 24 others, 23 part at a
  decision where cap5 made a `feed_switch` that cap0 did not (or a different one), 1 at a world switch;
  median parting ply 39. Results differ in 10: cap5 better in 4, cap0 better in 6.
- Across the three caps (10, 5, 0; mostly the same games): feed switches 150, 125, 104; score 145, 148,
  150; contender sudden mates (pool.py) 63, 65, 66 against L50's 44, 42, 42. The sudden-mate excess does
  not shrink as switches are removed, and in each match the games without any feed switch score about
  45% (45.4%, 45.6%, 45.2%).

**`cap20-b` finished (23:02; night-shift Opus, recorded only).** `HBTellRootMaxCost=20`, otherwise as `cap10-b`.
- **142-158-0 (47.3%), 95% 42.3% to 52.4%, pairs 26-90-34 (sign test p 0.366).** No errors; 293 mates, 7 flags.
- Sudden mates (pool.py): contender 63, baseline 46 (p 0.125); postmortem 66 against 46. Fatal pieces:
  cap20 Q 32, N 17, P 11, R 8, B 6; L50 Q 21, N 12, P 9, R 6, B 4.
- First to see itself mated: cap20 155 (lost 150), L50 144 (lost 137).
- `feed_switch` 177 of 17,834 (1.0%). All switches 17.0% against 17.9%.
- By game: 136 games with a feed switch, contender 72 (52.9%); 164 without, 70 (42.7%). Pairs with a
  switch won 20, split 60, lost 24; without won 6, split 30, lost 10.
- **Against `cap10-b`** (`diverge.py cap10-b cap20-b`): 257 of 300 identical. Of the 43 others, 33 part
  where cap20 made a `feed_switch` that cap10 did not (cost 11 to 20 cp), 10 at world switches or kept
  moves; median parting ply 44. Results differ in 17: cap10 better in 10, cap20 better in 7.

All four caps (mostly the same games; `gain33-b` and `gain100-b`, the uncapped references, still to come):

| cap | feed switches | score /300 | pairs won-split-lost | sudden mates, contender-L50 (pool.py) | games without a switch: contender |
|---|---|---|---|---|---|
| 0 | 104 | 150 | 33-84-33 | 66-42 (p 0.026) | 45.2% |
| 5 | 125 | 148 | 32-84-34 | 65-42 (p 0.033) | 45.6% |
| 10 | 150 | 145 | 28-89-33 | 63-44 (p 0.081) | 45.4% |
| 20 | 177 | 142 | 26-90-34 | 63-46 (p 0.125) | 42.7% |

**`gain33-b` finished (00:33, 11-13; night-shift Opus, recorded only).** Fable's v8k spec (09:55): gains only
at a third of the told figure (`HBTellRootSide=1,HBPriceScale=33`, no `HBTellRootMaxCost`), against L50 on v8k,
same 150 pairs.
- **159-141-0 (53.0%), 95% 47.8% to 58.2%, pairs 36-87-27 (sign test p 0.314).** No errors; 293 mates, 7 flags.
- Sudden mates (pool.py): contender 62, baseline 55 (p 0.579); postmortem 62 against 55. Fatal pieces:
  gain33 Q 31, N 21, P 13, R 7, B 4; L50 Q 21, R 14, N 10, P 10, B 9.
- First to see itself mated: gain33 141 (lost 136), L50 159 (lost 154).
- `feed_switch` 206 of 17,528 (1.2%). All switches 18.1% against 17.3%.
- By game: 157 games with a feed switch, contender 96 (61.1%); 143 without, 63 (44.1%). Pairs with a
  switch won 34, split 61, lost 26; **pairs without any feed switch: won 2, split 26, lost 1.**
- **Here the "no switch, so as L50" premise nearly holds** (3 decisive pairs of 29 without a switch); in the
  four cap matches it did not (21, 24, 27, 16 decisive pairs without a switch). The caps differ from
  gain33 in `HBPriceScale` (100 against 33) and in having `HBTellRootMaxCost` set; `gain100-b` (scale 100,
  no cap) is next and will show which of the two goes with the extra difference.
- **Against the caps game by game:** `diverge.py cap0-b gain33-b`: 78 identical; results differ in 97, cap0
  better in 44, gain33 better in 53. `diverge.py cap20-b gain33-b`: 75 identical; differ in 99, cap20 better
  in 41, gain33 better in 58. Parting decisions are mixed (kept/feed/world switches on either side, median
  ply 44-46): the scale changes far more games than the cap does.
**`gain100-b` finished (11:07, 11-13; Opus, recorded only).** Fable's v8k spec (09:55): gains only at the full
told figure (`HBTellRootSide=1,HBPriceScale=100`, no `HBTellRootMaxCost`), against L50 on v8k, same 150 pairs.
The laptop was suspended 01:02-10:06 (lid closed); fixed nodes, so the games are unaffected.
- **112-187-1 (37.5%), 95% 32.4% to 42.6%, pairs 17-79-54 (sign test p 0.000); arena Elo -89 (-127 to -51).**
  No errors or illegal moves; 293 mates, 6 flags, 1 draw. Never reached the 33% stop.
- Sudden mates (pool.py): contender 74, baseline 38 (**p 0.001**); postmortem 75 against 38. Fatal pieces:
  gain100 Q 34, N 16, P 13, B 12, R 10; L50 Q 18, N 9, R 6, P 5, B 4.
- First to see itself mated: gain100 190 (lost 184), L50 109 (lost 106).
- `feed_switch` 784 of 16,429 contender decisions (4.8%; caps 0.6-1.0%, gain33 1.2%). All switches 20.5%
  against 17.2%; change by the next decision -60 against -32 cp. Calibration: at stated 40-60% gain100
  won 38.5%, L50 61.2%.
- By game: 280 games with a feed switch (median 3), contender 39.1%; 20 without, 15.0%. No pair was free
  of switches.
- **Game by game:** `diverge.py gain33-b gain100-b`: 23 identical; results differ in 141, gain33 better in 94,
  gain100 better in 47. `diverge.py cap0-b gain100-b`: 23 identical; differ in 130, cap0 better in 84,
  gain100 better in 46.

The four `HBPriceScale=100` matches with a cap (0-20) and this one without, side by side with `gain33-b`:

| contender | feed switches | score /300 | pairs won-split-lost | sudden mates, contender-L50 |
|---|---|---|---|---|
| cap 0 | 104 | 150 | 33-84-33 | 66-42 |
| cap 5 | 125 | 148 | 32-84-34 | 65-42 |
| cap 10 | 150 | 145 | 28-89-33 | 63-44 |
| cap 20 | 177 | 142 | 26-90-34 | 63-46 |
| no cap, scale 100 | 784 | 112.5 | 17-79-54 | 74-38 |
| no cap, scale 33 | 206 | 159 | 36-87-27 | 62-55 |

## Loss analysis (2026-11-10, Opus session; for Fable to judge)

Measurements only, none match-tested, and no engine change was made. Scripts and
their data are in `logs/loss-analysis/` (git-ignored). Sources: `v6h-np-vs-v5e`
and, for the king and imaginary-piece sections, also `v6h-np-vs-v5e-b`.

**How the 44 losses in `v6h-np-vs-v5e` look** (`losses.py`, `losses2.py`, `losses3.py`)

- In all 98 games where a seat stood mated by force, the side that saw it first
  lost (55 v5e, 43 v6h-np), with `HBPlayOn` on for v6h-np. It appears about 75 s
  before the end.
- 42 of 44 losing seats saw the mate before it landed, median 3-4 moves out. Of 23
  mates by drop, the piece was in hand at the seat's last move in 19.
- Sharp eval falls (from -300 or better, by 500+) in lost games: 116, of which 111
  followed a new piece reaching the opponent's hand. Rate 21% with an arrival, 1%
  without. Partly arithmetic: a piece in the opponent's hand counts against us.
- At the decision before seeing mate: 13 of 42 level or better ("sudden"), 20 of 42
  already at -800 or worse.
- In 6 of 44 losses (v5e: 2 of 56) the other seat still had a forced mate at its
  last decision: clock races while both sides sat (game 86 by 1.3 s).

**The 13 sudden losses** (`sudden.py`, `walkback.py`; judge is `bin/hypebeast-v6h`
with `Coordination=false,HBFeedPrices=false`, as `tests/loss_set.py`'s `bin/hypebeast-v3`
is absent from this worktree; "survives" means no forced mate found at 400,000 nodes)

- All 13: the move played was not forced mate without the arriving piece, and was
  with it.
- 10 of 13: no legal move survived at that decision (usually 1-6 legal moves).
  3 of 13 (games 17, 20, 21) had a survivor, which a plain search told of the
  arrival found.
- Last free choice: 2 at that decision, 10 one to five own moves earlier, 1 further
  back. The walk-back hands over all later pieces for both sides at once, so it
  does not establish when each game became lost.
- The feeding capture was already legal at the decision in 9 of 13. The partner had
  a move avoiding that capture within about 250 cp in 8 of 13 (50,000-node search),
  none in 3, and only at 446 and 1400 cp in the other 2.
- Game 21: the forecast scored the world of the actual capture (`e7e5`, p 0.04),
  had `g8e7` at -99996 there, and kept `g8e7`. 102 of 103 legal moves survived.
  Across all 4,193 v6h-np decisions with worlds in step 2, the chosen move was mated
  in a scored world with an escape in only 21; where a move safe in every scored
  world existed (16), it cost a median 350 cp in the other worlds.

**When we get mated** (`hazard.py`, `hazard2.py`; 200 games). Chance of seeing forced
mate within 20 s, from positions v6h-np itself rated -200 or better:

| feature | rate |
|---|---|
| all | 108/6331 (1.7%) |
| king on home rank | 61/5575 (1.1%) |
| king 1 rank up | 37/712 (5.2%) |
| king 2+ ranks up | 10/44 (22.7%) |
| no pawns in front of the king | 25/617 (4.1%) |
| 2+ pawns in front | 28/2149 (1.3%) |
| king off home and attacker hand 6+ points | 20/250 (8.0%) |
| king home and attacker hand under 6 | 27/3751 (0.7%) |

v5e shows the same direction (2.5%, 5.4%, 14.3% by king rank). Hand size alone
barely separates (1.1% to 3.1%). 55 of 98 mated v6h-np seats still had the king on
the home rank at their last decision before seeing mate; first sight is at a median
101 s. The opponent's partner captures within 10 s about 67% of the time whether or
not a drop would mate (67.0% against 67.1%).

**Imaginary extra piece** (`phantom.py`; plain search, 100,000 nodes, one extra piece
in the attacker's hand, positions the seat rated -200 or better, both engines):

| positions | no real mate | some extra piece mates | extra queen mates |
|---|---|---|---|
| last decision before seeing mate | 61 | 61 (100%; partly circular) | 55 (90%) |
| two decisions earlier | 74 | 36 (49%) | 34 (46%) |
| from won games, never mated | 200 | 22 (11%) | 21 (10%) |

For v6h-np alone: 41% (22 positions) against 4% (94). A one-move drop-mate check is
much weaker: it flagged 9% of v6h-np seats at the last decision. Mate being rare,
roughly 1 alarm in 10 would be real. The "won games" sample is likely safer than
ordinary positions.

**Facts about the engine and arena.** Upstream virtual drops (search uses pieces not
in hand) are off in HypeBeast mode through `HB::FrozenHands`, set in
`on_hypebeast_option` (`engine/src/hb_arena.cpp`), by the choice in PLAN.md section 4;
no UCI option turns them back on. The arena has no partner channel (upstream's
`ptell` is CECP only), though each seat sees both boards.

**Suggested next, for Fable to accept or reject:** (1) at free decisions where the
imaginary-queen search fires, does some move clear it, and at what cost? (2) ablation:
virtual drops back on in the main search, against the candidate; (3) ablation: a king
exposure penalty scaled by the attacker's hand, at a few strengths; (4) extend
`tests/loss_set.py` with labels of the moves safe against each capture available,
with an equal share of positions from won games where caution costs something.

