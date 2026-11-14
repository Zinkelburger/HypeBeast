# Autopsy 3: what loses a board first (hb-l50, 700 games)

Written 2026-11-12, 00:50 to 01:45, by an Opus session, from logs only: no engine was run, built or stopped,
and nothing here was match-tested. Scripts and outputs are in `logs/loss-analysis/autopsy3/` (git-ignored);
`run_all.sh` rebuilds everything in about 3 minutes, one niced Python process at a time. A name in brackets after
a claim is the output it comes from. The suggestions at the end are for Fable to judge.

## Summary

**The question** (EXPERIMENTS.md, night of 2026-11-11): the sudden mate is mostly how a lost board ends, so what
makes the board fall in the first place? For every hb-l50 seat of `plan-vs-l50`, `plan-vs-l50-b`, `plan-c`,
`kd60-vs-l50`, `matefree` and `matekeep` (700 games, 1,400 seats, 79,394 decisions, all matched to games) I took
the first decision after which its score stays below -300 for the rest of the game and classified the largest
step among the three steps into it.

**Answer: a piece arrives from the partner board.** 635 seats fell, 536 of them on teams that lost and 99 on teams
that won anyway. In 263 (72%) of the 364 falls that were the team's first in a lost game, the key step was a
piece reaching the opponent's hand [report3_l50.md]:

| what made the board fall (key step) | all falls | team's first fall, lost games |
|---|---|---|
| a piece arrived that the seat had forecast, and every candidate it compared fell in that world (A5) | 276 | 176 |
| a piece arrived that was in no forecast world (A1) | 86 | 57 |
| a piece arrived; its world had the move holding, and the fall was deeper than the world said (A3) | 46 | 21 |
| a piece arrived; another candidate held in its world (A4) | 13 | 9 |
| own board, after a switch away from the main move (C5) | 62 | 25 |
| own board: the reply its line expected (C2) / another reply (C3) / a mate appeared (C1) | 23 / 26 / 19 | 12 / 17 / 12 |
| a sit (H) | 27 | 11 |
| slide, no step of 200 cp (S) | 36 | 13 |
| a switch that went wrong (G) | 18 | 9 |
| lost from the first decision (O) | 3 | 2 |

The order of the classes is the same in each of the six matches.

**What the 421 arrival falls (A1 to A5) have in common:**

1. **The seat saw it coming, and could not dodge it.** The piece was in a scored world in 335 of 421, at a median
   p of 0.27. In the biggest class (A5) the move played went from -50 in "nothing arrives" to -774 in that world,
   and the best candidate compared there was no better (-748). At the two decisions before, the world holding that
   piece again had no candidate 200 cp better in 155 of 276, no world held it in 87, and a candidate that held
   existed in only 8. The seat's own forecast of a fall is roughly calibrated. When its worlds put 0.60 on the move
   played falling below -300, it did so at the next decision 48% of the time; at 0.27, 24%; at 0, 2.9%
   [hazard_l50.txt].
2. **The partner's move that let the piece go cost the partner's board nothing.** The partner's own score changed
   by a median of +0 from that decision to its next, while ours fell a median of 879 cp. The two-board sum fell by
   more than 300 in 371 of 421, and the partner's gain covered our loss in 17 [partner_net.txt].
3. **It was usually the second half of a trade the partner began.** In 302 of 421 our partner had captured on its
   board within the three plies before; that piece reached our hand first, and the fatal piece was the
   recapture. The pairs were: we got a pawn and they got a queen 47 times, queen for queen 41, knight for queen
   27 [trades.txt]. The trade is even on the partner's board and uneven on ours.
4. **The partner's own search knew.** The capture was the reply in the partner's own main line in 249 of 421
   (59%). In 111 (26%) the partner had switched away from its main move (17.4% of all its decisions are switches).
   In 48 of those its main move left no capture of that piece at once, and scored a median 78 cp *better* for
   the partner's own board [partner_switch.txt, partner_alt.txt].
5. **The cost was measured on our side and never reached the partner.** Before the fall, our forecast had
   measured the fatal piece at 500 cp or more in 197 of 421 (queens: 128 of 183). hb-l50 has `HBFeedPrices=false`
   and does not talk, so none of this reaches the partner's search. When the partner's line hands our opponent a
   queen we had priced at 500 or more and that reply is played, we fall for good within two decisions 18.8% of
   the time (95% 13.7 to 23.4), against 7.7% when it is not played. For rooks it is 21.0% against 9.7%. Minor
   pieces and pawns show little difference [hazard_l50.txt].
