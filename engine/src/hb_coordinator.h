/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

// Team-aware move selection (PLAN.md section 5): candidate discovery,
// simulated incoming hands, paired probes, the S rule, and bounded
// voluntary waiting.

#ifndef HB_COORDINATOR_H_INCLUDED
#define HB_COORDINATOR_H_INCLUDED

#include <string>

#include "hb_probe.h"
#include "hb_team_state.h"

namespace Stockfish::HB {

class DecisionLog;

// Frozen coefficients (PLAN.md 5.3/5.4) and engineering caps.
namespace Coef {
  constexpr int    MaxMainCandidates = 3;
  constexpr int    MaxDeliveries     = 2;
  constexpr Depth  ProbeDepth        = 3;       // local plies after the candidate, plus qsearch
  constexpr uint64_t ProbeNodeCap    = 100000;  // equal cap for every paired probe
  constexpr int    FiniteCap         = 2000;
  constexpr int    RCap              = 150;
  constexpr int    FCap              = 100;
  constexpr int    SwitchMargin      = 20;
  constexpr int    WaitMs            = 3000;
  constexpr int    WaitReserveMs     = 1000;
  constexpr int    SafetyCheckLimit  = 20000;   // positions in the waiting safety check
}

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
  Budget& budget;          // shared go budget; use phases DISCOVERY/PROBES/COMPARE
  ChildWorker& worker;     // sequential child searches: worker.run(req, budget, &log)
  DecisionLog& log;
};

/// Choose our move after the main search. Returns a legal move of
/// ctx.actual.pos(ctx.board). Uses the rest of the go budget.
Decision coordinate(CoordinatorContext& ctx);

/// Voluntary waiting (PLAN.md 5.4), evaluated before any search when our
/// seat is on turn with legal moves. Returns pass=true (with wakeAfterMs)
/// to sit, otherwise pass=false. Keeps per-process wait state: at most one
/// 3000 ms wait per own-board turn, original expiry kept across wakes.
Decision consider_voluntary_wait(const CoordinatorContext& ctx);
void reset_wait_state();

} // namespace Stockfish::HB

#endif // #ifndef HB_COORDINATOR_H_INCLUDED
