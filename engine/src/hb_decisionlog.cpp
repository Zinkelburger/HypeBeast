/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

#include <cstdlib>
#include <fstream>
#include <mutex>
#include <sstream>

#include "hb_decisionlog.h"

namespace Stockfish::HB {

void DecisionLog::clear() {
  log.clear();
  fields.clear();
}

void DecisionLog::add(Phase phase, const std::string& tag, const ProbeResult& r) {
  log.push_back({phase, tag, r});
}

uint64_t DecisionLog::nodes(Phase p) const {
  uint64_t n = 0;
  for (const auto& e : log)
      if (e.phase == p)
          n += e.result.nodes;
  return n;
}

uint64_t DecisionLog::total_nodes() const {
  uint64_t n = 0;
  for (const auto& e : log)
      n += e.result.nodes;
  return n;
}

int DecisionLog::searches(Phase p) const {
  int n = 0;
  for (const auto& e : log)
      n += e.phase == p && e.result.status == ProbeResult::OK;
  return n;
}

int DecisionLog::child_searches() const {
  int n = 0;
  for (const auto& e : log)
      n += e.phase != Phase::MAIN && e.result.status == ProbeResult::OK;
  return n;
}

int DecisionLog::exact_child_searches() const {
  int n = 0;
  for (const auto& e : log)
      n += e.phase != Phase::MAIN && e.result.usable_exact();
  return n;
}

TimePoint DecisionLog::child_ms() const {
  TimePoint t = 0;
  for (const auto& e : log)
      if (e.phase != Phase::MAIN)
          t += e.result.ms;
  return t;
}

TimePoint DecisionLog::clear_ms() const {
  TimePoint t = 0;
  for (const auto& e : log)
      t += e.result.clearMs;
  return t;
}

std::string DecisionLog::summary(TimePoint elapsed) const {
  std::ostringstream ss;
  for (const auto& f : fields)
      ss << f.first << "=" << f.second << " ";
  int requested = 0;
  for (const auto& e : log)
      requested += e.phase != Phase::MAIN;
  ss << "main_nodes=" << nodes(Phase::MAIN)
     << " child_requests=" << requested
     << " child_searches=" << child_searches()
     << " child_exact=" << exact_child_searches()
     << " discovery_nodes=" << nodes(Phase::DISCOVERY)
     << " probe_nodes=" << nodes(Phase::PROBES)
     << " child_ms=" << child_ms()
     << " clear_ms=" << clear_ms()
     << " total_nodes=" << total_nodes()
     << " elapsed_ms=" << elapsed;
  return ss.str();
}

void DecisionLog::flush_jsonl(TimePoint elapsed) const {
  const char* path = std::getenv("HB_DECISION_LOG");
  if (!path || !*path)
      return;
  static std::mutex mtx;
  std::lock_guard<std::mutex> lock(mtx);
  std::ofstream out(path, std::ios::app);
  if (!out)
      return;
  out << "{\"elapsed_ms\":" << elapsed << ",\"fields\":{";
  bool first = true;
  for (const auto& f : fields)
  {
      out << (first ? "" : ",") << "\"" << f.first << "\":\"" << f.second << "\"";
      first = false;
  }
  out << "},\"searches\":[";
  first = true;
  for (const auto& e : log)
  {
      out << (first ? "" : ",") << "{\"phase\":\"" << phase_name(e.phase)
          << "\",\"tag\":\"" << e.tag << "\",\"result\":" << result_json(e.result) << "}";
      first = false;
  }
  out << "]}\n";
}

} // namespace Stockfish::HB
