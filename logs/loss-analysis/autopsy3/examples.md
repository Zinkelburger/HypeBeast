# AUTOPSY3: ten falls in detail

Selection: lost games, the team's first fall, score at K of 0 or better but not a forced mate for us (4 falls start from one), largest drop per class (A5 three, A1 two of which one without a forecast, one each of A4, A3, C2, C5, H). FENs are crazyhouse FENs with the hands in brackets (upper case: White's hand). Scores are the seat's main score in cp, from its side; M-n: mated in n plies.

## 1. plan-vs-l50-b game 72, Bwhite (A5: arrival; every candidate fell in its world)

- Scores at its last decisions into the fall: 1186 → 1796 → 2295 → M-4. Key step n=62 → n=66: 2295 → M-4. Team result: lost (checkmate).
- Clocks at K (aW, aB, bW, bB): 97.0, 96.8, 97.6, 96.2 s.
- Our board at K: `r1b2knr/ppp2p1p/3Pp3/4n2N/3n4/2bPP3/PP1K2PP/R1B3NR[QBNPbp] w - - 0 16`
- Other board at K: `r3kBr1/p1p2pPp/2p2n2/1q6/3Pp3/2P5/P1P1QPPP/R1B1K2R[Nqbppp] w KQq - 5 17`
- King: rank 1 from home, 4 king-zone squares attacked, in check: True; opponent's hand worth 4, ours 16. Partner's last score: 725.
- K played `b2c3` (kept_main), main depth 13, main line: `b2c3 d4f3 g2f3 B@e1 d2e1 P@f2 e1f1`
- K's last depths: d10 1869, d11 1964, d12 2184, d13 2295, d14 2462

| world at K | p | `b2c3` (played) | `d2d1` | `d2c3` |
|---|---|---|---|---|
| none | 0.17 | 2234 | M-2 | 591 |
| +Q-Q | 0.83 | M-6 | M-2 | M-6 |

- Our forecast's measured price of one arriving piece: {'+Q': 357, '-Q': 2000, '-P': 27}
- Reached the opponent's hand in the step: Q; ours: Q. The capture: `e2b5` on the other board, the reply to the partner's `e5b5` (partner's own line had that capture: no).
- The partner at that decision: 725 → 1042 at its next; its line `e5f5 N@h4 B@b5 h4f5`.
- Captures on our board in the step: we took ['B'], they took nothing.
- Opponent's reply on our board: `Q@c2` (K's line expected `d4f3`).
- At N: `r1b2knr/ppp2p1p/3Pp3/4n2N/3n4/2PPP3/P1qK2PP/R1B3NR[QQBNPbp] w - - 1 17`, score M-4, line `d2e1 e5d3 e1f1 c2f2`; first depth below -300: 3.

## 2. plan-vs-l50 game 41, Bblack (A5: arrival; every candidate fell in its world)

- Scores at its last decisions into the fall: 645 → 863 → 1277 → M-14. Key step n=64 → n=68: 1277 → M-14. Team result: lost (checkmate).
- Clocks at K (aW, aB, bW, bB): 96.2, 94.3, 96.1, 94.3 s.
- Our board at K: `r1bq1kQ~1/ppp3p1/2n5/4p1N1/3P2pP/2PQ4/P1P2PP1/q~1B1K2R[rnppp] b K - 0 17`
- Other board at K: `r1b1kb1N/ppp2pNp/2n2p2/1B6/4P1q1/2P1b1P1/P1PP2Pn/R1BQK3[RRBNPr] b q - 0 16`
- King: rank 0 from home, 3 king-zone squares attacked, in check: True; opponent's hand worth 0, ours 11. Partner's last score: 685.
- K played `f8g8` (kept_main), main depth 16, main line: `f8g8 d3h7 g8f8 e1g1 R@h6 c1a3 P@d6 f1a1 h6h7 g5h7`
- K's last depths: d13 960, d14 1039, d15 1155, d16 1277, d17 1325

| world at K | p | `f8g8` (played) | `f8e7` |
|---|---|---|---|
| none | 0.15 | 1444 | M-4 |
| +R-N | 0.36 | M-16 | M-4 |
| -N | 0.25 | M-16 | M-4 |
| +B-N | 0.24 | M-16 | M-4 |

