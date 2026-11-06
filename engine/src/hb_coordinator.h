/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

// Team-aware move selection (PLAN.md section 5). This is a STUB: it returns
// the main-search move. Candidate discovery, simulated hands, probe scoring
// and voluntary waiting are to be implemented on top of this interface.

#ifndef HB_COORDINATOR_H_INCLUDED
#define HB_COORDINATOR_H_INCLUDED

#include <string>

#include "hb_probe.h"
#include "hb_team_state.h"

namespace Stockfish::HB {

class DecisionLog;

/// What the controller returns for one 'go'.
struct Decision {
  Move move = MOVE_NONE;   // our seat's move; MOVE_NONE with pass=true sits
  bool pass = false;
  int  wakeAfterMs = 0;    // >0 with pass: emit 'info string hb_wake_after_ms=N'
  std::string reason;      // short token for hb_summary
};

/// Everything the coordinator may use. The actual state is const: build
/// scenarios on TeamState copies (TeamState copy is deep and isolated).
struct CoordinatorContext {
  const TeamState& actual;
  Seat seat;
  Color team;              // seat_team(seat)
  int board;               // our board
  Color us;                // our colour on our board
  bool advantage[COLOR_NB];      // time advantage per team (ours from TimeAdvantage)
  bool advantageKnown[COLOR_NB]; // false: assumed (no Clocks supplied)
  bool clocksKnown;
  int  clocksMs[4];        // aW, aB, bW, bB when clocksKnown
  const Verdict& verdict;  // root verdict of the actual state
  const ProbeResult& main; // main search on our board (already charged to budget)
  Move fallback;           // deterministic legal fallback (always legal)
  Budget& budget;          // shared go budget; use phases DISCOVERY/PROBES
  ChildWorker& worker;     // sequential child searches: worker.run(req, budget, &log)
  DecisionLog& log;
};

/// Choose our move. Must return a legal move of ctx.actual.pos(ctx.board)
/// or a pass. The controller re-checks legality and falls back if needed.
Decision coordinate(CoordinatorContext& ctx);

} // namespace Stockfish::HB

#endif // #ifndef HB_COORDINATOR_H_INCLUDED
