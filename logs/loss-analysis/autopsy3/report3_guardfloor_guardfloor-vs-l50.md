# AUTOPSY3 tables (falls_guardfloor_guardfloor-vs-l50.json)

Seats: 200; falls: 74 (56 on teams that lost, 18 on teams that won, 0 drawn). Team's first fall in lost games: 37. Seats that never fell: 126.

## Classes

| class | all falls | team lost | team's first fall, lost | key step: score at K → at N (medians) | N a forced mate |
|---|---|---|---|---|---|
| A1 arrival in no world | 5 | 4 | 4 | +100 → -689 | 1 |
| A3 arrival; its world had the move played holding | 3 | 2 | 2 | +545 → -446 | 1 |
| A5 arrival; every candidate fell in its world | 33 | 26 | 16 | -8 → -746 | 9 |
| C1 own board: a forced mate appeared | 3 | 3 | 3 | -159 → -99992 | 3 |
| C2 own board: the reply K's line expected | 11 | 6 | 4 | -47 → -455 | 0 |
| C3 own board: another reply | 3 | 2 | 0 | +62 → -616 | 0 |
| C5 own board after a switch (no line for the move played) | 6 | 5 | 2 | +17 → -484 | 0 |
| H a sit | 3 | 1 | 0 | +639 → -137 | 0 |
| S slide (no step of 200 cp) | 5 | 5 | 4 | -224 → -361 | 0 |
| O lost from the first decision | 2 | 2 | 2 | - → - | 0 |

By match (all falls):

| class | guardfloor-vs-l50 |
|---|---|
| A1 | 5 |
| A3 | 3 |
| A5 | 33 |
| C1 | 3 |
| C2 | 11 |
| C3 | 3 |
| C5 | 6 |
| H | 3 |
| S | 5 |
| O | 2 |
| seats | 200 |

## Arrival falls

| class | n | fatal piece Q / R / B / N / P | world p (median) | move played in "none" → in its world (median) | best candidate in its world (median) | candidates compared (median) | seen at 1+ of the 2 decisions before (p>=0.10) |
|---|---|---|---|---|---|---|---|
| A1 | 5 | 1 / 0 / 2 / 2 / 0 | - | +55 → - | - | 2 | 2 |
| A3 | 3 | 2 / 1 / 0 / 0 / 0 | 0.22 | +367 → -204 | -204 | 3 | 2 |
| A5 | 33 | 12 / 3 / 7 / 8 / 3 | 0.30 | -83 → -693 | -693 | 3 | 19 |

A1 split: no worlds scored at K 1 (reasons {'only_move': 1}; one legal move 1); worlds scored but none held the piece 4 (worlds scored: {2: 1, 3: 1, 4: 2}); of those, the forecast had measured the piece's price (a line held it) 3, at 500 or more 1.

A5: the same piece at the seat's two decisions before K (the world holding it with the largest p):

| at the two decisions before K | n |
|---|---|
| no candidate 200 cp better | 19 |
| no world held the piece at either | 10 |
| a candidate 200+ cp better, not holding | 3 |
| a candidate held (>= -300) where the move played fell | 1 |

## Flags at K, by class

| class | n | in check | king off home rank | 3+ king-zone squares attacked | partner sat in the step | partner's board below -300 | K switched | opponent's hand 6+ | our hand 6+ | clock 5 s+ behind |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 5 | 2 | 0 | 2 | 0 | 2 | 1 | 2 | 3 | 0 |
| A3 | 3 | 1 | 1 | 1 | 0 | 1 | 2 | 2 | 1 | 0 |
| A5 | 33 | 16 | 12 | 19 | 0 | 11 | 9 | 14 | 22 | 1 |
| C1 | 3 | 2 | 0 | 1 | 0 | 1 | 1 | 3 | 3 | 0 |
| C2 | 11 | 0 | 3 | 3 | 0 | 2 | 1 | 8 | 8 | 0 |
| C3 | 3 | 0 | 1 | 0 | 0 | 3 | 0 | 2 | 1 | 0 |
| C5 | 6 | 2 | 3 | 3 | 0 | 3 | 6 | 4 | 4 | 0 |
| H | 3 | 1 | 2 | 1 | 0 | 1 | 0 | 2 | 2 | 0 |
| S | 5 | 1 | 1 | 2 | 0 | 1 | 2 | 1 | 3 | 1 |
| all | 72 | 25 | 23 | 32 | 0 | 25 | 22 | 38 | 47 | 2 |

## Information that existed

| class | n | its worlds had a move 200+ better in the world that came true | ... and that move cost <= 100 in "none" | partner's own line had the capture | partner had a candidate within 150 cp | fall visible at depth 1 at N | K's score fell with depth |
|---|---|---|---|---|---|---|---|
| A1 | 5 | 0 | 0 | 4 of 5 | 3 of 5 | 4 | 0 |
| A3 | 3 | 0 | 0 | 2 of 3 | 1 of 3 | 0 | 0 |
| A5 | 33 | 3 | 0 | 20 of 33 | 24 of 33 | 27 | 4 |
| C1 | 3 | 0 | 0 | 1 of 3 | 3 of 3 | 2 | 0 |
| C2 | 11 | 0 | 0 | 3 of 10 | 8 of 10 | 7 | 2 |
| C3 | 3 | 0 | 0 | 1 of 2 | 2 of 2 | 1 | 0 |
| C5 | 6 | 1 | 1 | 4 of 6 | 3 of 6 | 5 | 2 |
| H | 3 | 0 | 0 | 2 of 3 | 1 of 3 | 2 | 0 |
| S | 5 | 1 | 1 | 2 of 3 | 2 of 3 | 3 | 0 |

## Shape of the fall

Key step: the last step into F in 61, one before in 4, two before in 7. The fall was the seat's last decision in 4. The seat ended mated in 45.

| drop at the key step (clipped at +-3000) | n | team lost |
|---|---|---|
| -100000 to -3000 | 11 | 10 |
| -3000 to -1500 | 4 | 4 |
| -1500 to -800 | 14 | 8 |
| -800 to -500 | 9 | 7 |
| -500 to -300 | 22 | 16 |
| -300 to -200 | 7 | 4 |
| -200 to 0 | 5 | 5 |

