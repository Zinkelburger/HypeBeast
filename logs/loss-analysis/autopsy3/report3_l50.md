# AUTOPSY3 tables (falls_l50.json)

Seats: 1400; falls: 635 (536 on teams that lost, 99 on teams that won, 0 drawn). Team's first fall in lost games: 364. Seats that never fell: 765.

## Classes

| class | all falls | team lost | team's first fall, lost | key step: score at K → at N (medians) | N a forced mate |
|---|---|---|---|---|---|
| A1 arrival in no world | 86 | 75 | 57 | +4 → -1056 | 33 |
| A3 arrival; its world had the move played holding | 46 | 33 | 21 | +425 → -270 | 4 |
| A4 arrival; another candidate held in its world | 13 | 11 | 9 | +23 → -590 | 2 |
| A5 arrival; every candidate fell in its world | 276 | 247 | 176 | +10 → -866 | 72 |
| C1 own board: a forced mate appeared | 19 | 17 | 12 | +65 → -99990 | 19 |
| C2 own board: the reply K's line expected | 23 | 18 | 12 | -104 → -483 | 0 |
| C3 own board: another reply | 26 | 25 | 17 | -108 → -558 | 0 |
| C5 own board after a switch (no line for the move played) | 62 | 51 | 25 | -156 → -664 | 0 |
| G a switch that went wrong | 18 | 16 | 9 | -16 → -549 | 1 |
| H a sit | 27 | 13 | 11 | +105 → -837 | 11 |
| S slide (no step of 200 cp) | 36 | 28 | 13 | -227 → -318 | 0 |
| O lost from the first decision | 3 | 2 | 2 | - → - | 0 |

By match (all falls):

| class | plan-vs-l50 | plan-vs-l50-b | plan-c | kd60-vs-l50 | matefree | matekeep |
|---|---|---|---|---|---|---|
| A1 | 11 | 8 | 27 | 14 | 14 | 12 |
| A3 | 8 | 6 | 15 | 4 | 5 | 8 |
| A4 | 0 | 1 | 7 | 0 | 4 | 1 |
| A5 | 43 | 38 | 70 | 45 | 39 | 41 |
| C1 | 2 | 2 | 8 | 2 | 3 | 2 |
| C2 | 4 | 5 | 2 | 4 | 4 | 4 |
| C3 | 6 | 3 | 9 | 2 | 5 | 1 |
| C5 | 9 | 15 | 17 | 10 | 7 | 4 |
| G | 4 | 3 | 6 | 2 | 3 | 0 |
| H | 4 | 4 | 8 | 5 | 1 | 5 |
| S | 3 | 5 | 18 | 4 | 3 | 3 |
| O | 1 | 1 | 0 | 0 | 1 | 0 |
| seats | 200 | 200 | 400 | 200 | 200 | 200 |

## Arrival falls

| class | n | fatal piece Q / R / B / N / P | world p (median) | move played in "none" → in its world (median) | best candidate in its world (median) | candidates compared (median) | seen at 1+ of the 2 decisions before (p>=0.10) |
|---|---|---|---|---|---|---|---|
| A1 | 86 | 38 / 14 / 10 / 21 / 3 | - | -107 → - | - | 2 | 36 |
| A3 | 46 | 21 / 4 / 6 / 13 / 2 | 0.28 | +421 → -158 | -108 | 3 | 30 |
| A4 | 13 | 2 / 1 / 2 / 5 / 3 | 0.16 | +39 → -384 | -176 | 3 | 11 |
| A5 | 276 | 122 / 40 / 30 / 54 / 30 | 0.27 | -50 → -774 | -748 | 3 | 173 |

A1 split: no worlds scored at K 32 (reasons {'only_move': 24, 'no_arrivals': 8}; one legal move 24); worlds scored but none held the piece 54 (worlds scored: {4: 39, 3: 7, 2: 8}); of those, the forecast had measured the piece's price (a line held it) 25, at 500 or more 19.

