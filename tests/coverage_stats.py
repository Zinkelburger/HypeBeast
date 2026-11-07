"""Coordination coverage statistics from hb_summary key=value dicts.

    python3 tests/coverage_stats.py <engine log files or directories>...
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

COMPARED = ("kept_main", "override")


def coverage(summaries: list[dict]) -> dict:
    coord = [s for s in summaries if s.get("coord") == "1"]
    searched = [s for s in coord if "coord_reason" in s]
    reasons = Counter(s["coord_reason"] for s in searched)
    compared = sum(reasons[r] for r in COMPARED)
    overrides = sum(s.get("override") == "1" for s in searched)
    req = sum(int(s.get("probes_required", 0)) for s in searched)
    done = sum(int(s.get("probes_completed", 0)) for s in searched)
    waits = Counter(s.get("wait", "none").split("_")[0] for s in coord if s.get("reason") == "voluntary_wait")
    n = max(1, len(searched))
    def avg(key):
        vals = [int(s[key]) for s in searched if s.get(key, "").lstrip("-").isdigit()]
        return round(sum(vals) / len(vals), 2) if vals else None
    return {
        "decisions": len(summaries), "coordinated": len(coord), "coordinated_searches": len(searched),
        "compared_fraction": round(compared / n, 3), "override_count": overrides,
        "override_rate": round(overrides / n, 3),
        "probe_completion": f"{done}/{req}" + (f" ({done / req:.3f})" if req else ""),
        "fallback_rate": round(sum(s.get("used_fallback") == "1" for s in summaries) / max(1, len(summaries)), 4),
        "reasons": dict(reasons), "voluntary_waits": sum(waits.values()),
        "passes": sum(s.get("decision") == "pass" for s in summaries),
        "avg_main_depth": avg("main_depth"), "avg_common_depth": avg("common_depth"),
        "avg_candidates": avg("candidates"), "avg_enemy_scenarios": avg("scen_enemy"),
        "avg_friendly_scenarios": avg("scen_friendly"), "avg_elapsed_ms": avg("elapsed_ms"),
        "avg_total_nodes": avg("total_nodes"),
    }


def parse_files(paths: list[str]) -> list[dict]:
    out = []
    files = []
    for p in map(Path, paths):
        files += sorted(p.rglob("*")) if p.is_dir() else [p]
    for f in files:
        if not f.is_file():
            continue
        for line in f.read_text(errors="replace").splitlines():
            i = line.find("info string hb_summary ")
            if i >= 0:
                out.append(dict(kv.split("=", 1) for kv in line[i:].split()[3:] if "=" in kv))
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(coverage(parse_files(sys.argv[1:])), indent=2))
