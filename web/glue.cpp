// The browser build's input side: the page queues UCI commands and the net
// through two exported functions, and the engine's UCI loop reads them with
// js_getline() in place of std::getline(std::cin). Adapted from
// lichess-org/stockfish-web (src/glue.cpp, GPL-3.0).

#include "glue.hpp"

#include <iostream>
#include <string>

#include "evaluate.h"
#include "position.h"
#include "uci.h"
#include "nnue/nnue_architecture.h"
#include "nnue/evaluate_nnue.h"

namespace {

const std::string load_nnue_cmd(Command& cmd) {
  std::istream in(&cmd);
  if (Stockfish::Eval::NNUE::load_eval("", in))
      return "setoption name Use NNUE value true";
  std::cerr << "BAD_NNUE" << std::endl;
  return "setoption name Use NNUE value false";
}

CommandQueue inQ;

} // namespace

extern "C" {
  EMSCRIPTEN_KEEPALIVE void uci(const char* utf8) { inQ.push(Command(utf8)); }

  EMSCRIPTEN_KEEPALIVE void setNnueBuffer(char* buf, size_t sz, int index) {
    inQ.push(Command(buf, sz, index));
  }

  EMSCRIPTEN_KEEPALIVE const char* getRecommendedNnue(int) { return ""; }
}

std::string js_getline() {
  auto cmd = inQ.pop();
  if (cmd.type == cmd.UCI)
      return cmd.uci;
  if (cmd.type == cmd.NNUE && cmd.ptr)
      return load_nnue_cmd(cmd);
  return "";
}
