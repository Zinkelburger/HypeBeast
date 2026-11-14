"""Minimal Talk (HBTell=minimal): what a seat says, and what its partner makes of it.

The partner is given the turn by the game's own next move on its board (a capture
there changes a hand on the teller's board: the message must then be refused), and
is asked before the teller's move is on the board (0 plies since), after it (1),
after the reply the teller expected (2), and after another reply.

    python3 coord8.py bin/hypebeast-v8c
"""
import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/anbernal/Projects/HypeBeast-v5/tests")
import chess
from hbutil import ROOT, Bughouse, Engine, parse_bestmove, position_command
NEW = sys.argv[1]
res = [json.loads(l) for l in open(ROOT / "logs/late50-vs-np-b/results.jsonl")]
PARTNER = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
SEATS = ("Awhite", "Ablack", "Bwhite", "Bblack")


def key(s):
    kv = dict(p.split("=", 1) for p in s.split() if "=" in p)
    return tuple(kv.get(k) for k in ("decision", "main_score_cp", "coord_reason", "total_nodes", "main_depth"))


def game_at(r, cut, more=()):
    g = Bughouse(*r["opening"]["fens"]) if "fens" in r["opening"] else Bughouse()
    toks = list(r["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in r["result"]["events"] if e["kind"] == "move"]
    for t in toks[:cut]:
        g.push(int(t[0]) - 1, t[1:])
    for b, m in more:
        g.push(b, m)
    return g


def on_turn(g, seat):
    b = 0 if seat[0] == "A" else 1
    return g.turn(b) == (chess.WHITE if seat.endswith("white") else chess.BLACK)


def ask(binary, opts, g, seat):
    e = Engine(ROOT / binary, options={"Hash": 64, "HBFeedPrices": "false", "HBForecastTrustLate": 50, **opts})
    e.setoption("Seat", seat); e.setoption("Team", "white" if seat in ("Awhite", "Bblack") else "black")
    e.setoption("Clocks", "90000,88000,91000,87000"); e.send("ucinewgame"); e.sync()
    e.send(position_command(g))
    lines = e.go("go nodes 500000", timeout=900)
    e.close()
    summ = [l for l in lines if "hb_summary" in l]
    kv = dict(p.split("=", 1) for p in summ[-1].split() if "=" in p) if summ else {}
    fc = next((json.loads(l.split("hb_forecast ", 1)[1]) for l in lines if "hb_forecast " in l), None)
    return {"move": parse_bestmove(lines), "key": key(summ[-1]) if summ else None,
            "errs": [l for l in lines if "hb_error" in l],
            "tell": next((l.split("hb_tell ", 1)[1] for l in lines if "hb_tell " in l), None),
            "fc": fc, "main_nodes": kv.get("main_nodes"), "main_depth": kv.get("main_depth"), "reason": kv.get("coord_reason")}


def show_fc(fc):
    if not fc:
        return "no forecast"
    worlds = " ".join(f"{w['arrival']}={w['p']:.2f}" for w in fc["worlds"])
    lines = "; ".join(f"{l['source']} {l['weight']:.2f} {','.join(l['pv'][:4])} [{' '.join(l['captures'])}]" for l in fc["lines"][:4])
    return f"talk={fc.get('talk')} mover={fc['mover']} depth={fc['depth']} mate={fc['team_mate']} worlds: {worlds} | {lines}"


used = refused = 0
for gi, cut in ((3, 40), (11, 61), (35, 72), (22, 139), (16, 83)):
    g = game_at(res[gi], cut)
    toks = list(res[gi]["opening"]["moves"]) + [("1" if e["board"] == "A" else "2") + e["uci"] for e in res[gi]["result"]["events"] if e["kind"] == "move"]
    for teller in SEATS:
        if not on_turn(g, teller):
            continue
        c = ask(NEW, {"HBTell": "minimal"}, g, teller)
        text = c["tell"]
        print(gi, cut, teller, "plays", c["move"], "says:", text, flush=True)
        if not text or " lines " not in text:
            continue
        hearer = PARTNER[teller]
        tb, hb = (0, 1) if teller[0] == "A" else (1, 0)
        pre = ()
        if not on_turn(g, hearer):
            nxt = next((t[1:] for t in toks[cut:] if int(t[0]) - 1 == hb), None)
            if nxt is None:
                continue
            pre = ((hb, nxt),)
        first = text.split(" lines ", 1)[1].split()[0].split(":", 1)[1].split(",")
        cases = [("0 plies since", pre)]
        if g.is_legal(tb, first[0]):
            cases.append(("1 ply since", pre + ((tb, first[0]),)))
            g1 = game_at(res[gi], cut, pre + ((tb, first[0]),))
            if len(first) > 1 and g1.is_legal(tb, first[1]):
                cases.append(("2 plies since, the reply expected", pre + ((tb, first[0]), (tb, first[1]))))
            other = next((m for m in sorted(g1.legal_moves(tb)) if len(first) < 2 or m != first[1]), None)
            if other:
                cases.append((f"2 plies since, another reply ({other})", pre + ((tb, first[0]), (tb, other))))
        for name, more in cases:
            gh = game_at(res[gi], cut, more)
            if not on_turn(gh, hearer):
                print(f"    {hearer} hears {teller}, {name}: not on turn", flush=True)
                continue
            own = ask(NEW, {"HBTell": "minimal"}, gh, hearer)
            h = ask(NEW, {"HBTell": "minimal", "HBPartnerTell": text}, gh, hearer)
            t = (h["fc"] or {}).get("talk")
            used += t == "told"; refused += t != "told"
            print(f"    {hearer} hears {teller}, {name}" + (f", after {pre[0][1]} on its own board" if pre else "") + ":", flush=True)
            print(f"        told: {show_fc(h['fc'])}", flush=True)
            print(f"        own:  {show_fc(own['fc'])}", flush=True)
            print(f"        move {h['move']} reason {h['reason']} main_nodes {h['main_nodes']} depth {h['main_depth']} | own: move {own['move']} reason {own['reason']} main_nodes {own['main_nodes']} depth {own['main_depth']} | errs {h['errs']}", flush=True)
print("message used:", used, "refused:", refused)
