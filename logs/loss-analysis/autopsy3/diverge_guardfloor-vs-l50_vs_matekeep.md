# Where guardfloor-vs-l50 (hb-guardfloor) and matekeep (hb-matekeep) part

Games matched by opening pair and colour: 100 (only in guardfloor-vs-l50: 0, only in matekeep: 0, opening mismatch: 0).
Identical games: 0. Score of hb-guardfloor 63, of hb-matekeep 51 (out of 100).

Results that differ: 44; hb-guardfloor better in 28, hb-matekeep better in 16.

| cause at the parting decision | games | results differ | hb-guardfloor better | hb-matekeep better | ply parted (median) |
|---|---|---|---|---|---|
| mate price earlier | 2 | 0 | 0 | 0 | 35 |
| no mate price: probe here | 9 | 4 | 3 | 1 | 22 |
| no mate price: both probed | 89 | 40 | 25 | 15 | 21 |

hb-guardfloor's guard at the parting decision: probed 91, low (below the floor) 9.
hb-matekeep's guard at the parting decision: no guard; price probes ran 100.
First difference in logged guard or mate prices (same position): none 61, B probed, A did not 36, mate prices differ 3.
Plies from that first difference to the parting move: median 1 (0 in 19 of 39).
rescue= or partner_held= at the parting decision: 0.

Per game (pair, contender colour): parting ply, seat, cause; each side's decision (reason; guard; mate prices); result A-B.

