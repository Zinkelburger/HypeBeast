# Combining the two boards' scores

Matches: late50-vs-np-b, late50-vs-late25, worlds5-vs-l50.

Pairs: 33130; time between a decision and its partner's paired decision: median 2.0 s, 90th percentile 3.8 s. Draws count 0.5.

### candidates (hb-late50, hb-l50): 16564 paired decisions, 300 games

| model | best scale (cp per logistic unit) | 95% interval | log loss | 95% interval | beats the sum in |
|---|---|---|---|---|---|
| own | 1078 | 927..1254 | 0.5962 | 0.5768..0.6146 | 0.0% |
| partner | 1025 | 882..1193 | 0.5974 | 0.5768..0.6164 | 0.0% |
| sum | 1134 | 975..1319 | 0.5390 | 0.5099..0.5667 | - |
| smaller | 1078 | 882..1319 | 0.6030 | 0.5789..0.6281 | 0.0% |
| larger | 975 | 797..1254 | 0.5906 | 0.5601..0.6161 | 0.0% |
| mean | 560 | 482..685 | 0.5391 | 0.5099..0.5667 | 44.0% |
| min+max (two weights) | min x 0.845, max x 0.913 per 1000 cp (scales 1183 and 1095 cp) | min 0.676..1.056, max 0.731..1.141 | 0.5389 | 0.5087..0.5659 | 95.2% |

Log loss minus the sum's, x1000, resampled mean (95%): own +57.16 (+45.79..+69.81); partner +58.29 (+48.54..+70.44); smaller +64.29 (+42.73..+86.12); larger +50.37 (+28.38..+69.25); mean +0.00 (-0.03..+0.03); min+max -0.74 (-4.00..+0.01).

### all engines: 33130 paired decisions, 300 games

| model | best scale (cp per logistic unit) | 95% interval | log loss | 95% interval | beats the sum in |
|---|---|---|---|---|---|
| own | 1078 | 882..1254 | 0.5953 | 0.5696..0.6147 | 0.0% |
| partner | 1025 | 882..1254 | 0.6004 | 0.5748..0.6193 | 0.0% |
| sum | 1134 | 927..1387 | 0.5405 | 0.5063..0.5687 | - |
| smaller | 1025 | 838..1193 | 0.5960 | 0.5693..0.6153 | 0.0% |
| larger | 1078 | 882..1254 | 0.5995 | 0.5745..0.6184 | 0.0% |
| mean | 560 | 482..685 | 0.5405 | 0.5063..0.5687 | 49.2% |
| min+max (two weights) | min x 0.894, max x 0.848 per 1000 cp (scales 1119 and 1179 cp) | min 0.760..1.073, max 0.721..1.018 | 0.5404 | 0.5062..0.5686 | 95.8% |

Log loss minus the sum's, x1000, resampled mean (95%): own +55.19 (+44.33..+66.78); partner +60.21 (+50.26..+71.60); smaller +55.85 (+45.79..+66.96); larger +59.45 (+48.87..+70.67); mean +0.00 (-0.03..+0.03); min+max -0.07 (-0.18..+0.00).

### Direct comparison, candidates

| cell | paired decisions | games | team win rate | 95% interval | | other cell | paired decisions | games | team win rate | 95% interval | difference (first - second), 95% | first better in |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (+300, 0): one 200..400, other -100..100 | 757 | 215 | 53.9% | 45.4%..62.2% | | (+150, +150): both 50..250 | 505 | 154 | 50.2% | 40.7%..60.7% | +3.7 pts (-5.8..+12.6) | 78.2% |
| (+600, 0): one 500..700, other -100..100 | 258 | 111 | 71.7% | 60.7%..82.5% | | (+300, +300): both 200..400 | 256 | 106 | 61.3% | 50.2%..72.6% | +10.4 pts (-2.4..+23.5) | 93.6% |
| (0, -300): one -100..100, other -400..-200 | 686 | 197 | 42.0% | 33.5%..50.6% | | (-150, -150): both -250..-50 | 385 | 142 | 50.9% | 40.0%..60.9% | -8.9 pts (-18.2..+0.1) | 2.8% |

### Direct comparison, all engines

| cell | paired decisions | games | team win rate | 95% interval | | other cell | paired decisions | games | team win rate | 95% interval | difference (first - second), 95% | first better in |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (+300, 0): one 200..400, other -100..100 | 1474 | 270 | 55.5% | 50.3%..60.5% | | (+150, +150): both 50..250 | 935 | 225 | 52.0% | 45.8%..59.2% | +3.5 pts (-3.4..+10.3) | 83.6% |
| (+600, 0): one 500..700, other -100..100 | 536 | 201 | 70.8% | 63.8%..76.2% | | (+300, +300): both 200..400 | 495 | 167 | 59.0% | 48.9%..67.7% | +11.8 pts (+1.4..+21.1) | 98.6% |
| (0, -300): one -100..100, other -400..-200 | 1440 | 270 | 42.6% | 37.3%..48.3% | | (-150, -150): both -250..-50 | 808 | 225 | 49.6% | 42.5%..56.5% | -6.9 pts (-13.7..+0.1) | 3.0% |