6. **Mostly queens and rooks, mostly not mates at once.** The fatal piece was a queen in 183 of 421 and a rook in
   59. They are 148 of the 263 team's-first arrival falls in lost games (56%). The step ended in a forced mate in
   111 of 421.

**What did not matter:** the partner was sitting during the fall in 8 of 632 falls, and the seat's clock was 5 s or
more behind in 27. More depth at K would rarely have helped. At N the fall shows at depth 1 in 435 of 632 (the
piece in hand is enough), and K's own score fell with depth in 67. Moves the seat's own worlds showed to be
better, and cheap where nothing arrives, existed in 31 falls, 18 of them the G class by definition.

**Cross-check with the floor guard.** In `guardfloor-vs-l50` (100 games, the 63-37 match) the hb-guardfloor seats
fell 74 times and the hb-l50 seats 114. Arrival falls were 41 against 81, and A5 33 against 53. Own-board falls
with the expected reply (C2) went the other way, 11 against 3 [report3_guardfloor_guardfloor-vs-l50.md,
report3_l50_guardfloor-vs-l50.md]. **Added 02:20:** on the 300 new games of `guardfloor-b` (157-143) this did not
repeat. The guard's seats fell 282 times against 270, arrival falls were 180 against 202 (A5 122 against 139), and
own-board falls 65 against 46 [falls_guardfloor_guardfloor-b.json, falls_l50_guardfloor-b.json]. Over the 400
games, the guard cuts arrival falls by about a quarter (221 against 283) and adds own-board falls.

**Replication on new games (added 02:25).** The hb-l50 seats of `guardfloor-b` are 300 games on 150 openings that
appear in none of the six matches, played on `bin/hypebeast-v8h` with the guard off. They give the same picture
[report3_l50_guardfloor-b.md]:

| | six matches (700 games) | guardfloor-b hb-l50 seats (300 games) | guardnone-b hb-l50 seats (300 games) |
|---|---|---|---|
| falls | 635 | 270 | 278 |
| team's first fall in lost games that was an arrival | 263 of 364 (72%) | 130 of 157 (83%) | 100 of 139 (72%) |
| largest class | A5, 276 | A5, 139 | A5, 119 |
| arrival falls with the capture in the partner's own line | 249 of 421 (59%) | 109 of 202 (54%) | 108 of 177 (61%) |
| fatal piece a queen or rook | 242 of 421 (57%) | 106 of 202 (52%) | 99 of 177 (56%) |
| our forecast had priced the fatal piece at 500 or more | 197 of 421 (47%) | 90 of 202 (45%) | 72 of 177 (41%) |
| the partner sat during the fall | 8 | 5 | 4 |

The guardnone-b column (added 04:55) uses the same 150 openings as guardfloor-b, so it is not independent of it in
the first 20 or so plies. After that the games part (see EXPERIMENTS.md, item 3) [report3_l50_guardnone-b.md].

## Data and definitions

- **Matches.** `plan-vs-l50` (`bin/hypebeast-v8d`), `plan-vs-l50-b`, `plan-c` (200 games), `kd60-vs-l50`,
  `matefree`, `matekeep` (all `bin/hypebeast-v8g`). In each game one team is hb-l50 (`HBFeedPrices=false,
  HBForecastTrustLate=50`, 500,000 nodes) and the other is the contender. Only the hb-l50 seats are classified;
  a seat's partner is the other hb-l50 seat.
- **Rows** [common3.py]. The rows are `scripts/postmortem.py`'s `collect()` plus these fields from the engine logs:
  the whole `hb_summary`; the main search's score at each depth; every coordinator world with each candidate's
  value; the forecast's measured prices (`hb_forecast` `prices`); the clocks; both boards' FENs with hands; and
  AUTOPSY2's position features (king, hands, drop checks). 0 decisions were unmatched and 0 lacked the extras.
