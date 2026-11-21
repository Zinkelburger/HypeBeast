"""What the match logs say about each opening.

An opening is useful for telling two engines apart when its two games (same
opening, teams swapped) do not split 1-1. This module reads every
`results.jsonl` under the given log roots and counts, per opening:

  pairs       complete pairs played on it (both games present, no error)
  decisive    pairs whose two games did not split 1-1
  expected    how many decisive pairs an average opening would have had in
              the same matches: the sum, over its pairs, of that match's own
              decisive share. Matches differ a lot (two nearly equal builds
              split almost every pair), so an opening is compared only with
              the other openings of the matches it was played in.
  usefulness  (decisive + PRIOR) / (expected + PRIOR): above 1 the opening
              separates engines more often than average. PRIOR pulls an
              opening with few pairs toward 1.
  games       distinct games on it (two games with the same move list count
              once: equal engines at a node budget replay each other)
  white       distinct games won by the team that has White on board A
  side        (white + SIDE_PRIOR/2) / (games + SIDE_PRIOR): that team's
              score, pulled toward 0.5

PRIOR = 8 was chosen by prediction: openings were scored on half of the
matches and used to predict which pairs were decisive in the other half
(30 random halvings of 60 matches, 8,363 games). Usefulness with a prior of
6 to 12 predicted best; adding the side score to it did not improve the
prediction, and the side score alone predicted a quarter as well. So the
side score is only a guard here, not the ranking.

Only HypeBeast against HypeBeast games count: a game against another engine
says how that engine handles the opening, which is not what these sets are
for.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIOR = 8.0
SIDE_PRIOR = 20.0
OTHER_ENGINES = ("hm", "fsf", "random")

ARENA_TOOLS = Path(os.environ.get("HB_ARENA_TOOLS", Path.home() / "Projects/Chess-Auto-Prep/tools"))


def default_log_roots() -> list[Path]:
    """This checkout's logs and those of the sibling worktrees (HypeBeast-*)."""
    roots = [ROOT / "logs"]
    roots += sorted(p / "logs" for p in ROOT.parent.glob(ROOT.name + "-*") if (p / "logs").is_dir())
    return [r for r in roots if r.is_dir()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_set(path: Path) -> list[tuple[str, str]]:
    """The openings of a set file, in order: (moves, provenance)."""
    out = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        out.append((" ".join(fields[0].split()), fields[1].strip() if len(fields) > 1 else ""))
    return out


def _hypebeast_only(match_dir: Path, record: dict) -> bool:
    manifest = match_dir / "manifest.json"
    if manifest.exists():
        try:
            sides = json.loads(manifest.read_text()).get("sides") or {}
            kinds = {s.get("kind") for s in sides.values()}
            if kinds:
                return kinds == {"hypebeast"}
        except (ValueError, AttributeError):
            pass
    return not any(str(record.get(k, "")).startswith(OTHER_ENGINES) for k in ("contender", "baseline"))


def load_matches(roots: list[Path]) -> dict[str, dict]:
    """Every match under the roots: its complete pairs and its games.

    Returns {match name: {"dir", "openings_sha256", "games": [...],
    "pairs": [{"opening", "source", "decisive", "games": (g, g)}]}}.
    A game is {"opening", "winner", "moves_hash"}.
    """
    matches: dict[str, dict] = {}
    for root in roots:
        for results in sorted(root.glob("**/results.jsonl")):
            match_dir = results.parent
            name = f"{root.parent.name}:{match_dir.relative_to(root)}"
            by_pair: dict[int, dict[str, dict]] = defaultdict(dict)
            games = []
            for line in results.read_text().splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                opening = r.get("opening") or {}
                result = r.get("result") or {}
                if "contender_score" not in r or not opening.get("moves") or result.get("error"):
                    continue
                if not _hypebeast_only(match_dir, r):
                    break
                game = {
                    "opening": " ".join(opening["moves"]),
                    "source": opening.get("source", ""),
                    "winner": result.get("winner"),
                    "moves_hash": hashlib.sha1(" ".join(result.get("moves") or []).encode()).hexdigest(),
                    "contender_score": r["contender_score"],
                }
                games.append(game)
                by_pair[r["pair"]][r["contender_team"]] = game
            pairs = []
            for both in by_pair.values():
                if len(both) == 2:
                    a, b = both["white"], both["black"]
                    pairs.append({"opening": a["opening"], "source": a["source"],
                                  "decisive": a["contender_score"] + b["contender_score"] != 1,
                                  "games": (a, b)})
            if not pairs:
                continue
            sha = None
            manifest = match_dir / "manifest.json"
            if manifest.exists():
                try:
                    sha = ((json.loads(manifest.read_text()).get("pins") or {}).get("openings") or {}).get("sha256")
                except ValueError:
                    pass
            matches[name] = {"dir": match_dir, "openings_sha256": sha, "games": games, "pairs": pairs}
    return matches


def measure(matches: dict[str, dict]) -> dict[str, dict]:
    """Per opening: the counts described in the module docstring."""
    stats: dict[str, dict] = {}
    distinct: dict[str, dict[str, str]] = defaultdict(dict)
    for match in matches.values():
        share = sum(p["decisive"] for p in match["pairs"]) / len(match["pairs"])
        for p in match["pairs"]:
            s = stats.setdefault(p["opening"], {"source": p["source"], "pairs": 0, "decisive": 0,
                                                "expected": 0.0, "matches": 0, "_seen": set()})
            s["pairs"] += 1
            s["decisive"] += p["decisive"]
            s["expected"] += share
            s["_seen"].add(id(match))
        for g in match["games"]:
            if g["winner"]:
                distinct[g["opening"]].setdefault(g["moves_hash"], g["winner"])
    for opening, s in stats.items():
        s["matches"] = len(s.pop("_seen"))
        won = distinct.get(opening, {})
        s["games"] = len(won)
        s["white"] = sum(w == "white" for w in won.values())
        s["usefulness"] = (s["decisive"] + PRIOR) / (s["expected"] + PRIOR)
        s["side"] = (s["white"] + SIDE_PRIOR / 2) / (s["games"] + SIDE_PRIOR)
    return stats


def board_sans(opening: str) -> tuple[list[str], list[str]]:
    """The opening's moves in SAN, per board (needs the arena's referee)."""
    if str(ARENA_TOOLS) not in sys.path:
        sys.path.insert(0, str(ARENA_TOOLS))
    from bughouse_arena.referee import Bughouse

    game = Bughouse()
    out: tuple[list[str], list[str]] = ([], [])
    for token in opening.split():
        b = int(token[0]) - 1
        board = game.boards[b]
        out[b].append(board.san(board.parse_uci(token[1:])))
        game.push(b, token[1:])
    return out


def sign_test(won: int, lost: int) -> float:
    """Two-sided: the chance that equal engines split won+lost decisive pairs
    at least this unevenly."""
    from math import comb

    n, k = won + lost, max(won, lost)
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)
