# AUTOPSY3 tables (falls_l50.json)

Seats: 1400; falls: 635 (536 on teams that lost, 99 on teams that won, 0 drawn). Team's first fall in lost games: 364. Seats that never fell: 765.

## Classes

| class | all falls | team lost | team's first fall, lost | key step: score at K → at N (medians) | N a forced mate |
|---|---|---|---|---|---|
| A1 arrival in no world | 86 | 75 | 57 | +4 → -1056 | 33 |
| A3 arrival; its world had the move played holding | 41 | 29 | 21 | +372 → -337 | 4 |
| A4 arrival; another candidate held in its world | 13 | 11 | 8 | +107 → -814 | 2 |
| A5 arrival; every candidate fell in its world | 263 | 238 | 170 | +28 → -851 | 70 |
| C1 own board: a forced mate appeared | 21 | 20 | 15 | +38 → -99990 | 21 |
| C2 own board: the reply K's line expected | 32 | 24 | 15 | -103 → -486 | 0 |
| C3 own board: another reply | 28 | 27 | 17 | -116 → -568 | 0 |
| C5 own board after a switch (no line for the move played) | 70 | 55 | 27 | -135 → -652 | 0 |
| G a switch that went wrong | 15 | 14 | 8 | -35 → -538 | 1 |
| H a sit | 27 | 13 | 11 | +105 → -837 | 11 |
| S slide (no step of 200 cp) | 36 | 28 | 13 | -227 → -318 | 0 |
| O lost from the first decision | 3 | 2 | 2 | - → - | 0 |

By match (all falls):

| class | plan-vs-l50 | plan-vs-l50-b | plan-c | kd60-vs-l50 | matefree | matekeep |
|---|---|---|---|---|---|---|
| A1 | 11 | 8 | 27 | 14 | 14 | 12 |
| A3 | 7 | 5 | 15 | 3 | 2 | 9 |
| A4 | 0 | 2 | 6 | 1 | 3 | 1 |
| A5 | 46 | 34 | 65 | 43 | 36 | 39 |
| C1 | 3 | 2 | 10 | 2 | 2 | 2 |
| C2 | 4 | 9 | 5 | 5 | 5 | 4 |
| C3 | 5 | 3 | 10 | 2 | 7 | 1 |
| C5 | 8 | 16 | 18 | 11 | 12 | 5 |
| G | 3 | 2 | 5 | 2 | 3 | 0 |
| H | 4 | 4 | 8 | 5 | 1 | 5 |
| S | 3 | 5 | 18 | 4 | 3 | 3 |
| O | 1 | 1 | 0 | 0 | 1 | 0 |
| seats | 200 | 200 | 400 | 200 | 200 | 200 |

## Arrival falls

| class | n | fatal piece Q / R / B / N / P | world p (median) | move played in "none" → in its world (median) | best candidate in its world (median) | candidates compared (median) | seen at 1+ of the 2 decisions before (p>=0.10) |
|---|---|---|---|---|---|---|---|
| A1 | 86 | 38 / 14 / 10 / 21 / 3 | - | -107 → - | - | 2 | 36 |
| A3 | 41 | 22 / 3 / 5 / 10 / 1 | 0.33 | +340 → -113 | -106 | 3 | 26 |
| A4 | 13 | 2 / 2 / 2 / 3 / 4 | 0.19 | +121 → -384 | -186 | 4 | 10 |
| A5 | 263 | 116 / 38 / 28 / 52 / 29 | 0.34 | -45 → -830 | -797 | 3 | 165 |

A1 split: no worlds scored at K 32 (reasons {'only_move': 24, 'no_arrivals': 8}; one legal move 24); worlds scored but none held the piece 54 (worlds scored: {4: 39, 3: 7, 2: 8}); of those, the forecast had measured the piece's price (a line held it) 25, at 500 or more 19.

A5: the same piece at the seat's two decisions before K (the world holding it with the largest p):

| at the two decisions before K | n |
|---|---|
| no candidate 200 cp better | 145 |
| no world held the piece at either | 83 |
| a candidate 200+ cp better, not holding | 27 |
| a candidate held (>= -300) where the move played fell | 8 |

## Flags at K, by class

| class | n | in check | king off home rank | 3+ king-zone squares attacked | partner sat in the step | partner's board below -300 | K switched | opponent's hand 6+ | our hand 6+ | clock 5 s+ behind |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 86 | 38 | 21 | 46 | 1 | 26 | 8 | 37 | 61 | 4 |
| A3 | 41 | 12 | 10 | 14 | 0 | 13 | 12 | 18 | 27 | 0 |
| A4 | 13 | 2 | 3 | 3 | 0 | 5 | 3 | 6 | 8 | 0 |
| A5 | 263 | 106 | 96 | 115 | 0 | 98 | 77 | 106 | 182 | 11 |
| C1 | 21 | 12 | 7 | 13 | 1 | 8 | 2 | 15 | 16 | 0 |
| C2 | 32 | 7 | 7 | 8 | 1 | 9 | 0 | 16 | 18 | 2 |
| C3 | 28 | 5 | 3 | 7 | 0 | 16 | 1 | 13 | 13 | 0 |
| C5 | 70 | 3 | 9 | 15 | 1 | 34 | 64 | 46 | 38 | 5 |
| G | 15 | 4 | 4 | 9 | 0 | 7 | 15 | 9 | 8 | 1 |
| H | 27 | 12 | 7 | 13 | 0 | 3 | 0 | 11 | 17 | 2 |
| S | 36 | 5 | 6 | 10 | 4 | 15 | 12 | 17 | 18 | 2 |
| all | 632 | 206 | 173 | 253 | 8 | 234 | 194 | 294 | 406 | 27 |

## Information that existed

| class | n | its worlds had a move 200+ better in the world that came true | ... and that move cost <= 100 in "none" | partner's own line had the capture | partner had a candidate within 150 cp | fall visible at depth 1 at N | K's score fell with depth |
|---|---|---|---|---|---|---|---|
| A1 | 86 | 0 | 0 | 49 of 86 | 55 of 86 | 63 | 7 |
| A3 | 41 | 0 | 0 | 27 of 41 | 30 of 41 | 19 | 2 |
| A4 | 13 | 7 | 1 | 5 of 13 | 10 of 13 | 10 | 0 |
| A5 | 263 | 16 | 1 | 157 of 263 | 146 of 263 | 218 | 17 |
| C1 | 21 | 3 | 2 | 8 of 15 | 8 of 15 | 11 | 8 |
| C2 | 32 | 1 | 1 | 10 of 27 | 15 of 27 | 18 | 5 |
| C3 | 28 | 1 | 0 | 16 of 26 | 19 of 26 | 17 | 3 |
| C5 | 70 | 7 | 7 | 27 of 59 | 45 of 59 | 38 | 14 |
| G | 15 | 15 | 15 | 3 of 5 | 1 of 5 | 10 | 3 |
| H | 27 | 0 | 0 | 18 of 26 | 11 of 26 | 16 | 5 |
| S | 36 | 1 | 1 | 12 of 21 | 9 of 21 | 15 | 3 |

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

