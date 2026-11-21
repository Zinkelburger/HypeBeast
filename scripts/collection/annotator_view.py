#!/usr/bin/env python3
"""A fact sheet cut down to what an annotator reads: the whole game as a move
list, and for each key move its facts and lines without the per-move FENs and
the search commands. Writes logs/collection/view/<id>.json (about a tenth of
the fact sheet). Nothing here is new information; the fact sheet stays the
source."""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "logs" / "collection"
LINE_FACTS = ("purpose", "source", "why_listed", "score_mover_cp", "score_mover_mate", "truncated_from",
              "played_move_same_method", "world_best_from_game", "world_scores_cp_mover", "engine_mate_count")


def view(game: dict) -> dict:
    moves = game["moves"]
    out = {k: game[k] for k in ("id", "event", "date", "seats", "teams", "result", "initial_clock")}
    out["how_to_read"] = ("game: every move in the order played. eval/mate are from that board's White. "
                          "key_moves: the moves to annotate, with the position before and after on both boards "
                          "(FEN, reserves in brackets), the mover's engine facts and the engine's lines. "
                          "See scripts/collection/README.md for every field.")
    out["game"] = [
        {k: v for k, v in {
            "i": m["i"], "board": m["board"], "seat": m["seat"], "num": m["num"], "san": m["san"], "t": m["t"],
            "eval": m["eval"], "mate": m["mate"], "book": m["book"] or None, "waited": m["waited"],
            "reason": (m.get("facts") or {}).get("reason"),
            "own_best": (m.get("facts") or {}).get("own_best_san"),
            "key": bool((m.get("facts") or {}).get("key")) or None,
        }.items() if v is not None}
        for m in moves
    ]
    keys = []
    for m in moves:
        facts = m.get("facts") or {}
        if not facts.get("key"):
            continue
        before = moves[m["i"] - 1]["fen"] if m["i"] else game["start"]
        keys.append({
            "i": m["i"], "board": m["board"], "seat": m["seat"], "num": m["num"], "san": m["san"],
            "fen_before": before, "fen_after": m["fen"], "clocks_after": m["clocks"], "waited": m["waited"],
            "facts": facts,
            "lines": [{
                "id": ln["id"], "kind": ln["kind"], "from": ln["from"], "board": ln["board"], "assume": ln["assume"],
                "start": ln["start"], "moves": " ".join(x["san"] for x in ln["moves"]),
                "eval_white": ln["eval"], "mate_white": ln["mate"],
                "facts": {k: ln["facts"][k] for k in LINE_FACTS if k in ln.get("facts", {})},
            } for ln in m["lines"]],
        })
    out["key_moves"] = keys
    last = moves[-1].get("facts") or {}
    if last.get("sitting_at_end") and not last.get("key"):
        out["sitting_at_end"] = last["sitting_at_end"]
    return out


def main():
    ids = sys.argv[1:] or sorted(p.stem for p in (OUT / "facts").glob("*.json"))
    (OUT / "view").mkdir(exist_ok=True)
    for gid in ids:
        game = json.loads((OUT / "facts" / f"{gid}.json").read_text())
        path = OUT / "view" / f"{gid}.json"
        path.write_text(json.dumps(view(game), indent=1) + "\n")
        print(path, path.stat().st_size)


if __name__ == "__main__":
    main()