- Our forecast's measured price of one arriving piece: {'+B': 532, '-N': 450}
- Reached the opponent's hand in the step: N; ours: B. The capture: `g4g7` on the other board, the reply to the partner's `h5g7` (partner's own line had that capture: yes).
- The partner at that decision: 685 → 932 at its next; its line `h5g7 g4g7 d2e3 c8g4`.
- Captures on our board in the step: we took ['P'], they took nothing.
- Opponent's reply on our board: `d3h7` (K's line expected `d3h7`).
- At N: `r1bq2k1/ppp3pQ/2n5/4p1N1/3P2pP/2P5/P1P2PP1/q~1B1K2R[Nrbnppp] b K - 1 18`, score M-14, line `g8f8 N@g6 f8e8 h7g8 R@f8 g8f8 e8d7 f8f5 d7d6 g5f7`; first depth below -300: 8.
- The same piece in its worlds at the two decisions before K: p 0.31, move played M-10, best candidate M-10.

## 3. matekeep game 66, Bwhite (A5: arrival; every candidate fell in its world)

- Scores at its last decisions into the fall: M+9 → M+7 → 1250 → M-4. Key step n=78 → n=82: 1250 → M-4. Team result: lost (checkmate).
- Clocks at K (aW, aB, bW, bB): 87.1, 88.9, 85.3, 90.7 s.
- Our board at K: `r1b3k1/pppp1p1p/2P3pP/2b1Q3/8/5p2/PP3nPP/RNBq1K1R[QBPP] w - - 6 21`
- Other board at K: `r2q1k1r/pppP1ppp/4P2n/1B2p1N1/1n2P2n/4b1PN/PPP3Pp/RN1b1K1R[Br] w - - 0 20`
- King: rank 0 from home, 5 king-zone squares attacked, in check: True; opponent's hand worth 0, ours 14. Partner's last score: 1368.
- K played `B@e1` (kept_main), main depth 17, main line: `B@e1 f3g2 f1g2 d1g4 Q@g3 g4e4 P@f3 c5d4 e5e4 f2e4`
- K's last depths: d14 746, d15 811, d16 1091, d17 1250, d18 1297

| world at K | p | `B@e1` (played) | `Q@e1` |
|---|---|---|---|
| none | 0.20 | 1404 | 812 |
| -P | 0.67 | M-6 | M-6 |
| +N-P | 0.13 | M-6 | M-6 |

- Our forecast's measured price of one arriving piece: {'+N': 253, '+P': 86, '-N': 605, '-P': 2000}
- Reached the opponent's hand in the step: P; ours: N. The capture: `g5h7` on the other board, the reply to the partner's `c6b4` (partner's own line had that capture: no).
- The partner at that decision: 1368 → 1657 at its next; its line `c6b4 b1c3 d8f6 B@f2`.
- Opponent's reply on our board: `P@e2` (K's line expected `f3g2`).
- At N: `r1b3k1/pppp1p1p/2P3pP/2b1Q3/8/5p2/PP2pnPP/RNBqBK1R[QNPP] w - - 8 22`, score M-4, line `e5e2 f3e2 f1g1 f2h3`; first depth below -300: 1.

## 4. kd60-vs-l50 game 56, Ablack (A1: arrival in no world)

- Scores at its last decisions into the fall: 52 → 459 → 1127 → M-6. Key step n=107 → n=111: 1127 → M-6. Team result: lost (checkmate).
- Clocks at K (aW, aB, bW, bB): 75.8, 70.5, 72.1, 74.2 s.
- Our board at K: `r1bkRb1r/1pp2Pp1/2np1nNp/3BPn1q/2p2P2/2P1B1QP/P3p1PP/6RK[Prbp] b - - 2 27`
- Other board at K: `r3q3/1bp2pk1/p1n1p1p1/2NpPRPp/B2Pp3/2NBP2Q/PP4P1/R5K1[N] w - - 1 28`
- King: rank 0 from home, 3 king-zone squares attacked, in check: True; opponent's hand worth 1, ours 9. Partner's last score: 1827.
- K played `f6e8` (kept_main), main depth 15, main line: `f6e8 g3f3 h5g6 P@h5 f5e3 h5g6 e3d5 f7e8r d8e8 f3d5`
- K's last depths: d12 1020, d13 1093, d14 1029, d15 1127, d16 1135

| world at K | p | `f6e8` (played) | `d8d7` |
|---|---|---|---|
| none | 0.48 | 1158 | M-2 |
| -B | 0.39 | 510 | M-2 |
| +N-B-B | 0.08 | 616 | M-2 |
| +P-B | 0.05 | 594 | M-2 |

