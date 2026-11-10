/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

#include <algorithm>
#include <cmath>
#include <map>
#include <set>
#include <sstream>

#include "hb_coordinator.h"
#include "hb_decisionlog.h"
#include "hb_forecast.h"
#include "movegen.h"
#include "uci.h"

namespace Stockfish::HB {

namespace {

const PieceType Types[] = { QUEEN, ROOK, BISHOP, KNIGHT, PAWN };

char type_char(PieceType pt) {
  return pt == PAWN ? 'P' : pt == KNIGHT ? 'N' : pt == BISHOP ? 'B' : pt == ROOK ? 'R' : pt == QUEEN ? 'Q' : '?';
}

// Used when a price probe does not finish: roughly half a piece's board value.
int default_price(PieceType pt) {
  return pt == PAWN ? 40 : pt == KNIGHT ? 100 : pt == BISHOP ? 100 : pt == ROOK ? 130 : pt == QUEEN ? 200 : 0;
}

/// The captures in the first plies of a partner-board line, as an arrival on
/// our board. partner: our team's colour on the partner board.
Arrival read_line(const Position& root, const std::vector<Move>& pv, Color partner,
                  std::vector<std::string>& uci, std::vector<std::string>& captures, Arrival& later) {
  Arrival a;
  StateListPtr states(new std::deque<StateInfo>(1));
  Position p;
  p.set(root.variant(), root.fen(), false, &states->back(), root.this_thread());
  for (size_t k = 0; k < pv.size() && int(k) < Coef::ForecastScanPlies; ++k)
  {
      Move m = pv[k];
      if (!MoveList<LEGAL>(p).contains(m))
          break;
      PieceType t = TeamState::captured_type(p, m);
      if (t != NO_PIECE_TYPE)
      {
          bool ours = p.side_to_move() == partner;
          captures.push_back(std::to_string(k) + (ours ? '+' : '-') + type_char(t));
          ++(ours ? later.us : later.them)[t];
          if (int(k) < Coef::ForecastPlies)
              ++(ours ? a.us : a.them)[t];
      }
      uci.push_back(UCI::move(p, m));
      states->emplace_back();
      p.do_move(m, states->back());
  }
  return a;
}

} // namespace

// ------------------------------------------------------------------ Arrival

bool Arrival::empty() const { return count() == 0; }

int Arrival::count() const {
  int n = 0;
  for (PieceType t : Types)
      n += us[t] + them[t];
  return n;
}

std::string Arrival::key() const {
  std::string s;
  for (PieceType t : Types)
      for (int i = 0; i < us[t]; ++i)
          s += '+', s += type_char(t);
  for (PieceType t : Types)
      for (int i = 0; i < them[t]; ++i)
          s += '-', s += type_char(t);
  return s.empty() ? "none" : s;
}

// ----------------------------------------------------------------- Forecast

Forecast::Forecast() {
  for (int t = 0; t < PIECE_TYPE_NB; ++t)
      priceUs[t] = priceThem[t] = -1;
  worlds.push_back(World{Arrival(), 1.0});
}

std::string Forecast::json() const {
  std::ostringstream ss;
  ss << "{\"ready\":" << (ready ? "true" : "false");
  if (!why.empty())
      ss << ",\"why\":\"" << why << "\"";
  ss << ",\"mover\":\"" << (moverIsPartner ? "partner" : "opponent") << "\""
     << ",\"depth\":" << depth << ",\"lines\":[";
  for (size_t i = 0; i < lines.size(); ++i)
  {
      const ForecastLine& l = lines[i];
      ss << (i ? "," : "") << "{\"move\":\"" << l.move << "\",\"source\":\"" << l.source
         << "\",\"score\":" << l.score << ",\"gain\":" << l.gain
         << ",\"arrival\":\"" << l.arrival.key() << "\",\"later\":\"" << l.later.key()
         << "\",\"weight\":" << l.weight << ",\"pv\":[";
      for (size_t k = 0; k < l.pv.size(); ++k)
          ss << (k ? "," : "") << "\"" << l.pv[k] << "\"";
      ss << "],\"captures\":[";
      for (size_t k = 0; k < l.captures.size(); ++k)
          ss << (k ? "," : "") << "\"" << l.captures[k] << "\"";
      ss << "]}";
  }
  ss << "],\"prices\":{";
  bool first = true;
  for (int side = 0; side < 2; ++side)
      for (PieceType t : Types)
      {
          int v = side ? priceThem[t] : priceUs[t];
          if (v < 0)
              continue;
          ss << (first ? "" : ",") << "\"" << (side ? '-' : '+') << type_char(t) << "\":" << v;
          first = false;
      }
  ss << "},\"worlds\":[";
  for (size_t i = 0; i < worlds.size(); ++i)
      ss << (i ? "," : "") << "{\"arrival\":\"" << worlds[i].arrival.key() << "\",\"p\":" << worlds[i].p << "}";
  ss << "]}";
  return ss.str();
}

void weigh(Forecast& f, double tempCp, double trust, double trustLate, double priceWeight) {
  f.worlds.clear();
  f.worlds.push_back(World{Arrival(), 1.0});
  if (f.lines.empty())
      return;

  auto price = [&](bool ours, PieceType t) {
      int v = ours ? f.priceUs[t] : f.priceThem[t];
      return v >= 0 ? v : default_price(t);
  };
  // A capture helps the side that made it: the side to move there owns the
  // even plies, so its team's arrivals count for the line and the other
  // team's against it.
  double best = -1e18;
  std::vector<double> adjusted;
  for (auto& l : f.lines)
  {
      int ours = 0, theirs = 0;
      for (PieceType t : Types)
          ours += l.arrival.us[t] * price(true, t), theirs += l.arrival.them[t] * price(false, t);
      l.gain = f.moverIsPartner ? ours - theirs : theirs - ours;
      adjusted.push_back(l.score + priceWeight * l.gain);
      best = std::max(best, adjusted.back());
  }
  double total = 0;
  for (size_t i = 0; i < f.lines.size(); ++i)
  {
      f.lines[i].weight = std::exp((adjusted[i] - best) / std::max(1.0, tempCp));
      total += f.lines[i].weight;
  }
  std::map<std::string, World> byKey;
  for (auto& l : f.lines)
  {
      l.weight /= total;
      // Captures deeper in a line are believed less. A line with both splits:
      // everything arrives, only the early part arrives, or nothing does.
      bool deeper = l.later.count() > l.arrival.count();
      double late = deeper ? std::min(trustLate, trust) : 0.0;
      if (deeper && late > 0)
      {
          World& w = byKey[l.later.key()];
          w.arrival = l.later;
          w.p += l.weight * late;
      }
      if (!l.arrival.empty())
      {
          World& w = byKey[l.arrival.key()];
          w.arrival = l.arrival;
          w.p += l.weight * (trust - late);
      }
  }
  std::vector<World> packages;
  for (const auto& kv : byKey)
      if (kv.second.p >= Coef::MinWorldP)
          packages.push_back(kv.second);
  std::stable_sort(packages.begin(), packages.end(), [](const World& a, const World& b) {
      return a.p != b.p ? a.p > b.p : a.arrival.key() < b.arrival.key();
  });
  if (int(packages.size()) > Coef::MaxWorlds - 1)
      packages.resize(Coef::MaxWorlds - 1);
  double arriving = 0;
  for (const auto& w : packages)
      arriving += w.p, f.worlds.push_back(w);
  f.worlds[0].p = 1.0 - arriving;
}

Forecast make_forecast(CoordinatorContext& ctx) {
  Forecast f;
  const int X = ctx.board, Y = 1 - X;
  const Position& py = ctx.actual.pos(Y);
  const Position& px = ctx.actual.pos(X);
  const Color partner = ~ctx.us;
  Budget& b = ctx.budget;
  f.moverIsPartner = py.side_to_move() == partner;

  MoveList<LEGAL> legalY(py);
  if (!legalY.size())
  {
      f.why = "partner_board_no_moves";
      return f;
  }

  auto add_lines = [&](const ProbeResult& r, const std::string& source) {
      for (size_t i = 0; i < r.lines.size() && i < r.linePvs.size(); ++i)
      {
          if (r.lines[i].second == -VALUE_INFINITE || r.linePvs[i].empty())
              continue;
          ForecastLine l;
          l.move = UCI::move(py, r.lines[i].first);
          l.source = source;
          l.score = finite_cp(r.lines[i].second);
          l.arrival = read_line(py, r.linePvs[i], partner, l.pv, l.captures, l.later);
          f.lines.push_back(l);
      }
  };

  // ---- the partner board's best lines
  ProbeRequest req;
  req.fen = ctx.actual.fen(Y);
  req.phase = Phase::DISCOVERY;
  req.clear = true;
  req.multiPV = Coef::ForecastLines;
  req.maxNodes = b.share_nodes(Coef::ForecastShare);
  req.maxTimeMs = b.share_ms(Coef::ForecastShare);
  req.tag = "forecast";
  ProbeResult top = ctx.worker.run(req, b, &ctx.log);
  if (!top.usable_exact() || top.lines.empty())
  {
      f.why = std::string("forecast_") + status_name(top.status);
      return f;
  }
  f.depth = top.depth;
  add_lines(top, "top");

  // ---- captures outside those lines: poor on that board alone, but a
  // capture can be played for what the piece does on ours
  {
      struct Cap { Move m; int value; std::string uci; };
      std::vector<Cap> caps;
      for (const auto& mv : legalY)
      {
          PieceType t = TeamState::captured_type(py, mv);
          if (t == NO_PIECE_TYPE)
              continue;
          std::string uci = UCI::move(py, mv);
          bool known = false;
          for (const auto& l : f.lines)
              known |= l.move == uci;
          if (!known)
              caps.push_back(Cap{mv, int(PieceValue[MG][t]), uci});
      }
      std::stable_sort(caps.begin(), caps.end(), [](const Cap& a, const Cap& c) {
          return a.value != c.value ? a.value > c.value : a.uci < c.uci;
      });
      if (int(caps.size()) > Coef::ForecastExtraCaptures)
          caps.resize(Coef::ForecastExtraCaptures);
      if (!caps.empty())
      {
          ProbeRequest cr = req;
          cr.clear = false;
          cr.searchMoves.clear();
          for (const auto& c : caps)
              cr.searchMoves.push_back(c.uci);
          cr.multiPV = caps.size();
          cr.maxNodes = b.share_nodes(Coef::ForecastCaptureShare);
          cr.maxTimeMs = b.share_ms(Coef::ForecastCaptureShare);
          cr.tag = "forecast_captures";
          ProbeResult extra = ctx.worker.run(cr, b, &ctx.log);
          if (extra.usable_exact())
              add_lines(extra, "capture");
      }
  }

  // ---- what each arriving piece is worth on our board: the same position
  // searched with and without it. A piece of ours cannot be dropped on the
  // first move, because it has not arrived yet.
  std::set<PieceType> needUs, needThem;
  for (const auto& l : f.lines)
      for (PieceType t : Types)
      {
          if (l.arrival.us[t])   needUs.insert(t);
          if (l.arrival.them[t]) needThem.insert(t);
      }
  size_t probes = needUs.size() + needThem.size();
  if (probes)
  {
      std::vector<std::string> legalX;
      for (const auto& mv : MoveList<LEGAL>(px))
          legalX.push_back(UCI::move(px, mv));
      ProbeRequest pr;
      pr.phase = Phase::DISCOVERY;
      pr.depth = Coef::ForecastPriceDepth;
      pr.searchMoves = legalX;
      pr.maxNodes = b.share_nodes(Coef::ForecastPriceShare / double(probes + 1));
      pr.maxTimeMs = b.share_ms(Coef::ForecastPriceShare / double(probes + 1));
      auto value = [&](const std::string& fen, const std::string& tag, bool clear, int& out) {
          pr.fen = fen;
          pr.tag = tag;
          pr.clear = clear;
          ProbeResult r = ctx.worker.run(pr, b, &ctx.log);
          if (!r.usable_exact() || !r.reachedDepth)
              return false;
          out = finite_cp(r.score);   // our seat is to move at the root
          return true;
      };
      int v0;
      if (value(ctx.actual.fen(X), "price_base", false, v0))
          for (int side = 0; side < 2; ++side)
              for (PieceType t : side ? needThem : needUs)
              {
                  TeamState w;
                  w.assign_light(ctx.actual);
                  w.add_to_pocket(X, make_piece(side ? ~ctx.us : ctx.us, t));
                  int v;
                  if (value(w.fen(X), std::string(side ? "price_them_" : "price_us_") + type_char(t), false, v))
                      (side ? f.priceThem : f.priceUs)[t] = std::clamp(side ? v0 - v : v - v0, 0, Coef::FiniteCap);
              }
  }

  f.ready = true;
  weigh(f, double(int(Options["HBForecastTemp"])), double(int(Options["HBForecastTrust"])) / 100.0,
        double(int(Options["HBForecastTrustLate"])) / 100.0, double(int(Options["HBForecastPrice"])) / 100.0);
  return f;
}

} // namespace Stockfish::HB
