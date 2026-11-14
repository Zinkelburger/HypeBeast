#!/bin/sh
# The whole autopsy2 pass on the finished match, one script at a time, at the lowest priority.
cd "$(dirname "$0")" || exit 1
set -e
nice -n 19 python3 common2.py plan-vs-l50
nice -n 19 python3 classify2.py plan-vs-l50 > /dev/null
nice -n 19 python3 losses_q3.py plan-vs-l50 > q3_plan-vs-l50.txt
nice -n 19 python3 visibility.py plan-vs-l50 > collapses_plan-vs-l50.txt
nice -n 19 python3 sides.py plan-vs-l50 --worlds > sides_plan-vs-l50.txt
nice -n 19 python3 gen_table2.py plan-vs-l50 > table_plan-vs-l50.md
nice -n 19 python3 calib2.py > calib_plan-vs-l50.txt
nice -n 19 python3 calib2.py --more > calib_more.txt
echo done
