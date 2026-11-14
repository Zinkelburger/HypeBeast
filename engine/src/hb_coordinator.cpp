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
#include <cstdlib>
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
  // A search with a target depth is exact only if it reached it; one to a
  // node cap is exact from its first completed iteration.
  if (!r.usable_exact())
      return false;
  out = finite_cp(stm == ours ? r.score : -r.score);
  return true;
}

/// v6: partner-board probes deepen to a node cap instead of stopping at
/// ProbeDepth. A mate that needs a new piece is usually 3 to 5 moves long,
/// which a depth-3 search cannot see.
bool deep_probes() { return int(Options["HBPriceShare"]) > 0; }

/// A board with one more piece in a hand (`with`) against the same board
/// without it (`base`), both from `ours`'s side. Two searches to a node cap
/// end at different depths, so they are compared at the deepest depth both
/// completed. A forced mate found by either one stands, whatever its depth.
bool pair_values(const ProbeResult& base, const ProbeResult& with, Color stm, Color ours, int& v0, int& v1) {
  if (!team_value(base, stm, ours, v0) || !team_value(with, stm, ours, v1))
      return false;
  if (!deep_probes() || base.status != ProbeResult::OK || with.status != ProbeResult::OK)
      return true;
  const int sign = stm == ours ? 1 : -1;
  int d = std::min({int(base.depth), int(with.depth), int(base.depthScores.size()) - 1, int(with.depthScores.size()) - 1});
  while (d > 0 && (base.depthScores[d] == VALUE_NONE || with.depthScores[d] == VALUE_NONE))
      --d;
  if (d < 1)
      return false;
  const bool baseMate = mate_plies(base.score) != 0, withMate = mate_plies(with.score) != 0;
  if (!baseMate)
      v0 = finite_cp(Value(sign * int(base.depthScores[d])));
  if (!withMate)
      v1 = finite_cp(Value(sign * int(with.depthScores[d])));
  // The board is decided without the piece. The piece undoes that only if
  // its own search looked as deep as the one that found the mate.
  if (baseMate && !withMate && with.depth < base.depth)
      v1 = v0;
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
  int feed = 0;                          // v8j: cp for our partner's board from what this move hands over (HBTellRoot)
  int S0 = 0;                            // S without it
  int tier = 0;                          // SAFE, SOFT or CERTAIN
  bool probeFatal = false;               // a probe scored an enemy arrival as mate
  std::string exposure;
};

