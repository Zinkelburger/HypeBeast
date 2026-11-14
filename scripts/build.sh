#!/usr/bin/env bash
# Build the engine as it stands in engine/src and keep it as bin/NAME.
#
#   scripts/build.sh hypebeast-v8h
#
# Not beside a match: put it on a line of logs/queue.txt, or run it when
# `pgrep -fa "[b]ughouse_arena"` shows nothing. Log: logs/build-NAME.log
set -uo pipefail
HB=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
NAME=${1:?usage: build.sh NAME   (kept as bin/NAME)}
[[ -e $HB/bin/$NAME ]] && { echo "bin/$NAME exists: binaries are never overwritten" >&2; exit 2; }
if pgrep -f "[b]ughouse_arena" >/dev/null; then echo "a match is running: not building" >&2; exit 1; fi
cd "$HB/engine/src" || exit 2
nice -n 10 make -j8 build ARCH=x86-64-bmi2 COMP=gcc >"$HB/logs/build-$NAME.log" 2>&1 || { echo "build failed: logs/build-$NAME.log"; tail -15 "$HB/logs/build-$NAME.log"; exit 1; }
cp stockfish "$HB/bin/$NAME" && echo "built bin/$NAME sha256 $(sha256sum "$HB/bin/$NAME" | cut -c1-16)..."
