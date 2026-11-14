/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <deque>
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
  for (size_t k = 0; k < pv.size() && int(k) < int(Options["HBForecastScan"]); ++k)
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
          int& lp = (ours ? later.plyUs : later.plyThem)[t];
          if (lp < 0)
              lp = int(k);
          if (int(k) < Coef::ForecastPlies)
          {
              ++(ours ? a.us : a.them)[t];
              int& ap = (ours ? a.plyUs : a.plyThem)[t];
              if (ap < 0)
                  ap = int(k);
          }
      }
      uci.push_back(UCI::move(p, m));
      states->emplace_back();
      p.do_move(m, states->back());
  }
  return a;
}

// ---- Minimal Talk (HBTell=minimal, PARTNER_TALK.md): the partner's own lines

bool mode_has(const std::string& mode, const char* name) {
  std::istringstream ss(mode);
  std::string part;
  while (std::getline(ss, part, '+'))
      if (part == name)
          return true;
  return false;
}

/// The part of a partner's message that Minimal Talk reads:
///   v1 n=<n> at=<a> d=<depth> score=<cp> mate=<plies> hands=<white>/<black> ... lines <w>:<m>,<m>,... <w>:...
/// at: plies played on the teller's board before the first move of every
/// line. score and mate are the first line's, from the teller's side at that
/// point. hands: both hands on its board at that point, as TeamState::pocket.
struct ToldLines {
  int at = -1, depth = 0, score = 0, mate = 0;
  bool hasHands = false;
  std::string hands[COLOR_NB];
  std::vector<std::pair<int, std::vector<std::string>>> lines;
};

bool told_int(const std::string& s, int& out) {
  if (s.empty())
      return false;
  char* end = nullptr;
  long v = std::strtol(s.c_str(), &end, 10);
  if (end == s.c_str() || *end != '\0')
      return false;
  out = int(std::clamp(v, -1000000L, 1000000L));
  return true;
}

bool parse_told(const std::string& text, ToldLines& t) {
  std::istringstream ss(text);
  std::string tok;
  if (!(ss >> tok) || tok != "v1")
      return false;
  bool inLines = false;
  while (ss >> tok)
  {
      if (tok == "worth" || tok == "plan" || tok == "menu" || tok == "odds" || tok == "lines")
      {
          inLines = tok == "lines";
          continue;
      }
      if (inLines)
      {
          size_t colon = tok.find(':');
          int w = 0;
          if (colon == std::string::npos || !told_int(tok.substr(0, colon), w) || w <= 0)
              continue;
          std::vector<std::string> moves;
          std::istringstream ms(tok.substr(colon + 1));
          std::string m;
          while (std::getline(ms, m, ','))
              if (!m.empty())
                  moves.push_back(m);
          if (!moves.empty())
              t.lines.emplace_back(w, moves);
      }
      else if (tok.rfind("at=", 0) == 0)
          told_int(tok.substr(3), t.at);
      else if (tok.rfind("d=", 0) == 0)
          told_int(tok.substr(2), t.depth);
      else if (tok.rfind("score=", 0) == 0)
          told_int(tok.substr(6), t.score);
      else if (tok.rfind("mate=", 0) == 0)
          told_int(tok.substr(5), t.mate);
      else if (tok.rfind("hands=", 0) == 0)
      {
          const std::string h = tok.substr(6);
          size_t slash = h.find('/');
          if (slash != std::string::npos)
          {
              t.hands[WHITE] = h.substr(0, slash);
              t.hands[BLACK] = h.substr(slash + 1);
              t.hasHands = true;
          }
      }
  }
  return true;
}

