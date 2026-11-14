# Post-mortem: late50-vs-np-b

100 games, 11446 decisions. Score: hb-late50 56.5, hb-np 43.5.

## Did the stated winning chances come true?

From the main search's score (logistic, 1000 cp per unit; a mate is 0% or 100%). Decisions of one game are not independent, so read the columns as a shape, not to the digit.

| stated | hb-late50: n | hb-late50: mean stated | hb-late50: won | hb-np: n | hb-np: mean stated | hb-np: won |
|---|---|---|---|---|---|---|
| 0-10% | 348 | 1.0% | 8.0% | 445 | 0.5% | 6.1% |
| 10-25% | 307 | 18.0% | 28.0% | 210 | 18.2% | 20.0% |
| 25-40% | 736 | 34.0% | 40.7% | 668 | 34.2% | 30.4% |
| 40-60% | 2897 | 50.3% | 54.7% | 2840 | 50.0% | 45.1% |
| 60-75% | 724 | 66.0% | 67.9% | 830 | 66.0% | 58.0% |
| 75-90% | 233 | 82.5% | 83.7% | 330 | 81.7% | 73.3% |
| 90-100% | 343 | 99.1% | 93.9% | 298 | 98.1% | 88.9% |

## Did the forecast worlds come true?

An arrival world counts as true when its whole package had reached the hands before ply q of our board (q=1: the opponent's reply, q=2: our next move). Only decisions with 6 or more plies of our board left.

**hb-late50** (Brier score against "arrived by q<=4": 0.202 over 12517 worlds)

| stated p | worlds | mean p | by q<=1 | by q<=2 | by q<=4 | by q<=6 |
|---|---|---|---|---|---|---|
| 0.00-0.10 | 2652 | 0.07 | 1.2% | 5.6% | 14.3% | 22.8% |
| 0.10-0.20 | 5323 | 0.14 | 4.4% | 12.3% | 25.1% | 34.5% |
| 0.20-0.35 | 3059 | 0.26 | 10.9% | 24.3% | 40.0% | 49.2% |
| 0.35-0.60 | 1243 | 0.44 | 16.9% | 33.1% | 50.5% | 60.8% |
| 0.60-1.00 | 240 | 0.73 | 56.7% | 77.9% | 85.0% | 87.1% |

| stated "nothing arrives" | decisions | nothing by q<=1 | by q<=2 | by q<=4 |
|---|---|---|---|---|
| 0.0-0.3 | 882 | 32.9% | 12.2% | 3.5% |
| 0.3-0.5 | 1716 | 53.1% | 31.4% | 11.0% |
| 0.5-0.7 | 1600 | 76.9% | 53.7% | 22.2% |
| 0.7-0.9 | 453 | 94.9% | 82.3% | 53.6% |
| 0.9-1.0 | 270 | 93.0% | 90.0% | 75.9% |

**hb-np** (Brier score against "arrived by q<=4": 0.220 over 9711 worlds)

| stated p | worlds | mean p | by q<=1 | by q<=2 | by q<=4 | by q<=6 |
|---|---|---|---|---|---|---|
| 0.00-0.10 | 2381 | 0.07 | 1.4% | 8.9% | 18.7% | 27.6% |
| 0.10-0.20 | 3111 | 0.15 | 2.8% | 15.3% | 28.2% | 38.9% |
| 0.20-0.35 | 2227 | 0.26 | 9.9% | 28.1% | 43.0% | 52.4% |
| 0.35-0.60 | 1334 | 0.45 | 26.1% | 48.4% | 62.2% | 68.5% |
| 0.60-1.00 | 658 | 0.74 | 50.6% | 72.5% | 79.6% | 83.7% |

| stated "nothing arrives" | decisions | nothing by q<=1 | by q<=2 | by q<=4 |
|---|---|---|---|---|
| 0.0-0.3 | 1302 | 33.9% | 13.6% | 4.3% |
| 0.3-0.5 | 1150 | 49.7% | 30.1% | 10.2% |
| 0.5-0.7 | 947 | 72.0% | 48.9% | 20.7% |
| 0.7-0.9 | 837 | 90.2% | 70.3% | 35.1% |
| 0.9-1.0 | 704 | 94.7% | 82.5% | 55.5% |

## When did a forecast piece arrive?

A piece (side and type) by the earliest ply k at which any forecast line names it, all engines, decisions with 6 or more plies left: share in that hand before ply q of our board.

| named at ply k | pieces | q<=1 | q<=2 | q<=3 | q<=4 | q<=5 | q<=6 |
|---|---|---|---|---|---|---|---|
| 0 | 15219 | 22.7% | 26.0% | 35.7% | 39.2% | 45.7% | 48.9% |
| 1 | 17424 | 1.6% | 16.8% | 20.6% | 29.3% | 32.9% | 38.8% |
| 2 | 5457 | 0.1% | 1.9% | 15.6% | 19.7% | 27.7% | 31.3% |
| 3 | 6774 | 0.4% | 4.1% | 6.1% | 14.4% | 18.0% | 24.5% |

## Arrivals nobody forecast

What reached the OPPONENT's hand before our next move (q<=2), and the main score at the seat's next decision minus the score now (mates left out).

| engine | to the opponent by q<=2 | decisions | share | mean change in score (cp) | then saw itself mated |
|---|---|---|---|---|---|
| hb-late50 | nothing arrived | 3357 | 61.6% | +110 | 11 |
| hb-late50 | all of it was in a world | 1806 | 33.1% | -168 | 36 |
| hb-late50 | a piece in no world | 285 | 5.2% | -275 | 7 |
| hb-np | nothing arrived | 3380 | 61.6% | +126 | 18 |
| hb-np | all of it was in a world | 1732 | 31.6% | -194 | 43 |
| hb-np | a piece in no world | 375 | 6.8% | -257 | 14 |

## Switching away from the main search's move

| engine | decision | n | share | mean change in score by the next decision (cp) | games won |
|---|---|---|---|---|---|
| hb-late50 | kept | 4640 | 81.3% | +13 | 52.7% |
| hb-late50 | switched | 1065 | 18.7% | -35 | 54.6% |
| hb-np | kept | 4952 | 86.3% | +14 | 43.7% |
| hb-np | switched | 789 | 13.7% | -46 | 48.8% |

| engine | reason for the switch | n |
|---|---|---|
| hb-late50 | world_switch | 1024 |
| hb-np | world_switch | 739 |
| hb-np | exposure_veto | 32 |
| hb-late50 | exposure_veto | 15 |
| hb-late50 | soft_switch | 13 |
| hb-late50 | delivery_win | 13 |
| hb-np | delivery_win | 9 |
| hb-np | soft_switch | 9 |

## First to see itself mated

| engine | games in which it was first | of those lost |
|---|---|---|
| hb-late50 | 43 | 41 |
| hb-np | 56 | 54 |

## Sudden collapses

Decisions at -300 cp or better whose next decision was a forced mate against the seat. "Fatal piece": what reached the opponent's hand before our next move. For the partner: its last decision before that capture, and whether the capture was the reply its own main line expected.

| engine | collapses | what the seat knew | n |
|---|---|---|---|
| hb-late50 | 18 | in a world, where every candidate was mated | 11 |
| hb-late50 | 18 | in a world, where the move played was not mated | 3 |
| hb-late50 | 18 | in a world, but the move was not scored there | 2 |
| hb-late50 | 18 | the piece was in no world | 2 |
| hb-late50 | 18 | fatal pieces: -Q 14, -N 4, -P 1, -R 1 |  |
| hb-np | 28 | in a world, where every candidate was mated | 14 |
| hb-np | 28 | in a world, where the move played was not mated | 8 |
| hb-np | 28 | in a world, but the move was not scored there | 3 |
| hb-np | 28 | the piece was in no world | 3 |
| hb-np | 28 | fatal pieces: -Q 10, -N 10, -R 6, -B 2, -P 2 |  |

| engine | the partner's last decision before the capture | n | partner ahead (>300) | level | behind (<-300) | our team took a piece there too |
|---|---|---|---|---|---|---|
| hb-late50 | the partner's own line had that capture | 10 | 5 | 3 | 2 | 10 |
| hb-late50 | the partner's line expected another reply | 8 | 5 | 1 | 2 | 5 |
| hb-np | the partner's line expected another reply | 16 | 9 | 5 | 2 | 14 |
| hb-np | the partner's own line had that capture | 12 | 6 | 2 | 4 | 10 |

## The 15 decisions followed by the largest drop

Score now and at the seat's next decision (mate = -100000). "to them" is what reached the opponent's hand before our next move, with the largest stated probability of a world holding it (0: in none).

| engine | game | seat | moves played | score | next | played | to them | game |
|---|---|---|---|---|---|---|---|---|
| hb-late50 | 96 | Awhite | 137 | 99971 | -99986 | h2g1 | -Q (p 0.32) | lost |
| hb-np | 22 | Bwhite | 140 | 2265 | -99998 | c2b1 | -Q (p 0.82) | lost |
| hb-late50 | 93 | Ablack | 102 | 1869 | -99998 | e7f8 | -Q (p 0.46), -N (p 0.46) | lost |
| hb-np | 16 | Ablack | 84 | 1230 | -99998 | R@g5 | -Q (p 0.76), -R (p 0.00) | lost |
| hb-np | 40 | Bwhite | 62 | 1168 | -99998 | h1g2 | -Q (p 0.85), -P (p 0.00) | lost |
| hb-np | 25 | Awhite | 101 | 1173 | -99990 | e3g5 | -N (p 0.10) | lost |
| hb-np | 58 | Bwhite | 88 | 1067 | -99984 | c3c4 (main c3d3) | -Q (p 0.81) | lost |
| hb-late50 | 2 | Bblack | 98 | 1005 | -99998 | pass | -Q (p 0.85) | lost |
| hb-late50 | 77 | Ablack | 169 | 922 | -99998 | e7d5 | -Q (p 0.77) | lost |
| hb-np | 80 | Ablack | 82 | 875 | -99996 | Q@g6 | -N (p 0.46) | lost |
| hb-np | 65 | Bblack | 160 | 849 | -99998 | g7f6 | -Q (p 0.85) | lost |
| hb-late50 | 54 | Bblack | 72 | 707 | -99998 | pass | -Q (p 0.82) | lost |
| hb-late50 | 3 | Bwhite | 116 | 668 | -99998 | f2f3 | -N (p 0.35), -P (p 0.00) | lost |
| hb-late50 | 27 | Bwhite | 111 | 609 | -99996 | g2f3 | -Q (p 0.29) | lost |
| hb-np | 69 | Bblack | 106 | 537 | -99998 | g8f8 | -R (p 0.53) | lost |

## Missed supplies

Episodes in which a scored world of a single +T had the move played at a mate for us while the "none" world did not (one episode: consecutive decisions of one seat in one game with the same T). "At once": the partner's next move on the other board had a legal capture of a T (a promoted piece is a P). Each cell: episodes (games won by the seat's team).

