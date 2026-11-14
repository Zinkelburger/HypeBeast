# Autopsy 2: why hb-plan and hb-l50 lose (plan-vs-l50)

Written 2026-11-11 from logs only. No engine was run, built or stopped. Scripts and their outputs are in
`logs/loss-analysis/autopsy2/` (git-ignored). The number in brackets after a claim names the script or output
file it comes from. `run_all.sh` reruns the whole pass. Game numbers are the `game` field of
`logs/plan-vs-l50/results.jsonl`. "n" counts plies on both boards before a decision, as in AUTOPSY.md.

## Summary

**The match.** `hb-plan` beat `hb-l50` 57-43 (57.0%, 95% CI 48.1% to 65.5%, Elo +49, CI -13 to +111). 96 games
ended by checkmate and 4 on the clock. hb-l50 lost 57 games and hb-plan lost 43.

**Losses by first cause** [classify2.py, `classes_plan-vs-l50.txt`]:

| first cause | hb-l50 (57) | hb-plan (43) |
|---|---|---|
| decisive drop (400+ cp) after an arrival the seat had forecast (a4) | 14 | 13 |
| partner's board lost first (d) | 14 | 10 |
| slow loss on its own board (c) | 8 | 7 |
| sudden mate after a forecast arrival (a, a2, a3) | 12 | 9 |
| arrival in no world: mate or decisive drop (b, b2) | 5 | 1 |
| a sit that went wrong (h, all `stall_deny`) | 2 | 1 |
| a switch away from the main move that went wrong (g) | 1 | 1 |
| lost a mating race (e) | 1 | 1 |
| missed supply (f), clock (flag while not yet lost) | 0 | 0 |

- **Who could have seen the turning point.** In most falls the seat's own worlds had already priced the
  fatal piece, but its candidates did no better in that world. The best candidate beat the move played by 200 cp
  or more in only 3 of 42 scored falls for hb-l50 and 2 of 31 for hb-plan. So once the piece was coming, the
  seat could not dodge it.
  - The capture was in the partner's own main line in 34 of 52 falls for hb-l50 and 26 of 39 for hb-plan.
  - More depth would have found the mate in only 2 and 3 of the sudden-mate losses. Pieces that were in no
    world explain 6 and 5 of the falls (first cause in 5 and 1 losses) [losses_q3.py].
- **Evaluation errors with real signal**, net of the score [calib2.py; 400 games: this match plus the hb-l50 and
  hb-late50 seats of three earlier matches]:
  1. **King danger.** With 3 or more squares of the king zone attacked, the chance of collapsing within 3
     decisions is 9.2 points higher (CI 7.3 to 11.7). A king off its home rank adds 3.9 (CI 1.4 to 6.4) and being
     in check adds 2.7 (CI 0.9 to 4.4).
     - The king-zone effect holds on each side of this match alone: +10.8 for hb-l50 and +7.9 for hb-plan.
     - It is also visible in game results: -5.9 points (CI -9.0 to -2.8).
  2. **The partner's board.** A partner behind by more than 300 adds 5.3 points of collapse risk (CI 3.3 to 6.9).
     In game results, a partner behind is worth -11.3 points and a partner ahead +14.2.
  3. **Whose move it is on the other board.** With the partner to move there, collapses are 3.2 points rarer
     (CI 2.2 to 4.2). The turning point fell with the partner *not* to move in 35 of 56 and 23 of 41 losses,
     against about half of all decisions.

  Pieces in the opponent's hand, drop checks available to it, and a queen's possible drop checks carry **no**
  signal once the score is known: every interval crosses 0. The overconfidence AUTOPSY.md found shows again:
  stated chances above 50% come true 6.1 points less often than stated (CI 2.6 to 9.6).
- **What hearing the partner's line (hb-plan) changed.**
  - The forecast gives more probability to what really came: 0.399 against 0.364 (difference +0.035, CI +0.027
    to +0.044). Arrivals that were in no world fall from 21.4% to 19.6%.
  - Its Brier score is worse, 0.210 against 0.201 (difference +0.009, CI +0.003 to +0.016). The reason is one
    kind of world. The world holding the told line's whole package, stated at 0.31, arrived by the seat's next
    move in 2.9% of 1,399 cases and within four plies in 22.1%. The other worlds at the same decisions, stated at
    0.26, arrived in 48.7% and 62.9% [sides.py].
  - hb-plan switches away from its main move more often: 20.6% under the told line, 18.4% to 18.8% when it
    refused the message, 17.3% for hb-l50.
  - 16 of hb-plan's 40 turning points were switches, 13 of them under the told line. For comparison, switches
    made up 35% of hb-plan's decisions followed by a 400+ drop and 31.5% of hb-l50's.
  - Collapses per game did not change: 0.18 against 0.20.

**Ranked improvements** (details and tests in section 5):

1. A king-danger correction to the evaluation or to the coordinator's winning chance. It needs a build. Upper
   bound: 31 of hb-l50's 57 losses and 19 of hb-plan's 43 had a king-danger flag at the turning point.
2. A team winning chance in E that uses the partner's score. It needs a build, and the spec exists in
   PARTNER_TALK.md.
3. Fix the weight of the told line's late captures. Try `HBPlanTrust=30` as an option-only match against
   hb-plan. Upper bound: 13 losses.
4. `HBWinScale=1200`. It is option-only and already queued as F16.
5. Test `HBStall=false`. It is option-only. Upper bound: 3 losses here, and the evidence is weak.

The data does not support more search depth, more worlds, a back-channel alarm (already tested at 51-49), or
missed-supply work.

## Data and definitions

- **Match.** `logs/plan-vs-l50`: 100 games, `hb-plan` against `hb-l50`, both on `bin/hypebeast-v8d` at 500,000
  nodes a move. hb-plan adds its partner's told main line to its forecast (`HBTell=plan`, `HBPlanTrust=60`).
  Each game has one team of each engine, so the two sides' lost games are disjoint.
- **Rows** [common2.py]. There are 11,527 decisions, all matched to games. They come from
  `scripts/postmortem.py`'s `collect()`. To these I added the clocks, the full main line, the told line from
  `hb_forecast`, the value of every candidate in every coordinator world (`hb_coord`), and features of the
  position replayed with python-chess.
- **Definitions** are AUTOPSY.md's, unchanged, so the counts compare directly:
  - *Mated seat* S: the losing seat on the board that decided the game, or the flagged seat. *Partner* P.
  - *Lost for good* at a decision: the seat's main score is below -300 there and at every later decision.
  - *Fall*: the step from the seat's last decision at -300 or better (*pre*) to its first lost-for-good decision.
  - *Fatal piece*: the piece that reached the seat's opponent's hand in that step whose world gave the move
    played the lowest value.
  - *Turning point*: the `pre` decision of whichever seat of the losing team fell first.
