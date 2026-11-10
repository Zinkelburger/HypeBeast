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

#include "hb_forecast.h"
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
  constexpr int    RCap              = 400;     // after halving: a threat, not a verdict
  constexpr int    RDiv              = 2;
  constexpr int    FCap              = 100;     // only without feed prices
  constexpr int    SwitchMargin      = 20;
  constexpr int    WaitMs            = 3000;
  constexpr int    WaitReserveMs     = 1000;
  constexpr int    SafetyCheckLimit  = 20000;   // positions in the waiting safety check

  // Feed prices: half the measured gain, because a piece in hand is not
  // always usable at once; a mate seen on the other board is priced apart.
  constexpr int    PriceDiv          = 2;
  constexpr int    PriceCap          = 500;
  constexpr int    MatePriceOurs     = 800;
  constexpr int    MatePriceTheirs   = 1500;
  constexpr int    PriceMinMs        = 500;     // shorter searches skip prices
  constexpr uint64_t PriceMinNodes   = 200000;

  // A soft warning only moves us if the safer move is about this close.
  constexpr int    SoftSwitchBound   = 600;

  // Stalling: our clock must beat the seat we would race on the other board.
  constexpr int    StallReserveMs    = 8000;
  constexpr int    StallLeadMs       = 500;
  constexpr int    StallPartnerMs    = 2500;    // extra lead while our partner must move first

  // Arrival forecast and worlds (v4). Shares are fractions of the whole go.
  constexpr int    ForecastLines         = 4;     // best partner-board lines read
  constexpr int    ForecastExtraCaptures = 4;     // captures outside them, searched on request
  constexpr int    ForecastPlies         = 2;     // plies of each line counted as arriving soon
  constexpr int    ForecastScanPlies     = 4;     // plies read and reported
  constexpr double ForecastShare         = 0.07;
  constexpr double ForecastCaptureShare  = 0.03;
  constexpr double ForecastPriceShare    = 0.03;
  constexpr Depth  ForecastPriceDepth    = 5;
  constexpr int    MaxWorlds             = 4;     // including "nothing arrives"
  constexpr double MinWorldP             = 0.04;  // rarer packages are folded into "nothing arrives"
  constexpr int    WorldMainCandidates   = 2;
  constexpr int    WorldDeliveries       = 1;
  constexpr double WorldOwnShare         = 0.30;  // of the budget left: each world's own best move
  constexpr double WorldScoreShare       = 0.40;  // of the budget left: scoring candidates in arrival worlds
  constexpr int    WorldSwitchMargin     = 25;    // cp-equivalent lead needed to replace the main choice
  constexpr size_t WorldHashMb           = 16;
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

/// What one more piece in hand is worth on one board, to each colour, for
/// display: the receiver's gain in centipawns from the receiver's side,
/// unhalved and uncapped, or a mate the piece makes possible. Read from
/// paired child searches (the position with and without the piece) at a
/// common depth.
struct PieceValues {
  int board = 0;
  Color stm = WHITE;            // side to move on that board
  Depth depth = 0;
  bool baseOk = false;
  int base = 0;                 // the board without extra pieces, White's view
  bool ok[COLOR_NB][PIECE_TYPE_NB] = {};
  bool mate[COLOR_NB][PIECE_TYPE_NB] = {};
  int gain[COLOR_NB][PIECE_TYPE_NB] = {};
  void set(Color receiver, PieceType t, int with, int without);  // both from the receiver's side
  std::string json(const char* source) const;
};

/// Measures PieceValues for `board` with 11 probes of `depth` plies (each
/// capped at maxNodes), charged to ctx.budget in the given phase.
PieceValues measure_piece_values(CoordinatorContext& ctx, int board, Depth depth,
                                 uint64_t maxNodes, Phase phase);

/// Before the main search: measure what each piece type is worth to each
/// team on the partner board, and install those prices for this go's
/// main-pool searches. Short searches skip this and use the F term instead.
void prepare_feed_prices(CoordinatorContext& ctx);

/// Before the main search (v4): forecast what arrives from the partner board.
/// Short searches skip this; coordinate() then uses the v3 rule.
void prepare_forecast(CoordinatorContext& ctx);

/// Choose our move after the main search. Returns a legal move of
/// ctx.actual.pos(ctx.board), or pass=true to stall. Uses the rest of the
/// go budget.
Decision coordinate(CoordinatorContext& ctx);

/// Voluntary waiting (PLAN.md 5.4), evaluated before any search when our
/// seat is on turn with legal moves. Returns pass=true (with wakeAfterMs)
/// to sit, otherwise pass=false. Keeps per-process wait state: at most one
/// 3000 ms wait per own-board turn, original expiry kept across wakes.
Decision consider_voluntary_wait(const CoordinatorContext& ctx);
void reset_wait_state();

} // namespace Stockfish::HB

#endif // #ifndef HB_COORDINATOR_H_INCLUDED