- **Rules** (`falls.py` docstring):
  - *F* is the first decision whose score, and every later score, is below -300. The *key step* is the largest
    drop among the up to three steps into F (scores clipped to +-3000; ties go to the later step). *K* is its
    first decision and *N* its second. In 548 of 632 falls the key step is the last one into F.
  - An *arrival* is a piece our opponent's partner captured on the other board between K and N; it reaches our
    opponent's hand. The *matching world* is chosen among K's scored worlds whose "-" pieces include every "-"
    piece that arrived: the one whose whole package is closest to what arrived (both signs), then the largest p.
    The *arrival cost* is the move played's value in "none" minus its value in the matching world, or else the
    forecast's measured price. The arrival explains the step if the cost is unknown or at least min(300, half
    the drop).
  - Classes, first rule that applies:
    - O: F is the first decision.
    - S: the drop is smaller than 200.
    - H: K was a sit (hold_partner, hold_feed, stall_deny, voluntary_wait).
    - G: K switched away from the main move and, in the world that came true, the main move scored 300 or more
      higher, or was not mated where the move played was.
    - A1 to A5, an arrival explains the step: no world held it; the move played was not scored there (none
      occurred); the world had the move at -300 or better; it had the move below -300 and another candidate at
      -300 or better; every candidate was below -300.
    - C1 to C5, otherwise: N is a forced mate; the opponent replied with the second move of K's main line;
      another reply; no reply (none occurred); K played a move other than its line's first move.
  - **One rule was revised after the first run.** The matching world had been the largest-p world holding the
    pieces, which matched plan-vs-l50-b 66 Ablack to `+Q-R-P` (p 0.20) when only `-R` came (`-R` had p 0.14). The
    closest-package rule moved 55 of 635 falls between classes. The arrival falls rose from 403 to 421 (A5 263 to
    276, A3 41 to 46, C2 32 to 23, C5 70 to 62), and every conclusion above holds under both rules. The first
    run's output is kept as `falls_l50_rule1.json` and `report3_l50_rule1.md`.
- "Candidates" are the 2 to 5 moves the coordinator scored in its worlds (median 3), not every legal move. "Every
  candidate fell" says nothing about the moves it did not compare.
- Intervals are 95%, from 2,000 resamples of whole games.

## 1. Classes

Counts per match and the flags at K are in `report3_l50.md`. Game lists are in `classes_l50.txt` (game, board,
colour; `*` when the team won anyway).

| class | n | K → N (medians) | N a forced mate | team lost |
|---|---|---|---|---|
| A1 arrival in no world | 86 | +4 → -1056 | 33 | 75 |
| A3 arrival, its world had the move holding | 46 | +425 → -270 | 4 | 33 |
| A4 arrival, another candidate held | 13 | +23 → -590 | 2 | 11 |
| A5 arrival, every candidate fell | 276 | +10 → -866 | 72 | 247 |
| C1 own board, a mate appeared | 19 | +65 → mate | 19 | 17 |
| C2 own board, the reply K's line expected | 23 | -104 → -483 | 0 | 18 |
| C3 own board, another reply | 26 | -108 → -558 | 0 | 25 |
| C5 own board, after a switch | 62 | -156 → -664 | 0 | 51 |
| G switch that went wrong | 18 | -16 → -549 | 1 | 16 |
| H sit | 27 | +105 → -837 | 11 | 13 |
| S slide | 36 | -227 → -318 | 0 | 28 |

- **Falls are steps, not slides.** 548 of 632 key steps are the last step into F, and 427 of 632 drop by 500 cp
  or more in that one step. 451 of the 635 falling seats were mated in the end.
- **Almost every loss has a fall.** 364 of 366 lost games have a hb-l50 seat falling. Of the other 2, one was a
  flag and one a mate with no decision below -300 before it. In 172 games both seats of the team fell.
