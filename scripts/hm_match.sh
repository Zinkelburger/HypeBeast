#!/usr/bin/env bash
# HypeBeast against HiveMind CPU on the screen20 openings, through the bughouse
# arena, without the 2-CPU job runner.
#
#   scripts/hm_match.sh BINSPEC [PAIRS] [HM_NODES] [HB_NODES]
#
#   e.g. scripts/hm_match.sh "bin=$PWD/bin/hypebeast-base" 10 1500 4500000
#        scripts/hm_match.sh "bin=$PWD/bin/hypebeast-chance,HBChance=true,name=chance" 10
#
# BINSPEC is an arena hypebeast spec without the kind: bin=PATH, any
# Option=value (sent with setoption), and optionally name= and nodes= or
# movetime=. A bare word is taken as a binary in bin/ (hypebeast-v4) or a path.
# Defaults: PAIRS 10, HM_NODES 1500, HB_NODES 4,500,000 (the mean of what v4
# searched in 9652 ms, PLAN rev 9). HiveMind gets nodes=HM_NODES. Both sides
# search a node budget, so neither gets weaker when the machine is busy; the
# game clock is virtual (1.5-2.5 s per move whatever the search took).
#
# Output: logs/NAME-vs-hm-n<HM_NODES>/ with engine logs, and NAME-...log beside
# it, where NAME is name= from the spec or the binary's basename (hypebeast-
# prefix dropped). Run the same command again to continue: --resume is added
# when results exist.
#
# Environment:
#   CONCURRENCY  games at once (default 2; see below)
#   CPUS         taskset CPU list for the whole match (default 0-11; empty: no pinning)
#   SEARCH_TIMEOUT  hard per-search limit in s (default 300)
#   OPENINGS     opening file (default the arena's screen20.txt)
#   HIVEMIND_BIN/HIVEMIND_MODEL/HIVEMIND_LIB  the HiveMind build; default the
#                pinned engine-v0.2.0 bundle unpacked in upstream/hivemind
#                (same SHA-256 as the app's copy), else whatever the arena finds
#   EXTRA_ARGS   appended to the arena command
#
# Threads (measured 2026-11-14, Ryzen AI 9 HX PRO 370, 12 cores / 24 threads):
# the shipped HiveMind runs 4 search workers and sizes ONNX Runtime's intra-op
# pool as hardware_concurrency / 4 = 6 threads each, ignoring
# HIVEMIND_ORT_THREADS and CPU affinity, so the arena's --ort-threads has no
# effect on it. One HiveMind search therefore wants the whole machine; CPUS
# confines the match to a CPU set instead. HiveMind speed pinned to CPUs 0-11
# (one thread on each of the 12 cores), preflight middlegames, warm process:
#
#   budget  processes searching at once  s/search  nodes/s per search  total nodes/s
#     400            1                     2.1         216 (444 nodes done)   202
#    1500            1                     5.6         274                  267
#    5000            1                    18.4         274                  272
#    1500            2                    11.1         139                  272
#    1500            3                    20.6          75                  217
#    1500            4                    28.3          54                  210
#    1500   1, CPUs 0-5,12-17 (6 cores)    7.1         217
#
# HiveMind's throughput is fixed by the cores: two searches at once share it
# evenly, three or more lose about 20% to oversubscription (24 ORT threads per
# process). In a match only the seat on turn searches and half the decisions
# are HypeBeast's (single-threaded, about 10 s at 4.5M nodes), so CONCURRENCY
# 2-3 keeps the cores busy. First run, CONCURRENCY 3 on CPUs 0-11: base at
# 4.5M nodes against HiveMind at 1500, 10 pairs, 6729 s wall (336 s per game
# of throughput; a game took 525-1857 s, mean 955); HypeBeast searches
# averaged 9.4 s (p95 16.5 s), HiveMind's 15.7 s (p95 26.5 s, max 62 s), so
# the 300 s default SEARCH_TIMEOUT has a wide margin. The node count is
# the same at any load (1540 for 1500) and the source (agent.cc) bounds the
# root mate pre-pass by nodes, with a deadline only under movetime, so its
# strength does not depend on load. Its search is multi-threaded and not
# bit-exact, so repeated games are not move-for-move repeats.
set -uo pipefail
HB=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SPEC=${1:?usage: hm_match.sh BINSPEC [PAIRS] [HM_NODES] [HB_NODES]}
PAIRS=${2:-10}
HM_NODES=${3:-1500}
HB_NODES=${4:-4500000}
CONCURRENCY=${CONCURRENCY:-2}
CPUS=${CPUS-0-11}
SEARCH_TIMEOUT=${SEARCH_TIMEOUT:-300}
export HYPEBEAST_HOME=${HYPEBEAST_HOME:-$HB}
TOOLS=${ARENA_TOOLS:-${HB_ARENA_TOOLS:-$HB/upstream/cap-dev/tools}}
OPENINGS=${OPENINGS:-$TOOLS/bughouse_arena/opening_sets/screen20.txt}

