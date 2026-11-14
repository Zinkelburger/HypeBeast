# Post-mortem: late50-vs-late25

100 games, 11768 decisions. Score: hb-late25 43, hb-late50 57.

## Did the stated winning chances come true?

From the main search's score (logistic, 1000 cp per unit; a mate is 0% or 100%). Decisions of one game are not independent, so read the columns as a shape, not to the digit.

| stated | hb-late25: n | hb-late25: mean stated | hb-late25: won | hb-late50: n | hb-late50: mean stated | hb-late50: won |
|---|---|---|---|---|---|---|
| 0-10% | 422 | 0.7% | 0.2% | 443 | 0.9% | 2.9% |
| 10-25% | 240 | 18.1% | 6.7% | 264 | 18.0% | 20.1% |
| 25-40% | 585 | 33.8% | 21.4% | 844 | 33.4% | 40.3% |
| 40-60% | 2918 | 50.3% | 43.0% | 2954 | 50.0% | 56.4% |
| 60-75% | 919 | 66.4% | 56.7% | 669 | 65.9% | 77.9% |
| 75-90% | 312 | 81.7% | 80.4% | 269 | 82.0% | 89.2% |
| 90-100% | 367 | 98.5% | 96.5% | 350 | 98.7% | 100.0% |

## Did the forecast worlds come true?

