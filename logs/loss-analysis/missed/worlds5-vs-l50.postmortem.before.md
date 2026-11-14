# Post-mortem: worlds5-vs-l50

100 games, 11527 decisions. Score: hb-l50 47, hb-worlds5 53.

## Did the stated winning chances come true?

From the main search's score (logistic, 1000 cp per unit; a mate is 0% or 100%). Decisions of one game are not independent, so read the columns as a shape, not to the digit.

| stated | hb-l50: n | hb-l50: mean stated | hb-l50: won | hb-worlds5: n | hb-worlds5: mean stated | hb-worlds5: won |
|---|---|---|---|---|---|---|
| 0-10% | 424 | 0.6% | 6.8% | 440 | 0.9% | 10.5% |
| 10-25% | 191 | 18.5% | 21.5% | 229 | 18.3% | 23.1% |
| 25-40% | 615 | 33.8% | 28.6% | 758 | 33.9% | 38.0% |
| 40-60% | 2952 | 50.2% | 41.8% | 2937 | 50.1% | 58.1% |
| 60-75% | 823 | 66.0% | 59.9% | 736 | 66.2% | 67.7% |
| 75-90% | 269 | 81.4% | 77.3% | 234 | 81.5% | 79.1% |
| 90-100% | 356 | 98.3% | 88.5% | 323 | 99.1% | 95.0% |

## Did the forecast worlds come true?

