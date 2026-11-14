# Autopsy of the candidate's lost games (worlds5-vs-l50, late50-vs-np-b)

Written 2026-11-11 from logs only (no engine was run). Scripts and their outputs are in
`logs/loss-analysis/autopsy/` (git-ignored); every number below comes from one of them, named
in brackets.

## Summary

1. The candidate lost 96 games: 53 of 100 in `worlds5-vs-l50` (hb-l50) and 43 of 100 in `late50-vs-np-b` (hb-late50, which also drew 1). 92 ended by checkmate, 4 by flag. All 4 flags came after the flagged seat had already seen a forced mate against itself [classify.py].
2. First causes: slow loss on its own board 19, partner's board lost first 19, sudden mate after a forecast arrival 27 (17 already marked fatal at the decision before), a decisive non-mate drop after a forecast arrival 16, an arrival in no world 7, the team had a forced mate first and lost the race 4, the partner could have supplied a mating piece first 4 [classify.py].
3. In 41 of the 96 games the mated seat went from -300 or better straight to a forced mate in one decision. The arriving piece was a queen in 28. In 33 of the 41 the capture was in the partner's own main line. The partner was ahead (>300) in 23, level in 10 and behind in 8 [detail.py].
4. At the decision before such a mate, a candidate that survived in the fatal world existed in 2 of the 41 cases (looking up to 6 decisions back). By then the seat itself had no escape; only the partner, or an earlier decision, could have changed the result [detail.py].
5. In 17 games the mated seat's world searches had already scored the fatal piece as a forced mate, against no mate with nothing arriving, at a decision before the partner's decision that let the piece go. In 14 of them the partner's own line had the capture. That is the most the planned Alarm message could have reached [bounds.py].
6. Such an alarm would have fired on 1.8% and 1.3% of the candidate's decisions (100 and 68), in 50 and 40 games, of which 38 and 32 were lost. The piece really reached the opponent before the seat's next move in 41 and 27 of those decisions [alarmrate.py].
7. In 21 more games the seat's worlds said in time that the piece cost 300 cp or more without mating (Worth). In 9 more, the partner's previous decision already had the capture in its line (Plan, then Alarm). In 48 of the 96 games none of the planned messages could have arrived in time, including 18 of the 19 slow losses [mapping.py].
8. Missed supplies are rare: in 6 lost games the partner had a legal capture of a piece that a world said would mate for us, and did not take it (10 decisions) [extra.py].
9. Clocks did not decide these games. At the mated seat's decision before its fall its median clock was 84 s, and its clock and its opponent's differed by more than 5 s in 4 of 95. 81 mated seats ended at 500 ms or less because they sat out a mate they had already seen [clocks.py].
10. Evaluation: the partner's score predicts the result as well as the seat's own (log loss 0.651 each, 0.636 together at 1500 cp per unit). Net of the score: king off its home rank -9 points of result (CI -15 to -4); opponent with 9+ points in hand +9 (CI +5 to +12); own hand 4+ -4.5 (CI -8 to -1). The best single scale is 1200 cp, not 1000 [calib.py, scale.py].

## Definitions

- **Mated seat (S)**: the losing team's seat on the board that decided the game. For a checkmate this is the board
  where the loser stands checkmated in the final position: in 0 of 92 checkmates was it completed by a move on the
  other board. For a flag it is the seat whose clock hit 0. **Partner (P)**: the other seat of that team.
- **Lost for good** at decision n: the seat's main score is below -300 at n and at every later decision. If a seat
  never was, but was mated, the end of the game counts (1 game: `late50` 53).
- **Its fall**: the step from the seat's last decision at -300 or better (the *decision before*) to the first
  lost-for-good decision. **Arrival in that step**: a piece that reached the seat's opponent's hand between those two decisions.
  **Fatal piece**: of those arrivals, the one whose world gave the move played the lowest value.
- **Partner's decision before the capture**: P's last decision with n not after the capture. "In its line" means the
  capture is the move P's main line expected at that ply (the deepest full PV of the last two depths), "later/elsewhere" that
  it appears at another ply of that PV.
