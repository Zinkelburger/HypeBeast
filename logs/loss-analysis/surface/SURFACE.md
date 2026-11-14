# Two-board score and team win rate: the shape of the surface

Data: 880 games and 95,698 paired decisions from 9 matches. Each decision of a seat is paired with its partner's most
recent decision. All 18 engine sides passed the filter: HBFeedPrices=false was sent, HBPhantom and HBHandDiscount appear
only as advertised options at their default of 0, and no HBTell exists. **No engine was dropped.**
Postmortems were generated for late25-vs-np, late25-vs-np-b, late85-vs-late50, gap0-vs-np and np-woff-vs-np. All fits
are in pure Python, because numpy, scipy and matplotlib are not installed for the only Python on this machine (3.14).
**So no picture was made (surface.png is absent)**; the heat maps are given as tables in the appendices.

## The answer in one paragraph

Away from forced mates, **the team's chance depends on the sum of the two scores and almost nothing else.** Every two-board
shape tried cross-validates within 0.0001 log loss of the plain sum (with and without the mate terms alike): weaker/stronger
weights, a*b interaction, |a-b| imbalance, separate own/partner weights, tanh saturation and imbalance-shrink. Clipping
does worse. The fitted weights of the
weaker and the stronger board are equal (0.872 and 0.873 per 1000 cp). **What the sum misses is forced mates.** A board
showing a forced mate is worth far more than its clamped +/-3000. With mates as their own term, the plain sum gets most
of the way to a shape-free flexible surface. The earlier finding that big margins count more than in proportion (the
|s|^1.25 power) is almost entirely mates in disguise: once mates have their own term, the per-board curve is close to
linear. On "0 and +6 beats two +3", the raw cells lean that way and the flexible surface agrees in sign, but neither is
statistically clear. The split matters only when it gets large. With one board behind by about 800 cp and the other ahead
by 800, the team does 3 points worse than level (flexible surface; the raw cells say worse still, on few games). Beyond
that the data are too thin to say.

## Recommended formula (m1: sum + mate counts)

```
a, b  = own and partner main scores (cp, own point of view), clamped to +/-3000; a forced mate counts as +/-3000
Nfor  = number of the two boards showing a forced mate FOR its seat (0..2)
Nag   = number showing a forced mate AGAINST (0..2)

logit = -0.0440 + 0.7148*(a+b)/1000 + 1.9109*Nfor - 1.8595*Nag
P(team wins) = 1 / (1 + exp(-logit))
```

Integer form (computed by export.py): `P = 1/(1+exp(-(a + b + 2673*Nfor - 2601*Nag - 62) / 1399))`.
So **a forced-mate board counts about +5673 cp (for) or -5601 cp (against)** in the sum, and 1399 cp of total equals one
logit unit. To choose moves only the ordering matters, so the engine can maximise
`a + b + 2673*Nfor - 2601*Nag` directly. The logistic and the -62 offset are only needed for a probability.

Coefficient 95% intervals (200 resamples of games): intercept -0.044 [-0.051, -0.038], sum 0.715 [0.601, 0.841] per
1000 cp, mate-for 1.91 [1.50, 2.39], mate-against -1.86 [-2.33, -1.49]. Some reference values: P(0,0) = 48.9%,
P(0,+600) = P(+300,+300) = 59.5% [58.0, 61.2], a mate for us with the other board at 0 = 98.2%, a mate against with the
other board at 0 = 1.7%, one mate each way = 50.2%. The intercept is below zero: at a level position the deciding seat's
team won 48.9% in the model (49.5% [48.1, 50.9] in the raw cell). It is a constant and does not affect move choice.

**surface.json** (written): `logs/loss-analysis/surface/surface.json` holds this model on a 61 x 61 grid every 100 cp
from -3000 to +3000. Own score is the rows and partner score the columns, for bilinear interpolation. Mates are separate:
`mate_for_vs_other[j]` and `mate_against_vs_other[j]` are indexed by the other board's score, and `mate_both` gives the
three two-mate cases. Coefficients and the integer form are under `source`.

Why this model and not the flexible surface: the flexible surface is better by only 0.99e-3 in pooled CV log loss, with a
per-fold SD of the difference of 1.77e-3. m1 wins 3 of 10 folds. The more elaborate simple formulas (m3, m6, m7, m10,
m11) close at most 0.08e-3 of that gap. If a table is preferred anyway, `flex_full.json` holds the flexible surface's
parameters. Appendix C shows where the two differ: the flexible surface flattens a single board's lead beyond about
+/-1200 cp, and it makes a mate decide the game (97-98%) almost whatever the other board shows.

## Cross-validated log loss (10 folds by game; lower is better)

The reference is the flexible surface: a symmetric bilinear surface on 21 score knots, with forced mate for and against as
two extra categories. It has a second-difference penalty, and lambda was chosen by the same CV. The full table, with all
lambdas, is in Appendix B.

| model | CV log loss | fold SD | minus flexible (x1000), pooled | SD of fold differences (x1000) |
|---|---|---|---|---|
| **f. flexible 2-D surface (lambda=100)** | **0.5367** | 0.0301 | 0 | - |
| a. sum | 0.5444 | 0.0325 | +7.69 | 4.41 |
| b. power g(a)+g(b), p=1.35 (folds 1.31..1.40) | 0.5414 | 0.0311 | +4.67 | 2.38 |
| c. w1*weaker + w2*stronger (0.872, 0.873) | 0.5444 | 0.0325 | +7.69 | 4.41 |
| d. sum + c*a*b | 0.5444 | 0.0326 | +7.65 | 4.43 |
| e. sum + |a-b| (coef +0.0005) | 0.5444 | 0.0325 | +7.69 | 4.41 |
| x1. own, partner weights (0.863, 0.884) | 0.5444 | 0.0326 | +7.67 | 4.40 |
| x3. sum + sum of cubes | 0.5400 | 0.0308 | +3.25 | 2.47 |
| x4. additive free h(a)+h(b), mates as 3000 | 0.5388 | 0.0299 | +2.09 | 1.80 |
| **m1. sum + mate counts (recommended)** | **0.5377** | 0.0300 | **+0.99** | 1.77 |
| m3. tanh-saturated sum + mates (L=2955 cp, at the search edge) | 0.5376 | 0.0299 | +0.90 | 1.72 |
| m4. additive free h + mates | 0.5379 | 0.0299 | +1.18 | 1.29 |
| m7. sum + a*b + mates | 0.5376 | 0.0300 | +0.91 | 1.72 |
| m8. sum + |a-b| + mates | 0.5377 | 0.0301 | +0.99 | 1.76 |
| m10. own, partner + mate flags per board | 0.5376 | 0.0300 | +0.91 | 1.76 |
| m11. (a+b)/(1+|a-b|/M) + mates, M=5800 cp | 0.5376 | 0.0301 | +0.91 | 1.40 |
| m12. mate rows get their own level | 0.5377 | 0.0300 | +1.01 | 2.97 |
| g. m1 + plies x every term | 0.5374 | | +0.64 | |
| g. m1 + plies main effect + plies x every term | 0.5373 | | +0.60 | |
| g. m1 + clock x every term | 0.5378 | | +1.06 | |

