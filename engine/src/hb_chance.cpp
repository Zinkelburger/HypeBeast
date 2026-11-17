/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

#include <cmath>
#include <sstream>

#include "hb_chance.h"
#include "hb_forecast.h"
#include "misc.h"
#include "uci.h"

namespace Stockfish::HB::Chance {

Table T;
bool Planned = false;
bool Active = false;
Key PlyKey[MaxPlies + 1];
Key ExtKey[MaxExtension + 1];

namespace {

const PieceType Types[] = { QUEEN, ROOK, BISHOP, KNIGHT, PAWN };
constexpr double Cap = 0.95;

char type_char(PieceType pt) {
  return pt == PAWN ? 'P' : pt == KNIGHT ? 'N' : pt == BISHOP ? 'B' : pt == ROOK ? 'R' : pt == QUEEN ? 'Q' : '?';
}

struct KeyInit {
  KeyInit() {
    PRNG rng(0x48424368616e6365ULL);   // "HBChance"
    for (int i = 0; i <= MaxPlies; ++i)
        PlyKey[i] = rng.rand<Key>();
    for (int i = 0; i <= MaxExtension; ++i)
        ExtKey[i] = rng.rand<Key>();
  }
} keyInit;

double win(Value v) {
  if (v >= VALUE_MATE_IN_MAX_PLY)
      return 1.0;
  if (v <= VALUE_MATED_IN_MAX_PLY)
      return 0.0;
  double cp = double(v) * 100.0 / double(PawnValueEg);
  return 1.0 / (1.0 + std::exp(-cp / T.winScale));
}

void clear_table() {
  for (int s = 0; s < 2; ++s)
      for (int t = 0; t < PIECE_TYPE_NB; ++t)
          T.p[s][t][0] = T.p[s][t][1] = 0.0;
}

} // namespace

Value mix(double p, Value vd, Value vno) {
  if (vd <= vno)
      return vno;
  double wd = win(vd), wn = win(vno);
  // Both mates for the mover, or both mated: the winning chance is the same
  // either way, so the drop changes nothing.
  if (wn >= 1.0 || wd <= 0.0)
      return vno;
  double w = p * wd + (1.0 - p) * wn;
  if (w <= wn)
      return vno;
  w = std::clamp(w, 1e-12, 1.0 - 1e-12);
  double cp = T.winScale * std::log(w / (1.0 - w));
  const double lim = double(VALUE_TB_WIN_IN_MAX_PLY - 1);
  Value r = Value(std::lround(std::clamp(cp * double(PawnValueEg) / 100.0, -lim, lim)));
  return std::max(r, vno);
}

Value threshold(double p, Value vno, Value target) {
  Value lo = vno + 1, hi = VALUE_MATE;
  if (lo > hi || mix(p, hi, vno) <= target)
      return VALUE_NONE;
  // mix() is non-decreasing in vd: find the smallest vd with mix > target
  while (lo < hi)
  {
      Value mid = Value(int(lo) + (int(hi) - int(lo)) / 2);
      if (mix(p, mid, vno) > target)
          hi = mid;
      else
          lo = mid + 1;
  }
  return lo;
}

void read_options() {
  T.plies = std::clamp(int(Options["HBChancePlies"]), 1, MaxPlies);
  T.minP = double(int(Options["HBChanceMinP"])) / 100.0;
  T.maxCands = int(Options["HBChanceMaxCands"]);
  T.maxPerLine = int(Options["HBChanceMaxPerLine"]);
  T.winScale = double(int(Options["HBWinScale"]));
  T.horizon = int(Options["HBChanceHorizon"]);
  T.stable = bool(Options["HBChanceStable"]);
  T.aspiration = bool(Options["HBChanceAspiration"]);
  T.condition = bool(Options["HBChanceCondition"]);
  T.hold = bool(Options["HBChanceHold"]);
}

Calibration read_calibration() {
  Calibration c;
  const char* who[2] = { "Us", "Them" };
  for (int s = 0; s < 2; ++s)
  {
      std::string w = who[s];
      c.trust0[s] = double(int(Options["HBChanceTrust" + w + "0"])) / 100.0;
      c.floor0[s] = double(int(Options["HBChanceFloor" + w + "0"])) / 10000.0;
      c.trust1[s] = double(int(Options["HBChanceTrust" + w + "1"])) / 100.0;
      c.late1[s]  = double(int(Options["HBChanceLate" + w + "1"])) / 100.0;
      c.floor1[s] = double(int(Options["HBChanceFloor" + w + "1"])) / 10000.0;
  }
  return c;
}

void build(const Forecast& f, Color us, const Calibration& c, const bool present[2][PIECE_TYPE_NB]) {
  clear_table();
  T.root = us;
  T.source = "forecast";
  for (int s = 0; s < 2; ++s)
      for (PieceType t : Types)
      {
          double early = 0, late = 0;
          for (const auto& l : f.lines)
          {
              int soon = s ? l.arrival.them[t] : l.arrival.us[t];
              int all  = s ? l.later.them[t]   : l.later.us[t];
              if (soon > 0)
                  early += l.weight;
              else if (all > 0)
                  late += l.weight;
          }
          // A type the giving side cannot capture there gets no floor (a
          // capture in a forecast line implies the type is present).
          double f0 = present[s][t] ? c.floor0[s] : 0.0;
          double f1 = present[s][t] ? c.floor1[s] : 0.0;
          double p0 = std::min(Cap, f0 + (1.0 - f0) * std::min(1.0, c.trust0[s] * early));
          double p1 = std::min(Cap, f1 + (1.0 - f1) * std::min(1.0, c.trust1[s] * early + c.late1[s] * late));
          T.p[s][t][0] = p0;
          T.p[s][t][1] = std::max(p0, p1);
      }
}

bool parse(const std::string& text, Color us, std::string& err) {
  clear_table();
  T.root = us;
  T.source = "injected";
  std::string s = text;
  for (char& ch : s)
      if (ch == ',' || ch == ';')
          ch = ' ';
  std::istringstream ss(s);
  std::string tok;
  while (ss >> tok)
  {
      // e.g. +N=90/90
      size_t eq = tok.find('='), slash = tok.find('/');
      if (tok.size() < 5 || (tok[0] != '+' && tok[0] != '-') || eq != 2 || slash == std::string::npos)
      {
          err = "bad_entry " + tok;
          return false;
      }
      PieceType t = NO_PIECE_TYPE;
      for (PieceType c : Types)
          if (type_char(c) == char(toupper(tok[1])))
              t = c;
      if (t == NO_PIECE_TYPE)
      {
          err = "bad_piece " + tok;
          return false;
      }
      int a = std::atoi(tok.substr(eq + 1, slash - eq - 1).c_str());
      int b = std::atoi(tok.substr(slash + 1).c_str());
      int side = tok[0] == '+' ? 0 : 1;
      T.p[side][t][0] = std::min(Cap, std::clamp(a, 0, 100) / 100.0);
      T.p[side][t][1] = std::min(Cap, std::max(std::clamp(a, 0, 100), std::clamp(b, 0, 100)) / 100.0);
  }
  return true;
}

std::string json() {
  std::ostringstream ss;
  ss << "{\"source\":\"" << T.source << "\",\"plies\":" << T.plies
     << ",\"min\":" << T.minP << ",\"cands\":" << T.maxCands
     << ",\"per_line\":" << T.maxPerLine;
  if (T.condition)
      ss << ",\"condition\":1";
  if (T.hold)
      ss << ",\"hold\":1";
  ss << ",\"p\":{";
  bool first = true;
  for (int s = 0; s < 2; ++s)
      for (PieceType t : Types)
      {
          if (T.p[s][t][0] <= 0 && T.p[s][t][1] <= 0)
              continue;
          ss << (first ? "" : ",") << "\"" << (s ? '-' : '+') << type_char(t) << "\":["
             << std::lround(T.p[s][t][0] * 1000) / 1000.0 << ","
             << std::lround(T.p[s][t][1] * 1000) / 1000.0 << "]";
          first = false;
      }
  ss << "}}";
  return ss.str();
}

} // namespace Stockfish::HB::Chance
