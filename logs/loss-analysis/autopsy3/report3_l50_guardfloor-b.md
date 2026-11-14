# AUTOPSY3 tables (falls_l50_guardfloor-b.json)

Seats: 600; falls: 270 (227 on teams that lost, 43 on teams that won, 0 drawn). Team's first fall in lost games: 157. Seats that never fell: 330.

## Classes

| class | all falls | team lost | team's first fall, lost | key step: score at K → at N (medians) | N a forced mate |
|---|---|---|---|---|---|
| A1 arrival in no world | 30 | 25 | 23 | +0 → -99987 | 16 |
| A3 arrival; its world had the move played holding | 26 | 23 | 17 | +242 → -348 | 2 |
| A4 arrival; another candidate held in its world | 7 | 7 | 4 | +284 → -446 | 3 |
| A5 arrival; every candidate fell in its world | 139 | 119 | 86 | +0 → -756 | 41 |
| C1 own board: a forced mate appeared | 6 | 6 | 6 | +188 → -99992 | 6 |
| C2 own board: the reply K's line expected | 14 | 12 | 5 | -128 → -529 | 0 |
| C3 own board: another reply | 10 | 8 | 1 | -135 → -460 | 0 |
| C5 own board after a switch (no line for the move played) | 16 | 12 | 4 | -101 → -562 | 0 |
| G a switch that went wrong | 3 | 2 | 2 | +36 → -643 | 0 |
| H a sit | 6 | 3 | 2 | +48 → -50368 | 3 |
| S slide (no step of 200 cp) | 10 | 7 | 4 | -182 → -310 | 0 |
| O lost from the first decision | 3 | 3 | 3 | - → - | 0 |

By match (all falls):

| class | guardfloor-b |
|---|---|
| A1 | 30 |
| A3 | 26 |
| A4 | 7 |
| A5 | 139 |
| C1 | 6 |
| C2 | 14 |
| C3 | 10 |
| C5 | 16 |
| G | 3 |
| H | 6 |
| S | 10 |
| O | 3 |
| seats | 600 |

## Arrival falls

| class | n | fatal piece Q / R / B / N / P | world p (median) | move played in "none" → in its world (median) | best candidate in its world (median) | candidates compared (median) | seen at 1+ of the 2 decisions before (p>=0.10) |
|---|---|---|---|---|---|---|---|
| A1 | 30 | 12 / 4 / 7 / 3 / 4 | - | -34 → - | - | 2 | 10 |
| A3 | 26 | 7 / 4 / 4 / 10 / 1 | 0.32 | +200 → -174 | -160 | 3 | 20 |
| A4 | 7 | 3 / 0 / 0 / 2 / 2 | 0.11 | +299 → -421 | -70 | 3 | 3 |
| A5 | 139 | 59 / 17 / 18 / 31 / 14 | 0.30 | -61 → -694 | -670 | 3 | 91 |

A1 split: no worlds scored at K 12 (reasons {'only_move': 10, 'no_arrivals': 2}; one legal move 10); worlds scored but none held the piece 18 (worlds scored: {4: 17, 3: 1}); of those, the forecast had measured the piece's price (a line held it) 7, at 500 or more 5.

A5: the same piece at the seat's two decisions before K (the world holding it with the largest p):

| at the two decisions before K | n |
|---|---|
| no candidate 200 cp better | 77 |
| no world held the piece at either | 39 |
| a candidate 200+ cp better, not holding | 16 |
| a candidate held (>= -300) where the move played fell | 7 |

## Flags at K, by class

| class | n | in check | king off home rank | 3+ king-zone squares attacked | partner sat in the step | partner's board below -300 | K switched | opponent's hand 6+ | our hand 6+ | clock 5 s+ behind |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 30 | 16 | 14 | 18 | 1 | 4 | 6 | 15 | 21 | 1 |
| A3 | 26 | 7 | 5 | 9 | 0 | 10 | 8 | 11 | 20 | 2 |
| A4 | 7 | 1 | 0 | 2 | 0 | 3 | 1 | 5 | 4 | 0 |
| A5 | 139 | 58 | 44 | 53 | 2 | 55 | 41 | 62 | 106 | 4 |
| C1 | 6 | 4 | 2 | 3 | 0 | 2 | 1 | 5 | 6 | 0 |
| C2 | 14 | 3 | 1 | 2 | 0 | 7 | 0 | 6 | 6 | 0 |
| C3 | 10 | 2 | 1 | 2 | 1 | 9 | 0 | 9 | 7 | 0 |
| C5 | 16 | 2 | 3 | 6 | 0 | 8 | 16 | 8 | 10 | 0 |
| G | 3 | 1 | 1 | 1 | 0 | 1 | 3 | 2 | 1 | 0 |
| H | 6 | 3 | 0 | 3 | 0 | 1 | 0 | 3 | 4 | 0 |
| S | 10 | 1 | 0 | 2 | 1 | 1 | 2 | 3 | 3 | 0 |
| all | 267 | 98 | 71 | 101 | 5 | 101 | 78 | 129 | 188 | 7 |

## Information that existed

| class | n | its worlds had a move 200+ better in the world that came true | ... and that move cost <= 100 in "none" | partner's own line had the capture | partner had a candidate within 150 cp | fall visible at depth 1 at N | K's score fell with depth |
|---|---|---|---|---|---|---|---|
| A1 | 30 | 0 | 0 | 10 of 30 | 16 of 30 | 18 | 1 |
| A3 | 26 | 0 | 0 | 14 of 26 | 12 of 26 | 4 | 1 |
| A4 | 7 | 5 | 1 | 4 of 7 | 7 of 7 | 4 | 0 |
| A5 | 139 | 6 | 1 | 81 of 139 | 88 of 139 | 115 | 12 |
| C1 | 6 | 0 | 0 | 3 of 3 | 3 of 3 | 2 | 1 |
| C2 | 14 | 0 | 0 | 5 of 12 | 9 of 12 | 8 | 5 |
| C3 | 10 | 0 | 0 | 4 of 8 | 5 of 8 | 3 | 5 |
| C5 | 16 | 0 | 0 | 8 of 15 | 10 of 15 | 8 | 2 |
| G | 3 | 3 | 3 | 3 of 3 | 3 of 3 | 3 | 0 |
| H | 6 | 0 | 0 | 5 of 6 | 3 of 6 | 6 | 0 |
| S | 10 | 1 | 0 | 4 of 7 | 4 of 7 | 1 | 1 |

## Shape of the fall

Key step: the last step into F in 227, one before in 20, two before in 20. The fall was the seat's last decision in 10. The seat ended mated in 190.

| drop at the key step (clipped at +-3000) | n | team lost |
|---|---|---|
| -100000 to -3000 | 56 | 54 |
| -3000 to -1500 | 27 | 27 |
| -1500 to -800 | 34 | 27 |
| -800 to -500 | 51 | 41 |
| -500 to -300 | 73 | 54 |
| -300 to -200 | 16 | 14 |
| -200 to 0 | 10 | 7 |