if [[ -z ${HIVEMIND_BIN:-} && -x $HB/upstream/hivemind/hivemind-linux ]]; then
  export HIVEMIND_BIN=$HB/upstream/hivemind/hivemind-linux
  export HIVEMIND_MODEL=$HB/upstream/hivemind/hivemind.onnx
  export HIVEMIND_LIB=$HB/upstream/hivemind
fi

# A bare word is a binary.
if [[ $SPEC != *=* ]]; then
  if [[ -x $HB/bin/$SPEC ]]; then SPEC="bin=$HB/bin/$SPEC"; else SPEC="bin=$SPEC"; fi
fi
SPEC=${SPEC#hypebeast,}
bin=$(tr ',' '\n' <<<"$SPEC" | sed -n 's/^bin=//p')
bin=${bin:-$HYPEBEAST_HOME/bin/hypebeast}
[[ -x $bin ]] || { echo "not executable: $bin" >&2; exit 2; }
name=$(tr ',' '\n' <<<"$SPEC" | sed -n 's/^name=//p')
if [[ -z $name ]]; then
  name=$(basename "$bin"); name=${name#hypebeast-}
  SPEC+=",name=hb-$name"
else
  name=${name#hb-}
fi
[[ ,$SPEC, == *,nodes=* || ,$SPEC, == *,movetime=* ]] || SPEC+=",nodes=$HB_NODES"

OUT=$HB/logs/$name-vs-hm-n$HM_NODES
LOG=$OUT.log
mkdir -p "$HB/logs"
args=(--fixed-sample --openings "$OPENINGS" --pairs "$PAIRS"
      --concurrency "$CONCURRENCY" --engine-logs --search-timeout "$SEARCH_TIMEOUT"
      --contender "hypebeast,$SPEC"
      --baseline "hivemind,nodes=$HM_NODES,name=hm-n$HM_NODES"
      --output "$OUT")
[[ -f $OUT/results.jsonl ]] && args+=(--resume)
# shellcheck disable=SC2206
[[ -n ${EXTRA_ARGS:-} ]] && args+=($EXTRA_ARGS)
pin=()
[[ -n $CPUS ]] && pin=(taskset -c "$CPUS")

export PYTHONUNBUFFERED=1   # progress lines reach the log as games finish
cd "$TOOLS" || exit 2
echo "=== $(date -Is) ${pin[*]} python3 -m bughouse_arena ${args[*]}" >>"$LOG"
start=$(date +%s)
"${pin[@]}" python3 -m bughouse_arena "${args[@]}" 2>&1 | tee -a "$LOG"
status=${PIPESTATUS[0]}
echo "=== exit=$status wall=$(( $(date +%s) - start ))s $(date -Is)" | tee -a "$LOG"
exit "$status"