**Closest simple formula to the flexible surface:** without mates, the power formula (b) is best but still trails by
4.7e-3. With mates, m1 and its relatives sit within 1e-3, a gap of under 2 fold standard errors.

**Phase (g).** A score does *not* mean more late in the game in these data. Refit by tercile of plies played (cuts at
54 and 91 move tokens), the weight on the sum is 0.71 / 0.77 / 0.68 per 1000 cp, and the shape stays a plain sum. The
mate terms shrink late: +2.63 / +2.55 / +1.84 for a mate for, -2.61 / -2.56 / -1.74 against. Adding plies x every term
gains 0.4e-3 in CV, and the clock (t) gains nothing.

**Mates (g).** Mates are the single biggest correction: a. sum 0.5444 becomes m1 0.5377 (-6.7e-3). Fitted on rows
with no mate on either board (78,068 rows), the sum weight is 0.729, almost the same as m1's 0.715. Raw: when the own board
shows a forced mate for the seat, the team won 94.7% (4,565 decisions); against, 7.2% (6,446). Mate flags per board
(m10) give own and partner mates similar weights (+1.65/-1.94 own, +2.09/-1.82 partner).

## The owner's questions

Win %, with 95% intervals from 200 resamples of games (100 for the flexible surface). In "raw", both boards are within
100 cp of the stated point, in either order, with no mate on either board. In m1, every split at the same total is equal
by construction, so the raw cells and the flexible surface are the informative columns.

| question | raw cells | flexible surface | m1 |
|---|---|---|---|
| (0,+600) | 63.3 [59.6, 67.7] (565 games) | 59.8 [57.0, 62.0] | 59.5 [58.0, 61.2] |
| (+300,+300) | 58.9 [54.1, 63.5] (475 games) | 58.8 [54.8, 62.3] | 59.5 |
| (-100,+700) | 60.3 [55.4, 64.8] (430 games) | 59.9 [56.9, 62.6] | 59.5 |
| (0,+600) minus (+300,+300) | **+4.4 pts [-1.3, +11.0]**, better in 94% of resamples | **+0.9 [-1.9, +4.5]**, better in 78% | 0 |
| (-100,+700) minus (+300,+300) | **+1.4 [-4.8, +8.3]**, 67% | **+1.0 [-2.6, +5.4]**, 81% | 0 |
| (-100,+700) minus (0,+600) | **-3.0 [-8.0, +1.6]**, 14% | **+0.1 [-0.8, +1.2]**, 65% | 0 |

So (0,+600) is probably a little better than (+300,+300), but by a few points at most, and the interval includes zero.
(-100,+700) is about the same as both of them: no difference is distinguishable. The earlier combine.md result
(+11.8 pts for (+600,0) over (+300,+300)) used wider windows and 300 games. With 880 games and +/-100 cp windows,
the gap shrinks to +4.4.

**Along fixed totals** (boards T/2-d and T/2+d; flexible surface, change from the equal split, in points; raw cells in
Appendix B):

| d (cp from equal) | 0 | 100 | 200 | 300 | 500 | 800 | 1200 |
|---|---|---|---|---|---|---|---|
| total +600 | 58.8% | -0.1 [-0.9, 0.8] | +0.1 [-1.8, 2.2] | +0.9 [-1.9, 4.5] | +1.1 [-2.9, 5.9] | -1.4 [-5.6, 4.0] | -4.2 [-9.5, 2.5] |
| total +300 | 53.6% | -0.1 [-1.3, 0.9] | -0.1 [-2.2, 1.9] | +0.6 [-2.3, 3.3] | +1.2 [-1.9, 4.7] | -1.4 [-4.8, 2.6] | -2.4 [-6.7, 2.9] |
| total 0 | 49.7% | -0.4 [-0.9, 0.2] | -0.4 [-1.3, 0.6] | +0.1 [-1.2, 1.5] | -0.5 [-2.1, 1.2] | **-2.9 [-5.2, -0.4]** | -1.9 [-6.6, 2.3] |
| total -300 | 45.4% | -0.2 [-1.2, 0.6] | -0.2 [-2.2, 1.4] | -0.2 [-3.5, 2.5] | -2.0 [-5.8, 1.1] | **-3.5 [-8.2, -0.0]** | -1.1 [-7.3, 3.3] |

Raw cells along the same lines (sum within 150 cp, half-gap within 75 cp) are flat within noise up to d = 500. At d = 800
they drop: total 0 gives 40.9% [31.1, 50.0] (66 games) against 49.5% level, and total -300 gives 38.9% [25.5, 50.0]
(78 games) against 45.5%. At d = 1200 there are 5 to 16 games per line, which is not usable.

**Where being behind starts to cost more than the same lead gains:** at a split of about **+/-800 cp per board** (one board
near -800, the other near +800). The flexible surface's (-x,+x) minus (0,0) is within +/-0.5 points up to x = 500,
-1.7 [-3.4, +0.5] at x = 600, -2.9 [-5.2, -0.4] at x = 800 and -2.5 [-6.0, +0.9] at x = 1000. The raw (-800,+800) cell
gives 40.9% [33.6, 46.8] (124 games, wider window) against 49.5% at (0,0). Beyond about 1000 cp the data are too thin to
say whether the cost grows or fades. The tails of the raw grid suggest it fades again: a board at +1500 or beyond with
the other at -1500 or below gives 50% (Appendix A), but mates dominate those cells. The m7 interaction fits a small *bonus*
for opposite-signed boards (a*b coefficient -0.049 [-0.078, -0.018]). That one global term is set by the same-signed
regions, and in the opposite-signed region it disagrees with the raw cells and the flexible surface, so it is not used.

## What this is and what it is not (warnings)

- **Descriptive, not causal.** This describes how games between these HypeBeast builds ended, given the main-search
  scores they printed. It does not show that steering toward a cell causes that cell's win rate. A position the engine
  steers into on purpose may differ from one it merely landed in. And once the engine optimises a combined score, the
  scores it prints become a different variable.
- **Who and what stands behind it:** 880 games and 95,698 paired decisions; 3 games were draws, counted as 0.5. All
  engines are 500k-node HypeBeast builds on the same net, playing each other: v7b-v8a, with ForecastTrustLate, MaxWorlds,
  ArrivalTiming, WorldMaxGap and WorldSwitch variants. The engines' scores are not calibrated against stronger
  opponents, other time controls or humans. The surface may not transfer to builds with HBFeedPrices=true, to table or
  alarm builds, or to builds whose score scale changes.
- **Decisions in a game are not independent.** The median game contributes 105 decisions. Every interval here
  resamples whole games, and every CV fold holds out whole games.
- **The partner score is stale:** the paired partner decision is a median 2.0 s older (90th percentile 3.8 s). Own and
  partner nonetheless get almost equal weights.
- **Thin regions.** Of the 568 non-empty 150 cp own x partner cells, 104 have fewer than 20 games. In the 300 cp table,
  every cell with one board between -1500 and -900 and the other between +900 and +1500 has at most 23 games.
  Lines at a 1200 cp split have 5-17 games. Treat everything beyond +/-1000 cp per board, outside the mate
  categories, as extrapolation by the formula, not as measurement. Two-mate cases rest on few rows (the mate x mate
  cells of the flexible surface are lightly ridge-penalised).