- **First-cause rules** [classify2.py], fixed before I looked at the counts and applied in this order:
  1. Events: S's fall; P's fall; W, the team's first forced mate for itself; F, the first missed supply. The
     earliest wins. Ties go S, P, W, F.
  2. A flag while the flagged seat was not yet lost: **clock**.
  3. W first: **e**, lost a mating race. F first: **f**, missed supply.
  4. A fall first: the falling seat's `pre` decides the class.
     - **h**, a sit that went wrong: `pre` was a sit for a reason other than `hold_mated`.
     - **g**, a switch that went wrong: `pre` overrode the main move, and in the coordinator world matching what
       really arrived before the next decision, the main move scored 300 cp or more above the move played, or
       survived where the move played was mated.
     - Otherwise AUTOPSY.md's kinds:
       - **a**, **a2**, **a3**: sudden mate after an arrival in a world where the move played was mated, was
         scored survivable, or was not scored.
       - **b**: sudden mate after an arrival in no world. **c2**: sudden mate with nothing arriving.
       - **a4**, **b2**: a drop of 400 cp or more after an arrival in a world, or in no world.
       - **c**: anything else.
     - If P fell first, the class is **d**, and P's kind is the sub-class.
- **Who could see a fall** [losses_q3.py, visibility.py]:
  - *Seat's worlds*: at `pre`, or at one of the seat's last two decisions before the partner's decision that
    let the piece go, a world holding the piece had the move played mated while "none" did not. For a fall that
    is not a mate, the test is 300 cp or more worse than "none".
  - Otherwise *partner's line*: the capture was in the partner's own main line at its last decision before it.
  - Otherwise *nobody*.
- **Collapse within 3**: within the seat's next three decisions, either a forced mate against it, or a score
  at least 600 cp lower that is also below -300.
- **Intervals** are 95%, from 2000 resamples of whole games (400 for the joint models). Differences between the
  engines resample the same games for both.

## 1. Why each game was lost

### Counts

[classify2.py; game lists in `classes_plan-vs-l50.txt`]

| class | hb-l50 (57 lost) | hb-plan (43 lost) |
|---|---|---|
| (a4) decisive drop after a forecast arrival | 14: 1, 6, 9, 12, 19, 28, 39, 47, 52, 81, 84, 86, 93, 98 | 13: 5, 7, 8, 14, 21, 27, 42, 57, 62, 65, 72, 77, 78 |
| (d) partner's board lost first | 14: 24, 25, 29, 33, 43, 45, 49, 55, 56, 60, 63, 67, 75, 95 | 10: 13, 16, 31, 50, 69, 73, 83, 88, 90, 92 |
| (c) slow loss on its own board | 8: 0, 15, 23, 30, 40, 48, 89, 91 | 7: 10, 44, 53, 68, 80, 87, 99 |
| (a) sudden mate, the move was mated in the piece's world | 6: 17, 41, 46, 59, 61, 82 | 3: 3, 11, 36 |
| (a2) sudden mate, the world scored the move survivable | 4: 4, 37, 94, 97 | 4: 26, 54, 70, 74 |
| (a3) sudden mate, the move was not scored in that world | 2: 18, 20 | 2: 51, 71 |
| (b2) decisive drop after an arrival in no world | 3: 22, 76, 85 | 1: 96 |
| (b) sudden mate after an arrival in no world | 2: 35, 66 | 0 |
| (h) a sit that went wrong (`stall_deny`) | 2: 34, 79 | 1: 38 |
| (g) a switch that went wrong | 1: 64 | 1: 2 |
| (e) lost a mating race | 1: 58 | 1: 32 |
| (f) missed supply; clock | 0 | 0 |

- **d, by the partner's own fall**: hb-l50 a4 11, c 3. hb-plan c 4, a4 4, b2 1, g 1.
- **S's own fall, whatever came first**: hb-l50 a4 21, c 11, a 6, a2 6, b2 4, a3 3, b 2, g 2, h 2. hb-plan a4 16,
  c 12, a 4, a2 4, a3 3, b 1, b2 1, g 1, h 1.
- **Flags.** All 4 came after the flagged seat was already lost for good, so they are counted under their cause
  (hb-l50 1, 43, 56, 58). This confirms AUTOPSY.md.
- **Clocks.** At the turning point the seat's clock was a median 0.5 s (hb-l50) and 1.5 s (hb-plan) behind its
  opponent's. The two differed by more than 5 s in 2 of 56 and 1 of 41 [gen_table2.py]. Clocks did not decide
  these games.
- **An opening.** Games 44 and 45 are one opening pair. Bblack lost both at n=17 with -437 before any decision of
  its own counted, so the forced opening moves left that seat lost in both games.

**Against AUTOPSY.md** (96 losses of hb-l50 and hb-late50 in two older matches). The overall shape is the same:
about a fifth each for slow losses and partner-first losses, and most of the rest in arrival falls. Four
differences:

- **Fewer sudden mates "known fatal" (a).** 6 of 57 and 3 of 43, against 17 of 96.
- **More decisive drops short of mate (a4, b2).** 17 of 57 and 14 of 43, against 20 of 96. On v8d, falls more
  often go through a lost piece than straight to a mate.
- **No missed supply as a first cause**, against 4. The post-mortem counts 4 and 5 "could take, did not" episodes,
  and the team won all but one of them.
- **Fewer arrivals in no world.** 5 and 1 first causes, against 7.

### Turning points

