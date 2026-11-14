/*
  Stockfish, a UCI chess playing engine derived from Glaurung 2.1
  Copyright (C) 2004-2022 The Stockfish developers (see AUTHORS file)

  Stockfish is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  Stockfish is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#include <algorithm>
#include <cassert>
#include <ostream>
#include <sstream>
#include <iostream>

#include "evaluate.h"
#include "hb_arena.h"
#include "misc.h"
#include "piece.h"
#include "search.h"
#include "thread.h"
#include "tt.h"
#include "uci.h"
#include "variant.h"
#include "syzygy/tbprobe.h"

using std::string;

namespace Stockfish {

UCI::OptionsMap Options; // Global object

namespace PSQT {
  void init(const Variant* v);
}

namespace UCI {

// standard variants of XBoard/WinBoard
std::set<string> standard_variants = {
    "normal", "nocastle", "fischerandom", "knightmate", "3check", "makruk", "shatranj",
    "asean", "seirawan", "crazyhouse", "bughouse", "suicide", "giveaway", "losers", "atomic",
    "capablanca", "gothic", "janus", "caparandom", "grand", "shogi", "xiangqi", "duck",
    "berolina", "spartan"
};

void init_variant(const Variant* v) {
    pieceMap.init(v);
    Bitboards::init_pieces();
}

/// 'On change' actions, triggered by an option's value change
void on_clear_hash(const Option&) { Search::clear(); }
void on_hash_size(const Option& o) { TT.resize(size_t(o)); }
void on_logger(const Option& o) { start_logger(o); }
void on_threads(const Option& o) { Threads.set(size_t(o)); }
void on_tb_path(const Option& o) { Tablebases::init(o); }
void on_hypebeast(const Option&) { HB::Arena::on_hypebeast_option(); }

void on_use_NNUE(const Option& ) { Eval::NNUE::init(); }
void on_eval_file(const Option& ) { Eval::NNUE::init(); }

void on_variant_path(const Option& o) {
    std::stringstream ss((std::string)o);
    std::string path;

    while (std::getline(ss, path, SepChar))
        variants.parse<false>(path);

    Options["UCI_Variant"].set_combo(variants.get_keys());
}
void on_variant_set(const Option &o) {
    // Re-initialize NNUE
    Eval::NNUE::init();

    const Variant* v = variants.find(o)->second;
    init_variant(v);
    PSQT::init(v);

    // Load the tablebases of the variant
    Tablebases::init(Options["SyzygyPath"]);
}
void on_variant_change(const Option &o) {
    // Variant initialization
    on_variant_set(o);

    const Variant* v = variants.find(o)->second;
    // Do not send setup command for known variants
    if (standard_variants.find(o) != standard_variants.end())
        return;
    int pocketsize = v->pieceDrops ? (v->pocketSize ? v->pocketSize : popcount(v->pieceTypes)) : 0;
    if (CurrentProtocol == XBOARD)
    {
        // Overwrite setup command for Janggi variants
        auto itJanggi = variants.find("janggi");
        if (   itJanggi != variants.end()
            && v->variantTemplate == itJanggi->second->variantTemplate
            && v->startFen == itJanggi->second->startFen
            && v->pieceToCharTable == itJanggi->second->pieceToCharTable)
        {
            sync_cout << "setup (PH.R.AE..K.C.ph.r.ae..k.c.) 9x10+0_janggi "
                      << "rhea1aehr/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/RHEA1AEHR w - - 0 1"
                      << sync_endl;
            return;
        }
        // Send setup command
        sync_cout << "setup (" << v->pieceToCharTable << ") "
                  << v->maxFile + 1 << "x" << v->maxRank + 1
                  << "+" << pocketsize << "_" << v->variantTemplate
                  << " " << v->startFen
                  << sync_endl;
        // Send piece command with Betza notation
        // https://www.gnu.org/software/xboard/Betza.html
        for (PieceSet ps = v->pieceTypes; ps;)
        {
            PieceType pt = pop_lsb(ps);
            string suffix =   pt == PAWN && v->doubleStep     ? "ifmnD"
                            : pt == KING && v->cambodianMoves ? "ismN"
                            : pt == FERS && v->cambodianMoves ? "ifD"
                                                              : "";
            // Janggi palace moves
            if (v->diagonalLines)
            {
                PieceType pt2 = pt == KING ? v->kingType : pt;
                if (pt2 == WAZIR)
                    suffix += "F";
                else if (pt2 == SOLDIER)
                    suffix += "fF";
                else if (pt2 == ROOK)
                    suffix += "B";
                else if (pt2 == JANGGI_CANNON)
                    suffix += "pB";
            }
            // Castling
            if (pt == KING && v->castling)
                 suffix += "O" + std::to_string((v->castlingKingsideFile - v->castlingQueensideFile) / 2);
            // Drop region
            if (v->pieceDrops)
            {
                if (pt == PAWN && !v->firstRankPawnDrops)
                    suffix += "j";
                else if (pt == v->dropNoDoubled)
                    suffix += std::string(v->dropNoDoubledCount, 'f');
                else if (pt == BISHOP && v->dropOppositeColoredBishop)
                    suffix += "s";
                suffix += "@" + std::to_string(pt == PAWN && !v->promotionZonePawnDrops && v->promotionRegion[WHITE] ? rank_of(lsb(v->promotionRegion[WHITE])) : v->maxRank + 1);
            }
            sync_cout << "piece " << v->pieceToChar[pt] << "& " << pieceMap.find(pt == KING ? v->kingType : pt)->second->betza << suffix << sync_endl;
            PieceType promType = v->promotedPieceType[pt];
            if (promType)
                sync_cout << "piece +" << v->pieceToChar[pt] << "& " << pieceMap.find(promType)->second->betza << sync_endl;
        }
    }
    else
        sync_cout << "info string variant " << (std::string)o
                << " files " << v->maxFile + 1
                << " ranks " << v->maxRank + 1
                << " pocket " << pocketsize
                << " template " << v->variantTemplate
                << " startpos " << v->startFen
                << sync_endl;
}


/// Our case insensitive less() function as required by UCI protocol
bool CaseInsensitiveLess::operator() (const string& s1, const string& s2) const {

  return std::lexicographical_compare(s1.begin(), s1.end(), s2.begin(), s2.end(),
         [](char c1, char c2) { return tolower(c1) < tolower(c2); });
}


/// UCI::init() initializes the UCI options to their hard-coded default values

void init(OptionsMap& o) {

  constexpr int MaxHashMB = Is64Bit ? 33554432 : 2048;

  o["Debug Log File"]        << Option("", on_logger);
  o["Threads"]               << Option(1, 1, 512, on_threads);
  o["Hash"]                  << Option(16, 1, MaxHashMB, on_hash_size);
  o["Clear Hash"]            << Option(on_clear_hash);
  o["Ponder"]                << Option(false);
  o["MultiPV"]               << Option(1, 1, 500);
  o["Skill Level"]           << Option(20, -20, 20);
  o["Move Overhead"]         << Option(10, 0, 5000);
  o["Slow Mover"]            << Option(100, 10, 1000);
  o["nodestime"]             << Option(0, 0, 10000);
  o["UCI_Chess960"]          << Option(false);
  o["UCI_Variant"]           << Option("chess", variants.get_keys(), on_variant_change);
  o["UCI_AnalyseMode"]       << Option(false);
  o["UCI_LimitStrength"]     << Option(false);
  o["UCI_Elo"]               << Option(1350, 500, 2850);
  o["UCI_ShowWDL"]           << Option(false);
  o["SyzygyPath"]            << Option("<empty>", on_tb_path);
  o["SyzygyProbeDepth"]      << Option(1, 1, 100);
  o["Syzygy50MoveRule"]      << Option(true);
  o["SyzygyProbeLimit"]      << Option(7, 0, 7);
#ifdef __EMSCRIPTEN__
  // The page hands the net over with setNnueBuffer, which turns this on.
  o["Use NNUE"]              << Option(false, on_use_NNUE);
#else
  o["Use NNUE"]              << Option(true, on_use_NNUE);
#endif
#ifndef NNUE_EMBEDDING_OFF
  o["EvalFile"]              << Option(EvalFileDefaultName, on_eval_file);
#else
  o["EvalFile"]              << Option("<empty>", on_eval_file);
#endif
  o["TsumeMode"]             << Option(false);
  o["VariantPath"]           << Option("<empty>", on_variant_path);
  o["usemillisec"]           << Option(true); // time unit for UCCI
  // HypeBeast arena mode (off by default: upstream behaviour)
  o["HypeBeast"]             << Option(false, on_hypebeast);
  o["Coordination"]          << Option(true);
  o["HBFeedPrices"]          << Option(true);   // price captures across boards in the main search
  o["HBStall"]               << Option(true);   // sit to deny a verified fed mate when the clocks allow
  o["HBWorlds"]              << Option(true);   // forecast arrivals and choose over weighted worlds (v4)
  o["HBHold"]                << Option(true);   // sit when mated by force or while the partner mates (v5)
  o["HBRescue"]              << Option(true);   // price the piece that ends a sitting partner's mate (v5)
  o["HBWorldSwitch"]         << Option(true);   // false: keep the forecast, spend the worlds' share on the main search
  o["HBPlayOn"]              << Option(true);   // a mated seat plays the mate out while its sitting is what would stop the other board (v6)
  o["HBDraws"]               << Option(true);   // take the referee's repetition draw when lost, refuse it otherwise (v6)
  o["HBFeedHold"]            << Option(false);  // sit while the best line loses a piece that mates on the partner board (v6: measured, no gain)
  o["HBPhantom"]             << Option(0, 0, 3000);      // cp: what a mate needing one pawn not in hand adds to the position it starts from (other types by how often they arrive); 0: off
  o["HBPhantomOwn"]          << Option(true);            // false: only the opponent's phantom mates count
  o["HBHandDiscount"]        << Option(0, -200, 200);    // cp taken off for each point of hand material held more than the opponent (negative: added); 0: off
  o["HBTeamScore"]           << Option(0, 0, 200);       // %: share of the partner's told score added to ours in every world's winning chance; 0: off (needs HBTell=plan or minimal)
  o["HBKingDanger"]          << Option(0, 0, 500);       // cp taken off for each square of the king's zone the opponent attacks beyond two, and added for the opponent's king; 0: off (AUTOPSY2.md)
  o["HBWorldMaxGap"]         << Option(4000, 0, 4000);   // cp: a world switch may cost this much when nothing arrives, unless an arrival mates the main choice; 4000: no limit (v6)
  o["HBPriceScale"]          << Option(50, 0, 200);      // %: share of a piece's measured gain on the partner board that is its price
  o["HBPriceCap"]            << Option(500, 0, 2000);    // cp: the most a price can be, mates apart
  o["HBPriceKeepTable"]      << Option(false);           // keep the main hash table between moves while every feed price is zero (v7d)
  o["HBPriceShare"]          << Option(10, 0, 100);      // permille of the go for each partner-board price probe; 0: depth 3 (v5)
  o["HBMainShare"]           << Option(66, 30, 90);      // %: prices, forecast and main search together (58 through v5)
  o["HBForecastTemp"]        << Option(250, 10, 2000);   // cp: how sharply better partner-board lines are favoured
  o["HBForecastTrust"]       << Option(85, 0, 100);      // %: share of a forecast arrival that is believed
  o["HBForecastTrustLate"]   << Option(0, 0, 100);       // %: the same for captures 3-4 plies into a line (0: v4 as measured)
  o["HBMaxWorlds"]           << Option(4, 2, 8);         // worlds chosen over, "nothing arrives" included (4 through v7d)
  o["HBForecastScan"]        << Option(4, 2, 8);         // plies of each forecast line read for late captures (4 through v7d)
  o["HBArrivalTiming"]       << Option(0, 0, 2);         // in a world, a forecast piece cannot be dropped before the move it could arrive on: 0 off (through v7e), 1 captures 3+ plies into a line, 2 every capture
  o["HBForecastPrice"]       << Option(50, 0, 200);      // %: how much of a capture's value on our board counts there
  o["HBWinScale"]            << Option(1000, 50, 4000);   // cp per logistic unit of winning chances
  o["HBTell"]                << Option("off");            // partner talk (PARTNER_TALK.md): off, alarm, worth, table, minimal or plan ('+' joins); what this seat tells and how it hears
  o["HBPartnerTell"]         << Option("none");           // the partner's last hb_tell text, set by the arena; none: nothing heard
  o["HBPlanTrust"]           << Option(60, 0, 100);       // %: weight of the partner's told line among our own forecast lines (HBTell=plan)
  o["HBMateGuard"]           << Option(false);            // price only a piece of ours whose loss mates our partner, probing only the types that can be taken now, a queen, and last go's (v8h); overrides HBFeedPrices
  o["HBMateGuardFloor"]      << Option(-100000, -100000, 100000);  // cp: HBMateGuard prices nothing while the partner's board, in our team's view, is below this; -100000: always priced
  o["HBMateGuardQuiet"]      << Option(false);            // HBMateGuard with no mate priced: the go without prices in every respect but the probes (v8i)
  o["HBTellFloor"]           << Option(-100000, -100000, 100000);  // cp: a message is not honoured while the teller's own board (base=) is below this (v8i)
  o["HBTellMin"]             << Option(0, 0, 5000);       // cp: a told cost or worth below this is not priced; mates always are (v8i)
  o["HBTellLossesOnly"]      << Option(false);            // honour only what the teller loses when its opponent gets a piece (v8i)
  o["HBTellRoot"]            << Option(false);            // a heard message prices nothing in the search; what each candidate hands over (its capture: the teller's +T, the expected reply's capture: its -T) is added to its value at the choice (v8j)
  o["HBTellRootSide"]        << Option(0, 0, 2);          // HBTellRoot counts 0: both, 1: only what our capture gives the partner, 2: only what the expected reply costs it (v8k)
  o["HBTellRootMaxCost"]     << Option(-1, -1, 4000);     // cp: HBTellRoot counts a candidate's feed only if it costs at most this much when nothing arrives (main L minus its L); -1: no limit (v8k, the user's tie-break)
  o["HBPlanTrustLate"]       << Option(-1, -1, 100);     // %: HBForecastTrustLate for the partner's told line; -1: the same as for our own lines
  o["HBTableShare"]          << Option(5, 0, 50);         // permille of the go for each table search (HBTell=table); 0: none
  o["Seat"]                  << Option("Awhite", {"Awhite", "Ablack", "Bwhite", "Bblack"});
  o["Clocks"]                << Option("");
  // Arena/HiveMind names and semantics: Team white = White on A + Black on B
  o["Team"]                  << Option("white", {"white", "black"});
  o["TimeAdvantage"]         << Option(false);
}


/// operator<<() is used to print all the options default values in chronological
/// insertion order (the idx field) and in the format defined by the UCI protocol.

std::ostream& operator<<(std::ostream& os, const OptionsMap& om) {

  if (CurrentProtocol == XBOARD)
  {
      for (size_t idx = 0; idx < om.size(); ++idx)
          for (const auto& it : om)
              if (it.second.idx == idx && it.first != "UCI_Variant" && it.first != "Threads" && it.first != "Hash")
              {
                  const Option& o = it.second;
                  os << "\nfeature option=\"" << it.first << " -" << o.type;

                  if (o.type == "string" || o.type == "combo")
                      os << " " << o.defaultValue;
                  else if (o.type == "check")
                      os << " " << int(o.defaultValue == "true");

                  if (o.type == "combo")
                      for (string value : o.comboValues)
                          if (value != o.defaultValue)
                              os << " /// " << value;

                  if (o.type == "spin")
                      os << " " << int(stof(o.defaultValue))
                         << " " << o.min
                         << " " << o.max;

                  os << "\"";

                  break;
              }
  }
  else

  for (size_t idx = 0; idx < om.size(); ++idx)
      for (const auto& it : om)
          if (it.second.idx == idx)
          {
              const Option& o = it.second;
              // UCI dialects do not allow spaces
              if (CurrentProtocol == UCCI || CurrentProtocol == USI)
              {
                  string name = option_name(it.first);
                  // UCCI skips "name"
                  os << "\noption " << (CurrentProtocol == UCCI ? "" : "name ") << name << " type " << o.type;
              }
              else
                  os << "\noption name " << it.first << " type " << o.type;

              if (o.type == "string" || o.type == "check" || o.type == "combo")
                  os << " default " << o.defaultValue;

              if (o.type == "combo")
                  for (string value : o.comboValues)
                      os << " var " << value;

              if (o.type == "spin")
                  os << " default " << int(stof(o.defaultValue))
                     << " min "     << o.min
                     << " max "     << o.max;

              break;
          }

  return os;
}


/// Option class constructors and conversion operators

Option::Option(const char* v, OnChange f) : type("string"), min(0), max(0), on_change(f)
{ defaultValue = currentValue = v; }

Option::Option(const char* v, const std::vector<std::string>& values, OnChange f) : type("combo"), min(0), max(0), comboValues(values), on_change(f)
{ defaultValue = currentValue = v; }

Option::Option(bool v, OnChange f) : type("check"), min(0), max(0), on_change(f)
{ defaultValue = currentValue = (v ? "true" : "false"); }

Option::Option(OnChange f) : type("button"), min(0), max(0), on_change(f)
{}

Option::Option(double v, int minv, int maxv, OnChange f) : type("spin"), min(minv), max(maxv), on_change(f)
{ defaultValue = currentValue = std::to_string(v); }

Option::operator double() const {
  assert(type == "check" || type == "spin");
  return (type == "spin" ? stof(currentValue) : currentValue == "true");
}

Option::operator std::string() const {
  assert(type == "string" || type == "combo");
  return currentValue;
}

bool Option::operator==(const char* s) const {
  assert(type == "combo");
  return   !CaseInsensitiveLess()(currentValue, s)
        && !CaseInsensitiveLess()(s, currentValue);
}

bool Option::operator!=(const char* s) const {
  assert(type == "combo");
  return !(*this == s);
}


/// operator<<() inits options and assigns idx in the correct printing order

void Option::operator<<(const Option& o) {

  static size_t insert_order = 0;

  *this = o;
  idx = insert_order++;
}


/// operator=() updates currentValue and triggers on_change() action. It's up to
/// the GUI to check for option's limits, but we could receive the new value
/// from the user by console window, so let's check the bounds anyway.

Option& Option::operator=(const string& v) {

  assert(!type.empty());

  if (   (type != "button" && v.empty())
      || (type == "check" && v != "true" && v != "false")
      || (type == "combo" && (std::find(comboValues.begin(), comboValues.end(), v) == comboValues.end()))
      || (type == "spin" && (stof(v) < min || stof(v) > max)))
      return *this;

  if (type == "combo")
  {
      OptionsMap comboMap; // To have case insensitive compare
      for (string token : comboValues)
          comboMap[token] << Option();
      if (!comboMap.count(v) || v == "var")
          return *this;
  }

  if (type != "button")
      currentValue = v;

  if (on_change)
      on_change(*this);

  return *this;
}

void Option::set_combo(std::vector<std::string> newComboValues) {
    comboValues = newComboValues;
}

void Option::set_default(std::string newDefault) {
    defaultValue = currentValue = newDefault;

    // When changing the variant default, suppress variant definition output,
    // but still do the essential re-initialization of the variant
    if (on_change)
        (on_change == on_variant_change ? on_variant_set : on_change)(*this);
}

const std::string Option::get_type() const {
    return type;
}

} // namespace UCI

} // namespace Stockfish