- The flexible reference's smoothing is in knot-index space (knots spaced 150 cp apart near 0, up to 800 cp at the ends).
  A centipawn-curvature penalty cross-validated slightly worse (0.5370 against 0.5367, cv_flex_cppen.json). So the tail
  flattening is supported by held-out games, but it is partly shaped by that smoothing.
- The power and clip parameters were refitted inside each fold. For m2, m3, m5 and m6 the fold search was limited to
  +/-600 cp around the full-data value, and for m11 to 0.6x-1.6x. m3's L sits at the 3000 cp edge of its range, which
  means "no saturation wanted".

## Files (all in logs/loss-analysis/surface/, git-ignored)

`common.py` (loading, pairing, fitting), `cells.py` (Appendix A, `cells_own_partner.csv`, `cells_weak_strong.csv`:
150 cp cells with decisions, games, win rate and 95% interval), `models.py` (CV: `cv_simple.json`, `cv_flex.json`,
`cv_extra.json`, `flex_full.json`), `questions.py` (`questions_boot.json`), `summarise.py` (Appendices B and C),
`export.py` (`surface.json`), `pairs.json` (the paired rows). Run each with `nice -n 19 python3`, one at a time.

---

# Appendix A: data and the empirical surface

### Data

| match | games | paired decisions | engines | mate score on own board | draws (games) |
|---|---|---|---|---|---|
| late25-vs-np | 100 | 10768 | hb-late25, hb-np | 11.3% | 0 |
| late25-vs-np-b | 100 | 11099 | hb-late25, hb-np | 12.3% | 0 |
| late50-vs-late25 | 100 | 11265 | hb-late25, hb-late50 | 11.3% | 0 |
| late50-vs-np-b | 100 | 10892 | hb-late50, hb-np | 10.9% | 1 |
| late85-vs-late50 | 100 | 10950 | hb-late50, hb-late85 | 11.4% | 0 |
| worlds5-vs-l50 | 100 | 10973 | hb-l50, hb-worlds5 | 11.6% | 0 |
| timing2-vs-l50 | 80 | 8608 | hb-l50, hb-timing2 | 12.5% | 0 |
| gap0-vs-np | 100 | 11047 | hb-gap0, hb-np | 11.5% | 0 |
| np-woff-vs-np | 100 | 10096 | hb-np, hb-np-woff | 10.9% | 2 |
| **all** | 880 | 95698 | | 11.5% | 3 |

Pairs with a forced mate on at least one board: 17630 (18.4%). Time between a decision and the partner decision it is paired with: median 2.0 s, 90th percentile 3.8 s. Decisions per game: median 105.
Own board shows a forced mate FOR the seat: 4565 decisions, team won 94.7%; AGAINST: 6446 decisions, team won 7.2%.

### Team win rate, 300 cp cells: own (across) x partner (down, top = partner far ahead)

Each cell: win % [95% interval] (games). Tails include forced mates. Empty: no data.

| | <-1500 | -1500..-1200 | -1200..-900 | -900..-600 | -600..-300 | -300..0 | 0..300 | 300..600 | 600..900 | 900..1200 | 1200..1500 | >=1500 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **>=1500** | 51 [49-52] (143) | 97 [92-100] (65) | 94 [89-98] (104) | 95 [92-98] (160) | 93 [90-96] (212) | 93 [89-95] (251) | 89 [86-93] (307) | 89 [86-93] (297) | 91 [88-95] (288) | 94 [91-97] (265) | 96 [93-98] (209) | 98 [97-99] (311) |
| **1200..1500** | 1 [0-4] (54) | 100 [100-100] (2) | 67 [44-100] (6) | 47 [28-70] (25) | 57 [43-71] (49) | 74 [65-82] (93) | 67 [59-76] (116) | 80 [72-86] (130) | 81 [72-88] (135) | 86 [78-93] (98) | 90 [83-96] (63) | 95 [92-98] (220) |
| **900..1200** | 5 [2-9] (110) | 41 [17-67] (14) | 40 [21-57] (23) | 53 [40-63] (56) | 61 [53-71] (105) | 69 [62-76] (183) | 72 [65-78] (244) | 75 [70-81] (259) | 80 [74-86] (222) | 87 [79-93] (136) | 87 [80-93] (111) | 92 [89-95] (292) |
| **600..900** | 5 [1-10] (135) | 33 [17-56] (23) | 37 [23-51] (58) | 39 [32-47] (106) | 58 [51-64] (218) | 58 [53-62] (453) | 62 [57-66] (518) | 71 [67-76] (438) | 73 [66-78] (261) | 79 [73-85] (224) | 83 [74-90] (133) | 90 [86-94] (319) |
| **300..600** | 8 [5-11] (227) | 44 [25-62] (41) | 34 [25-43] (118) | 40 [33-45] (231) | 49 [46-52] (459) | 54 [51-57] (695) | 57 [53-60] (762) | 68 [63-73] (517) | 71 [67-75] (451) | 79 [73-84] (282) | 76 [69-81] (164) | 88 [84-92] (332) |
| **0..300** | 8 [5-12] (275) | 26 [18-36] (89) | 34 [27-41] (227) | 37 [33-43] (437) | 46 [43-49] (730) | 49 [49-50] (806) | 53 [50-56] (776) | 57 [54-60] (763) | 62 [57-66] (564) | 67 [61-72] (291) | 71 [63-78] (137) | 87 [83-90] (344) |
| **-300..0** | 6 [4-9] (300) | 26 [18-34] (110) | 31 [25-38] (259) | 33 [28-38] (477) | 41 [37-44] (741) | 46 [43-49] (802) | 49 [48-50] (803) | 53 [51-56] (741) | 59 [55-64] (486) | 72 [65-78] (212) | 73 [65-83] (96) | 90 [86-93] (294) |
| **-600..-300** | 8 [5-12] (309) | 18 [12-24] (137) | 23 [18-29] (265) | 26 [22-32] (390) | 30 [26-35] (484) | 40 [37-44] (729) | 48 [45-51] (710) | 52 [49-54] (447) | 54 [49-60] (251) | 57 [48-65] (126) | 62 [50-78] (56) | 88 [84-93] (226) |
| **-900..-600** | 5 [3-8] (306) | 14 [8-20] (128) | 19 [13-26] (210) | 21 [15-27] (231) | 25 [21-30] (379) | 32 [28-38] (467) | 37 [33-42] (418) | 36 [29-42] (225) | 47 [39-54] (109) | 55 [43-69] (55) | 50 [29-77] (22) | 93 [89-96] (159) |
| **-1200..-900** | 5 [2-8] (268) | 14 [6-23] (84) | 11 [6-18] (117) | 15 [10-21] (194) | 22 [17-27] (239) | 28 [23-35] (237) | 38 [31-45] (203) | 36 [25-45] (107) | 39 [25-54] (67) | 39 [22-54] (19) | 82 [62-100] (8) | 92 [86-96] (110) |
| **-1500..-1200** | 4 [1-7] (177) | 5 [1-10] (58) | 7 [2-12] (100) | 20 [11-28] (122) | 20 [12-27] (116) | 23 [15-31] (107) | 29 [19-40] (73) | 44 [28-62] (42) | 62 [30-86] (13) | 20 [0-43] (12) | 50 [0-100] (3) | 94 [87-99] (65) |
| **<-1500** | 1 [0-2] (282) | 2 [0-4] (165) | 4 [2-8] (232) | 6 [3-9] (270) | 9 [5-14] (261) | 9 [6-13] (246) | 9 [6-14] (231) | 8 [4-12] (200) | 4 [1-8] (121) | 6 [2-10] (95) | 2 [0-6] (41) | 49 [46-51] (140) |

