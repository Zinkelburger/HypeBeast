#!/usr/bin/env bash
# One feature on against the same engine with it off.
#
#   scripts/ab.sh NAME ON [BOTH]
#   scripts/ab.sh --list            the engine's switches and their defaults
#
# ON    options only the contender gets, e.g. "HBTell=plan" or "HBKingDanger=60,HBWinScale=1200"
# BOTH  options both sides get, e.g. "HBTell=plan" when ON is something on top of the plan
#
# Both sides start from BASE (below); an option named in ON or BOTH replaces the
# same option in BASE. Settings, as environment variables:
#   OPENINGS=dev100 | dev100b | dev200c | a path     (default dev100: its first PAIRS openings)
#   PAIRS=50   AT_ONCE=8   BIN=bin/hypebeast-v8g   NODES=500000   CONTENDER_NODES=...
#   DRY=1      print the command and stop
#
# Examples
#   scripts/ab.sh plan-c HBTell=plan                      # talking against not talking
#   OPENINGS=dev200c PAIRS=100 scripts/ab.sh plan-c HBTell=plan
#   scripts/ab.sh planlate HBPlanTrustLate=15 HBTell=plan # on top of the plan, both sides talk
#
# Output: logs/NAME, logs/NAME.log, and the pooled figures of scripts/pool.py.
# Refuses to start while another match is running (one match at a time).
set -uo pipefail
HB=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BIN=${BIN:-bin/hypebeast-v8g}
NODES=${NODES:-500000}
BASE=${BASE:-Hash=64,HBFeedPrices=false,HBForecastTrustLate=50}

if [[ ${1:-} == --list ]]; then
  printf 'uci\nquit\n' | "$HB/$BIN" | sed -n 's/^option name \(HB[A-Za-z]*\) type [a-z]* default \([^ ]*\).*/\1=\2/p' | column -c 110
  exit 0
fi
NAME=${1:?usage: ab.sh NAME ON [BOTH]   (ab.sh --list shows the switches)}
ON=${2:?the options to turn on for the contender, e.g. HBTell=plan}
BOTH=${3:-}
PAIRS=${PAIRS:-50}
AT_ONCE=${AT_ONCE:-8}
OPENINGS=${OPENINGS:-dev100}
[[ -f $OPENINGS ]] || OPENINGS=$HB/openings/$OPENINGS.txt
[[ -f $OPENINGS ]] || { echo "no opening set $OPENINGS" >&2; exit 2; }

# merge "a=1,b=2" lists: a later list's option replaces an earlier one's
merge() {
  local out="" item key
  local -A seen=()
  local all; IFS=, read -ra all <<<"$(IFS=,; echo "$*")"
  for (( i = ${#all[@]} - 1; i >= 0; i-- )); do
    item=${all[i]}; [[ -z $item ]] && continue
    key=${item%%=*}
    [[ -n ${seen[$key]:-} ]] && continue
    seen[$key]=1; out="$item${out:+,$out}"
  done
  echo "$out"
}
# every option must exist in the binary: a misspelt switch would silently test nothing
known=$(printf 'uci\nquit\n' | "$HB/$BIN" | sed -n 's/^option name \([^ ]*\) type.*/\1/p')
for item in $(tr , ' ' <<<"$BASE,$ON,$BOTH"); do
  grep -qx "${item%%=*}" <<<"$known" || { echo "$BIN has no option '${item%%=*}' (scripts/ab.sh --list)" >&2; exit 2; }
done
short=${NAME%%-vs-*}
contender="bin=$BIN,nodes=${CONTENDER_NODES:-$NODES},$(merge "$BASE" "$BOTH" "$ON"),name=hb-$short"
baseline="bin=$BIN,nodes=$NODES,$(merge "$BASE" "$BOTH"),name=hb-base"
cmd=(env "ARENA=${ARENA:-$HOME/.local/share/chess-prep/worktrees/hb-partner-tell}"
     "$HB/scripts/run_match_stop.sh" "$NAME" "$contender" "$baseline" "$PAIRS" "$AT_ONCE" "$OPENINGS")
echo "contender: $contender"
echo "baseline:  $baseline"
echo "openings:  $OPENINGS, $PAIRS pairs, $AT_ONCE games at once"
[[ -n ${DRY:-} ]] && { printf '%q ' "${cmd[@]}"; echo; exit 0; }
if running=$(pgrep -fa "[b]ughouse_arena" | head -1) && [[ -n $running ]]; then
  echo "a match is already running, not starting another:" >&2
  echo "  ${running:0:200}" >&2
  exit 1
fi
"${cmd[@]}"
status=$?
python3 "$HB/scripts/pool.py" "$HB/logs/$NAME"
exit "$status"
