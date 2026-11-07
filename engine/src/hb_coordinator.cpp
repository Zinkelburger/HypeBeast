/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

// PLAN.md section 5, v1. Order of work inside one 'go':
//
//   main search (MAIN, 60%)       -> main choice M, root order
//   immediate team win check      -> referee on the concrete joint state
//   partner probes (DISCOVERY)    -> F_T for every capturable type T
//   delivery candidates           -> up to 2 captures outside the root top 3
//   local probes (PROBES)         -> P0 and one probe per distinct enemy arrival
//   comparison search (COMPARE)   -> root-restricted MultiPV over all candidates:
//                                    every L(m) at one common completed depth;
//                                    it absorbs all budget left over (to 95%)
//   S rule                        -> replace M only by >= 20 cp
//
// When no comparison is possible (one candidate, or a required probe is
// missing) the leftover budget instead extends the main search (warm TT),
// whose move is played only if it completed at least the main depth.

#include <algorithm>
#include <map>
#include <set>
#include <sstream>

#include "hb_coordinator.h"
#include "hb_decisionlog.h"
#include "movegen.h"
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
      req.clear = true;
      req.tag = tag;
      ++run;
      return results[fen] = ctx.worker.run(req, ctx.budget, &ctx.log);
  }
};

std::string json_str(const std::string& s) { return "\"" + s + "\""; }

} // namespace


Decision coordinate(CoordinatorContext& ctx) {
  Decision d;
  const Position& root = ctx.actual.pos(ctx.board);
  const int pb = 1 - ctx.board;
  const Color partner = ~ctx.us;              // our team's colour on the partner board
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
  if (legal.size() <= 1)
      return finish(d, "only_move");

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
  for (Move m : ctx.main.rootOrder)
      if (int(cands.size()) < Coef::MaxMainCandidates)
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
  ProbeCache cache;
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
          if (added < Coef::MaxDeliveries && !used.count(del.t))
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

  // ---- final use of the remaining budget
  auto extend_main = [&](const std::string& why) {
      ProbeResult ext = run_main_search(ctx.actual, ctx.board, ctx.budget, Phase::COMPARE, &log, {}, 1, "extension");
      log.set("extension_depth", std::to_string(ext.depth));
      if (ext.status == ProbeResult::OK && ext.finalMove != MOVE_NONE
          && ext.depth >= ctx.main.depth && legal.contains(ext.finalMove))
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

  if (cands.size() < 2)
  {
      report_candidates(0);
      return extend_main("single_candidate");
  }
  if (!complete)
  {
      report_candidates(0);
      return extend_main("partial_coverage");
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
      c.S = c.L + std::clamp(c.R, -Coef::RCap, 0) + std::clamp(c.F, -Coef::FCap, Coef::FCap);
  report_candidates(cmp.depth);

  if (cmp.status != ProbeResult::OK || cmp.depth == 0 || !cands[0].hasL)
      return finish(d, "compare_incomplete");

  // ---- S rule: replace the main choice only by at least 20 cp
  const Candidate* best = nullptr;
  for (size_t i = 1; i < cands.size(); ++i)
  {
      const Candidate& c = cands[i];
      if (!c.hasL)
          continue;                      // no score at the common depth: ineligible
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

int clock_of(const CoordinatorContext& ctx, int board, Color c) {
  return ctx.clocksMs[board * 2 + (c == BLACK)];
}

// All PLAN 5.4 conditions for waiting waitMs more. why = first failure.
bool wait_conditions(const CoordinatorContext& ctx, int waitMs, std::string& why) {
  const int pb = 1 - ctx.board;
  const Color partner = ~ctx.us;
  if (!ctx.clocksKnown)                           { why = "no_clocks"; return false; }
  if (!ctx.advantage[ctx.team])                   { why = "no_time_advantage"; return false; }
  int ours = clock_of(ctx, ctx.board, ctx.us);
  int theirs = clock_of(ctx, pb, ctx.us);        // opposing seat on the partner board
  if (ours <= waitMs + Coef::WaitReserveMs)       { why = "low_clock"; return false; }
  if (ours <= theirs + waitMs + Coef::WaitReserveMs) { why = "partner_opponent_clock"; return false; }

  const Position& root = ctx.actual.pos(ctx.board);
  if (ctx.actual.pos(pb).side_to_move() != partner) { why = "partner_not_on_turn"; return false; }

  TeamState work;
  work.assign_light(ctx.actual);
  for (const auto& m : MoveList<LEGAL>(root))
      if (wins_now(work, ctx.board, m, ctx.team, ctx.advantage, ctx.advantageKnown))
      { why = "local_win_available"; return false; }

  MoveList<LEGAL> partnerMoves(work.pos(pb));
  if (!partnerMoves.size())                       { why = "partner_no_moves"; return false; }
  // Cheap pass first: every partner move must be a capture.
  for (const auto& p : partnerMoves)
      if (TeamState::captured_type(work.pos(pb), p) == NO_PIECE_TYPE)
      { why = "partner_noncapture"; return false; }

  bool inCheck = root.checkers();
  int checked = 0;
  for (const auto& p : partnerMoves)
  {
      TeamUndo u = work.play_undoable(pb, p);
      PieceType t = type_of(u.transfer.piece);
      bool needed = false;
      for (const auto& dm : MoveList<LEGAL>(work.pos(ctx.board)))
      {
          if (type_of(dm) != DROP || in_hand_piece_type(dm) != t)
              continue;
          if (inCheck) { needed = true; break; }         // a legal drop in check is a block
          TeamUndo u2 = work.play_undoable(ctx.board, dm);
          bool win = work.is_checkmate(~ctx.team, ctx.advantage[~ctx.team]);
          work.undo(u2);
          if (win) { needed = true; break; }              // immediate winning drop
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

void reset_wait_state() { Wait = WaitState(); }

Decision consider_voluntary_wait(const CoordinatorContext& ctx) {
  Decision d;
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
