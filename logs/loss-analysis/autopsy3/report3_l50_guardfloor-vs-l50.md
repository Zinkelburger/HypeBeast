# AUTOPSY3 tables (falls_l50_guardfloor-vs-l50.json)

Seats: 200; falls: 114 (100 on teams that lost, 14 on teams that won, 0 drawn). Team's first fall in lost games: 63. Seats that never fell: 86.

## Classes

| class | all falls | team lost | team's first fall, lost | key step: score at K → at N (medians) | N a forced mate |
|---|---|---|---|---|---|
| A1 arrival in no world | 13 | 13 | 9 | -6 → -1018 | 3 |
| A3 arrival; its world had the move played holding | 13 | 9 | 6 | +345 → -317 | 0 |
| A4 arrival; another candidate held in its world | 2 | 2 | 1 | -162 → -432 | 0 |
| A5 arrival; every candidate fell in its world | 53 | 46 | 31 | +0 → -691 | 14 |
| C1 own board: a forced mate appeared | 1 | 1 | 0 | +236 → -99982 | 1 |
| C2 own board: the reply K's line expected | 3 | 3 | 0 | -40 → -572 | 0 |
| C3 own board: another reply | 8 | 7 | 2 | -63 → -558 | 0 |
| C5 own board after a switch (no line for the move played) | 9 | 8 | 7 | -89 → -661 | 0 |
| G a switch that went wrong | 5 | 5 | 2 | +78 → -766 | 0 |
| H a sit | 2 | 2 | 1 | +49902 → -50990 | 1 |
| S slide (no step of 200 cp) | 4 | 3 | 3 | -224 → -400 | 0 |
| O lost from the first decision | 1 | 1 | 1 | - → - | 0 |

By match (all falls):

| class | guardfloor-vs-l50 |
|---|---|
| A1 | 13 |
| A3 | 13 |
| A4 | 2 |
| A5 | 53 |
| C1 | 1 |
| C2 | 3 |
| C3 | 8 |
| C5 | 9 |
| G | 5 |
| H | 2 |
| S | 4 |
| O | 1 |
| seats | 200 |

## Arrival falls

| class | n | fatal piece Q / R / B / N / P | world p (median) | move played in "none" → in its world (median) | best candidate in its world (median) | candidates compared (median) | seen at 1+ of the 2 decisions before (p>=0.10) |
|---|---|---|---|---|---|---|---|
| A1 | 13 | 6 / 4 / 2 / 1 / 0 | - | -243 → - | - | 3 | 5 |
| A3 | 13 | 5 / 1 / 2 / 2 / 3 | 0.30 | +300 → -212 | -185 | 3 | 7 |
| A4 | 2 | 0 / 0 / 0 / 2 / 0 | 0.24 | -121 → -306 | -170 | 4 | 1 |
| A5 | 53 | 15 / 9 / 7 / 14 / 8 | 0.29 | -30 → -729 | -698 | 3 | 37 |

A1 split: no worlds scored at K 6 (reasons {'only_move': 3, 'no_arrivals': 3}; one legal move 3); worlds scored but none held the piece 7 (worlds scored: {4: 6, 3: 1}); of those, the forecast had measured the piece's price (a line held it) 3, at 500 or more 1.

A5: the same piece at the seat's two decisions before K (the world holding it with the largest p):

| at the two decisions before K | n |
|---|---|
| no candidate 200 cp better | 33 |
| no world held the piece at either | 13 |
| a candidate held (>= -300) where the move played fell | 4 |
| a candidate 200+ cp better, not holding | 3 |

## Flags at K, by class

| class | n | in check | king off home rank | 3+ king-zone squares attacked | partner sat in the step | partner's board below -300 | K switched | opponent's hand 6+ | our hand 6+ | clock 5 s+ behind |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 13 | 5 | 4 | 5 | 1 | 5 | 2 | 8 | 8 | 0 |
| A3 | 13 | 5 | 2 | 4 | 0 | 4 | 4 | 6 | 10 | 0 |
| A4 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| A5 | 53 | 20 | 20 | 18 | 0 | 21 | 15 | 23 | 36 | 2 |
| C1 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| C2 | 3 | 0 | 1 | 1 | 0 | 3 | 0 | 2 | 1 | 0 |
| C3 | 8 | 0 | 1 | 1 | 0 | 4 | 1 | 8 | 5 | 1 |
| C5 | 9 | 2 | 2 | 2 | 0 | 2 | 9 | 7 | 8 | 0 |
| G | 5 | 1 | 0 | 2 | 0 | 2 | 5 | 4 | 4 | 0 |
| H | 2 | 2 | 1 | 2 | 0 | 1 | 0 | 1 | 2 | 0 |
| S | 4 | 0 | 0 | 1 | 0 | 1 | 1 | 3 | 2 | 0 |
| all | 113 | 36 | 32 | 37 | 1 | 44 | 37 | 62 | 77 | 3 |

## Information that existed

| class | n | its worlds had a move 200+ better in the world that came true | ... and that move cost <= 100 in "none" | partner's own line had the capture | partner had a candidate within 150 cp | fall visible at depth 1 at N | K's score fell with depth |
|---|---|---|---|---|---|---|---|
| A1 | 13 | 0 | 0 | 8 of 13 | 7 of 13 | 10 | 2 |
| A3 | 13 | 1 | 1 | 8 of 13 | 6 of 13 | 4 | 2 |
| A4 | 2 | 0 | 0 | 1 of 2 | 2 of 2 | 2 | 0 |
| A5 | 53 | 3 | 0 | 26 of 53 | 33 of 53 | 43 | 5 |
| C1 | 1 | 0 | 0 | 0 of 1 | 1 of 1 | 1 | 0 |
| C2 | 3 | 0 | 0 | 1 of 3 | 2 of 3 | 1 | 2 |
| C3 | 8 | 0 | 0 | 2 of 7 | 6 of 7 | 4 | 2 |
| C5 | 9 | 0 | 0 | 5 of 7 | 3 of 7 | 5 | 3 |
| G | 5 | 5 | 5 | 2 of 2 | 0 of 2 | 5 | 2 |
| H | 2 | 0 | 0 | 2 of 2 | 2 of 2 | 2 | 0 |
| S | 4 | 1 | 1 | 1 of 2 | 1 of 2 | 1 | 0 |

## Shape of the fall

Key step: the last step into F in 99, one before in 7, two before in 7. The fall was the seat's last decision in 1. The seat ended mated in 79.

| drop at the key step (clipped at +-3000) | n | team lost |
|---|---|---|
| -100000 to -3000 | 14 | 14 |
| -3000 to -1500 | 8 | 8 |
| -1500 to -800 | 22 | 20 |
| -800 to -500 | 27 | 23 |
| -500 to -300 | 26 | 22 |
| -300 to -200 | 12 | 9 |
| -200 to 0 | 4 | 3 |

