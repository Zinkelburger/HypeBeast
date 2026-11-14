"""A queen trade that wins or loses by whose move it is on the other board.

Board A (the user's position, 2026-11-11): either side mates at once with a
queen in hand (Q@f7 for White, Q@f2 for Black) and with nothing else. Board B:
the queens face each other on an open file, each defended, so either side can
trade them and each capture sends a queen to board A.

The team whose player is on move on board A wants the trade now: that player
drops the queen and mates before the recapture matters. The other team must
not trade and must not leave its queen to be taken.

    python3 tests/tempo_trade_check.py [BINARY] [NODES]

Reports what each seat on move does, without partner talk and with the full
table heard from a partner who is also on move. It reports; it does not fail
the run: no build is expected to pass all of it yet. Never run it beside a match.
"""
import json
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import chess
import chess.variant
from hbutil import ROOT, Bughouse, Engine, parse_bestmove, summary_fields

BINARY = sys.argv[1] if len(sys.argv) > 1 else "bin/hypebeast-v8b"
NODES = int(sys.argv[2]) if len(sys.argv) > 2 else 500000
A = "rnbqkbnr/ppp3pp/8/4N3/4n3/8/PPP3PP/RNBQKBNR[] {} KQkq - 0 1"
B = "r2q1rk1/ppp2ppp/2n2n2/8/8/2N2N2/PPP2PPP/R2Q1RK1[] {} - - 0 1"
PARTNER = {"Awhite": "Bblack", "Bblack": "Awhite", "Ablack": "Bwhite", "Bwhite": "Ablack"}
# aW, aB, bW, bB in ms: first the Awhite+Bblack team ahead, then the other team
CLOCKS = {"white team ahead": "90000,60000,60000,90000", "black team ahead": "60000,90000,90000,60000"}
BASE = {"Hash": 64, "HBFeedPrices": "false", "HBForecastTrustLate": 50}


def ask(seat, game, clocks, opts):
    e = Engine(ROOT / BINARY, options={**BASE, **opts})
    e.setoption("Seat", seat)
    e.setoption("Team", "white" if seat in ("Awhite", "Bblack") else "black")
    e.setoption("Clocks", clocks)
    e.send("ucinewgame")
    e.sync()
    e.send(f"position fen {game.dual_fen()}")
    lines = e.go(f"go nodes {NODES}", timeout=600)
    e.close()
    s = summary_fields(lines)
    move = next((m for m in parse_bestmove(lines) if m != "pass"), "pass")
    return {"move": move, "reason": s.get("coord_reason"), "score": s.get("main_score_cp"),
            "tell": next((l.split("hb_tell ", 1)[1] for l in lines if "hb_tell " in l), None),
            "heard": s.get("heard"), "errs": [l for l in lines if "hb_error" in l]}


def takes_queen(board, uci):
    m = chess.Move.from_uci(uci)
    return board.is_capture(m) and board.piece_type_at(m.to_square) == chess.QUEEN


def queen_can_be_taken_after(board, uci):
    b = board.copy()
    b.push(chess.Move.from_uci(uci))
    return any(b.is_capture(m) and b.piece_type_at(m.to_square) == chess.QUEEN for m in b.legal_moves)


def mated_by_a_queen_after(board, uci):
    """After this move the opponent, given a queen, mates in one."""
    b = board.copy()
    b.push(chess.Move.from_uci(uci))
    b.pockets[b.turn].add(chess.QUEEN)
    for m in list(b.legal_moves):
        b.push(m)
        mate = b.is_checkmate()
        b.pop()
        if mate:
            return True
    return False


def judge(seat, partner_on_move, board, move):
    """What the seat should do, and whether it did."""
    if seat[0] == "B":
        if partner_on_move:
            return "take the queen now", move != "pass" and takes_queen(board, move)
        ok = move == "pass" or (not takes_queen(board, move) and not queen_can_be_taken_after(board, move))
        return "no trade, queen not left to be taken", ok
    if partner_on_move:
        return "wait for the queen", move == "pass"
    return "wait, or a move a queen does not punish", move == "pass" or not mated_by_a_queen_after(board, move)


rows = []
for ta in "wb":
    for tb in "wb":
        game = Bughouse(A.format(ta), B.format(tb))
        on_move = ["A" + ("white" if ta == "w" else "black"), "B" + ("white" if tb == "w" else "black")]
        for label, clocks in CLOCKS.items():
            quiet = {s: ask(s, game, clocks, {}) for s in on_move}
            said = {s: ask(s, game, clocks, {"HBTell": "table"}) for s in on_move}
            for seat in on_move:
                partner = PARTNER[seat]
                board = game.boards[0 if seat[0] == "A" else 1]
                text = said[partner]["tell"] if partner in on_move else None
                heard = ask(seat, game, clocks, {"HBTell": "table", "HBPartnerTell": text}) if text else None
                for name, r in (("no talk", quiet[seat]), ("table, partner heard", heard)):
                    if r is None:
                        continue
                    want, ok = judge(seat, partner in on_move, board, r["move"])
                    rows.append({"A_to_move": ta, "B_to_move": tb, "clocks": label, "seat": seat, "setting": name,
                                 "want": want, "ok": ok, **r, "partner_said": text if name != "no talk" else None})
                    print(f"A:{ta} B:{tb} | {label:16} | {seat:6} | {name:20} | {r['move']:6} {str(r['reason']):14} "
                          f"score {r['score']} | want: {want} | {'OK' if ok else 'WRONG'}"
                          + (f" | heard {r['heard']}" if name != "no talk" else "") + (f" | errs {r['errs']}" if r["errs"] else ""),
                          flush=True)
            for s in on_move:
                if said[s]["tell"]:
                    print(f"      {s} says: {said[s]['tell']}", flush=True)

for name in ("no talk", "table, partner heard"):
    part = [r for r in rows if r["setting"] == name]
    print(f"{name}: {sum(r['ok'] for r in part)} of {len(part)} right")
out = ROOT / "logs/loss-analysis/tempo"
out.mkdir(parents=True, exist_ok=True)
(out / "tempo_trade.json").write_text(json.dumps({"binary": BINARY, "nodes": NODES, "rows": rows}, indent=1))
