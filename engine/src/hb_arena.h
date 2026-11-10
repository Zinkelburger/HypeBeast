/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

// UCI adapter for the bughouse arena (one process per seat). Active only
// with 'setoption name HypeBeast value true'; otherwise upstream UCI runs.
//
//   position startpos|fen <A>|<B> [moves 1e2e4 2d7d5 ...]
//   go nodes N | go movetime M        -> exactly one 'bestmove (moveA,moveB)'
//   hbstate                           -> one JSON line describing the actual state
//   hbmakeundo [iterations N] [plies P] [seed S]   (self-test)
//   hbprobe [nodes N|movetime M] [count K] [depth D] [clear 0|1] [fen F]  (self-test)
//   hbforecast [nodes N|movetime M]   -> the arrival forecast for the seat on turn
//   hbvalues board A|B [nodes N|movetime M]
//        -> 'info string hb_values {...}' per completed depth (3, 5, 7, ...),
//           then 'bestmove (none)': one more piece in hand, for each colour

#ifndef HB_ARENA_H_INCLUDED
#define HB_ARENA_H_INCLUDED

#include <sstream>

namespace Stockfish::HB::Arena {

bool enabled();
void on_hypebeast_option();

void position(std::istringstream& is);
void go(std::istringstream& is);
void stop();      // 'stop'/'quit': cancel the running controller
void wait();      // block until the running controller (if any) has answered
void new_game();
void hbstate(std::istringstream& is);
void hbmakeundo(std::istringstream& is);
void hbprobe(std::istringstream& is);
void hbforecast(std::istringstream& is);
void hbvalues(std::istringstream& is);
void shutdown();  // join controller and free the child worker

} // namespace Stockfish::HB::Arena

#endif // #ifndef HB_ARENA_H_INCLUDED
