#!/usr/bin/env bash
# Build HypeBeast for the browser: web/dist/hypebeast.{js,wasm}.
#
# Needs Emscripten 5.0.7 (the version lichess-org/stockfish-web builds
# Fairy-Stockfish with). EMSDK points at an emsdk checkout; the default is
# build/emsdk in this repository. The flags are stockfish-web's: pthreads,
# 128-bit SIMD, no tablebases, the net handed over by the page.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
emsdk="${EMSDK:-$root/build/emsdk}"
# shellcheck disable=SC1091
source "$emsdk/emsdk_env.sh" >/dev/null 2>&1
want=5.0.7
have="$(emcc --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
[ "$have" = "$want" ] || { echo "emcc $have found, $want needed" >&2; exit 1; }

tb="${HB_TB--DNO_TABLEBASES}"
opt="${HB_OPT:--O3 -flto --closure=1}"
src="${HB_SRC:-$root/engine/src}"
obj="${HB_OBJ:-$root/build/web-obj}"
out="${HB_OUT:-$root/web/dist}"
mkdir -p "$obj" "$out"

srcs=$(cd "$src" && ls *.cpp nnue/*.cpp nnue/features/*.cpp syzygy/*.cpp | grep -v -e '^ffishjs.cpp$' -e '^pyffish.cpp$')

cat > "$obj/Makefile" <<MK
CXX = em++
CXX_FLAGS = $opt -DNDEBUG -I$src -pthread -msimd128 -mavx -fno-exceptions \\
	-DUSE_POPCNT -DUSE_SSE2 -DUSE_SSSE3 -DUSE_SSE41 -DNO_PREFETCH -DUSE_SLOPPY_ATOMICS \\
	-DNNUE_EMBEDDING_OFF -DNO_TABLEBASES -std=c++17
LD_FLAGS = -sENVIRONMENT=web,worker,node \\
	--pre-js=$root/web/initModule.js -sEXIT_RUNTIME -sEXPORT_ES6 -sEXPORT_NAME=HypeBeast \\
	-sEXPORTED_FUNCTIONS='[_malloc,_main]' -sEXPORTED_RUNTIME_METHODS='[stringToUTF8,UTF8ToString,HEAPU8]' \\
	-sINCOMING_MODULE_JS_API='[locateFile,print,printErr,wasmMemory,buffer,instantiateWasm,mainScriptUrlOrBlob,onExit]' \\
	-sINITIAL_MEMORY=64MB -sALLOW_MEMORY_GROWTH -sSTACK_SIZE=3MB -sSTRICT -sPROXY_TO_PTHREAD \\
	-sALLOW_BLOCKING_ON_MAIN_THREAD=0 -Wno-pthreads-mem-growth -sPTHREAD_POOL_SIZE=5 -sDEFAULT_PTHREAD_STACK_SIZE=4MB
SRCS = $(echo $srcs)
OBJS = \$(addprefix o/, \$(SRCS:.cpp=.o)) o/glue.o
DEPS = \$(OBJS:.o=.d)

hypebeast.js: \$(OBJS)
	\$(CXX) \$(CXX_FLAGS) \$(LD_FLAGS) \$(OBJS) -o hypebeast.js

\$(OBJS): Makefile

o/%.o: $src/%.cpp
	@mkdir -p \$(dir \$@)
	\$(CXX) \$(CXX_FLAGS) -MMD -MP -c \$< -o \$@

o/glue.o: $root/web/glue.cpp
	@mkdir -p o
	\$(CXX) \$(CXX_FLAGS) -MMD -MP -c \$< -o \$@

-include \$(DEPS)
MK

make -C "$obj" -j"$(nproc)"
cp "$obj/hypebeast.js" "$obj/hypebeast.wasm" "$out/"
sha256sum "$out/hypebeast.js" "$out/hypebeast.wasm"
