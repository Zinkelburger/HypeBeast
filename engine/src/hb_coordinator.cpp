/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

// Order of work inside one 'go':
//
//   feed prices (DISCOVERY)       -> what each piece type is worth to each team
//                                    on the partner board; the main search adds
//                                    this to the eval at every capture
//   main search (MAIN)            -> main choice M, root order
//   immediate team win check      -> referee on the concrete joint state
//   delivery win check            -> a capture that lets our partner mate at once
//   delivery candidates           -> up to 2 captures outside the root top 3
//   exposure tiers                -> SAFE, SOFT or CERTAIN for every candidate
//   local probes (PROBES)         -> P0 and one probe per distinct enemy arrival
//   comparison search (COMPARE)   -> root-restricted MultiPV over all candidates:
//                                    every L(m) at one common completed depth;
//                                    it absorbs all budget left over
//   tiers, then the S rule        -> a CERTAIN main choice is replaced or stalled;
//                                    a SOFT one yields to a close safe move;
//                                    otherwise replace M only by >= 20 cp
//
// When no comparison is possible (one candidate, or a required probe is
// missing) the leftover budget instead extends the main search (warm TT),
// whose move is played only if it completed at least the main depth.

#include <algorithm>
#include <cmath>
#include <map>
#include <set>
#include <sstream>

#include "hb_coordinator.h"
#include "hb_decisionlog.h"
#include "movegen.h"
#include "tt.h"
#include "uci.h"

