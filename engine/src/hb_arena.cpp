/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

#include <algorithm>
#include <cstdlib>
#include <memory>
#include <mutex>
#include <sstream>
#include <thread>

#include "evaluate.h"
#include "hb_arena.h"
#include "hb_coordinator.h"
#include "hb_decisionlog.h"
#include "hb_probe.h"
#include "hb_team_state.h"
#include "misc.h"
#include "movegen.h"
#include "thread.h"
#include "uci.h"

namespace Stockfish::HB::Arena {

namespace {

std::unique_ptr<TeamState> Actual;     // authoritative replay of the arena's position
std::string PositionError;             // last 'position' problem, reported at 'go'
std::thread Controller;
std::mutex ControllerMutex;

TeamState& actual() {
  if (!Actual)
      Actual = std::make_unique<TeamState>();
  return *Actual;
}

void join_controller() {
  std::lock_guard<std::mutex> lock(ControllerMutex);
  if (Controller.joinable())
      Controller.join();
}

template<typename F>
void spawn(F f) {
  join_controller();
  std::lock_guard<std::mutex> lock(ControllerMutex);
  Budget::Cancel = false;
  Controller = std::thread(f);
}

/// Seat/team/clock context as seen at 'go' time.
struct SeatContext {
  Seat seat = AWHITE;
  Color team = WHITE;
  int board = BOARD_A;
  Color us = WHITE;
  bool advantage[COLOR_NB] = {false, false};
  bool advantageKnown[COLOR_NB] = {false, false};
  bool clocksKnown = false;
  int clocks[4] = {0, 0, 0, 0};
  std::vector<std::string> errors, warnings;
};

bool parse_clocks(const std::string& s, int out[4]) {
  std::string t = s;
  std::replace(t.begin(), t.end(), ',', ' ');
  std::istringstream ss(t);
  for (int i = 0; i < 4; ++i)
      if (!(ss >> out[i]))
          return false;
  std::string extra;
  return !(ss >> extra);
}

SeatContext seat_context() {
  SeatContext c;
  if (!parse_seat(std::string(Options["Seat"]), c.seat))
      c.errors.push_back("bad_seat value=" + std::string(Options["Seat"]));
  c.board = seat_board(c.seat);
  c.us = seat_color(c.seat);
  c.team = seat_team(c.seat);
  Color optionTeam = Options["Team"] == "black" ? BLACK : WHITE;
  if (optionTeam != c.team)
      c.errors.push_back(std::string("seat_team_mismatch seat=") + seat_name(c.seat)
                         + " team=" + team_name(optionTeam) + " using_seat_team=" + team_name(c.team));

  bool ourAdv = bool(Options["TimeAdvantage"]);
  std::string clocks = std::string(Options["Clocks"]);
  if (!clocks.empty())
  {
      if (parse_clocks(clocks, c.clocks))
          c.clocksKnown = true;
      else
          c.errors.push_back("bad_clocks value=" + clocks);
  }
  if (c.clocksKnown)
  {
      // arena sim.time_advantage: A seat of the team vs same-colour seat on B
      c.advantage[WHITE] = c.clocks[0] > c.clocks[2];
      c.advantage[BLACK] = c.clocks[1] > c.clocks[3];
      c.advantageKnown[WHITE] = c.advantageKnown[BLACK] = true;
      if (c.advantage[c.team] != ourAdv)
          c.warnings.push_back("timeadvantage_disagrees_with_clocks using=TimeAdvantage");
  }
  c.advantage[c.team] = ourAdv;
  c.advantageKnown[c.team] = true;
  return c;
}

std::string joint(int board, const std::string& ours) {
  return board == BOARD_A ? "(" + ours + ",pass)" : "(pass," + ours + ")";
}

std::string bool_str(bool b) { return b ? "true" : "false"; }

std::string json_escape(const std::string& s) {
  std::string o;
  for (char ch : s)
      if (ch == '"' || ch == '\\')
          o += '\\', o += ch;
      else
          o += ch;
  return o;
}

std::vector<std::string> sorted_legal(const Position& p) {
  std::vector<std::string> v;
  for (const auto& m : MoveList<LEGAL>(p))
      v.push_back(UCI::move(p, m));
  std::sort(v.begin(), v.end());
  return v;
}

/// One 'go' in arena mode. Always prints exactly one bestmove.
void controller(Search::LimitsType limits) {
  DecisionLog log;
  SeatContext sc = seat_context();
  TeamState& ts = actual();

  if (!PositionError.empty())
      sc.errors.push_back("position " + PositionError);
  if (Options["UCI_Variant"] != "bughouse")
      sc.errors.push_back("variant_not_bughouse variant=" + std::string(Options["UCI_Variant"]));
  if (!Eval::useNNUE)
      sc.errors.push_back("nnue_inactive classical_eval_in_use");

  for (const auto& e : sc.errors)
      sync_cout << "info string hb_error " << e << sync_endl;
  for (const auto& w : sc.warnings)
      sync_cout << "info string hb_warn " << w << sync_endl;

  Verdict verdict = ts.verdict(sc.advantage[WHITE], sc.advantage[BLACK]);
  const Position& pos = ts.pos(sc.board);
  bool onTurn = pos.side_to_move() == sc.us;
  MoveList<LEGAL> legal(pos);
  Move fallback = deterministic_fallback(pos);
  bool coordination = bool(Options["Coordination"]);

  Decision d;
  ProbeResult mainResult;
  bool searched = false;
  if (!onTurn)
      d.pass = true, d.reason = "not_on_turn";
  else if (!legal.size())
      // Mandatory wait: the referee decides whether the game is over; if it
      // is not, a seat without a legal move sits.
      d.pass = true, d.reason = verdict.terminal() ? "no_legal_moves_terminal" : "no_legal_moves";
  else
  {
      Budget budget(limits, coordination);
      if (coordination)
      {
          // Voluntary waiting is decided before any search (PLAN 5.4)
          ProbeResult none;
          CoordinatorContext wctx{ts, sc.seat, sc.team, sc.board, sc.us,
                                  {sc.advantage[WHITE], sc.advantage[BLACK]},
                                  {sc.advantageKnown[WHITE], sc.advantageKnown[BLACK]},
                                  sc.clocksKnown,
                                  {sc.clocks[0], sc.clocks[1], sc.clocks[2], sc.clocks[3]},
                                  verdict, none, fallback, budget, ChildWorker::get(), log};
          Decision w = consider_voluntary_wait(wctx);
          if (w.pass)
              d = w;
      }
  }
  if (onTurn && legal.size() && !d.pass)
  {
      Budget budget(limits, coordination);
      mainResult = run_main_search(ts, sc.board, budget, Phase::MAIN, &log);
      searched = true;
      if (coordination)
      {
          CoordinatorContext ctx{ts, sc.seat, sc.team, sc.board, sc.us,
                                 {sc.advantage[WHITE], sc.advantage[BLACK]},
                                 {sc.advantageKnown[WHITE], sc.advantageKnown[BLACK]},
                                 sc.clocksKnown,
                                 {sc.clocks[0], sc.clocks[1], sc.clocks[2], sc.clocks[3]},
                                 verdict, mainResult, fallback, budget,
                                 ChildWorker::get(), log};
          d = coordinate(ctx);
      }
      else if (mainResult.status == ProbeResult::OK && mainResult.finalMove != MOVE_NONE)
          d.move = mainResult.finalMove, d.reason = "main";
      else
          d.move = fallback, d.reason = "fallback";

      if (!d.pass && (d.move == MOVE_NONE || !legal.contains(d.move)))
      {
          sync_cout << "info string hb_error illegal_decision reason=" << d.reason
                    << " using_fallback" << sync_endl;
          d.move = fallback, d.reason = "fallback_after_illegal";
      }
      log.set("budget_nodes", std::to_string(budget.total_nodes()));
      log.set("budget_ms", std::to_string(budget.total_ms()));
  }

  std::string ours = d.pass ? "pass" : UCI::move(pos, d.move);
  TimePoint elapsed = now() - limits.startTime;

  log.set("seat", seat_name(sc.seat));
  log.set("team", team_name(sc.team));
  log.set("coord", coordination ? "1" : "0");
  log.set("verdict", verdict.result);
  log.set("legal", std::to_string(legal.size()));
  log.set("decision", ours);
  log.set("reason", d.reason);
  log.set("fallback", fallback != MOVE_NONE ? UCI::move(pos, fallback) : "(none)");
  log.set("used_fallback", (!d.pass && d.move == fallback && d.reason.rfind("fallback", 0) == 0) ? "1" : "0");
  if (searched)
  {
      log.set("main_status", status_name(mainResult.status));
      log.set("main_depth", std::to_string(mainResult.depth));
      log.set("main_exact", mainResult.exact ? "1" : "0");
      log.set("main_score_cp", mainResult.exact ? std::to_string(to_cp(mainResult.score)) : "none");
  }

  // Last non-string info line carries the aggregate node count (the arena
  // reads the final 'info ... nodes N' line before bestmove).
  {
      std::ostringstream info;
      info << "info depth " << (searched ? mainResult.depth : 0);
      if (searched && mainResult.exact)
          info << " score " << UCI::value(mainResult.score);
      info << " nodes " << log.total_nodes() << " time " << elapsed;
      sync_cout << info.str() << sync_endl;
  }
  sync_cout << "info string hb_summary " << log.summary(elapsed) << sync_endl;
  if (d.pass && d.wakeAfterMs > 0)
      sync_cout << "info string hb_wake_after_ms=" << d.wakeAfterMs << sync_endl;
  sync_cout << "bestmove " << joint(sc.board, ours) << sync_endl;
  log.flush_jsonl(elapsed);
}

Search::LimitsType parse_go(std::istringstream& is) {
  Search::LimitsType limits;
  limits.startTime = now();
  std::string token;
  while (is >> token)
      if      (token == "wtime")     is >> limits.time[WHITE];
      else if (token == "btime")     is >> limits.time[BLACK];
      else if (token == "winc")      is >> limits.inc[WHITE];
      else if (token == "binc")      is >> limits.inc[BLACK];
      else if (token == "movestogo") is >> limits.movestogo;
      else if (token == "depth")     is >> limits.depth;
      else if (token == "nodes")     is >> limits.nodes;
      else if (token == "movetime")  is >> limits.movetime;
      else if (token == "mate")      is >> limits.mate;
      else if (token == "infinite")  limits.infinite = 1;
  return limits;
}

} // namespace

bool enabled() { return bool(Options["HypeBeast"]); }

void on_hypebeast_option() {
  bool on = bool(Options["HypeBeast"]);
  FrozenHands = on;
  if (on && Options["UCI_Variant"] != "bughouse")
      Options["UCI_Variant"] = std::string("bughouse");
}

void position(std::istringstream& is) {
  wait();
  std::string token, fen;
  is >> token;
  std::string fenA, fenB;
  if (token == "startpos")
  {
      fenA = fenB = bughouse_variant()->startFen;
      is >> token; // "moves"
  }
  else if (token == "fen")
  {
      while (is >> token && token != "moves")
          fen += token + " ";
      size_t bar = fen.find('|');
      if (bar == std::string::npos || fen.find('|', bar + 1) != std::string::npos)
      {
          PositionError = "dual_fen_needs_one_bar";
          sync_cout << "info string hb_error position " << PositionError << sync_endl;
          return;
      }
      fenA = fen.substr(0, bar);
      fenB = fen.substr(bar + 1);
      auto trim = [](std::string& s) {
          s.erase(0, s.find_first_not_of(' '));
          s.erase(s.find_last_not_of(' ') + 1);
      };
      trim(fenA), trim(fenB);
  }
  else
  {
      PositionError = "unknown_position_token " + token;
      sync_cout << "info string hb_error position " << PositionError << sync_endl;
      return;
  }

  PositionError.clear();
  std::string err;
  TeamState& ts = actual();
  if (!ts.reset(fenA, fenB, err))
  {
      PositionError = err;
      ts.reset_startpos();
      sync_cout << "info string hb_error position " << err << sync_endl;
      return;
  }
  while (is >> token)
  {
      if (token.size() < 2 || (token[0] != '1' && token[0] != '2'))
      {
          PositionError = "bad_move_token " + token;
          break;
      }
      if (!ts.play(token[0] - '1', token.substr(1), err))
      {
          PositionError = err;
          break;
      }
  }
  if (!PositionError.empty())
      sync_cout << "info string hb_error position " << PositionError << sync_endl;
}

void go(std::istringstream& is) {
  Search::LimitsType limits = parse_go(is);
  actual();   // make sure the state exists before the thread starts
  spawn([limits]() { controller(limits); });
}

void stop() {
  Budget::Cancel = true;
  Threads.stop = true;
}

void wait() { join_controller(); }

void new_game() {
  wait();
  reset_wait_state();
  actual().reset_startpos();
  PositionError.clear();
}

void hbstate(std::istringstream&) {
  wait();
  TeamState& ts = actual();
  SeatContext sc = seat_context();
  Verdict v = ts.verdict(sc.advantage[WHITE], sc.advantage[BLACK]);
  std::string keyErr;
  bool keysOk = ts.keys_consistent(keyErr);

  std::ostringstream ss;
  ss << "hbstate {\"seat\":\"" << seat_name(sc.seat) << "\",\"team\":\"" << team_name(sc.team)
     << "\",\"board\":" << sc.board << ",\"color\":\"" << (sc.us == WHITE ? "w" : "b") << "\""
     << ",\"moves\":" << ts.move_count()
     << ",\"position_error\":\"" << json_escape(PositionError) << "\""
     << ",\"boards\":[";
  for (int b : {BOARD_A, BOARD_B})
  {
      const Position& p = ts.pos(b);
      std::vector<std::string> moves = sorted_legal(p);
      ss << (b ? "," : "") << "{\"fen\":\"" << ts.referee_fen(b) << "\""
         << ",\"engine_fen\":\"" << ts.fen(b) << "\""
         << ",\"placement\":\"" << ts.placement(b) << "\""
         << ",\"pocket_white\":\"" << ts.pocket(b, WHITE) << "\""
         << ",\"pocket_black\":\"" << ts.pocket(b, BLACK) << "\""
         << ",\"stm\":\"" << (p.side_to_move() == WHITE ? "w" : "b") << "\""
         << ",\"castling\":\"" << ts.castling(b) << "\""
         << ",\"ep\":\"" << ts.legal_ep(b) << "\""
         << ",\"halfmove\":" << ts.halfmove(b)
         << ",\"fullmove\":" << ts.fullmove(b)
         << ",\"repetitions\":" << ts.repetitions(b)
         << ",\"in_check\":" << bool_str(p.checkers())
         << ",\"legal_count\":" << moves.size()
         << ",\"legal\":[";
      for (size_t i = 0; i < moves.size(); ++i)
          ss << (i ? "," : "") << "\"" << moves[i] << "\"";
      ss << "]}";
  }
  ss << "],\"mate\":{\"white\":[" << bool_str(v.mate[WHITE][0]) << "," << bool_str(v.mate[WHITE][1])
     << "],\"black\":[" << bool_str(v.mate[BLACK][0]) << "," << bool_str(v.mate[BLACK][1]) << "]}"
     << ",\"draw\":" << bool_str(v.draw)
     << ",\"advantage\":{\"white\":" << bool_str(v.advantage[WHITE]) << ",\"black\":" << bool_str(v.advantage[BLACK])
     << ",\"white_known\":" << bool_str(sc.advantageKnown[WHITE]) << ",\"black_known\":" << bool_str(sc.advantageKnown[BLACK]) << "}"
     << ",\"first\":\"" << team_name(v.first) << "\""
     << ",\"verdict\":\"" << v.result << "\""
     << ",\"on_turn\":" << bool_str(ts.pos(sc.board).side_to_move() == sc.us)
     << ",\"our_legal\":" << MoveList<LEGAL>(ts.pos(sc.board)).size()
     << ",\"keys_ok\":" << bool_str(keysOk)
     << ",\"key_error\":\"" << json_escape(keyErr) << "\""
     << ",\"frozen_hands\":" << bool_str(FrozenHands)
     << "}";
  sync_cout << ss.str() << sync_endl;
}

// Randomized make/undo restoration and incremental-vs-fresh NNUE check on
// isolated copies of the actual boards (pocket changes included).
void hbmakeundo(std::istringstream& is) {
  wait();
  int iterations = 20, plies = 12;
  uint64_t seed = 1;
  std::string token;
  while (is >> token)
      if (token == "iterations") is >> iterations;
      else if (token == "plies") is >> plies;
      else if (token == "seed")  is >> seed;
  PRNG rng(seed ? seed : 1);

  const TeamState& base = actual();
  int checks = 0, evals = 0;
  std::string failure;
  auto fresh_eval = [](const Position& p) {
      StateListPtr st(new std::deque<StateInfo>(1));
      Position f;
      f.set(p.variant(), p.fen(), false, &st->back(), Threads.main());
      return std::make_pair(Eval::NNUE::evaluate(f), f.key());
  };

  for (int it = 0; it < iterations && failure.empty(); ++it)
  {
      TeamState copy(base);
      int b = it % 2;
      // Sometimes simulate an arrival first: the hand change must refresh NNUE
      if (rng.rand<unsigned>() % 2)
      {
          PieceType pts[] = {PAWN, KNIGHT, BISHOP, ROOK, QUEEN};
          Color c = rng.rand<unsigned>() % 2 ? WHITE : BLACK;
          copy.add_to_pocket(b, make_piece(c, pts[rng.rand<unsigned>() % 5]));
      }
      Position& p = copy.pos(b);
      std::string fen0 = p.fen();
      Key key0 = p.key();
      Value eval0 = Eval::useNNUE ? Eval::NNUE::evaluate(p) : VALUE_ZERO;
      if (Eval::useNNUE)
      {
          auto fr = fresh_eval(p);
          ++evals;
          if (fr.first != eval0)
              failure = "root eval incremental=" + std::to_string(eval0) + " fresh=" + std::to_string(fr.first) + " fen=" + fen0;
          if (fr.second != key0)
              failure = "root key differs from fresh fen=" + fen0;
      }

      std::vector<Move> played;
      std::deque<StateInfo> sts;
      for (int i = 0; i < plies && failure.empty(); ++i)
      {
          MoveList<LEGAL> ml(p);
          if (!ml.size())
              break;
          Move m = *(ml.begin() + rng.rand<unsigned>() % ml.size());
          sts.emplace_back();
          p.do_move(m, sts.back());
          played.push_back(m);
          ++checks;
          if (Eval::useNNUE)
          {
              Value inc = Eval::NNUE::evaluate(p);
              auto fr = fresh_eval(p);
              ++evals;
              if (inc != fr.first)
                  failure = "eval incremental=" + std::to_string(inc) + " fresh=" + std::to_string(fr.first) + " fen=" + p.fen();
          }
      }
      while (!played.empty())
      {
          p.undo_move(played.back());
          played.pop_back();
      }
      if (failure.empty() && (p.fen() != fen0 || p.key() != key0))
          failure = "undo did not restore fen0=" + fen0 + " now=" + p.fen();
      if (failure.empty() && Eval::useNNUE && Eval::NNUE::evaluate(p) != eval0)
          failure = "eval after undo differs fen=" + fen0;
  }
  // The actual state must be unchanged
  std::string err;
  if (failure.empty() && !actual().keys_consistent(err))
      failure = "actual state changed: " + err;

  if (failure.empty())
      sync_cout << "hbmakeundo ok iterations=" << iterations << " moves=" << checks
                << " evals=" << evals << " nnue=" << bool_str(Eval::useNNUE) << sync_endl;
  else
      sync_cout << "hbmakeundo fail " << failure << sync_endl;
}

// Child-probe self-test: runs K sequential child searches against one shared
// budget, exactly as the coordinator would, then prints 'hbprobe done ...'.
void hbprobe(std::istringstream& is) {
  Search::LimitsType limits;
  limits.startTime = now();
  int count = 1;
  ProbeRequest base;
  base.phase = Phase::PROBES;
  bool coord = true;
  std::string token, fen;
  while (is >> token)
      if      (token == "nodes")    is >> limits.nodes;
      else if (token == "movetime") is >> limits.movetime;
      else if (token == "count")    is >> count;
      else if (token == "depth")    is >> base.depth;
      else if (token == "maxnodes") is >> base.maxNodes;
      else if (token == "maxtime")  is >> base.maxTimeMs;
      else if (token == "clear")    { int c; is >> c; base.clear = c != 0; }
      else if (token == "coord")    { int c; is >> c; coord = c != 0; }
      else if (token == "hash")     { size_t mb; is >> mb; ChildWorker::get().set_hash_mb(mb); }
      else if (token == "phase")
      {
          is >> token;
          base.phase = token == "discovery" ? Phase::DISCOVERY : token == "main" ? Phase::MAIN : Phase::PROBES;
      }
      else if (token == "fen")
      {
          while (is >> token)
              fen += (fen.empty() ? "" : " ") + token;
      }

  actual();
  spawn([limits, count, base, coord, fen]() {
      TeamState& ts = actual();
      SeatContext sc = seat_context();
      ProbeRequest req = base;
      req.fen = fen.empty() ? ts.fen(sc.board) : fen;
      Move fallback = deterministic_fallback(ts.pos(sc.board));
      Budget budget(limits, coord);
      DecisionLog log;
      for (int i = 0; i < count; ++i)
      {
          req.tag = "selftest" + std::to_string(i);
          ProbeResult r = ChildWorker::get().run(req, budget, &log);
          sync_cout << "hbprobe " << i << " " << result_json(r) << sync_endl;
      }
      TimePoint elapsed = now() - limits.startTime;
      sync_cout << "hbprobe done total_nodes=" << budget.nodes_used()
                << " budget_nodes=" << budget.total_nodes()
                << " budget_ms=" << budget.total_ms()
                << " elapsed_ms=" << elapsed
                << " cancelled=" << bool_str(Budget::cancelled())
                << " fallback=" << (fallback != MOVE_NONE ? UCI::move(ts.pos(sc.board), fallback) : "(none)")
                << " child_searches_total=" << ChildWorker::get().searches()
                << sync_endl;
  });
}

void shutdown() {
  stop();
  wait();
  ChildWorker::shutdown();
}

} // namespace Stockfish::HB::Arena