| pair | colour | ply | seat | cause | hb-guardfloor | hb-matekeep | result |
|---|---|---|---|---|---|---|---|
| 0 | black | 58 | Bwhite | no mate price: both probed | `b2b1` (kept_main; guard QRP; no mate price; score 24) | `b2b3` (kept_main; guard None; no mate price; score 13) | 1-0 |
| 0 | white | 21 | Bblack | no mate price: both probed | `b8c6` (kept_main; guard QP; no mate price; score -281) | `f8e7` (kept_main; guard None; no mate price; score -281) | 1-1 |
| 1 | black | 16 | Ablack | no mate price: both probed | `g8f6` (kept_main; guard QP; no mate price; score -84) | `d7d6` (kept_main; guard None; no mate price; score -81) | 1-1 |
| 1 | white | 23 | Awhite | no mate price: both probed | `c3d5` (kept_main; guard QNP; no mate price; score 123) | `e1g1` (world_switch; guard None; no mate price; score 92) | 1-1 |
| 2 | black | 20 | Bwhite | no mate price: probe here | `g5h4` (kept_main; guard low; no mate price; score -150) | `g5d2` (kept_main; guard None; no mate price; score -159) | 0-0 |
| 2 | white | 21 | Awhite | no mate price: both probed | `c1d2` (kept_main; guard QNP; no mate price; score 473) | `f3e5` (kept_main; guard None; no mate price; score 405) | 1-1 |
| 3 | black | 22 | Ablack | no mate price: both probed | `P@b4` (kept_main; guard Q; no mate price; score 187) | `B@h5` (world_switch; guard None; no mate price; score 219) | 1-1 |
| 3 | white | 18 | Bblack | no mate price: both probed | `d7d5` (no_arrivals; guard QP; no mate price; score -198) | `e8g8` (no_arrivals; guard None; no mate price; score -198) | 0-0 |
| 4 | black | 19 | Ablack | no mate price: both probed | `c6d4` (kept_main; guard QP; no mate price; score -57) | `c8g4` (kept_main; guard None; no mate price; score -34) | 1-0 |
| 4 | white | 20 | Awhite | no mate price: both probed | `f3d4` (kept_main; guard QNP; no mate price; score 90) | `c1g5` (kept_main; guard None; no mate price; score 59) | 0-1 |
| 5 | black | 19 | Ablack | no mate price: both probed | `e7e6` (kept_main; guard QP; no mate price; score -500) | `b8c6` (world_switch; guard None; no mate price; score -500) | 0-1 |
| 5 | white | 25 | Awhite | no mate price: both probed | `e4d5` (kept_main; guard QP; no mate price; score 135) | `f1b5` (kept_main; guard None; no mate price; score 131) | 0-0 |
| 6 | black | 31 | Ablack | mate price earlier | `d8d7` (kept_main; guard QNP; no mate price; score 218) | `c6b4` (kept_main; guard None; no mate price; score 155) | 1-1 |
| 6 | white | 17 | Awhite | no mate price: both probed | `b2b4` (kept_main; guard QP; no mate price; score -347) | `d2d3` (world_switch; guard None; no mate price; score -347) | 1-0 |
| 7 | black | 18 | Ablack | no mate price: both probed | `c6d4` (kept_main; guard QN; no mate price; score 383) | `f8c5` (kept_main; guard None; no mate price; score 456) | 0-0 |
| 7 | white | 22 | Bblack | no mate price: probe here | `f8c5` (kept_main; guard low; no mate price; score 20) | `f8b4` (kept_main; guard None; no mate price; score 64) | 0-0 |
| 8 | black | 25 | Bwhite | no mate price: both probed | `e1g1` (kept_main; guard QNP; no mate price; score 235) | `B@h4` (world_switch; guard None; no mate price; score 177) | 1-1 |
| 8 | white | 31 | Bblack | no mate price: both probed | `f8e7` (kept_main; guard QP; no mate price; score -187) | `h7h6` (kept_main; guard None; no mate price; score -163) | 0-0 |
| 9 | black | 24 | Bwhite | no mate price: both probed | `e4c4` (no_arrivals; guard QN; no mate price; score -106) | `e4d3` (no_arrivals; guard None; no mate price; score -55) | 0-0 |
| 9 | white | 18 | Bblack | no mate price: both probed | `f8e7` (world_switch; guard QNP; no mate price; score 67) | `g8e7` (kept_main; guard None; no mate price; score 67) | 1-0 |
| 10 | black | 23 | Bwhite | no mate price: both probed | `c3e4` (kept_main; guard QNP; no mate price; score -11) | `f3g5` (kept_main; guard None; no mate price; score -14) | 1-0 |
| 10 | white | 21 | Bblack | no mate price: both probed | `d5e4` (world_switch; guard QP; no mate price; score 40) | `g8f6` (kept_main; guard None; no mate price; score 3) | 0-0 |
| 11 | black | 17 | Ablack | no mate price: both probed | `h7h5` (kept_main; guard QP; no mate price; score 187) | `c8d7` (kept_main; guard None; no mate price; score 237) | 1-1 |
| 11 | white | 27 | Awhite | no mate price: both probed | `e1f1` (kept_main; guard QP; no mate price; score -192) | `P@f3` (world_switch; guard None; no mate price; score -177) | 1-0 |
| 12 | black | 22 | Ablack | no mate price: both probed | `B@d5` (kept_main; guard QN; no mate price; score 316) | `d7c6` (kept_main; guard None; no mate price; score 294) | 0-0 |
| 12 | white | 17 | Awhite | no mate price: both probed | `e4f6` (world_switch; guard QNP; no mate price; score -116) | `c1g5` (kept_main; guard None; no mate price; score -116) | 1-0 |
| 13 | black | 22 | Bwhite | no mate price: both probed | `d4e5` (kept_main; guard QP; no mate price; score 77) | `B@g3` (kept_main; guard None; no mate price; score 84) | 1-1 |
| 13 | white | 16 | Bblack | no mate price: both probed | `e7e5` (world_switch; guard Q; no mate price; score -101) | `b8c6` (kept_main; guard None; no mate price; score -101) | 0-1 |
| 14 | black | 21 | Bwhite | no mate price: both probed | `f1e2` (kept_main; guard QP; no mate price; score 108) | `f1b5` (kept_main; guard None; no mate price; score 124) | 0-0 |
| 14 | white | 16 | Awhite | no mate price: both probed | `e4e5` (no_arrivals; guard QP; no mate price; score 236) | `f1d3` (no_arrivals; guard None; no mate price; score 232) | 1-1 |
| 15 | black | 17 | Ablack | no mate price: both probed | `d7d6` (kept_main; guard Q; no mate price; score 82) | `d7d5` (kept_main; guard None; no mate price; score 82) | 0-0 |
| 15 | white | 21 | Bblack | no mate price: both probed | `e8g8` (kept_main; guard QNP; no mate price; score -72) | `b4d2` (kept_main; guard None; no mate price; score -80) | 1-1 |
| 16 | black | 20 | Ablack | no mate price: both probed | `e8g8` (kept_main; guard QP; no mate price; score 1) | `b8c6` (world_switch; guard None; no mate price; score 0) | 0-0 |
| 16 | white | 18 | Awhite | no mate price: both probed | `f1b5` (world_switch; guard Q; no mate price; score 392) | `f1e2` (kept_main; guard None; no mate price; score 392) | 1-1 |
| 17 | black | 16 | Ablack | no mate price: both probed | `d7d5` (kept_main; guard QP; no mate price; score -65) | `b8c6` (kept_main; guard None; no mate price; score -65) | 0-1 |
| 17 | white | 17 | Bblack | no mate price: both probed | `a5b6` (world_switch; guard Q; no mate price; score 19) | `a5e5` (world_switch; guard None; no mate price; score 19) | 0-1 |
| 18 | black | 19 | Bwhite | no mate price: both probed | `e4e5` (kept_main; guard QP; no mate price; score 154) | `f1d3` (kept_main; guard None; no mate price; score 160) | 1-1 |
| 18 | white | 26 | Awhite | no mate price: both probed | `e5f6` (world_switch; guard QP; no mate price; score 59) | `f1e2` (kept_main; guard None; no mate price; score 6) | 1-0 |
| 19 | black | 32 | Bwhite | no mate price: both probed | `c2c3` (kept_main; guard QNP; no mate price; score 200) | `e4f6` (kept_main; guard None; no mate price; score 225) | 1-0 |
| 19 | white | 21 | Awhite | no mate price: both probed | `b5c6` (kept_main; guard QP; no mate price; score 30) | `e1g1` (kept_main; guard None; no mate price; score 20) | 1-1 |
| 20 | black | 20 | Bwhite | no mate price: both probed | `f1d3` (kept_main; guard QP; no mate price; score 221) | `f1c4` (kept_main; guard None; no mate price; score 227) | 1-0 |
| 20 | white | 17 | Awhite | no mate price: both probed | `e4e5` (kept_main; guard QP; no mate price; score 107) | `g1f3` (kept_main; guard None; no mate price; score 172) | 0-0 |
| 21 | black | 16 | Ablack | no mate price: both probed | `d7d6` (kept_main; guard QP; no mate price; score 70) | `e8g8` (kept_main; guard None; no mate price; score 70) | 0-0 |
| 21 | white | 38 | Bblack | no mate price: both probed | `f8b4` (kept_main; guard QP; no mate price; score 100) | `b6a5` (world_switch; guard None; no mate price; score 63) | 1-1 |
| 22 | black | 18 | Bwhite | no mate price: both probed | `g1f3` (kept_main; guard QP; no mate price; score 40) | `e4e5` (kept_main; guard None; no mate price; score 94) | 1-0 |
| 22 | white | 19 | Awhite | no mate price: both probed | `f1b5` (world_switch; guard QP; no mate price; score 54) | `c1e3` (kept_main; guard None; no mate price; score 54) | 1-1 |
| 23 | black | 23 | Bwhite | no mate price: probe here | `b1c3` (kept_main; guard low; no mate price; score -201) | `c1d2` (kept_main; guard None; no mate price; score -205) | 1-0 |
| 23 | white | 21 | Bblack | no mate price: both probed | `h7h5` (world_switch; guard QP; no mate price; score 43) | `f8c5` (world_switch; guard None; no mate price; score 16) | 1-1 |
| 24 | black | 21 | Ablack | no mate price: both probed | `a7a6` (kept_main; guard QNP; no mate price; score 118) | `e7g6` (kept_main; guard None; no mate price; score 121) | 0-1 |
| 24 | white | 36 | Bblack | no mate price: both probed | `g7h6` (kept_main; guard QP; no mate price; score -217) | `Q@e6` (kept_main; guard None; no mate price; score -187) | 0-1 |
| 25 | black | 23 | Ablack | no mate price: probe here | `h7h5` (kept_main; guard low; no mate price; score -765) | `b8c6` (kept_main; guard None; no mate price; score -782) | 0-0 |
| 25 | white | 21 | Awhite | no mate price: both probed | `g1f3` (kept_main; guard QP; no mate price; score 812) | `f1d3` (kept_main; guard None; no mate price; score 814) | 1-1 |
| 26 | black | 27 | Ablack | no mate price: both probed | `e4c3` (kept_main; guard QNP; no mate price; score -99) | `b8c6` (kept_main; guard None; no mate price; score -66) | 1-0 |
| 26 | white | 17 | Awhite | no mate price: both probed | `b1c3` (kept_main; guard QP; no mate price; score -328) | `d2d4` (world_switch; guard None; no mate price; score -328) | 0-1 |
| 27 | black | 22 | Bwhite | no mate price: both probed | `b1c3` (kept_main; guard QN; no mate price; score -118) | `b1d2` (kept_main; guard None; no mate price; score -98) | 1-0 |
| 27 | white | 23 | Awhite | no mate price: both probed | `e5f3` (kept_main; guard QNP; no mate price; score 89) | `e5f7` (kept_main; guard None; no mate price; score 127) | 1-0 |
| 28 | black | 44 | Bwhite | no mate price: probe here | `N@h5` (kept_main; guard low; no mate price; score 516) | `P@h6` (kept_main; guard None; no mate price; score 559) | 1-0 |
| 28 | white | 16 | Awhite | no mate price: both probed | `d4f5` (world_switch; guard QNP; no mate price; score 103) | `d4c6` (kept_main; guard None; no mate price; score 103) | 1-0 |
| 29 | black | 16 | Bwhite | no mate price: probe here | `e1g1` (kept_main; guard low; no mate price; score 157) | `d2d4` (kept_main; guard None; no mate price; score 157) | 1-1 |
| 29 | white | 21 | Awhite | no mate price: both probed | `e4f6` (kept_main; guard QNP; no mate price; score 303) | `e4g5` (world_switch; guard None; no mate price; score 310) | 1-1 |
| 30 | black | 18 | Ablack | no mate price: both probed | `f6e4` (kept_main; guard QP; no mate price; score 204) | `b8c6` (world_switch; guard None; no mate price; score 193) | 1-1 |
| 30 | white | 20 | Awhite | no mate price: probe here | `d2d4` (world_switch; guard low; no mate price; score -211) | `e1g1` (kept_main; guard None; no mate price; score -196) | 0-0 |
| 31 | black | 23 | Ablack | no mate price: both probed | `N@f4` (kept_main; guard QN; no mate price; score -86) | `d5c3` (world_switch; guard None; no mate price; score -116) | 0-1 |
| 31 | white | 30 | Bblack | no mate price: probe here | `d8e7` (kept_main; guard low; no mate price; score -67) | `e8f8` (kept_main; guard None; no mate price; score -28) | 0-1 |
| 32 | black | 28 | Bwhite | no mate price: both probed | `N@d5` (kept_main; guard QP; no mate price; score 414) | `d4f4` (world_switch; guard None; no mate price; score 403) | 0-0 |
| 32 | white | 21 | Bblack | no mate price: both probed | `d8f6` (world_switch; guard QP; no mate price; score -137) | `g8f6` (kept_main; guard None; no mate price; score -157) | 0-0 |
| 33 | black | 21 | Bwhite | no mate price: both probed | `b1c3` (world_switch; guard QP; no mate price; score -632) | `c4f7` (world_switch; guard None; no mate price; score -569) | 0-1 |
| 33 | white | 16 | Awhite | no mate price: both probed | `f3e5` (world_switch; guard Q; no mate price; score 156) | `d2d3` (kept_main; guard None; no mate price; score 156) | 1-1 |
| 34 | black | 22 | Ablack | no mate price: both probed | `f6h5` (world_switch; guard QNP; no mate price; score 126) | `f6g4` (world_switch; guard None; no mate price; score 106) | 1-0 |
| 34 | white | 29 | Awhite | no mate price: both probed | `d1d4` (kept_main; guard QP; no mate price; score -316) | `f1e2` (kept_main; guard None; no mate price; score -240) | 1-0 |
| 35 | black | 20 | Bwhite | no mate price: both probed | `f1b5` (kept_main; guard QNP; no mate price; score -102) | `c3d5` (kept_main; guard None; no mate price; score -121) | 1-1 |
| 35 | white | 18 | Bblack | no mate price: both probed | `P@g4` (world_switch; guard QN; no mate price; score 300) | `d7d6` (kept_main; guard None; no mate price; score 300) | 1-0 |
| 36 | black | 18 | Ablack | no mate price: both probed | `d7d5` (kept_main; guard Q; no mate price; score -291) | `d7d6` (world_switch; guard None; no mate price; score -290) | 1-0 |
| 36 | white | 32 | Awhite | no mate price: both probed | `f1e1` (kept_main; guard QRBP; no mate price; score 361) | `g5f6` (kept_main; guard None; no mate price; score 329) | 1-0 |
| 37 | black | 20 | Bwhite | no mate price: probe here | `c4f7` (kept_main; guard low; no mate price; score 529) | `f3e5` (world_switch; guard None; no mate price; score 546) | 1-0 |
| 37 | white | 19 | Bblack | no mate price: both probed | `c6d4` (kept_main; guard QBP; no mate price; score -127) | `d7d5` (world_switch; guard None; no mate price; score -127) | 0-0 |
| 38 | black | 19 | Bwhite | no mate price: both probed | `e4d5` (world_switch; guard QBP; no mate price; score -661) | `d2d4` (kept_main; guard None; no mate price; score -661) | 0-0 |
| 38 | white | 24 | Bblack | no mate price: both probed | `P@h3` (world_switch; guard QP; no mate price; score 280) | `N@d6` (kept_main; guard None; no mate price; score 274) | 1-1 |
| 39 | black | 19 | Ablack | no mate price: both probed | `c8f5` (kept_main; guard QP; no mate price; score 14) | `b8c6` (world_switch; guard None; no mate price; score 14) | 1-1 |
| 39 | white | 25 | Awhite | no mate price: both probed | `c1e3` (kept_main; guard QNP; no mate price; score -66) | `c1d2` (kept_main; guard None; no mate price; score 0) | 0-0 |
| 40 | black | 21 | Bwhite | no mate price: both probed | `e1g1` (kept_main; guard QP; no mate price; score -79) | `d3d4` (kept_main; guard None; no mate price; score -75) | 1-1 |
| 40 | white | 20 | Awhite | no mate price: both probed | `b1c3` (kept_main; guard QNP; no mate price; score 55) | `f1b5` (kept_main; guard None; no mate price; score 76) | 1-0 |
| 41 | black | 26 | Ablack | no mate price: both probed | `P@e4` (kept_main; guard QNP; no mate price; score 134) | `g8f6` (kept_main; guard None; no mate price; score 163) | 1-1 |
| 41 | white | 16 | Awhite | no mate price: both probed | `b5d7` (world_switch; guard QB; no mate price; score 20) | `d2d4` (kept_main; guard None; no mate price; score 20) | 1-1 |
| 42 | black | 35 | Ablack | mate price earlier | `d5c6` (kept_main; guard QRP; no mate price; score 47) | `d5c4` (kept_main; guard None; no mate price; score 78) | 1-1 |
| 42 | white | 18 | Bblack | no mate price: both probed | `f6e4` (world_switch; guard QP; no mate price; score -99) | `h7h6` (kept_main; guard None; no mate price; score -99) | 1-0 |
| 43 | black | 27 | Bwhite | no mate price: both probed | `B@h4` (kept_main; guard QP; no mate price; score 53) | `f4g5` (kept_main; guard None; no mate price; score 60) | 1-1 |
| 43 | white | 18 | Awhite | no mate price: both probed | `c1g5` (world_switch; guard QP; no mate price; score 112) | `g1f3` (kept_main; guard None; no mate price; score 112) | 1-1 |
| 44 | black | 29 | Ablack | no mate price: both probed | `b7c6` (kept_main; guard QP; no mate price; score 503) | `e7c6` (world_switch; guard None; no mate price; score 485) | 0-1 |
| 44 | white | 20 | Bblack | no mate price: both probed | `f8e7` (kept_main; guard QP; no mate price; score -30) | `a7a6` (kept_main; guard None; no mate price; score -32) | 1-0 |
| 45 | black | 20 | Bwhite | no mate price: both probed | `f1b5` (kept_main; guard QNP; no mate price; score 107) | `P@g4` (kept_main; guard None; no mate price; score 106) | 1-0 |
| 45 | white | 23 | Bblack | no mate price: both probed | `f5d7` (kept_main; guard QBNP; no mate price; score -73) | `f5g6` (kept_main; guard None; no mate price; score -98) | 0-1 |
| 46 | black | 16 | Ablack | no mate price: both probed | `c7c5` (kept_main; guard QN; no mate price; score -267) | `b6b5` (world_switch; guard None; no mate price; score -267) | 0-1 |
| 46 | white | 26 | Awhite | no mate price: both probed | `h1g1` (no_arrivals; guard QP; no mate price; score 215) | `g2h3` (no_arrivals; guard None; no mate price; score 184) | 1-1 |
| 47 | black | 22 | Bwhite | no mate price: both probed | `g1f3` (kept_main; guard QP; no mate price; score -234) | `P@e5` (world_switch; guard None; no mate price; score -224) | 1-1 |
| 47 | white | 25 | Bblack | no mate price: both probed | `P@h3` (kept_main; guard QN; no mate price; score -162) | `a8c8` (kept_main; guard None; no mate price; score -193) | 0-1 |
| 48 | black | 23 | Ablack | no mate price: both probed | `c6e5` (kept_main; guard QN; no mate price; score -46) | `h7h5` (kept_main; guard None; no mate price; score -46) | 1-1 |
| 48 | white | 33 | Awhite | no mate price: both probed | `f1e1` (kept_main; guard QRNP; no mate price; score 4) | `g1h1` (kept_main; guard None; no mate price; score 16) | 0-1 |
| 49 | black | 28 | Ablack | no mate price: both probed | `d8e7` (kept_main; guard QNP; no mate price; score 21) | `c8d7` (kept_main; guard None; no mate price; score 92) | 1-0 |
| 49 | white | 25 | Bblack | no mate price: both probed | `d7d5` (world_switch; guard QP; no mate price; score -233) | `e5d4` (world_switch; guard None; no mate price; score -200) | 1-1 |