namespace Stockfish::HB {

namespace {

const PieceType DeliveryTypes[] = { QUEEN, ROOK, BISHOP, KNIGHT, PAWN };

char type_char(PieceType pt) {
  return pt == PAWN ? 'P' : pt == KNIGHT ? 'N' : pt == BISHOP ? 'B' : pt == ROOK ? 'R' : pt == QUEEN ? 'Q' : '?';
}

/// Exact team-perspective value of a probe, finite()-clipped.
/// stm: side to move at the probe root; ours: our team's colour on that board.
bool team_value(const ProbeResult& r, Color stm, Color ours, int& out) {
  if (r.status == ProbeResult::NO_LEGAL_MOVES)
  {
      // Locally lost for the side to move (bughouse: mate and stalemate lose)
      out = stm == ours ? -Coef::FiniteCap : Coef::FiniteCap;
      return true;
  }
  if (!r.usable_exact() || !r.reachedDepth)
      return false;
  out = finite_cp(stm == ours ? r.score : -r.score);
  return true;
}

bool wins_now(TeamState& work, int board, Move m, Color team, const bool adv[], const bool known[]) {
  TeamUndo u = work.play_undoable(board, m);
  Color opp = ~team;
  // sim.terminal() checks the team on move on the board just moved first:
  // that is the opponent, so their mate is our win.
  bool win = known[opp] ? work.is_checkmate(opp, adv[opp])
                        : work.is_checkmate(opp, false) && work.is_checkmate(opp, true);
  work.undo(u);
  return win;
}

int mvv_lva(const Position& pos, Move m) {
  PieceType captured = TeamState::captured_type(pos, m);
  return int(PieceValue[MG][captured]) * 16 - int(PieceValue[MG][type_of(pos.moved_piece(m))]) / 16;
}

struct Scenario {
  Piece arrival = NO_PIECE;              // NO_PIECE: no-arrival scenario
  std::vector<std::string> donors;       // provenance (partner-board captures)
  std::string fen;
  int value = 0;
  bool done = false;
};

struct Candidate {
  Move move = MOVE_NONE;
  std::string uci, source;
  PieceType delivery = NO_PIECE_TYPE;    // demoted type sent to the partner
  bool mating = false, blocking = false;
  bool enemyDonor = false;
  int friendlyScenarios = 0, enemyCaptures = 0;
  std::vector<Scenario> scen;            // [0] = no-arrival when enemy scenarios exist
  bool hasL = false, hasR = false, hasF = false;
  int L = 0, R = 0, F = 0, S = 0;
  double E = 0;                          // v4: weighted winning chances over the worlds
  int tier = 0;                          // SAFE, SOFT or CERTAIN
  bool probeFatal = false;               // a probe scored an enemy arrival as mate
  std::string exposure;
};

struct ProbeCache {
  std::map<std::string, ProbeResult> results;
  int requested = 0, run = 0;
  const ProbeResult& get(CoordinatorContext& ctx, const std::string& fen, Phase phase, const std::string& tag) {
      auto it = results.find(fen);
      ++requested;
      if (it != results.end() && it->second.status != ProbeResult::NO_BUDGET && it->second.status != ProbeResult::CANCELLED)
          return it->second;
      ProbeRequest req;
      req.fen = fen;
      req.depth = Coef::ProbeDepth;
      req.maxNodes = Coef::ProbeNodeCap;
      req.phase = phase;
      // One clean start per go is enough: later probes differ in board or
      // hand, so they cannot read each other's table entries.
      req.clear = run == 0 || !bool(Options["HBWorlds"]);
      req.tag = tag;
      ++run;
      return results[fen] = ctx.worker.run(req, ctx.budget, &ctx.log);
  }
};

std::string json_str(const std::string& s) { return "\"" + s + "\""; }

TeamState with_piece(const TeamState& actual, int board, Piece pc) {
  TeamState t;
  t.assign_light(actual);
  t.add_to_pocket(board, pc);
  return t;
}

ProbeCache Cache;        // this go's probes; prices and F share the partner ones
bool PricesOn = false;   // this go's main-pool searches use feed prices
Forecast Fc;             // this go's arrival forecast (v4)
bool WorldsOn = false;   // this go chooses over forecast worlds

enum Tier { SAFE = 0, SOFT = 1, CERTAIN = 2 };

int clock_of(const CoordinatorContext& ctx, int board, Color c) {
  return ctx.clocksMs[board * 2 + (c == BLACK)];
}

bool opponent_mated(TeamState& work, const CoordinatorContext& ctx) {
  Color opp = ~ctx.team;
  return ctx.advantageKnown[opp] ? work.is_checkmate(opp, ctx.advantage[opp])
                                 : work.is_checkmate(opp, false) && work.is_checkmate(opp, true);
}

/// Stalling races our clock against the same-colour seat on the other board:
/// if both sit, both burn at the same rate and the lower one flags first.
bool stall_ok(const CoordinatorContext& ctx) {
  if (!bool(Options["HBStall"]) || !ctx.clocksKnown)
      return false;
  const int pb = 1 - ctx.board;
  int ours = clock_of(ctx, ctx.board, ctx.us);
  int theirs = clock_of(ctx, pb, ctx.us);
  bool partnerFirst = ctx.actual.pos(pb).side_to_move() == ~ctx.us;
  return ours >= Coef::StallReserveMs
      && ours - theirs >= Coef::StallLeadMs + (partnerFirst ? Coef::StallPartnerMs : 0);
}

struct StallState {
  bool active = false;
  size_t moves = 0;      // game length when the stall began
};
StallState Stall;

// Can the opponent's partner, holding `fed`, drop it on Y for an immediate
// team mate (joint referee)? Their side must be on move on Y.
bool drop_mates(const CoordinatorContext& ctx, TeamState& probe, int Y, Piece fed, std::string& how) {
  const Position& py = probe.pos(Y);
  for (const auto& dm : MoveList<LEGAL>(py))
  {
      if (type_of(dm) != DROP || in_hand_piece_type(dm) != type_of(fed) || !py.gives_check(dm))
          continue;
      std::string dropUci = UCI::move(py, dm);
      TeamUndo u = probe.play_undoable(Y, dm);
      bool mated = probe.is_checkmate(ctx.team, ctx.advantage[ctx.team]);
      probe.undo(u);
      if (mated)
      {
          how = std::string(1, "AB"[Y]) + dropUci;
          return true;
      }
  }
  return false;
}

std::string with_turn(const std::string& fen, Color c) {
  std::istringstream ss(fen);
  std::vector<std::string> f;
  std::string tok, out;
  while (ss >> tok)
      f.push_back(tok);
  if (f.size() >= 4)
      f[1] = c == WHITE ? "w" : "b", f[3] = "-";
  for (size_t i = 0; i < f.size(); ++i)
      out += (i ? " " : "") + f[i];
  return out;
}

/// How exposed is our move m to a capture-then-mating-drop, by the joint referee?
///
/// Direction 1: the opponent captures on our board and their partner drops
/// that piece for mate on the other board.
///  - Their partner is on turn there: CERTAIN.
///  - Our partner is on turn and in check: CERTAIN if every reply still allows it.
///  - Our partner is on turn otherwise: SOFT, since our partner may move away.
/// Direction 2: m hands the opponent the turn on our board, and the opponent on
/// the other board is on turn with a capture that feeds the mating drop: CERTAIN.
int exposure_tier(const CoordinatorContext& ctx, TeamState& work, Move m, std::string& how) {
  const int X = ctx.board, Y = 1 - ctx.board;
  int tier = SAFE;
  TeamUndo u = work.play_undoable(X, m);
  MoveList<LEGAL> replies(work.pos(X));
  for (const auto& r : replies)
  {
      PieceType t = TeamState::captured_type(work.pos(X), r);
      if (t == NO_PIECE_TYPE)
          continue;
      std::string rUci = UCI::move(work.pos(X), r);
      TeamUndo u2 = work.play_undoable(X, r);    // piece goes to the opponent on Y
      Piece fed = u2.transfer.piece;
      Color dropper = color_of(fed);              // opponent's colour on Y
      std::string fenX = work.fen(X), fenY = work.fen(Y), drop;
      auto build = [&](TeamState& p, const std::string& fy) {
          std::string err;
          return p.reset(X == BOARD_A ? fenX : fy, X == BOARD_A ? fy : fenX, err);
      };
      TeamState probe;
      int found = SAFE;
      if (work.pos(Y).side_to_move() == dropper)
      {
          if (build(probe, fenY) && drop_mates(ctx, probe, Y, fed, drop))
              found = CERTAIN;
      }
      else if (!work.pos(Y).checkers())
      {
          if (build(probe, with_turn(fenY, dropper)) && drop_mates(ctx, probe, Y, fed, drop))
              found = SOFT;
      }
      else if (build(probe, fenY))
      {
          MoveList<LEGAL> partnerMoves(probe.pos(Y));
          bool all = partnerMoves.size() > 0 && partnerMoves.size() <= 12;
          for (const auto& p : partnerMoves)
          {
              if (!all)
                  break;
              TeamUndo u3 = probe.play_undoable(Y, p);
              all = drop_mates(ctx, probe, Y, fed, drop);
              probe.undo(u3);
          }
          if (all)
              found = CERTAIN;
      }
      if (found > tier)
      {
          tier = found;
          how = rUci + ">" + drop;
      }
      work.undo(u2);
      if (tier == CERTAIN)
          break;
  }
  if (tier != CERTAIN && work.pos(Y).side_to_move() == ctx.us)   // the opponent's colour on Y
  {
      MoveList<LEGAL> donors(work.pos(Y));
      for (const auto& r : donors)
      {
          PieceType t = TeamState::captured_type(work.pos(Y), r);
          if (t == NO_PIECE_TYPE)
              continue;
          std::string rUci = UCI::move(work.pos(Y), r), drop;
          TeamUndo u2 = work.play_undoable(Y, r);  // piece goes to the opponent on X
          bool mates = drop_mates(ctx, work, X, u2.transfer.piece, drop);
          work.undo(u2);
          if (mates)
          {
              tier = CERTAIN;
              how = rUci + ">" + drop;
              break;
          }
      }
  }
  work.undo(u);
  return tier;
}

/// Our capture m lets our partner, on turn, drop the piece for a team mate,
/// and the opponent cannot win first with a reply on our board.
bool delivery_wins(const CoordinatorContext& ctx, TeamState& work, Move m) {
  const int X = ctx.board, Y = 1 - ctx.board;
  TeamUndo u = work.play_undoable(X, m);
  PieceType t = type_of(u.transfer.piece);
  bool wins = false;
  for (const auto& dm : MoveList<LEGAL>(work.pos(Y)))
  {
      if (type_of(dm) != DROP || in_hand_piece_type(dm) != t)
          continue;
      TeamUndo u2 = work.play_undoable(Y, dm);
      wins = opponent_mated(work, ctx);
      work.undo(u2);
      if (wins)
          break;
  }
  if (wins)
      for (const auto& r : MoveList<LEGAL>(work.pos(X)))
      {
          TeamUndo u2 = work.play_undoable(X, r);
          bool lost = work.is_checkmate(ctx.team, ctx.advantage[ctx.team]);
          work.undo(u2);
          if (lost)
          {
              wins = false;
              break;
          }
      }
  work.undo(u);
  return wins;
}

} // namespace


void PieceValues::set(Color receiver, PieceType t, int with, int without) {
  ok[receiver][t] = true;
  mate[receiver][t] = with >= Coef::FiniteCap && without < Coef::FiniteCap;
  gain[receiver][t] = with - without;
}

std::string PieceValues::json(const char* source) const {
  std::ostringstream ss;
  ss << "{\"board\":\"" << (board == BOARD_A ? 'A' : 'B') << "\",\"source\":\"" << source
     << "\",\"stm\":\"" << (stm == WHITE ? 'w' : 'b') << "\",\"depth\":" << int(depth)
     << ",\"base\":";
  if (baseOk) ss << base; else ss << "null";
  for (Color c : { WHITE, BLACK })
  {
      ss << (c == WHITE ? ",\"white\":{" : ",\"black\":{");
      bool first = true;
      for (PieceType t : DeliveryTypes)
      {
          ss << (first ? "" : ",") << "\"" << type_char(t) << "\":";
          first = false;
          if (!ok[c][t])        ss << "null";
          else if (mate[c][t])  ss << "\"mate\"";
          else                  ss << gain[c][t];
      }
      ss << "}";
  }
  ss << "}";
  return ss.str();
}

PieceValues measure_piece_values(CoordinatorContext& ctx, int board, Depth depth,
                                 uint64_t maxNodes, Phase phase) {
  PieceValues pv;
  pv.board = board;
  pv.depth = depth;
  pv.stm = ctx.actual.pos(board).side_to_move();
  auto probe = [&](const std::string& fen, const std::string& tag, bool clear) {
      ProbeRequest req;
      req.fen = fen;
      req.depth = depth;
      req.maxNodes = maxNodes;
      req.phase = phase;
      req.clear = clear;
      req.tag = tag;
      return ctx.worker.run(req, ctx.budget, &ctx.log);
  };
  int q0 = 0;
  if (!team_value(probe(ctx.actual.fen(board), "values_base", true), pv.stm, WHITE, q0))
      return pv;
  pv.baseOk = true;
  pv.base = q0;
  for (PieceType t : DeliveryTypes)
      for (Color c : { WHITE, BLACK })
      {
          int v;
          if (ctx.budget.exhausted())
              return pv;
          std::string tag = std::string("values_") + (c == WHITE ? "w" : "b") + type_char(t);
          if (team_value(probe(with_piece(ctx.actual, board, make_piece(c, t)).fen(board), tag, false), pv.stm, c, v))
              pv.set(c, t, v, c == WHITE ? q0 : -q0);
      }
  return pv;
}

void prepare_feed_prices(CoordinatorContext& ctx) {
  Cache = ProbeCache();
  PricesOn = false;
  set_feed_prices_planned(false);
  Budget& b = ctx.budget;
  bool bigEnough = b.node_limited() ? b.total_nodes() > Coef::PriceMinNodes
                                    : b.time_limited() && b.total_ms() >= Coef::PriceMinMs;
  if (!bool(Options["HBFeedPrices"]) || !bigEnough)
      return;

  const int pb = 1 - ctx.board;
  const Color pbStm = ctx.actual.pos(pb).side_to_move();
  const Color partner = ~ctx.us;
  // Used when a probe does not finish: roughly half a piece's board value.
  std::map<PieceType, int> ours{{PAWN, 40}, {KNIGHT, 100}, {BISHOP, 100}, {ROOK, 130}, {QUEEN, 200}};
  std::map<PieceType, int> theirs = ours;

  int q0 = 0;
  PieceValues shown;      // the same probes, unhalved, for the page
  shown.board = pb;
  shown.stm = pbStm;
  shown.depth = Coef::ProbeDepth;
  const ProbeResult& r0 = Cache.get(ctx, ctx.actual.fen(pb), Phase::DISCOVERY, "partner_base");
  if (team_value(r0, pbStm, partner, q0))
  {
      shown.baseOk = true;
      shown.base = partner == WHITE ? q0 : -q0;
  }
  if (shown.baseOk)
      for (PieceType t : DeliveryTypes)
      {
          TeamState mine, enemy;
          mine.assign_light(ctx.actual);
          enemy.assign_light(ctx.actual);
          mine.add_to_pocket(pb, make_piece(partner, t));
          enemy.add_to_pocket(pb, make_piece(ctx.us, t));
          int v;
          if (team_value(Cache.get(ctx, mine.fen(pb), Phase::DISCOVERY, std::string("partner_") + type_char(t)), pbStm, partner, v))
              shown.set(partner, t, v, q0),
              ours[t] = v >= Coef::FiniteCap && q0 < Coef::FiniteCap ? Coef::MatePriceOurs
                                                                     : std::clamp((v - q0) / Coef::PriceDiv, 0, Coef::PriceCap);
          if (team_value(Cache.get(ctx, enemy.fen(pb), Phase::DISCOVERY, std::string("enemy_") + type_char(t)), pbStm, partner, v))
              shown.set(ctx.us, t, -v, -q0),
              theirs[t] = v <= -Coef::FiniteCap && q0 > -Coef::FiniteCap ? Coef::MatePriceTheirs
                                                                         : std::clamp((q0 - v) / Coef::PriceDiv, 0, Coef::PriceCap);
      }

  std::ostringstream ps;
  ps << "{\"base\":" << q0;
  for (int side = 0; side < 2; ++side)
  {
      ps << (side ? ",\"theirs\":{" : ",\"ours\":{");
      bool first = true;
      for (PieceType t : DeliveryTypes)
      {
          int cp = side ? theirs[t] : ours[t];
          FedGain[side ? ~ctx.us : ctx.us][t] = cp * PawnValueEg / 100;
          ps << (first ? "" : ",") << "\"" << type_char(t) << "\":" << cp;
          first = false;
      }
      ps << "}";
  }
  ps << "}";
  FedRoot = ctx.us;
  // Scores in the table carry another go's prices and root.
  TT.clear();
  PricesOn = true;
  set_feed_prices_planned(true);
  ctx.log.set("prices", "1");
  sync_cout << "info string hb_prices " << ps.str() << sync_endl;
  sync_cout << "info string hb_values " << shown.json("partner") << sync_endl;
}


void prepare_forecast(CoordinatorContext& ctx) {
  Fc = Forecast();
  WorldsOn = false;
  Budget& b = ctx.budget;
  bool bigEnough = b.node_limited() ? b.total_nodes() > Coef::PriceMinNodes
                                    : b.time_limited() && b.total_ms() >= Coef::PriceMinMs;
  if (!bool(Options["HBWorlds"]) || !bigEnough)
      return;
  // The forecast runs before the main search and the worlds after it.
  b.set_slices(Slices{0.58, 0.02, 0.38, 0.02});
  ctx.worker.set_hash_mb(Coef::WorldHashMb);
  Fc = make_forecast(ctx);
  WorldsOn = true;
  ctx.log.set("worlds", std::to_string(Fc.worlds.size()));
  ctx.log.set("p_none", std::to_string(int(std::lround(Fc.worlds[0].p * 100))));
  sync_cout << "info string hb_forecast " << Fc.json() << sync_endl;
}

Decision coordinate(CoordinatorContext& ctx) {
  Decision d;
  const Position& root = ctx.actual.pos(ctx.board);
  const int pb = 1 - ctx.board;
  const Color partner = ~ctx.us;              // our team's colour on the partner board
  const bool pbOnTurnIsPartner = ctx.actual.pos(pb).side_to_move() == partner;
  MoveList<LEGAL> legal(root);
  DecisionLog& log = ctx.log;
  std::ostringstream js;                      // hb_coord report
  auto finish = [&](Decision dec, const std::string& why) {
      dec.reason = why;
      log.set("coord_reason", why);
      sync_cout << "info string hb_coord {\"reason\":" << json_str(why) << js.str() << "}" << sync_endl;
      return dec;
  };

  Move M = ctx.main.status == ProbeResult::OK && ctx.main.finalMove != MOVE_NONE ? ctx.main.finalMove : ctx.fallback;
  d.move = M;
  log.set("override", "0");

  auto stall = [&]() {
      Decision s;
      s.pass = true;
      s.wakeAfterMs = std::max(1, clock_of(ctx, ctx.board, ctx.us) - Coef::StallReserveMs);
      Stall.active = true;
      Stall.moves = ctx.actual.move_count();
      log.set("stall_lead_ms", std::to_string(clock_of(ctx, ctx.board, ctx.us) - clock_of(ctx, pb, ctx.us)));
      return s;
  };

  TeamState work;
  work.assign_light(ctx.actual);

  // ---- verified immediate team win (joint referee after the concrete move)
  {
      std::vector<std::string> wins;
      bool mainWins = false;
      for (const auto& m : legal)
          if (wins_now(work, ctx.board, m, ctx.team, ctx.advantage, ctx.advantageKnown))
          {
              wins.push_back(UCI::move(root, m));
              mainWins |= Move(m) == M;
          }
      if (!wins.empty())
      {
          std::sort(wins.begin(), wins.end());
          js << ",\"team_wins\":" << wins.size();
          log.set("team_win", "1");
          if (mainWins)
              return finish(d, "team_win_main");
          std::string w = wins.front();
          d.move = UCI::to_move(root, w);
          log.set("override", "1");
          return finish(d, "team_win_override");
      }
  }

  // ---- a forced move can still be refused: sitting costs only clock
  if (legal.size() <= 1)
  {
      std::string how;
      if (exposure_tier(ctx, work, M, how) == CERTAIN && stall_ok(ctx))
      {
          log.set("veto", how);
          return finish(stall(), "stall_deny");
      }
      return finish(d, "only_move");
  }

  // ---- verified delivery win: both seats reach this conclusion, so the
  // partner can wait for it (see wait_conditions)
  if (pbOnTurnIsPartner)
  {
      std::vector<std::string> wins;
      bool mainWins = false;
      for (const auto& m : legal)
          if (TeamState::captured_type(root, m) != NO_PIECE_TYPE && delivery_wins(ctx, work, m))
          {
              wins.push_back(UCI::move(root, m));
              mainWins |= Move(m) == M;
          }
      if (!wins.empty())
      {
          std::sort(wins.begin(), wins.end());
          js << ",\"delivery_wins\":" << wins.size();
          if (mainWins)
              return finish(d, "delivery_win_main");
          d.move = UCI::to_move(root, wins.front());
          log.set("override", "1");
          return finish(d, "delivery_win");
      }
  }

  if (ctx.main.status != ProbeResult::OK || ctx.main.depth == 0)
      return finish(d, "main_incomplete");

  // ---- candidates from the main search
  std::vector<Candidate> cands;
  auto add_candidate = [&](Move m, const std::string& source) {
      if (m == MOVE_NONE || !legal.contains(m))
          return;
      for (const auto& c : cands)
          if (c.move == m)
              return;
      Candidate c;
      c.move = m;
      c.uci = UCI::move(root, m);
      c.source = source;
      c.delivery = TeamState::captured_type(root, m);
      cands.push_back(c);
  };
  add_candidate(M, "main");
  const int maxMain = WorldsOn ? Coef::WorldMainCandidates : Coef::MaxMainCandidates;
  const int maxDeliveries = WorldsOn ? Coef::WorldDeliveries : Coef::MaxDeliveries;
  for (Move m : ctx.main.rootOrder)
      if (int(cands.size()) < maxMain)
          add_candidate(m, "root");

  // ---- partner probes: same partner board and turn with/without each type
  const Position& pbPos = ctx.actual.pos(pb);
  const Color pbStm = pbPos.side_to_move();
  std::set<PieceType> captureTypes;
  for (const auto& m : legal)
  {
      PieceType t = TeamState::captured_type(root, m);
      if (t != NO_PIECE_TYPE)
          captureTypes.insert(t);
  }
  ProbeCache& cache = Cache;
  int q0 = 0;
  bool hasQ0 = false;
  std::map<PieceType, int> F;                 // only exact pairs
  if (!captureTypes.empty())
  {
      const ProbeResult& r0 = cache.get(ctx, ctx.actual.fen(pb), Phase::DISCOVERY, "partner_base");
      hasQ0 = team_value(r0, pbStm, partner, q0);
      js << ",\"partner_base\":" << (hasQ0 ? std::to_string(q0) : "null");
      js << ",\"partner_probes\":{";
      bool first = true;
      for (PieceType t : DeliveryTypes)
          if (captureTypes.count(t))
          {
              TeamState copy;
              copy.assign_light(ctx.actual);
              copy.add_to_pocket(pb, make_piece(partner, t));
              const ProbeResult& r = cache.get(ctx, copy.fen(pb), Phase::DISCOVERY, std::string("partner_") + type_char(t));
              int qt;
              bool ok = hasQ0 && team_value(r, pbStm, partner, qt);
              if (ok)
                  F[t] = qt - q0;
              js << (first ? "" : ",") << "\"" << type_char(t) << "\":" << (ok ? std::to_string(qt - q0) : "null");
              first = false;
          }
      js << "}";
  }

  // ---- delivery candidates (captures outside the current candidate set)
  {
      struct Del { Move m; PieceType t; bool mating, blocking; int gain, order; std::string uci; };
      std::vector<Del> dels;
      bool partnerOnTurn = pbStm == partner;
      bool partnerStuck = partnerOnTurn && pbPos.checkers() && !MoveList<LEGAL>(pbPos).size();
      for (const auto& mv : legal)
      {
          Move m = mv;
          PieceType t = TeamState::captured_type(root, m);
          if (t == NO_PIECE_TYPE)
              continue;
          bool already = false;
          for (const auto& c : cands)
              already |= c.move == m;
          if (already)
              continue;
          Del del{m, t, false, false, 0, mvv_lva(root, m), UCI::move(root, m)};
          if (partnerOnTurn)
          {
              TeamUndo u = work.play_undoable(ctx.board, m);
              const Position& p2 = work.pos(pb);
              if (partnerStuck && MoveList<LEGAL>(p2).size())
                  del.blocking = true;
              for (const auto& dm : MoveList<LEGAL>(p2))
                  if (type_of(dm) == DROP && in_hand_piece_type(dm) == t && !del.mating)
                  {
                      TeamUndo u2 = work.play_undoable(pb, dm);
                      Color opp = ~ctx.team;
                      del.mating = ctx.advantageKnown[opp] ? work.is_checkmate(opp, ctx.advantage[opp])
                                                           : work.is_checkmate(opp, false) && work.is_checkmate(opp, true);
                      work.undo(u2);
                  }
              work.undo(u);
          }
          // a delivery needs its paired partner probe (F) to be scored at all
          if (!F.count(t))
              continue;
          del.gain = F[t];
          if (!(del.mating || del.blocking || del.gain > 0))
              continue;
          dels.push_back(del);
      }
      std::sort(dels.begin(), dels.end(), [](const Del& a, const Del& b) {
          if (a.mating != b.mating) return a.mating;
          if (a.blocking != b.blocking) return a.blocking;
          if (a.gain != b.gain) return a.gain > b.gain;
          if (a.order != b.order) return a.order > b.order;
          return a.uci < b.uci;
      });
      std::set<PieceType> used;
      int added = 0;
      for (const auto& del : dels)
          if (added < maxDeliveries && !used.count(del.t))
          {
              add_candidate(del.m, "delivery");
              cands.back().mating = del.mating;
              cands.back().blocking = del.blocking;
              used.insert(del.t);
              ++added;
          }
      js << ",\"delivery_options\":" << dels.size();
      log.set("deliveries", std::to_string(added));
  }

  // ---- exposure tiers: can a capture feed a mating drop after this move?
  int certainCount = 0;
  for (auto& c : cands)
  {
      c.tier = exposure_tier(ctx, work, c.move, c.exposure);
      certainCount += c.tier == CERTAIN;
  }
  log.set("exposed", std::to_string(certainCount));
  if (cands[0].tier == CERTAIN && certainCount == int(cands.size()))
  {
      // Every candidate loses to it: scan the other legal moves.
      std::vector<Move> safe, soft;
      int scanned = 0;
      for (const auto& mv : legal)
      {
          uint64_t gn; TimePoint gt;
          if (!ctx.budget.passthrough() && !ctx.budget.grant(Phase::COMPARE, gn, gt))
              break;
          bool known = false;
          for (const auto& c : cands)
              known |= c.move == Move(mv);
          if (known)
              continue;
          std::string how;
          ++scanned;
          int t = exposure_tier(ctx, work, mv, how);
          if (t == SAFE)
              safe.push_back(mv);
          else if (t == SOFT)
              soft.push_back(mv);
      }
      log.set("safety_scanned", std::to_string(scanned));
      log.set("safety_found", std::to_string(safe.size() + soft.size()));
      const std::vector<Move>& pool = safe.empty() ? soft : safe;
      if (!pool.empty())
      {
          Move pick = pool.front();
          ProbeResult sr = run_main_search(ctx.actual, ctx.board, ctx.budget, Phase::COMPARE, &log, pool, 1, "safety", 0.4);
          if (sr.status == ProbeResult::OK && sr.finalMove != MOVE_NONE
              && std::count(pool.begin(), pool.end(), sr.finalMove))
              pick = sr.finalMove;
          add_candidate(pick, "safety");
          cands.back().tier = safe.empty() ? SOFT : SAFE;
      }
  }

  // Best alternative no worse than maxTier: by S when every candidate is
  // scored, otherwise the first in candidate order.
  auto alternative = [&](bool byS, int maxTier, int minL) -> const Candidate* {
      const Candidate* best = nullptr;
      for (size_t i = 1; i < cands.size(); ++i)
      {
          const Candidate& c = cands[i];
          if (c.tier > maxTier || (byS && (!c.hasL || c.L < minL)))
              continue;
          if (!best)
              best = &c;
          else if (byS && (c.S > best->S || (c.S == best->S && c.uci < best->uci)))
              best = &c;
      }
      return best;
  };
  // Replace or stall an exposed main choice. Returns the reason, empty if it stands.
  auto resolve_tier = [&](bool byS, Decision& dec) -> std::string {
      const Candidate& mc = cands[0];
      auto play = [&](const Candidate* a) {
          dec.move = a->move;
          log.set("override", "1");
          log.set("override_source", a->source);
          log.set("veto", mc.exposure);
      };
      if (mc.tier == SOFT)
      {
          const Candidate* a = byS ? alternative(true, SAFE, mc.L - Coef::SoftSwitchBound) : nullptr;
          if (!a)
              return "";
          play(a);
          return "soft_switch";
      }
      if (mc.tier != CERTAIN)
          return "";
      const int notMated = -Coef::FiniteCap + 1;
      const Candidate* a = alternative(byS, SAFE, notMated);
      if (!a)
          a = alternative(byS, SOFT, notMated);
      bool poor = a && byS && a->L < mc.L - Coef::SoftSwitchBound;
      if ((!a || poor) && stall_ok(ctx))
      {
          log.set("veto", mc.exposure);
          dec = stall();
          return "stall_deny";
      }
      if (!a)
      {
          log.set("veto", "no_safe_candidate");
          return "";
      }
      play(a);
      return "exposure_veto";
  };

  // ---- final use of the remaining budget
  auto extend_main = [&](const std::string& why) {
      ProbeResult ext = run_main_search(ctx.actual, ctx.board, ctx.budget, Phase::COMPARE, &log, {}, 1, "extension");
      log.set("extension_depth", std::to_string(ext.depth));
      std::string how;
      if (ext.status == ProbeResult::OK && ext.finalMove != MOVE_NONE
          && ext.depth >= ctx.main.depth && legal.contains(ext.finalMove)
          && (ext.finalMove == M || exposure_tier(ctx, work, ext.finalMove, how) <= cands[0].tier))
      {
          d.move = ext.finalMove;
          log.set("extension_used", "1");
      }
      return finish(d, why);
  };

  auto report_candidates = [&](int depth) {
      js << ",\"common_depth\":" << depth << ",\"candidates\":[";
      for (size_t i = 0; i < cands.size(); ++i)
      {
          const Candidate& c = cands[i];
          js << (i ? "," : "") << "{\"move\":" << json_str(c.uci) << ",\"source\":" << json_str(c.source)
             << ",\"delivery\":" << json_str(c.delivery != NO_PIECE_TYPE ? std::string(1, type_char(c.delivery)) : "")
             << ",\"mating\":" << (c.mating ? "true" : "false") << ",\"blocking\":" << (c.blocking ? "true" : "false")
             << ",\"enemy_donor\":" << (c.enemyDonor ? "true" : "false")
             << ",\"friendly_scenarios\":" << c.friendlyScenarios << ",\"enemy_captures\":" << c.enemyCaptures
             << ",\"L\":" << (c.hasL ? std::to_string(c.L) : "null")
             << ",\"R\":" << (c.hasR ? std::to_string(c.R) : "null")
             << ",\"F\":" << (c.hasF ? std::to_string(c.F) : "null")
             << ",\"S\":" << (c.hasL && c.hasR && c.hasF ? std::to_string(c.S) : "null")
             << ",\"E\":" << c.E
             << ",\"tier\":" << c.tier
             << ",\"probe_fatal\":" << (c.probeFatal ? "true" : "false")
             << ",\"exposed\":" << json_str(c.tier ? c.exposure : "")
             << ",\"scenarios\":[";
          for (size_t k = 0; k < c.scen.size(); ++k)
          {
              const Scenario& s = c.scen[k];
              js << (k ? "," : "") << "{\"arrival\":" << json_str(s.arrival == NO_PIECE ? "none"
                                     : std::string(1, color_of(s.arrival) == WHITE ? type_char(type_of(s.arrival)) : char(tolower(type_char(type_of(s.arrival))))))
                 << ",\"value\":" << (s.done ? std::to_string(s.value) : "null")
                 << ",\"donors\":[";
              for (size_t j = 0; j < s.donors.size(); ++j)
                  js << (j ? "," : "") << json_str(s.donors[j]);
              js << "],\"fen\":" << json_str(s.fen) << "}";
          }
          js << "]}";
      }
      js << "]";
  };

  // ---- v4: one search of our board per forecast world, then the move with
  // the best probability-weighted winning chances
  if (WorldsOn)
  {
      const Forecast& fc = Fc;
      for (auto& c : cands)
          c.hasR = c.hasF = true;
      if (fc.worlds.size() < 2)
      {
          report_candidates(0);
          std::string why = resolve_tier(false, d);
          return why.empty() ? extend_main("no_arrivals") : finish(d, why);
      }

      struct WorldRun {
        Arrival arrival;
        double p = 0;
        std::string key, fen, best;
        int depth = 0;
        bool scored = false;
        std::map<Move, int> value;     // cp for us, per candidate
      };
      std::vector<WorldRun> runs;
      for (const World& w : fc.worlds)
      {
          WorldRun r;
          r.arrival = w.arrival;
          r.p = w.p;
          r.key = w.arrival.key();
          TeamState copy;
          copy.assign_light(ctx.actual);
          for (PieceType t : DeliveryTypes)
          {
              for (int i = 0; i < w.arrival.us[t]; ++i)
                  copy.add_to_pocket(ctx.board, make_piece(ctx.us, t));
              for (int i = 0; i < w.arrival.them[t]; ++i)
                  copy.add_to_pocket(ctx.board, make_piece(~ctx.us, t));
          }
          r.fen = copy.fen(ctx.board);
          runs.push_back(r);
      }
      const size_t extra = runs.size() - 1;
      uint64_t leftNodes = 0;
      TimePoint leftMs = 0;
      ctx.budget.grant(Phase::COMPARE, leftNodes, leftMs);
      auto cap_nodes = [&](double share) {
          return leftNodes ? std::max<uint64_t>(1, uint64_t(double(leftNodes) * share / double(extra))) : uint64_t(0);
      };
      auto cap_ms = [&](double share) {
          return leftMs ? std::max<TimePoint>(1, TimePoint(double(leftMs) * share / double(extra))) : TimePoint(0);
      };
      // Root moves are the moves legal now: a piece of ours that has not
      // arrived yet cannot be dropped on this move.
      std::vector<std::string> legalUci;
      for (const auto& m : legal)
          legalUci.push_back(UCI::move(root, m));

      // Each arrival world's own best move joins the candidates.
      for (size_t i = 1; i < runs.size(); ++i)
      {
          ProbeRequest req;
          req.fen = runs[i].fen;
          req.searchMoves = legalUci;
          req.phase = Phase::PROBES;
          req.clear = i == 1;
          req.fed = true;
          req.maxNodes = cap_nodes(Coef::WorldOwnShare);
          req.maxTimeMs = cap_ms(Coef::WorldOwnShare);
          req.tag = "world_" + runs[i].key;
          ProbeResult r = ctx.worker.run(req, ctx.budget, &log);
          if (!r.usable_exact() || !legal.contains(r.move))
              continue;
          runs[i].best = UCI::move(root, r.move);
          size_t before = cands.size();
          add_candidate(r.move, "world");
          if (cands.size() > before)
          {
              Candidate& c = cands.back();
              c.tier = exposure_tier(ctx, work, c.move, c.exposure);
              c.hasR = c.hasF = true;
          }
      }

      std::vector<Move> sm;
      std::vector<std::string> smUci;
      for (const auto& c : cands)
          sm.push_back(c.move), smUci.push_back(c.uci);

      // Every candidate scored in every arrival world.
      for (size_t i = 1; i < runs.size(); ++i)
      {
          ProbeRequest req;
          req.fen = runs[i].fen;
          req.searchMoves = smUci;
          req.multiPV = sm.size();
          req.phase = Phase::PROBES;
          req.clear = false;
          req.fed = true;
          req.maxNodes = cap_nodes(Coef::WorldScoreShare);
          req.maxTimeMs = cap_ms(Coef::WorldScoreShare);
          req.tag = "score_" + runs[i].key;
          ProbeResult r = ctx.worker.run(req, ctx.budget, &log);
          if (!r.usable_exact())
              continue;
          for (const auto& line : r.lines)
              if (line.second != -VALUE_INFINITE)
                  runs[i].value[line.first] = to_cp(line.second);   // our seat is to move; mates kept
          runs[i].depth = r.depth;
          runs[i].scored = runs[i].value.size() == sm.size();
      }

      // The no-arrival world on the main pool: warm table, real history,
      // and everything the arrival worlds left over.
      ProbeResult cmp = run_main_search(ctx.actual, ctx.board, ctx.budget, Phase::COMPARE, &log, sm, sm.size(), "compare");
      log.set("common_depth", std::to_string(cmp.depth));
      if (cmp.status == ProbeResult::OK && cmp.depth > 0)
          for (const auto& line : cmp.lines)
              if (line.second != -VALUE_INFINITE)
                  runs[0].value[line.first] = to_cp(line.second);
      runs[0].depth = cmp.depth;
      runs[0].scored = runs[0].value.size() == sm.size();
      for (auto& c : cands)
          if (runs[0].value.count(c.move))
              c.hasL = true, c.L = std::clamp(runs[0].value[c.move], -Coef::FiniteCap, Coef::FiniteCap);

      // A world that could not be scored counts as "nothing arrives".
      double pNone = runs[0].p;
      int scoredWorlds = 0;
      for (size_t i = 1; i < runs.size(); ++i)
          if (runs[i].scored)
              ++scoredWorlds;
          else
              pNone += runs[i].p;
      const double scale = double(int(Options["HBWinScale"]));
      // A mate on our board decides the game; any other score only shifts the odds.
      auto win = [&](int cp) {
          return cp >= 90000 ? 1.0 : cp <= -90000 ? 0.0 : 1.0 / (1.0 + std::exp(-double(cp) / scale));
      };
      if (runs[0].scored)
          for (auto& c : cands)
          {
              // With nothing arriving, the main search has already ranked the
              // moves, deeper than this comparison: nothing beats its choice there.
              double e = pNone * win(std::min(runs[0].value[c.move], runs[0].value[cands[0].move]));
              for (size_t i = 1; i < runs.size(); ++i)
                  if (runs[i].scored)
                      e += runs[i].p * win(runs[i].value[c.move]);
              c.E = e;
              double q = std::clamp(e, 1e-4, 1.0 - 1e-4);
              c.S = std::clamp(int(std::lround(scale * std::log(q / (1.0 - q)))), -Coef::FiniteCap, Coef::FiniteCap);
          }

      log.set("worlds_scored", std::to_string(scoredWorlds));
      js << ",\"worlds\":[";
      for (size_t i = 0; i < runs.size(); ++i)
      {
          const WorldRun& r = runs[i];
          js << (i ? "," : "") << "{\"arrival\":" << json_str(r.key) << ",\"p\":" << r.p
             << ",\"best\":" << json_str(r.best) << ",\"depth\":" << r.depth
             << ",\"scored\":" << (r.scored ? "true" : "false") << ",\"values\":{";
          bool first = true;
          for (const auto& c : cands)
              if (r.value.count(c.move))
              {
                  js << (first ? "" : ",") << json_str(c.uci) << ":" << r.value.at(c.move);
                  first = false;
              }
          js << "}}";
      }
      js << "]";
      report_candidates(cmp.depth);

      if (!runs[0].scored)
      {
          std::string why = resolve_tier(false, d);
          return finish(d, why.empty() ? "compare_incomplete" : why);
      }
      {
          std::string why = resolve_tier(true, d);
          if (why.empty() && cands[0].tier == CERTAIN)
              why = resolve_tier(false, d);
          if (!why.empty())
              return finish(d, why);
      }
      const Candidate* best = nullptr;
      for (size_t i = 1; i < cands.size(); ++i)
      {
          const Candidate& c = cands[i];
          if (!c.hasL || c.tier > cands[0].tier)
              continue;
          if (!best || c.S > best->S || (c.S == best->S && c.uci < best->uci))
              best = &c;
      }
      if (scoredWorlds && best && best->S >= cands[0].S + Coef::WorldSwitchMargin)
      {
          d.move = best->move;
          log.set("override", "1");
          log.set("override_source", best->source);
          return finish(d, "world_switch");
      }
      return finish(d, "kept_main");
  }

  // ---- simulated hands: one scenario per partner-board capture after m
  int enemyScen = 0, friendlyScen = 0, dedup = 0;
  for (auto& c : cands)
  {
      if (c.delivery != NO_PIECE_TYPE)
      {
          c.hasF = F.count(c.delivery);
          c.F = c.hasF ? F[c.delivery] : 0;
      }
      else
          c.hasF = true, c.F = 0;

      TeamUndo u = work.play_undoable(ctx.board, c.move);
      const Position& p2 = work.pos(pb);
      Color donor = p2.side_to_move();
      c.enemyDonor = donor != partner;
      std::map<PieceType, Scenario> byType;
      for (const auto& dm : MoveList<LEGAL>(p2))
      {
          PieceType t = TeamState::captured_type(p2, dm);
          if (t == NO_PIECE_TYPE)
              continue;
          if (!c.enemyDonor)
          {
              ++c.friendlyScenarios;      // informs waiting/diagnostics only
              continue;
          }
          ++c.enemyCaptures;
          std::string duci = UCI::move(p2, dm);
          auto it = byType.find(t);
          if (it != byType.end())
          {
              it->second.donors.push_back(duci);   // identical hand addition
              ++dedup;
              continue;
          }
          Scenario s;
          TeamUndo u2 = work.play_undoable(pb, dm);   // donor board + receiving pocket
          s.arrival = u2.transfer.piece;
          s.fen = work.fen(ctx.board);                // our board: same turn, one more piece
          s.donors.push_back(duci);
          work.undo(u2);
          byType[t] = s;
      }
      if (c.enemyDonor && !byType.empty())
      {
          Scenario none;
          none.fen = work.fen(ctx.board);
          c.scen.push_back(none);
          for (PieceType t : DeliveryTypes)
              if (byType.count(t))
                  c.scen.push_back(byType[t]);
      }
      work.undo(u);
      enemyScen += std::max(0, int(c.scen.size()) - 1);
      friendlyScen += c.friendlyScenarios;
  }

  // ---- local probes, deterministic round robin over candidates/scenarios
  size_t rounds = 0;
  for (const auto& c : cands)
      rounds = std::max(rounds, c.scen.size());
  int required = 0, completed = 0;
  for (size_t k = 0; k < rounds; ++k)
      for (auto& c : cands)
          if (k < c.scen.size())
          {
              Scenario& s = c.scen[k];
              ++required;
              const ProbeResult& r = cache.get(ctx, s.fen, Phase::PROBES,
                                               c.uci + (k ? std::string("+") + type_char(type_of(s.arrival)) : std::string("+none")));
              // probe root: opponent to move on our board (turn unchanged)
              s.done = team_value(r, ~ctx.us, ctx.us, s.value);
              completed += s.done;
          }
  for (auto& c : cands)
  {
      if (c.scen.empty())
      {
          c.hasR = true, c.R = 0;
          continue;
      }
      bool all = std::all_of(c.scen.begin(), c.scen.end(), [](const Scenario& s) { return s.done; });
      c.hasR = all;
      if (all)
      {
          int worst = 0;
          for (size_t k = 1; k < c.scen.size(); ++k)
              worst = std::min(worst, c.scen[k].value - c.scen[0].value);
          c.R = std::min(0, worst);
      }
      // The arrival is mate in the probe while the same position without it is not.
      for (size_t k = 1; k < c.scen.size(); ++k)
          if (c.scen[k].done && c.scen[k].value <= -Coef::FiniteCap && c.scen[0].value > -Coef::FiniteCap)
              c.probeFatal = true;
      if (c.probeFatal && c.tier == SAFE)
          c.tier = SOFT;
  }
  int partnerRequired = 0, partnerCompleted = 0;
  for (auto& c : cands)
      if (c.delivery != NO_PIECE_TYPE)
          ++partnerRequired, partnerCompleted += c.hasF;

  bool complete = std::all_of(cands.begin(), cands.end(), [](const Candidate& c) { return c.hasR && c.hasF; });
  log.set("candidates", std::to_string(cands.size()));
  log.set("scen_enemy", std::to_string(enemyScen));
  log.set("scen_friendly", std::to_string(friendlyScen));
  log.set("scen_dedup", std::to_string(dedup));
  log.set("probes_required", std::to_string(required + partnerRequired));
  log.set("probes_completed", std::to_string(completed + partnerCompleted));
  log.set("probe_cache_hits", std::to_string(cache.requested - cache.run));

  if (cands.size() < 2)
  {
      report_candidates(0);
      std::string why = resolve_tier(false, d);
      return why.empty() ? extend_main("single_candidate") : finish(d, why);
  }
  if (!complete)
  {
      report_candidates(0);
      std::string why = resolve_tier(false, d);
      return why.empty() ? extend_main("partial_coverage") : finish(d, why);
  }

  // ---- L(m): one root-restricted MultiPV search over all candidates, so
  // every candidate has an exact score at one common completed depth.
  std::vector<Move> sm;
  for (const auto& c : cands)
      sm.push_back(c.move);
  ProbeResult cmp = run_main_search(ctx.actual, ctx.board, ctx.budget, Phase::COMPARE, &log, sm, sm.size(), "compare");
  log.set("common_depth", std::to_string(cmp.depth));
  for (auto& c : cands)
      for (const auto& line : cmp.lines)
          if (line.first == c.move && line.second != -VALUE_INFINITE)
              c.hasL = true, c.L = finite_cp(line.second);
  for (auto& c : cands)
      // With prices on, L already holds what the capture is worth across boards.
      c.S = c.L + std::max(c.R / Coef::RDiv, -Coef::RCap)
                + (PricesOn ? 0 : std::clamp(c.F, -Coef::FCap, Coef::FCap));
  report_candidates(cmp.depth);

  if (cmp.status != ProbeResult::OK || cmp.depth == 0 || !cands[0].hasL)
  {
      std::string why = resolve_tier(false, d);
      return finish(d, why.empty() ? "compare_incomplete" : why);
  }
  {
      std::string why = resolve_tier(true, d);
      if (why.empty() && cands[0].tier == CERTAIN)
          why = resolve_tier(false, d);
      if (!why.empty())
          return finish(d, why);
  }

  // ---- S rule: replace the main choice only by at least 20 cp
  const Candidate* best = nullptr;
  for (size_t i = 1; i < cands.size(); ++i)
  {
      const Candidate& c = cands[i];
      if (!c.hasL || c.tier > cands[0].tier)
          continue;                      // unscored at the common depth, or more exposed: ineligible
      if (!best || c.S > best->S || (c.S == best->S && c.uci < best->uci))
          best = &c;
  }
  if (best && best->S >= cands[0].S + Coef::SwitchMargin)
  {
      d.move = best->move;
      log.set("override", "1");
      log.set("override_source", best->source);
      return finish(d, "override");
  }
  return finish(d, "kept_main");
}


// ------------------------------------------------------------- waiting

namespace {

struct WaitState {
  std::string turnKey;
  bool active = false;   // a voluntary wait is running for this turn
  bool used = false;     // this turn's one wait has been spent
  int expiryClock = 0;   // our clock value at which the wait expires
};
WaitState Wait;

std::string turn_key(const TeamState& ts, int board) {
  int plies = 0;
  for (const auto& m : ts.move_list())
      plies += m.first == board;
  return std::to_string(plies) + ":" + ts.rep_key(board);
}

// Conditions for waiting waitMs more. why = first failure.
//
// Two reasons to wait:
//  A. Our partner, on turn, has a capture that hands us a winning drop. It
//     runs the same delivery check and will play it, so the wait is short and
//     needs no clock lead, only enough clock.
//  B. We are in check and every legal partner move supplies a block. That is
//     less decisive, so it needs a real lead over the seat we would race.
bool wait_conditions(const CoordinatorContext& ctx, int waitMs, std::string& why) {
  const int pb = 1 - ctx.board;
  const Color partner = ~ctx.us;
  if (!ctx.clocksKnown)                           { why = "no_clocks"; return false; }
  int ours = clock_of(ctx, ctx.board, ctx.us);
  int theirs = clock_of(ctx, pb, ctx.us);        // opposing seat on the partner board
  if (ours <= waitMs + Coef::WaitReserveMs)       { why = "low_clock"; return false; }

  const Position& root = ctx.actual.pos(ctx.board);
  if (ctx.actual.pos(pb).side_to_move() != partner) { why = "partner_not_on_turn"; return false; }

  TeamState work;
  work.assign_light(ctx.actual);
  for (const auto& m : MoveList<LEGAL>(root))
      if (wins_now(work, ctx.board, m, ctx.team, ctx.advantage, ctx.advantageKnown))
      { why = "local_win_available"; return false; }

  MoveList<LEGAL> partnerMoves(work.pos(pb));
  if (!partnerMoves.size())                       { why = "partner_no_moves"; return false; }

  // A: a verified winning delivery from our partner
  for (const auto& p : partnerMoves)
  {
      if (TeamState::captured_type(work.pos(pb), p) == NO_PIECE_TYPE)
          continue;
      TeamUndo u = work.play_undoable(pb, p);
      PieceType t = type_of(u.transfer.piece);
      bool win = false;
      for (const auto& dm : MoveList<LEGAL>(work.pos(ctx.board)))
          if (type_of(dm) == DROP && in_hand_piece_type(dm) == t)
          {
              TeamUndo u2 = work.play_undoable(ctx.board, dm);
              win = opponent_mated(work, ctx);
              work.undo(u2);
              if (win)
                  break;
          }
      if (win)
          for (const auto& r : MoveList<LEGAL>(work.pos(pb)))
          {
              TeamUndo u3 = work.play_undoable(pb, r);
              bool lost = work.is_checkmate(ctx.team, ctx.advantage[ctx.team]);
              work.undo(u3);
              if (lost)
              {
                  win = false;
                  break;
              }
          }
      work.undo(u);
      if (win)
      {
          why = "ok";
          return true;
      }
  }

  // B: in check, every partner move supplies a block
  bool inCheck = root.checkers();
  if (!inCheck)                                   { why = "no_winning_delivery"; return false; }
  if (ours <= theirs + waitMs + Coef::WaitReserveMs) { why = "partner_opponent_clock"; return false; }
  for (const auto& p : partnerMoves)
      if (TeamState::captured_type(work.pos(pb), p) == NO_PIECE_TYPE)
      { why = "partner_noncapture"; return false; }

  int checked = 0;
  for (const auto& p : partnerMoves)
  {
      TeamUndo u = work.play_undoable(pb, p);
      PieceType t = type_of(u.transfer.piece);
      bool needed = false;
      for (const auto& dm : MoveList<LEGAL>(work.pos(ctx.board)))
          if (type_of(dm) == DROP && in_hand_piece_type(dm) == t)
          {
              needed = true;      // a legal drop in check is a block
              break;
          }
      if (!needed)
      {
          work.undo(u);
          why = "arrival_not_needed";
          return false;
      }
      // Bounded safety: the partner's move does not lose, and no opposing
      // reply on the partner board wins immediately for them.
      if (work.is_checkmate(ctx.team, ctx.advantage[ctx.team]))
      {
          work.undo(u);
          why = "partner_loses";
          return false;
      }
      for (const auto& r : MoveList<LEGAL>(work.pos(pb)))
      {
          if (++checked > Coef::SafetyCheckLimit)
          {
              work.undo(u);
              why = "safety_incomplete";
              return false;
          }
          TeamUndo u3 = work.play_undoable(pb, r);
          bool lost = work.is_checkmate(ctx.team, ctx.advantage[ctx.team]);
          work.undo(u3);
          if (lost)
          {
              work.undo(u);
              why = "opponent_wins_after_delivery";
              return false;
          }
      }
      work.undo(u);
  }
  why = "ok";
  return true;
}

} // namespace

void reset_wait_state() {
  Wait = WaitState();
  Stall = StallState();
}

Decision consider_voluntary_wait(const CoordinatorContext& ctx) {
  Decision d;
  // A stall holds without a new search while nothing has moved.
  if (Stall.active)
  {
      if (Stall.moves == ctx.actual.move_count() && stall_ok(ctx))
      {
          ctx.log.set("wait", "stall_continue");
          d.pass = true, d.reason = "stall_deny";
          return d;
      }
      Stall.active = false;
  }
  std::string key = turn_key(ctx.actual, ctx.board);
  if (key != Wait.turnKey)
  {
      Wait = WaitState();
      Wait.turnKey = key;
  }
  int ours = ctx.clocksKnown ? clock_of(ctx, ctx.board, ctx.us) : 0;
  std::string why;

  if (Wait.active)
  {
      int remaining = ours - Wait.expiryClock;
      if (!ctx.clocksKnown || remaining <= 0)
      {
          Wait.active = false, Wait.used = true;
          ctx.log.set("wait", "expired");
          return d;
      }
      if (wait_conditions(ctx, remaining, why))
      {
          ctx.log.set("wait", "continue");
          d.pass = true, d.wakeAfterMs = remaining, d.reason = "voluntary_wait";
          return d;
      }
      Wait.active = false, Wait.used = true;
      ctx.log.set("wait", "stopped_" + why);
      return d;
  }
  if (Wait.used)
  {
      ctx.log.set("wait", "used");
      return d;
  }
  if (!wait_conditions(ctx, Coef::WaitMs, why))
  {
      ctx.log.set("wait", "skip_" + why);
      return d;
  }
  Wait.active = true;
  Wait.expiryClock = ours - Coef::WaitMs;
  ctx.log.set("wait", "start");
  d.pass = true, d.wakeAfterMs = Coef::WaitMs, d.reason = "voluntary_wait";
  return d;
}

} // namespace Stockfish::HB
