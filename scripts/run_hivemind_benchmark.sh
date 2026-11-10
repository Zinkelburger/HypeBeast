#!/usr/bin/env bash
# The HiveMind benchmark: a frozen HypeBeast binary against HiveMind CPU on the
# screen20 openings, through the bughouse arena in Chess-Auto-Prep.
#
#   scripts/run_hivemind_benchmark.sh BINARY [PAIRS]     e.g. hypebeast-v4 3
#
# HiveMind searches HM_NODES nodes a move (default 1500; 400 until 2026-11-10).
# The game clock is virtual: every move costs 1.5-2.5 s of clock whatever the
# search took, so the node budgets change how long the match takes to run and
# how strong each side is, never the clocks.
#
# HypeBeast searches HB_NODES nodes a move (default 4,500,000: the mean of what
# v4 searched in 9652 ms in logs/v4-vs-hivemind-screen5, 325 searches). A node
# budget keeps its strength the same when the machine is busy; a movetime does
# not. Set HB_MOVETIME (ms) to use a movetime instead, as the matches before
# 2026-11-10 did. The job is capped at 2 CPUs by the arena's job runner.
#
# Run again with the same arguments to continue an interrupted match. The log is
# logs/<name>-vs-hivemind-n<nodes>.log, the match directory the same without .log.
set -uo pipefail
HB=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ARENA=${ARENA:-$HOME/Projects/Chess-Auto-Prep}
BIN=${1:?usage: run_hivemind_benchmark.sh BINARY [PAIRS]}
PAIRS=${2:-3}
NODES=${HM_NODES:-1500}
if [[ -n ${HB_MOVETIME:-} ]]; then
  BUDGET=movetime=$HB_MOVETIME
else
  BUDGET=nodes=${HB_NODES:-4500000}
fi
# A 1500-node search takes about 36 s here and twice that on a busy machine;
# the arena's 120 s default for node budgets leaves little room.
TIMEOUT=${SEARCH_TIMEOUT:-300}
[[ -x $HB/bin/$BIN ]] || { echo "no binary $HB/bin/$BIN" >&2; exit 2; }
NAME=hb-${BIN#hypebeast-}
OUT=$HB/logs/${NAME#hb-}-vs-hivemind-n$NODES
LOG=$OUT.log
ATTEMPT=$(mktemp)
trap 'rm -f "$ATTEMPT"' EXIT

args=(--fixed-sample --openings bughouse_arena/opening_sets/screen20.txt
      --pairs "$PAIRS" --engine-logs --search-timeout "$TIMEOUT"
      --contender "hypebeast,bin=$HB/bin/$BIN,$BUDGET,name=$NAME"
      --baseline "hivemind,nodes=$NODES,name=hm-n$NODES"
      --output "$OUT")
[[ -f $OUT/results.jsonl ]] && args+=(--resume)

cd "$ARENA/tools" || exit 2
date >>"$LOG"
while :; do
  ../scripts/ci.sh with -- python3 -m bughouse_arena "${args[@]}" >"$ATTEMPT" 2>&1
  status=$?
  # Both job slots taken: the job gives up after two minutes. Keep asking.
  if grep -q 'Queue timeout' "$ATTEMPT" && ! grep -q '^agent-job: slot' "$ATTEMPT"; then
    sleep 60
    continue
  fi
  cat "$ATTEMPT" >>"$LOG"
  break
done
echo "exit=$status" >>"$LOG"
date >>"$LOG"
exit "$status"
