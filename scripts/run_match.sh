#!/usr/bin/env bash
# A version-against-version match through the bughouse arena, at low priority.
#
#   scripts/run_match.sh NAME CONTENDER_SPEC BASELINE_SPEC [PAIRS] [CONCURRENCY] [OPENINGS]
#
# A spec is the arena's engine spec without kind and net, e.g.
#   "bin=bin/hypebeast-v5,nodes=500000,name=v5"
# Node budgets keep each side's strength the same on a busy machine; the game
# clock is virtual. Output goes to logs/NAME and logs/NAME.log. Run again with
# the same arguments to continue an interrupted match.
set -uo pipefail
HB=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ARENA=${ARENA:-$HOME/Projects/Chess-Auto-Prep}
NAME=${1:?usage: run_match.sh NAME CONTENDER_SPEC BASELINE_SPEC [PAIRS] [CONCURRENCY] [OPENINGS]}
CONTENDER=${2:?contender spec}
BASELINE=${3:?baseline spec}
PAIRS=${4:-50}
CONCURRENCY=${5:-8}
OPENINGS=${6:-$HB/openings/dev100.txt}
NET=${HB_NET:-$HB/nets/bughouse-cd8cceab93fe.nnue}
OUT=$HB/logs/$NAME
abs() { sed -E "s#(^|,)bin=([^/,][^,]*)#\1bin=$HB/\2#" <<<"$1"; }
args=(--fixed-sample --openings "$OPENINGS" --pairs "$PAIRS" --concurrency "$CONCURRENCY"
      --engine-logs --search-timeout "${SEARCH_TIMEOUT:-300}"
      --contender "hypebeast,net=$NET,$(abs "$CONTENDER")"
      --baseline "hypebeast,net=$NET,$(abs "$BASELINE")"
      --output "$OUT")
[[ -f $OUT/results.jsonl ]] && args+=(--resume)
mkdir -p "$HB/logs"
cd "$ARENA/tools" || exit 2
date >>"$OUT.log"
nice -n 19 python3 -u -m bughouse_arena "${args[@]}" >>"$OUT.log" 2>&1
status=$?
echo "exit=$status" >>"$OUT.log"
date >>"$OUT.log"
# Every decision beside what happened next: postmortem.jsonl and postmortem.md
[[ $status -eq 0 ]] && nice -n 19 python3 "$HB/scripts/postmortem.py" "$OUT" >/dev/null 2>>"$OUT.log"
exit "$status"
