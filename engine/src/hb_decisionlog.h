/*
  HypeBeast, a bughouse team engine built on Fairy-Stockfish
  Copyright (C) 2026 HypeBeast authors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
*/

// Per-go record of every search request/result, the aggregate
// 'info string hb_summary' line, and optional JSONL output
// (environment variable HB_DECISION_LOG=<path>).

#ifndef HB_DECISIONLOG_H_INCLUDED
#define HB_DECISIONLOG_H_INCLUDED

#include <map>
#include <string>
#include <vector>

#include "hb_probe.h"

namespace Stockfish::HB {

class DecisionLog {
public:
  struct Entry {
    Phase phase;
    std::string tag;
    ProbeResult result;
  };

  void clear();
  void add(Phase phase, const std::string& tag, const ProbeResult& r);
  void set(const std::string& key, const std::string& value) { fields[key] = value; }

  uint64_t nodes(Phase p) const;
  uint64_t total_nodes() const;
  int searches(Phase p) const;
  int child_searches() const;
  int exact_child_searches() const;
  TimePoint child_ms() const;
  TimePoint clear_ms() const;
  const std::vector<Entry>& entries() const { return log; }

  // Key=value pairs for 'info string hb_summary ...' (single line).
  std::string summary(TimePoint elapsed) const;
  // Append one JSON line to $HB_DECISION_LOG if set.
  void flush_jsonl(TimePoint elapsed) const;

private:
  std::vector<Entry> log;
  std::map<std::string, std::string> fields;
};

} // namespace Stockfish::HB

#endif // #ifndef HB_DECISIONLOG_H_INCLUDED