- Our forecast's measured price of one arriving piece: {'+B': 116, '+N': 166, '+P': 45, '-R': 850, '-B': 316, '-N': 313}
- Reached the opponent's hand in the step: R; ours: P. The capture: `e8f7` on the other board, the reply to the partner's `f5f7` (partner's own line had that capture: yes).
- The partner at that decision: 2825 → 2880 at its next; its line `f5f7 e8f7 c5e6 g7h8`.
- Captures on our board in the step: we took ['R'], they took ['N'].
- Opponent's reply on our board: `f7e8q` (K's line expected `g3f3`).
- At N: `r1bkQ~b1r/1pp3p1/2np2Np/3BPn1q/2p2P2/2P1B1QP/P3p1PP/6RK[RPrbpp] b - - 0 28`, score M-6, line `d8e8 P@f7 e8d8 R@e8 d8d7 e5e6`; first depth below -300: 8.
- The same piece in its worlds at the two decisions before K: p 0.15, move played -31, best candidate -31; p 0.30, move played M-10, best candidate M-10.

## 5. matefree game 72, Bwhite (A1: arrival in no world)

- Scores at its last decisions into the fall: 806 → 831 → 377 → M-6. Key step n=72 → n=76: 377 → M-6. Team result: lost (checkmate).
- Clocks at K (aW, aB, bW, bB): 91.5, 92.2, 92.0, 91.8 s.
- Our board at K: `r4rk1/ppp1bppp/4p1n1/4R3/3P1n1q/1PP2BKP/1BP2P2/R2Q4[QRNPPp] w - - 1 19`
- Other board at K: `r1bB3r/ppp2k1p/2n1p2p/b6N/3PqN2/N1P2b2/PP3PPP/R1B3K1[Pnpp] w - - 0 19`
- King: rank 2 from home, 6 king-zone squares attacked, in check: True; opponent's hand worth 1, ours 19. Partner's last score: 1062.
- K played `g3h2` (only_move), main depth 15, main line: `g3h2 h4f2 N@g2 P@g3 h2h1 f7f6 Q@f1 f2f1 d1f1 f6e5`
- K's last depths: d12 143, d13 219, d14 272, d15 377, d16 385
- No coordinator worlds at K (reason only_move, 1 legal moves).
- Reached the opponent's hand in the step: B. The capture: `g2f3` on the other board, the reply to the partner's `e2f3` (partner's own line had that capture: yes).
- The partner at that decision: 1062 → 852 at its next; its line `e2f3 g2f3 h8g8 P@g3`.
- Captures on our board in the step: we took nothing, they took ['P'].
- Opponent's reply on our board: `h4h3` (K's line expected `h4f2`).
- At N: `r4rk1/ppp1bppp/4p1n1/4R3/3P1n2/1PP2B1q/1BP2P1K/R2Q4[QRNPPbp] w - - 0 20`, score M-6, line `h2g1 B@h2 g1h1 P@g2 f3g2 h3g2`; first depth below -300: 1.
- The same piece in its worlds at the two decisions before K: p 0.12, move played -134, best candidate -134.

## 6. matefree game 46, Ablack (A4: arrival; another candidate held in its world)

- Scores at its last decisions into the fall: 539 → 673 → 922 → -1469. Key step n=94 → n=98: 922 → -1469. Team result: lost (checkmate).
- Clocks at K (aW, aB, bW, bB): 80.9, 80.1, 80.9, 80.0 s.
- Our board at K: `r2q4/ppp3kp/2n1B2n/5p2/1P1pPBrb/5N1P/P1P2PP1/R2Q1RK1[QPqbnppp] b - - 2 23`
- Other board at K: `r1b2rk1/p1p1B1pp/2p5/4P3/3p4/P3bN1P/1P4K1/RN3B1R[NPPPPnp] b - - 2 25`
- King: rank 1 from home, 3 king-zone squares attacked, in check: False; opponent's hand worth 10, ours 18. Partner's last score: 162.
- K played `g4f4` (kept_main), main depth 13, main line: `g4f4 d1e1 P@e3 g1h1 Q@e7 P@g3 f4e4 g3h4 e4e6`
- K's last depths: d10 787, d11 727, d12 796, d13 922, d14 935

| world at K | p | `g4f4` (played) | `d4d3` | `g4g2` |
|---|---|---|---|---|
| none | 0.49 | 846 | -161 | 311 |
| +N | 0.24 | 879 | -10 | 364 |
| +R-N | 0.16 | -1191 | M-12 | 327 |
| -N | 0.11 | -1629 | M-12 | -257 |