- First cause is the earliest of: S lost for good, P lost for good, the team's first forced mate *for* itself
  (score >= 90000), and the first missed supply (a world of a single `+T` had S mating while nothing arriving did not,
  P had a legal capture of a T at its next decision before S's next, and did not take one). When S's fall comes first,
  the class says what kind of fall it was:

| class | S's fall |
|---|---|
| a | straight to a forced mate. The fatal piece was in a world where the move played was already mated |
| a2 | straight to a forced mate. The fatal piece was in a world where the move played was not mated |
| a3 | straight to a forced mate. The fatal piece was in a world, but the move played had no value there (only move, a sit, or an unscored world) |
| a4 | not to a mate, but a drop of 400 cp or more with a forecast arrival |
| b, b2 | as a and a4, but the fatal piece was in no world |
| c | no arrival, or a drop under 400 cp: a slow loss on its own board |
| d | P was lost for good first |
| e | the team reported a forced mate first and lost the race. A flag while S was not yet lost would also be e: there were none |
| f | a missed supply came first |

## Classes

[classify.py; game numbers are the `game` field of results.jsonl]

| class | worlds5-vs-l50 (hb-l50, 53 lost) | late50-vs-np-b (hb-late50, 43 lost) | total |
|---|---|---|---|
| (c) slow loss on its own board | 9: 11, 15, 27, 36, 50, 56, 62, 70, 79 | 10: 5, 14, 37, 38, 47, 52, 64, 84, 87, 98 | 19 |
| (d) partner's board lost first | 10: 7, 12, 17, 24, 40, 57, 58, 73, 81, 99 | 9: 32, 35, 53, 57, 67, 82, 88, 90, 95 | 19 |
| (a) sudden mate, the piece was known fatal | 8: 33, 48, 51, 63, 64, 83, 85, 92 | 9: 0, 3, 7, 27, 30, 45, 48, 71, 93 | 17 |
| (a4) decisive drop after a forecast arrival | 12: 5, 28, 55, 59, 60, 65, 69, 72, 74, 88, 89, 96 | 4: 20, 26, 31, 49 | 16 |
| (a3) sudden mate, forecast arrival, move not scored there | 4: 18, 26, 43, 52 | 2: 2, 54 | 6 |
| (a2) sudden mate, forecast arrival scored as survivable | 2: 30, 87 | 2: 4, 10 | 4 |
| (e) the team had a forced mate first, lost the race | 3: 35, 38, 82 | 1: 96 | 4 |
| (f) the partner could have supplied a mating piece first | 3: 4, 21, 67 | 1: 77 | 4 |
| (b2) decisive drop after an arrival in no world | 1: 9 | 3: 21, 70, 78 | 4 |
| (b) sudden mate after an arrival in no world | 1: 93 | 2: 33, 73 | 3 |
| (c2) sudden mate with nothing arriving | 0 | 0 | 0 |
| flags (counted under their cause above) | 36 (c), 82 (e) | 2 (a3), 54 (a3) | 4 |

The mated seat's own fall, whatever came first: a 24, a4 25, c 25, a2 7, a3 6, b2 5, b 4.

**What the timelines show** (per-game rows in the table at the end of this section)

- **Sudden mates (41 falls of the a, a2, a3 and b kinds)** [detail.py]: fatal piece Q 28, N 6, R 5, B 1, P 1.
  - The partner's decision before the capture had it in its line 30 times, elsewhere in its line 3, not at all 8. The partner was ahead 23, level 10, behind 8.
  - Our side took a piece on that board the ply before or after in 36: it was a trade.
  - In 11 the fatal world had shown the move as mated at 2 or more of the seat's decisions.
  - In 2 a candidate escaped that world at some decision within 6 back.
- **Decisive drops (29 of the 30 a4 and b2 falls; one has no decision before it)**: fatal piece Q 10, R 7, N 5, B 5, P 2.
  - Partner in its line 12, elsewhere in its line 5, not 12. Partner ahead 6, level 12, behind 11.
- **Class d**: by the same rules, the partner's own fall was a4 in 9, c in 7 and b2 in 3 [extra.py].
  - In 10 of the 19 the partner was lost only 1 to 8 plies before S, usually in the same exchange; in 9 it was 11 to 83 plies earlier.
- **Class c**: median 75 plies (22 decisions) from lost for good to the end [cslow.py].
  - At the fall the king was on its home rank in 15 of 19. Median board material own minus opponent was -2. Median hands were 5 for the opponent and 4 own.
  - In the three examples below the step was small (-52 to -295 before, -310 to -644 after) and came early (n = 23, 32, 56).
- **Class e**:
  - `worlds5` 38: the partner Ablack had M+13 at n=125 and was still at M+5 to M+7 at the end. Its mating line g6g2 h1g2 gave up a queen, and Bwhite (+3907 at n=134) was mated through that queen first.
  - `late50` 96: Awhite had M+17. Its partner Bblack lost a queen on h5, and the queen mated Awhite. Awhite's worlds had shown -Q as M-10 at n=137, before Bblack's decision at n=138.
- **Clocks and sitting** [clocks.py, sits.py]:
  - At the decision before the fall S's team had the time advantage in 27 of 95. The base rate over all candidate decisions is 3357 of 9963.
  - 86 of 96 mated seats sat with reason `hold_mated` and 81 ended at 500 ms or less. That is the hold floor, reached after the mate was seen.
  - The 4 flags are sit races lost by a seat already mated. In `late50` 54, Bblack sat from 57.3 s until it flagged at 146.8 s while Ablack also sat (`hold_partner`), so its partner Awhite (+1937) could not move.
  - `stall_deny` sits before the fall came in 4 lost games (`late50` 2 and 54, `worlds5` 18 and 72). Over all games the candidate's seats sat `stall_deny` in 15 seat-games, and the team won 3.
- **The three decisions before the first mate was seen** (step 1 of the request): listed per game in `timeline.txt`. Each line gives every piece that reached either hand, its world probability and value at each of those decisions, and the partner's knowledge, score and trades.

**Which planned partner message could have arrived in time, by class** [mapping.py]

- alarm: the seat's worlds marked the fatal piece `#` at its last decision before the partner's.
- worth: they said 300 cp or more then.
- plan+alarm: neither of those, but the partner's previous decision already had the capture in its line, at ply 3 with the moves matching [plan_prev.py].
- supply: a missed supply.

| class | alarm | worth | plan+alarm | supply | none | total |
|---|---|---|---|---|---|---|
| d | 2 | 3 | 2 | 0 | 12 | 19 |
| c | 0 | 0 | 0 | 1 | 18 | 19 |
| a | 8 | 4 | 3 | 0 | 2 | 17 |
| a4 | 0 | 9 | 1 | 0 | 6 | 16 |
| a3 | 2 | 2 | 0 | 0 | 2 | 6 |
| f | 3 | 0 | 1 | 0 | 0 | 4 |
| b2 | 0 | 0 | 0 | 0 | 4 | 4 |
| a2 | 0 | 2 | 1 | 0 | 1 | 4 |
| e | 2 | 1 | 1 | 0 | 0 | 4 |
| b | 0 | 0 | 0 | 0 | 3 | 3 |
| all | 17 | 21 | 9 | 1 | 48 | 96 |

- 24 falls had the piece in no world of the seat before the partner's decision [bounds.py]. In 15 of them the capture was the opponent's immediate reply in the partner's own line, 1 ply after its decision.
- **Odds** (the partner's forecast of its own board) reaches the seat only after that decision, and the seat had no escape anyway (point 4), so it cannot help these 15. Only a check made by the partner before it moves can: today's price probes (F6, F13, F14).
- **Menu** concerns the 6 missed-supply games. Those 6 are its whole bound, and Alarm's `+T=#` half reaches the same games.
- **No message touches class c** (18 of 19 games), nor 12 of the 19 d games.

### Per-game timelines

[gen_table.py] "Piece" is the fatal piece of S's fall, with the largest world probability that held it at the
decision before and the move played's value in that world (`?`: not scored, `none`: no arrival). The partner column is
its decision before that capture. "Team mate first" is the first decision where the losing team reported a forced mate for itself.

| match | game | class | mated seat | its fall (n: score before -> after) | mate seen at n | piece to opponent in that step (world p; move's value there) | partner's decision before the capture | partner lost at n | team mate first at n | end |
|---|---|---|---|---|---|---|---|---|---|---|
| worlds5 | 4 | f | Bwhite | 102: -141 -> M- | 102 | -N (0.73; -377) | in its line, score M+ | - | 97 | checkmate, S clock 400 ms |
| worlds5 | 5 | a4 | Awhite | 88: -57 -> -499 | 116 | -P (0.50; -458) | in its line later/elsewhere, score 402 | 128 | - | checkmate, S clock 2900 ms |
| worlds5 | 7 | d | Awhite | 117: -131 -> -1452 | 125 | -Q (0.25; -808) | in its line, score -999 | 114 | - | checkmate, S clock 400 ms |
| worlds5 | 9 | b2 | Bblack | 53: -295 -> -2635 | 69 | -Q (0.00; ?) | not in its line, score 242 | - | - | checkmate, S clock 400 ms |
| worlds5 | 11 | c | Bblack | 77: -87 -> -451 | 140 | -B (0.26; -1201) | not in its line, score -288 | 91 | - | checkmate, S clock 400 ms |
| worlds5 | 12 | d | Bwhite | 117: 477 -> -578 | 133 | -N (0.21; M-) | not in its line, score -810 | 106 | - | checkmate, S clock 1585 ms |
| worlds5 | 15 | c | Bblack | 60: -255 -> -644 | 130 | -P (0.15; -579) | in its line later/elsewhere, score -139 | 112 | - | checkmate, S clock 400 ms |
| worlds5 | 17 | d | Awhite | 87: -125 -> -670 | 103 | -R (0.42; -862) | not in its line, score -1420 | 79 | - | checkmate, S clock 400 ms |
| worlds5 | 18 | a3 | Ablack | 150: 490 -> M- | 133 | -Q (0.50; ?) | not in its line, score 56 | - | - | checkmate, S clock 400 ms |
| worlds5 | 21 | f | Bblack | 161: M+ -> M- | 161 | -Q (0.22; M-) | in its line, score 638 | - | 157 | checkmate, S clock 400 ms |
| worlds5 | 24 | d | Bwhite | 138: -139 -> -435 | 147 | none | - | 133 | - | checkmate, S clock 400 ms |
| worlds5 | 26 | a3 | Ablack | 84: -100 -> M- | 84 | -Q (0.40; ?) | in its line, score 417 | - | 91 | checkmate, S clock 400 ms |
| worlds5 | 27 | c | Bblack | 61: -191 -> -583 | 89 | none | - | 98 | - | checkmate, S clock 400 ms |
| worlds5 | 28 | a4 | Ablack | 149: -181 -> -668 | 200 | -R (0.11; -832) | not in its line, score -941 | 191 | - | checkmate, S clock 400 ms |
| worlds5 | 30 | a2 | Bwhite | 80: 1460 -> M- | 80 | -Q (0.41; 596) | in its line, score 525 | - | - | checkmate, S clock 400 ms |
| worlds5 | 33 | a | Awhite | 125: 124 -> M- | 125 | -Q (0.30; M-) | not in its line, score -123 | 130 | - | checkmate, S clock 400 ms |
| worlds5 | 35 | e-race | Awhite | 153: 59 -> -707 | 157 | -Q (0.20; -948) | in its line later/elsewhere, score -237 | - | 129 | checkmate, S clock 40882 ms |
| worlds5 | 36 | c | Ablack | 65: -208 -> -562 | 79 | -P (0.32; -431) | in its line, score 745 | - | - | flag, S clock 0 ms |
| worlds5 | 38 | e-race | Bwhite | 138: 3907 -> M- | 138 | -Q (0.85; M-) | in its line, score M+ | - | 114 | checkmate, S clock 400 ms |
| worlds5 | 40 | d | Bwhite | 70: 2062 -> M- | 70 | -Q (0.31; -566) | in its line, score 200 | 69 | - | checkmate, S clock 400 ms |
| worlds5 | 43 | a3 | Awhite | 100: 1142 -> M- | 100 | -R (0.79; ?) | in its line, score 724 | - | - | checkmate, S clock 400 ms |
| worlds5 | 48 | a | Ablack | 78: 115 -> M- | 78 | -R (0.38; M-) | in its line, score 941 | - | - | checkmate, S clock 400 ms |
| worlds5 | 50 | c | Ablack | 76: -79 -> -361 | 128 | -P (0.61; -234) | not in its line, score -140 | 127 | - | checkmate, S clock 400 ms |
| worlds5 | 51 | a | Bblack | 69: 806 -> M- | 69 | -Q (0.47; M-) | in its line, score 156 | - | - | checkmate, S clock 400 ms |
| worlds5 | 52 | a3 | Ablack | 77: 588 -> M- | 77 | -Q (0.37; ?) | in its line, score -52 | 85 | - | checkmate, S clock 400 ms |
| worlds5 | 55 | a4 | Bblack | 160: 157 -> -738 | 197 | -N (0.85; -769) | in its line, score 174 | 167 | - | checkmate, S clock 5400 ms |
| worlds5 | 56 | c | Ablack | 70: -91 -> -303 | 107 | -P (0.49; -282) | in its line later/elsewhere, score -282 | - | - | checkmate, S clock 400 ms |
| worlds5 | 57 | d | Awhite | 121: -62 -> -726 | 145 | -N (0.00; ?) | not in its line, score -811 | 118 | - | checkmate, S clock 400 ms |
| worlds5 | 58 | d | Ablack | 164: 0 -> M- | 164 | -Q (0.25; M-) | in its line later/elsewhere, score -1179 | 138 | - | checkmate, S clock 400 ms |
| worlds5 | 59 | a4 | Awhite | 103: 313 -> -656 | 107 | -Q (0.16; -573) | in its line, score 2007 | - | - | checkmate, S clock 400 ms |
| worlds5 | 60 | a4 | Ablack | 72: 76 -> -813 | 76 | -Q (0.49; -512) | in its line later/elsewhere, score -2 | - | - | checkmate, S clock 400 ms |
| worlds5 | 62 | c | Ablack | 128: 0 -> -350 | 132 | -P (0.65; -450) | in its line later/elsewhere, score -816 | - | - | checkmate, S clock 400 ms |
| worlds5 | 63 | a | Awhite | 73: 0 -> M- | 73 | -Q (0.26; M-) | in its line, score 72 | 86 | - | checkmate, S clock 400 ms |
| worlds5 | 64 | a | Ablack | 82: 1368 -> M- | 82 | -Q (0.42; M-) | in its line, score 1718 | - | - | checkmate, S clock 86797 ms |
| worlds5 | 65 | a4 | Bblack | 79: 397 -> -520 | 83 | -Q (0.24; -969) | in its line, score 109 | - | - | checkmate, S clock 400 ms |
| worlds5 | 67 | f | Awhite | 132: -206 -> -906 | 144 | -R (0.33; -710) | in its line, score -975 | 115 | - | checkmate, S clock 54540 ms |
| worlds5 | 69 | a4 | Bblack | 113: -1 -> -557 | 147 | -B (0.19; -281) | in its line, score -689 | 118 | - | checkmate, S clock 5400 ms |
| worlds5 | 70 | c | Ablack | 64: -133 -> -357 | 123 | -N (0.10; -531) | not in its line, score -77 | 116 | - | checkmate, S clock 400 ms |
| worlds5 | 72 | a4 | Ablack | 71: 194 -> -878 | - | -Q (0.12; 126) | not in its line, score -20 | 72 | - | checkmate, S clock 59742 ms |
| worlds5 | 73 | d | Awhite | 84: 190 -> -907 | 121 | -Q (0.85; -875) | not in its line, score -388 | 79 | - | checkmate, S clock 400 ms |
| worlds5 | 74 | a4 | Ablack | 54: -88 -> -1215 | 78 | -Q (0.44; -1528) | in its line, score -164 | - | - | checkmate, S clock 77918 ms |
| worlds5 | 79 | c | Awhite | 71: -291 -> -566 | 184 | -P (0.06; -190) | not in its line, score -7 | 168 | - | checkmate, S clock 400 ms |
| worlds5 | 81 | d | Bblack | 98: -74 -> -575 | 139 | -R (0.31; -67) | in its line, score -963 | 86 | - | checkmate, S clock 54819 ms |
| worlds5 | 82 | e-race | Ablack | 114: -69 -> M- | 114 | -N (0.50; M-) | in its line, score M+ | - | 105 | flag, S clock 0 ms |
| worlds5 | 83 | a | Bblack | 58: 458 -> M- | 58 | -B (0.20; M-) | in its line, score 615 | - | - | checkmate, S clock 400 ms |
| worlds5 | 85 | a | Awhite | 95: 378 -> M- | 95 | -Q (0.47; M-) | in its line, score 493 | - | - | checkmate, S clock 400 ms |
| worlds5 | 87 | a2 | Awhite | 104: 304 -> M- | 104 | -P (0.26; -491) | not in its line, score -439 | - | - | checkmate, S clock 400 ms |
| worlds5 | 88 | a4 | Ablack | 106: 0 -> -600 | 110 | -B (0.30; -366) | not in its line, score -13 | - | - | checkmate, S clock 400 ms |
| worlds5 | 89 | a4 | Bblack | 71: -161 -> -757 | 75 | -B (0.11; -421) | not in its line, score -22 | - | - | checkmate, S clock 400 ms |
| worlds5 | 92 | a | Ablack | 100: 303 -> M- | 100 | -Q (0.42; M-) | in its line, score 1062 | - | - | checkmate, S clock 400 ms |
| worlds5 | 93 | b | Bblack | 105: 126 -> M- | 105 | -R (0.00; ?) | in its line, score 799 | - | 114 | checkmate, S clock 400 ms |
| worlds5 | 96 | a4 | Ablack | 122: -153 -> -608 | 126 | -P (0.19; -736) | in its line, score 431 | - | - | checkmate, S clock 400 ms |
| worlds5 | 99 | d | Awhite | 118: -123 -> M- | 118 | -N (0.47; M-) | in its line, score -1708 | 66 | - | checkmate, S clock 62779 ms |
| late50- | 0 | a | Awhite | 107: -50 -> M- | 107 | -Q (0.41; M-) | in its line, score -96 | 115 | - | checkmate, S clock 400 ms |
| late50- | 2 | a3 | Bblack | 99: 1005 -> M- | 99 | -Q (0.85; ?) | not in its line, score 1208 | - | - | flag, S clock 0 ms |
| late50- | 3 | a | Bwhite | 120: 668 -> M- | 120 | -N (0.35; M-) | in its line, score 895 | - | - | checkmate, S clock 400 ms |
| late50- | 4 | a2 | Awhite | 150: 0 -> M- | 150 | -N (0.09; -488) | not in its line, score -611 | - | - | checkmate, S clock 400 ms |
| late50- | 5 | c | Bwhite | 76: -212 -> -321 | 155 | none | - | 140 | - | checkmate, S clock 400 ms |
| late50- | 7 | a | Ablack | 48: 394 -> M- | 48 | -Q (0.76; M-) | in its line, score 809 | - | - | checkmate, S clock 400 ms |
| late50- | 10 | a2 | Awhite | 151: -245 -> M- | 151 | -Q (0.34; -1454) | in its line, score -403 | - | 164 | checkmate, S clock 400 ms |
| late50- | 14 | c | Awhite | 78: -156 -> -497 | 205 | -N (0.43; -524) | not in its line, score -17 | 81 | - | checkmate, S clock 400 ms |
| late50- | 20 | a4 | Bblack | 161: -103 -> -977 | 169 | -N (0.11; -1007) | in its line later/elsewhere, score 806 | 192 | - | checkmate, S clock 400 ms |
| late50- | 21 | b2 | Ablack | 43: -275 -> -944 | 99 | -N (0.00; ?) | not in its line, score 133 | 65 | - | checkmate, S clock 400 ms |
| late50- | 26 | a4 | Bblack | 77: 229 -> -868 | 126 | -Q (0.12; -924) | not in its line, score 663 | 102 | - | checkmate, S clock 400 ms |
| late50- | 27 | a | Bwhite | 115: 609 -> M- | 115 | -Q (0.29; M-) | in its line, score 91 | - | - | checkmate, S clock 400 ms |
| late50- | 30 | a | Bblack | 66: 411 -> M- | 66 | -Q (0.70; M-) | in its line, score 43 | - | - | checkmate, S clock 400 ms |
| late50- | 31 | a4 | Ablack | 103: 218 -> -443 | 111 | -R (0.50; -636) | in its line, score 471 | - | 124 | checkmate, S clock 400 ms |
| late50- | 32 | d | Awhite | 88: -269 -> -605 | 125 | -B (0.33; -233) | in its line later/elsewhere, score -782 | 80 | - | checkmate, S clock 400 ms |
| late50- | 33 | b | Ablack | 107: -107 -> M- | 107 | -Q (0.00; ?) | not in its line, score 452 | - | - | checkmate, S clock 400 ms |
| late50- | 35 | d | Bwhite | 70: -129 -> -356 | 102 | -P (0.42; -667) | in its line later/elsewhere, score -539 | 65 | - | checkmate, S clock 400 ms |
| late50- | 37 | c | Ablack | 36: -295 -> -430 | 83 | -N (0.23; -765) | not in its line, score -106 | 92 | - | checkmate, S clock 400 ms |
| late50- | 38 | c | Awhite | 86: 3 -> -329 | 98 | -B (0.29; -32) | not in its line, score 302 | 110 | - | checkmate, S clock 400 ms |
| late50- | 45 | a | Bwhite | 115: 203 -> M- | 115 | -R (0.50; M-) | in its line later/elsewhere, score 231 | - | - | checkmate, S clock 2900 ms |
| late50- | 47 | c | Ablack | 61: 7 -> -354 | 126 | -P (0.26; -376) | not in its line, score 272 | - | 121 | checkmate, S clock 400 ms |
| late50- | 48 | a | Awhite | 88: 448 -> M- | 88 | -Q (0.50; M-) | in its line, score -646 | - | - | checkmate, S clock 400 ms |
| late50- | 49 | a4 | Ablack | 90: 231 -> -521 | 137 | -B (0.25; -637) | in its line, score -6 | - | - | checkmate, S clock 400 ms |
| late50- | 52 | c | Bblack | 43: -90 -> -485 | 91 | -P (0.07; -1221) | in its line later/elsewhere, score 474 | 72 | - | checkmate, S clock 400 ms |
| late50- | 53 | d | Bwhite | 89: -292 -> M- | - | -R (0.00; ?) | in its line, score M- | 23 | - | checkmate, S clock 83345 ms |
| late50- | 54 | a3 | Bblack | 73: 707 -> M- | 73 | -Q (0.82; ?) | in its line, score 1775 | - | - | flag, S clock 0 ms |
| late50- | 57 | d | Bwhite | 101: -139 -> -514 | 126 | -P (0.16; -289) | not in its line, score -1561 | 18 | - | checkmate, S clock 400 ms |
| late50- | 64 | c | Bblack | 81: -198 -> -501 | 148 | -P (0.12; -503) | in its line, score 122 | 110 | - | checkmate, S clock 400 ms |
| late50- | 67 | d | Ablack | 64: -105 -> -329 | 131 | -P (0.23; 32) | not in its line, score -176 | 63 | - | checkmate, S clock 60857 ms |
| late50- | 70 | b2 | Bblack | 17: ? -> -487 | 118 | -N (0.00; ?) | - | 85 | - | checkmate, S clock 400 ms |
| late50- | 71 | a | Bwhite | 104: 425 -> M- | 104 | -N (0.60; M-) | not in its line, score 1057 | - | - | checkmate, S clock 400 ms |
| late50- | 73 | b | Ablack | 77: 401 -> M- | 77 | -Q (0.00; ?) | in its line, score 926 | - | - | checkmate, S clock 400 ms |
| late50- | 77 | f | Ablack | 173: 922 -> M- | 173 | -Q (0.77; M-) | in its line, score M+ | - | 157 | checkmate, S clock 400 ms |
| late50- | 78 | b2 | Awhite | 89: -37 -> -506 | 97 | -R (0.00; ?) | in its line later/elsewhere, score 28 | - | - | checkmate, S clock 400 ms |
| late50- | 82 | d | Awhite | 88: -133 -> -542 | 108 | -R (0.28; -988) | in its line, score -1554 | 70 | - | checkmate, S clock 400 ms |
| late50- | 84 | c | Bblack | 81: -289 -> -644 | 105 | -P (0.29; -522) | in its line later/elsewhere, score 356 | - | - | checkmate, S clock 400 ms |
| late50- | 87 | c | Bwhite | 93: 0 -> -351 | 101 | none | - | 113 | - | checkmate, S clock 400 ms |
| late50- | 88 | d | Awhite | 84: 143 -> -359 | 136 | -B (0.62; -273) | not in its line, score -583 | 79 | - | checkmate, S clock 400 ms |
| late50- | 90 | d | Bblack | 60: -158 -> -555 | 80 | -N (0.36; -445) | in its line, score -660 | 46 | - | checkmate, S clock 400 ms |
| late50- | 93 | a | Ablack | 106: 1869 -> M- | 106 | -Q (0.46; M-) | in its line, score 969 | - | - | checkmate, S clock 400 ms |
| late50- | 95 | d | Ablack | 109: 303 -> M- | 109 | -Q (0.32; -1077) | not in its line, score -351 | 95 | - | checkmate, S clock 400 ms |
| late50- | 96 | e-race | Awhite | 142: M+ -> M- | 142 | -Q (0.32; M-) | in its line later/elsewhere, score 1917 | - | 133 | checkmate, S clock 51720 ms |
| late50- | 98 | c | Bblack | 27: -52 -> -310 | 55 | -B (0.27; -280) | in its line, score 0 | - | - | checkmate, S clock 400 ms |

## Accounts

The prefix is the arena move list (board digit and UCI, as in `position startpos moves ...`) up to the decision. Replay it with
`position startpos moves <prefix>` for that seat (`setoption name Seat value ...`), or with python-chess as
`scripts/postmortem.py`'s `replay()` does. `n` counts moves on both boards; `M-6` is a forced mate in 6 against.

### Class a: sudden mate after a forecast arrival the seat knew was fatal

**worlds5-vs-l50 game 64, Ablack (hb-l50), decision n=78 at 62.5 s.**
- Main score +1368 at depth 14. It played b7c8 (the main move), E=0.186.
- Worlds: nothing p 0.24, +1245. `+N-Q` p 0.42, M-6. `-Q` p 0.29, M-6. `+N-Q-N` p 0.05, M-4. The best candidate was mated in all three queen worlds.
- At its previous decision (n=75) the `-Q` world already had the move played mated (p 0.19), against +986 with nothing arriving: an alarm would have been sent then.
- The partner Bwhite (hb-l50) decided at n=77, score +1718. It played g5h3, with main line `g5h3 f5g4 N@f6 ...`: its queen was taken on g4 as the reply it expected.
- Token #79 `2f5g4` took the queen. Ablack's next decision (n=82) saw M-4, and it was mated at ply 85.

```
2e2e4 1e2e4 1e7e6 2e7e5 1b1c3 1d7d5 2g1f3 2f8c5 1e4d5 1e6d5 1d2d4 2d2d4 1b8c6 2e5d4 1g1f3 1f8b4 1f1b5 2f1c4 1g8e7 2d7d5 1P@h6 2c4d5 1g7h6 2P@e6 1c1h6 1d8d6 2d5c4 1h6e3 2b8c6 1h8g8 2e1g1 1f3e5 2g8f6 1c8d7 2e4e5 1d1f3 2f6g4 2c1g5 1c6e5 2c5e7 1d4e5 2g5e7 1b4c3 2d8e7 1b2c3 2P@d6 1d6e5 2c7d6 1B@f6 2e5d6 1e5e6 2e7d6 1b5d7 2N@e4 1e8d7 2B@c7 1f6e7 1B@g4 2e4d6 2c7d6 1P@f5 2b1d2 1e6e7 2N@f4 1f3d5 2d2e4 1d7c8 2e8g8 1e1g1 2f3g5 1Q@d8 2B@f5 1d5b7 2d1g4 2N@h3 1c8b7 1N@a5 2g5h3
```

**late50-vs-np-b game 7, Ablack (hb-late50), decision n=44 at 28.3 s.**
- Main score +394. The main move f7g8 was vetoed (`exposure_veto`) and it played B@g6, E=0.108.
- Worlds: nothing p 0.19, +250 (best +402). `-Q` p 0.76, M-10. `+P-Q` p 0.05, M-10.
- The partner Bwhite decided at n=43, score +809, before Ablack's world had a queen in it. It played f3f6, with main line `f3f6 g7f6 Q@d2 ...`: giving its queen was the expected reply.
- Token #45 `2g7f6` took the queen. Ablack saw M-8 at n=48 and played on (`mated_play_on`), then sat (`hold_mated`) down to 400 ms. It was mated at ply 63.
- Not reachable by Alarm (no world in time); a partner-side probe was the only route.

```
1e2e4 2d2d4 1e7e6 1b1c3 2g8f6 2g1f3 1b8c6 1g1f3 2e7e6 2c1g5 1g8f6 2f8e7 1d2d4 2g5f6 1f8b4 1c1g5 1h7h6 2e7f6 2e2e4 1g5f6 2d7d6 1d8f6 1e4e5 2b1c3 1f6g6 2b8c6 2B@g3 1f1d3 1g6g2 2c8d7 1h1g1 2e4e5 1g2f3 2c6d4 1d1f3 2e5f6 1c6d4 2d4f3 1f3f7 2d1f3 1e8f7 2d8f6 1B@h5 2f3f6
```

**late50-vs-np-b game 27, Bwhite (hb-late50), decision n=111 at 96.4 s.**
- Main score +609. It played g2f3 (main), E=0.309.
- Worlds: nothing p 0.47, +623. `-Q` p 0.29, M-6. `+B-Q-N` p 0.14, M-6. `+B-Q` p 0.10, M-6.
- The partner Ablack decided next, at n=112, score +91 (level). It played f6d4, with main line `f6d4 e3d4 R@e6 ...`, so its queen was recaptured as it expected. An alarm printed at n=111 would have been the last message before that decision.
- Token #114 `1e3d4` took the queen. Bwhite saw M-4 at n=115 and was mated at ply 125.

```
2e2e4 2g8f6 1b2b3 1d7d5 1c1b2 1b8c6 2b1c3 2d7d5 1e2e3 2e4d5 2e7e6 1c8f5 1g1f3 2f1b5 1g8f6 2c7c6 2d5c6 1f1b5 2b7c6 1f5d7 2b5e2 1b5c6 2f8e7 1d7c6 2d2d4 1d2d3 2e8g8 1e7e6 2c1e3 1a2a3 2b8d7 1f8c5 2B@f3 1b3b4 2d8c7 1c5e7 2g1h3 1b1c3 2c8b7 2e3f4 1e8g8 2e6e5 1b4b5 2f4g3 1c6e8 2N@f5 1P@g5 2e1g1 1f6h5 2f5g3 1c3d5 2h2g3 1e6d5 2e5d4 1P@h6 2d1d4 1g7h6 2d7e5 1g5h6 2P@g5 1N@f5 2f6e8 1f3e5 2d4h4 1P@g6 2b7c8 1e5g4 2N@f4 1P@g7 2P@h6 1h6g7 2c3d5 1h5g7 2c6d5 1B@h6 2f4d5 1P@h5 2e5f3 1B@f6 2e2f3 1e7f6 2P@g4 1g4f6 2f3g4 1g8h8 2h6g5 2h3g5 1h6g7 1f5g7 2P@h6 1P@h6 2P@d7 1N@f5 2c7d7 1h6g7 2g4d7 1f5g7 2e7g5 1N@g3 2P@e7 1Q@a5 2g5h4 1P@b4 2e7f8q 1d5d4 2g8f8 1P@h6 2d7e8 1d8f6 2N@f3 1b2d4
```

### Class d: the partner's board lost first

**worlds5-vs-l50 game 12: Ablack (hb-l50) fell first. Decision n=102 at 88.3 s.**
- Score -109. It played g7h7, E=0.414.
- Worlds: `+B+P-R-P` p 0.19, -851. `+P-R` p 0.13, -1052 (best -1028).
- Token #103 `2e2d1q` (a promotion capturing a rook on board B) gave the rook. Bwhite's own line at n=101 had a promotion capture on d1 (`... e2d1n`).
- Ablack n=106: -1464 (only move), then -1312 and -810.
- Bwhite (the mated seat) was at +477 at n=113, with `+N-Q-N` p 0.21 at M-6. Token #116 gave the knight, and Bwhite was at -578 from n=117. It saw the mate at n=133 and was mated at ply 137.

```
2d2d4 1e2e4 2e7e6 1b8c6 1b1c3 1e7e6 2g1f3 1g1f3 2a7a6 1d7d5 2b1c3 1e4d5 2b7b5 1e6d5 1f1b5 2c1g5 1g8f6 2f8e7 1d2d4 2h2h4 1f8e7 2b5b4 1f3e5 2c3e4 2c8b7 1e8g8 2e4c5 1b5c6 2b7f3 1b7c6 2e2f3 1e1g1 2b8c6 1d8e8 2g5e7 1c1g5 1g8h8 2g8e7 1f1e1 2f1d3 2N@f5 1f6g8 2c2c3 1g5e7 2e8g8 1e8e7 2P@g4 1d1h5 2b4c3 1B@h6 1B@e3 2b2c3 2P@g3 1P@g5 2g4f5 1h2h4 1N@f6 2g3f2 1h5h6 2e1f2 1g7h6 2B@e3 1P@g7 2f2e3 1h8g7 2e7d5 1h4g5 2e3e2 1h6g5 2d5c3 1P@b7 1B@h2 2e2f1 1g1h1 2c3d1 1c8f5 2a1d1 1e3g5 2P@c4 1h7h6 2P@h6 1N@h4 2c4d3 1B@e6 2h6g7 1h4f5 2P@e2 1e6f5 1Q@h4 2f1e1 1a8e8 2B@g3 1g5h6 2e1d2 1g8h6 2B@h6 1P@g5 2B@e3 1N@g4 2h6g7 1g5h6 2P@h6
```

**worlds5-vs-l50 game 81: Awhite (hb-l50) fell first. Decision n=82 at 66.8 s.**
- Score +6. It switched (`world_switch`) from c2d2 to c2c1, E=0.445.
- Worlds: `+P-R-P` p 0.29, -614 (best -564). `+P-R` p 0.20, -209.
- The partner Bblack (n=81, +121) also switched, from P@e4 to P@h3. Its main line `P@e4 f5g7` had the rook capture as the expected reply, and token #83 `2f5g7` made it anyway.
- Awhite went -628 at n=86, then -912 and -963.
- Bblack (the mated seat) fell at n=98 (-74 to -575) after a `-R` (p 0.31; the move played -67 there). It saw the mate at n=139 and was mated at ply 151.

```
2d2d4 1d2d4 2b8c6 1e7e6 2g1f3 1b1c3 2e7e5 2b1c3 1g8f6 2e5d4 1g1f3 2f3d4 2g8f6 1b8c6 2e2e3 1c3e4 1f6e4 2f8b4 1g2g3 2f1d3 1d7d5 2e8g8 1c2c3 2e1g1 1c8d7 2d7d5 1P@d3 2N@h5 1e4d6 2b4c3 1f1g2 2b2c3 1h7h5 2c6e5 1h2h3 2c1a3 1h5h4 2f8e8 1f3h4 2h5g7 1h8h4 2g8g7 1g3h4 2N@g5 1d6f5 2g7g8 1N@f3 2d1d2 1f5h4 2R@h5 1f3h4 2d2e2 1d8h4 2c8g4 1N@f3 2f2f3 1h4h5 2h5g5 1c1f4 2N@h6 1B@d6 2g8h8 1f4d6 2P@f4 1f8d6 2e5f3 1P@e5 1d6e7 2f1f3 1d1c2 2g5g7 2h6f5 1P@g3 2g4f3 1R@g8 2d4f3 1B@f8 2P@f2 1f2g3 2g1h1 1N@e3 2P@h3
```

**late50-vs-np-b game 82: Bblack (hb-late50) fell first. Decision n=66 at 51.6 s.**
- Score -20. It played h7g6 (main), E=0.382.
- Worlds: `+N-N-P` p 0.36, -421. `+N-N` p 0.25, -273. `+P-Q` p 0.13, M-8 (best -982).
- The partner Awhite (n=65, +1) switched from e5f6 to g5e6. Token #67 `1f7e6` gave a knight.
- Bblack went -724 at n=70, then -1156 and -1308.
- Awhite (the mated seat) fell at n=88 (-133 to -542) after a `-R` (p 0.28, -988). It was mated at ply 125, and its main search never showed the mate.

```
2e2e4 2b8c6 1e2e4 2b1c3 2e7e6 2g1f3 2d7d5 2d2d4 1g8f6 1d2d4 2g8f6 1e7e5 2f1d3 1g1f3 1f6e4 2d5e4 1f3e5 2c3e4 1d7d5 2f6e4 1b1c3 2d3e4 1f8b4 2f8e7 1f1b5 2e1g1 1b8c6 2e8g8 1e1g1 2f1e1 1P@h3 2c8d7 2d1e2 1b5c6 2P@h6 1b7c6 2B@f4 1d1h5 2N@g5 1N@g6 2f4g5 1c3e4 2h6g5 1h3g2 2P@b5 1e4g5 2f7f5 1g2f1r 2e4c6 1g1f1 2b7c6 1N@f6 2f3e5 2N@f7 1h5e2 1g6e5 2e5f7 1d4e5 2f8f7 1N@d4 2N@e5 1P@e6 2d7e8 1c8e6 2P@g6 1g5e6
```

### Class c: slow loss on its own board

**late50-vs-np-b game 98, Bblack (hb-late50), decision n=23 at 8.0 s.**
- Score -52. It switched (`world_switch`) from e8d7 to e8e7, E=0.457.
- Worlds: nothing p 0.58, -133 for the move played against -29 for the best candidate. `+N-B` p 0.27, -280.
- The partner Awhite was level (0). Its line `b5d7 f6d7` traded a bishop for a knight: tokens #24 and #26.
- From n=27 Bblack was at -310, -310 and -716, and never at -300 or better again. It saw the mate at n=55 and was mated at ply 97, 70 plies after the fall.

```
2e2e4 1d2d4 2g8f6 1d7d5 2b1c3 2d7d5 2g1f3 1g1f3 1g8f6 2d5e4 1c1f4 2f3g5 1c8f5 2e7e5 1b1d2 1e7e6 1e2e3 2f1c4 1b8d7 2c8g4 1f1b5 2c4f7 1a7a6
```

**worlds5-vs-l50 game 15, Bblack (hb-l50), decision n=56 at 41.1 s.**
- Score -255. It played c8b7 (main), E=0.405.
- Worlds: nothing p 0.61, -263. `+B+N-B-P` p 0.15, -579 (best -119). `+B+N-B-B` p 0.12, -879 (best -285). `+N` p 0.12, -286.
- A pawn arrived (token #57). Bblack went -644 at n=60, then -1315 at n=64 (switched from e7f6 to c3d2) and -1628.
- It saw the mate at n=130 and was mated at ply 142. The partner was at -139 at n=55.

```
2e2e4 1e2e4 1d7d5 2g7g6 2b1c3 2f8g7 1e4d5 1e7e6 2d2d4 2g8f6 1b1c3 1e6d5 1d2d4 1g8f6 2P@h6 1g1f3 2g7f8 1f8e7 1f1d3 2e4e5 2P@b4 1e8g8 2c3b5 1e1g1 2a7a6 2e5f6 1b8c6 1f3e5 2d7d5 2f6e7 1N@h4 2f8e7 1P@h6 2g1f3 1g7h6 2h8g8 1c1h6 2c1f4 1P@g7 2a6b5 1h6g7 2f1b5 1g8g7 1f2f4 2b8c6 1c6d4 2f3e5 1d3h7 2P@c3 1P@h3 2b5c6 1g2h3 2b7c6 1e7c5 2P@b7 1B@e3
```

**late50-vs-np-b game 37, Ablack (hb-late50), decision n=32 at 15.6 s.**
- Score -295. It played c6b4 (main), E=0.422.
- Worlds: `+N+N-B-N` p 0.23, -765. `+N-B` p 0.22, -385. `+N` p 0.19, +249.
- A knight arrived (token #33). Ablack went -430 at n=36, then -548 and -868.
- It saw the mate at n=83 and was mated at ply 111. The partner was at -106 at n=31.

```
2d2d4 1d2d3 2e7e5 1c7c5 2g1f3 1g1f3 2e5d4 2f3d4 1d7d5 1b1c3 2b8c6 2e2e3 1e7e5 2g8f6 1e2e4 2b1c3 1g8f6 2d7d5 1c1g5 2f1b5 1d5d4 2c8d7 1c3d5 2e3e4 1b8c6 2d5e4 1g5f6 2c1g5 1g7f6 2f8e7 1f1e2 2e1g1
```

## Evaluation check

[calib.py] 19,950 decisions with a non-mate main score (all four engines; they share the net and the evaluation),
200 games. Stated chance = 1/(1+exp(-cp/1000)). Result = the team's score in that game. Bias = mean result minus
mean stated. Intervals: 95%, from 2000 resamples of whole games. Pooling both teams of every game makes the
all-engine intervals narrower than a one-team sample: the candidate-only column (9,963 decisions) is wider, and
I quote it where it matters.

| feature (all engines) | decisions | games | stated | won | bias | 95% interval |
|---|---|---|---|---|---|---|
| opponent hand 0 | 2107 | 198 | 0.560 | 0.537 | -0.022 | -0.054 to +0.011 |
| opponent hand 9+ | 4654 | 196 | 0.447 | 0.489 | +0.042 | +0.011 to +0.073 |
| opponent hand holds a queen | 2877 | 183 | 0.451 | 0.496 | +0.045 | +0.006 to +0.083 |
| own hand 9+ | 5160 | 198 | 0.569 | 0.517 | -0.051 | -0.078 to -0.027 |
| king on home rank | 17378 | 200 | 0.507 | 0.511 | +0.003 | -0.005 to +0.012 |
| king 1 rank up | 2261 | 185 | 0.510 | 0.457 | -0.053 | -0.113 to -0.003 |
| king 2+ ranks up | 311 | 71 | 0.503 | 0.428 | -0.075 | -0.194 to +0.059 |
| (candidate only) king 2+ ranks up | 165 | 34 | 0.501 | 0.236 | -0.265 | -0.406 to -0.055 |
| 0-1 shelter pawns in front of the king | 8104 | 199 | 0.510 | 0.480 | -0.030 | -0.055 to -0.005 |
| 3+ squares of the king zone attacked | 3346 | 198 | 0.478 | 0.434 | -0.044 | -0.077 to -0.014 |
| partner mated (its score <= -90000) | 703 | 177 | 0.450 | 0.018 | -0.431 | -0.472 to -0.390 |
| partner behind (< -300, not mated) | 4260 | 200 | 0.420 | 0.317 | -0.103 | -0.146 to -0.056 |
| partner level | 9009 | 200 | 0.505 | 0.499 | -0.006 | -0.011 to -0.001 |
| partner ahead (> 300, not mating) | 4687 | 200 | 0.591 | 0.665 | +0.074 | +0.027 to +0.115 |
| partner mating (>= 90000) | 891 | 181 | 0.564 | 0.974 | +0.411 | +0.369 to +0.456 |
| team has the time advantage | 7011 | 200 | 0.511 | 0.584 | +0.073 | +0.012 to +0.133 |
| team has not | 12939 | 200 | 0.506 | 0.460 | -0.046 | -0.078 to -0.012 |
| own clock 10+ s behind its opponent | 157 | 126 | 0.500 | 0.975 | +0.475 | +0.420 to +0.531 |
| own clock 10+ s ahead | 47 | 34 | 0.515 | 0.021 | -0.493 | -0.598 to -0.397 |

Joint linear model of (result - stated) on all indicators at once, all engines, 500 game resamples:

| term | coefficient | 95% interval |
|---|---|---|
| intercept | +0.055 | +0.031 to +0.085 |
| opponent hand >= 4 | +0.017 | -0.024 to +0.055 |
| opponent hand >= 9 | +0.087 | +0.050 to +0.124 |
| own hand >= 4 | -0.045 | -0.081 to -0.010 |
| king off its home rank | -0.092 | -0.150 to -0.035 |
| 0-1 shelter pawns | -0.028 | -0.069 to +0.014 |
| partner mated | -0.434 | -0.470 to -0.398 |
| partner behind (not mated) | -0.125 | -0.164 to -0.086 |
| partner ahead (not mating) | +0.113 | +0.072 to +0.149 |
| partner mating | +0.426 | +0.383 to +0.464 |
| own clock 10+ s behind | +0.092 | +0.047 to +0.133 |
| own clock 10+ s ahead | -0.053 | -0.129 to +0.018 |
| stated chance above 0.5 | -0.081 | -0.130 to -0.039 |

Scale [scale.py]:

- Own score alone: the best logistic scale is 1200 cp, log loss 0.6567 against 0.6584 at the engine's 1000. Across 1000 game resamples the best grid value was 1000, 1200 or 1500 in 905 (1200 in 425).
- On the 17,956 decisions where the partner's latest score is known and neither score is a mate:
  - own score alone: 0.6509
  - partner's score alone: 0.6508
  - both, as 1/(1+exp(-(own/1500 + partner/1500))): 0.6362
  - constant 0.5: 0.6931
- (1500, 1500) was the best pair in 156 of 300 resamples. The candidate alone gives the same pair, 0.6356.

What carries a real bias, and how large:

- **The partner's board** is the largest effect and is real. Net of the own score, a partner behind costs 12.5 points of result and a partner ahead adds 11.3. A partner's seen mate either way is about 43 points.
  - In the bands: with the partner behind, a stated 60-75% won 46%; with the partner ahead, a stated 40-60% won 60%.
  - The engine's E (`hb_coordinator.cpp`, `win()` near "HBWinScale") uses its own board only. Unscored worlds count as "nothing arrives".
- **King off its home rank**: -9 points net (CI -15 to -4). For the candidate alone, a king 2+ ranks up won 23.6% against 50.1% stated (165 decisions, 34 games).
  - The earlier loss analysis (EXPERIMENTS.md, from `hazard.json`, scores within 600 cp, other engines) found no effect of king rank once the score was known. This sample differs in engines and score range, so treat the two as disagreeing.
  - Fewer than 2 shelter pawns: -3 points, CI crossing 0 in the joint model.
- **Hands are overvalued on both sides**, the same direction as EXPERIMENTS.md's "about 50 cp a point too much": opponent holding 9+ points +8.7 (CI +5 to +12), own 4+ -4.5 (CI -8 to -1).
  - `HBHandDiscount=30` (F2) already lost 44-56, so this is not a new suggestion.
- **Overconfidence**: the intercept +5.5 with -8.1 above 50% means stated chances are too far from 50% on both sides. This is what the 1200 cp fit says.
- **The clock rows are selection, not a clock effect.** A seat 10+ s behind on its own board is almost always one that sat while its partner mated: 157 decisions, won 97.5%. 99.0% of decisions (19,746 of 19,950) have the two clocks within 10 s. The team time advantage is +7.3 marginal, but the candidate-only interval crosses 0 (-0.011 to +0.171).

## Suggestions (ranked)

The bound is the number of lost games (of 96) whose first cause, or the fall that decided them, the change could have
touched at most. It is not a forecast of games won: no replay says the partner had a playable alternative.

1. **Alarm message (PARTNER_TALK paradigm 1, step T1).**
   - Addresses classes a, a3, e and f, and 2 of d.
   - Bound: **17 games**, in 14 of which the partner's own line had the capture: `worlds5` 4, 12, 21, 33, 40, 52, 63, 64, 82, 83; `late50` 0, 2, 3, 27, 30, 77, 96 [bounds.py].
   - Evidence: the seat's worlds had `-T=#` before the partner's decision in those 17. Alarms are rare (1.3% to 1.8% of decisions) and mostly real: in 70 of the 90 games with one the team lost, and the piece came in 68 of the 168 decisions [alarmrate.py].
   - Cheapest test, a position test before the build (after the running match): replay the partner's decision before the capture in these 17 games with `HBFeedPrices=true,HBPriceScale=0` on the existing v7e. Record whether it keeps the piece and its score change. That is the same 1500 cp price the alarm would set, through probes. Then T1 (`alarm-vs-c`, a new build v8b) and its collapse table.
2. **A check by the partner of its own planned trades: F13 or F14 (queued, option-only on v7e).**
   - Addresses the a and b falls the seat could not report in time.
   - Bound: **15 games** where the piece was in no world of the seat but was the opponent's immediate reply in the partner's own line: `worlds5` 5, 38, 51, 60, 74, 81, 85, 93, 99; `late50` 7, 10, 53, 54, 73, 78. These are on top of item 1's 17, which the probes can also see.
   - Evidence: in all 15 the capture came 1 ply after the partner's decision, so no message from the seat can arrive first.
   - Cheapest test: F13 as queued (`matekeep-vs-l50`). Read its collapse table, and in its post-mortem the share of falls whose capture was in the partner's line (33 of 41 here).
3. **Worth message (paradigm 2, T2), with the share and cap ablation.**
   - Addresses a4 above all (9 of 16), and also a, a2, a3, d and e.
   - Bound: **21 games**, beyond item 1's, where the seat's worlds said the piece cost 300 cp or more (not a mate) before the partner's decision: `worlds5` 7, 26, 28, 35, 43, 48, 55, 59, 65, 87, 92, 96; `late50` 4, 20, 26, 31, 45, 49, 82, 93, 95.
   - Evidence: the fall was a drop of 400 cp or more right after that piece arrived, while the partner was ahead in 6 of the 29 drops, level in 12 and behind in 11. So "do not sell your own board" matters here more than for mates.
   - The probe-priced version (`HBFeedPrices=true` with scale 50) is what NP dropped, so only the message version is untested.
   - Cheapest test: T2a-d (a new build). Before that, a log-only check: list, from T1's logs, the captures the partner made while the worth entry was non-zero (PARTNER_TALK's "sell-outs").
4. **Plan, then alarm (paradigm 3 with 1, `worth+plan` or `alarm+plan`).**
   - Addresses a, a2, a4, d, e and f.
   - Bound: **9 more games** (not in items 1 or 3) where the partner's previous decision already had the fatal capture at ply 3 of its line, moves matching. A plan message from it would have put the piece into the seat's worlds one decision earlier, in time for an alarm back. 18 falls in all have that property [plan_prev.py, mapping.py].
   - Cheapest test: T3 after T1. Read "told and happened" for `-T=#` against T1 alone.
5. **A team winning chance in the coordinator's E** (a new evaluation of candidates, not of positions).
   - Use the partner's score: E = sum of p times 1/(1+exp(-(v + partner)/1500)), with mates still 0 and 1.
   - Addresses e (4 games) directly. It also makes a mate against us cost more when the partner is ahead, which was the case in 23 of the 41 sudden mates.
   - Bound from logs: small. The seat had a surviving candidate in 2 of the 41, and its partner's queen trades are not changed by it (the partner's E does not see our board's mate).
   - Evidence: the calibration above (partner's score as informative as own; log loss 0.651 to 0.636).
   - Cheapest test: log-only first. Recompute E with the partner term over the logged `hb_coord` candidates and count the decisions whose argmax changes, in won and lost games. Then a new build and a match.
6. **`HBWinScale=1200` (option-only on v7e).**
   - Addresses the seat's own choice between candidates in a, a4 and b.
   - Bound: at most the 2 sudden mates with a surviving candidate, plus an unknown share of the a4 drops.
   - Evidence: best fit 1200 cp (1000 to 1500 in 905 of 1000 resamples), and the overconfidence term (-8.1 above 50%). The gain in log loss is small (0.6584 to 0.6567).
   - Cheapest test: `ws1200-vs-l50`, 100 games, option-only.
7. **A king-exposure term** (EXPERIMENTS.md loss analysis, suggestion 3).
   - Addresses c and a4.
   - Bound: weak. The king was off its home rank at the fall in only 4 of the 19 c games and 6 of the 18 d falls with a decision; I did not count it for a4.
   - Evidence: -9 points net for a king off its home rank (CI -15 to -4), and -26.5 points for the candidate's king 2+ ranks up. Opposite to the earlier finding on other engines.
   - Cheapest test: a position test on the c and a4 games named above. Do plain searches with the term choose moves that keep the king home, and at what score cost? Then a new build.
8. **Missed supplies** (the `+T=#` half of Alarm, or paradigm 5 Menu).
   - Addresses f.
   - Bound: **6 games** with a legal capture not taken (`worlds5` 4, 21, 67; `late50` 14, 49, 77), 4 of them as first cause.
   - Evidence: 10 decisions in total; 3 more where the capture was made.
   - Cheapest test: comes free with T1: read "told and happened" for `+T=#`. Menu only if T1 shows `+T=#` pieces still not taken.

Not touched by any of these: the 19 slow losses (class c, 18 with no message possible) and 12 of the 19 partner-first
games (d). They are ordinary losses on a board. The logs show when they happened (early, from a small step: -52 to -295
cp before, 75 plies to the end), not why.

## What I could not determine from logs alone

- **Whether the partner had a playable alternative** to the move that let the piece go, and at what cost, in the
  17 alarm games and the 15 immediate-reply trades. This needs a replay of those partner decisions, with and without a
  mate price. The 2026-11-10 loss analysis did that for 13 older games: 8 had a move within 250 cp.
- **Whether a sudden mate was really forced earlier**:
  - The world searches are about 9 to 11 plies deep with every forecast piece droppable at the root (v7e).
  - In 4 a2 games the world scored the arrival as survivable and the seat was mated after it: `worlds5` 30, `-Q` +596 two moves before M-2.
  - Telling a search horizon from a wrong arrival time needs a judge search of those positions.
- **Candidates outside the coordinator's list.** "No surviving candidate" (39 of 41) means none of the 3 to 5 scored candidates. It does not mean no legal move: a full-width judge search would say.
- **Why the slow losses went wrong**: which move started them, and whether it was evaluation or search. This needs a deeper engine (or a fixed judge) on the decisions just before each c fall.
- **Unscored worlds.** In 6 games the move played had no value in the world that held the fatal piece (a3: only moves, sits, an unscored world). Whether a scored world would have changed an earlier decision needs a replay.
- **The cost of each suggestion in the games we won.** Alarm frequency is measured (point 6 of the summary), but the cost on the partner's board of honouring an alarm or a worth entry is not in any log.
- **Sitting.** Whether moving instead of sitting after a seen mate would ever have saved a game. 86 of 96 mated seats sat; the 4 flags were sit races lost by a seat already mated. Logs show only the branch taken.
- **Partner-aware E.** How many decisions it would change is computable from `hb_coord` logs (item 5), but what those changed decisions would have led to is not.

Scripts, in the order they ran (each `nice -n 19 python3 <script>` from `logs/loss-analysis/autopsy/`):

- `common.py`: cache of games, rows, clocks, full PVs and board features.
- `timeline.py`: `timeline.json`, `timeline.txt`.
- `classify.py`: `classes.json`, `classes.txt`.
- `detail.py`: `detail.json`, `detail.txt`.
- `extra.py`, `cslow.py`, `sits.py`, `clocks.py`, `alarmrate.py`, `bounds.py`, `plan_prev.py`, `mapping.py`.
- `calib.py`, `scale.py`.
- `gen_table.py`.
- `accounts.py` and `show.py`, for reading one game.
