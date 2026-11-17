#!/usr/bin/env bash
# A/B two HypeBeast configurations through the bughouse arena at a node budget.
#
#   scripts/ab_match.sh NAME SPEC_A SPEC_B [PAIRS] [NODES] [CONCURRENCY]
#
#   e.g. scripts/ab_match.sh chance-vs-base \
#          "bin=$PWD/bin/hypebeast-chance,HBChance=true" "bin=$PWD/bin/hypebeast-base"
#
# SPEC_A (the contender) and SPEC_B (the baseline) are arena hypebeast specs
# without the kind: bin=PATH (default $HYPEBEAST_HOME/bin/hypebeast), net=PATH,
# name=LABEL, and any Option=value, which is sent with setoption. A spec gets
# nodes=NODES unless it gives nodes= or movetime= itself, and name=NAME-a /
# NAME-b unless it gives a name.
#
# Defaults: PAIRS 50, NODES 500000, CONCURRENCY 8. Openings are the first
# PAIRS lines of openings/dev100.txt, each played twice with teams swapped,
# --fixed-sample (pair-aware Wilson interval, no SPRT). Output goes to
# logs/NAME (results.jsonl, summary.json, games.bpgn, manifest.json) and the
# arena's own log to logs/NAME.log. Run the same command again to continue
# an interrupted match: --resume is added when logs/NAME/results.jsonl exists
# (the arena refuses if a binary, net, opening file or clock changed).
#
# Environment: ENGINE_LOGS=1 adds --engine-logs (each process's UCI traffic,
# including hb_forecast/hb_summary, in logs/NAME/engine_logs; about 30 MB per
# game pair at 500k nodes). SEARCH_TIMEOUT (seconds) overrides the per-search
# hard limit, ARENA_TOOLS the arena checkout's tools/ directory,
# OPENINGS the opening file, and EXTRA_ARGS is appended to the arena command.
#
# Concurrency, measured 2026-11-14 on this machine (Ryzen AI 9 HX PRO 370,
# 12 cores / 24 threads, 58 GB): HypeBeast is single-threaded and a game has
# one search running at a time, so a game keeps about one core busy and
# CONCURRENCY N uses about N cores. With node budgets the moves do not depend
# on load: the first 3 pairs replayed at concurrency 2 gave the same move
# lists, events and clocks as at concurrency 12. Load changes only the wall
# time: at 500k nodes a search averaged 665 ms at concurrency 2 and 893 ms
# (median 915, p95 1153, max 2759) at concurrency 12, so 50 pairs take about
# 14 minutes at 12. Recommended: CONCURRENCY 12 on an otherwise idle machine
# (one game per physical core), 8 when sharing it; going past 12 puts two
# searches on one core's SMT threads and buys little.
#
# Memory limits concurrency before the cores do. A game runs four HypeBeast
# processes of 280-420 MB each (256 MB hash in HypeBeast mode, cleared and so
# touched every go), about 1.5 GB per game. Sessions started from the desktop
# terminal share one cgroup capped at 16 GiB (memory.max of the konsole
# scope's parent): on 2026-11-14 an 11-game run next to another agent's
# matches hit it, and the OOM killer took 198 engine processes (theirs too),
# voiding 82 of the games. Check
#   cat /sys/fs/cgroup$(dirname $(cut -d: -f3 /proc/self/cgroup))/memory.{max,current}
# and keep CONCURRENCY * 1.5 GB inside the headroom. The arena's search
# limit (120 s for node budgets) is more than 40x the slowest 500k search
# seen; SEARCH_TIMEOUT defaults to 120 s below 2M nodes and 300 s at or above.
#
# A deterministic engine at a node budget plays both games of a pair as exact
# mirrors when SPEC_A and SPEC_B are the same, so base against base scores
# exactly 1-1 on every pair (50 of 50 at 500k nodes). That is not a noise
# floor for an A/B: once A and B differ the games diverge, and the arena's
# pair-level interval on the A/B itself is the error bar to read.
set -uo pipefail
HB=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
usage="usage: ab_match.sh NAME SPEC_A SPEC_B [PAIRS] [NODES] [CONCURRENCY]"
NAME=${1:?$usage}
SPEC_A=${2:?$usage}
SPEC_B=${3:?$usage}
PAIRS=${4:-50}
NODES=${5:-500000}
CONCURRENCY=${6:-8}
export HYPEBEAST_HOME=${HYPEBEAST_HOME:-$HB}
TOOLS=${ARENA_TOOLS:-${HB_ARENA_TOOLS:-$HB/upstream/cap-dev/tools}}
OPENINGS=${OPENINGS:-$HB/openings/dev100.txt}
if [[ -z ${SEARCH_TIMEOUT:-} ]]; then
  if (( NODES >= 2000000 )); then SEARCH_TIMEOUT=300; else SEARCH_TIMEOUT=120; fi
fi

[[ $NAME =~ ^[A-Za-z0-9._-]+$ ]] || { echo "NAME must be [A-Za-z0-9._-]+" >&2; exit 2; }
[[ -d $TOOLS/bughouse_arena ]] || { echo "no arena in $TOOLS" >&2; exit 2; }

# spec SPEC LABEL -> full arena spec
spec() {
  local s=$1 label=$2 out=hypebeast
  [[ $s == hypebeast,* ]] && s=${s#hypebeast,}
  [[ -n $s ]] && out+=",$s"
  [[ ,$s, == *,nodes=* || ,$s, == *,movetime=* ]] || out+=",nodes=$NODES"
  [[ ,$s, == *,name=* ]] || out+=",name=$label"
  printf '%s' "$out"
}
for s in "$SPEC_A" "$SPEC_B"; do
  bin=$(tr ',' '\n' <<<"$s" | sed -n 's/^bin=//p')
  bin=${bin:-$HYPEBEAST_HOME/bin/hypebeast}
  [[ -x $bin ]] || { echo "not executable: $bin" >&2; exit 2; }
done

OUT=$HB/logs/$NAME
LOG=$HB/logs/$NAME.log
mkdir -p "$HB/logs"
args=(--fixed-sample --openings "$OPENINGS" --pairs "$PAIRS"
      --concurrency "$CONCURRENCY" --search-timeout "$SEARCH_TIMEOUT"
      --contender "$(spec "$SPEC_A" "$NAME-a")"
      --baseline "$(spec "$SPEC_B" "$NAME-b")"
      --output "$OUT")
[[ ${ENGINE_LOGS:-0} == 1 ]] && args+=(--engine-logs)
[[ -f $OUT/results.jsonl ]] && args+=(--resume)
# shellcheck disable=SC2206
[[ -n ${EXTRA_ARGS:-} ]] && args+=($EXTRA_ARGS)

export PYTHONUNBUFFERED=1   # progress lines reach the log as games finish
cd "$TOOLS" || exit 2
{ echo "=== $(date -Is) python3 -m bughouse_arena ${args[*]}"; } >>"$LOG"
start=$(date +%s)
python3 -m bughouse_arena "${args[@]}" 2>&1 | tee -a "$LOG"
status=${PIPESTATUS[0]}
echo "=== exit=$status wall=$(( $(date +%s) - start ))s $(date -Is)" | tee -a "$LOG"
exit "$status"
