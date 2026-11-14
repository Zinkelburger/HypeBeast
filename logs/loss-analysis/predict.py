"""How well does a forecast predict the next move on the partner board?
Own search (top line, any line) against the partner's told line, by how old the message is."""
import glob, json, collections, sys
d = sys.argv[1]
stats = collections.defaultdict(lambda: collections.Counter())
for path in sorted(glob.glob(f"{d}/engine_logs/w*-*.log")):
    role = "contender" if "-contender-" in path else "baseline"
    seat = heard = None
    blocks = []   # (moves, fc, heard) per go of the current game
    def flush():
        for i, (moves, fc, hd) in enumerate(blocks):
            if not fc or not fc.get("ready") or not fc.get("lines"):
                continue
            pb = "2" if seat[0] == "A" else "1"
            later = blocks[-1][0]
            nxt = next((t[1:] for t in later[len(moves):] if t[0] == pb), None)
            if nxt is None:
                continue
            talk = fc.get("talk") or "none"
            skip = None
            if hd and " at=" in hd:
                at = int(hd.split(" at=")[1].split()[0])
                skip = sum(t[0] == pb for t in moves) - at
            if role == "baseline":
                k = ("baseline own", fc["mover"])
            elif talk == "told":
                k = (f"told, {skip} plies old", fc["mover"])
            else:
                k = (f"minimal {talk}", fc["mover"])
            c = stats[k]
            c["n"] += 1
            best = max(fc["lines"], key=lambda l: l["weight"])
            c["top"] += best["move"] == nxt
            c["first"] += fc["lines"][0]["move"] == nxt
            c["any"] += any(l["move"] == nxt for l in fc["lines"])
            c["w"] += sum(l["weight"] for l in fc["lines"] if l["move"] == nxt)
    cur = None
    for line in open(path, errors="replace"):
        if line.startswith(">>> setoption name Seat value "):
            seat = line.split()[-1]
        elif line.startswith(">>> ucinewgame"):
            flush(); blocks = []; heard = None
        elif line.startswith(">>> setoption name HBPartnerTell value "):
            heard = line.rstrip("\n").split(" value ", 1)[1]
        elif line.startswith(">>> position startpos"):
            cur = [line.split()[4:] if " moves " in line else [], None, heard]
            blocks.append(cur)
        elif line.startswith("info string hb_forecast ") and cur is not None:
            cur[1] = json.loads(line.split("hb_forecast ", 1)[1])
    flush()
print("forecast | on turn there | decisions | first line's move was played | heaviest line's | some line's | weight on the move played")
for k in sorted(stats):
    c = stats[k]; n = c["n"]
    print(f"{k[0]} | {k[1]} | {n} | {100*c['first']/n:.0f}% | {100*c['top']/n:.0f}% | {100*c['any']/n:.0f}% | {c['w']/n:.2f}")
