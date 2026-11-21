#!/usr/bin/env python3
"""The annotator's to-do list for each fact sheet.

    python3 scripts/collection/notes_template.py [ID ...]   (default: every fact sheet)

Writes logs/collection/notes/<id>.todo.json. The annotator copies it to
logs/collection/notes/<id>.json and fills in only these:

  title                 at most 60 characters
  summary               one to three sentences
  moves[].glyph         key moves only: null or one of ! !! ? ?? !? ?!
  moves[].note          key moves only: plain text, at most 500 characters
  moves[].lines[].note  a note on one of that key move's lines
  moves[].lines[].drop  true to leave that line out of the published game
  extra_notes           {"<move index>": "text"} for a note on a move that is
                        not key (no glyph, no lines)

Everything else in the file (san, kind, first, the facts pointer) is there to
show what is being annotated; merge.py reads only the fields above, and
check.py fails a merged game whose notes changed anything but text.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
import hashlib  # noqa: E402
import json  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "logs" / "collection"


def todo_for(facts: dict, facts_sha: str) -> dict:
    moves = []
    for mv in facts["moves"]:
        if not (mv.get("facts") or {}).get("key"):
            continue
        moves.append({
            "i": mv["i"], "board": mv["board"], "num": mv["num"], "san": mv["san"],
            "why_key": mv["facts"]["key"],
            "glyph": None, "note": None,
            "lines": [{"id": ln["id"], "kind": ln["kind"], "from": ln["from"],
                       "moves": " ".join(m["san"] for m in ln["moves"]),
                       "note": None, "drop": False} for ln in mv["lines"]],
        })
    return {
        "id": facts["id"], "facts_file": f"logs/collection/facts/{facts['id']}.json", "facts_sha256": facts_sha,
        "how_to": ("Fill only title, summary, and for the key moves glyph, note, lines[].note and lines[].drop; "
                   "add notes on other moves under extra_notes as {\"<i>\": \"text\"}. Plain text, moves in SAN exactly "
                   "as in the fact sheet, no move the fact sheet does not contain. Notes at most 500 characters, "
                   "the title at most 60. Save as logs/collection/notes/<id>.json."),
        "title": None, "summary": None, "moves": moves, "extra_notes": {},
    }


def main():
    ids = sys.argv[1:] or sorted(p.stem for p in (OUT / "facts").glob("*.json"))
    for gid in ids:
        path = OUT / "facts" / f"{gid}.json"
        raw = path.read_bytes()
        todo = todo_for(json.loads(raw), hashlib.sha256(raw).hexdigest())
        dest = OUT / "notes" / f"{gid}.todo.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(todo, indent=1, ensure_ascii=False) + "\n")
        print(f"{dest.relative_to(ROOT)}: {len(todo['moves'])} key moves, "
              f"{sum(len(m['lines']) for m in todo['moves'])} lines")


if __name__ == "__main__":
    main()
