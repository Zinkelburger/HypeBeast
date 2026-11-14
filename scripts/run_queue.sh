#!/usr/bin/env bash
# Run the commands of a queue file one after another, one match at a time.
#
#   scripts/run_queue.sh [QUEUE_FILE]        (default logs/queue.txt)
#
# Each line of the file that is not blank or a # comment is one command, run from
# the project directory once no arena is running. A finished line is written to
# QUEUE_FILE.done and never run again, so lines can be added to the file while
# the queue runs, and the queue can be started again after an interruption.
# To stop after the match now playing: touch logs/queue.stop
# The queue stops by itself when a command fails (an early stop of a losing
# contender, exit 3, is not a failure). Progress: logs/queue.log
set -uo pipefail
HB=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
Q=${1:-$HB/logs/queue.txt}
DONE=$Q.done
LOG=$HB/logs/queue.log
touch "$DONE"
say() { echo "$(date '+%m-%d %H:%M') $*" | tee -a "$LOG"; }
wait_idle() {   # no arena for a full minute: the last match's post-mortem has finished too
  local quiet=0
  while (( quiet < 3 )); do
    if pgrep -f "[b]ughouse_arena" >/dev/null || pgrep -f "[p]ostmortem.py" >/dev/null; then quiet=0; else (( quiet++ )); fi
    sleep 20
  done
}
while :; do
  [[ -e $HB/logs/queue.stop ]] && { say "logs/queue.stop is there: stopped"; exit 0; }
  line=$(grep -v '^[[:space:]]*#' "$Q" | grep -v '^[[:space:]]*$' | grep -vxFf "$DONE" | head -1)
  [[ -z $line ]] && { say "queue finished"; exit 0; }
  wait_idle
  [[ -e $HB/logs/queue.stop ]] && { say "logs/queue.stop is there: stopped"; exit 0; }
  say "START $line"
  (cd "$HB" && bash -c "$line") >>"$LOG" 2>&1
  status=$?
  echo "$line" >>"$DONE"
  say "END exit=$status"
  if (( status != 0 && status != 3 )); then say "that command failed: queue stopped"; exit "$status"; fi
done