| engine | T | all | partner could take a T at once | of those, took one (now or within 2 moves) | could, did not | could not | a T reached the seat's hand before its next move |
|---|---|---|---|---|---|---|---|
| hb-late50 | any | 30 (80.0%) | 20 (85.0%) | 13 (92.3%) | 7 (71.4%) | 10 (70.0%) | 11 (100.0%) |
| hb-late50 | P | 6 (100.0%) | 5 (100.0%) | 2 (100.0%) | 3 (100.0%) | 1 (100.0%) | 2 (100.0%) |
| hb-late50 | N | 7 (78.6%) | 5 (100.0%) | 5 (100.0%) | 0 (-) | 2 (25.0%) | 5 (100.0%) |
| hb-late50 | B | 2 (100.0%) | 1 (100.0%) | 0 (-) | 1 (100.0%) | 1 (100.0%) | 0 (-) |
| hb-late50 | R | 4 (75.0%) | 3 (66.7%) | 2 (100.0%) | 1 (0.0%) | 1 (100.0%) | 1 (100.0%) |
| hb-late50 | Q | 11 (68.2%) | 6 (66.7%) | 4 (75.0%) | 2 (50.0%) | 5 (70.0%) | 3 (100.0%) |
| hb-np | any | 22 (90.9%) | 20 (90.0%) | 13 (100.0%) | 7 (71.4%) | 2 (100.0%) | 13 (100.0%) |
| hb-np | P | 1 (100.0%) | 1 (100.0%) | 1 (100.0%) | 0 (-) | 0 (-) | 1 (100.0%) |
| hb-np | N | 6 (66.7%) | 6 (66.7%) | 3 (100.0%) | 3 (33.3%) | 0 (-) | 3 (100.0%) |
| hb-np | B | 1 (100.0%) | 1 (100.0%) | 0 (-) | 1 (100.0%) | 0 (-) | 0 (-) |
| hb-np | R | 5 (100.0%) | 4 (100.0%) | 1 (100.0%) | 3 (100.0%) | 1 (100.0%) | 1 (100.0%) |
| hb-np | Q | 9 (100.0%) | 8 (100.0%) | 8 (100.0%) | 0 (-) | 1 (100.0%) | 8 (100.0%) |