### Team win rate, 300 cp cells: weaker board (across) x stronger board (down)

Each cell: win % [95% interval] (games). Tails include forced mates. Empty: no data.

| | <-1500 | -1500..-1200 | -1200..-900 | -900..-600 | -600..-300 | -300..0 | 0..300 | 300..600 | 600..900 | 900..1200 | 1200..1500 | >=1500 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **>=1500** | 50 [48-52] (145) | 96 [90-99] (77) | 93 [89-97] (124) | 94 [91-97] (187) | 91 [87-95] (254) | 91 [88-94] (320) | 88 [84-92] (373) | 89 [85-92] (367) | 91 [87-95] (354) | 93 [90-96] (320) | 96 [93-98] (250) | 98 [97-99] (311) |
| **1200..1500** | 1 [0-4] (61) | 67 [0-100] (3) | 75 [51-100] (10) | 48 [30-70] (31) | 60 [46-73] (78) | 73 [65-81] (134) | 69 [61-77] (176) | 78 [71-84] (201) | 82 [73-89] (182) | 86 [80-93] (143) | 90 [82-96] (63) |  |
| **900..1200** | 5 [2-9] (121) | 31 [13-49] (19) | 40 [25-53] (28) | 54 [45-65] (77) | 59 [50-68] (156) | 70 [65-76] (269) | 69 [64-75] (356) | 77 [72-82] (352) | 80 [74-85] (292) | 87 [79-92] (136) |  |  |
| **600..900** | 4 [1-9] (152) | 45 [25-63] (28) | 38 [26-50] (89) | 43 [37-49] (145) | 56 [50-61] (309) | 58 [54-62] (576) | 62 [58-66] (647) | 71 [67-75] (541) | 73 [67-79] (261) |  |  |  |
| **300..600** | 8 [4-12] (253) | 44 [29-58] (65) | 35 [25-45] (152) | 38 [32-44] (305) | 51 [48-53] (546) | 54 [51-56] (777) | 57 [54-60] (803) | 68 [63-73] (517) |  |  |  |  |
| **0..300** | 9 [5-12] (295) | 28 [18-37] (118) | 36 [30-42] (284) | 37 [33-42] (526) | 47 [44-50] (778) | 49 [48-50] (822) | 53 [49-55] (776) |  |  |  |  |  |
| **-300..0** | 7 [5-10] (324) | 24 [17-32] (149) | 30 [24-35] (329) | 32 [28-37] (568) | 40 [37-44] (794) | 46 [43-50] (802) |  |  |  |  |  |  |
| **-600..-300** | 9 [5-12] (338) | 19 [12-25] (177) | 22 [18-29] (322) | 26 [22-31] (474) | 30 [26-36] (484) |  |  |  |  |  |  |  |
| **-900..-600** | 6 [3-9] (328) | 17 [11-24] (173) | 17 [12-23] (264) | 21 [15-27] (231) |  |  |  |  |  |  |  |  |
| **-1200..-900** | 5 [2-8] (286) | 10 [4-18] (131) | 11 [5-18] (117) |  |  |  |  |  |  |  |  |  |
| **-1500..-1200** | 3 [1-5] (198) | 5 [1-12] (58) |  |  |  |  |  |  |  |  |  |  |
| **<-1500** | 1 [0-2] (282) |  |  |  |  |  |  |  |  |  |  |  |

150 cp grid (own x partner): 568 non-empty cells of 576; 104 have fewer than 20 games. Weaker x stronger: 297 non-empty cells, 41 with fewer than 20 games.

# Appendix B: all model fits, the fixed-total curves and the raw comparison cells (summarise.py)

| model | CV log loss | SD across folds | minus flexible, x1000: pooled | per-fold SD | better than flexible in folds |
|---|---|---|---|---|---|
| f. flexible 2-D surface, lambda=3 | 0.5373 | 0.0302 | +0.56 | 0.76 | 3/10 |
| f. flexible 2-D surface, lambda=10 | 0.5370 | 0.0302 | +0.28 | 0.53 | 3/10 |
| f. flexible 2-D surface, lambda=30 | 0.5368 | 0.0302 | +0.09 | 0.28 | 4/10 |
| f. flexible 2-D surface, lambda=100 (chosen) | 0.5367 | 0.0301 | +0.00 | 0.00 | 0/10 |
| f. flexible 2-D surface, lambda=300 | 0.5368 | 0.0300 | +0.11 | 0.26 | 2/10 |
| f. flexible 2-D surface, lambda=1000 | 0.5373 | 0.0299 | +0.56 | 0.64 | 2/10 |
| a. sum | 0.5444 | 0.0325 | +7.69 | 4.41 | 0/10 |
| b. power g(a)+g(b) (p=1.35) | 0.5414 | 0.0311 | +4.67 | 2.38 | 0/10 |
| c. weaker, stronger | 0.5444 | 0.0325 | +7.69 | 4.41 | 0/10 |
| d. sum + a*b | 0.5444 | 0.0326 | +7.65 | 4.43 | 0/10 |
| e. sum + |a-b| | 0.5444 | 0.0325 | +7.69 | 4.41 | 0/10 |
| x1. own, partner (two weights) | 0.5444 | 0.0326 | +7.67 | 4.40 | 0/10 |
| x2. power + |a-b| (p=1.35) | 0.5414 | 0.0311 | +4.67 | 2.38 | 0/10 |
| x3. sum + sum of cubes | 0.5400 | 0.0308 | +3.25 | 2.47 | 0/10 |
| x4. additive h(a)+h(b), h free (21-knot piecewise linear) | 0.5388 | 0.0299 | +2.09 | 1.80 | 1/10 |
| m1. sum + mate counts | 0.5377 | 0.0300 | +0.99 | 1.77 | 3/10 |
| m2. clipped sum (clip at L) + mate counts (p=2.18) | 0.5381 | 0.0300 | +1.34 | 1.65 | 1/10 |
| m3. tanh sum, L*[tanh(a/L)+tanh(b/L)], + mate counts (p=2.96) | 0.5376 | 0.0299 | +0.90 | 1.72 | 3/10 |
| m4. additive h(a)+h(b), h free, mates own categories | 0.5379 | 0.0299 | +1.18 | 1.29 | 1/10 |
| m5. clipped sum + |a-b| + mate counts (p=2.45) | 0.5379 | 0.0301 | +1.16 | 1.70 | 3/10 |
| m6. clipped sum + clipped product + mate counts (p=2.47) | 0.5377 | 0.0300 | +0.98 | 1.71 | 3/10 |
| m7. sum + a*b + mate counts | 0.5376 | 0.0300 | +0.91 | 1.72 | 3/10 |
| m8. sum + |a-b| + mate counts | 0.5377 | 0.0301 | +0.99 | 1.76 | 3/10 |
| m9. weaker, stronger + mate counts | 0.5377 | 0.0301 | +0.99 | 1.76 | 3/10 |
| m10. own, partner + mate flags by board | 0.5376 | 0.0300 | +0.91 | 1.76 | 3/10 |
| m11. sum shrunk by imbalance, (a+b)/(1+|a-b|/M), + mate counts (p=5.79) | 0.5376 | 0.0301 | +0.91 | 1.40 | 2/10 |
| m12. sum when no mate; a mate sets its own level (slope in the other board) | 0.5377 | 0.0300 | +1.01 | 2.97 | 3/10 |
| g. m1. sum + mate counts base | 0.5377 | 0.0300 | +0.99 | 1.77 | 3/10 |
| g. m1. sum + mate counts + plies x score term only | 0.5376 | 0.0300 | +0.86 | 2.92 | 5/10 |
| g. m1. sum + mate counts + plies x every term (score and mates) | 0.5374 | 0.0298 | +0.64 | 2.24 | 3/10 |
| g. m1. sum + mate counts + clock x every term | 0.5378 | 0.0302 | +1.05 | 2.44 | 4/10 |
| g. m1. sum + mate counts + plies main effect + plies x every term | 0.5373 | 0.0299 | +0.59 | 2.22 | 3/10 |