An arrival world counts as true when its whole package had reached the hands before ply q of our board (q=1: the opponent's reply, q=2: our next move). Only decisions with 6 or more plies of our board left.

**hb-late25** (Brier score against "arrived by q<=4": 0.214 over 12861 worlds)

| stated p | worlds | mean p | by q<=1 | by q<=2 | by q<=4 | by q<=6 |
|---|---|---|---|---|---|---|
| 0.00-0.10 | 4007 | 0.07 | 0.9% | 5.8% | 16.3% | 25.7% |
| 0.10-0.20 | 4621 | 0.14 | 3.6% | 13.8% | 29.2% | 39.4% |
| 0.20-0.35 | 2595 | 0.26 | 11.6% | 27.9% | 44.7% | 54.5% |
| 0.35-0.60 | 1285 | 0.45 | 33.7% | 56.4% | 68.5% | 74.9% |
| 0.60-1.00 | 353 | 0.70 | 43.6% | 68.8% | 79.3% | 84.1% |

| stated "nothing arrives" | decisions | nothing by q<=1 | by q<=2 | by q<=4 |
|---|---|---|---|---|
| 0.0-0.3 | 905 | 32.3% | 13.8% | 5.2% |
| 0.3-0.5 | 1608 | 48.1% | 25.0% | 7.8% |
| 0.5-0.7 | 1475 | 73.4% | 49.6% | 18.1% |
| 0.7-0.9 | 799 | 93.4% | 75.5% | 37.8% |
| 0.9-1.0 | 325 | 93.5% | 85.2% | 65.2% |

**hb-late50** (Brier score against "arrived by q<=4": 0.197 over 13160 worlds)

| stated p | worlds | mean p | by q<=1 | by q<=2 | by q<=4 | by q<=6 |
|---|---|---|---|---|---|---|
| 0.00-0.10 | 2765 | 0.07 | 1.1% | 4.8% | 13.7% | 22.7% |
| 0.10-0.20 | 5596 | 0.14 | 4.0% | 11.8% | 23.9% | 32.9% |
| 0.20-0.35 | 3259 | 0.26 | 11.3% | 24.5% | 40.1% | 49.2% |
| 0.35-0.60 | 1282 | 0.44 | 16.7% | 33.2% | 47.8% | 56.9% |
| 0.60-1.00 | 258 | 0.73 | 51.9% | 72.9% | 79.1% | 82.6% |

| stated "nothing arrives" | decisions | nothing by q<=1 | by q<=2 | by q<=4 |
|---|---|---|---|---|
| 0.0-0.3 | 896 | 34.2% | 14.1% | 5.7% |
| 0.3-0.5 | 1895 | 56.3% | 33.5% | 11.1% |
| 0.5-0.7 | 1636 | 74.4% | 52.1% | 22.4% |
| 0.7-0.9 | 443 | 93.7% | 80.1% | 48.8% |
| 0.9-1.0 | 224 | 88.4% | 78.1% | 58.5% |

## When did a forecast piece arrive?

A piece (side and type) by the earliest ply k at which any forecast line names it, all engines, decisions with 6 or more plies left: share in that hand before ply q of our board.

| named at ply k | pieces | q<=1 | q<=2 | q<=3 | q<=4 | q<=5 | q<=6 |
|---|---|---|---|---|---|---|---|
| 0 | 15902 | 22.7% | 26.0% | 36.0% | 39.4% | 46.1% | 49.4% |
| 1 | 18223 | 1.6% | 17.0% | 20.5% | 28.8% | 32.5% | 38.6% |
| 2 | 5448 | 0.0% | 2.3% | 15.5% | 19.8% | 26.8% | 30.5% |
| 3 | 6920 | 0.2% | 4.2% | 6.7% | 15.5% | 19.7% | 25.7% |

## Arrivals nobody forecast

What reached the OPPONENT's hand before our next move (q<=2), and the main score at the seat's next decision minus the score now (mates left out).

| engine | to the opponent by q<=2 | decisions | share | mean change in score (cp) | then saw itself mated |
|---|---|---|---|---|---|
| hb-late25 | nothing arrived | 3495 | 61.8% | +131 | 20 |
| hb-late25 | all of it was in a world | 1878 | 33.2% | -200 | 45 |
| hb-late25 | a piece in no world | 286 | 5.1% | -272 | 10 |
| hb-late50 | nothing arrived | 3435 | 61.1% | +111 | 17 |
| hb-late50 | all of it was in a world | 1903 | 33.9% | -177 | 37 |
| hb-late50 | a piece in no world | 282 | 5.0% | -193 | 10 |

## Switching away from the main search's move

| engine | decision | n | share | mean change in score by the next decision (cp) | games won |
|---|---|---|---|---|---|
| hb-late25 | kept | 5040 | 85.5% | +15 | 42.7% |
| hb-late25 | switched | 854 | 14.5% | -42 | 43.6% |
| hb-late50 | kept | 4712 | 80.2% | +12 | 54.1% |
| hb-late50 | switched | 1162 | 19.8% | -29 | 55.0% |

| engine | reason for the switch | n |
|---|---|---|
| hb-late50 | world_switch | 1120 |
| hb-late25 | world_switch | 798 |
| hb-late25 | exposure_veto | 38 |
| hb-late50 | exposure_veto | 18 |
| hb-late25 | soft_switch | 14 |
| hb-late50 | delivery_win | 13 |
| hb-late50 | soft_switch | 11 |
| hb-late25 | delivery_win | 4 |

## First to see itself mated

| engine | games in which it was first | of those lost |
|---|---|---|
| hb-late25 | 58 | 57 |
| hb-late50 | 41 | 41 |

## Sudden collapses

Decisions at -300 cp or better whose next decision was a forced mate against the seat. "Fatal piece": what reached the opponent's hand before our next move. For the partner: its last decision before that capture, and whether the capture was the reply its own main line expected.

| engine | collapses | what the seat knew | n |
|---|---|---|---|
| hb-late25 | 19 | in a world, where every candidate was mated | 12 |
| hb-late25 | 19 | the piece was in no world | 2 |
| hb-late25 | 19 | in a world, but the move was not scored there | 2 |
| hb-late25 | 19 | in a world, where the move played was not mated | 1 |
| hb-late25 | 19 | in a world, where another candidate was not mated | 1 |
| hb-late25 | 19 | nothing reached the opponent | 1 |
| hb-late25 | 19 | fatal pieces: -Q 12, -N 4, -B 2, -R 2, -P 2 |  |
| hb-late50 | 15 | in a world, where the move played was not mated | 6 |
| hb-late50 | 15 | in a world, where every candidate was mated | 5 |
| hb-late50 | 15 | in a world, but the move was not scored there | 2 |
| hb-late50 | 15 | the piece was in no world | 2 |
| hb-late50 | 15 | fatal pieces: -Q 5, -N 4, -R 3, -P 2, -B 1 |  |

| engine | the partner's last decision before the capture | n | partner ahead (>300) | level | behind (<-300) | our team took a piece there too |
|---|---|---|---|---|---|---|
| hb-late25 | the partner's own line had that capture | 9 | 4 | 4 | 1 | 8 |
| hb-late25 | the partner's line expected another reply | 9 | 4 | 4 | 1 | 7 |
| hb-late50 | the partner's line expected another reply | 9 | 2 | 3 | 4 | 7 |
| hb-late50 | the partner's own line had that capture | 6 | 0 | 3 | 3 | 5 |

## The 15 decisions followed by the largest drop

Score now and at the seat's next decision (mate = -100000). "to them" is what reached the opponent's hand before our next move, with the largest stated probability of a world holding it (0: in none).

| engine | game | seat | moves played | score | next | played | to them | game |
|---|---|---|---|---|---|---|---|---|
| hb-late25 | 77 | Awhite | 80 | 1493 | -99996 | pass | -Q (p 0.59) | lost |
| hb-late50 | 35 | Bwhite | 143 | 1107 | -99990 | P@f2 | -Q (p 0.08) | lost |
| hb-late25 | 18 | Ablack | 78 | 1081 | -99996 | g7h6 | -Q (p 0.82) | lost |
| hb-late25 | 95 | Bblack | 143 | 1025 | -99998 | b1a1 | -N (p 0.00), -Q (p 0.23) | lost |
| hb-late50 | 14 | Awhite | 114 | 830 | -99998 | d2c2 | -Q (p 0.66) | lost |
| hb-late25 | 9 | Awhite | 74 | 763 | -99996 | g1g2 (main d1e2) | -Q (p 0.43) | lost |
| hb-late25 | 19 | Awhite | 60 | 653 | -99998 | e1e2 (main b2c3) | -Q (p 0.73) | lost |
| hb-late50 | 88 | Awhite | 112 | 482 | -99994 | g2f3 | -R (p 0.05) | lost |
| hb-late25 | 65 | Awhite | 92 | 401 | -99998 | f2g1 | -R (p 0.43), -P (p 0.00) | lost |
| hb-late50 | 59 | Bwhite | 118 | 400 | -99992 | h1g2 | -B (p 0.34) | lost |
| hb-late50 | 3 | Bwhite | 112 | 329 | -99996 | b2c3 | -N (p 0.38) | lost |
| hb-late25 | 63 | Bblack | 104 | 248 | -99996 | g8h8 | -Q (p 0.47) | lost |
| hb-late25 | 61 | Awhite | 74 | 149 | -99990 | d2c3 | -B (p 0.42) | lost |
| hb-late50 | 27 | Ablack | 76 | 142 | -99996 | B@b8 (main N@b8) | -Q (p 0.10) | lost |
| hb-late25 | 69 | Awhite | 66 | 100 | -99996 | d1e1 | -Q (p 0.41) | lost |