/// The lines of the partner's message that still fit the partner board: the
/// moves played there since are a line's first moves, and the hands there
/// are what the partner searched with, less what was dropped since. Each
/// keeps the weight it was told with. False, with the reason in why, when
/// the message cannot be used.
bool told_lines(CoordinatorContext& ctx, bool moverIsPartner, std::vector<ForecastLine>& out,
                int& depth, std::string& why) {
  const int Y = 1 - ctx.board;
  const Position& py = ctx.actual.pos(Y);
  const Color partner = ~ctx.us;
  std::string text = std::string(Options["HBPartnerTell"]);
  ToldLines t;
  if (text == "none")
      return why = "none", false;
  if (!parse_told(text, t) || t.at < 0 || !t.hasHands || t.lines.empty())
      return why = "no_lines", false;

  std::vector<std::string> played;
  for (const auto& m : ctx.actual.move_list())
      if (m.first == Y)
          played.push_back(m.second);
  const int skip = int(played.size()) - t.at;
  if (skip < 0)
      return why = "stale", false;

  // A capture on our board since the partner searched has changed a hand on
  // its board: its lines are about a position that is gone.
  std::string hands[COLOR_NB] = { t.hands[WHITE], t.hands[BLACK] };
  Color mover = py.side_to_move();
  for (int j = 1; j <= skip; ++j)
  {
      mover = ~mover;
      const std::string& mv = played[played.size() - j];
      if (mv.size() > 1 && mv[1] == '@')
      {
          size_t k = hands[mover].find(char(std::toupper(static_cast<unsigned char>(mv[0]))));
          if (k == std::string::npos)
              return why = "hands", false;
          hands[mover].erase(k, 1);
      }
  }
  if (hands[WHITE] != ctx.actual.pocket(Y, WHITE) || hands[BLACK] != ctx.actual.pocket(Y, BLACK))
      return why = "hands", false;

  const int sign = moverIsPartner ? 1 : -1;   // told scores are the partner's
  for (size_t i = 0; i < t.lines.size(); ++i)
  {
      const std::vector<std::string>& mv = t.lines[i].second;
      if (int(mv.size()) <= skip)
          continue;
      bool same = true;
      for (int j = 0; j < skip; ++j)
          same = same && mv[j] == played[t.at + j];
      if (!same)
          continue;
      StateListPtr states(new std::deque<StateInfo>(1));
      Position p;
      p.set(py.variant(), py.fen(), false, &states->back(), py.this_thread());
      std::vector<Move> pv;
      for (size_t k = skip; k < mv.size(); ++k)
      {
          std::string s = mv[k];
          Move m = UCI::to_move(p, s);
          if (m == MOVE_NONE)
              break;
          pv.push_back(m);
          states->emplace_back();
          p.do_move(m, states->back());
      }
      if (pv.empty())
          continue;
      ForecastLine l;
      l.move = UCI::move(py, pv[0]);
      l.source = "told";
      l.score = std::clamp(sign * t.score, -Coef::FiniteCap, Coef::FiniteCap);
      // The mate was counted from the first told move: the moves played
      // since have used up that many plies of it. Only the first line's.
      if (i == 0 && t.mate != 0)
      {
          int left = std::max(1, std::abs(t.mate) - skip);
          l.mate = sign * (t.mate > 0 ? left : -left);
      }
      l.arrival = read_line(py, pv, partner, l.pv, l.captures, l.later);
      l.weight = t.lines[i].first;
      l.fixed = true;
      out.push_back(l);
  }
  if (out.empty())
      return why = "reply", false;
  depth = t.depth;
  return true;
}

} // namespace

// ------------------------------------------------------------------ Arrival