Full-data coefficients (scores in units of 1000 cp; the first coefficient is the intercept):

- a. sum: beta = [-0.0489, 0.8729]
- b. power g(a)+g(b): beta = [-0.0438, 0.7587], p = 1.350, p across folds 1.31..1.40
- c. weaker, stronger: beta = [-0.0493, 0.8724, 0.8734]
- d. sum + a*b: beta = [-0.0513, 0.8736, -0.0162]
- e. sum + |a-b|: beta = [-0.0493, 0.8729, 0.0005]
- x1. own, partner (two weights): beta = [-0.0496, 0.8630, 0.8839]
- x2. power + |a-b|: beta = [-0.0403, 0.7588, -0.0056], p = 1.350, p across folds 1.31..1.40
- x3. sum + sum of cubes: beta = [-0.0439, 0.6362, 0.0632]
- x4. additive h(a)+h(b), h free (21-knot piecewise linear): beta = [-3.8550, -1.2511, -1.1226, -1.0993, -0.8012, -0.7403, -0.5115, -0.3127, -0.1794, -0.1096, -0.0020, 0.0623, 0.1659, 0.3075, 0.4414, 0.5048, 0.8052, 1.0064, 1.0437, 1.0096, 3.8199]
- m1. sum + mate counts: beta = [-0.0440, 0.7148, 1.9109, -1.8595]
- m2. clipped sum (clip at L) + mate counts: beta = [-0.0439, 0.7257, 2.4649, -2.4119], p = 2.181, p across folds 1.60..2.57
- m3. tanh sum, L*[tanh(a/L)+tanh(b/L)], + mate counts: beta = [-0.0442, 0.7645, 1.7788, -1.7256], p = 2.955, p across folds 2.48..3.00
- m4. additive h(a)+h(b), h free, mates own categories: beta = [-2.0849, -1.4824, -1.0924, -1.1131, -0.8023, -0.7426, -0.5113, -0.3132, -0.1791, -0.1096, -0.0016, 0.0619, 0.1663, 0.3071, 0.4431, 0.5056, 0.8054, 1.0287, 0.9923, 1.3235, 1.6488, 4.0234, -4.0054]
- m5. clipped sum + |a-b| + mate counts: beta = [-0.0325, 0.7204, -0.0239, 2.3444, -2.1838], p = 2.446, p across folds 1.85..2.57
- m6. clipped sum + clipped product + mate counts: beta = [-0.0390, 0.7224, -0.0520, 2.1452, -2.3782], p = 2.468, p across folds 1.91..2.64
- m7. sum + a*b + mate counts: beta = [-0.0390, 0.7176, -0.0490, 1.7349, -2.0727]
- m8. sum + |a-b| + mate counts: beta = [-0.0320, 0.7154, -0.0252, 1.9803, -1.7869]
- m9. weaker, stronger + mate counts: beta = [-0.0320, 0.7405, 0.6902, 1.9803, -1.7869]
- m10. own, partner + mate flags by board: beta = [-0.0438, 0.7109, 0.7193, 1.6501, -1.9410, 2.0931, -1.8227]
- m11. sum shrunk by imbalance, (a+b)/(1+|a-b|/M), + mate counts: beta = [-0.0438, 0.8013, 2.3603, -2.3077], p = 5.794, p across folds 4.35..8.36
- m12. sum when no mate; a mate sets its own level (slope in the other board): beta = [-0.0436, 0.7293, 3.8368, 0.0178, -4.1166, 0.3783, 6.2275, -5.7953, 0.0770]

Phase and mate variants of m1. sum + mate counts (full data):

- base: beta = [-0.0440, 0.7148, 1.9109, -1.8595]
- + plies x score term only: beta = [-0.0462, 0.9243, 2.0244, -1.9700, -0.2208]
- + plies x every term (score and mates): beta = [-0.0456, 0.8616, 3.8522, -3.6420, -0.1539, -1.5157, 1.3935]
- + clock x every term: beta = [-0.0452, 0.8489, 2.2178, -2.4783, -0.1012, -0.1070, 0.2438]
- + plies main effect + plies x every term: beta = [0.0009, 0.8593, 3.8304, -3.6766, -0.0726, -0.1509, -1.4798, 1.4453]
- terciles of plies played (cuts at 54 and 91 move tokens): early: beta = [-0.0194, 0.7069, 2.6345, -2.6068] (n=31689); middle: beta = [-0.0581, 0.7739, 2.5463, -2.5626] (n=31450); late: beta = [-0.0765, 0.6781, 1.8392, -1.7395] (n=32559)
- rows with no forced mate on either board only (n=78068): beta = [-0.0436, 0.7293, 0.0000, 0.0000]

### Points and comparisons (win %, 95% interval from resampling games)

| | raw cells (both boards within 100 cp, either order) | m1. sum + mate counts | m7. sum + a*b + mate counts | flex |
|---|---|---|---|---|
| (0,+600) | 63.3 [59.6, 67.7] (565 g) | 59.5 [58.0, 61.2] | 59.7 [58.1, 61.4] | 59.8 [57.0, 62.0] |
| (+300,+300) | 58.9 [54.1, 63.5] (475 g) | 59.5 [58.0, 61.2] | 59.6 [58.0, 61.2] | 58.8 [54.8, 62.3] |
| (-100,+700) | 60.3 [55.4, 64.8] (430 g) | 59.5 [58.0, 61.2] | 59.7 [58.2, 61.5] | 59.9 [56.9, 62.6] |
| (0,+600) - (+300,+300), points | 4.4 [-1.3, 11.0] (better in 94%) | 0.0 [0.0, 0.0] (better in 0%) | 0.1 [0.0, 0.2] (better in 100%) | 0.9 [-1.9, 4.5] (better in 78%) |
| (-100,+700) - (+300,+300), points | 1.4 [-4.8, 8.3] (better in 67%) | 0.0 [0.0, 0.0] (better in 0%) | 0.2 [0.1, 0.3] (better in 100%) | 1.0 [-2.6, 5.4] (better in 81%) |
| (-100,+700) - (0,+600), points | -3.0 [-8.0, 1.6] (better in 14%) | 0.0 [0.0, 0.0] (better in 0%) | 0.1 [0.0, 0.1] (better in 100%) | 0.1 [-0.8, 1.2] (better in 65%) |

