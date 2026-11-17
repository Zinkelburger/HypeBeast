/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

// Chance inside the tree. The forecast says how likely each piece type is to
// have arrived, for each side, by its first and second turn in the search.
// At search nodes in the first plies, after the real moves have been
// searched, the side to move may also drop a piece it does not have yet
// ("virtual drop", the hand count goes negative). The node's value is the
// probability-weighted mix, in winning chances, of the best virtual drop and
// the best real move. Only main-pool searches use it.
//
// HBChanceHold replaces the virtual drops: an arrival is resolved as a branch
// that puts the piece in the real pocket and searches the node again (drop
// it now or hold it for later plies), mixed with the real moves, which are
// the world where it did not arrive (conditioned as with HBChanceCondition).

#ifndef HB_CHANCE_H_INCLUDED
#define HB_CHANCE_H_INCLUDED

#include <string>

#include "types.h"

namespace Stockfish::HB {

struct Forecast;

namespace Chance {

constexpr int MaxPlies = 8;

struct Table {
  // p[s][t][k]: probability that a t has arrived for side s by its k-th turn
  // in the search. s = 0: the side to move at the root (our seat), 1: the
  // opponent on our board. k = 0: plies 1-2, k = 1: plies 3 and later.
  double p[2][PIECE_TYPE_NB][2] = {};
  Color root = WHITE;
  int plies = 4;            // search plies 1..plies where chance applies
  double minP = 0.05;       // a type below this is ignored
  int maxCands = 12;        // candidate squares per type and node
  int maxPerLine = 1;       // virtual pieces per side on one line
  int reduction = 2;        // first test of a drop at depth - 1 - reduction - depth / reductionDiv
  int reductionDiv = 6;
  double winScale = 1000;   // cp per logistic unit (HBWinScale)
  int horizon = 0;          // HBChanceHorizon: 0 plain plies, 1 checks and evasions do not count
  bool stable = false;      // HBChanceStable: no singular extension where the mover may drop an arrival
  bool aspiration = false;  // HBChanceAspiration: root window as wide as the last swing
  bool verify = false;      // HBChanceVerify: claims from failed-low real moves are re-searched
  bool condition = false;   // HBChanceCondition: a later chance after one not taken is conditional
  bool hold = false;        // HBChanceHold: an arrival goes to the real pocket, dropped now or held
  std::string source;       // "forecast" or "injected"
};

/// How forecast weights become probabilities, per receiver (0: us, 1: them):
///   k = 0: p = floor0 + (1 - floor0) * min(1, trust0 * W01)
///   k = 1: p = floor1 + (1 - floor1) * min(1, trust1 * W01 + late1 * W23)
/// W01: weight of forecast lines with that capture in partner plies 0-1;
/// W23: weight of lines with it only in plies 2-3 (tests/arrival_rates.py).
/// Floors apply only to types the giving side has on the partner board.
/// Defaults reproduce the first version (trust 85, late 25, floor 0).
struct Calibration {
  double trust0[2], floor0[2], trust1[2], late1[2], floor1[2];
};

/// The HBChance* calibration options.
Calibration read_calibration();

constexpr int MaxExtension = 6;   // HBChanceHorizon 1: plies of checks/evasions not counted

extern Table T;
extern bool Planned;        // this go's main-pool searches use chance
extern bool Active;         // set around each main-pool search (like FedActive)
extern Key PlyKey[MaxPlies + 1];
extern Key ExtKey[MaxExtension + 1];

/// TT context key of a node at chance ply `cply` with `ext` uncounted plies.
inline Key context_key(int cply, int ext) {
  return PlyKey[cply] ^ (ext ? ExtKey[ext] : 0);
}

/// The turn index k (0 or 1) of chance ply `ply` (>= 1).
inline int turn(int ply) {
  return std::min(1, std::max(0, (ply - 1) / 2));
}

/// HBChanceCondition: the chances already offered on a line. Each side
/// (0: root side, 1: opponent) and type P..Q has a 2-bit field: 0 none,
/// k + 1 the latest turn k at which that side could have dropped an arrival
/// of that type and played a real move instead. A real move there is the
/// world where the piece had not arrived, so a later chance for the same
/// side and type uses P(arrived by now | not by turn k).
inline int seen_shift(int side, PieceType pt) {
  return 2 * (side * 5 + int(pt) - int(PAWN));
}

/// A node's offers (fields k + 1 for its side to move) merged into the line
/// state it inherited. An offered field is always higher than the inherited
/// one (an equal or lower turn conditions to 0 and is never offered).
inline uint32_t merge_seen(uint32_t seen, uint32_t offer) {
  const uint32_t low = (offer | (offer >> 1)) & 0x55555u;
  return (seen & ~(low * 3)) | offer;
}

/// HBChanceHold: bit 20 + side of the line state is set once an arrival of
/// that side has been resolved as arrived on the line (the piece went to the
/// real pocket). It stays set after the piece is dropped, so the side gets no
/// second arrival on the line (one piece per side per line).
inline uint32_t arrived_bit(int side) {
  return 1u << (20 + side);
}

/// TT key of a line state (0 for none, so the option off keeps all keys).
inline Key seen_key(uint32_t seen) {
  if (!seen)
      return 0;
  Key z = Key(seen) + 0x48424368616e6365ULL;
  z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
  return z ^ (z >> 31);
}

/// Probability that a pt has arrived for side c at search ply `ply` (>= 1),
/// given the line state `seen` (HBChanceCondition): after a chance at turn j
/// that was not taken, (p_k - p_j) / (1 - p_j), and 0 if p_k <= p_j.
inline double prob(Color c, int ply, PieceType pt, uint32_t seen = 0) {
  const int s = c == T.root ? 0 : 1;
  if (seen & arrived_bit(s))
      return 0.0;
  const double p = T.p[s][pt][turn(ply)];
  const int j = int((seen >> seen_shift(s, pt)) & 3) - 1;
  if (j < 0)
      return p;
  const double q = T.p[s][pt][j];
  return p > q ? (p - q) / (1.0 - q) : 0.0;
}

/// The node value when a virtual drop worth vd (for the side to move) is
/// available with probability p and the best real move is worth vno: the
/// mix in winning-chance space, never below vno. A mate for the mover has
/// winning chance 1, being mated 0. The result stays inside the non-mate
/// range unless both inputs are mates.
Value mix(double p, Value vd, Value vno);

/// Smallest vd > vno with mix(p, vd, vno) > target, or VALUE_NONE if not
/// even a mate gets there.
Value threshold(double p, Value vno, Value target);

/// Builds the table from the forecast lines. present[s][t]: the side that
/// would capture for receiver s finds a t on the partner board.
void build(const Forecast& f, Color us, const Calibration& c, const bool present[2][PIECE_TYPE_NB]);

/// Parses a table given as text, e.g. "+N=90/90,-Q=0/80": side (+ us,
/// - opponent), piece letter, then the % for k = 0 and k = 1.
bool parse(const std::string& s, Color us, std::string& err);

/// Reads the HBChance* tunables (plies, min, candidates, per line, win scale).
void read_options();

std::string json();

} // namespace Chance
} // namespace Stockfish::HB

#endif // #ifndef HB_CHANCE_H_INCLUDED
