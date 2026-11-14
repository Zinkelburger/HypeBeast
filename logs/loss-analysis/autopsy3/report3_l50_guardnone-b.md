# AUTOPSY3 tables (falls_l50_guardnone-b.json)

Seats: 600; falls: 278 (207 on teams that lost, 71 on teams that won, 0 drawn). Team's first fall in lost games: 139. Seats that never fell: 322.

## Classes

| class | all falls | team lost | team's first fall, lost | key step: score at K → at N (medians) | N a forced mate |
|---|---|---|---|---|---|
| A1 arrival in no world | 37 | 29 | 15 | +22 → -884 | 14 |
| A3 arrival; its world had the move played holding | 17 | 13 | 11 | +214 → -250 | 1 |
| A4 arrival; another candidate held in its world | 4 | 4 | 4 | +227 → -99992 | 3 |
| A5 arrival; every candidate fell in its world | 119 | 96 | 70 | -5 → -831 | 26 |
| C1 own board: a forced mate appeared | 5 | 5 | 5 | +161 → -99988 | 5 |
| C2 own board: the reply K's line expected | 10 | 7 | 5 | -34 → -386 | 0 |
| C3 own board: another reply | 19 | 13 | 6 | -148 → -490 | 0 |
| C5 own board after a switch (no line for the move played) | 32 | 22 | 11 | -47 → -513 | 0 |
| G a switch that went wrong | 6 | 6 | 2 | +290 → -648 | 0 |
| H a sit | 7 | 0 | 0 | -49 → -567 | 1 |
| S slide (no step of 200 cp) | 19 | 9 | 7 | -242 → -353 | 0 |
| O lost from the first decision | 3 | 3 | 3 | - → - | 0 |

By match (all falls):

| class | guardnone-b |
|---|---|
| A1 | 37 |
| A3 | 17 |
| A4 | 4 |
| A5 | 119 |
| C1 | 5 |
| C2 | 10 |
| C3 | 19 |
| C5 | 32 |
| G | 6 |
| H | 7 |
| S | 19 |
| O | 3 |
| seats | 600 |

## Arrival falls

| class | n | fatal piece Q / R / B / N / P | world p (median) | move played in "none" → in its world (median) | best candidate in its world (median) | candidates compared (median) | seen at 1+ of the 2 decisions before (p>=0.10) |
|---|---|---|---|---|---|---|---|
| A1 | 37 | 13 / 9 / 5 / 9 / 1 | - | +28 → - | - | 2 | 20 |
| A3 | 17 | 5 / 0 / 5 / 5 / 2 | 0.24 | +237 → -233 | -194 | 3 | 12 |
| A4 | 4 | 0 / 1 / 2 / 1 / 0 | 0.19 | +168 → -634 | -72 | 4 | 2 |
| A5 | 119 | 57 / 14 / 12 / 28 / 8 | 0.27 | -109 → -816 | -751 | 3 | 82 |

A1 split: no worlds scored at K 12 (reasons {'only_move': 7, 'no_arrivals': 5}; one legal move 7); worlds scored but none held the piece 25 (worlds scored: {3: 3, 4: 20, 2: 2}); of those, the forecast had measured the piece's price (a line held it) 13, at 500 or more 6.

A5: the same piece at the seat's two decisions before K (the world holding it with the largest p):

| at the two decisions before K | n |
|---|---|
| no candidate 200 cp better | 72 |
| no world held the piece at either | 30 |
| a candidate held (>= -300) where the move played fell | 11 |
| a candidate 200+ cp better, not holding | 6 |

## Flags at K, by class

| class | n | in check | king off home rank | 3+ king-zone squares attacked | partner sat in the step | partner's board below -300 | K switched | opponent's hand 6+ | our hand 6+ | clock 5 s+ behind |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 37 | 13 | 13 | 16 | 2 | 12 | 3 | 13 | 25 | 1 |
| A3 | 17 | 3 | 5 | 3 | 0 | 6 | 6 | 4 | 8 | 0 |
| A4 | 4 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 4 | 0 |
| A5 | 119 | 50 | 43 | 56 | 0 | 42 | 35 | 54 | 88 | 3 |
| C1 | 5 | 4 | 2 | 3 | 0 | 1 | 0 | 4 | 4 | 1 |
| C2 | 10 | 1 | 1 | 1 | 0 | 5 | 0 | 5 | 3 | 0 |
| C3 | 19 | 2 | 3 | 5 | 1 | 10 | 1 | 14 | 9 | 0 |
| C5 | 32 | 6 | 8 | 7 | 0 | 13 | 32 | 20 | 18 | 1 |
| G | 6 | 2 | 1 | 3 | 0 | 3 | 6 | 4 | 5 | 2 |
| H | 7 | 1 | 4 | 2 | 0 | 0 | 0 | 3 | 4 | 0 |
| S | 19 | 5 | 5 | 4 | 1 | 2 | 6 | 11 | 10 | 0 |
| all | 275 | 88 | 86 | 101 | 4 | 95 | 90 | 133 | 178 | 8 |

## Information that existed

| class | n | its worlds had a move 200+ better in the world that came true | ... and that move cost <= 100 in "none" | partner's own line had the capture | partner had a candidate within 150 cp | fall visible at depth 1 at N | K's score fell with depth |
|---|---|---|---|---|---|---|---|
| A1 | 37 | 0 | 0 | 18 of 37 | 20 of 37 | 25 | 2 |
| A3 | 17 | 2 | 0 | 11 of 17 | 13 of 17 | 2 | 3 |
| A4 | 4 | 3 | 0 | 2 of 4 | 4 of 4 | 2 | 0 |
| A5 | 119 | 8 | 1 | 77 of 119 | 69 of 119 | 95 | 7 |
| C1 | 5 | 0 | 0 | 1 of 4 | 2 of 4 | 2 | 1 |
| C2 | 10 | 2 | 0 | 2 of 8 | 8 of 8 | 3 | 1 |
| C3 | 19 | 0 | 0 | 8 of 14 | 11 of 14 | 10 | 7 |
| C5 | 32 | 3 | 3 | 15 of 24 | 16 of 24 | 19 | 5 |
| G | 6 | 6 | 6 | 3 of 3 | 2 of 3 | 6 | 0 |
| H | 7 | 0 | 0 | 6 of 7 | 4 of 7 | 4 | 0 |
| S | 19 | 2 | 1 | 6 of 9 | 6 of 9 | 9 | 2 |

## Shape of the fall

Key step: the last step into F in 223, one before in 20, two before in 32. The fall was the seat's last decision in 15. The seat ended mated in 186.

| drop at the key step (clipped at +-3000) | n | team lost |
|---|---|---|
| -100000 to -3000 | 31 | 28 |
| -3000 to -1500 | 30 | 29 |
| -1500 to -800 | 42 | 30 |
| -800 to -500 | 65 | 49 |
| -500 to -300 | 62 | 39 |
| -300 to -200 | 26 | 20 |
| -200 to 0 | 19 | 9 |