The full per-game table (turning point, fall, fatal piece, partner's decision, who could see it, clocks) is in
`logs/loss-analysis/autopsy2/table_plan-vs-l50.md`. One line per game:

| loser | game | class | turning point: seat, n, move played | evidence |
|---|---|---|---|---|
| hb-l50 | 0 | c | Bwhite 60 g2f3 | -172 -> -518; -P (p 0.17); partner -1039 |
| hb-l50 | 1 | a4 | Bblack 50 P@c2 (main P@h3, world_switch) | 33 -> -711; -Q (p 0.25, move -366) |
| hb-l50 | 4 | a2 | Ablack 108 d6e5 | 381 -> M-10; -Q (p 0.05, move -308); the capture was in the partner's line |
| hb-l50 | 6 | a4 | Ablack 78 d8g5 | -149 -> -593; -N (p 0.63, move -259) |
| hb-l50 | 9 | a4 | Bblack 18 f8e7 | -108 -> -592; -P (p 0.18) |
| hb-l50 | 12 | a4 | Bwhite 67 N@g4 (main Q@d2, world_switch) | 68 -> -343; -B (p 0.38) |
| hb-l50 | 15 | c | Awhite 103 N@g4 | -74 -> -429; -P (p 0.15) |
| hb-l50 | 17 | a | Awhite 118 e2f3 | 283 -> M-4; -Q (p 0.24; every candidate mated in that world, already at n=114) |
| hb-l50 | 18 | a3 | Ablack 78 g5f7 | 188 -> M-10; -Q (p 0.28, move not scored) |
| hb-l50 | 19 | a4 | Awhite 44 f1g2 | 0 -> -585; -N (p 0.12, move -731) |
| hb-l50 | 20 | a3 | Bwhite 96 f4e5 | 285 -> M-4; -N (p 0.50); partner +1618 |
| hb-l50 | 22 | b2 | Ablack 31 e4d3 | -284 -> -1084; -Q in no world |
| hb-l50 | 23 | c | Bblack 92 h4d4 (main c8b7, world_switch) | -148 -> -417 |
| hb-l50 | 24 | d/a4 | Bwhite 52 d4g4 | 258 -> -409; -N |
| hb-l50 | 25 | d/a4 | Awhite 92 B@c5 | -251 -> -799; -N |
| hb-l50 | 28 | a4 | Bwhite 106 h1g2 | 266 -> -406; -P |
| hb-l50 | 29 | d/a4 | Awhite 70 b1b2 | 22 -> -538; -N |
| hb-l50 | 30 | c | Bwhite 168 d2e1 | -128 -> -453; nothing arrived |
| hb-l50 | 33 | d/a4 | Bblack 48 e4d6 | 374 -> -485; -R |
| hb-l50 | 34 | h | Ablack 120 pass (stall_deny) | +241, in check; the queen arrived during the sit, then M-2 |
| hb-l50 | 35 | b | Bblack 129 g2h3 | -1 -> M-8; -Q in no world; the capture was in the partner's line |
| hb-l50 | 37 | a2 | Bblack 148 f5g3 (main c2d2, world_switch) | -104 -> M-4; -Q (p 0.46, move -122) |
| hb-l50 | 39 | a4 | Awhite 50 d4e5 | 645 -> -566; -Q (p 0.40, move +150) |
| hb-l50 | 40 | c | Ablack 85 a8d8 | -203 -> -448 |
| hb-l50 | 41 | a | Bblack 64 f8g8 | 1277 -> M-14; -N (p 0.36, M-16) |
| hb-l50 | 43 | d/c | Bblack 99 B@f8 (main B@b6, world_switch) | -208 -> -546; flag |
| hb-l50 | 45 | d/c | Bblack 17 (opening) | lost from the opening, as in game 44 |
| hb-l50 | 46 | a | Bwhite 84 h3g2 | -57 -> M-6; -B (M-8 in its world) |
| hb-l50 | 47 | a4 | Bblack 90 P@h4 | 337 -> -949; -Q (p 0.27, move -983) |
| hb-l50 | 48 | c | Ablack 98 B@e8 (main g7g6, world_switch) | -11 -> -317 |
| hb-l50 | 49 | d/a4 | Bblack 71 P@b2 | 244 -> -314; -N |
| hb-l50 | 52 | a4 | Bwhite 41 d4f4 (main d4e4, world_switch) | -287 -> -723; -N |
| hb-l50 | 55 | d/a4 | Awhite 91 c1h6 | 119 -> -1169; -Q |
| hb-l50 | 56 | d/a4 | Bwhite 116 c2d3 | -141 -> -853; -Q; flag |
| hb-l50 | 58 | e | Ablack 61 g1h1 | the partner had M+13; Ablack fell -62 -> -1024 first; flag |
| hb-l50 | 59 | a | Awhite 103 f1e2 | -53 -> M-8; -R (M-6 in its world) |
| hb-l50 | 60 | d/a4 | Ablack 121 g5g6 (main P@f5, world_switch) | 173 -> -435; -P |
| hb-l50 | 61 | a | Bblack 108 g7f6 | 34 -> M-2; -R (p 0.50, M-4); partner +962 |
| hb-l50 | 63 | d/a4 | Bblack 113 B@b6 | -72 -> -583; -N |
| hb-l50 | 64 | g | Bwhite 89 P@g7 (main f6g8, soft_switch) | -50 -> -595; nothing arrived; the main move scored 300+ better |
| hb-l50 | 66 | b | Bwhite 82 e4g2 | 163 -> M-8; -N in no world |
| hb-l50 | 67 | d/a4 | Bblack 100 N@f3 | -262 -> -782; -Q |
| hb-l50 | 75 | d/c | Bblack 51 P@h3 | -103 -> -393; -B |
| hb-l50 | 76 | b2 | Bwhite 65 N@b5 | 280 -> -403; -N in no world |
| hb-l50 | 79 | h | Bblack 64 pass (stall_deny) | -284 -> M-4; -N (p 0.48) |
| hb-l50 | 81 | a4 | Bblack 73 h6f7 | -152 -> -1061; -Q (p 0.50) |
| hb-l50 | 82 | a | Ablack 82 b7b6 (main b7b8, exposure_veto) | 324 -> M-4; -Q (p 0.62, M-6) |
| hb-l50 | 84 | a4 | Bwhite 60 d4c6 | -217 -> -1600; -P |
| hb-l50 | 85 | b2 | Bblack 63 c5d4 | 117 -> -954; -N in no world; partner +616 |
| hb-l50 | 86 | a4 | Ablack 60 a5d2 | -207 -> -1079; -B |
| hb-l50 | 89 | c | Bblack 47 e8f8 | -280 -> -624 |
| hb-l50 | 91 | c | Bblack 19 g8e7 | -260 -> -303, early |
| hb-l50 | 93 | a4 | Bblack 126 g3f2 (main c3b2, exposure_veto) | 43 -> -1147; -Q (p 0.46, move -1297) |
| hb-l50 | 94 | a2 | Ablack 67 g8g7 | 135 -> M-6; -B (p 0.16, move -662) |
| hb-l50 | 95 | d/a4 | Bblack 114 c7d6 | -173 -> -968; -N |
| hb-l50 | 97 | a2 | Bblack 115 g8g7 (main f8f7, world_switch) | 86 -> M-12; -Q (p 0.17, move -587); partner +575 |
| hb-l50 | 98 | a4 | Bwhite 64 Q@e4 (main B@e4, world_switch) | -292 -> -1666; -Q (p 0.85); partner +775 |
| hb-plan | 2 | g | Awhite 89 N@c8 (main e1f2, world_switch) | 222 -> -785; see account below |
| hb-plan | 3 | a | Bwhite 96 d1d2 | 443 -> M-2; -B (p 0.72, M-4); partner +650 |
| hb-plan | 5 | a4 | Ablack 86 h1e1 (main B@c2, world_switch) | 240 -> -420; -P |
| hb-plan | 7 | a4 | Ablack 42 N@e6 (main e8g8, world_switch) | 8 -> -582; -N (p 0.84) |
| hb-plan | 8 | a4 | Bblack 73 Q@g5 | -167 -> -609; -B; partner +573 |
| hb-plan | 10 | c | Awhite 155 c7e7 | -298 -> -461 |
| hb-plan | 11 | a | Bwhite 94 d1c2 (main d1c1, exposure_veto) | 953 -> M-8; -Q (p 0.64, M-10) |
| hb-plan | 13 | d/c | Bwhite 54 B@g3 (main B@f6, world_switch) | -56 -> -372 |
| hb-plan | 14 | a4 | Bblack 44 N@d6 | -218 -> -638; -B (p 0.73) |
| hb-plan | 16 | d/c | Bblack 75 N@g6 (main d8g5, world_switch) | -57 -> -407; -Q (p 0.21) |
| hb-plan | 21 | a4 | Bwhite 60 g2g3 (main g2g1, world_switch) | 1519 -> -608; see account below |
| hb-plan | 26 | a2 | Awhite 188 N@c6 (main f1g2, world_switch) | -192 -> M-14; -Q (p 0.73, move -268) |
| hb-plan | 27 | a4 | Bwhite 132 B@g4 | -77 -> -870; -N (p 0.45) |
| hb-plan | 31 | d/a4 | Ablack 40 h7g6 | -16 -> -526; -P; partner +758 |
| hb-plan | 32 | e | Bblack 98 e6f6 | the partner had a forced mate at n=105; Bblack was mated first |
| hb-plan | 36 | a | Bblack 132 a5b6 | 0 -> M-4; -R (M-6 in its world); partner +1202 |
| hb-plan | 38 | h | Bblack 102 pass (stall_deny) | +1446 -> M-30; partner +2511 |
| hb-plan | 42 | a4 | Bblack 59 c7d6 | -198 -> -611; -B |
| hb-plan | 44 | c | Bblack 17 (opening) | lost from the opening, as in game 45 |
| hb-plan | 50 | d/c | Bblack 69 P@f7 (main e6e4, world_switch) | -217 -> -490; nothing arrived |
| hb-plan | 51 | a3 | Ablack 113 g8h7 | 579 -> M-4; -Q (p 0.40) |
| hb-plan | 53 | c | Bwhite 16 d4d1 (main d4d3, world_switch) | -20 -> -355, early |
| hb-plan | 54 | a2 | Bblack 112 B@b2 (main f4g5, world_switch) | 27 -> M-10; -N (p 0.58, move -146) |
| hb-plan | 57 | a4 | Ablack 49 b7b5 | -282 -> -733; -N |
| hb-plan | 62 | a4 | Bblack 121 h5g7 | 250 -> -340; -Q (p 0.45) |
| hb-plan | 65 | a4 | Bwhite 93 B@d7 (main b1c3, soft_switch) | -254 -> -654; -Q |
| hb-plan | 68 | c | Bblack 57 g4e5 | -72 -> -445; partner +949 |
| hb-plan | 69 | d/a4 | Bwhite 67 g5e7 | 220 -> -512; -Q (p 0.50) |
| hb-plan | 70 | a2 | Awhite 94 P@g2 (main B@h3, exposure_veto) | 245 -> M-4; -Q (p 0.67, move -484) |
| hb-plan | 71 | a3 | Ablack 147 g7f7 | 756 -> M-8; -R (p 0.50); partner +1143 |
| hb-plan | 72 | a4 | Awhite 50 h2h3 | 29 -> -749; -N (p 0.51) |
| hb-plan | 73 | d/a4 | Bwhite 47 P@d7 (main g1g2, world_switch) | -189 -> -689; -B |
| hb-plan | 74 | a2 | Bblack 83 h4h2 | 109 -> M-6; -R (p 0.17, move -503) |
| hb-plan | 77 | a4 | Ablack 50 N@e5 (main h8g8, world_switch) | -163 -> -636; -N (p 0.61) |
| hb-plan | 78 | a4 | Bblack 104 P@f3 | -276 -> -842; -Q |
| hb-plan | 80 | c | Bblack 77 g6g3 | -255 -> -542 |
| hb-plan | 83 | d/c | Ablack 18 (opening) | -312 at its first counted decision |
| hb-plan | 87 | c | Bwhite 70 P@c3 | -243 -> -327 |
| hb-plan | 88 | d/b2 | Bblack 67 Q@b1 | -144 -> -961; -Q in no world |
| hb-plan | 90 | d/a4 | Bblack 54 e7e6 | -19 -> -756; -Q (p 0.73) |
| hb-plan | 92 | d/g | Bblack 122 e7g5 (main d7c6, world_switch) | -211 -> -441; nothing arrived; the main move scored 300+ better |
| hb-plan | 96 | b2 | Bblack 40 e8f7 | -112 -> -1423; -Q in no world |
| hb-plan | 99 | c | Ablack 99 f8g7 | -114 -> -481; partner +972 |

### Four accounts

[show2.py prints any decision in full]

**hb-plan game 2, Awhite, n=89: a switch made for a told world that did not come (class g).**
- Main score +222. The main move was e1f2. The told line `P@e6 f8f7 d7c6 f5e6` (weight 0.6) gave two pawns away.
- Worlds:
  - none: p 0.19, e1f2 +251.
  - `-P`: p 0.42, e1f2 -73, N@c8 -618.
  - `-P-P`: p 0.30, e1f2 M-14, N@c8 -656.
- It switched to N@c8 to escape the `-P-P` mate. One pawn came (q=2), then a queen. Awhite fell to -785 at n=93.
- In the world that came first, the main move was 545 cp better.

**hb-plan game 21, Bwhite, n=60: +1519, then -608 four plies later.**
- The king was one rank up, with no shelter pawns, 3 king-zone squares attacked, and in check.
- The told line (`f1e1 N@e4 g4f5 c8f5`, a knight to Bwhite's opponent at ply 2) made the world `+B-N` p 0.44.
- In that world the main move g2g1 was M-4. It switched to g2g3, which cost 1355 cp with nothing arriving.
- The knight came. The switch was right in that world (-366 against M-4), and the game was lost anyway.
- The main search's +1519 was a large evaluation error in an exposed-king position. This is item 1 of section 5.

**hb-l50 game 17, Awhite, n=114 and 118: a known fatal queen (class a).**
- At n=114 (+652), the world `+Q+P-Q-R` (p 0.37) had every candidate mated (M-10, M-4, M-8).
- At n=118 (+283), `+Q-Q` (p 0.24) had every candidate mated again.
- The partner's own line had the queen capture. The queen arrived at q=1, and Awhite was mated.
- No move of Awhite's could change it; only its partner's could.

**hb-l50 game 34, Ablack, n=120: a stall that let the queen in (class h).**
- Score +241, in check, with 5 king-zone squares attacked. It sat (`stall_deny`) to deny a fed mate.
- The worlds `+B-Q-P` and `+B-Q` (p 0.34 and 0.24) had the main move f7f8 at M-2.
- The queen reached the opponent during the sit (q=0), and the next decision was M-4.

## 2. Where the evaluation was wrong

### The decisions that were most wrong

[calib2.py, `calib_plan-vs-l50.txt`, section "Most wrong"]

- **How often.** In 67 seat-games (39 of hb-l50, 28 of hb-plan), a seat of the losing team scored 0 or better
  and, within its next three decisions, was mated or fell to -800 or lower. In 45 of hb-l50's 57 lost games and
  28 of hb-plan's 43, the losing team had a decision at +500 or more at some point.
- **The largest errors:**
  - hb-plan 21 Bwhite n=60: +1519 to M-12.
  - hb-plan 38 Bblack n=102: +1446 to M-12 (the stall).
  - hb-l50 41 Bblack n=64: +1277 to M-4.
  - hb-l50 55 Bblack n=108: +1269 to M-2.
  - hb-plan 32 Bblack n=122: +1075 to M-6.
  - hb-plan 11 Bwhite n=94: +953 to M-2.
- **What separates wrong from right.** Among decisions at 0 or better, compare those followed by a collapse
  (458) with the rest (4,628). The collapses more often had:
  - the seat in check: 20.7% against 14.3%;
  - 3 or more king-zone squares attacked: 21.8% against 15.8%;
  - a partner behind by more than 300: 21.0% against 13.1%;
  - an opponent with an empty hand less often: 7.9% against 14.3%.

  The other features differ by less.

### Every feature against the score

The score is the engine's own: stated chance = 1/(1+exp(-cp/1000)). Two targets:

- **Collapse within 3** measures whether the score saw the danger coming. It is defined per seat, so it works
  for one side alone.
- **Game result minus stated chance.** For one engine alone this is nearly useless: every decision of one team
  in a game shares one result, and the intervals are ±0.15 or wider. I quote it pooled over both teams.

To add power I pooled this match (both sides, 9,665 moving decisions) with the hb-l50 seats of `alarm-vs-l50` and
`worlds5-vs-l50` and the hb-late50 seats of `late50-vs-np-b`. That makes 24,158 decisions from 400 games, all with
the baseline engine settings. Feature definitions are in `calib2.py`.

**Collapse within 3, linear model with score bands as intercepts** (coefficient = change in collapse probability):

| feature | 400 games pooled | plan-vs-l50, both sides | hb-l50 only | hb-plan only |
|---|---|---|---|---|
| 3+ king-zone squares attacked | **+0.092 (+0.073 to +0.117)** | **+0.096 (+0.062 to +0.135)** | **+0.108 (+0.061 to +0.161)** | **+0.079 (+0.030 to +0.135)** |
| king off its home rank | **+0.039 (+0.014 to +0.064)** | +0.010 (-0.031 to +0.046) | +0.019 (-0.036 to +0.085) | +0.007 (-0.036 to +0.062) |
| in check | **+0.027 (+0.009 to +0.044)** | +0.022 (-0.004 to +0.051) | +0.032 (-0.004 to +0.072) | +0.012 (-0.028 to +0.052) |
| king on the d or e file | **-0.030 (-0.044 to -0.017)** | **-0.028 (-0.052 to -0.006)** | **-0.051** | -0.006 |
| 0-1 shelter pawns | +0.012 (-0.001 to +0.025) | +0.004 | +0.019 | -0.007 |
| partner to move on the other board | **-0.032 (-0.042 to -0.022)** | **-0.023 (-0.035 to -0.009)** | **-0.032 (-0.054 to -0.010)** | -0.014 (-0.036 to +0.007) |
| partner behind (< -300, not mated) | **+0.053 (+0.033 to +0.069)** | **+0.051 (+0.017 to +0.086)** | +0.031 (-0.011 to +0.070) | **+0.069 (+0.021 to +0.114)** |
| partner ahead (> 300) | -0.009 (-0.019 to +0.004) | -0.007 | -0.019 | -0.001 |
| board material own minus opponent <= -3 | **+0.022 (+0.008 to +0.036)** | **+0.028** | **+0.031** | +0.025 |
| board material own minus opponent >= +3 | **+0.024 (+0.009 to +0.040)** | +0.024 (-0.002 to +0.051) | **+0.049** | +0.009 |
| own hand 4+ points and the move not a drop | **+0.015 (+0.004 to +0.026)** | +0.001 | -0.003 | +0.006 |
| we have a drop check | **+0.019 (+0.004 to +0.034)** | +0.014 | +0.006 | +0.020 |
| opponent hand 9+ points | +0.020 (-0.005 to +0.047) | +0.024 (-0.006 to +0.060) | +0.004 | +0.034 |
| opponent holds a queen | +0.015 (-0.014 to +0.046) | +0.024 (-0.020 to +0.074) | +0.050 (-0.015 to +0.123) | +0.005 |
| opponent holds a knight | +0.002 | -0.009 | -0.008 | -0.011 |
| opponent has a drop check | +0.003 (-0.012 to +0.018) | +0.015 | -0.005 | **+0.036 (+0.006 to +0.067)** |
| opponent has 3+ safe drop checks | +0.020 (-0.038 to +0.074) | +0.024 | +0.051 | -0.008 |
| a queen in its hand would have 3+ safe drop checks | +0.011 (-0.019 to +0.041) | +0.003 | -0.005 | +0.006 |
| team has the time advantage | -0.006 | -0.001 | -0.007 | +0.004 |

Bold: the interval excludes 0. The size of the strongest effects, on decisions scored -300 to +300 (400 games;
base collapse rate 9.5%):

| condition | collapse rate with | collapse rate without |
|---|---|---|
| 3+ king-zone squares attacked (1,311 decisions) | 20.5% | 8.2% |
| king off its home rank (1,033) | 20.2% | 8.5% |
| king two or more ranks up (134) | 40.3% | 9.2% |
| in check (1,289) | 18.1% | 8.5% |
| opponent holds a queen (1,188) | 16.3% | 8.8% |
| opponent hand empty (1,561) | 5.1% | 10.2% |
| partner to move on the other board (5,797) | 8.3% | 10.8% |

**Game result minus stated chance, linear model, 400 games pooled** (only the terms whose interval excludes 0):

- 3+ king-zone squares attacked: -0.059 (-0.090 to -0.028).
- 0-1 shelter pawns: -0.043 (-0.080 to -0.004).
- Opponent hand 9+ points: +0.046 (+0.012 to +0.080). Opponent holds a knight: +0.036 (+0.002 to +0.071).
- Own hand 4+ and the move not a drop: -0.024 (-0.042 to -0.008).
- Board material behind by 3+: +0.042 (+0.002 to +0.075).
- Partner behind: -0.113. Partner ahead: +0.142. Partner mated: -0.428. Partner mating: +0.429.
- Stated chance above 0.5: -0.061 (-0.096 to -0.026).

On plan-vs-l50 alone (both sides pooled), only these hold: the partner terms (behind -0.139, ahead +0.123),
opponent holds a knight (+0.060, +0.011 to +0.109), and own hand 4+ unused (-0.035, -0.060 to -0.010).
King-zone attacked there is -0.036 (-0.086 to +0.014).

**What carries signal after the score:**

- **King danger: real.** It is the largest position feature by far and has the same sign everywhere.
  - 3+ king-zone squares attacked: +9 points of collapse risk in each of the four columns, and -6 points of
    result.
  - A king off its home rank, a king two ranks up and being in check point the same way.
  - This contradicts the 2026-11-10 loss analysis (no king effect once the score is known). It confirms
    AUTOPSY.md's -9 points for a king off its home rank, with a better measure.
- **The partner's board: real**, and the largest effect on the result.
  - The partner's score predicts the team's result as well as the seat's own; AUTOPSY.md found the same.
  - A partner behind also makes the seat's own collapse more likely, by 5 points.
- **Whose move on the other board: real** for collapse (-3.2 points pooled) and for hb-l50 alone. Mechanically,
  while the partner is to move, the partner's opponent cannot capture, so nothing reaches our opponent's hand
  before the partner moves. The engine's score is one board's and does not see it.
- **Hands: no signal for collapse once the score is known.** Opponent hand 9+, an opponent queen in hand, drop
  checks, safe drop checks and queen drop checks all cross 0. Their large raw differences (opponent queen 16.3%
  against 8.8%) are already in the score.
  - The result model's +4.6 for an opponent holding 9+ points is AUTOPSY.md's "hands overvalued" (+8.7) again.
    `HBHandDiscount=30` already lost that test.
- **Unused own hand: small.** +1.5 collapse and -2.4 result, pooled. Both intervals exclude 0, but the effect is
  small.
- **Material imbalance: small and two-sided.** About +2 points of collapse either way. Imbalanced positions are
  volatile.
- **Clocks: selection, not signal.** "Own clock under 20 s" (+33 points of result in this match) is a seat
  sitting while its partner mates, as AUTOPSY.md explained.
- **Overconfidence.** The stated chance is too far from 50%: -0.061 above 50% (pooled). In this match alone it is
  -0.037 (-0.099 to +0.023), so 100 games cannot show it.
- **World values are not biased.** When a piece reached the opponent, the coordinator world's value of the move
  played was within 3 cp of the next decision's score on average, for both engines (CIs about ±25). With nothing
  arriving, worlds read 27 to 29 cp lower than the next score [sides.py]. The a4 falls are not world searches
  being optimistic on average.

## 3. What more depth would and would not have found

**The falls at the turning points** [losses_q3.py]

| | hb-l50 | hb-plan |
|---|---|---|
| sudden mates at the turning point (mated seat or partner, whichever fell first) | 16 | 11 |
| ... seen by the seat's worlds (move mated there, at pre or before the partner's decision) | 9 | 3 |
| ... the capture was only in the partner's own main line | 5 | 6 |
| ... nobody | 2 | 2 |
| decisive drops (not mate) with a piece to the opponent | 36 | 28 |
| ... seat's worlds said it cost 300+ before the partner's decision | 20 | 15 |
| ... partner's line only | 7 | 8 |
| ... nobody | 9 | 5 |
| falls with nothing arriving / no decision before | 5 | 4 |
| best candidate at least 200 cp better than the move played in the fatal world at pre | 3 of 42 scored | 2 of 31 scored |

**Depth, for the sudden mates at turning points:**

- **Seen** (the world search had the mate; depth was enough): 6 and 3.
- **Move not scored** in the world that held the piece: 4 and 3.
- **Scored survivable, mate longer than the world's depth**, so more depth might have found it: 2 and 3.
- **Scored survivable, mate within the world's depth**: 2 and 1. A search of that depth should have seen the
  mate, so the arrival assumptions are a more likely cause than depth.
- **Piece in no world**: 2 and 1. No depth of the seat's own search helps here.

**All collapses**, in won games too [visibility.py: a decision at -300 or better followed by a forced mate at the
next decision]:

| | hb-l50 | hb-plan |
|---|---|---|
| collapses | 20 in 19 games (0.20 a game, CI 0.12 to 0.29) | 18 in 18 games (0.18, CI 0.11 to 0.26) |
| the move played was mated in the piece's world | 7 | 4 |
| scored survivable, mate longer than the world depth | 3 | 7 |
| scored survivable, mate within the world depth | 2 | 1 |
| not scored | 5 | 4 |
| in no world / nothing arrived | 2 / 1 | 2 / 0 |
| the capture was in the partner's own line (at that ply or later) | 15 of 19 | 14 of 18 |
| fatal piece a queen | 9 | 7 |
| median mate length at the next decision | 6 plies | 8 plies |

What this says:

- **The bottleneck is not knowledge on the seat's side.** In most falls the seat's worlds priced the fatal piece,
  or the partner's own line had the capture, and the seat had no candidate that did better in that world.
  - The decision that could have changed the outcome was the partner's: the capture was in its own line in
    roughly three of four collapses. AUTOPSY.md found the same.
  - The partner-side remedies were tested and did nothing: Alarm went 51-49 and table25 went 47-53.
- **More search depth is a small lever.** World searches that missed a mate by depth explain 2 hb-l50 and 3
  hb-plan losses. Searches that saw it, or forecasts that missed the piece entirely, explain more.
  - hb-plan's collapses include 7 "scored survivable, mate beyond the world's depth" against 3 for hb-l50. The
    told line adds a world, so each world gets less search. The numbers are too small to tell.

## 4. Does hearing the partner's line change anything?

[sides.py, `sides_plan-vs-l50.txt`. "plan": the told line was added (3,884 decisions). "own": refused,
`own_hands` 1,169, `own_reply` 463, `own_none` 100, `own_no_lines` 9. The groups are not comparable as an
experiment: a message is refused exactly when the partner's board went somewhere the teller did not expect. The
fair comparison is hb-plan against hb-l50, the two columns of the same games.]

| measure | hb-plan | hb-l50 | difference (95%) | hb-plan: plan | hb-plan: own |
|---|---|---|---|---|---|
| world Brier (arrived by q<=4) | 0.210 | 0.201 | **+0.009 (+0.003 to +0.016)** | 0.214 | 0.202 |
| p given to what really arrived by q<=2 | 0.399 | 0.364 | **+0.035 (+0.027 to +0.044)** | 0.417 | 0.359 |
| what arrived was in no world | 19.6% | 21.4% | **-1.7 (-3.1 to -0.2)** | 17.7% | 24.2% |
| arrival worlds per decision | 2.39 | 2.56 | **-0.17** | 2.33 | 2.52 |
| a piece in no world reached the opponent (surprise) | 5.0% | 4.6% | +0.4 (-0.4 to +1.2) | 4.0% | 7.4% |
| ... a queen in no world | 1.0% | 0.5% | **+0.5 (+0.2 to +0.9)** | 0.8% | 1.4% |
| switched away from the main move | 19.5% | 17.3% | **+2.2 (+0.6 to +3.8)** | 20.6% | 17.0% |
| switch: change of score by the next decision | -41 cp | -60 cp | +19 (-20 to +60) | -66 | +27 |
| kept: change of score by the next decision | +23 | +15 | +8 (-12 to +30) | +19 | +32 |
| switch: played minus main, in the world that came | +109 | +105 | +4 (-29 to +38) | +106 | +116 |
| switch: cost if nothing arrives | 62 cp | 55 cp | +8 (-11 to +25) | 67 | 50 |
| sits (all reasons) | 5.5% | 6.7% | -1.2 (-3.2 to +0.7) | 3.4% | 9.8% |
| collapses per decision | 0.3% | 0.4% | -0.0 | 0.4% | 0.2% |
| drops of 400+ by the next decision | 11.5% | 11.2% | +0.3 (-1.5 to +1.9) | 12.2% | 9.9% |
| main depth / nodes | 14 / 267k | 14 / 266k | 0 | | |

**World calibration by stated p**, arrived by q<=2 / q<=4 (decisions with 6+ plies left):

| stated p | hb-l50 | hb-plan, plan | told world (whole told package) | other worlds at the same decisions |
|---|---|---|---|---|
| 0.20-0.35 | 0.26 stated: 24.0% / 38.8% (3,073) | 0.29: 23.7% / 40.6% (2,563) | **0.31: 2.9% / 22.1% (1,399)** | **0.26: 48.7% / 62.9% (1,164)** |
| 0.35-0.50 | 0.41: 30.3% / 50.0% (1,041) | 0.40: 24.0% / 52.6% (713) | 0.40: 8.3% / 42.9% (553) | 0.40: 78.1% / 86.3% (160) |
| 0.50-0.70 | 0.57: 53.2% / 68.4% (374) | 0.59: 55.9% / 69.6% (644) | 0.59: 55.1% / 69.0% (622) | - |
| 0.70-1.00 | 0.80: 70.0% / 79.4% (170) | 0.78: 76.8% / 86.4% (177) | 0.78: 76.8% / 86.4% (177) | - |

**Where the told line helps:**

- When the told line has one immediate capture, its world is stated at 0.5 to 0.8 and comes true about as stated
  (55% to 77% by q<=2). That is where hb-plan's better "p given to what came" (+0.035) comes from.
- Arrivals in no world are 1.7 points rarer.
- hb-plan saw itself mated first in fewer games: 45 (lost 42) against 55 (lost 54).
- hb-plan's team won 7 of the 48 games in which one of its seats sat mated (`hold_mated`), against 2 of 57 for
  hb-l50. That is suggestive at best, Fisher p about 0.07.

**Where it hurts:**

- **The told line's full package is overweighted.** When the told line has a capture at ply 2 or later, that
  whole package gets p of about 0.31, and it came true within four plies in 22% of 1,399 cases. The sub-packages
  beside it, stated at 0.26, came true 63% of the time.
  - 0.31 is very likely `HBPlanTrust` 60% times `HBForecastTrustLate` 50%. That is inference from the numbers;
    I did not read the code.
  - The seat therefore insures against far-off told captures, as in game 2, where the main move was 545 cp
    better in the world that came. That raises its switch rate.
- **More switches, more of them before falls.** Under the told line hb-plan switched in 20.6% of decisions,
  against 18.4% to 18.8% when refusing it and 17.3% for hb-l50 [sides.py].
  - Before a 400+ drop: 39.4% of hb-plan's decisions under the told line were switches, against 21.6% under its
    own forecast. For hb-l50 it was 31.5% (117 of 372) [switch_control.py].
  - 13 of hb-plan's 40 turning points were switches under the told line. Switches happen where danger is seen,
    so this is association, not proof. The g rule, which needs the main move to have been 300 cp better in the
    world that came, caught only 1 game per side.
- **More queens in no world**: 1.0% against 0.5% of decisions. The told line takes one of the `HBMaxWorlds` = 4
  slots, leaving 0.17 fewer worlds a decision for the seat's own search.

**What it does not change:** collapses (0.18 against 0.20 a game), drops of 400+ (11.5% against 11.2%), clocks,
search depth and nodes.

**Did the plan let the seat warn back?**

- In 12 of hb-plan's 39 falls with a fatal piece, the told line held that piece at the seat's last decision
  before the partner gave it. In 8 of those (games 2, 3, 8, 11, 21, 42, 80, 90) the seat's own worlds also
  priced it as a mate or 300+ cp [plan_alarm_bound.py].
- At the turning point itself, the told line held the fatal piece in 22 of 27 plan decisions. By then the
  partner had usually already moved.

**Overall:** the told line makes forecasts sharper where the capture is immediate and overconfident where it is
late. The +14 game score margin cannot be pinned on either part: the match CI includes 0, and its class
differences (sudden mates 9 against 14, partner first 10 against 14) are within noise for 43 and 57 losses.

## 5. What to improve, ranked

The bound is the number of lost games in this match that had the property at the turning point (`bounds2.py`).
It is an **upper bound**, not a forecast of games saved: no replay shows that the changed decision would have
held.

**1. A king-danger correction (evaluation, or the coordinator's winning chance).**
- *The data shows:*
  - 3+ king-zone squares attacked raise the 3-decision collapse risk by 9.2 points net of the score (CI 7.3 to
    11.7, 400 games). The effect holds on each side of this match alone (+10.8 hb-l50, +7.9 hb-plan) and lowers
    the result by 5.9 points.
  - A king off its home rank (+3.9) and being in check (+2.7) point the same way. A king two ranks up collapsed
    40% of the time at a level score.
  - 3+ king-zone squares were attacked at 22 of hb-l50's 56 turning points and 13 of hb-plan's 41, against about
    12% of level decisions.
  - Examples: hb-plan 21 (+1519 with 3 king-zone squares attacked, in check), hb-l50 34 (5 attacked), hb-l50 20
    (7 attacked, king three ranks up).
- *Bound:* 31 of 57 (hb-l50) and 19 of 43 (hb-plan) turning points had a king-danger flag (3+ king-zone
  squares attacked, king off its home rank, or in check).
- *How to test:* this needs a build. No option covers it: `HBPhantom` asks a different question and lost as F1.
  - The cheapest version leaves the NNUE alone. In the coordinator's E, widen the uncertainty, or subtract a
    term, when the king zone is attacked. Size the term from these tables: about 0.09 of collapse at 3+ attacked
    squares.
  - Before a match, rescore the logged `hb_coord` candidates and count the decisions whose choice changes, as
    AUTOPSY.md proposed for item 5.
- *Could backfire:* the net already sees attackers, so a term can double-count them and make the seat passive.
  King-zone attacks also go with attacking chances of our own: the tables do not separate "we are attacked" from
  "the position is sharp".

**2. A team winning chance in E: weigh moves with the partner's score.**
- *The data shows:* net of the seat's own score, a partner behind costs 11 to 14 points of result and a partner
  ahead adds 12 to 14 (CIs about ±5, both samples). A partner behind also raises the seat's own collapse risk by
  5.3 points. Partner-first losses are the second-largest class: 14 and 10 games.
- *Bound:* the partner was behind at 11 and 9 turning points and ahead at 16 and 15. The 24 class-d games are
  where team-aware choices matter most.
- *How to test:* this needs a build. The spec direction is PARTNER_TALK.md "Team winning chance" plus the
  two-board surface work. First check from logs how many logged decisions would change.
- *Could backfire:* a seat that gives up its board for a partner who is ahead feeds the opponent pieces. The
  table match at half share (5-19) is that failure mode.

**3. Fix the told line's late-capture weight (hb-plan).**
- *The data shows:* told-package worlds stated at 0.31 came true in 22% of 1,399 cases within four plies (2.9%
  by the next move), while their sibling worlds at 0.26 came true in 63%. hb-plan switches 2.2 points more than
  hb-l50, and 39% of its plan-decisions before a 400+ drop were switches against 22% under its own forecast.
- *Bound:* 13 hb-plan losses had a switch under the told line at the turning point: 2, 5, 7, 11, 13, 21, 26, 50,
  54, 65, 70, 77, 92.
- *How to test:* option-only.
  - `HBPlanTrust=30` against `HBPlanTrust=60` (both hb-plan, `L50d`). Read the Brier score and the told-world
    calibration in the post-mortem (`sides.py --worlds`) and the switch rate.
  - A cleaner fix needs a build: trust only the told line's first capture, or give its late captures the
    measured 0.2.
- *Could backfire:* the told line is the likeliest reason hb-plan scored 57%. Its immediate-capture worlds are
  well calibrated, and lowering the trust lowers those too.

**4. `HBWinScale=1200`, the overconfidence fix (option-only, queued as F16).**
- *The data shows:* pooled over 400 games, stated chances above 50% come true 6.1 points less often (CI 2.6 to
  9.6). In this match alone it is -3.7 (CI -9.9 to +2.3), so this match neither confirms nor refutes it.
- *Bound:* small. It changes only close choices between candidates.
- *Test:* `ws1200-vs-l50` as queued, or against hb-plan if item 3 changes the default.
- *Could backfire:* a flatter curve also makes the seat value safe material less, and the gain in log loss
  AUTOPSY.md measured was small.

**5. `HBStall=false`, and the stall sits.**
- *The data shows:* the team won none of the 13 seat-games with a `stall_deny` sit (hb-plan 5, hb-l50 8).
  AUTOPSY.md found 3 wins in 15. A stall sit was the turning point in 3 losses: hb-l50 34 and 79, hb-plan 38. In
  game 34 the queen arrived during the sit.
- *Bound:* 3 games, plus 10 more lost games with a stall sit somewhere.
- *How to test:* option-only, `HBStall=false` against the current setting.
- *Could backfire:* stalling happens when a fed mate is already pending, so these games may be lost whatever
  the seat does. The logs show only the branch taken.

**What the data does not support:**

- **More world depth.** It explains 2 and 3 losses.
- **More worlds or a broader forecast.** Arrivals in no world were the first cause in 5 and 1 losses.
- **A back-channel alarm or worth message.** Its bound here is 8 hb-plan losses where the told line held the
  fatal piece and the seat's worlds priced it in time, but T1 (51-49) and T2f (47-53) already found no effect.
- **Missed supplies and clocks.** Neither was a first cause in any loss.
- **Slow losses.** The 8 and 7 class-c games and the 7 c-type partner falls are untouched by everything above
  except item 1. At 6 of the 19 turning points of these games (c, and d with a c-type partner fall) 3+ king-zone squares were attacked.

## What the logs cannot say

- Whether the partner had a playable alternative to the capture that gave the fatal piece. That needs a replay of
  those decisions.
- Whether a move outside the coordinator's 3 to 5 candidates escaped. "Escape gain" uses only the scored
  candidates.
- Whether the switches cause falls or only mark the dangerous positions. Only an option match can tell, for
  example item 3.
- The cost of items 1 and 2 in won games.

## Scripts

All in `logs/loss-analysis/autopsy2/`, run with `nice -n 19 python3`. `run_all.sh` reruns the pass on
plan-vs-l50.

- `common2.py`: rows, extras and features per match; caches in `cache_<match>.pkl`. Also builds the caches for
  `alarm-vs-l50`, `worlds5-vs-l50` and `late50-vs-np-b`.
- `classify2.py`: timelines, turning points and first causes for both sides. It reuses `autopsy/timeline.py` and
  `autopsy/classify.py`. Writes `lost_<match>.json` and `classes_<match>.txt`. Also run on `alarm-vs-l50`, where g
  and h are just as rare (1 and 1 first causes among 100 losses).
- `losses_q3.py`: who could see each fall, the escape gain and depth (`q3_*.txt`).
- `visibility.py`: every collapse (`collapses_*.txt`).
- `sides.py` (`--worlds`): section 4 (`sides_*.txt`).
- `switch_control.py`, `plan_alarm_bound.py`, `bounds2.py`: the switch control, the plan-then-alarm bound and
  section 5's bounds.
- `calib2.py` (`--more` for 400 games): section 2 (`calib_plan-vs-l50.txt`, `calib_more.txt`).
- `gen_table2.py`: the per-game table (`table_plan-vs-l50.md`).
- `show2.py MATCH GAME SEAT N`: one decision in full.
- `method.md`: the definitions as first drafted.