### Along fixed totals: boards (T/2 - d, T/2 + d), win % [95%]

**Total +600**

| d | boards | raw (sum within 150, half-gap within 75) | m1. sum + mate counts | m7. sum + a*b + mate counts | flex | m1. sum + mate counts: change from d=0, pts | m7. sum + a*b + mate counts: change from d=0, pts | flex: change from d=0, pts |
|---|---|---|---|---|---|---|---|---|
| 0 | (+300, +300) | 59.1 [54.5, 64.2] (494 g) | 59.5 [58.0, 61.2] | 59.6 [58.0, 61.2] | 58.8 [54.8, 62.3] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 100 | (+200, +400) | 57.6 [53.5, 61.2] (676 g) | 59.5 [58.0, 61.2] | 59.6 [58.1, 61.2] | 58.8 [55.5, 61.9] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | -0.1 [-0.9, 0.8] |
| 200 | (+100, +500) | 58.1 [54.3, 61.5] (658 g) | 59.5 [58.0, 61.2] | 59.6 [58.1, 61.3] | 58.9 [56.1, 61.4] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.1] | 0.1 [-1.8, 2.2] |
| 300 | (+0, +600) | 63.2 [59.7, 66.7] (597 g) | 59.5 [58.0, 61.2] | 59.7 [58.1, 61.4] | 59.8 [57.0, 62.0] | 0.0 [0.0, 0.0] | 0.1 [0.0, 0.2] | 0.9 [-1.9, 4.5] |
| 500 | (-200, +800) | 59.5 [54.3, 65.5] (323 g) | 59.5 [58.0, 61.2] | 59.9 [58.3, 61.7] | 59.9 [57.0, 63.2] | 0.0 [0.0, 0.0] | 0.3 [0.1, 0.5] | 1.1 [-2.9, 5.9] |
| 800 | (-500, +1100) | 51.6 [38.8, 65.1] (73 g) | 59.5 [58.0, 61.2] | 60.3 [58.6, 62.2] | 57.5 [53.1, 60.8] | 0.0 [0.0, 0.0] | 0.8 [0.3, 1.2] | -1.4 [-5.6, 4.0] |
| 1200 | (-900, +1500) | 85.0 [63.6, 100.0] (16 g) | 59.5 [58.0, 61.2] | 61.2 [59.1, 63.6] | 54.7 [49.6, 59.3] | 0.0 [0.0, 0.0] | 1.7 [0.6, 2.6] | -4.2 [-9.5, 2.5] |

**Total +300**

| d | boards | raw (sum within 150, half-gap within 75) | m1. sum + mate counts | m7. sum + a*b + mate counts | flex | m1. sum + mate counts: change from d=0, pts | m7. sum + a*b + mate counts: change from d=0, pts | flex: change from d=0, pts |
|---|---|---|---|---|---|---|---|---|
| 0 | (+150, +150) | 54.5 [50.3, 58.2] (670 g) | 54.3 [53.5, 55.0] | 54.4 [53.7, 55.2] | 53.6 [50.8, 55.9] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 100 | (+50, +250) | 53.9 [51.0, 56.7] (807 g) | 54.3 [53.5, 55.0] | 54.4 [53.7, 55.2] | 53.4 [51.4, 55.1] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | -0.1 [-1.3, 0.9] |
| 200 | (-50, +350) | 53.1 [50.5, 55.5] (774 g) | 54.3 [53.5, 55.0] | 54.4 [53.7, 55.2] | 53.5 [51.8, 54.8] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.1] | -0.1 [-2.2, 1.9] |
| 300 | (-150, +450) | 55.4 [52.1, 58.8] (621 g) | 54.3 [53.5, 55.0] | 54.5 [53.8, 55.4] | 54.2 [52.6, 55.8] | 0.0 [0.0, 0.0] | 0.1 [0.0, 0.2] | 0.6 [-2.3, 3.3] |
| 500 | (-350, +650) | 55.0 [49.8, 60.5] (322 g) | 54.3 [53.5, 55.0] | 54.7 [53.9, 55.6] | 54.7 [53.1, 57.0] | 0.0 [0.0, 0.0] | 0.3 [0.1, 0.5] | 1.2 [-1.9, 4.7] |
| 800 | (-650, +950) | 49.6 [38.7, 60.0] (84 g) | 54.3 [53.5, 55.0] | 55.1 [54.1, 56.3] | 52.2 [49.9, 54.5] | 0.0 [-0.0, 0.0] | 0.8 [0.3, 1.2] | -1.4 [-4.8, 2.6] |
| 1200 | (-1050, +1350) | 83.3 [50.0, 100.0] (5 g) | 54.3 [53.5, 55.0] | 56.1 [54.6, 57.8] | 51.2 [47.4, 55.0] | 0.0 [0.0, 0.0] | 1.7 [0.6, 2.7] | -2.4 [-6.7, 2.9] |

**Total +0**

| d | boards | raw (sum within 150, half-gap within 75) | m1. sum + mate counts | m7. sum + a*b + mate counts | flex | m1. sum + mate counts: change from d=0, pts | m7. sum + a*b + mate counts: change from d=0, pts | flex: change from d=0, pts |
|---|---|---|---|---|---|---|---|---|
| 0 | (+0, +0) | 49.5 [48.1, 50.9] (701 g) | 48.9 [48.7, 49.1] | 49.0 [48.8, 49.2] | 49.7 [48.8, 50.7] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 100 | (-100, +100) | 48.8 [47.7, 49.7] (787 g) | 48.9 [48.7, 49.1] | 49.0 [48.8, 49.2] | 49.3 [48.8, 49.8] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | -0.4 [-0.9, 0.2] |
| 200 | (-200, +200) | 48.1 [46.4, 49.8] (694 g) | 48.9 [48.7, 49.1] | 49.1 [48.9, 49.3] | 49.3 [48.9, 49.8] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.1] | -0.4 [-1.3, 0.6] |
| 300 | (-300, +300) | 50.3 [48.4, 52.3] (636 g) | 48.9 [48.7, 49.1] | 49.1 [48.9, 49.4] | 49.8 [49.0, 50.7] | 0.0 [0.0, 0.0] | 0.1 [0.0, 0.2] | 0.1 [-1.2, 1.5] |
| 500 | (-500, +500) | 50.8 [47.1, 55.4] (299 g) | 48.9 [48.7, 49.1] | 49.3 [49.0, 49.6] | 49.1 [48.0, 50.4] | 0.0 [0.0, 0.0] | 0.3 [0.1, 0.5] | -0.5 [-2.1, 1.2] |
| 800 | (-800, +800) | 40.9 [31.1, 50.0] (66 g) | 48.9 [48.7, 49.1] | 49.8 [49.2, 50.3] | 46.8 [44.7, 48.8] | 0.0 [0.0, 0.0] | 0.8 [0.3, 1.2] | -2.9 [-5.2, -0.4] |
| 1200 | (-1200, +1200) | 50.0 [0.0, 70.1] (7 g) | 48.9 [48.7, 49.1] | 50.8 [49.6, 51.9] | 47.7 [43.3, 51.7] | 0.0 [0.0, 0.0] | 1.8 [0.6, 2.8] | -1.9 [-6.6, 2.3] |