- Our forecast's measured price of one arriving piece: {'+R': 235, '+B': 48, '+N': 37, '-N': 947, '-P': 220}
- Reached the opponent's hand in the step: N. The capture: `f8f3` on the other board, the reply to the partner's `f2g2` (partner's own line had that capture: no).
- The partner at that decision: 162 → 412 at its next; its line `f2g3 c8d7 e7f8 a8f8`.
- Captures on our board in the step: we took ['B'], they took nothing.
- Opponent's reply on our board: `N@h5` (K's line expected `d1e1`).
- At N: `r2q4/ppp3kp/2n1B2n/5p1N/1P1pPr1b/5N1P/P1P2PP1/R2Q1RK1[QPqbnppp] b - - 1 24`, score -1469, line `g7g6 f3h4 g6g5 Q@g7 P@g6 h5f4 B@h2 g1h1 h2f4 h4f3`; first depth below -300: 1.
- The same piece in its worlds at the two decisions before K: p 0.32, move played -139, best candidate -105; p 0.16, move played -246, best candidate -70.

## 7. plan-c game 72, Ablack (A3: arrival; its world had the move holding)

- Scores at its last decisions into the fall: 1028 → 1626 → 1146 → M-4. Key step n=84 → n=88: 1146 → M-4. Team result: lost (checkmate).
- Clocks at K (aW, aB, bW, bB): 85.5, 85.7, 86.5, 84.7 s.
- Our board at K: `r2nk1r1/pppb1pq1/4pPp1/b6B/3PN2p/2P4P/PP1N1P2/R4QK1[BPqbnn] b q - 1 21`
- Other board at K: `3r1bkr/ppp2ppp/2n1pN1B/8/2p5/5N2/P1P2PPP/R2QK2R[RBPPPp] b KQ - 1 22`
- King: rank 0 from home, 1 king-zone squares attacked, in check: False; opponent's hand worth 4, ours 18. Partner's last score: M+9.
- K played `g7h7` (kept_main), main depth 15, main line: `g7h7 h5g4 B@f4 d2f3 Q@f5 a1e1 d7c6 d4d5 c6d5 f1d3`
- K's last depths: d12 1070, d13 1146, d14 1132, d15 1146, d16 1146

| world at K | p | `g7h7` (played) | `B@f4` | `g6h5` | `g7h8` |
|---|---|---|---|---|---|
| none | 0.15 | 1155 | 1154 | 896 | 963 |
| +B-N | 0.50 | 880 | 844 | 512 | 452 |
| -N | 0.35 | 683 | 482 | 259 | 569 |

- Our forecast's measured price of one arriving piece: {'-N': 960}
- Reached the opponent's hand in the step: N; ours: R. The capture: `g7f6` on the other board, the reply to the partner's `N@f6` (partner's own line had that capture: yes).
- The partner at that decision: M+9 → M+7 at its next; its line `N@f6 g7f6 d1d8 c6d8`.
- Opponent's reply on our board: `N@d6` (K's line expected `h5g4`).
- At N: `r2nk1r1/pppb1p1q/3NpPp1/b6B/3PN2p/2P4P/PP1N1P2/R4QK1[BPqrbnn] b q - 3 22`, score M-4, line `c7d6 e4d6 e8f8 P@e7`; first depth below -300: 3.

## 8. plan-c game 189, Bblack (C2: own board; the reply its line expected)

- Scores at its last decisions into the fall: -595 → -600 → 77 → -483. Key step n=100 → n=104: 77 → -483. Team result: lost (checkmate).
- Clocks at K (aW, aB, bW, bB): 77.3, 78.1, 76.7, 78.7 s.
- Our board at K: `rk5r/ppR1b1pp/2ppBP2/4P3/3p4/6N1/PPP1BKnP/R1B5[NNNPqbn] b - - 0 25`
- Other board at K: `r4rk1/ppP2p1p/3n3n/3p3B/5P2/8/PPP2PP1/R2Q1RK1[QPPqbbpppp] b - - 0 26`
- King: rank 0 from home, 2 king-zone squares attacked, in check: False; opponent's hand worth 10, ours 15. Partner's last score: 313.
- K played `B@e1` (kept_main), main depth 10, main line: `B@e1 f2g1 Q@f2 g1h1 g2h4 N@d7 b8c7`
- K's last depths: d6 409, d7 -41, d8 409, d9 -274, d10 77

| world at K | p | `B@e1` (played) | `Q@e1` | `b8c7` | `B@e3` |
|---|---|---|---|---|---|
| none | 0.56 | -304 | 40 | -956 | -463 |
| +P | 0.44 | 120 | 31 | -589 | -136 |