struct ProbeCache {
  std::map<std::string, ProbeResult> results;
  int requested = 0, run = 0;
  // deep: a partner-board probe, deepened to its share of the go (v6).
  const ProbeResult& get(CoordinatorContext& ctx, const std::string& fen, Phase phase, const std::string& tag,
                         bool deep = false) {
      auto it = results.find(fen);
      ++requested;
      if (it != results.end() && it->second.status != ProbeResult::NO_BUDGET && it->second.status != ProbeResult::CANCELLED)
          return it->second;
      ProbeRequest req;
      req.fen = fen;
      req.depth = Coef::ProbeDepth;
      req.maxNodes = Coef::ProbeNodeCap;
      if (deep && deep_probes())
      {
          const double share = double(int(Options["HBPriceShare"])) / 1000.0;
          req.depth = 0;
          req.maxNodes = ctx.budget.share_nodes(share);
          req.maxTimeMs = ctx.budget.share_ms(share);
      }
      req.phase = phase;
      // One clean start per go is enough: later probes differ in board or
      // hand, so they cannot read each other's table entries.
      req.clear = run == 0 || (!bool(Options["HBWorlds"]) && req.depth != 0);
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
bool TableDirty = false; // the main table holds scores searched with a price set (HBPriceKeepTable)

bool any_price() {
  for (Color c : {WHITE, BLACK})
      for (PieceType t : DeliveryTypes)
          if (FedGain[c][t])
              return true;
  return false;
}
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
/// needLead=false (v5): every move loses at once, so sitting costs nothing
/// that moving would keep, and only the reserve is asked for.
bool stall_ok(const CoordinatorContext& ctx, bool needLead = true) {
  if (!bool(Options["HBStall"]) || !ctx.clocksKnown)
      return false;
  const int pb = 1 - ctx.board;
  int ours = clock_of(ctx, ctx.board, ctx.us);
  int theirs = clock_of(ctx, pb, ctx.us);
  bool partnerFirst = ctx.actual.pos(pb).side_to_move() == ~ctx.us;
  if (ours < Coef::StallReserveMs)
      return false;
  if (!needLead && bool(Options["HBHold"]))
      return true;
  return ours - theirs >= Coef::StallLeadMs + (partnerFirst ? Coef::StallPartnerMs : 0);
}

// Why a seat is sitting on purpose.
//   EXPOSED: its move would let the opponents capture and drop a mate (v3).
//   MATED:   its own search sees a forced mate against it (v5).
//   PARTNER: its partner has a forced mate on the other board (v5).
//   FEED:    its best line loses a piece that mates on the partner board (v6).
enum HoldKind { HOLD_NONE, HOLD_EXPOSED, HOLD_MATED, HOLD_PARTNER, HOLD_FEED };

struct HoldState {
  int kind = HOLD_NONE;
  size_t moves = 0;        // game length at the last decision to hold
  bool needLead = true;    // EXPOSED: the stall needs a clock lead to go on
  std::string fen;         // MATED, PARTNER: our board, hands included, when the hold began
  int floorMs = 0;         // MATED: move again when our clock is down to this
  int clockStart = 0;      // PARTNER: our clock when this turn's wait began
};
HoldState Hold;
// One feed hold for each turn of ours, measured from our clock at its start.
struct FeedHoldState {
  std::string turn;
  int clockStart = 0;
};
FeedHoldState Feed;
int PartnerBase = 0;        // this go's probe of the partner board, our team's view
bool PartnerBaseOk = false;
bool GuardFatal[PIECE_TYPE_NB] = {};   // HBMateGuard: at our last go, losing this type mated our partner
size_t GuardPlies = 0;                 // plies of both boards at that go
// This go's probes say that one more piece of this type mates on the partner
// board: for the opponents (a piece we lose) or for our partner (one we win).
bool TheirsMate[PIECE_TYPE_NB] = {};
bool OursMate[PIECE_TYPE_NB] = {};
std::string WakeTurnKey;    // the turn whose one wake is booked, and
int WakeClock = 0;          // our clock when it comes
// Our partner is on turn and mated by force, so it is sitting: nothing we
// lose can be dropped on its board, and it will send us nothing.
bool PartnerHeld = false;

// What each piece type is worth to a partner that sits mated by force: with
// it in hand the mate is gone (cp > 0), it changes nothing (0), or the probe
// did not get deep enough to say (-1). The partner's board does not change
// while it sits, so this is measured once for each such board.
struct RescueMemo {
  std::string fen;                       // the partner board, hands included
  int cp[PIECE_TYPE_NB] = {};
};
RescueMemo Rescue;

// What the go before saw of the partner board, to tell a partner that is
// thinking from one that is sitting: a seat on turn moves within HoldMoveMs.
struct PartnerSeen {
  bool valid = false;
  bool onTurn = false;
  size_t moves = 0;        // moves played on the partner board
  int clock = 0;           // our partner's clock
};
PartnerSeen Seen;

struct MainMemo {
  std::string fen;
  uint64_t nodes = 0;
  TimePoint ms = 0;
  ProbeResult result;
};
MainMemo Memo;

std::string turn_key(const TeamState& ts, int board);

/// Sitting while our partner mates is safe only ahead on the clock of the
/// same-colour seat on the other board, the one being mated: it may sit too,
/// and then the lower clock of the two runs out first.
bool partner_hold_ok(const CoordinatorContext& ctx) {
  int ours = clock_of(ctx, ctx.board, ctx.us);
  int theirs = clock_of(ctx, 1 - ctx.board, ctx.us);
  return ours >= Coef::PartnerHoldReserveMs && ours - theirs >= Coef::PartnerHoldLeadMs;
}

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
  if (PartnerHeld)
      return tier;
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

// ---- partner talk (PARTNER_TALK.md)

/// HBTell is "off" or paradigm names joined by '+'.
bool tell_has(const std::string& mode, const char* name) {
  std::istringstream ss(mode);
  std::string part;
  while (std::getline(ss, part, '+'))
      if (part == name)
          return true;
  return false;
}

bool parse_int(const std::string& s, int& out) {
  if (s.empty())
      return false;
  char* end = nullptr;
  long v = std::strtol(s.c_str(), &end, 10);
  if (end == s.c_str() || *end != '\0')
      return false;
  out = int(std::clamp(v, -1000000L, 1000000L));
  return true;
}

/// A partner's message: its n and its worth section. Index 0 is the teller's
/// '+' side (a piece in its hand), 1 its '-' side (one in its opponent's hand).
struct HeardTell {
  int n = 0;
  // The teller's own score for its board and a forced mate there in plies
  // (+: it mates), from the message's score= and mate= when it has them.
  bool hasScore = false;
  int score = 0, mateTold = 0;
  // The judged move's value on the teller's board with nothing arriving (base=).
  bool hasBase = false;
  int base = 0;
  bool has[2][PIECE_TYPE_NB] = {};
  bool mate[2][PIECE_TYPE_NB] = {};
  int cp[2][PIECE_TYPE_NB] = {};
};

/// "v1 n=<n> [worth <entries>] [other sections]". False when the text is not
/// a v1 message with an n. Entries that do not read as [+-]<type>=<cp or #>
/// are skipped: an absent type counts as 0.
bool parse_tell(const std::string& text, HeardTell& h) {
  std::istringstream ss(text);
  std::string tok;
  if (!(ss >> tok) || tok != "v1")
      return false;
  if (!(ss >> tok) || tok.rfind("n=", 0) != 0 || !parse_int(tok.substr(2), h.n))
      return false;
  bool inWorth = false;
  while (ss >> tok)
  {
      if (tok == "worth" || tok == "plan" || tok == "menu" || tok == "odds" || tok == "lines")
      {
          inWorth = tok == "worth";
          continue;
      }
      if (tok.rfind("score=", 0) == 0)
      {
          h.hasScore = parse_int(tok.substr(6), h.score);
          continue;
      }
      if (tok.rfind("mate=", 0) == 0)
      {
          parse_int(tok.substr(5), h.mateTold);
          continue;
      }
      if (tok.rfind("base=", 0) == 0)
      {
          h.hasBase = parse_int(tok.substr(5), h.base);
          continue;
      }
      if (!inWorth || tok.size() < 4 || (tok[0] != '+' && tok[0] != '-') || tok[2] != '=')
          continue;
      PieceType t = NO_PIECE_TYPE;
      for (PieceType pt : DeliveryTypes)
          if (type_char(pt) == tok[1])
              t = pt;
      if (t == NO_PIECE_TYPE)
          continue;
      const int side = tok[0] == '-' ? 1 : 0;
      const std::string v = tok.substr(3);
      int cp = 0;
      if (v == "#")
          h.has[side][t] = h.mate[side][t] = true;
      else if (parse_int(v, cp))
          h.has[side][t] = true, h.cp[side][t] = cp;
  }
  return true;
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

namespace {

/// Sets this go's feed prices from ours (we capture a T: it goes to our
/// partner) and theirs (our opponent captures a T from us: it goes to our
/// partner's opponent), and prints them as hb_prices.
void publish_prices(CoordinatorContext& ctx, std::map<PieceType, int>& ours, std::map<PieceType, int>& theirs,
                    int q0, bool keepTable) {
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
          (side ? TheirsMate : OursMate)[t] = cp == (side ? Coef::MatePriceTheirs : Coef::MatePriceOurs);
          ps << (first ? "" : ",") << "\"" << type_char(t) << "\":" << cp;
          first = false;
      }
      ps << "}";
  }
  ps << "}";
  FedRoot = ctx.us;
  // Scores in the table carry another go's prices and root. v7d,
  // HBPriceKeepTable: with every price at zero, now and when the table was
  // written, they carry nothing and the table is kept.
  if (!keepTable)
      TT.clear();
  else
  {
      const bool any = any_price();
      if (any || TableDirty)
          TT.clear();
      TableDirty = any;
  }
  PricesOn = true;
  set_feed_prices_planned(true);
  ctx.log.set("prices", "1");
  sync_cout << "info string hb_prices " << ps.str() << sync_endl;
}

} // namespace

void prepare_feed_prices(CoordinatorContext& ctx) {
  Cache = ProbeCache();
  PricesOn = false;
  set_feed_prices_planned(false);
  for (PieceType t : DeliveryTypes)
      TheirsMate[t] = OursMate[t] = false;
  PartnerBaseOk = false;
  // Partner talk (PARTNER_TALK.md): with HBTell on, the prices are the
  // partner's message and no probe is run, so neither HBFeedPrices nor the
  // minimum budget applies.
  const std::string tellMode = std::string(Options["HBTell"]);
  const bool tellOn = tellMode != "off";
  Budget& b = ctx.budget;
  bool bigEnough = b.node_limited() ? b.total_nodes() > Coef::PriceMinNodes
                                    : b.time_limited() && b.total_ms() >= Coef::PriceMinMs;
  // v8h, HBMateGuard: the mate half of the feed prices at a fraction of
  // their cost. In F6 (mate prices only, eleven probes a go) a piece of ours
  // mated our partner in 9.4% of decisions, and of our piece types only 1.9
  // on average could be taken at once. So: probe the partner's board only
  // with the types the opponent can take from us now, a queen whenever we
  // have one (half of all flags), and a type that mated at our last go;
  // price nothing but those mates; keep the hash table while no price is set.
  if (!tellOn && bool(Options["HBMateGuard"]) && bigEnough)
  {
      const int gpb = 1 - ctx.board;
      const Color gStm = ctx.actual.pos(gpb).side_to_move();
      const Color gPartner = ~ctx.us;
      const Position& mine = ctx.actual.pos(ctx.board);
      const size_t plies = ctx.actual.move_list().size();
      if (plies < GuardPlies)                  // another game
          for (PieceType t : DeliveryTypes)
              GuardFatal[t] = false;
      GuardPlies = plies;
      bool risk[PIECE_TYPE_NB] = {};
      for (PieceType t : DeliveryTypes)
      {
          Bitboard b = mine.pieces(ctx.us, t);
          while (b)
          {
              Square s = pop_lsb(b);
              // A promoted piece reaches the other board as a pawn.
              PieceType fed = mine.is_promoted(s) ? PAWN : t;
              if (fed == QUEEN || GuardFatal[fed] || mine.attackers_to(s, ~ctx.us))
                  risk[fed] = true;
          }
      }
      std::map<PieceType, int> ours, theirs;
      for (PieceType t : DeliveryTypes)
          ours[t] = theirs[t] = 0;
      int q0 = 0, mates = 0;
      std::string probed;
      const ProbeResult& r0 = Cache.get(ctx, ctx.actual.fen(gpb), Phase::DISCOVERY, "partner_base", true);
      const bool baseOk = team_value(r0, gStm, gPartner, q0);
      PartnerBase = q0;
      PartnerBaseOk = baseOk;
      // HBMateGuardFloor: in F6 and P2 the partner's board stood below -300
      // at three mate prices in four, and those games were won 18% to 34% of
      // the time whatever we paid. Below the floor nothing is probed or priced.
      const bool alive = baseOk && q0 >= int(Options["HBMateGuardFloor"]);
      for (PieceType t : DeliveryTypes)
      {
          const bool was = GuardFatal[t];
          GuardFatal[t] = false;
          if (!alive || !risk[t])
              continue;
          TeamState enemy;
          enemy.assign_light(ctx.actual);
          enemy.add_to_pocket(gpb, make_piece(ctx.us, t));
          int w0, v;
          const ProbeResult& re = Cache.get(ctx, enemy.fen(gpb), Phase::DISCOVERY, std::string("enemy_") + type_char(t), true);
          probed += type_char(t);
          if (pair_values(r0, re, gStm, gPartner, w0, v))
          {
              if (v <= -Coef::FiniteCap && w0 > -Coef::FiniteCap)
                  theirs[t] = Coef::MatePriceTheirs, GuardFatal[t] = true, ++mates;
          }
          else
              GuardFatal[t] = was;             // not measured: what the last go found stands
      }
      ctx.log.set("guard", !alive ? "low" : probed.empty() ? "-" : probed);
      ctx.log.set("price_depth", std::to_string(int(r0.depth)));
      ctx.log.set("price_mates", std::to_string(mates));
      // v8i, HBMateGuardQuiet: with no mate priced this go is the go without
      // prices in every respect but the probes' nodes (no rescue prices, no
      // partner score in the draw rule). guardnone-b: prices on with nothing
      // priced scored 139-161 where the floor guard scored 157-143.
      if (!mates && bool(Options["HBMateGuardQuiet"]))
      {
          PartnerBaseOk = false;
          if (TableDirty)
              TT.clear(), TableDirty = false;
          return;
      }
      publish_prices(ctx, ours, theirs, q0, true);
      return;
  }

  if (!tellOn && (!bool(Options["HBFeedPrices"]) || !bigEnough))
  {
      if (TableDirty && bool(Options["HBPriceKeepTable"]))
          TT.clear(), TableDirty = false;
      return;
  }

  const int pb = 1 - ctx.board;
  const Color pbStm = ctx.actual.pos(pb).side_to_move();
  const Color partner = ~ctx.us;
  // Used when a probe does not finish: roughly half a piece's board value.
  std::map<PieceType, int> ours{{PAWN, 40}, {KNIGHT, 100}, {BISHOP, 100}, {ROOK, 130}, {QUEEN, 200}};
  std::map<PieceType, int> theirs = ours;

  if (tellOn)
  {
      // Only what the message prices is worth anything.
      for (PieceType t : DeliveryTypes)
          ours[t] = theirs[t] = 0;
      const std::string text = std::string(Options["HBPartnerTell"]);
      HeardTell h;
      std::string heard = "none";
      if (text != "none" && parse_tell(text, h))
      {
          // The partner board's plies in our position: n, or n + 1 once its
          // opponent has replied. More, and the message is about a board
          // that is gone.
          int plies = 0;
          for (const auto& m : ctx.actual.move_list())
              plies += m.first == pb;
          heard = plies > h.n + 1 ? "stale" : "fresh";
      }
      // v8i, three limits on what is honoured (all off by default):
      // HBTellFloor: nothing while the teller's own board is below it (the
      // floor guard: a price paid for a lost board is a board given away);
      // HBTellMin: a cost or worth under this many cp is not news (AUTOPSY3:
      // the falls are pieces our side had measured at 500 or more);
      // HBTellLossesOnly: only what the teller loses when its opponent gets a
      // piece, nothing for pieces we could win for it.
      if (heard == "fresh" && h.hasBase && h.base < int(Options["HBTellFloor"]))
          heard = "low";
      if (heard == "fresh")
      {
          const bool numbers = tell_has(tellMode, "worth") || tell_has(tellMode, "table");
          const int priceScale = int(Options["HBPriceScale"]), priceCap = int(Options["HBPriceCap"]);
          const int tellMin = int(Options["HBTellMin"]);
          const bool lossesOnly = bool(Options["HBTellLossesOnly"]);
          for (PieceType t : DeliveryTypes)
          {
              // The teller's +T (a T in its hand, it mates with '#') is a T
              // that we capture here.
              if (lossesOnly)
                  ours[t] = 0;
              else if (h.mate[0][t])
                  ours[t] = Coef::MatePriceOurs;
              else if (numbers && h.has[0][t] && h.cp[0][t] >= tellMin)
                  ours[t] = std::clamp(h.cp[0][t] * priceScale / 100, 0, priceCap);
              // Its -T (a T in its opponent's hand, '#': it is mated) is a T
              // that our opponent captures from us here.
              if (h.mate[1][t])
                  theirs[t] = Coef::MatePriceTheirs;
              else if (numbers && h.has[1][t] && h.cp[1][t] >= tellMin)
                  theirs[t] = std::clamp(h.cp[1][t] * priceScale / 100, 0, priceCap);
          }
      }
      // v8j, HBTellRoot: the message is used once, at the choice among the
      // candidates (coordinate), and prices nothing inside the search.
      if (bool(Options["HBTellRoot"]))
          for (PieceType t : DeliveryTypes)
              ours[t] = theirs[t] = 0;
      ctx.log.set("heard", heard);
      // Nothing priced: this go is the go without prices in every respect
      // (no rescue probes, the same candidates' scores), so two builds play
      // the same game until the first message that prices something.
      bool priced = false;
      for (PieceType t : DeliveryTypes)
          priced |= ours[t] > 0 || theirs[t] > 0;
      if (!priced)
      {
          if (TableDirty)
              TT.clear(), TableDirty = false;
          return;
      }
      // Kept as HBPriceKeepTable=true keeps it; no hb_values line.
      publish_prices(ctx, ours, theirs, 0, true);
      return;
  }

  int q0 = 0;
  PieceValues shown;      // the same probes, unhalved, for the page
  shown.board = pb;
  shown.stm = pbStm;
  const ProbeResult& r0 = Cache.get(ctx, ctx.actual.fen(pb), Phase::DISCOVERY, "partner_base", true);
  shown.depth = deep_probes() ? r0.depth : Coef::ProbeDepth;
  if (team_value(r0, pbStm, partner, q0))
  {
      shown.baseOk = true;
      shown.base = partner == WHITE ? q0 : -q0;
  }
  PartnerBase = q0;
  PartnerBaseOk = shown.baseOk;
  // Share of a piece's measured gain that counts as its price, and the most
  // a price can be (50% and 500 cp as measured through v5).
  const int priceScale = int(Options["HBPriceScale"]), priceCap = int(Options["HBPriceCap"]);
  int minDepth = r0.depth, mates = 0;
  if (shown.baseOk)
      for (PieceType t : DeliveryTypes)
      {
          TeamState mine, enemy;
          mine.assign_light(ctx.actual);
          enemy.assign_light(ctx.actual);
          mine.add_to_pocket(pb, make_piece(partner, t));
          enemy.add_to_pocket(pb, make_piece(ctx.us, t));
          // w0: the board without the piece, v: with it, at one common depth
          int w0, v;
          const ProbeResult& rm = Cache.get(ctx, mine.fen(pb), Phase::DISCOVERY, std::string("partner_") + type_char(t), true);
          if (pair_values(r0, rm, pbStm, partner, w0, v))
          {
              shown.set(partner, t, v, w0);
              ours[t] = v >= Coef::FiniteCap && w0 < Coef::FiniteCap ? Coef::MatePriceOurs
                                                                    : std::clamp((v - w0) * priceScale / 100, 0, priceCap);
              minDepth = std::min(minDepth, int(rm.depth));
              mates += ours[t] == Coef::MatePriceOurs;
          }
          const ProbeResult& re = Cache.get(ctx, enemy.fen(pb), Phase::DISCOVERY, std::string("enemy_") + type_char(t), true);
          if (pair_values(r0, re, pbStm, partner, w0, v))
          {
              shown.set(ctx.us, t, -v, -w0);
              theirs[t] = v <= -Coef::FiniteCap && w0 > -Coef::FiniteCap ? Coef::MatePriceTheirs
                                                                        : std::clamp((w0 - v) * priceScale / 100, 0, priceCap);
              minDepth = std::min(minDepth, int(re.depth));
              mates += theirs[t] == Coef::MatePriceTheirs;
          }
      }
  if (deep_probes())
  {
      ctx.log.set("price_depth", std::to_string(int(r0.depth)));
      ctx.log.set("price_min_depth", std::to_string(minDepth));
      ctx.log.set("price_mates", std::to_string(mates));
  }

  publish_prices(ctx, ours, theirs, q0, bool(Options["HBPriceKeepTable"]));
  sync_cout << "info string hb_values " << shown.json("partner") << sync_endl;
}


/// Our partner is mated in `plies` and sits. The feed prices come from
/// searches too shallow to see that mate, so they pay for pieces that change
/// nothing. Search its board with one more piece in its hand, well past the
/// mate's length: a piece that leaves it mated is worth nothing, and one that
/// ends the mate is priced as feed prices are, from a lost board.
void price_rescues(CoordinatorContext& ctx, int plies) {
  const int pb = 1 - ctx.board;
  const Color partner = ~ctx.us;
  const std::string fen = ctx.actual.fen(pb);
  if (Rescue.fen != fen)
  {
      Rescue = RescueMemo();
      Rescue.fen = fen;
      for (PieceType t : DeliveryTypes)
      {
          Rescue.cp[t] = -1;
          TeamState with;
          with.assign_light(ctx.actual);
          with.add_to_pocket(pb, make_piece(partner, t));
          ProbeRequest req;
          req.fen = with.fen(pb);
          req.phase = Phase::DISCOVERY;
          req.clear = true;
          req.depth = Depth(plies + Coef::RescueExtraPlies);
          req.maxNodes = ctx.budget.share_nodes(Coef::RescueShare);
          req.maxTimeMs = ctx.budget.share_ms(Coef::RescueShare);
          req.tag = std::string("rescue_") + type_char(t);
          ProbeResult r = ctx.worker.run(req, ctx.budget, &ctx.log);
          if (r.status != ProbeResult::OK || r.score == VALUE_NONE || r.depth < 1)
              continue;
          // Our partner is on turn there, so the score is its own. A mate
          // found is certain at any depth; its absence only at full depth.
          if (mate_plies(r.score) < 0)
              Rescue.cp[t] = 0;
          else if (r.depth >= req.depth)
              Rescue.cp[t] = std::clamp((finite_cp(r.score) + Coef::FiniteCap) / Coef::PriceDiv, 0, Coef::PriceCap);
      }
  }
  std::ostringstream ss;
  for (PieceType t : DeliveryTypes)
  {
      // Not measured: the price from the shallow probes stands.
      if (Rescue.cp[t] >= 0)
          FedGain[ctx.us][t] = Rescue.cp[t] * PawnValueEg / 100;
      ss << (ss.tellp() ? "," : "") << type_char(t) << ":" << Rescue.cp[t];
  }
  if (bool(Options["HBPriceKeepTable"]) && !TableDirty && any_price())
      TT.clear(), TableDirty = true;
  ctx.log.set("rescue", ss.str());
}

void prepare_forecast(CoordinatorContext& ctx) {
  Fc = Forecast();
  WorldsOn = false;
  PartnerHeld = false;
  Budget& b = ctx.budget;
  bool bigEnough = b.node_limited() ? b.total_nodes() > Coef::PriceMinNodes
                                    : b.time_limited() && b.total_ms() >= Coef::PriceMinMs;
  if (!bool(Options["HBWorlds"]) || !bigEnough)
      return;
  // The forecast runs before the main search and the worlds after it.
  // v6: the deeper price probes come out of the worlds' share, not out of
  // the main search's.
  const double mainCum = double(int(Options["HBMainShare"])) / 100.0;
  b.set_slices(Slices{mainCum, 0.02, 0.96 - mainCum, 0.02});
  ctx.worker.set_hash_mb(Coef::WorldHashMb);
  Fc = make_forecast(ctx);
  WorldsOn = true;
  if (bool(Options["HBHold"]) && ctx.clocksKnown && Fc.ready && Fc.moverIsPartner)
  {
      // Mated by force: it sits. Or lost, with a mate too deep for this
      // search, and seen on turn for longer than a move takes: it sits.
      const int pb = 1 - ctx.board;
      size_t moves = 0;
      for (const auto& m : ctx.actual.move_list())
          moves += m.first == pb;
      int clock = clock_of(ctx, pb, ~ctx.us);
      bool sitting = Seen.valid && Seen.onTurn && Seen.moves == moves && Seen.clock - clock > Coef::HoldMoveMs + 100;
      bool lost = !Fc.lines.empty() && Fc.lines[0].score <= -Coef::PartnerLostCp;
      PartnerHeld = Fc.teamMate < 0 || (sitting && lost);
      // The first sighting of this turn is the one to measure from.
      if (!(Seen.valid && Seen.onTurn && Seen.moves == moves))
          Seen = PartnerSeen{true, true, moves, clock};
  }
  else
      Seen = PartnerSeen();
  if (PartnerHeld)
  {
      // A sitting partner makes no captures and allows none, and a piece we
      // lose cannot be dropped on its board.
      Fc.worlds.clear();
      Fc.worlds.push_back(World{Arrival(), 1.0});
      if (PricesOn)
      {
          for (PieceType t : DeliveryTypes)
              FedGain[~ctx.us][t] = 0, TheirsMate[t] = false;
          if (Fc.teamMate < 0 && bool(Options["HBRescue"]))
              price_rescues(ctx, -Fc.teamMate);
      }
      ctx.log.set("partner_held", std::to_string(Fc.teamMate));
  }
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
  // v6: moves that end the game as the referee's draw: our move repeats the
  // position a third time (drawNow), or it leaves only replies that do (drawForced).
  // drawSeek: every reply brings back a position seen before, one step short.
  std::set<Move> drawNow, drawForced, drawSeek;
  bool avoidDraw = false;
  // Partner talk (HBTell, PARTNER_TALK.md): what the worlds said of the
  // moves, kept for finish, which tells the partner.
  struct TellWorlds {
    bool scored = false;                     // the worlds were scored in this go
    Move sitMove = MOVE_NONE;                // the move judged for a sit: the main search's
    std::map<Move, int> none;                // cp for us with nothing arriving
    std::vector<Arrival> arrival;            // each scored arrival world's package
    std::vector<std::map<Move, int>> value;  // and its cp for us
    // Minimal Talk: the comparison search's line for every candidate, and
    // the search that deepened the main one, when either was run.
    std::map<Move, std::vector<Move>> cmpPv;
    std::map<Move, Value> cmpScore;
    int cmpDepth = 0;
    bool hasExt = false;
    ProbeResult ext;
  };
  TellWorlds told;
  const std::string tellMode = std::string(Options["HBTell"]);
  // One hb_tell line for the decision dec.
  auto print_tell = [&](const Decision& dec) {
      int n = dec.pass ? 0 : 1;               // plies on our board, this move included
      for (const auto& m : ctx.actual.move_list())
          n += m.first == ctx.board;
      std::ostringstream ts;
      ts << "info string hb_tell v1 n=" << n;
      // Minimal Talk: what this seat's own search expects on this board
      // after the move decided (for a sit: the move it would play). No search
      // is made for it. The lines are the best lines of the last four
      // iterations of the main search that begin with that move, the deepest
      // counting 4 and the fourth 1; when the move came from elsewhere, the
      // comparison search's line for it.
      std::ostringstream linesText;
      if (tell_has(tellMode, "minimal") || tell_has(tellMode, "plan"))
      {
          const Move mv = !dec.pass ? dec.move
                        : ctx.main.status == ProbeResult::OK ? ctx.main.finalMove : MOVE_NONE;
          const ProbeResult& src = told.hasExt && told.ext.depth >= ctx.main.depth ? told.ext : ctx.main;
          const size_t maxLen = size_t(int(Options["HBForecastScan"])) + 2;
          auto spell = [&](const std::vector<Move>& pv) {
              std::string s;
              StateListPtr states(new std::deque<StateInfo>(1));
              Position p;
              p.set(root.variant(), root.fen(), false, &states->back(), root.this_thread());
              for (size_t k = 0; k < pv.size() && k < maxLen; ++k)
              {
                  if (!MoveList<LEGAL>(p).contains(pv[k]))
                      break;
                  s += (k ? "," : "") + UCI::move(p, pv[k]);
                  states->emplace_back();
                  p.do_move(pv[k], states->back());
              }
              return s;
          };
          std::vector<std::pair<int, std::string>> found;
          auto add = [&](int w, const std::vector<Move>& pv) {
              const std::string s = spell(pv);
              if (s.empty())
                  return;
              for (auto& f : found)
                  if (f.second == s)
                  {
                      f.first += w;
                      return;
                  }
              found.emplace_back(w, s);
          };
          Value sc = VALUE_NONE;
          int depth = 0;
          if (mv != MOVE_NONE)
          {
              int w = 4;
              for (int dd = int(src.depthPvs.size()) - 1; dd >= 1 && w > 0; --dd)
              {
                  const std::vector<Move>& pv = src.depthPvs[dd];
                  if (pv.empty())
                      continue;
                  if (pv[0] == mv)
                  {
                      if (found.empty() && size_t(dd) < src.depthScores.size())
                          sc = src.depthScores[dd], depth = dd;
                      add(w, pv);
                  }
                  --w;
              }
              if (found.empty() && told.cmpPv.count(mv))
              {
                  sc = told.cmpScore[mv], depth = told.cmpDepth;
                  add(4, told.cmpPv[mv]);
              }
          }
          if (!found.empty() && sc != VALUE_NONE)
          {
              int at = 0;                     // plies on our board before the lines' first move
              for (const auto& m : ctx.actual.move_list())
                  at += m.first == ctx.board;
              ts << " at=" << at << " d=" << depth << " score=" << to_cp(sc) << " mate=" << mate_plies(sc)
                 << " hands=" << ctx.actual.pocket(ctx.board, WHITE) << "/" << ctx.actual.pocket(ctx.board, BLACK);
              linesText << " lines";
              for (const auto& f : found)
                  linesText << ' ' << f.first << ':' << f.second;
          }
      }
      const bool numbers = tell_has(tellMode, "worth") || tell_has(tellMode, "table");
      const bool marks = numbers || tell_has(tellMode, "alarm");
      const Move mv = dec.pass ? told.sitMove : dec.move;
      if (marks && told.scored && told.none.count(mv))
      {
          // [0]: +T, a T in our hand; [1]: -T, a T in our opponent's hand.
          struct Entry { bool seen = false, mate = false, single = false; int cp = 0; };
          Entry e[2][PIECE_TYPE_NB];
          const int v0 = told.none.at(mv);
          // The judged move's value with nothing arriving: the entries are differences from it.
          ts << " base=" << v0;
          for (size_t i = 0; i < told.arrival.size(); ++i)
          {
              const auto it = told.value[i].find(mv);
              if (it == told.value[i].end())
                  continue;
              const int v = it->second;
              const Arrival& a = told.arrival[i];
              const bool single = a.count() == 1;   // the package is that one piece alone
              const bool mates = v >= 90000 && v0 < 90000;
              const bool mated = v <= -90000 && v0 > -90000;
              for (PieceType t : DeliveryTypes)
                  for (int side = 0; side < 2; ++side)
                  {
                      if (!(side ? a.them[t] : a.us[t]))
                          continue;
                      Entry& en = e[side][t];
                      // A difference across a mate score says "decisive", not a number of pawns.
                      const int diff = std::clamp(side ? v0 - v : v - v0, 0, Coef::FiniteCap);
                      en.mate = en.mate || (side ? mated : mates);
                      if (single)
                          en.cp = diff, en.single = true;
                      else if (!en.single)
                          en.cp = std::max(en.cp, diff);
                      en.seen = true;
                  }
          }
          ts << " worth";
          for (int side = 0; side < 2; ++side)
              for (PieceType t : DeliveryTypes)
              {
                  const Entry& en = e[side][t];
                  if (!en.seen || (!en.mate && !numbers))
                      continue;
                  ts << ' ' << (side ? '-' : '+') << type_char(t) << '=';
                  if (en.mate)
                      ts << '#';
                  else
                      ts << en.cp;
              }
      }
      sync_cout << ts.str() << linesText.str() << sync_endl;
      log.set("tell", tellMode);
  };
  auto finish = [&](Decision dec, const std::string& why) {
      if (avoidDraw && !dec.pass && (drawNow.count(dec.move) || drawForced.count(dec.move)))
      {
          // The search does not know this rule: its move would throw away a
          // board that is not lost. The next move in its order that keeps
          // the game going is played instead.
          Move alt = MOVE_NONE;
          for (Move m : ctx.main.rootOrder)
              if (alt == MOVE_NONE && legal.contains(m) && !drawNow.count(m) && !drawForced.count(m))
                  alt = m;
          for (const auto& m : legal)
              if (alt == MOVE_NONE && !drawNow.count(m) && !drawForced.count(m))
                  alt = m;
          if (alt != MOVE_NONE)
          {
              dec.move = alt;
              log.set("draw_avoided", "1");
          }
      }
      dec.reason = why;
      log.set("coord_reason", why);
      sync_cout << "info string hb_coord {\"reason\":" << json_str(why) << js.str() << "}" << sync_endl;
      // need_main is not a decision: coordinate() runs again after a fresh
      // main search, and that call tells.
      if (tellMode != "off" && why != "need_main")
          print_tell(dec);
      return dec;
  };

  Move M = ctx.main.status == ProbeResult::OK && ctx.main.finalMove != MOVE_NONE ? ctx.main.finalMove : ctx.fallback;
  d.move = M;
  log.set("override", "0");

  auto stall = [&](bool needLead) {
      Decision s;
      s.pass = true;
      s.wakeAfterMs = std::max(1, clock_of(ctx, ctx.board, ctx.us) - Coef::StallReserveMs);
      Hold = HoldState();
      Hold.kind = HOLD_EXPOSED;
      Hold.moves = ctx.actual.move_count();
      Hold.needLead = needLead;
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

  // ---- v6: the referee's draw by repetition, which the search cannot see
  // because it counts the hands as part of the position.
  if (bool(Options["HBDraws"]))
  {
      for (const auto& m : legal)
      {
          TeamUndo u = work.play_undoable(ctx.board, m);
          if (work.is_draw())
              drawNow.insert(m);
          else
          {
              MoveList<LEGAL> replies(work.pos(ctx.board));
              bool all = replies.size() > 0 && replies.size() <= 3, seen = all;
              for (const auto& r : replies)
              {
                  if (!seen)
                      break;
                  TeamUndo u2 = work.play_undoable(ctx.board, r);
                  all = all && work.is_draw();
                  seen = work.is_draw() || work.repetitions(ctx.board) >= 2;
                  work.undo(u2);
              }
              if (all)
                  drawForced.insert(m);
              else if (seen)
                  drawSeek.insert(m);
          }
          work.undo(u);
      }
      if (!drawNow.empty() || !drawForced.empty())
      {
          log.set("draw_moves", std::to_string(drawNow.size() + drawForced.size()));
          const bool searched = ctx.main.status == ProbeResult::OK && ctx.main.exact;
          const int plies = searched ? mate_plies(ctx.main.score) : 0;
          const int cp = searched ? finite_cp(ctx.main.score) : 0;
          const bool partnerWins = (WorldsOn && Fc.ready && Fc.teamMate > 0)
                                || (PartnerBaseOk && PartnerBase >= Coef::DrawSeekCp);
          if (searched && (plies < 0 || cp <= -Coef::DrawSeekCp) && !partnerWins)
          {
              // Half a point from a lost board.
              const std::set<Move>& pool = drawNow.empty() ? drawForced : drawNow;
              std::string best;
              for (Move m : pool)
              {
                  std::string uci = UCI::move(root, m);
                  if (best.empty() || uci < best)
                      best = uci, d.move = m;
              }
              log.set("override", d.move == M ? "0" : "1");
              return finish(d, "draw_taken");
          }
          avoidDraw = searched && (plies > 0 || (plies == 0 && cp >= Coef::DrawAvoidCp) || partnerWins);
      }
  }

  // ---- v5: holding. A seat that sits cannot be mated, captured from or
  // dropped on, and the other board plays on. Both seats run this same code
  // on the same two boards, so each knows when the other will sit.
  bool playOn = false;      // mated by force, and moving keeps the other board alive
  if (bool(Options["HBHold"]) && ctx.clocksKnown && ctx.main.status == ProbeResult::OK && ctx.main.exact)
  {
      const int ours = clock_of(ctx, ctx.board, ctx.us);
      const int mine = mate_plies(ctx.main.score);
      const std::string fen = ctx.actual.fen(ctx.board);
      // A capture that lets our partner mate at once is played, never held.
      bool delivers = false;
      if (pbOnTurnIsPartner)
          for (const auto& m : legal)
              if (TeamState::captured_type(root, m) != NO_PIECE_TYPE && delivery_wins(ctx, work, m))
              {
                  delivers = true;
                  break;
              }
      auto hold = [&](int kind, int wakeMs, const char* why) {
          Decision h;
          h.pass = true;
          h.wakeAfterMs = std::max(0, wakeMs);
          bool same = Hold.kind == kind && Hold.fen == fen;
          int began = same ? Hold.clockStart : ours;
          int floor = Hold.floorMs;
          Hold = HoldState();
          Hold.kind = kind;
          Hold.moves = ctx.actual.move_count();
          Hold.fen = fen;
          Hold.clockStart = began;
          Hold.floorMs = floor;
          log.set("hold", why);
          log.set("hold_mate", std::to_string(kind == HOLD_MATED ? mine : Fc.teamMate));
          return finish(h, why);
      };
      if (!delivers && mine < 0)
      {
          // Mated by force with the hands as they are: moving loses, so sit
          // until the clock only covers the moves the mate takes. The first
          // of them costs nothing, because a sitting seat moves at once.
          // Our partner has that long to win or to send a piece that defends.
          int floor = std::clamp(Coef::HoldMoveMs * (-mine / 2 - 1) + Coef::HoldFloorMinMs,
                                 Coef::HoldFloorMinMs, Coef::HoldFloorMaxMs);
          // Without a wake booked for the floor, the next chance to move is
          // the next move on the other board.
          bool timed = WakeTurnKey != turn_key(ctx.actual, ctx.board) || WakeClock == floor;
          // v6: sitting is what loses the other board. The seat our partner
          // plays against waits for this mate once it leads us on the clock
          // (PartnerHoldLeadMs), and then our partner never moves again. It
          // leads us only because we sit: a seat that moves in turn spends
          // what that seat spends, and one that moves while that seat waits
          // spends half as much, so each move of ours takes about 2 s off a
          // lead it already has. We have one move fewer than the mate is long
          // before the last stand. If some are left after the lead is gone,
          // we play the mate out and our partner keeps its moves for that long.
          // Not when that seat is too short of time to wait at all, and not
          // when our partner mates as well: then the seat that sits later wins.
          const int racing = clock_of(ctx, pb, ctx.us);
          const int lead = racing - ours;
          const int spent = lead < Coef::PartnerHoldLeadMs - Coef::PlayOnMarginMs
                          ? 0 : 1 + std::max(0, lead - Coef::PartnerHoldLeadMs) / Coef::PlayOnLeadPerMoveMs;
          playOn = bool(Options["HBPlayOn"]) && -mine / 2 - 1 - spent >= 1
                && !(WorldsOn && Fc.ready && Fc.teamMate > 0)
                && racing >= Coef::PartnerHoldReserveMs;
          if (!playOn && ours > floor + (timed ? 0 : Coef::HoldUntimedMs))
          {
              Hold.floorMs = floor;
              return hold(HOLD_MATED, ours - floor, "hold_mated");
          }
      }
      else if (!delivers && mine == 0 && WorldsOn && Fc.ready && Fc.teamMate > 0 && !root.checkers()
               && partner_hold_ok(ctx))
      {
          // Our partner mates by force and we do not: while we sit the
          // opponents get no new piece to block with and cannot mate us first.
          if (!pbOnTurnIsPartner)
              // The mated seat is on turn and may sit as well. We are ahead
              // of it on the clock, so it runs out first: no wake is needed.
              return hold(HOLD_PARTNER, 0, "hold_partner");
          // Our partner is on turn and moves within one move's time. The
          // wake is this turn's one booked wake, so the wait always ends.
          const std::string key = turn_key(ctx.actual, ctx.board);
          if (WakeTurnKey != key)
              return hold(HOLD_PARTNER, Coef::PartnerHoldMs, "hold_partner");
      }
  }
  Hold = HoldState();
  if (ctx.mainCached)
      return finish(d, "need_main");

  // Mated by force and out of time to sit: a move whose every reply repeats
  // an earlier position is a step towards the referee's draw.
  if (!drawSeek.empty() && ctx.main.status == ProbeResult::OK && ctx.main.exact && mate_plies(ctx.main.score) < 0)
  {
      std::string best;
      for (Move m : drawSeek)
      {
          std::string uci = UCI::move(root, m);
          if (best.empty() || uci < best)
              best = uci, d.move = m;
      }
      log.set("override", d.move == M ? "0" : "1");
      return finish(d, "draw_seek");
  }
  if (playOn)
  {
      // The main search's move is the longest defence.
      log.set("mated_play", "1");
      return finish(d, "mated_play_on");
  }

  // ---- v6: the best line loses a piece that mates on the partner board.
  // The main search already charges that capture as a lost game, so no move
  // avoids it. Sitting does: nothing is captured on a board whose seat sits.
  // Our partner sees the same capture in its forecast and has about two
  // moves to make the piece harmless; after that we play on.
  if (bool(Options["HBFeedHold"]) && ctx.clocksKnown && PricesOn && !PartnerHeld
      && ctx.main.status == ProbeResult::OK && ctx.main.exact && mate_plies(ctx.main.score) == 0
      && ctx.main.pv.size() >= 2 && ctx.main.pv[0] == M)
  {
      const int ours = clock_of(ctx, ctx.board, ctx.us);
      const std::string turn = turn_key(ctx.actual, ctx.board);
      if (Feed.turn != turn)
          Feed = FeedHoldState{turn, ours};
      PieceType won = TeamState::captured_type(root, M), lost = NO_PIECE_TYPE;
      TeamUndo u = work.play_undoable(ctx.board, M);
      if (MoveList<LEGAL>(work.pos(ctx.board)).contains(ctx.main.pv[1]))
          lost = TeamState::captured_type(work.pos(ctx.board), ctx.main.pv[1]);
      work.undo(u);
      // Not when our own capture lets our partner mate first.
      bool weMateFirst = won != NO_PIECE_TYPE && OursMate[won] && pbOnTurnIsPartner;
      int left = Coef::FeedHoldMs - (Feed.clockStart - ours);
      // The wake that ends the sit is this turn's one booked wake.
      bool wakeOk = WakeTurnKey != turn || WakeClock == Feed.clockStart - Coef::FeedHoldMs;
      if (lost != NO_PIECE_TYPE && TheirsMate[lost] && !weMateFirst && wakeOk
          && left > 300 && ours - left >= Coef::FeedHoldReserveMs)
      {
          Decision h;
          h.pass = true;
          h.wakeAfterMs = left;
          Hold.kind = HOLD_FEED;
          Hold.moves = ctx.actual.move_count();
          log.set("hold", "hold_feed");
          log.set("hold_piece", std::string(1, type_char(lost)));
          return finish(h, "hold_feed");
      }
  }

  // ---- a forced move can still be refused: sitting costs only clock
  if (legal.size() <= 1)
  {
      std::string how;
      if (exposure_tier(ctx, work, M, how) == CERTAIN && stall_ok(ctx, false))
      {
          log.set("veto", how);
          return finish(stall(false), "stall_deny");
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
      const ProbeResult& r0 = cache.get(ctx, ctx.actual.fen(pb), Phase::DISCOVERY, "partner_base", true);
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
              const ProbeResult& r = cache.get(ctx, copy.fen(pb), Phase::DISCOVERY, std::string("partner_") + type_char(t), true);
              int qb, qt;
              bool ok = hasQ0 && pair_values(r0, r, pbStm, partner, qb, qt);
              if (ok)
                  F[t] = qt - qb;
              js << (first ? "" : ",") << "\"" << type_char(t) << "\":" << (ok ? std::to_string(qt - qb) : "null");
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
      if ((!a || poor) && stall_ok(ctx, a != nullptr))
      {
          log.set("veto", mc.exposure);
          dec = stall(a != nullptr);
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
      if (ext.status == ProbeResult::OK && ext.depth > 0)
          told.ext = ext, told.hasExt = true;
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
             << ",\"feed\":" << c.feed
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
      // The forecast is kept for the holds, but no move is chosen over the
      // worlds: their share of the go deepens the main search instead.
      if (!bool(Options["HBWorldSwitch"]))
      {
          report_candidates(0);
          std::string why = resolve_tier(false, d);
          return why.empty() ? extend_main("worlds_off") : finish(d, why);
      }

      struct WorldRun {
        Arrival arrival;
        double p = 0;
        std::string key, fen, best, arrives;   // arrives: e.g. "-B@3", droppable from ply 3
        int depth = 0;
        bool scored = false;
        std::map<Move, int> value;     // cp for us, per candidate
        int arriveCount[COLOR_NB][PIECE_TYPE_NB] = {};
        int arrivePly[COLOR_NB][PIECE_TYPE_NB] = {};
      };
      // v8: when a forecast piece can be dropped here. Measured on 200 games
      // (EXPERIMENTS.md): the boards move in step, so a capture k plies into
      // the partner-board line is made after k+1 plies of ours, our move now
      // being the first. The opponent moves on odd plies and we on even ones.
      const int timing = int(Options["HBArrivalTiming"]);
      auto drop_ply = [](int k, bool ours) {
          int q = k + 1;
          return ours ? std::max(2, q + (q & 1)) : (q | 1);
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
              for (int side = 0; side < 2 && timing; ++side)
              {
                  const bool ours = side == 0;
                  const int n = ours ? w.arrival.us[t] : w.arrival.them[t];
                  const int k = ours ? w.arrival.plyUs[t] : w.arrival.plyThem[t];
                  if (!n || k < 0 || (timing == 1 && k < Coef::ForecastPlies))
                      continue;
                  // Untimed, our pieces wait for our next move (the root
                  // moves are today's) and theirs for their reply.
                  const int at = drop_ply(k, ours);
                  if (at <= (ours ? 2 : 1))
                      continue;
                  const Color c = ours ? ctx.us : ~ctx.us;
                  r.arriveCount[c][t] = n;
                  r.arrivePly[c][t] = at;
                  r.arrives += (r.arrives.empty() ? "" : ",") + std::string(ours ? "+" : "-") + " PNBRQ"[t] + "@" + std::to_string(at);
              }
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
          std::copy(&runs[i].arriveCount[0][0], &runs[i].arriveCount[0][0] + COLOR_NB * PIECE_TYPE_NB, &req.arriveCount[0][0]);
          std::copy(&runs[i].arrivePly[0][0], &runs[i].arrivePly[0][0] + COLOR_NB * PIECE_TYPE_NB, &req.arrivePly[0][0]);
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
          std::copy(&runs[i].arriveCount[0][0], &runs[i].arriveCount[0][0] + COLOR_NB * PIECE_TYPE_NB, &req.arriveCount[0][0]);
          std::copy(&runs[i].arrivePly[0][0], &runs[i].arrivePly[0][0] + COLOR_NB * PIECE_TYPE_NB, &req.arrivePly[0][0]);
          ProbeResult r = ctx.worker.run(req, ctx.budget, &log);
          if (!r.usable_exact())
              continue;
          for (const auto& line : r.lines)
              if (line.second != -VALUE_INFINITE)
                  runs[i].value[line.first] = to_cp(line.second);   // our seat is to move; mates kept
          runs[i].depth = r.depth;
          runs[i].scored = runs[i].value.size() == sm.size();
      }

      // Partner talk, HBTell=table: each piece type for each hand that has no
      // scored single-piece world above, searched as those worlds are scored.
      // For the message only: not in runs, so E, S and the choice never see it.
      std::vector<Arrival> tableArrival;
      std::vector<std::map<Move, int>> tableValue;
      const double tableShare = double(int(Options["HBTableShare"])) / 1000.0;
      if (tell_has(tellMode, "table") && tableShare > 0)
          for (int side = 0; side < 2; ++side)          // 0: into our hand, 1: into our opponent's
              for (PieceType t : DeliveryTypes)
              {
                  bool known = false;
                  for (size_t i = 1; i < runs.size(); ++i)
                  {
                      const Arrival& a = runs[i].arrival;
                      if (runs[i].scored && a.count() == 1 && (side ? a.them[t] : a.us[t]) == 1)
                          known = true;
                  }
                  if (known)
                      continue;
                  Arrival single;
                  if (side)
                      single.them[t] = 1;
                  else
                      single.us[t] = 1;
                  TeamState copy;
                  copy.assign_light(ctx.actual);
                  copy.add_to_pocket(ctx.board, make_piece(side ? ~ctx.us : ctx.us, t));
                  ProbeRequest req;
                  req.fen = copy.fen(ctx.board);
                  req.searchMoves = smUci;
                  req.multiPV = sm.size();
                  req.phase = Phase::PROBES;
                  req.clear = false;
                  req.fed = true;
                  req.maxNodes = ctx.budget.share_nodes(tableShare);
                  req.maxTimeMs = ctx.budget.share_ms(tableShare);
                  req.tag = std::string("table_") + (side ? '-' : '+') + type_char(t);
                  ProbeResult r = ctx.worker.run(req, ctx.budget, &log);
                  if (!r.usable_exact())
                      continue;
                  std::map<Move, int> value;
                  for (const auto& line : r.lines)
                      if (line.second != -VALUE_INFINITE)
                          value[line.first] = to_cp(line.second);
                  if (value.size() == sm.size())
                      tableArrival.push_back(single), tableValue.push_back(value);
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
      if (cmp.status == ProbeResult::OK && cmp.depth > 0 && cmp.linePvs.size() == cmp.lines.size())
      {
          told.cmpDepth = cmp.depth;
          for (size_t i = 0; i < cmp.lines.size(); ++i)
              if (cmp.lines[i].second != -VALUE_INFINITE && !cmp.linePvs[i].empty())
                  told.cmpPv[cmp.lines[i].first] = cmp.linePvs[i], told.cmpScore[cmp.lines[i].first] = cmp.lines[i].second;
      }
      // Partner talk: every scored world, for the line finish prints.
      if (tellMode != "off" && runs[0].scored)
      {
          told.none = runs[0].value;
          told.sitMove = cands[0].move;
          for (size_t i = 1; i < runs.size(); ++i)
              if (runs[i].scored)
                  told.arrival.push_back(runs[i].arrival), told.value.push_back(runs[i].value);
          for (size_t i = 0; i < tableArrival.size(); ++i)
              told.arrival.push_back(tableArrival[i]), told.value.push_back(tableValue[i]);
          told.scored = !told.arrival.empty();
      }
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
      // Team winning chance (HBTeamScore): the team's result follows the sum
      // of the two boards' scores, with a forced mate worth about 2,650 more
      // than the 3,000 a score is cut at (logs/loss-analysis/surface). The
      // partner's score, from its last message, is added to ours in every
      // world. It moves no move past another inside one world; it changes how
      // much each world counts: with the partner winning, only the worlds in
      // which we are mated still matter, and with the partner losing, the
      // worlds in which we gain most do.
      int teamShift = 0;
      if (int(Options["HBTeamScore"]) > 0)
      {
          const std::string text = std::string(Options["HBPartnerTell"]);
          HeardTell h;
          if (text != "none" && parse_tell(text, h) && h.hasScore)
          {
              int b = h.mateTold > 0 ? 3000 + 2673 : h.mateTold < 0 ? -(3000 + 2601) : std::clamp(h.score, -3000, 3000);
              teamShift = b * int(Options["HBTeamScore"]) / 100;
          }
          log.set("team_shift", std::to_string(teamShift));
          js << ",\"team_shift\":" << teamShift;
      }
      // v8j, HBTellRoot: what each candidate hands over, in the partner's own
      // figures. Our move's capture reaches our partner's hand (its +T); the
      // capture in the reply our comparison line expects reaches its
      // opponent's (its -T). The difference is added to the candidate's value
      // in every world, so an even trade costs about nothing and a queen
      // given for a pawn costs what the partner says a queen costs it. In
      // worth-b the losses alone, priced inside the search, scored 109-189.
      bool feedOn = false;
      std::string heardRoot = "off";
      if (bool(Options["HBTellRoot"]) && tellMode != "off" && runs[0].scored)
      {
          const std::string text = std::string(Options["HBPartnerTell"]);
          HeardTell h;
          heardRoot = "none";
          if (text != "none" && parse_tell(text, h))
          {
              int pbPlies = 0;
              for (const auto& m : ctx.actual.move_list())
                  pbPlies += m.first == pb;
              heardRoot = pbPlies > h.n + 1 ? "stale"
                        : h.hasBase && h.base < int(Options["HBTellFloor"]) ? "low" : "fresh";
          }
          if (heardRoot == "fresh")
          {
              const int share = int(Options["HBPriceScale"]), cap = int(Options["HBPriceCap"]);
              const int least = int(Options["HBTellMin"]);
              auto told_cp = [&](int side, PieceType t) {
                  if (t == NO_PIECE_TYPE)
                      return 0;
                  if (h.mate[side][t])
                      return cap;
                  return h.has[side][t] ? std::clamp(h.cp[side][t] * share / 100, 0, cap) : 0;
              };
              // v8k, HBTellRootSide: 1 counts only what our own capture gives the
              // partner, 2 only what the expected reply costs it. In feed-b a move
              // with a told gain was followed by about three quarters of it on the
              // partner's board; a switch made to avoid a told cost gave up 123 cp
              // here and the partner's score fell all the same.
              const int rootSide = int(Options["HBTellRootSide"]);
              for (auto& c : cands)
              {
                  int f = rootSide == 2 ? 0 : told_cp(0, TeamState::captured_type(root, c.move));
                  const auto pvIt = told.cmpPv.find(c.move);
                  if (rootSide != 1 && pvIt != told.cmpPv.end() && pvIt->second.size() >= 2)
                  {
                      TeamUndo fu = work.play_undoable(ctx.board, c.move);
                      const Move reply = pvIt->second[1];
                      if (MoveList<LEGAL>(work.pos(ctx.board)).contains(reply))
                          f -= told_cp(1, TeamState::captured_type(work.pos(ctx.board), reply));
                      work.undo(fu);
                  }
                  if (std::abs(f) >= least && f != 0)
                      c.feed = f, feedOn = true;
              }
          }
          log.set("heard_root", heardRoot);
      }
      // A mate on our board decides the game; any other score only shifts the odds.
      auto win = [&](int cp, int f) {
          return cp >= 90000 ? 1.0 : cp <= -90000 ? 0.0 : 1.0 / (1.0 + std::exp(-double(cp + teamShift + f) / scale));
      };
      if (runs[0].scored)
          for (auto& c : cands)
          {
              // With nothing arriving, the main search has already ranked the
              // moves, deeper than this comparison: nothing beats its choice there.
              const int vNone = std::min(runs[0].value[c.move], runs[0].value[cands[0].move]);
              double e = pNone * win(vNone, c.feed), e0 = pNone * win(vNone, 0);
              for (size_t i = 1; i < runs.size(); ++i)
                  if (runs[i].scored)
                  {
                      e += runs[i].p * win(runs[i].value[c.move], c.feed);
                      e0 += runs[i].p * win(runs[i].value[c.move], 0);
                  }
              c.E = e;
              double q = std::clamp(e, 1e-4, 1.0 - 1e-4), qPlain = std::clamp(e0, 1e-4, 1.0 - 1e-4);
              // S is on our own board's scale: the partner's share is taken out again.
              c.S = std::clamp(int(std::lround(scale * std::log(q / (1.0 - q)))) - teamShift, -Coef::FiniteCap, Coef::FiniteCap);
              c.S0 = std::clamp(int(std::lround(scale * std::log(qPlain / (1.0 - qPlain)))) - teamShift, -Coef::FiniteCap, Coef::FiniteCap);
          }

      log.set("worlds_scored", std::to_string(scoredWorlds));
      js << ",\"worlds\":[";
      for (size_t i = 0; i < runs.size(); ++i)
      {
          const WorldRun& r = runs[i];
          js << (i ? "," : "") << "{\"arrival\":" << json_str(r.key) << ",\"p\":" << r.p
             << ",\"arrives\":" << json_str(r.arrives)
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
      // v7c: a move that scores worse than the main choice when nothing arrives
      // replaces it only if an arrival mates the main choice. Measured on 400
      // games: the other switches lost about their gap in score by the next move.
      const int maxGap = int(Options["HBWorldMaxGap"]);
      bool mainMated = false;
      for (size_t i = 1; i < runs.size(); ++i)
          if (runs[i].scored && runs[i].value[cands[0].move] <= -90000)
              mainMated = true;
      log.set("main_mated_world", mainMated ? "1" : "0");
      // v8k, HBTellRootMaxCost (the user's tie-break): the partner's gain may
      // decide between near-equal moves only. In feed-b the gain switches that
      // cost 10 cp or less on our board held it (+22, +51 by the next decision);
      // those that cost more than 60 (148 of 223) lost 124. A candidate costing
      // more than the limit is judged without its feed.
      const int maxCost = int(Options["HBTellRootMaxCost"]);
      auto judged = [&](const Candidate& c) {
          return maxCost >= 0 && c.feed != 0 && cands[0].hasL && cands[0].L - c.L > maxCost ? c.S0 : c.S;
      };
      const Candidate* best = nullptr;
      for (size_t i = 1; i < cands.size(); ++i)
      {
          const Candidate& c = cands[i];
          if (!c.hasL || c.tier > cands[0].tier)
              continue;
          if (!mainMated && cands[0].hasL && c.L < cands[0].L - maxGap)
              continue;
          if (!best || judged(c) > judged(*best) || (judged(c) == judged(*best) && c.uci < best->uci))
              best = &c;
      }
      if ((scoredWorlds || feedOn) && best && judged(*best) >= cands[0].S + Coef::WorldSwitchMargin)
      {
          d.move = best->move;
          log.set("override", "1");
          log.set("override_source", best->source);
          // A switch the worlds alone would not have made is the message's.
          const bool worldsToo = scoredWorlds && best->S0 >= cands[0].S0 + Coef::WorldSwitchMargin;
          return finish(d, worldsToo ? "world_switch" : "feed_switch");
      }
      if (feedOn)
      {
          // The message kept the main move where the worlds alone would have switched.
          bool worldsSwitch = false;
          for (size_t i = 1; i < cands.size() && scoredWorlds; ++i)
              if (cands[i].hasL && cands[i].tier <= cands[0].tier && cands[i].S0 >= cands[0].S0 + Coef::WorldSwitchMargin)
                  worldsSwitch = true;
          if (worldsSwitch)
              log.set("feed_kept", "1");
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

std::string turn_key(const TeamState& ts, int board) {
  int plies = 0;
  for (const auto& m : ts.move_list())
      plies += m.first == board;
  return std::to_string(plies) + ":" + ts.rep_key(board);
}

} // namespace

const ProbeResult* held_main(const CoordinatorContext& ctx) {
  const Budget& b = ctx.budget;
  if (Hold.kind != HOLD_PARTNER || Hold.fen != ctx.actual.fen(ctx.board)
      || Memo.fen != Hold.fen || Memo.nodes != b.total_nodes() || Memo.ms != b.total_ms())
      return nullptr;
  return &Memo.result;
}

void note_wake_request(const CoordinatorContext& ctx, int wakeAfterMs) {
  std::string key = turn_key(ctx.actual, ctx.board);
  if (!ctx.clocksKnown || wakeAfterMs <= 0 || key == WakeTurnKey)
      return;
  WakeTurnKey = key;
  WakeClock = clock_of(ctx, ctx.board, ctx.us) - wakeAfterMs;
}

void remember_main(const CoordinatorContext& ctx, const ProbeResult& r) {
  Memo.fen = ctx.actual.fen(ctx.board);
  Memo.nodes = ctx.budget.total_nodes();
  Memo.ms = ctx.budget.total_ms();
  Memo.result = r;
}

namespace {

struct WaitState {
  std::string turnKey;
  bool active = false;   // a voluntary wait is running for this turn
  bool used = false;     // this turn's one wait has been spent
  int expiryClock = 0;   // our clock value at which the wait expires
};
WaitState Wait;

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
  Hold = HoldState();
  Feed = FeedHoldState();
  WakeTurnKey.clear();
  WakeClock = 0;
  PartnerHeld = false;
  Rescue = RescueMemo();
  Seen = PartnerSeen();
  Memo = MainMemo();
}

Decision consider_voluntary_wait(const CoordinatorContext& ctx) {
  Decision d;
  // A stall holds without a new search while nothing has moved.
  if (Hold.kind == HOLD_EXPOSED)
  {
      if (Hold.moves == ctx.actual.move_count() && stall_ok(ctx, Hold.needLead))
      {
          ctx.log.set("wait", "stall_continue");
          d.pass = true, d.reason = "stall_deny";
          return d;
      }
      Hold = HoldState();
  }
  // A feed hold sits on while nothing has moved and its time is not up.
  if (Hold.kind == HOLD_FEED)
  {
      int clock = ctx.clocksKnown ? clock_of(ctx, ctx.board, ctx.us) : 0;
      int left = Coef::FeedHoldMs - (Feed.clockStart - clock);
      if (ctx.clocksKnown && Hold.moves == ctx.actual.move_count()
          && Feed.turn == turn_key(ctx.actual, ctx.board) && left > 300)
      {
          ctx.log.set("wait", "hold_continue");
          ctx.log.set("hold", "hold_feed");
          d.pass = true, d.wakeAfterMs = left, d.reason = "hold_feed";
          return d;
      }
      Hold = HoldState();
  }
  // A mated seat's board is the same until a piece reaches a hand there, so
  // its search would say the same again.
  if (Hold.kind == HOLD_MATED)
  {
      int clock = ctx.clocksKnown ? clock_of(ctx, ctx.board, ctx.us) : 0;
      bool timed = WakeTurnKey == turn_key(ctx.actual, ctx.board) && WakeClock == Hold.floorMs;
      if (Hold.fen == ctx.actual.fen(ctx.board) && clock > Hold.floorMs + (timed ? 0 : Coef::HoldUntimedMs))
      {
          ctx.log.set("wait", "hold_continue");
          ctx.log.set("hold", "hold_mated");
          Hold.moves = ctx.actual.move_count();
          d.pass = true, d.wakeAfterMs = clock - Hold.floorMs, d.reason = "hold_mated";
          return d;
      }
      Hold = HoldState();
  }
  // Waiting for a partner's mate: woken with nothing moved, the wait runs on
  // until its time is up. A move on the other board is looked at again.
  if (Hold.kind == HOLD_PARTNER)
  {
      const bool partnerOnTurn = ctx.actual.pos(1 - ctx.board).side_to_move() == ~ctx.us;
      int clock = ctx.clocksKnown ? clock_of(ctx, ctx.board, ctx.us) : 0;
      // With our partner on turn the wait lasts until the booked wake.
      bool timeUp = partnerOnTurn && (WakeTurnKey != turn_key(ctx.actual, ctx.board) || clock <= WakeClock + 100);
      if (Hold.fen != ctx.actual.fen(ctx.board) || !ctx.clocksKnown)
          Hold = HoldState();
      else if (Hold.moves == ctx.actual.move_count())
      {
          // Woken with nothing moved: sit on, unless the wait has run out.
          if (partner_hold_ok(ctx) && !timeUp)
          {
              ctx.log.set("wait", "hold_continue");
              ctx.log.set("hold", "hold_partner");
              d.pass = true, d.wakeAfterMs = partnerOnTurn ? clock - WakeClock : 0, d.reason = "hold_partner";
              return d;
          }
          Hold = HoldState();
      }
      // A move on the other board: the hold stands until coordinate() has
      // looked at that board again, with our own search reused.
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
