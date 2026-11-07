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
#include <sstream>

#include "apiutil.h"
#include "hb_decisionlog.h"
#include "hb_probe.h"
#include "hb_team_state.h"
#include "movegen.h"
#include "thread.h"
#include "tt.h"
#include "uci.h"

namespace Stockfish::HB {

std::atomic<bool> Budget::Cancel{false};

namespace {

TranspositionTable ChildTT;   // the child worker's own table (swapped with TT)
ChildWorker* Worker = nullptr;

// RAII: install the child thread and table for the duration of one search.
struct ChildScope {
  std::vector<Thread*>& pool;
  Search::HBHooks saved;
  ChildScope(std::vector<Thread*>& p) : pool(p), saved(Search::HBHook) {
      Threads.main()->wait_for_search_finished();
      static_cast<std::vector<Thread*>&>(Threads).swap(pool);
      TT.swap(ChildTT);
      Search::HBHook.capture = true;
      Search::HBHook.silent = true;
      Search::HBHook.multiPV = 0;
  }
  ~ChildScope() {
      Threads.main()->wait_for_search_finished();
      TT.swap(ChildTT);
      static_cast<std::vector<Thread*>&>(Threads).swap(pool);
      Search::HBHook = saved;
  }
};

void fill_result(ProbeResult& r, const Position& root, Depth targetDepth) {
  const Search::HBSearchResult& R = Search::HBResult;
  r.nodes = R.nodes;
  r.depth = R.completedDepth;
  r.finalMove = R.finalMove;
  r.finalScore = R.finalScore;
  r.finalMoveUci = R.finalMove != MOVE_NONE ? UCI::move(root, R.finalMove) : "(none)";
  r.lines = R.completedDepth > 0 ? R.lines : std::vector<std::pair<Move, Value>>();
  r.rootOrder = R.rootOrder;

  if (R.completedDepth > 0 && !R.exactPV.empty() && R.exactScore != -VALUE_INFINITE)
  {
      r.score = R.exactScore;
      r.move = R.exactPV[0];
      r.pv = R.exactPV;
      r.moveUci = UCI::move(root, r.move);
      // PV spellings need the moves played out on a scratch copy
      StateListPtr states(new std::deque<StateInfo>(1));
      Position p;
      p.set(root.variant(), root.fen(), false, &states->back(), root.this_thread());
      for (Move m : r.pv)
      {
          if (!p.pseudo_legal(m) || !p.legal(m))
              break;
          r.pvUci.push_back(UCI::move(p, m));
          states->emplace_back();
          p.do_move(m, states->back());
      }
      r.exact = true;
  }
  r.reachedDepth = targetDepth > 0 && R.completedDepth >= targetDepth;
  if (targetDepth > 0 && !r.reachedDepth)
  {
      r.exact = false;
      r.interrupted = true;
  }
  if (Budget::cancelled())
      r.interrupted = true;

  r.finalFromPartial = !(r.exact && R.finalMove == r.move && R.finalScore == r.score);
  if (R.finalScore == -VALUE_INFINITE)
      r.finalBound = BOUND_NONE;
  else if (!r.finalFromPartial)
      r.finalBound = BOUND_EXACT;
  else
      r.finalBound =  R.finalScore >= R.finalBeta  ? BOUND_LOWER
                    : R.finalScore <= R.finalAlpha ? BOUND_UPPER
                                                   : BOUND_EXACT;
}

} // namespace

const char* phase_name(Phase p) {
  switch (p)
  {
  case Phase::MAIN:      return "main";
  case Phase::DISCOVERY: return "discovery";
  case Phase::PROBES:    return "probes";
  case Phase::COMPARE:   return "compare";
  case Phase::RESERVE:   return "reserve";
  default:               return "?";
  }
}

const char* status_name(ProbeResult::Status s) {
  switch (s)
  {
  case ProbeResult::OK:              return "ok";
  case ProbeResult::INVALID_FEN:     return "invalid_fen";
  case ProbeResult::NO_LEGAL_MOVES:  return "no_legal_moves";
  case ProbeResult::NO_BUDGET:       return "no_budget";
  case ProbeResult::CANCELLED:       return "cancelled";
  case ProbeResult::BAD_SEARCHMOVES: return "bad_searchmoves";
  default:                           return "?";
  }
}

int to_cp(Value v) {
  if (v == VALUE_NONE || std::abs(v) >= VALUE_INFINITE)
      return 0;
  if (std::abs(v) < VALUE_MATE_IN_MAX_PLY)
      return v * 100 / PawnValueEg;
  int plies = VALUE_MATE - std::abs(v);
  return v > 0 ? 100000 - plies : -100000 + plies;
}

int finite_cp(Value v) {
  if (v != VALUE_NONE && std::abs(v) >= VALUE_MATE_IN_MAX_PLY && std::abs(v) < VALUE_INFINITE)
      return v > 0 ? 2000 : -2000;
  return std::clamp(to_cp(v), -2000, 2000);
}

std::string result_json(const ProbeResult& r) {
  auto boundName = [](Bound b) {
      return b == BOUND_EXACT ? "exact" : b == BOUND_LOWER ? "lower" : b == BOUND_UPPER ? "upper" : "none";
  };
  std::ostringstream ss;
  ss << "{\"status\":\"" << status_name(r.status) << "\""
     << ",\"exact\":" << (r.exact ? "true" : "false")
     << ",\"reached_depth\":" << (r.reachedDepth ? "true" : "false")
     << ",\"interrupted\":" << (r.interrupted ? "true" : "false")
     << ",\"depth\":" << r.depth
     << ",\"score\":" << (r.exact ? std::to_string(to_cp(r.score)) : "null")
     << ",\"move\":\"" << (r.moveUci.empty() ? "(none)" : r.moveUci) << "\""
     << ",\"pv\":[";
  for (size_t i = 0; i < r.pvUci.size(); ++i)
      ss << (i ? "," : "") << "\"" << r.pvUci[i] << "\"";
  ss << "],\"final_move\":\"" << (r.finalMoveUci.empty() ? "(none)" : r.finalMoveUci) << "\""
     << ",\"final_score\":" << (r.finalBound != BOUND_NONE ? std::to_string(to_cp(r.finalScore)) : "null")
     << ",\"final_bound\":\"" << boundName(r.finalBound) << "\""
     << ",\"final_partial\":" << (r.finalFromPartial ? "true" : "false")
     << ",\"nodes\":" << r.nodes
     << ",\"ms\":" << r.ms
     << ",\"clear_ms\":" << r.clearMs
     << ",\"granted_nodes\":" << r.grantedNodes
     << ",\"granted_ms\":" << r.grantedMs
     << ",\"fen\":\"" << r.fen << "\"}";
  return ss.str();
}

// ------------------------------------------------------------------ Budget

Budget::Budget(const Search::LimitsType& g, bool coordination, Slices s)
  : go(g), coord(coordination), slices(s) {
  start = go.startTime ? go.startTime : now();
  if (!go.use_time_management() && !go.infinite)
  {
      totalNodes = go.nodes > 0 ? uint64_t(go.nodes) : 0;
      totalMs = go.movetime > 0 ? go.movetime : 0;
  }
}

double Budget::cumulative(Phase p) const {
  if (!coord)
      return 1.0;
  double c = slices.main;
  if (p >= Phase::DISCOVERY) c += slices.discovery;
  if (p >= Phase::PROBES)    c += slices.probes;   // COMPARE shares this cap
  if (p >= Phase::RESERVE)   c += slices.reserve;
  return std::min(c, 1.0);
}

bool Budget::exhausted() const {
  if (cancelled())
      return true;
  if (node_limited() && usedNodes >= totalNodes)
      return true;
  if (time_limited() && elapsed() >= totalMs)
      return true;
  return false;
}

bool Budget::grant(Phase p, uint64_t& nodes, TimePoint& movetimeMs) const {
  nodes = 0;
  movetimeMs = 0;
  if (cancelled())
      return false;
  if (passthrough())
      return p == Phase::MAIN;
  // The reserve is held back for the response, never searched.
  if (coord && p == Phase::RESERVE)
      return false;
  double c = cumulative(p);
  if (node_limited())
  {
      uint64_t cap = uint64_t(std::floor(c * double(totalNodes)));
      if (p == Phase::MAIN)
          cap = std::max<uint64_t>(cap, 1);   // the main search always gets to start
      cap = std::min(totalNodes, cap);
      if (usedNodes >= cap)
          return false;
      nodes = cap - usedNodes;
  }
  if (time_limited())
  {
      TimePoint slice = TimePoint(std::floor(c * double(totalMs)));
      if (p == Phase::MAIN)
          slice = std::max<TimePoint>(slice, 1);
      TimePoint deadline = start + std::min(totalMs, slice);
      TimePoint left = deadline - now();
      if (left < 1)
          return false;
      movetimeMs = left;
  }
  return true;
}

// ------------------------------------------------------------- main search

ProbeResult run_main_search(const TeamState& ts, int board, Budget& budget,
                            Phase phase, DecisionLog* log,
                            const std::vector<Move>& searchMoves, size_t multiPV,
                            const std::string& tag) {
  ProbeResult r;
  TimePoint t0 = now();
  const Position& actual = ts.pos(board);
  r.fen = actual.fen();

  if (!MoveList<LEGAL>(actual).size())
  {
      r.status = ProbeResult::NO_LEGAL_MOVES;
      if (log) log->add(phase, tag, r);
      return r;
  }
  if (Budget::cancelled())
  {
      r.status = ProbeResult::CANCELLED;
      if (log) log->add(phase, tag, r);
      return r;
  }

  Search::LimitsType limits = budget.go_limits();
  limits.searchmoves = searchMoves;
  limits.banmoves.clear();
  if (phase != Phase::MAIN)
  {
      // A later search in the same go: deadline and node budget come from
      // the shared budget only; never a fresh movetime or depth.
      limits.depth = 0;
      limits.mate = 0;
      limits.infinite = 0;
  }
  limits.startTime = budget.start_time();
  if (budget.passthrough() && phase != Phase::MAIN)
  {
      r.status = ProbeResult::NO_BUDGET;
      if (log) log->add(phase, tag, r);
      return r;
  }
  if (!budget.passthrough())
  {
      uint64_t n;
      TimePoint ms;
      if (!budget.grant(phase, n, ms))
      {
          r.status = ProbeResult::NO_BUDGET;
          if (log) log->add(phase, tag, r);
          return r;
      }
      limits.nodes = int64_t(n);
      // movetime is measured from limits.startTime (the 'go' arrival)
      limits.movetime = ms ? (now() - limits.startTime) + ms : 0;
      r.grantedNodes = n;
      r.grantedMs = ms;
  }

  Search::HBHooks saved = Search::HBHook;
  Search::HBHook.capture = true;
  Search::HBHook.silent = phase != Phase::MAIN;
  Search::HBHook.multiPV = multiPV;
  Search::HBResult = Search::HBSearchResult();

  StateListPtr states = ts.history_copy(board);
  // Node checks start fresh (upstream carries callsCnt over between searches,
  // which lets a node-limited search overshoot by up to 1024 nodes).
  Threads.main()->callsCnt = 0;
  Threads.start_thinking(const_cast<Position&>(actual), states, limits);
  if (Budget::cancelled())
      Threads.stop = true;
  Threads.main()->wait_for_search_finished();
  Search::HBHook = saved;

  r.status = ProbeResult::OK;
  fill_result(r, actual, limits.depth);
  r.ms = now() - t0;
  budget.charge(r.nodes);
  if (log) log->add(phase, tag, r);
  return r;
}

// ------------------------------------------------------------ ChildWorker

ChildWorker::ChildWorker() {
  thread = new MainThread(0);
  pool.push_back(thread);
}

ChildWorker::~ChildWorker() {
  delete thread;   // joins the native thread
}

ChildWorker& ChildWorker::get() {
  if (!Worker)
      Worker = new ChildWorker();
  return *Worker;
}

void ChildWorker::shutdown() {
  delete Worker;
  Worker = nullptr;
}

void ChildWorker::set_hash_mb(size_t mb) {
  ttMb = std::max<size_t>(1, mb);
  ttReady = false;
}

ProbeResult ChildWorker::run(const ProbeRequest& req, Budget& budget, DecisionLog* log) {
  ProbeResult r;
  TimePoint t0 = now();
  r.fen = req.fen;
  auto done = [&](ProbeResult::Status s) {
      r.status = s;
      r.ms = now() - t0;
      if (log) log->add(req.phase, req.tag, r);
      return r;
  };

  if (Budget::cancelled())
      return done(ProbeResult::CANCELLED);
  if (FEN::validate_fen(req.fen, bughouse_variant(), false) != FEN::FEN_OK)
      return done(ProbeResult::INVALID_FEN);

  uint64_t nodes;
  TimePoint ms;
  if (budget.passthrough() || !budget.grant(req.phase, nodes, ms))
      return done(ProbeResult::NO_BUDGET);
  if (req.maxNodes)
      nodes = nodes ? std::min(nodes, req.maxNodes) : req.maxNodes;
  if (req.maxTimeMs)
      ms = ms ? std::min(ms, req.maxTimeMs) : req.maxTimeMs;
  r.grantedNodes = nodes;
  r.grantedMs = ms;

  Search::LimitsType limits;
  {
      ChildScope scope(pool);

      TimePoint tc = now();
      if (!ttReady)
      {
          TT.resize(ttMb);    // also clears
          ttReady = true;
          Threads.clear();
      }
      else if (req.clear || count == 0)
      {
          TT.clear();
          Threads.clear();
      }
      r.clearMs = now() - tc;

      StateListPtr states(new std::deque<StateInfo>(1));
      Position p;
      p.set(bughouse_variant(), req.fen, false, &states->back(), Threads.main());
      if (!MoveList<LEGAL>(p).size())
          return done(ProbeResult::NO_LEGAL_MOVES);
      for (const std::string& s : req.searchMoves)
      {
          std::string t = s;
          Move m = UCI::to_move(p, t);
          if (m == MOVE_NONE)
              return done(ProbeResult::BAD_SEARCHMOVES);
          limits.searchmoves.push_back(m);
      }

      // Charge clearing time against the deadline as well
      if (ms)
      {
          TimePoint spent = now() - t0;
          if (ms <= spent)
              return done(ProbeResult::NO_BUDGET);
      }
      limits.startTime = t0;
      limits.nodes = int64_t(nodes);
      limits.movetime = ms;
      limits.depth = req.depth;
      if (!limits.nodes && !limits.movetime && !limits.depth)
          return done(ProbeResult::NO_BUDGET); // never an unbounded child

      Search::HBResult = Search::HBSearchResult();
      Threads.main()->callsCnt = 0;
      Threads.start_thinking(p, states, limits);
      if (Budget::cancelled())
          Threads.stop = true;
      Threads.main()->wait_for_search_finished();

      r.status = ProbeResult::OK;
      fill_result(r, p, req.depth);
      ++count;
  }
  budget.charge(r.nodes);
  r.ms = now() - t0;
  if (log) log->add(req.phase, req.tag, r);
  return r;
}

} // namespace Stockfish::HB
