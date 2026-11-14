#!/bin/bash
# AUTOPSY3: rebuild every output from the match logs. Logs only, one niced Python process at a time.
set -e
cd "$(dirname "$0")"
for m in plan-vs-l50 plan-vs-l50-b plan-c kd60-vs-l50 matefree matekeep guardfloor-vs-l50; do
  [ -e cache_$m.pkl ] || nice -n 19 python3 common3.py $m
done
nice -n 19 python3 falls.py                                   # falls_l50.json (the six hb-l50 matches)
nice -n 19 python3 report3.py falls_l50.json > /dev/null      # report3_l50.md, classes_l50.txt
nice -n 19 python3 hazard3.py > /dev/null                     # hazard_l50.txt
nice -n 19 python3 partner_net.py > /dev/null                 # partner_net.txt
nice -n 19 python3 trades.py > /dev/null                      # trades.txt
nice -n 19 python3 partner_switch.py > /dev/null              # partner_switch.txt
nice -n 19 python3 partner_alt.py > /dev/null                 # partner_alt.txt
nice -n 19 python3 examples.py > /dev/null                    # examples.md
# cross-check: both sides of guardfloor-vs-l50
nice -n 19 python3 falls.py hb-guardfloor guardfloor-vs-l50
nice -n 19 python3 falls.py hb-l50 guardfloor-vs-l50
nice -n 19 python3 report3.py falls_guardfloor_guardfloor-vs-l50.json > /dev/null
nice -n 19 python3 report3.py falls_l50_guardfloor-vs-l50.json > /dev/null
# replication and cross-check on guardfloor-b (300 new games)
[ -e cache_guardfloor-b.pkl ] || nice -n 19 python3 common3.py guardfloor-b
nice -n 19 python3 falls.py hb-guardfloor guardfloor-b
nice -n 19 python3 falls.py hb-l50 guardfloor-b
nice -n 19 python3 report3.py falls_l50_guardfloor-b.json > /dev/null
nice -n 19 python3 guardstats.py guardfloor-vs-l50 guard-vs-l50 guardfloor-b > guardstats.txt
# item 3: where two matches with the same baseline part
nice -n 19 python3 diverge.py guardfloor-vs-l50 guard-vs-l50 > /dev/null
nice -n 19 python3 diverge.py guardfloor-vs-l50 matekeep > /dev/null
nice -n 19 python3 diverge.py guardfloor-vs-l50 matefree > /dev/null
# item 3 proper: guardfloor-b against guardnone-b (04:20)
[ -e cache_guardnone-b.pkl ] || nice -n 19 python3 common3.py guardnone-b
nice -n 19 python3 diverge.py guardfloor-b guardnone-b > /dev/null
nice -n 19 python3 guardstats.py guardnone-b > guardstats_guardnone-b.txt
nice -n 19 python3 falls.py hb-guardnone guardnone-b
nice -n 19 python3 falls.py hb-l50 guardnone-b
rm -f samepos.txt; nice -n 19 python3 samepos.py guardnone-b guardfloor-b > /dev/null
# worth-b (07:21)
[ -e cache_worth-b.pkl ] || nice -n 19 python3 common3.py worth-b
nice -n 19 python3 guardstats.py worth-b > guardstats_worth-b.txt
nice -n 19 python3 samepos.py worth-b > /dev/null
nice -n 19 python3 worth.py worth-b > /dev/null
# guardquiet-b (09:15)
[ -e cache_guardquiet-b.pkl ] || nice -n 19 python3 common3.py guardquiet-b
nice -n 19 python3 guardstats.py guardquiet-b > guardstats_guardquiet-b.txt
nice -n 19 python3 diverge.py guardfloor-b guardquiet-b > /dev/null
nice -n 19 python3 diverge.py guardquiet-b guardnone-b > /dev/null
nice -n 19 python3 samepos.py guardquiet-b > /dev/null
# feed-b (09:50, stopped at 96 games)
[ -e cache_feed-b.pkl ] || nice -n 19 python3 common3.py feed-b
nice -n 19 python3 worth.py feed-b > /dev/null
nice -n 19 python3 samepos.py feed-b > /dev/null