- Our forecast's measured price of one arriving piece: {'+P': 75}
- Reached the opponent's hand in the step: nothing.
- Opponent's reply on our board: `f2g1` (K's line expected `f2g1`).
- At N: `rk5r/ppR1b1pp/2ppBP2/4P3/3p4/6N1/PPP1B1nP/R1B1b1K1[NNNPqn] b - - 2 26`, score -483, line `Q@f2 g1h1 g2h4 N@d7 b8c7 N@b5 c6b5 N@d5 c7c6 d5e7`; first depth below -300: 8.

## 9. kd60-vs-l50 game 36, Bwhite (C5: own board after a switch)

- Scores at its last decisions into the fall: -46 → -506 → 59 → -1595. Key step n=82 → n=86: 59 → -1595. Team result: lost (checkmate).
- Clocks at K (aW, aB, bW, bB): 87.4, 85.8, 85.0, 88.2 s.
- Our board at K: `r5k1/pbp1B1bp/1p2p2p/3pN2B/3P1P2/2PPP2q/P5rP/R2Q1R1K[BPbbp] w - - 1 22`
- Other board at K: `r5nr/pp1Bkppp/4p3/1N2n3/3pPnNP/8/PPP2P2/R2Q1K1R[NPPqnp] w - - 2 21`
- King: rank 0 from home, 3 king-zone squares attacked, in check: False; opponent's hand worth 7, ours 4. Partner's last score: 308.
- K played `P@f7` (exposure_veto; main B@g1), main depth 12, main line: `B@g1 g2h2 g1h2 P@g2 h1g1 g2f1q d1f1 h3h5`
- K's last depths: d8 87, d9 61, d10 -2, d11 -149, d12 59

| world at K | p | `B@g1` | `B@g3` | `P@f7` (played) |
|---|---|---|---|---|
| none | 0.68 | M-12 | -197 | -431 |
| -P | 0.22 | -36 | -554 | -135 |
| +B | 0.05 | 277 | -662 | 149 |
| +N | 0.05 | 482 | 427 | 443 |

- Our forecast's measured price of one arriving piece: {'+B': 327, '+N': 410, '-N': 463, '-P': 126}
- Reached the opponent's hand in the step: nothing.
- Opponent's reply on our board: `g8h8` (K's line expected `g2h2`).
- At N: `r6k/pbp1BPbp/1p2p2p/3pN2B/3P1P2/2PPP2q/P5rP/R2Q1R1K[Bbbp] w - - 3 23`, score -1595, line `e5g4 g2g3 f1f2 B@g2 h1g1 g2f3 B@g2 g3g2 g1f1 P@e2`; first depth below -300: 1.

## 10. matekeep game 38, Ablack (H: a sit)

- Scores at its last decisions into the fall: -62 → 221 → 1072 → M-4. Key step n=98 → n=99: 1072 → M-4. Team result: lost (flag).
- Clocks at K (aW, aB, bW, bB): 79.2, 76.6, 75.9, 79.9 s.
- Our board at K: `r1b2k1Q/p1p3p1/6Bp/3pN2p/3P4/2N2r1n/PPP2PNP/R1B2R1K[qqbnnnpp] b - - 7 26`
- Other board at K: `r2k1b2/ppp2Ppr/4ppQ1/1b1RP1B1/8/8/PPP2PPP/5RK1[BNPPpp] b - - 0 24`
- King: rank 0 from home, 5 king-zone squares attacked, in check: True; opponent's hand worth 0, ours 32. Partner's last score: 2012.
- K played `pass` (stall_deny), main depth 15, main line: `B@g8 e5f3 N@g4 c1e3 Q@f6 e3h6 g4f2 f1f2 h3f2 h1g1`
- K's last depths: d12 766, d13 957, d14 962, d15 1072, d16 1088

| world at K | p | `B@g8` | `Q@g8` | `f8e7` |
|---|---|---|---|---|
| none | 0.20 | 1150 | 580 | M-4 |
| +P+P-R-P | 0.47 | M-2 | M-2 | M-4 |
| +P-R | 0.33 | M-2 | M-2 | M-4 |

- Our forecast's measured price of one arriving piece: {'+B': 215, '+P': 186, '-R': 2000}
- Reached the opponent's hand in the step: R. The capture: `e6d5` on the other board, the reply to the partner's `d1d5` (partner's own line had that capture: yes).
- Opponent's reply on our board: `None` (K's line expected `e5f3`).
- At N: `r1b2k1Q/p1p3p1/6Bp/3pN2p/3P4/2N2r1n/PPP2PNP/R1B2R1K[Rqqbnnnpp] b - - 7 26`, score M-4, line `f8e7 h8e8 e7d6 c3b5`; first depth below -300: 1.