A5: the same piece at the seat's two decisions before K (the world holding it with the largest p):

| at the two decisions before K | n |
|---|---|
| no candidate 200 cp better | 155 |
| no world held the piece at either | 87 |
| a candidate 200+ cp better, not holding | 26 |
| a candidate held (>= -300) where the move played fell | 8 |

## Flags at K, by class

| class | n | in check | king off home rank | 3+ king-zone squares attacked | partner sat in the step | partner's board below -300 | K switched | opponent's hand 6+ | our hand 6+ | clock 5 s+ behind |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 86 | 38 | 21 | 46 | 1 | 26 | 8 | 37 | 61 | 4 |
| A3 | 46 | 10 | 9 | 14 | 0 | 18 | 13 | 23 | 30 | 2 |
| A4 | 13 | 2 | 3 | 2 | 0 | 5 | 2 | 7 | 8 | 0 |
| A5 | 276 | 110 | 97 | 117 | 0 | 102 | 82 | 104 | 187 | 12 |
| C1 | 19 | 11 | 6 | 11 | 1 | 8 | 1 | 15 | 15 | 0 |
| C2 | 23 | 5 | 6 | 8 | 1 | 6 | 0 | 15 | 13 | 0 |
| C3 | 26 | 6 | 4 | 7 | 0 | 13 | 1 | 14 | 13 | 0 |
| C5 | 62 | 3 | 10 | 16 | 1 | 30 | 57 | 40 | 35 | 4 |
| G | 18 | 4 | 4 | 9 | 0 | 8 | 18 | 11 | 9 | 1 |
| H | 27 | 12 | 7 | 13 | 0 | 3 | 0 | 11 | 17 | 2 |
| S | 36 | 5 | 6 | 10 | 4 | 15 | 12 | 17 | 18 | 2 |
| all | 632 | 206 | 173 | 253 | 8 | 234 | 194 | 294 | 406 | 27 |

## Information that existed

| class | n | its worlds had a move 200+ better in the world that came true | ... and that move cost <= 100 in "none" | partner's own line had the capture | partner had a candidate within 150 cp | fall visible at depth 1 at N | K's score fell with depth |
|---|---|---|---|---|---|---|---|
| A1 | 86 | 0 | 0 | 49 of 86 | 55 of 86 | 63 | 7 |
| A3 | 46 | 2 | 1 | 29 of 46 | 31 of 46 | 14 | 2 |
| A4 | 13 | 9 | 2 | 5 of 13 | 10 of 13 | 10 | 0 |
| A5 | 276 | 14 | 1 | 166 of 276 | 162 of 276 | 234 | 18 |
| C1 | 19 | 3 | 2 | 5 of 13 | 7 of 13 | 10 | 7 |
| C2 | 23 | 1 | 1 | 6 of 18 | 8 of 18 | 11 | 5 |
| C3 | 26 | 0 | 0 | 13 of 24 | 16 of 24 | 15 | 3 |
| C5 | 62 | 4 | 4 | 25 of 51 | 36 of 51 | 34 | 12 |
| G | 18 | 18 | 18 | 4 of 8 | 4 of 8 | 13 | 5 |
| H | 27 | 0 | 0 | 18 of 26 | 11 of 26 | 16 | 5 |
| S | 36 | 2 | 2 | 12 of 21 | 9 of 21 | 15 | 3 |

## Shape of the fall

Key step: the last step into F in 548, one before in 35, two before in 49. The fall was the seat's last decision in 24. The seat ended mated in 451.

| drop at the key step (clipped at +-3000) | n | team lost |
|---|---|---|
| -100000 to -3000 | 100 | 98 |
| -3000 to -1500 | 64 | 63 |
| -1500 to -800 | 129 | 105 |
| -800 to -500 | 134 | 107 |
| -500 to -300 | 127 | 102 |
| -300 to -200 | 42 | 31 |
| -200 to 0 | 36 | 28 |