- **Mating races are rare as first falls.** 4 falls start from a forced mate for us. A forced mate for the team
  (ours, or the partner's last score) stood at K in 42 falls, and the team won 36 of those because the partner mated
  first. 14 of the 42 are sits (H), mostly `hold_partner` while the partner mates.

## 2. Arrival falls (A1 to A5, 421)

| class | n | fatal piece Q / R / B / N / P | world p (median) | move played: "none" → its world (medians) | best candidate there | seen at 1+ of the 2 decisions before |
|---|---|---|---|---|---|---|
| A1 | 86 | 38 / 14 / 10 / 21 / 3 | - | -107 → - | - | 36 |
| A3 | 46 | 21 / 4 / 6 / 13 / 2 | 0.28 | +421 → -158 | -108 | 30 |
| A4 | 13 | 2 / 1 / 2 / 5 / 3 | 0.16 | +39 → -384 | -176 | 11 |
| A5 | 276 | 122 / 40 / 30 / 54 / 30 | 0.27 | -50 → -774 | -748 | 173 |

**A1, the piece was in no world (86).** Two different cases:
- 32 had no forecast at all at K: `only_move` (24, a single legal move, usually out of check) or `no_arrivals`
  (8).
- 54 had scored worlds that did not hold the piece. 39 of them were at the cap of four scored worlds ("none"
  plus three; 62% of all decisions are at the cap). In 25 the forecast had measured the piece's price, so one of
  its lines held it, but that line's package was not among the worlds scored. 19 of those prices were 500 or more.
  In example 4 below, `-R` was priced at 850 and no world held it.

**A3, the world said the move held (46).** The world foresaw much of the drop (+421 to -158) and the real score was
lower (-270 median at N). In most of them the fall is a little deeper than the world said. Example 7 is the
exception: the world said +683 and the truth was mate in 4.

**A4, another candidate held (13).** This is the only class where the seat's own worlds had a way out. In 9 of
them a candidate scored 200 or more better in the world that came true, and in 2 of those 9 it also cost 100 or
less in "none". The coordinator weighs a world by its p (median 0.16 here) and kept the move that was best on
average.

**A5, every candidate fell (276).** It compared three moves (median), and all were about 750 cp worse in the world
that came true. 110 of the 276 were in check at K, and 117 had three or more king-zone squares attacked. At the two
decisions before K:

| the world holding that piece at the two decisions before K | n |
|---|---|
| no candidate 200 cp better | 155 |
| no world held the piece at either | 87 |
| a candidate 200+ cp better, not holding | 26 |
| a candidate held where the move played fell | 8 |

So within its own candidates the seat had no defence even two decisions earlier.

**The partner's side of it** [partner_net.txt, trades.txt, partner_switch.txt, partner_alt.txt]:

| | A1 | A3 | A4 | A5 | all 421 |
|---|---|---|---|---|---|
| partner's score at the feeding move (median) | +88 | -42 | -159 | -114 | -80 |
| partner's change by its next decision (median) | +0 | +0 | +0 | +0 | +0 |
| our drop (median) | -1183 | -686 | -583 | -888 | -879 |
| two-board change below -300 | 81 | 36 | 12 | 242 | 371 |
| the capture was the reply in the partner's own main line | 49 | 29 | 5 | 166 | 249 |
| the partner had switched away from its main move | 27 | 11 | 5 | 68 | 111 |
| one of the partner's compared candidates left no capture of that piece at once | 49 | 18 | 2 | 107 | 176 |
| ... and was within 150 cp on the partner's own board | 35 | 11 | 1 | 63 | 110 |

- In 302 falls our partner captured first and the fatal piece was the recapture. In 84 the partner took back
  only after, and in 35 our partner made no capture within three plies. When it took back after, our piece
  reached our hand before N in 23 of 84.
- At the feeding move the partner itself was below -300 in 159 of 421, between -300 and +300 in 152, and above +300
  in 110. The two-board change is worst when the partner was ahead (median -1644): a winning partner trading
  pieces it does not need.
- Median two-board change by piece: queen -1391 (183 falls), rook -1101 (59), bishop -678, knight -683, pawn -574.
- "Left no capture of that piece at once" is geometry (python-chess on the partner's board): after the
  candidate, the opponent's partner has no legal capture of a piece of that type. It does not rule out other losses.

## 3. Falls on the seat's own board (C, G, H, S: 211)

- **After a switch (C5 62, G 18).** 57 of the 62 C5 falls followed a switch at K (51 `world_switch`, 6
  `exposure_veto`). By the worlds' own numbers the switch was right: in the world that came true, the move played
  scored better than the main move in 44 of the 55 where both were scored. Our board fell anyway, mostly by
  captures on it (the opponent took a pawn in 17 and a knight or queen in 6 each). The worlds are searched at the
  common depth (10 to 11), shallower than the main search (15 or more), and they misjudged our own board. In 30
  of the 62 the partner's board was already below -300. G (18) is where the world that came true preferred the
  main move by 300 or more: 9 `exposure_veto`, 5 `world_switch`, 4 `soft_switch`.
- **The reply was the line's (C2, 23) or not (C3, 26).** These are small and about even. In C2 the opponent played
  what K's line expected, and the score of that same line was a median 377 cp lower at N: a horizon effect.
  Example 8 adds one more thing: the main search there reached only depth 10, with scores swinging from +409 to
  -274. The "none" world had the move played at -304 and another candidate (`Q@e1`) at +40, and the rule that
  nothing beats the main move where nothing arrives kept it.
- **A mate appeared with nothing decisive arriving (C1, 19).** 11 of the 19 were in check at K.
- **Sits (H, 27): 14 `hold_partner`, 13 `stall_deny`.** The team won 14 of the 27. A piece arrived during the sit
  in 26 of them, a queen in 13. In example 10 the seat sat while its worlds put p 0.80 on a rook arriving with
  every candidate mated.
- **Slides (S, 36).** The score crossed -300 by less than 200 per step: -227 to -318, median.

## 4. Flags at K, and base rates

Flags across the 632 falls (O left out) [report3_l50.md]:

| flag at K | falls |
|---|---|
| in check | 206 |
| king off its home rank | 173 |
| three or more king-zone squares attacked | 253 |
| partner sat during the step | 8 |
| partner's board below -300 | 234 |
| K had switched | 194 |
| opponent's hand worth 6 or more | 294 |
| our hand worth 6 or more | 406 |
| clock 5 s or more behind | 27 |

Against all 27,550 hb-l50 decisions at -300 or better (the chance of falling for good at the next decision is 2.3%
overall) [hazard_l50.txt]:

| at the decision | n | falls for good next | without it |
|---|---|---|---|
| only one legal move | 280 | 10.4% (6.7 to 14.2) | 2.2% |
| a world with `-Q` at p 0.2 or more | 1,740 | 7.9% (6.7 to 9.1) | 1.9% |
| three or more king-zone squares attacked | 4,247 | 6.0% (5.2 to 6.8) | 1.6% |
| in check | 3,751 | 5.4% (4.7 to 6.2) | 1.8% |
| partner's board below -300 | 4,593 | 5.2% (4.6 to 5.9) | 1.7% |
| king off its home rank | 3,594 | 4.9% (4.2 to 5.7) | 1.9% |
| opponent holds a queen | 3,319 | 4.1% (3.5 to 4.9) | 2.0% |
| switched away from the main move | 4,874 | 3.9% (3.4 to 4.5) | 1.9% |
| opponent's hand worth 6 or more | 9,065 | 3.4% (3.0 to 3.8) | 1.7% |
| score -300 to -100, -100 to +100, above +100 | 4,454; 6,716; 16,380 | 6.4%; 2.5%; 1.1% | |

**The seat's own forecast of a fall.** This is the sum of p over the scored worlds where the move played is below -300:

| forecast | decisions | mean forecast | below -300 at the next decision | falls for good |
|---|---|---|---|---|
| 0 | 19,351 | 0.000 | 2.9% | 0.5% |
| 0.001-0.10 | 1,020 | 0.074 | 9.3% | 1.5% |
| 0.10-0.20 | 1,904 | 0.143 | 12.6% | 2.5% |
| 0.20-0.35 | 1,513 | 0.270 | 24.2% | 4.6% |
| 0.35-0.50 | 896 | 0.420 | 27.3% | 7.9% |
| 0.50-0.75 | 723 | 0.602 | 47.9% | 17.6% |
| 0.75-1.00 | 453 | 0.884 | 60.9% | 28.9% |

The forecast ranks well and is roughly calibrated against "below -300 next": a little low at 0 and a little high
above 0.5. The weak point is not the worlds but what the seat can do about them.

**Partner feeds** (the partner's line hands a piece to our opponent while we are at -300 or better; we fall for good
within our next two decisions):

| piece, our measured price | n | reply played | fell, played | fell, not played |
|---|---|---|---|---|
| Q, 500 or more | 353 | 288 | 18.8% (13.7 to 23.4) | 7.7% (1.6 to 14.8) |
| Q, price not measured | 444 | 358 | 15.9% (12.2 to 19.8) | 4.7% (1.1 to 9.8) |
| R, 500 or more | 93 | 62 | 21.0% (11.3 to 31.1) | 9.7% (0.0 to 20.7) |
| R, 200 to 499 | 143 | 97 | 9.3% (4.1 to 15.3) | 13.0% (4.3 to 23.4) |
| N, 500 or more | 263 | 198 | 8.1% (4.1 to 12.6) | 4.6% (0.0 to 10.6) |
| N, 200 to 499 | 972 | 719 | 4.0% (2.7 to 5.5) | 1.6% (0.4 to 3.3) |
| B or P, any price | | | 3% to 7% | 0% to 6% |

## 5. Information that existed, by class

| class | n | its worlds had a move 200+ better in the world that came true | ... costing 100 or less in "none" | partner's own line had the capture | partner compared a move leaving no such capture at once (within 150 cp) | fall visible at depth 1 at N | K's score fell with depth |
|---|---|---|---|---|---|---|---|
| A1 | 86 | 0 | 0 | 49 | 49 (35) | 63 | 7 |
| A3 | 46 | 2 | 1 | 29 | 18 (11) | 14 | 2 |
| A4 | 13 | 9 | 2 | 5 | 2 (1) | 10 | 0 |
| A5 | 276 | 14 | 1 | 166 | 107 (63) | 234 | 18 |
| C1 | 19 | 3 | 2 | 5 of 13 with an arrival | | 10 | 7 |
| C2 | 23 | 1 | 1 | 6 of 18 | | 11 | 5 |
| C3 | 26 | 0 | 0 | 13 of 24 | | 15 | 3 |
| C5 | 62 | 4 | 4 | 25 of 51 | | 34 | 12 |
| G | 18 | 18 | 18 | 4 of 8 | | 13 | 5 |
| H | 27 | 0 | 0 | 18 of 26 | | 16 | 5 |
| S | 36 | 2 | 2 | 12 of 21 | | 15 | 3 |

- **In its own worlds.** A move 200 or more better in the world that came true, and cheap in "none", existed in
  31 of 632 falls, 18 of them the G class by definition. The seat's own choice of move is not where the falls
  come from.
- **In the partner's search.** For the arrival falls, the partner's main line had the capture in 249 of 421. In
  110 the partner had compared a move within 150 cp that did not leave the piece en prise at once. The partner
  does not know what the piece costs on our board, because hb-l50 has no feed prices and no talk. Our forecast
  had measured that cost at 500 or more in 197 of 421.
- **In depth.** At N the fall shows at depth 1 in 435 of 632: it is the piece in hand, not a deep combination. A
  deeper search at K would not have seen more, since K's main search never has the piece in the opponent's hand:
  hands are frozen in the search (`HB::FrozenHands`; AUTOPSY.md).

## 6. Ten falls in detail

The ten were picked by a fixed rule: lost games, the team's first fall, K at 0 or better but not a forced mate
for us, and the largest drop per class (A5 three, A1 two, one each of A4, A3, C2, C5, H).
`logs/loss-analysis/autopsy3/examples.md` has the full positions, every world with every candidate's value, the
lines at K and N, and the partner's line. Short form:

1. **plan-vs-l50-b 72 Bwhite, A5.** `r1b2knr/ppp2p1p/3Pp3/4n2N/3n4/2bPP3/PP1K2PP/R1B3NR[QBNPbp] w`, in check, at
   2295. Its worlds put p 0.83 on `+Q-Q`, with every candidate mated, and our forecast priced `-Q` at 2000 (a mate).
   The partner switched (`world_switch`: `e5b5` against its main `e5f5`), and `e2b5` took its queen. We got a
   queen too, but `Q@c2` came first and we were mated.
2. **plan-vs-l50 41 Bblack, A5.** 1277 → M-14 after a knight arrived (`h5g7 g4g7`, in the partner's own line).
3. **matekeep 66 Bwhite, A5.** At 1250, in check, five king-zone squares attacked. Its worlds put p 0.80 on a pawn
   arriving, with both candidates mated in 6, and the forecast priced `-P` at 2000. A pawn came (`g5h7`, not in the
   partner's line), then `P@e2`.
4. **kd60-vs-l50 56 Ablack, A1.** `r1bkRb1r/1pp2Pp1/2np1nNp/3BPn1q/2p2P2/2P1B1QP/P3p1PP/6RK[Prbp] b`, in check, at
   1127. The partner, at +2825, played `f5f7`; its own line `f5f7 e8f7` gave a rook. Our forecast had priced `-R`
   at 850, but its three arrival worlds were all `-B` packages. Mated after `f7e8q`.
5. **matefree 72 Bwhite, A1.** One legal move (`g3h2`, out of check), so no forecast. A bishop arrived (`e2f3 g2f3`,
   in the partner's line), and after `h4h3` we were mated in 6.
6. **matefree 46 Ablack, A4.** At 922. In the `-N` world (p 0.11) the move played was -1629 and `g4g2` held at
   -257, but `g4g2` cost 535 in "none". The partner switched (`f2g2` against its main `f2g3`), the knight was taken,
   and we fell to -1469.
7. **plan-c 72 Ablack, A3.** At 1146. The `-N` world (p 0.35) had the move played at +683. The knight came
   (`N@f6 g7f6`, in the partner's line, while the partner was itself at M+9), and `N@d6` mated in 4: a mating race
   lost.
8. **plan-c 189 Bblack, C2.** At 77, with the main search only at depth 10 and swinging from +409 to -274. The "none"
   world had `B@e1` at -304 and `Q@e1` at +40, but it kept `B@e1`. The reply `f2g1` was the one it expected: -483.
9. **kd60-vs-l50 36 Bwhite, C5.** `exposure_veto` switched from `B@g1` (mated in "none") to `P@f7` (-431 in "none"),
   with the main search unstable from +87 to -149 by depth. Nothing arrived, and it fell to -1595.
10. **matekeep 38 Ablack, H.** A `stall_deny` sit at +1072 while its worlds put p 0.80 on a rook arriving with every
    candidate mated. The rook (`d1d5 e6d5`, in the partner's line, the partner at +2012) arrived during the sit.

## 7. Suggestions (for Fable; none tested)

These are ordered by how many falls they could touch. Each upper bound comes from the counts above.

1. **Price what a feed costs on the partner's board, but only for expensive pieces.** The mate guard already does
   this for mates. With the floor it scored 63-37, and it halved the arrival falls in its own games. The falls
   here are mostly not mates at once (111 of 421 arrival falls ended in a mate at N), and they are queens and
   rooks. Among the 262 arrival falls where the feeding partner's own board was alive (-300 or better), 149 were
   Q or R and 128 were priced at 500 or more on our side. A guard that prices the loss of a Q or R when our side's
   measured cost is 500 or more, with the same floor, would sit between the mate guard and full feed prices
   (which lost 39-61). Upper bound: the 197 arrival falls our side had priced at 500 or more. Narrower: in 72
   of them (45 queens, 16 rooks), a move the partner had itself compared left no capture of that piece at once and
   cost the partner's board less than our price [partner_alt.txt]. Moves it did not compare are not counted.
2. **Partner switches that hand over a piece.** 111 of 421 feeding moves were switches (26%, against 17.4% of all
   decisions). In 48 of those the main move kept the piece and was better for the partner's own board. A
   `world_switch` is chosen for the worlds of the switcher's own board and does not look at what it gives away.
   Possible test: no `world_switch` to a move that leaves a Q or R capturable at once when the main move does not.
   Upper bound: 48 falls.
3. **A world for every priced Q or R.** In 25 A1 falls a forecast line held the fatal piece (its price was
   measured), but its package was not among the scored worlds; 19 of those were priced at 500 or more. Possible
   test: always score a world for a Q or R arrival priced at 500 or more. Upper bound: 25 falls. AUTOPSY2 found
   that more worlds in general did not help, but this is a narrower selection.
4. **Only moves.** 24 A1 falls came at a forced move out of check, where no forecast is made. The move cannot
   change, but what the seat knows could still reach the partner, through talk or the guard's probe. Upper bound:
   24 falls.
5. **Not the seat's own choice.** A4 plus G is 31 of 632 falls, and the forecast of a fall is roughly calibrated.
   More depth would rarely help, because falls show at depth 1 once the piece is in hand. More candidates in the
   worlds might: the three or so compared are not every move, and AUTOPSY.md's walk-back found a surviving move in
   3 of 13 sudden losses. Settling that needs engine runs on the A5 positions (`falls_l50.json` and the caches
   have the positions and moves).

## Limits

- Logs only. "Every candidate fell" covers the 2 to 5 candidates that were scored. "A safe partner candidate" is
  geometry: it shows no capture of that piece type at once and does not rule out other losses. Scores are the
  engine's own, not ground truth.
- The class is decided by the largest step into the fall, so a fall with two big steps is classified by the
  larger.
- One classification rule was revised after the first run (see Data and definitions). Both runs are kept.
- `plan-vs-l50` was played on v8d and the others on v8g; the counts per match are similar.
- The 99 falls on teams that won anyway are counted in "all falls" and left out of "team's first fall, lost
  games".
