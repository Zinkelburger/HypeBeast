/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

// One shared search budget per 'go', the main search runner, and the
// sequential single-threaded child-search worker the coordinator uses.

#ifndef HB_PROBE_H_INCLUDED
#define HB_PROBE_H_INCLUDED

#include <atomic>
#include <string>
#include <vector>

#include "search.h"
#include "thread.h"
#include "types.h"

namespace Stockfish::HB {

class TeamState;
class DecisionLog;

// COMPARE: the final root-restricted comparison (or main extension) search.
// It has the same cumulative cap as PROBES, so it absorbs whatever the
// earlier phases left unused.
enum class Phase : int { MAIN, DISCOVERY, PROBES, COMPARE, RESERVE, NB };
const char* phase_name(Phase p);

/// Budget fractions. Cumulative: phase k may use everything up to the sum of
/// slices 0..k minus what earlier phases already used, so unused budget flows
/// forward. The reserve is never granted to a search. The absolute deadline
/// and total node count override all slices.
struct Slices {
  double main = 0.60, discovery = 0.10, probes = 0.25, reserve = 0.05;
};

class Budget {
public:
  // go: limits parsed from 'go' (startTime = when 'go' arrived).
  // coordination=false: the main search gets the full budget.
  Budget(const Search::LimitsType& go, bool coordination, Slices s = Slices());

  bool node_limited() const { return totalNodes > 0; }
  bool time_limited() const { return totalMs > 0; }
  // wtime/btime/infinite/depth-only go: passed through to the main search;
  // children get no budget.
  bool passthrough() const { return !node_limited() && !time_limited(); }

  // Grant for one search in phase p. nodes/movetimeMs are 0 when that
  // dimension is unlimited. False if the phase (or the total) is exhausted.
  bool grant(Phase p, uint64_t& nodes, TimePoint& movetimeMs) const;
  void charge(uint64_t nodes) { usedNodes += nodes; }

  uint64_t nodes_used() const { return usedNodes; }
  uint64_t total_nodes() const { return totalNodes; }
  TimePoint total_ms() const { return totalMs; }
  TimePoint elapsed() const { return now() - start; }
  TimePoint start_time() const { return start; }
  bool exhausted() const;
  const Search::LimitsType& go_limits() const { return go; }
  bool coordination() const { return coord; }

  // Cooperative cancellation ('stop'/'quit' while the controller runs).
  static std::atomic<bool> Cancel;
  static bool cancelled() { return Cancel.load(); }

private:
  double cumulative(Phase p) const;
  Search::LimitsType go;
  bool coord;
  Slices slices;
  uint64_t totalNodes = 0, usedNodes = 0;
  TimePoint totalMs = 0, start = 0;
};

/// Request for one isolated child search.
struct ProbeRequest {
  std::string fen;                        // bughouse FEN of the local board (validated)
  std::vector<std::string> searchMoves;   // optional UCI root restriction
  Depth depth = 0;                        // target depth, 0 = iterative deepening to budget
  uint64_t maxNodes = 0;                  // per-probe cap (0 = phase grant only)
  TimePoint maxTimeMs = 0;                // per-probe cap (0 = phase grant only)
  Phase phase = Phase::PROBES;
  bool clear = true;                      // clear child TT and heuristics first
  std::string tag;                        // label for the decision log
};

/// Result of a main or child search. Scores are internal Values from the
/// side to move at the root of that search.
struct ProbeResult {
  enum Status { OK, INVALID_FEN, NO_LEGAL_MOVES, NO_BUDGET, CANCELLED, BAD_SEARCHMOVES };
  Status status = NO_BUDGET;

  // exact: at least one root iteration completed (its score is exact) and,
  // if a target depth was requested, it was reached. Never true for a bound.
  bool exact = false;
  bool reachedDepth = false;  // depth>0 requested and reached
  bool interrupted = false;   // stopped by budget/cancel before finishing
  Depth depth = 0;            // last completed iteration
  Value score = VALUE_NONE;   // exact score of the last completed iteration
  Move move = MOVE_NONE;      // best move of the last completed iteration
  std::vector<Move> pv;

  // Raw final state, as upstream would report it (may come from a partial
  // iteration; finalBound tells whether finalScore is a bound).
  Move  finalMove = MOVE_NONE;
  Value finalScore = VALUE_NONE;
  Bound finalBound = BOUND_NONE;
  bool  finalFromPartial = false;

  // Exact (move, score) of every MultiPV line of the last completed
  // iteration, and the first root moves in final order (main pool only).
  std::vector<std::pair<Move, Value>> lines;
  std::vector<Move> rootOrder;

  // UCI spellings (filled from the search's own root position)
  std::string moveUci, finalMoveUci;
  std::vector<std::string> pvUci;

  uint64_t nodes = 0;
  TimePoint ms = 0;           // wall time including clearing
  TimePoint clearMs = 0;
  uint64_t grantedNodes = 0;
  TimePoint grantedMs = 0;
  std::string fen;

  bool usable_exact() const { return status == OK && exact; }
};

const char* status_name(ProbeResult::Status s);
// Internal value -> UCI centipawns (mate scores map to +/-(100000 - plies)).
int to_cp(Value v);
// Clipped to [-2000, 2000]; local mate reports map to the endpoints.
int finite_cp(Value v);
std::string result_json(const ProbeResult& r);

/// Main search on our actual board (thread pool, main TT, actual history).
// searchMoves restricts the root; multiPV > 1 gives every line an exact score.
// The main TT and main-thread heuristics are used (same context and hands).
ProbeResult run_main_search(const TeamState& ts, int board, Budget& budget,
                            Phase phase, DecisionLog* log,
                            const std::vector<Move>& searchMoves = {},
                            size_t multiPV = 1, const std::string& tag = "main");

/// Sequential, reusable, single-threaded child worker. It owns a separate
/// MainThread (own heuristics) and a separate TT, swapped in only for the
/// duration of a child search, so the main search's TT and histories are
/// untouched. Each search runs on a Position rebuilt from req.fen with its
/// own StateInfo storage; the actual game state is never touched.
class ChildWorker {
public:
  static ChildWorker& get();
  static void shutdown();

  ProbeResult run(const ProbeRequest& req, Budget& budget, DecisionLog* log);

  void set_hash_mb(size_t mb);
  size_t hash_mb() const { return ttMb; }
  uint64_t searches() const { return count; }

private:
  ChildWorker();
  ~ChildWorker();
  MainThread* thread = nullptr;
  std::vector<Thread*> pool;     // {thread}
  size_t ttMb = 4;
  bool ttReady = false;
  uint64_t count = 0;
};

} // namespace Stockfish::HB

#endif // #ifndef HB_PROBE_H_INCLUDED
