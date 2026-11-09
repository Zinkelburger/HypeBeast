"""Child-probe infrastructure and shared go budget.

Checks: actual state untouched by probes, fixed-node determinism (within
and across processes), budget exhaustion and flow, target-depth flags,
cancellation, time slicing, main-search isolation from child TT/heuristics,
legal fallback, and go budget behaviour at arena scale (movetime 9652) and
at tiny limits.

    python3 tests/test_probe.py [--long]
"""

from __future__ import annotations

import json
import sys
import time

from hbutil import Engine, parse_bestmove, summary_fields

POS = "position startpos moves 1e2e4 2d2d4 1d7d5 1e4d5 2d7d5 1g8f6 2c2c4 1b1c3"
SEAT = {"Seat": "Ablack", "Team": "black"}
VOLATILE = ("ms", "clear_ms", "granted_ms")

failures = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"[{'ok' if ok else 'FAIL'}] {what}" + (f": {detail}" if detail else ""))


def probes(engine: Engine, args: str, timeout: float = 120) -> tuple[list[dict], str]:
    engine.send(f"hbprobe {args}")
    lines = engine.read_until("hbprobe done", timeout)
    results = [json.loads(l.split(" ", 2)[2]) for l in lines if l.startswith("hbprobe ") and not l.startswith("hbprobe done")]
    return results, lines[-1]


def stable(r: dict) -> dict:
    return {k: v for k, v in r.items() if k not in VOLATILE}


def done_fields(line: str) -> dict:
    return dict(kv.split("=", 1) for kv in line.split()[2:])


