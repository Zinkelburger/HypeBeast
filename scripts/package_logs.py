#!/usr/bin/env python3
"""Package the match logs for publishing.

    scripts/package_logs.py [LOGS_DIR] [OUT_DIR]

For every match under LOGS_DIR (default logs/) that has games:

- OUT_DIR/<match>.tar.zst: everything the match wrote (results.jsonl, games.bpgn,
  manifest.json, summary.json, postmortem.jsonl, postmortem.md, engine_logs/, and
  the progress log <match>.log), with this machine's names taken out.
- data/matches/<match>/summary.json and postmortem.md: the two small files, in the
  repository itself.

and once:

- OUT_DIR/loss-analysis.tar.zst: the analysis scripts and their outputs.
- data/matches.md: one row per match (what played what, the score, the archive).

Machine names (home directory, host name, user id) are replaced before anything is
written, and the script fails if one is still present afterwards.
"""
import getpass
import io
import json
import os
import re
import socket
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "logs"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build" / "data-release"
DATA = ROOT / "data"

USER = getpass.getuser()
HOME = str(Path.home())
HOST = socket.gethostname()
UID = str(os.getuid())


def machine_names():
    """Home directory, every host name a manifest recorded, the user name, and the
    user id where it stands as one (a bare number could be a node count). Longest first."""
    hosts = {HOST, HOST.split(".")[0]}
    for m in LOGS.glob("*/manifest.json"):
        try:
            h = (json.loads(m.read_text()).get("environment") or {}).get("hostname")
        except ValueError:
            h = None
        if h:
            hosts |= {h, h.split(".")[0]}
    pairs = [(HOME.encode(), b"/home/user")]
    pairs += [(h.encode(), b"host") for h in sorted(hosts, key=len, reverse=True)]
    pairs += [(f"user-{UID}".encode(), b"user-0"), (f"user@{UID}".encode(), b"user@0"),
              (f"/run/user/{UID}".encode(), b"/run/user/0"), (USER.encode(), b"user")]
    return pairs


SCRUB = machine_names()
# The bare user id is not searched for: only the name, the home and the hosts must be gone.
LEFT = re.compile(b"|".join(re.escape(a) for a, _ in SCRUB if not a.startswith((b"user-", b"user@", b"/run/user/"))))


def scrub(data: bytes) -> bytes:
    for a, b in SCRUB:
        data = data.replace(a, b)
    if LEFT.search(data):
        raise SystemExit("a machine name survived the scrub")
    return data


def archive(dest: Path, files):
    """files: (path on disk, name in the archive). Text is scrubbed; nothing else is expected."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    zstd = subprocess.Popen(["zstd", "-q", "-19", "-T2", "-o", str(dest), "-f"], stdin=subprocess.PIPE)
    with tarfile.open(fileobj=zstd.stdin, mode="w|") as tar:
        for path, name in files:
            data = scrub(path.read_bytes())
            info = tarfile.TarInfo(scrub(name.encode()).decode())
            info.size = len(data)
            info.mtime = int(path.stat().st_mtime)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    zstd.stdin.close()
    if zstd.wait() != 0:
        raise SystemExit(f"zstd failed on {dest}")


def spec(side):
    """bin and options of one side, as short as they can be said."""
    opts = dict(side.get("options") or {})
    parts = [Path(side.get("binary") or side.get("kind", "?")).name]
    if side.get("nodes"):
        parts.append(f"nodes={side['nodes']}")
    if side.get("movetime_ms"):
        parts.append(f"movetime={side['movetime_ms']}")
    parts += [f"{k}={v}" for k, v in opts.items() if k not in ("Hash", "EvalFile")]
    return " ".join(parts)


def main():
    rows = []
    for d in sorted(p for p in LOGS.iterdir() if p.is_dir() and (p / "results.jsonl").exists()):
        name = d.name
        files = [(p, f"{name}/{p.relative_to(d)}") for p in sorted(d.rglob("*")) if p.is_file()]
        if (LOGS / f"{name}.log").exists():
            files.append((LOGS / f"{name}.log", f"{name}/{name}.log"))
        dest = OUT / f"{name}.tar.zst"
        archive(dest, files)
        small = DATA / "matches" / name
        small.mkdir(parents=True, exist_ok=True)
        for f in ("summary.json", "postmortem.md"):
            if (d / f).exists():
                (small / f).write_bytes(scrub((d / f).read_bytes()))
        games = sum(1 for _ in open(d / "results.jsonl"))
        s = json.loads(scrub((d / "summary.json").read_bytes())) if (d / "summary.json").exists() else {}
        started = ""
        if (d / "manifest.json").exists():
            sessions = json.loads((d / "manifest.json").read_text()).get("sessions") or []
            started = (sessions[0].get("started") or "")[:16].replace("T", " ") if sessions else ""
        c, b = s.get("contender", {}), s.get("baseline", {})
        score = (f"{s.get('contender_wins', '?')}-{s.get('contender_losses', '?')}-{s.get('draws', '?')}"
                 if s else "not summarised")
        rows.append((started, name, c.get("name", "?"), spec(c) if c else "", b.get("name", "?"), spec(b) if b else "",
                     games, score, f"{dest.stat().st_size / 1e6:.1f} MB"))
        print(f"{name}: {len(files)} files, {games} games, {dest.stat().st_size / 1e6:.1f} MB", flush=True)

    la = LOGS / "loss-analysis"
    if la.exists():
        archive(OUT / "loss-analysis.tar.zst",
                [(p, f"loss-analysis/{p.relative_to(la)}") for p in sorted(la.rglob("*"))
                 if p.is_file() and "__pycache__" not in p.parts])
        print(f"loss-analysis: {(OUT / 'loss-analysis.tar.zst').stat().st_size / 1e6:.1f} MB", flush=True)

    rows.sort()
    out = ["# Matches", "",
           "One row per match, oldest first. The score is the contender's: wins-losses-draws. A match stopped early",
           "has fewer games than it was started for; `EXPERIMENTS.md` says why (search it for the match name).",
           "Each archive is a file of the data release (see `data/README.md`).", "",
           "| started | match | contender | its binary and options | baseline | its binary and options | games | score | archive |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r[0]} | `{r[1]}` | {r[2]} | `{r[3]}` | {r[4]} | `{r[5]}` | {r[6]} | {r[7]} | `{r[1]}.tar.zst`, {r[8]} |")
    (DATA / "matches.md").write_text("\n".join(out) + "\n")
    print(f"{len(rows)} matches; index in {DATA / 'matches.md'}; archives in {OUT}")


if __name__ == "__main__":
    main()