**Total -300**

| d | boards | raw (sum within 150, half-gap within 75) | m1. sum + mate counts | m7. sum + a*b + mate counts | flex | m1. sum + mate counts: change from d=0, pts | m7. sum + a*b + mate counts: change from d=0, pts | flex: change from d=0, pts |
|---|---|---|---|---|---|---|---|---|
| 0 | (-150, -150) | 45.5 [42.2, 50.1] (647 g) | 43.6 [42.5, 44.5] | 43.6 [42.5, 44.6] | 45.4 [43.2, 48.2] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 100 | (-250, -50) | 46.4 [43.3, 49.5] (799 g) | 43.6 [42.5, 44.5] | 43.7 [42.5, 44.6] | 45.3 [43.3, 47.4] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | -0.2 [-1.2, 0.6] |
| 200 | (-350, +50) | 46.8 [43.8, 49.5] (759 g) | 43.6 [42.5, 44.5] | 43.7 [42.6, 44.7] | 45.3 [43.6, 47.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.1] | -0.2 [-2.2, 1.4] |
| 300 | (-450, +150) | 45.4 [42.2, 49.1] (629 g) | 43.6 [42.5, 44.5] | 43.8 [42.7, 44.8] | 45.3 [43.2, 47.4] | 0.0 [-0.0, 0.0] | 0.1 [0.0, 0.2] | -0.2 [-3.5, 2.5] |
| 500 | (-650, +350) | 44.0 [38.5, 49.3] (304 g) | 43.6 [42.5, 44.5] | 44.0 [42.9, 44.9] | 43.4 [40.7, 45.9] | 0.0 [-0.0, 0.0] | 0.3 [0.1, 0.5] | -2.0 [-5.8, 1.1] |
| 800 | (-950, +650) | 38.9 [25.5, 50.0] (78 g) | 43.6 [42.5, 44.5] | 44.4 [43.4, 45.6] | 41.9 [38.3, 45.1] | 0.0 [0.0, 0.0] | 0.8 [0.3, 1.2] | -3.5 [-8.2, -0.0] |
| 1200 | (-1350, +1050) | 14.3 [0.0, 50.0] (6 g) | 43.6 [42.5, 44.5] | 45.4 [43.9, 46.9] | 44.3 [39.0, 48.9] | 0.0 [-0.0, 0.0] | 1.7 [0.6, 2.8] | -1.1 [-7.3, 3.3] |

### Behind on one board by x, ahead on the other by x, minus level (0,0): win-rate points [95%]

| x | raw (-x,+x) win % | m1. sum + mate counts | m7. sum + a*b + mate counts | flex |
|---|---|---|---|---|
| 100 | 48.8 [47.7, 49.7] (787 g) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | -0.4 [-0.9, 0.2] |
| 200 | 48.1 [46.4, 49.8] (694 g) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.1] | -0.4 [-1.3, 0.6] |
| 300 | 50.3 [48.4, 52.3] (636 g) | 0.0 [0.0, 0.0] | 0.1 [0.0, 0.2] | 0.1 [-1.2, 1.5] |
| 400 | 51.6 [48.7, 54.5] (483 g) | 0.0 [0.0, 0.0] | 0.2 [0.1, 0.3] | 0.1 [-1.5, 1.7] |
| 500 | 49.8 [45.8, 54.2] (316 g) | 0.0 [0.0, 0.0] | 0.3 [0.1, 0.5] | -0.5 [-2.1, 1.2] |
| 600 | 49.8 [45.2, 54.7] (251 g) | 0.0 [0.0, 0.0] | 0.4 [0.2, 0.7] | -1.7 [-3.4, 0.5] |
| 800 | 40.9 [33.6, 46.8] (124 g) | 0.0 [0.0, 0.0] | 0.8 [0.3, 1.2] | -2.9 [-5.2, -0.4] |
| 1000 | 46.2 [33.8, 55.7] (50 g) | 0.0 [0.0, 0.0] | 1.2 [0.4, 1.9] | -2.5 [-6.0, 0.9] |
| 1200 | 45.2 [21.4, 60.7] (17 g) | 0.0 [0.0, 0.0] | 1.8 [0.6, 2.8] | -1.9 [-6.6, 2.3] |
| 1500 | - | 0.0 [0.0, 0.0] | 2.8 [1.0, 4.4] | -1.2 [-7.5, 4.6] |
| 2000 | - | 0.0 [0.0, 0.0] | 4.9 [1.8, 7.7] | -0.6 [-8.6, 7.6] |
| 2500 | - | 0.0 [0.0, 0.0] | 7.6 [2.8, 11.9] | -0.3 [-9.7, 9.6] |
| 3000 | - | 0.0 [0.0, 0.0] | 10.9 [4.0, 16.9] | -0.1 [-11.0, 11.2] |

Raw (0,0) (sum within 150, half-gap within 75): 49.5 [48.1, 50.9] (701 g).

Coefficient intervals, m1. sum + mate counts: beta0 -0.0440 [-0.0509, -0.0379], beta1 0.7148 [0.6006, 0.8411], beta2 1.9109 [1.5049, 2.3850], beta3 -1.8595 [-2.3336, -1.4891]

Coefficient intervals, m7. sum + a*b + mate counts: beta0 -0.0390 [-0.0470, -0.0319], beta1 0.7176 [0.6034, 0.8427], beta2 -0.0490 [-0.0775, -0.0176], beta3 1.7349 [1.3112, 2.2254], beta4 -2.0727 [-2.5044, -1.6773]


# Appendix C: fitted surfaces as tables (no picture: matplotlib is not installed)

### Model surface: flexible surface (lambda=100), team win % (own across, partner down)