def main() -> int:
    long_run = "--long" in sys.argv
    e = Engine(options=SEAT)
    e.send(POS)
    before = e.hbstate()

    # Determinism: identical clean child searches give identical results.
    rs, _ = probes(e, "nodes 60000 count 1 clear 1")
    rs2, _ = probes(e, "nodes 60000 count 1 clear 1")
    check(rs[0]["status"] == "ok" and stable(rs[0]) == stable(rs2[0]),
          "fixed-node determinism (same process)", f"{rs[0]['move']} {rs[0]['score']} nodes={rs[0]['nodes']}")
    e2 = Engine(options=SEAT)
    e2.send(POS)
    rs3, _ = probes(e2, "nodes 60000 count 1 clear 1")
    check(stable(rs[0]) == stable(rs3[0]), "fixed-node determinism (fresh process)")
    e2.close()

    # Per-probe caps inside one budget: each probe identical, total within budget.
    rs, done = probes(e, "nodes 100000 count 3 maxnodes 20000 clear 1")
    d = done_fields(done)
    same = all(stable(r) == stable(rs[0]) for r in rs)
    check(same and all(r["status"] == "ok" for r in rs), "repeated capped probes identical",
          f"nodes={[r['nodes'] for r in rs]}")
    check(int(d["total_nodes"]) == sum(r["nodes"] for r in rs), "budget charged with every child node",
          f"total={d['total_nodes']}")

    # Exhaustion: the first probe takes the whole probe allowance (98% of the
    # budget with nothing spent earlier), later ones get no budget.
    rs, done = probes(e, "nodes 30000 count 3 clear 1")
    d = done_fields(done)
    check(rs[0]["status"] == "ok" and rs[0]["granted_nodes"] == 29400
          and [r["status"] for r in rs[1:]] == ["no_budget", "no_budget"],
          "budget exhaustion", f"granted={rs[0]['granted_nodes']} statuses={[r['status'] for r in rs]}")
    check(int(d["total_nodes"]) <= 30000 + 1024, "total nodes within budget (+check granularity)",
          f"{d['total_nodes']} of 30000")

    # Coordination off: no slices, the probe phase may use the full budget.
    rs, _ = probes(e, "nodes 30000 count 1 coord 0")
    check(rs[0]["granted_nodes"] == 30000, "coord=0 grants the full budget", str(rs[0]["granted_nodes"]))

    # Target depth: unreached depth is never exact; reached depth is.
    rs, _ = probes(e, "nodes 3000 depth 40")
    r = rs[0]
    check(r["status"] == "ok" and not r["exact"] and r["interrupted"] and not r["reached_depth"]
          and r["score"] is None, "incomplete depth flagged, score withheld",
          f"depth={r['depth']} final_bound={r['final_bound']}")
    rs, _ = probes(e, "nodes 5000000 depth 5")
    r = rs[0]
    check(r["exact"] and r["reached_depth"] and r["depth"] >= 5 and r["final_bound"] == "exact",
          "reached depth is exact", f"depth={r['depth']} score={r['score']}")

    # Time slicing: five probes capped at 100 ms inside a 1000 ms budget.
    t0 = time.monotonic()
    rs, done = probes(e, "movetime 1000 count 5 maxtime 100")
    wall = (time.monotonic() - t0) * 1000
    d = done_fields(done)
    oks = [r for r in rs if r["status"] == "ok"]
    check(len(oks) >= 4 and all(r["ms"] <= 130 for r in oks) and int(d["elapsed_ms"]) <= 1000,
          "time-sliced probes respect caps and deadline",
          f"ms={[r['ms'] for r in rs]} elapsed={d['elapsed_ms']} wall={wall:.0f}")
    # One probe without a cap must stop at the cumulative probe deadline (98%).
    rs, done = probes(e, "movetime 800 count 2")
    d = done_fields(done)
    check(rs[0]["status"] == "ok" and int(d["elapsed_ms"]) <= 800 and rs[1]["status"] == "no_budget",
          "uncapped probe stops at the shared deadline", f"elapsed={d['elapsed_ms']} ms={rs[0]['ms']}")

    # Cancellation: stop during a long probe returns promptly, rest cancelled.
    e.send("hbprobe movetime 20000 count 3")
    time.sleep(0.3)
    t0 = time.monotonic()
    e.send("stop")
    lines = e.read_until("hbprobe done", 10)
    took = time.monotonic() - t0
    rs = [json.loads(l.split(" ", 2)[2]) for l in lines if l.startswith("hbprobe ") and not l.startswith("hbprobe done")]
    check(took < 1.0 and rs[0]["interrupted"] and [r["status"] for r in rs[1:]] == ["cancelled", "cancelled"],
          "cancellation", f"took={took*1000:.0f}ms statuses={[r['status'] for r in rs]} first_depth={rs[0]['depth']}")

    # Invalid FEN is refused, not searched.
    rs, _ = probes(e, "nodes 1000 fen this is not a fen")
    check(rs[0]["status"] == "invalid_fen", "invalid FEN refused")

    # Actual state unchanged by all of the above.
    after = e.hbstate()
    check(before == after, "actual state untouched by child probes")

    # Main search isolation: child probes must not touch the main TT or
    # histories. Same clean main search with and without probes in between.
    e.setoption("Coordination", "false")
    def clean_main(with_probes: bool) -> tuple:
        e.send("ucinewgame")
        e.send(POS)
        if with_probes:
            probes(e, "nodes 200000 count 3 maxnodes 60000 clear 0")
        lines = e.go("go nodes 50000")
        info = [l for l in lines if l.startswith("info depth") and " pv " in l][-1]
        return parse_bestmove(lines), info.split(" nps ")[0], summary_fields(lines)["main_nodes"]
    a, b = clean_main(False), clean_main(True)
    check(a == b, "main search unaffected by child TT/heuristics", f"{a[0]} nodes={a[2]}")

    # Legal fallback and pass are always well formed; go on tiny limits.
    for cmd in ("go nodes 1", "go movetime 1", "go movetime 5", "go nodes 50"):
        for coord in ("true", "false"):
            e.setoption("Coordination", coord)
            e.send(POS)
            lines = e.go(cmd)
            a, b = parse_bestmove(lines)
            s = summary_fields(lines)
            legal = a in before["boards"][0]["legal"] and b == "pass"
            check(legal and s.get("decision") == a, f"{cmd} coord={coord} legal", f"{a} reason={s.get('reason')} "
                  f"nodes={s.get('total_nodes')} elapsed={s.get('elapsed_ms')}")

    # Budget split in real go: coordination on gives main <= 72% of nodes.
    for coord, share in (("true", 0.72), ("false", 1.0)):
        e.setoption("Coordination", coord)
        e.send(POS)
        lines = e.go("go nodes 200000")
        s = summary_fields(lines)
        mn = int(s["main_nodes"])
        check(mn <= share * 200000 + 1024 and mn >= share * 200000 * 0.9,
              f"go nodes 200000 coord={coord} main share", f"main_nodes={mn}")
        nodes_info = [l for l in lines if l.startswith("info depth") and "string" not in l][-1]
        check(f"nodes {s['total_nodes']} " in nodes_info, "final info line carries aggregate nodes", nodes_info)

    # Timed go at arena scale and small scale.
    times = [9652] if long_run else []
    times += [300, 50]
    for mt in times:
        for coord in ("true", "false"):
            e.setoption("Coordination", coord)
            e.send(POS)
            t0 = time.monotonic()
            lines = e.go(f"go movetime {mt}", timeout=mt / 1000 + 30)
            wall = (time.monotonic() - t0) * 1000
            s = summary_fields(lines)
            el = int(s["elapsed_ms"])
            limit = 0.72 * mt if coord == "true" else mt
            check(el <= mt + 15 and int(s["main_nodes"]) > 0, f"go movetime {mt} coord={coord}",
                  f"elapsed={el} wall={wall:.0f} main_depth={s['main_depth']} (main slice {limit:.0f} ms)")

    e.close()
    print("RESULT", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
