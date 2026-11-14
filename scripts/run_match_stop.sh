#!/usr/bin/env bash
# scripts/run_match.sh with an early stop for a clear loser.
#
#   scripts/run_match_stop.sh NAME CONTENDER_SPEC BASELINE_SPEC [PAIRS] [CONCURRENCY] [OPENINGS]
#
# After STOP_AFTER games (default 30) the match is stopped when the contender's
# share of the decided games is at or below STOP_BELOW percent (default 33), and
# the post-mortem is run on what was played. A match that is not stopped ends as
# run_match.sh ends it. The arena runs in its own process group so that a stop
# takes its engines with it.
set -uo pipefail
HB=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
NAME=${1:?usage: run_match_stop.sh NAME CONTENDER_SPEC BASELINE_SPEC [PAIRS] [CONCURRENCY] [OPENINGS]}
STOP_AFTER=${STOP_AFTER:-30}
STOP_BELOW=${STOP_BELOW:-33}
LOG=$HB/logs/$NAME.log
setsid "$HB/scripts/run_match.sh" "$@" &
pid=$!
while kill -0 "$pid" 2>/dev/null; do
  sleep 20
  line=$(grep -E '^game [0-9]+/' "$LOG" 2>/dev/null | tail -1)
  [[ $line =~ \|\ \+([0-9]+)\ -([0-9]+)\ = ]] || continue
  w=${BASH_REMATCH[1]}; l=${BASH_REMATCH[2]}
  if (( w + l >= STOP_AFTER && w * 100 <= STOP_BELOW * (w + l) )); then
    echo "stopped early at +$w -$l (at or below $STOP_BELOW% after $STOP_AFTER games)" >>"$LOG"
    kill -- -"$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    nice -n 19 python3 "$HB/scripts/postmortem.py" "$HB/logs/$NAME" >/dev/null 2>>"$LOG"
    echo "stopped early: +$w -$l"
    exit 3
  fi
done
wait "$pid"