An arrival world counts as true when its whole package had reached the hands before ply q of our board (q=1: the opponent's reply, q=2: our next move). Only decisions with 6 or more plies of our board left.

**hb-l50** (Brier score against "arrived by q<=4": 0.203 over 12639 worlds)

| stated p | worlds | mean p | by q<=1 | by q<=2 | by q<=4 | by q<=6 |
|---|---|---|---|---|---|---|
| 0.00-0.10 | 2594 | 0.07 | 1.8% | 6.1% | 15.0% | 23.3% |
| 0.10-0.20 | 5417 | 0.14 | 4.2% | 12.5% | 25.1% | 34.4% |
| 0.20-0.35 | 3026 | 0.26 | 10.7% | 23.4% | 39.3% | 48.7% |
| 0.35-0.60 | 1343 | 0.43 | 15.5% | 34.1% | 51.5% | 59.0% |
| 0.60-1.00 | 259 | 0.73 | 51.7% | 72.6% | 79.5% | 83.0% |

| stated "nothing arrives" | decisions | nothing by q<=1 | by q<=2 | by q<=4 |
|---|---|---|---|---|
| 0.0-0.3 | 930 | 33.8% | 15.3% | 5.3% |
| 0.3-0.5 | 1771 | 54.9% | 31.1% | 11.0% |
| 0.5-0.7 | 1597 | 75.1% | 54.2% | 23.2% |
| 0.7-0.9 | 435 | 91.5% | 79.5% | 50.1% |
| 0.9-1.0 | 233 | 92.7% | 84.1% | 63.9% |

**hb-worlds5** (Brier score against "arrived by q<=4": 0.194 over 15143 worlds)

| stated p | worlds | mean p | by q<=1 | by q<=2 | by q<=4 | by q<=6 |
|---|---|---|---|---|---|---|
| 0.00-0.10 | 4588 | 0.07 | 1.5% | 6.1% | 15.4% | 23.5% |
| 0.10-0.20 | 5898 | 0.14 | 4.1% | 12.4% | 24.8% | 34.1% |
| 0.20-0.35 | 3076 | 0.26 | 11.7% | 24.6% | 39.3% | 49.6% |
| 0.35-0.60 | 1277 | 0.44 | 16.4% | 32.0% | 51.2% | 59.9% |
| 0.60-1.00 | 304 | 0.73 | 46.7% | 71.7% | 78.3% | 83.2% |

| stated "nothing arrives" | decisions | nothing by q<=1 | by q<=2 | by q<=4 |
|---|---|---|---|---|
| 0.0-0.3 | 1358 | 36.4% | 15.8% | 5.6% |
| 0.3-0.5 | 1984 | 59.5% | 36.3% | 12.9% |
| 0.5-0.7 | 978 | 83.1% | 63.4% | 29.6% |
| 0.7-0.9 | 421 | 94.3% | 82.4% | 52.3% |
| 0.9-1.0 | 221 | 93.2% | 84.2% | 67.0% |

## When did a forecast piece arrive?

A piece (side and type) by the earliest ply k at which any forecast line names it, all engines, decisions with 6 or more plies left: share in that hand before ply q of our board.

| named at ply k | pieces | q<=1 | q<=2 | q<=3 | q<=4 | q<=5 | q<=6 |
|---|---|---|---|---|---|---|---|
| 0 | 15393 | 23.2% | 26.5% | 36.4% | 39.7% | 46.6% | 49.9% |
| 1 | 17722 | 1.6% | 17.0% | 20.4% | 29.2% | 32.6% | 38.5% |
| 2 | 5417 | 0.1% | 2.0% | 15.3% | 19.4% | 26.8% | 30.4% |
| 3 | 6770 | 0.5% | 4.5% | 6.7% | 15.0% | 18.8% | 25.2% |

## Arrivals nobody forecast

What reached the OPPONENT's hand before our next move (q<=2), and the main score at the seat's next decision minus the score now (mates left out).

| engine | to the opponent by q<=2 | decisions | share | mean change in score (cp) | then saw itself mated |
|---|---|---|---|---|---|
| hb-l50 | nothing arrived | 3385 | 61.5% | +131 | 21 |
| hb-l50 | all of it was in a world | 1819 | 33.0% | -188 | 48 |
| hb-l50 | a piece in no world | 303 | 5.5% | -212 | 6 |
| hb-worlds5 | nothing arrived | 3335 | 60.6% | +116 | 25 |
| hb-worlds5 | all of it was in a world | 1954 | 35.5% | -189 | 37 |
| hb-worlds5 | a piece in no world | 218 | 4.0% | -237 | 12 |

## Switching away from the main search's move

| engine | decision | n | share | mean change in score by the next decision (cp) | games won |
|---|---|---|---|---|---|
| hb-l50 | kept | 4729 | 82.4% | +23 | 43.5% |
| hb-l50 | switched | 1012 | 17.6% | -39 | 44.2% |
| hb-worlds5 | kept | 4592 | 79.4% | +11 | 52.4% |
| hb-worlds5 | switched | 1194 | 20.6% | -45 | 57.5% |

| engine | reason for the switch | n |
|---|---|---|
| hb-worlds5 | world_switch | 1132 |
| hb-l50 | world_switch | 959 |
| hb-worlds5 | exposure_veto | 34 |
| hb-l50 | exposure_veto | 30 |
| hb-worlds5 | delivery_win | 17 |
| hb-l50 | soft_switch | 16 |
| hb-worlds5 | soft_switch | 11 |
| hb-l50 | delivery_win | 7 |

## First to see itself mated

| engine | games in which it was first | of those lost |
|---|---|---|
| hb-l50 | 48 | 48 |
| hb-worlds5 | 52 | 47 |

## Sudden collapses

Decisions at -300 cp or better whose next decision was a forced mate against the seat. "Fatal piece": what reached the opponent's hand before our next move. For the partner: its last decision before that capture, and whether the capture was the reply its own main line expected.

| engine | collapses | what the seat knew | n |
|---|---|---|---|
| hb-l50 | 25 | in a world, where every candidate was mated | 15 |
| hb-l50 | 25 | in a world, but the move was not scored there | 4 |
| hb-l50 | 25 | in a world, where the move played was not mated | 4 |
| hb-l50 | 25 | the piece was in no world | 2 |
| hb-l50 | 25 | fatal pieces: -Q 15, -R 6, -N 5, -B 1, -P 1 |  |
| hb-worlds5 | 15 | the piece was in no world | 5 |
| hb-worlds5 | 15 | in a world, where every candidate was mated | 5 |
| hb-worlds5 | 15 | nothing reached the opponent | 2 |
| hb-worlds5 | 15 | in a world, where another candidate was not mated | 1 |
| hb-worlds5 | 15 | in a world, where the move played was not mated | 1 |
| hb-worlds5 | 15 | in a world, but the move was not scored there | 1 |
| hb-worlds5 | 15 | fatal pieces: -Q 6, -P 4, -B 2, -R 2, -N 1 |  |

| engine | the partner's last decision before the capture | n | partner ahead (>300) | level | behind (<-300) | our team took a piece there too |
|---|---|---|---|---|---|---|
| hb-l50 | the partner's own line had that capture | 15 | 11 | 3 | 1 | 13 |
| hb-l50 | the partner's line expected another reply | 10 | 5 | 3 | 2 | 10 |
| hb-worlds5 | the partner's own line had that capture | 9 | 6 | 2 | 1 | 8 |
| hb-worlds5 | the partner's line expected another reply | 4 | 1 | 1 | 2 | 4 |

## The 15 decisions followed by the largest drop

Score now and at the seat's next decision (mate = -100000). "to them" is what reached the opponent's hand before our next move, with the largest stated probability of a world holding it (0: in none).

| engine | game | seat | moves played | score | next | played | to them | game |
|---|---|---|---|---|---|---|---|---|
| hb-l50 | 21 | Bblack | 157 | 99985 | -99996 | h6g5 | -Q (p 0.22) | lost |
| hb-l50 | 38 | Bwhite | 134 | 3907 | -99996 | g4f5 | -Q (p 0.85) | lost |
| hb-worlds5 | 54 | Awhite | 76 | 2838 | -99998 | f1e2 (main d1e2) | -Q (p 0.83) | lost |
| hb-l50 | 40 | Bwhite | 66 | 2062 | -99992 | N@g3 (main e4f4) | -Q (p 0.31) | lost |
| hb-l50 | 30 | Bwhite | 76 | 1460 | -99998 | g5e7 (main N@e5) | -Q (p 0.41) | lost |
| hb-l50 | 64 | Ablack | 78 | 1368 | -99996 | b7c8 | -Q (p 0.42) | lost |
| hb-l50 | 43 | Awhite | 96 | 1142 | -99998 | b1a1 | -R (p 0.79), -R (p 0.79) | lost |
| hb-l50 | 51 | Bblack | 64 | 806 | -99992 | g7f6 (main g7h7) | -Q (p 0.47), -N (p 0.47) | lost |
| hb-worlds5 | 34 | Bblack | 79 | 724 | -99998 | e6d7 | -P (p 0.09) | lost |
| hb-l50 | 52 | Ablack | 74 | 588 | -99994 | g8h8 | -Q (p 0.37) | lost |
| hb-l50 | 18 | Ablack | 146 | 490 | -99998 | h5h4 | -Q (p 0.50) | lost |
| hb-worlds5 | 61 | Bwhite | 146 | 465 | -99998 | g1h1 | -B (p 0.28), -P (p 0.28) | lost |
| hb-l50 | 83 | Bblack | 53 | 458 | -99996 | g8g7 | -B (p 0.20) | lost |
| hb-l50 | 85 | Awhite | 92 | 378 | -99994 | h2g3 | -Q (p 0.47) | lost |
| hb-worlds5 | 42 | Bblack | 103 | 368 | -99996 | c6b5 | -P (p 0.00) | lost |

