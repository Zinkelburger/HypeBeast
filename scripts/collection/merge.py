#!/usr/bin/env python3
"""Fact sheet + filled notes -> the publishable game file and index.json.

    python3 scripts/collection/merge.py [ID ...]   (default: every fact sheet)

Reads logs/collection/facts/<id>.json and logs/collection/notes/<id>.json
(falling back to the unfilled <id>.todo.json, which publishes the game with no
text). Writes logs/collection/site/<id>-<first 10 hex of sha256>.json with every
`facts` and `builder` object removed, and logs/collection/site/index.json.
Only the fields notes_template.py lists are read from the notes; check.py
verifies the result.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
import copy  # noqa: E402
import datetime  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "logs" / "collection"
SOURCE = ("Bughouse games played by HypeBeast 1.1.1, a Fairy-Stockfish fork that plays one board while "
          "pricing the other, against HypeBeast 1.1.0 and against itself, at fixed node budgets on a virtual clock. "
          "Each game starts from the first 16 moves of a rated game between people (FICS, 2014), and the engines "
          "play on from there. The scores are the engines' own.")


def load_notes(gid: str) -> dict:
    for name in (f"{gid}.json", f"{gid}.todo.json"):
        p = OUT / "notes" / name
        if p.exists():
            return json.loads(p.read_text())
    return {"title": None, "summary": None, "moves": [], "extra_notes": {}}


def strip(game: dict) -> dict:
    out = copy.deepcopy(game)
    out.pop("builder", None)
    for mv in out["moves"]:
        mv.pop("facts", None)
        for ln in mv["lines"]:
            ln.pop("facts", None)
    return out


def merge(facts: dict, notes: dict) -> dict:
    game = strip(facts)
    game["title"] = notes.get("title")
    game["summary"] = notes.get("summary")
    by_i = {mv["i"]: mv for mv in game["moves"]}
    for nm in notes.get("moves", []):
        mv = by_i.get(nm.get("i"))
        if mv is None:
            continue
        mv["glyph"] = nm.get("glyph")
        mv["note"] = nm.get("note")
        lnotes = {ln.get("id"): ln for ln in nm.get("lines", [])}
        kept = []
        for ln in mv["lines"]:
            n = lnotes.get(ln["id"], {})
            if n.get("drop"):
                continue
            ln["note"] = n.get("note")
            kept.append(ln)
        mv["lines"] = kept
    for i, text in (notes.get("extra_notes") or {}).items():
        mv = by_i.get(int(i))
        if mv is not None and mv["note"] is None:
            mv["note"] = text
    return game


def serialize(game: dict) -> bytes:
    return (json.dumps(game, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def main():
    ids = sys.argv[1:] or sorted(p.stem for p in (OUT / "facts").glob("*.json"))
    # HB_COLLECTION_SITE: another output folder, so several annotators can merge at once
    site = Path(os.environ.get("HB_COLLECTION_SITE") or OUT / "site")
    site.mkdir(parents=True, exist_ok=True)
    sel = OUT / "selection.json"
    order = json.loads(sel.read_text())["picked"] if sel.exists() else ids
    entries = {}
    for gid in ids:
        facts = json.loads((OUT / "facts" / f"{gid}.json").read_text())
        game = merge(facts, load_notes(gid))
        data = serialize(game)
        name = f"{gid}-{hashlib.sha256(data).hexdigest()[:10]}.json"
        for old in site.glob(f"{gid}-*.json"):
            if old.name != name:
                old.unlink()
        (site / name).write_bytes(data)
        entries[gid] = {"id": gid, "file": name, "title": game["title"], "summary": game["summary"],
                        "event": game["event"], "date": game["date"], "seats": game["seats"],
                        "winner": game["result"]["winner"], "how": game["result"]["how"],
                        "moves": len(game["moves"]), "notes": sum(1 for m in game["moves"] if m["note"])}
        print(f"site/{name}")
    # keep entries of games merged earlier but not named this time
    index_path = site / "index.json"
    if index_path.exists() and sys.argv[1:]:
        for e in json.loads(index_path.read_text())["games"]:
            entries.setdefault(e["id"], e)
    games = [entries[g] for g in order if g in entries] + [e for g, e in entries.items() if g not in order]
    index = {"version": 1, "generated": datetime.date.today().isoformat(), "source": SOURCE, "games": games}
    index_path.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n")
    print(f"site/index.json: {len(games)} games")


if __name__ == "__main__":
    main()
