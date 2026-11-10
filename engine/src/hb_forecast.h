/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

// Arrival forecast (v4). A short multi-line search of the partner board says
// which captures are likely there in the next move or two. Each line's
// captures are a package of pieces arriving on our board, for us and for our
// opponent. Lines are weighted by score, the packages become "worlds" with
// probabilities, and the coordinator searches our board once per world.

#ifndef HB_FORECAST_H_INCLUDED
#define HB_FORECAST_H_INCLUDED

#include <string>
#include <vector>

#include "types.h"

namespace Stockfish::HB {

struct CoordinatorContext;

/// Pieces reaching our board from the partner board.
struct Arrival {
  int us[PIECE_TYPE_NB] = {};     // into our hand (our partner captured them)
  int them[PIECE_TYPE_NB] = {};   // into our opponent's hand
  bool empty() const;
  int count() const;
  // "none", or e.g. "+N" (we get a knight), "-Q" (they get a queen), "+N-B"
  std::string key() const;
};

/// One line of the partner-board search.
struct ForecastLine {
  std::string move;               // root move on the partner board
  std::string source;             // "top" (best lines) or "capture" (searched on request)
  std::vector<std::string> pv;    // the plies that were read
  std::vector<std::string> captures; // every capture in them: "<ply><+|-><type>", e.g. "0-N", "3+Q"
  int score = 0;                  // cp for the side to move there
  int gain = 0;                   // what the line's captures are worth on our board, same side
  Arrival arrival;                // captures in the first plies: arriving soon
  Arrival later;                  // every capture read, including those
  double weight = 0;              // share of the forecast, before trust
};

struct World {
  Arrival arrival;
  double p = 0;
};

struct Forecast {
  bool ready = false;             // a partner-board search completed
  std::string why;                // reason when not ready
  bool moverIsPartner = false;    // who is on turn on the partner board
  int depth = 0;
  std::vector<ForecastLine> lines;
  // What one arriving piece is worth on our board (cp, >= 0), measured by
  // paired searches; -1 where it was not needed or not measured.
  int priceUs[PIECE_TYPE_NB];
  int priceThem[PIECE_TYPE_NB];
  std::vector<World> worlds;      // [0] is always "nothing arrives"

  Forecast();
  std::string json() const;
};

/// Runs the partner-board searches and the price probes on our board, then
/// weighs the lines. Uses the DISCOVERY phase of the go budget.
Forecast make_forecast(CoordinatorContext& ctx);

/// (Re)computes line weights and worlds from scores, gains and prices.
/// tempCp: softmax temperature; trust: share of a soon arrival believed (0..1);
/// trustLate: the same for captures deeper in a line; priceWeight: how much of
/// the cross-board gain counts in a line's score.
void weigh(Forecast& f, double tempCp, double trust, double trustLate, double priceWeight);

} // namespace Stockfish::HB

#endif // #ifndef HB_FORECAST_H_INCLUDED
