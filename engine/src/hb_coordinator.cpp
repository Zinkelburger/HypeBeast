/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

#include "hb_coordinator.h"
#include "hb_decisionlog.h"

namespace Stockfish::HB {

// STUB (PLAN.md section 9 step 3 is not implemented yet): keep the main
// search's move, or the deterministic fallback if the main search produced
// none. No child searches are run, so the unused budget is simply returned.
Decision coordinate(CoordinatorContext& ctx) {
  Decision d;
  if (ctx.main.status == ProbeResult::OK && ctx.main.finalMove != MOVE_NONE)
  {
      d.move = ctx.main.finalMove;
      d.reason = "main";
  }
  else
  {
      d.move = ctx.fallback;
      d.reason = "fallback";
  }
  ctx.log.set("coordinator", "stub");
  return d;
}

} // namespace Stockfish::HB