| partner \ own | -1500 | -1200 | -900 | -600 | -300 | +0 | +300 | +600 | +900 | +1200 | +1500 | +2200 | mate for |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mate for** | 98 | 98 | 98 | 98 | 98 | 98 | 97 | 97 | 97 | 98 | 98 | 98 | 99 |
| **+2200** | 54 | 57 | 60 | 64 | 69 | 73 | 78 | 84 | 89 | 92 | 94 | 97 | 98 |
| **+1500** | 48 | 51 | 55 | 59 | 65 | 70 | 75 | 81 | 86 | 89 | 91 | 94 | 98 |
| **+1200** | 45 | 48 | 51 | 56 | 63 | 68 | 73 | 79 | 84 | 87 | 89 | 92 | 98 |
| **+900** | 41 | 43 | 47 | 52 | 60 | 65 | 70 | 76 | 81 | 84 | 86 | 89 | 97 |
| **+600** | 36 | 38 | 42 | 48 | 55 | 60 | 65 | 72 | 76 | 79 | 81 | 84 | 97 |
| **+300** | 31 | 33 | 37 | 44 | 50 | 53 | 59 | 65 | 70 | 73 | 75 | 78 | 97 |
| **+0** | 27 | 29 | 33 | 39 | 46 | 50 | 53 | 60 | 65 | 68 | 70 | 73 | 98 |
| **-300** | 22 | 25 | 28 | 32 | 39 | 46 | 50 | 55 | 60 | 63 | 65 | 69 | 98 |
| **-600** | 16 | 18 | 21 | 25 | 32 | 39 | 44 | 48 | 52 | 56 | 59 | 64 | 98 |
| **-900** | 11 | 13 | 16 | 21 | 28 | 33 | 37 | 42 | 47 | 51 | 55 | 60 | 98 |
| **-1200** | 8 | 10 | 13 | 18 | 25 | 29 | 33 | 38 | 43 | 48 | 51 | 57 | 98 |
| **-1500** | 7 | 8 | 11 | 16 | 22 | 27 | 31 | 36 | 41 | 45 | 48 | 54 | 98 |
| **mate against** | 1 | 1 | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 3 | 3 | 3 | 52 |

### Model surface: m1. sum + mate counts, team win % (own across, partner down)

| partner \ own | -1500 | -1200 | -900 | -600 | -300 | +0 | +300 | +600 | +900 | +1200 | +1500 | +2200 | mate for |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mate for** | 95 | 96 | 97 | 97 | 98 | 98 | 99 | 99 | 99 | 99 | 99 | 100 | 100 |
| **+2200** | 61 | 66 | 71 | 75 | 79 | 82 | 85 | 88 | 90 | 92 | 93 | 96 | 100 |
| **+1500** | 49 | 54 | 60 | 65 | 69 | 74 | 78 | 81 | 84 | 87 | 89 | 93 | 99 |
| **+1200** | 44 | 49 | 54 | 60 | 65 | 69 | 74 | 78 | 81 | 84 | 87 | 92 | 99 |
| **+900** | 38 | 44 | 49 | 54 | 60 | 65 | 69 | 74 | 78 | 81 | 84 | 90 | 99 |
| **+600** | 33 | 38 | 44 | 49 | 54 | 60 | 65 | 69 | 74 | 78 | 81 | 88 | 99 |
| **+300** | 29 | 33 | 38 | 44 | 49 | 54 | 60 | 65 | 69 | 74 | 78 | 85 | 99 |
| **+0** | 25 | 29 | 33 | 38 | 44 | 49 | 54 | 60 | 65 | 69 | 74 | 82 | 98 |
| **-300** | 21 | 25 | 29 | 33 | 38 | 44 | 49 | 54 | 60 | 65 | 69 | 79 | 98 |
| **-600** | 18 | 21 | 25 | 29 | 33 | 38 | 44 | 49 | 54 | 60 | 65 | 75 | 97 |
| **-900** | 15 | 18 | 21 | 25 | 29 | 33 | 38 | 44 | 49 | 54 | 60 | 71 | 97 |
| **-1200** | 12 | 15 | 18 | 21 | 25 | 29 | 33 | 38 | 44 | 49 | 54 | 66 | 96 |
| **-1500** | 10 | 12 | 15 | 18 | 21 | 25 | 29 | 33 | 38 | 44 | 49 | 61 | 95 |
| **mate against** | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 3 | 3 | 4 | 5 | 8 | 50 |

### Model surface: m7. sum + a*b + mate counts, team win % (own across, partner down)

| partner \ own | -1500 | -1200 | -900 | -600 | -300 | +0 | +300 | +600 | +900 | +1200 | +1500 | +2200 | mate for |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mate for** | 95 | 96 | 97 | 97 | 98 | 98 | 98 | 99 | 99 | 99 | 99 | 99 | 100 |
| **+2200** | 65 | 69 | 73 | 76 | 80 | 82 | 85 | 87 | 89 | 91 | 92 | 95 | 99 |
| **+1500** | 52 | 57 | 61 | 66 | 70 | 74 | 77 | 81 | 83 | 86 | 88 | 92 | 99 |
| **+1200** | 46 | 51 | 56 | 61 | 65 | 69 | 73 | 77 | 80 | 83 | 86 | 91 | 99 |
| **+900** | 40 | 45 | 50 | 55 | 60 | 65 | 69 | 73 | 77 | 80 | 83 | 89 | 99 |
| **+600** | 35 | 39 | 44 | 49 | 55 | 60 | 65 | 69 | 73 | 77 | 81 | 87 | 99 |
| **+300** | 29 | 34 | 39 | 44 | 49 | 54 | 60 | 65 | 69 | 73 | 77 | 85 | 98 |
| **+0** | 25 | 29 | 34 | 38 | 44 | 49 | 54 | 60 | 65 | 69 | 74 | 82 | 98 |
| **-300** | 21 | 24 | 29 | 33 | 38 | 44 | 49 | 55 | 60 | 65 | 70 | 80 | 98 |
| **-600** | 17 | 20 | 24 | 29 | 33 | 38 | 44 | 49 | 55 | 61 | 66 | 76 | 97 |
| **-900** | 14 | 17 | 20 | 24 | 29 | 34 | 39 | 44 | 50 | 56 | 61 | 73 | 97 |
| **-1200** | 11 | 14 | 17 | 20 | 24 | 29 | 34 | 39 | 45 | 51 | 57 | 69 | 96 |
| **-1500** | 9 | 11 | 14 | 17 | 21 | 25 | 29 | 35 | 40 | 46 | 52 | 65 | 95 |
| **mate against** | 0 | 0 | 1 | 1 | 1 | 1 | 2 | 2 | 3 | 4 | 5 | 9 | 52 |

Per-board h (logit units) from x4. additive h(a)+h(b), h free (21-knot piecewise linear): -3000: -3.85, -2200: -1.25, -1700: -1.12, -1300: -1.10, -1000: -0.80, -800: -0.74, -600: -0.51, -450: -0.31, -300: -0.18, -150: -0.11, +0: -0.00, +150: +0.06, +300: +0.17, +450: +0.31, +600: +0.44, +800: +0.50, +1000: +0.81, +1300: +1.01, +1700: +1.04, +2200: +1.01, +3000: +3.82

Per-board h (logit units) from m4. additive h(a)+h(b), h free, mates own categories: -3000: -2.08, -2200: -1.48, -1700: -1.09, -1300: -1.11, -1000: -0.80, -800: -0.74, -600: -0.51, -450: -0.31, -300: -0.18, -150: -0.11, +0: -0.00, +150: +0.06, +300: +0.17, +450: +0.31, +600: +0.44, +800: +0.51, +1000: +0.81, +1300: +1.03, +1700: +0.99, +2200: +1.32, +3000: +1.65; mate for: +4.02, mate against: -4.01

