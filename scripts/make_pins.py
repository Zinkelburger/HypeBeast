#!/usr/bin/env python3
"""Write manifests/pins.json: upstream/fork source identities, build flags,
binary and net hashes. Run after building both binaries."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args, cwd=ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout.strip()


net = ROOT / "nets/bughouse-cd8cceab93fe.nnue"
compiler = subprocess.run(["g++", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
pins = {
    "fairy_stockfish_upstream": {
        "repo": "https://github.com/fairy-stockfish/Fairy-Stockfish",
        "requested": "4e3d014",
        "sha": git("rev-parse", "HEAD", cwd=ROOT / "upstream"),
        "tree": git("rev-parse", "HEAD^{tree}", cwd=ROOT / "upstream"),
        "note": "4e3d014 resolves to upstream master HEAD at clone time (2026-11-05 commit)",
    },
    "hypebeast_fork": {
        "path": "engine/ (tracked in this repo)",
        "pristine_import_commit": git("log", "--format=%H", "--diff-filter=A", "--", "engine/src/position.cpp").splitlines()[-1],
        "pristine_engine_tree_equals_upstream_tree": True,
        "repo_head": git("rev-parse", "HEAD"),
    },
    "build": {
        "command": "make -j22 build ARCH=x86-64-bmi2 COMP=gcc (in upstream/src and engine/src)",
        "arch": "x86-64-bmi2", "comp": "gcc", "compiler": compiler,
        "largeboards": "no", "nnue_embedding": "off (EvalFile required)",
    },
    "binaries": {f"bin/{p.name}": sha256(p) for p in sorted((ROOT / "bin").iterdir()) if p.is_file()},
    "binary_notes": {
        "bin/hypebeast": "v1, frozen for the screen20 screening matches (engine commit c7c9f94)",
        "bin/hypebeast-v2": "v2 = v1 + exposure veto (engine commit 69dc856); tuned on debug.txt only",
        "bin/hypebeast-v3": "v3 = v2 + feed prices, exposure tiers, stalling, delivery-win waits (engine commit c8f5abd); tuned on debug.txt only",
    },
    "net": {
        "file": "nets/" + net.name,
        "sha256": sha256(net),
        "bytes": net.stat().st_size,
        "source": "https://fairy-stockfish.github.io/nnue/ (bughouse row, 2023/01/24, Google Drive id 1qZVSzm5G_KRc33YCqmsPM6Ayxo3CI4ME)",
        "loads_for": "UCI_Variant=bughouse (info string NNUE evaluation using ... enabled)",
    },
    "hivemind_checkout": {
        "path": "~/Projects/hivemind (reference only; installed arena binary pinned by the arena)",
        "sha": git("rev-parse", "HEAD", cwd=Path.home() / "Projects/hivemind"),
    },
}
out = ROOT / "manifests/pins.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(pins, indent=2) + "\n")
print(out.read_text())
