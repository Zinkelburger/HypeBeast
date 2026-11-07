/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

// Actual two-board game state: joint replay with transfers, plus an exact
// port of the arena referee's root terminal rules
// (Chess-Auto-Prep tools/bughouse_arena/referee.py).

#ifndef HB_TEAM_STATE_H_INCLUDED
#define HB_TEAM_STATE_H_INCLUDED

#include <map>
#include <string>
#include <utility>
#include <vector>

#include "position.h"

namespace Stockfish::HB {

constexpr int BOARD_A = 0;
constexpr int BOARD_B = 1;

enum Seat : int { AWHITE, ABLACK, BWHITE, BBLACK, SEAT_NB };

inline int   seat_board(Seat s) { return int(s) / 2; }
inline Color seat_color(Seat s) { return int(s) % 2 ? BLACK : WHITE; }
inline Seat  make_seat(int board, Color c) { return Seat(board * 2 + (c == BLACK)); }
// Team WHITE plays White on board A and Black on board B (arena convention).
inline Color team_color(Color team, int board) { return board == BOARD_A ? team : ~team; }
inline Color seat_team(Seat s) { return team_color(seat_color(s), seat_board(s)); }

const char* seat_name(Seat s);              // "Awhite", ...
bool parse_seat(const std::string& s, Seat& out);
inline const char* team_name(Color team) { return team == WHITE ? "white" : "black"; }

const Variant* bughouse_variant();

/// What a move sends to the partner board.
struct Transfer {
  int   toBoard = -1;     // -1: nothing transferred
  Piece piece = NO_PIECE; // colour = colour of the captured piece = receiving side
};

/// One actual board with its full history.
struct BoardState {
  Position pos;
  StateListPtr states;
  std::vector<std::string> repKeys;      // referee keys of every position so far
  std::map<std::string, int> repCount;   // referee repetition counter (pockets ignored)
  int halfmove = 0;                      // referee (python-chess) halfmove clock
};

/// Root terminal verdict in the referee's terms.
struct Verdict {
  // mate[team][timeAdvantage]: Bughouse.is_checkmate(team, timeAdvantage)
  bool mate[COLOR_NB][2] = {{false, false}, {false, false}};
  bool draw = false;
  Color first = WHITE;          // team checked first, as sim.terminal() does
  bool  advantage[COLOR_NB] = {false, false};
  // "none", "white_mated", "black_mated" or "draw"
  std::string result;
  bool terminal() const { return result != "none"; }
};

/// Undo record for TeamState::play_undoable().
struct TeamUndo {
  int board = -1;
  Move move = MOVE_NONE;
  Transfer transfer;
  int halfmove = 0;
  int lastBoard = -1;
  std::string key;
};

class TeamState {
public:
  TeamState();
  TeamState(const TeamState& other);
  TeamState& operator=(const TeamState& other);

  // Both boards from FEN (bughouse FEN with [pockets] and ~ promoted markers).
  bool reset(const std::string& fenA, const std::string& fenB, std::string& err);
  void reset_startpos();

  // Play a referee-format move ("e2e4", "N@f3", "e7e8q") on a board,
  // applying the transfer to the partner board. False if illegal.
  bool play(int board, const std::string& uci, std::string& err);
  // Play an already legal move. Returns the transfer applied.
  Transfer play(int board, Move m);

  // Same as play() but reversible with undo() (most recent first).
  TeamUndo play_undoable(int board, Move m);
  void undo(const TeamUndo& u);

  // Cheap copy for referee checks and probe construction: each board is
  // rebuilt from its FEN with a single StateInfo (no pre-root history);
  // referee halfmove clocks and repetition counts are kept.
  void assign_light(const TeamState& other);

  // Hypothetical arrival (scenario copies only): add a piece to a hand on a
  // board without changing whose turn it is.
  void add_to_pocket(int board, Piece pc);

  Position& pos(int b) { return boards[b].pos; }
  const Position& pos(int b) const { return boards[b].pos; }

  // Copy of a board's history chain (relinked), suitable for
  // Threads.start_thinking() with pos(b) as the position.
  StateListPtr history_copy(int b) const;

  // ---- referee port ----
  bool has_legal_move(int b) const;
  bool is_checkmate(Color team, bool timeAdvantage);
  bool partner_can_provide_blocker(int boardInCheck, Color checkedSide, bool timeAdvantage);
  bool is_draw() const;
  Verdict verdict(bool advWhite, bool advBlack);

  // ---- queries ----
  std::string rep_key(int b) const;         // (placement with ~, turn, castling, legal ep)
  int repetitions(int b) const;             // count of the current key
  int halfmove(int b) const { return boards[b].halfmove; }
  int fullmove(int b) const;
  std::string placement(int b) const;       // board part of the FEN, with ~ markers
  std::string castling(int b) const;        // FEN castling field
  std::string legal_ep(int b) const;        // ep square if a legal ep capture exists, else "-"
  std::string pocket(int b, Color c) const; // "QRBNP" order, uppercase
  std::string fen(int b) const;             // engine FEN (FSF counters)
  std::string referee_fen(int b) const;     // FEN with referee halfmove clock
  int last_board() const { return lastBoard; }
  size_t move_count() const { return moves.size(); }
  const std::vector<std::pair<int, std::string>>& move_list() const { return moves; }

  // Sanity: stored hash keys equal a fresh Position::set() of the same FEN.
  bool keys_consistent(std::string& err) const;

  // What a move on pos would send to the partner (referee's _captured_type):
  // drops send nothing, en passant sends a pawn, promoted pieces go back as pawns.
  static PieceType captured_type(const Position& pos, Move m);

private:
  void init_board(int b);
  void record(int b);
  static void clone_board(const BoardState& src, BoardState& dst);
  bool has_useful_capture(Position& p, Bitboard pawnValid) const;

  BoardState boards[2];
  std::vector<std::pair<int, std::string>> moves;
  int lastBoard = -1;
};

/// Deterministic legal fallback: lexicographically smallest UCI string.
Move deterministic_fallback(const Position& pos);

} // namespace Stockfish::HB

#endif // #ifndef HB_TEAM_STATE_H_INCLUDED