Arrival::Arrival() {
  for (int t = 0; t < PIECE_TYPE_NB; ++t)
      plyUs[t] = plyThem[t] = -1;
}

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
  if (!talk.empty())
      ss << ",\"talk\":\"" << talk << "\"";
  ss << ",\"mover\":\"" << (moverIsPartner ? "partner" : "opponent") << "\""
     << ",\"depth\":" << depth << ",\"team_mate\":" << teamMate << ",\"lines\":[";
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
  // Fixed lines are the partner's own and came with their share. The lines
  // of our search divide what is left by their scores.
  double best = -1e18, fixedSum = 0, softSum = 0;
  std::vector<double> adjusted;
  for (auto& l : f.lines)
  {
      int ours = 0, theirs = 0;
      for (PieceType t : Types)
          ours += l.arrival.us[t] * price(true, t), theirs += l.arrival.them[t] * price(false, t);
      l.gain = f.moverIsPartner ? ours - theirs : theirs - ours;
      adjusted.push_back(l.score + priceWeight * l.gain);
      if (l.fixed)
          fixedSum += l.weight;
      else
          best = std::max(best, adjusted.back());
  }
  for (size_t i = 0; i < f.lines.size(); ++i)
      if (!f.lines[i].fixed)
      {
          f.lines[i].weight = std::exp((adjusted[i] - best) / std::max(1.0, tempCp));
          softSum += f.lines[i].weight;
      }
  // With no line of our own the fixed ones are the whole forecast.
  const double fixedShare = softSum > 0 ? std::min(fixedSum, 1.0) : 1.0;
  for (auto& l : f.lines)
      l.weight = l.fixed ? l.weight / fixedSum * fixedShare : l.weight / softSum * (1.0 - fixedShare);
  const double total = 1.0;
  std::map<std::string, World> byKey;
  for (auto& l : f.lines)
  {
      l.weight /= total;
      // Captures deeper in a line are believed less. A line with both splits:
      // everything arrives, only the early part arrives, or nothing does.
      bool deeper = l.later.count() > l.arrival.count();
      // A told line's later captures can be believed less than our own
      // lines' (HBPlanTrustLate): stated at 0.31 they came within four plies
      // 22 times in 100, and the switches they alone caused lost 45 cp each
      // in hindsight (EXPERIMENTS.md, plan-vs-l50).
      const int planLate = int(Options["HBPlanTrustLate"]);
      const double lineLate = l.fixed && planLate >= 0 ? double(planLate) / 100.0 : trustLate;
      double late = deeper ? std::min(lineLate, trust) : 0.0;
      // Lines with the same package can differ in when it comes: the world
      // takes the timing of the line that adds most to it (the first on a tie).
      auto add = [&](const Arrival& a, double share) {
          World& w = byKey[a.key()];
          if (w.p == 0 || share > w.top)
              w.arrival = a, w.top = share;
          w.p += share;
      };
      if (deeper && late > 0)
          add(l.later, l.weight * late);
      if (!l.arrival.empty())
          add(l.arrival, l.weight * (trust - late));
  }
  std::vector<World> packages;
  for (const auto& kv : byKey)
      if (kv.second.p >= Coef::MinWorldP)
          packages.push_back(kv.second);
  std::stable_sort(packages.begin(), packages.end(), [](const World& a, const World& b) {
      return a.p != b.p ? a.p > b.p : a.arrival.key() < b.arrival.key();
  });
  const int maxWorlds = int(Options["HBMaxWorlds"]);
  if (int(packages.size()) > maxWorlds - 1)
      packages.resize(maxWorlds - 1);
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
          l.mate = mate_plies(r.lines[i].second);
          l.arrival = read_line(py, r.linePvs[i], partner, l.pv, l.captures, l.later);
          f.lines.push_back(l);
      }
  };

  // ---- Minimal Talk: the partner has searched that board with most of its
  // go and said what it found. When that still fits, nothing is searched
  // here: not its board, and not the prices that weigh our own guesses.
  const std::string tellMode = std::string(Options["HBTell"]);
  std::vector<ForecastLine> told;
  int toldDepth = 0;
  if (mode_has(tellMode, "minimal"))
  {
      std::string whyNot;
      if (told_lines(ctx, f.moverIsPartner, told, toldDepth, whyNot))
      {
          f.lines = told;
          f.depth = toldDepth;
          int tm = f.lines[0].mate;
          f.teamMate = f.moverIsPartner ? tm : -tm;
          f.talk = "told";
          f.ready = true;
          weigh(f, double(int(Options["HBForecastTemp"])), double(int(Options["HBForecastTrust"])) / 100.0,
                double(int(Options["HBForecastTrustLate"])) / 100.0, double(int(Options["HBForecastPrice"])) / 100.0);
          return f;
      }
      f.talk = "own_" + whyNot;
  }

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
  if (!f.lines.empty())
  {
      // The first line is the mover's best: a mate there is forced.
      int m = f.lines[0].mate;
      f.teamMate = f.moverIsPartner ? m : -m;
  }

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

  // ---- Plan (HBTell=plan): we search broadly for what can arrive; the
  // partner has searched narrowly for its best move, far deeper. Its line
  // for the move it decided joins ours with a fixed share of the weight: as
  // measured, that line's next move is the one played 62 times in 100, the
  // first line of our own search 46 times.
  if (mode_has(tellMode, "plan"))
  {
      std::string whyNot;
      if (told_lines(ctx, f.moverIsPartner, told, toldDepth, whyNot))
      {
          told[0].weight = double(int(Options["HBPlanTrust"])) / 100.0;
          told[0].mate = 0;        // mates and the partner's score stay our own search's
          f.lines.push_back(told[0]);
          f.talk = "plan";
      }
      else
          f.talk = "own_" + whyNot;
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
