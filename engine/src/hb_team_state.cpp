/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

#include <algorithm>
#include <sstream>

#include "apiutil.h"
#include "hb_team_state.h"
#include "movegen.h"
#include "thread.h"
#include "uci.h"

namespace Stockfish::HB {

namespace {

const char* SeatNames[SEAT_NB] = { "Awhite", "Ablack", "Bwhite", "Bblack" };

std::vector<std::string> fen_fields(const std::string& fen) {
  std::istringstream ss(fen);
  std::vector<std::string> f;
  std::string t;
  while (ss >> t)
      f.push_back(t);
  return f;
}

} // namespace

const char* seat_name(Seat s) { return SeatNames[s]; }

bool parse_seat(const std::string& s, Seat& out) {
  for (int i = 0; i < SEAT_NB; ++i)
  {
      std::string a = s, b = SeatNames[i];
      std::transform(a.begin(), a.end(), a.begin(), ::tolower);
      std::transform(b.begin(), b.end(), b.begin(), ::tolower);
      if (a == b)
      {
          out = Seat(i);
          return true;
      }
  }
  return false;
}

const Variant* bughouse_variant() {
  static const Variant* v = variants.find("bughouse")->second;
  return v;
}

Move deterministic_fallback(const Position& pos) {
  Move best = MOVE_NONE;
  std::string bestStr;
  for (const auto& m : MoveList<LEGAL>(pos))
  {
      std::string s = UCI::move(pos, m);
      if (best == MOVE_NONE || s < bestStr)
          best = m, bestStr = s;
  }
  return best;
}

PieceType TeamState::captured_type(const Position& pos, Move m) {
  if (type_of(m) == DROP || type_of(m) == CASTLING)
      return NO_PIECE_TYPE;
  if (type_of(m) == EN_PASSANT)
      return PAWN;
  Square to = to_sq(m);
  Piece captured = pos.piece_on(to);
  if (captured == NO_PIECE)
      return NO_PIECE_TYPE;
  if (pos.is_promoted(to))
      return PAWN;
  return type_of(captured);
}

TeamState::TeamState() { reset_startpos(); }

TeamState::TeamState(const TeamState& other) { *this = other; }

TeamState& TeamState::operator=(const TeamState& other) {
  if (this == &other)
      return *this;
  for (int b : {BOARD_A, BOARD_B})
      clone_board(other.boards[b], boards[b]);
  moves = other.moves;
  lastBoard = other.lastBoard;
  return *this;
}

StateListPtr TeamState::history_copy(int b) const {
  StateListPtr copy(new std::deque<StateInfo>(*boards[b].states));
  StateInfo* prev = nullptr;
  for (auto& si : *copy)
  {
      si.previous = prev;
      si.accumulator.computed[WHITE] = si.accumulator.computed[BLACK] = false;
      prev = &si;
  }
  return copy;
}

void TeamState::clone_board(const BoardState& src, BoardState& dst) {
  // Fresh storage: never share pointer-linked StateInfo with the source.
  StateListPtr copy(new std::deque<StateInfo>(*src.states));
  StateInfo* prev = nullptr;
  for (auto& si : *copy)
  {
      si.previous = prev;
      si.accumulator.computed[WHITE] = si.accumulator.computed[BLACK] = false;
      prev = &si;
  }
  StateInfo saved = copy->back();
  dst.pos.set(bughouse_variant(), src.pos.fen(), false, &copy->back(), Threads.main());
  copy->back() = saved;
  dst.states = std::move(copy);
  dst.repKeys = src.repKeys;
  dst.repCount = src.repCount;
  dst.halfmove = src.halfmove;
}

void TeamState::reset_startpos() {
  std::string err;
  const std::string& start = bughouse_variant()->startFen;
  reset(start, start, err);
}

bool TeamState::reset(const std::string& fenA, const std::string& fenB, std::string& err) {
  const std::string fens[2] = { fenA, fenB };
  for (int b : {BOARD_A, BOARD_B})
      if (FEN::validate_fen(fens[b], bughouse_variant(), false) != FEN::FEN_OK)
      {
          err = std::string("invalid FEN for board ") + "AB"[b] + ": " + fens[b];
          return false;
      }
  for (int b : {BOARD_A, BOARD_B})
  {
      BoardState& bs = boards[b];
      bs.states = StateListPtr(new std::deque<StateInfo>(1));
      bs.pos.set(bughouse_variant(), fens[b], false, &bs.states->back(), Threads.main());
      std::vector<std::string> f = fen_fields(fens[b]);
      bs.halfmove = f.size() > 4 ? std::max(0, std::atoi(f[4].c_str())) : 0;
      bs.repKeys.clear();
      bs.repCount.clear();
      record(b);
  }
  moves.clear();
  lastBoard = -1;
  return true;
}

void TeamState::record(int b) {
  std::string k = rep_key(b);
  boards[b].repKeys.push_back(k);
  boards[b].repCount[k]++;
}

bool TeamState::play(int board, const std::string& uci, std::string& err) {
  std::string token = uci;
  Move m = UCI::to_move(pos(board), token);
  if (m == MOVE_NONE)
  {
      err = std::string("illegal move ") + uci + " on board " + "AB"[board] + " in " + fen(board);
      return false;
  }
  play(board, m);
  return true;
}

Transfer TeamState::play(int board, Move m) {
  BoardState& bs = boards[board];
  Position& p = bs.pos;
  Color mover = p.side_to_move();
  PieceType captured = captured_type(p, m);
  // python-chess: drops never reset the clock; pawn moves and captures do.
  bool zeroing =  type_of(m) != DROP
               && (type_of(p.moved_piece(m)) == PAWN || captured != NO_PIECE_TYPE);
  std::string uci = UCI::move(p, m);

  bs.states->emplace_back();
  p.do_move(m, bs.states->back());
  bs.halfmove = zeroing ? 0 : bs.halfmove + 1;

  Transfer t;
  if (captured != NO_PIECE_TYPE)
  {
      // The capture belongs to the mover's partner, who plays the opposite
      // colour on the other board: the piece keeps the captured piece's colour.
      t.toBoard = 1 - board;
      t.piece = make_piece(~mover, captured);
      pos(t.toBoard).hb_add_to_hand(t.piece);
  }
  record(board);
  moves.emplace_back(board, uci);
  lastBoard = board;
  return t;
}

TeamUndo TeamState::play_undoable(int board, Move m) {
  TeamUndo u;
  u.board = board;
  u.move = m;
  u.halfmove = boards[board].halfmove;
  u.lastBoard = lastBoard;
  u.transfer = play(board, m);
  u.key = boards[board].repKeys.back();
  return u;
}

void TeamState::undo(const TeamUndo& u) {
  BoardState& bs = boards[u.board];
  if (u.transfer.toBoard >= 0)
      pos(u.transfer.toBoard).hb_remove_from_hand(u.transfer.piece);
  bs.pos.undo_move(u.move);
  bs.states->pop_back();
  bs.halfmove = u.halfmove;
  if (--bs.repCount[u.key] == 0)
      bs.repCount.erase(u.key);
  bs.repKeys.pop_back();
  moves.pop_back();
  lastBoard = u.lastBoard;
}

void TeamState::assign_light(const TeamState& other) {
  for (int b : {BOARD_A, BOARD_B})
  {
      BoardState& bs = boards[b];
      bs.states = StateListPtr(new std::deque<StateInfo>(1));
      bs.pos.set(bughouse_variant(), other.fen(b), false, &bs.states->back(), Threads.main());
      bs.repKeys = other.boards[b].repKeys;
      bs.repCount = other.boards[b].repCount;
      bs.halfmove = other.boards[b].halfmove;
  }
  moves = other.moves;
  lastBoard = other.lastBoard;
}

void TeamState::add_to_pocket(int board, Piece pc) {
  pos(board).hb_add_to_hand(pc);
}

// ---------------------------------------------------------------- queries

std::string TeamState::fen(int b) const { return pos(b).fen(); }

std::string TeamState::placement(int b) const {
  std::string f = fen(b);
  size_t end = f.find_first_of("[ ");
  return f.substr(0, end);
}

std::string TeamState::castling(int b) const {
  std::vector<std::string> f = fen_fields(fen(b));
  return f.size() > 2 ? f[2] : "-";
}

std::string TeamState::legal_ep(int b) const {
  for (const auto& m : MoveList<LEGAL>(pos(b)))
      if (type_of(m) == EN_PASSANT)
          return UCI::square(pos(b), to_sq(m));
  return "-";
}

std::string TeamState::pocket(int b, Color c) const {
  std::string s;
  for (PieceType pt : {QUEEN, ROOK, BISHOP, KNIGHT, PAWN})
      s += std::string(std::max(0, pos(b).count_in_hand(c, pt)), "PNBRQ"[pt == PAWN ? 0 : pt == KNIGHT ? 1 : pt == BISHOP ? 2 : pt == ROOK ? 3 : 4]);
  return s;
}

int TeamState::fullmove(int b) const {
  const Position& p = pos(b);
  return 1 + (p.game_ply() - (p.side_to_move() == BLACK)) / 2;
}

std::string TeamState::rep_key(int b) const {
  return placement(b) + (pos(b).side_to_move() == WHITE ? " w " : " b ")
         + castling(b) + " " + legal_ep(b);
}

int TeamState::repetitions(int b) const {
  auto it = boards[b].repCount.find(rep_key(b));
  return it == boards[b].repCount.end() ? 0 : it->second;
}

std::string TeamState::referee_fen(int b) const {
  std::vector<std::string> f = fen_fields(fen(b));
  std::ostringstream ss;
  for (size_t i = 0; i < f.size(); ++i)
      ss << (i ? " " : "") << (i == 4 ? std::to_string(halfmove(b)) : f[i]);
  return ss.str();
}

bool TeamState::keys_consistent(std::string& err) const {
  for (int b : {BOARD_A, BOARD_B})
  {
      StateInfo si;
      Position fresh;
      fresh.set(bughouse_variant(), fen(b), false, &si, Threads.main());
      if (fresh.key() != pos(b).key())
      {
          err = std::string("key mismatch on board ") + "AB"[b] + " fen " + fen(b);
          return false;
      }
      for (Color c : {WHITE, BLACK})
          for (PieceType pt : {PAWN, KNIGHT, BISHOP, ROOK, QUEEN})
              if (fresh.count_in_hand(c, pt) != pos(b).count_in_hand(c, pt))
              {
                  err = std::string("hand mismatch on board ") + "AB"[b];
                  return false;
              }
  }
  return true;
}

// ---------------------------------------------------------- referee port

bool TeamState::has_legal_move(int b) const {
  return MoveList<LEGAL>(pos(b)).size() > 0;
}

bool TeamState::is_draw() const {
  for (int b : {BOARD_A, BOARD_B})
  {
      if (halfmove(b) >= 100)
          return true;
      if (repetitions(b) >= 3)
          return true;
  }
  return false;
}

// Port of Bughouse.is_checkmate (HiveMind Board::is_checkmate)
bool TeamState::is_checkmate(Color team, bool timeAdvantage) {
  bool on[2] = { pos(BOARD_A).side_to_move() == team_color(team, BOARD_A),
                 pos(BOARD_B).side_to_move() == team_color(team, BOARD_B) };
  int legal[2] = { -1, -1 };
  auto hasLegal = [&](int b) {
      if (legal[b] < 0)
          legal[b] = has_legal_move(b) ? 1 : 0;
      return legal[b] == 1;
  };

  for (int b : {BOARD_A, BOARD_B})
      if (on[b] && pos(b).checkers() && !hasLegal(b))
          if (!partner_can_provide_blocker(b, pos(b).side_to_move(), timeAdvantage))
              return true;

  if (on[BOARD_A] || on[BOARD_B])
  {
      bool movesOnA = on[BOARD_A] && hasLegal(BOARD_A);
      bool movesOnB = on[BOARD_B] && hasLegal(BOARD_B);
      if (!movesOnA && !movesOnB && (!timeAdvantage || (on[BOARD_A] && on[BOARD_B])))
          return true;
  }
  return false;
}

bool TeamState::has_useful_capture(Position& p, Bitboard pawnValid) const {
  for (const auto& m : MoveList<LEGAL>(p))
  {
      PieceType captured = captured_type(p, m);
      if (captured == NO_PIECE_TYPE)
          continue;
      if (captured == PAWN)
      {
          if (pawnValid)
              return true;
      }
      else
          return true;
  }
  return false;
}

// Port of Bughouse._partner_can_provide_blocker (HiveMind
// Board::can_partner_provide_blocking_piece)
bool TeamState::partner_can_provide_blocker(int boardInCheck, Color checkedSide, bool timeAdvantage) {
  int partnerBoard = 1 - boardInCheck;
  Color partnerSide = ~checkedSide;
  Position& partner = pos(partnerBoard);
  bool isPartnerTurn = partner.side_to_move() == partnerSide;

  if (!isPartnerTurn && !timeAdvantage)
      return false;

  const Position& checked = pos(boardInCheck);
  Square king = checked.square<KING>(checkedSide);
  Bitboard checkers = checked.checkers();
  if (popcount(checkers) > 1)
      return false;
  Square checker = lsb(checkers);
  // python-chess between() excludes both endpoints; FSF's includes the second
  Bitboard blocking = between_bb(king, checker) & ~square_bb(checker);
  if (!blocking)
      return false;
  Bitboard available = blocking & ~checked.pieces();
  if (!available)
      return false;
  Bitboard pawnValid = available & ~(rank_bb(RANK_1) | rank_bb(RANK_8));

  if (isPartnerTurn)
      return has_useful_capture(partner, pawnValid);

  // Up on time the checked team may wait, but the opponent picks the
  // intervening move: a blocker is guaranteed only if every reply still
  // leaves the partner a useful capture.
  MoveList<LEGAL> replies(partner);
  if (!replies.size())
      return false;
  for (const auto& reply : replies)
  {
      StateInfo si;
      partner.do_move(reply, si);
      bool useful = has_useful_capture(partner, pawnValid);
      partner.undo_move(reply);
      if (!useful)
          return false;
  }
  return true;
}

Verdict TeamState::verdict(bool advWhite, bool advBlack) {
  Verdict v;
  for (Color team : {WHITE, BLACK})
      for (int adv : {0, 1})
          v.mate[team][adv] = is_checkmate(team, adv);
  v.draw = is_draw();
  v.advantage[WHITE] = advWhite;
  v.advantage[BLACK] = advBlack;
  v.first = lastBoard < 0 ? WHITE
                          : seat_team(make_seat(lastBoard, pos(lastBoard).side_to_move()));
  v.result = "none";
  for (Color team : {v.first, ~v.first})
      if (v.mate[team][v.advantage[team]])
      {
          v.result = team == WHITE ? "white_mated" : "black_mated";
          return v;
      }
  if (v.draw)
      v.result = "draw";
  return v;
}

} // namespace Stockfish::HB
