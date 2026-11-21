#!/usr/bin/env python3
"""Fact sheets for the picked games: the contract's game file with every
builder field filled, plus a `facts` object on each move (stripped by
merge.py) and, on the key moves, engine lines.

    python3 scripts/collection/build_game.py [ID ...]     (default: the picks in selection.json)

Writes logs/collection/facts/<id>.json. Engine searches are single-process,
fixed-node, nice 19, one at a time, cached in logs/collection/cache/ (a rerun
costs nothing). See README.md in this directory for every field.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("hb_collection_common", HERE / "common.py")
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)

import json  # noqa: E402
import re  # noqa: E402

import chess  # noqa: E402

FALL_CP = 500          # a fall of the mover's score by its next decision that counts as sharp
MAX_KEY, MIN_KEY = 15, 8
MAX_LINE = 8
ARRIVES_P = 0.5
NO_LINES = "--no-lines" in sys.argv
# v1.1.0's own sessions are replayed (self-check only: its facts use no replay
# output) in these games; elsewhere its moves say "not replayed".
V110_REPLAY_SAMPLE = {"v111-v110-g10", "v111pre-v110-g28"}


# ----------------------------------------------------------------- helpers

def white_view(score: dict | None, mover_white: bool) -> tuple[int | None, int | None]:
    """A UCI score from the side to move -> (cp, mate) from that board's White."""
    if not score:
        return None, None
    s = 1 if mover_white else -1
    if "mate" in score:
        return None, s * score["mate"]
    if "cp" in score:
        return s * score["cp"], None
    return None, None


def negate(score: dict | None) -> dict | None:
    if not score:
        return None
    return {k: -v for k, v in score.items() if k in ("cp", "mate")}


def clipped(score: dict | None):
    if not score:
        return None
    if "mate" in score:
        return 2000 if score["mate"] > 0 else -2000
    return max(-2000, min(2000, score["cp"])) if "cp" in score else None


def final_score(out: dict) -> dict | None:
    f = out.get("final") or {}
    for k in ("cp", "mate"):
        if k in f:
            return {k: f[k]}
    return None


def arrival_letters(key: str, mover_white: bool) -> tuple[str, str]:
    """'+N-Q' -> (pieces for the mover, pieces for the opponent) as FEN letters on this board."""
    mine = "".join(t for s, t in re.findall(r"([+-])([PNBRQ])", key) if s == "+")
    theirs = "".join(t for s, t in re.findall(r"([+-])([PNBRQ])", key) if s == "-")
    up = (lambda x: x.upper()) if mover_white else (lambda x: x.lower())
    down = (lambda x: x.lower()) if mover_white else (lambda x: x.upper())
    return up(mine), down(theirs)


def san_list(fen_this, fen_other, b, ucis):
    return [s for _, s, _ in c.walk_line(fen_this, fen_other, b, ucis, max_moves=len(ucis))]


def captured_letter(pos: chess.variant.CrazyhouseBoard, mv: chess.Move) -> str | None:
    if mv.drop:
        return None
    if pos.is_en_passant(mv):
        return "P"
    pt = pos.piece_type_at(mv.to_square)
    if pt is None:
        return None
    if pos.promoted & chess.BB_SQUARES[mv.to_square]:
        return "P"
    return chess.piece_symbol(pt).upper()


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def sit_detail(s: dict) -> dict | None:
    """The hb_summary fields of a sit, named (hb_coordinator.cpp hold_mated / hold /
    resolve_tier / consider_voluntary_wait). Clocks in ms; 'diagonal' is the seat of
    the mover's colour on the other board, whose clock races the mover's while both sit."""
    r = s.get("reason")
    if s.get("wait") in ("hold_continue", "stall_continue", "continue"):
        return {"continued_without_search": s.get("wait")}
    if r == "hold_mated" and "mated_plies" in s:
        return {"mated_in_plies": _int(s.get("mated_plies")),
                "partner_board_cp_for_partner": _int((s.get("hold") or "=").split("=", 1)[1]),
                "clock_ms": _int(s.get("clock")), "diagonal_clock_ms": _int(s.get("diagonal")),
                "lead_ms": _int(s.get("lead")), "partner_mate_in_moves": _int(s.get("partner_mate")) or None,
                "lead_needed_ms": 0 if s.get("race") == "free" else _int(s.get("need")),
                "partner_on_turn": s.get("partner_on_turn") == "1"}
    if r == "hold_partner_mate" and (s.get("hold") or "").startswith("partner_mate="):
        return {"partner_mate_in_moves": _int(s["hold"].split("=", 1)[1]),
                "clock_ms": _int(s.get("clock")), "diagonal_clock_ms": _int(s.get("diagonal")),
                "lead_ms": _int(s.get("lead")), "lead_needed_ms": _int(s.get("need")),
                "partner_on_turn": s.get("partner_on_turn") == "1"}
    if r == "stall_deny" and s.get("veto") and ">" in s["veto"]:
        cap, drop = s["veto"].split(">", 1)
        return {"exposed_to": {"opponent_capture_uci": cap, "then_drop_board": drop[:1], "then_drop_uci": drop[1:]}}
    if r == "voluntary_wait":
        return {"wait": s.get("wait")}
    return None


# ------------------------------------------------------------ the builder

class GameBuilder:
    def __init__(self, sel_entry: dict, m: dict):
        self.x = sel_entry
        self.m = m
        self.match = sel_entry["match"]
        self.g = sel_entry["game"]
        self.rec = m["records"][self.g]
        self.decs = m["decisions"][self.g]
        self.toks = c.game_tokens(self.rec)
        self.states = c.replay_states(self.rec)
        self.n_book = len(self.rec["opening"]["moves"])
        self.names = {c.SEAT_OF_ARENA[k]: c.MATCHES[self.match]["names"][
            "contender" if v == self.rec["contender"] else "baseline"] for k, v in self.rec["seats"].items()}
        self.role = {c.SEAT_OF_ARENA[k]: ("contender" if v == self.rec["contender"] else "baseline")
                     for k, v in self.rec["seats"].items()}
        man = json.loads((c.LOGS / self.match / "manifest.json").read_text())
        self.nodes = {r: man["sides"][r]["nodes"] for r in ("contender", "baseline")}
        self.date = man["sessions"][0]["started"][:10]
        skip = set() if sel_entry["id"] in V110_REPLAY_SAMPLE else {c.BIN_V110}
        self.replay = c.replay_sessions(m, self.g, skip_binaries=skip)
        self.searches = 0
        self.engine_seconds = 0.0
        self.move_dec = {}            # move index -> deciding decision
        self.sits_before = {}         # move index -> [sit decisions]
        for d in self.decs:
            if d["event"]["kind"] == "move":
                self.move_dec[d["n"]] = d
        for i, d in self.move_dec.items():
            b = self.states[i]["board"]
            prev = max([j for j in range(self.n_book, i) if self.states[j]["board"] == b], default=-1)
            t0 = self.event_t(prev) if prev >= self.n_book else -1
            self.sits_before[i] = [s for s in self.decs if s["seat"] == d["seat"] and s["event"]["kind"] == "sit"
                                   and t0 <= s["event"]["t"] <= d["event"]["t"] and s["n"] <= i]
        self.next_dec_of_seat = {}
        for seat in c.SEATS:
            sd = [d for d in self.decs if d["seat"] == seat]
            for a, b in zip(sd, sd[1:]):
                self.next_dec_of_seat[id(a)] = b

    def event_t(self, i: int):
        d = self.move_dec.get(i)
        return d["event"]["t"] if d else None

    def binary(self, seat):
        return c.MATCHES[self.match]["binaries"][self.role[seat]]

    def replayed(self, d):
        rs = self.replay.get(d["seat"])
        return rs["gos"][d["k"]] if rs and d["k"] < len(rs["gos"]) else None

    def reproduced(self, d):
        r = self.replayed(d)
        return bool(r) and c.same_decision(d["out"], r)

    def run(self, search: c.Search) -> dict:
        r = search.run()
        self.searches += 1
        self.engine_seconds += r["seconds"] if not r.get("_cached") else 0
        return r

    # ---------------------------------------------------------- searches

    def search_spec(self, seat, position, nodes, coordination=True, clocks=None, extra=None):
        clocks = clocks or [120000] * 4
        setup = c.arena_setup(seat, coordination, extra, c.adv_for(clocks, seat), c.clocks_str(clocks))
        return c.Search(self.binary_for_search, setup, position, f"go nodes {nodes}")

    def describe(self, s: c.Search, result: dict, purpose: str) -> dict:
        return {"purpose": purpose, "source": "fresh-process search", "binary": result["binary"],
                "binary_sha256": result["binary_sha256"], "commands": result["script"][1:],
                "engine_seconds": result["seconds"]}

    def reply_line(self, d, first_uci: str, start_fen: str, purpose: str, world_fen: str | None = None):
        """first move, then the mover's engine searching for the opponent seat
        (full coordination, the game's node budget, a fresh process)."""
        seat = d["seat"]
        b = 0 if seat[0] == "A" else 1
        nodes = self.nodes[self.role[seat]]
        self.binary_for_search = self.binary(seat)
        if world_fen is None:
            position = c.position_cmd(self.rec, self.toks[:d["n"]] + [f"{b + 1}{first_uci}"])
        else:
            game = c.game_at(self.rec, d["n"])
            fa, fb = (world_fen, c.board_fen(game, 1)) if b == 0 else (c.board_fen(game, 0), world_fen)
            position = f"position fen {fa}|{fb} moves {b + 1}{first_uci}"
        clocks = d["event"]["clocks"]
        s = self.search_spec(c.opponent_seat(seat), position, nodes, True, clocks)
        r = self.run(s)
        out = c.parse_output(r["lines"])
        pv = out["main_pv"]["moves"] if out["main_pv"] else []
        opp = final_score(out)
        return {"moves": [first_uci] + pv, "score_mover": negate(opp), "out": out,
                "facts": self.describe(s, r, purpose), "start": start_fen}

    def own_search(self, d, nodes, coordination=True, extra=None, purpose=""):
        seat = d["seat"]
        self.binary_for_search = self.binary(seat)
        position = c.position_cmd(self.rec, self.toks[:d["n"]])
        s = self.search_spec(seat, position, nodes, coordination, d["event"]["clocks"], extra)
        r = self.run(s)
        out = c.parse_output(r["lines"])
        return out, self.describe(s, r, purpose)

    # ------------------------------------------------------------- facts

    def plain_world(self, w: dict, mover_white: bool, values: dict | None, before_fen: str, other: str, b: int):
        mine, theirs = arrival_letters(w["arrival"], mover_white)
        out = {"arrival": w["arrival"], "pieces_for_mover": mine.upper(), "pieces_for_opponent": theirs.upper(),
               "probability": round(w["p"], 3)}
        if values:
            out["candidate_scores_cp_mover"] = {self.san_at(before_fen, other, b, u): v for u, v in values.items()}
        return out

    def exposure_sans(self, i, own, cap, drop) -> dict:
        """SAN of the capture after own_best and of the mating drop after it (referee replay)."""
        try:
            b = self.states[i]["board"]
            game = c.game_at(self.rec, i)
            game.push(b, own)
            pos = game.boards[b]
            cap_san = c.san_of(pos, chess.Move.from_uci(cap))
            game.push(b, cap)
            db = "AB".index(drop[0])
            dpos = game.boards[db]
            mv = chess.Move.from_uci(drop[1:])
            drop_san = c.san_of(dpos, mv) if mv in dpos.legal_moves else None
            return {"opponent_capture_san": cap_san, "then_drop_san": drop_san}
        except ValueError:    # the referee's IllegalMove and python-chess's errors are ValueErrors
            return {}

    def san_at(self, fen_this, fen_other, b, uci):
        got = c.walk_line(fen_this, fen_other, b, [uci], 1)
        return got[0][1] if got else uci

    def arrivals_after(self, i: int, seat: str) -> list[dict]:
        """Pieces that reached either hand on the mover's board after move i,
        until the mover's next move on that board."""
        b = 0 if seat[0] == "A" else 1
        mover_white = seat.endswith("white")
        out = []
        q = 1
        game = c.game_at(self.rec, i + 1)
        for j in range(i + 1, len(self.toks)):
            bj = int(self.toks[j][0]) - 1
            if bj == b:
                q += 1
                if q > 2:
                    break
                game.push(bj, self.toks[j][1:])
                continue
            pos = game.boards[bj]
            mv = chess.Move.from_uci(self.toks[j][1:])
            cap = captured_letter(pos, mv)
            capturer_white = pos.turn == chess.WHITE
            game.push(bj, self.toks[j][1:])
            if cap:
                # the capturer's partner plays the other colour on our board
                to_white = not capturer_white
                out.append({"piece": cap, "hand": "mover" if to_white == mover_white else "opponent",
                            "by": self.states[j]["san"], "board": "AB"[bj], "i": j,
                            "when": "before the opponent's reply" if q == 1 else "before the mover's next move"})
        return out

    def move_facts(self, i: int) -> dict | None:
        d = self.move_dec.get(i)
        if d is None:
            return None
        st = self.states[i]
        seat = d["seat"]
        b = st["board"]
        mover_white = st["white"]
        out = d["out"]
        s = out["summary"]
        pm = d["pm"] or {}
        before, other = st["before"][b], st["before"][1 - b]
        score = final_score(out)
        wcp, wmate = white_view(score, mover_white)
        f = {"engine": self.names[seat], "nodes": self.nodes[self.role[seat]],
             "score_view_note": "score_mover_* is from the side that moved; score_white_* from this board's White",
             "score_mover_cp": score.get("cp") if score else None,
             "score_mover_mate": score.get("mate") if score else None,
             "score_white_cp": wcp, "score_white_mate": wmate,
             "depth": int(s["main_depth"]) if s.get("main_depth", "").isdigit() else None,
             "reason": s.get("reason"), "reason_meaning": c.REASONS.get(s.get("reason"))}
        mpv = out.get("main_pv")
        own = mpv["moves"][0] if mpv else None
        if own and own != st["uci"]:
            f["own_best_uci"] = own
            f["own_best_san"] = self.san_at(before, other, b, own)
            f["score_is_for"] = "the board's own search move (own_best), not the move played"
            if s.get("override") != "1" and s.get("extension_used") == "1":
                f["own_best_note"] = "the main search's move; a deeper search with the leftover budget chose the move played"
        else:
            f["score_is_for"] = "the move played (the board's own search move)"
        f["override"] = s.get("override") == "1"
        if s.get("veto") and ">" in s["veto"] and s.get("reason") in ("exposure_veto", "soft_switch"):
            cap, drop = s["veto"].split(">", 1)
            f["own_best_exposed_to"] = {"opponent_capture_uci": cap, "then_drop_board": drop[:1],
                                        "then_drop_uci": drop[1:],
                                        **self.exposure_sans(i, own, cap, drop),
                                        "meaning": ("after own_best the opponent can capture with this move and its "
                                                    "partner drop the piece for mate on that board, at once or after "
                                                    "any reply of the mover's partner (in check there)")
                                        if s.get("reason") == "exposure_veto" else
                                        ("after own_best the opponent can capture with this move and its partner "
                                         "drop the piece for mate on that board unless the mover's partner moves "
                                         "first (or a short probe scored that arrival as mate)")}
        # forecast and the worlds
        fc = out.get("forecast")
        coord = out.get("coord") or {}
        if fc and fc.get("ready"):
            vals = {w["arrival"]: w.get("values") for w in coord.get("worlds", [])}
            worlds = [self.plain_world(w, mover_white, vals.get(w["arrival"]) if f["override"] or i in self.key_set else None,
                                       before, other, b) for w in fc["worlds"]]
            f["forecast"] = {"partner_board_on_turn": "the mover's partner" if fc.get("mover") == "partner" else "the opponent's partner",
                             "worlds": worlds}
            if f["override"] or i in self.key_set:
                cands = []
                for cnd in coord.get("candidates", []):
                    cands.append({"san": self.san_at(before, other, b, cnd["move"]), "source": cnd["source"],
                                  "weighted_win_chance": round(cnd["E"], 3) if cnd.get("E") else None})
                if cands:
                    f["candidates"] = cands
        f["arrived"] = self.arrivals_after(i, seat)
        # prices, feed
        prices = out.get("prices")
        rep = self.replayed(d) if self.reproduced(d) else None
        fed, fed_src = None, None
        if rep and rep.get("main_pv") and rep["main_pv"].get("fed") is not None:
            fed, fed_src = rep["main_pv"]["fed"], "engine (hb_fed of the replayed decision)"
        elif pm.get("_fed_estimate") is not None and prices:
            fed, fed_src = pm["_fed_estimate"], "estimate (hb_prices summed over the main line's captures)"
        capture = captured_letter(chess.variant.CrazyhouseBoard(before), chess.Move.from_uci(st["uci"])) is not None
        if prices and (capture or (fed or 0) != 0):
            f["prices"] = {"mover_captures_cp": prices.get("ours"), "opponent_captures_cp": prices.get("theirs"),
                           "partner_lost": bool(prices.get("partner_lost"))}
            # hb_prices prints base 0 when the partner probe did not finish; the
            # replay's hb_values says which (its base is null then).
            if rep and rep.get("values") and rep["values"].get("base") is not None:
                f["prices"]["partner_board_score_cp_partner"] = prices.get("base")
            if rep and rep.get("values"):
                v = rep["values"]
                pw = v.get("white" if not mover_white else "black")   # the partner plays the other colour
                ow = v.get("black" if not mover_white else "white")
                f["piece_values_partner_board"] = {"one_more_for_partner_cp": pw, "one_more_for_opponents_partner_cp": ow,
                                                   "probe_depth": v.get("depth")}
        if fed is not None and score and "cp" in score:
            f["fed_cp_mover"] = fed
            f["own_board_cp_mover"] = score["cp"] - fed
            f["fed_source"] = fed_src
        # sits before the move
        sits = self.sits_before.get(i) or []
        if sits:
            f["sat_before"] = [{"t": round(x["event"]["t"] / 1000, 1), "reason": x["out"]["summary"].get("reason"),
                                "meaning": c.REASONS.get(x["out"]["summary"].get("reason")),
                                "detail": sit_detail(x["out"]["summary"]),
                                "searched": bool(x["out"]["summary"].get("main_depth"))} for x in sits]
        f["replay"] = ("reproduced" if self.reproduced(d) else "differs" if self.replayed(d) else "not replayed")
        return f

    def sitting_at_end(self) -> list[dict]:
        """Seats whose last decision was a sit: they were sitting when the game
        ended, so no move of theirs carries the sit (the contract's `waited`
        sits on the move that follows a sit)."""
        out = []
        for seat in c.SEATS:
            sd = [d for d in self.decs if d["seat"] == seat]
            if not sd or sd[-1]["event"]["kind"] != "sit":
                continue
            run = []
            for d in reversed(sd):
                if d["event"]["kind"] != "sit":
                    break
                run.append(d)
            run.reverse()
            sm = run[0]["out"]["summary"]
            out.append({"seat": seat, "engine": self.names[seat], "since_t": round(run[0]["event"]["t"] / 1000, 1),
                        "sits": len(run), "reason": sm.get("reason"), "meaning": c.REASONS.get(sm.get("reason")),
                        "detail": sit_detail(sm)})
        return out

    # ---------------------------------------------------------- key moves

    def key_moves(self) -> dict[int, list[str]]:
        sig = self.x["details"]
        keys: dict[int, list[str]] = {}
        order: list[int] = []

        def add(i, why, cap=None, bucket=None):
            if i is None or i < self.n_book or i not in self.move_dec:
                return False
            if i not in keys:
                if len(order) >= MAX_KEY:
                    return False
                keys[i] = []
                order.append(i)
            if why not in keys[i]:
                keys[i].append(why)
            return True

        # final mating sequence: the mating seat's last three moves on that board
        if self.rec["result"]["termination"] == "checkmate":
            last = max(self.move_dec)
            seat = self.move_dec[last]["seat"]
            mine = sorted(i for i, d in self.move_dec.items() if d["seat"] == seat)[-3:]
            for i in mine:
                add(i, "final mating sequence")
        # sits (at most two)
        for i, sits in sorted(self.sits_before.items()):
            if sits and sum(any(w.startswith("sat") for w in v) for v in keys.values()) < 2:
                add(i, "sat before moving (" + ", ".join(sorted({x["out"]["summary"].get("reason", "?") for x in sits})) + ")")
        # forecast arrivals used at once (at most two, likeliest first)
        for e in sorted(sig.get("forecast_used", []), key=lambda e: -e["p"])[:2]:
            add(e["n"], f"dropped a forecast arrival: a {c.PIECE_NAMES[e['piece']]} the forecast at move i={e['forecast_n']} "
                        f"gave probability {e['p']} reached the hand before this move")
        # sharp falls, largest first (at most two)
        falls = []
        for d in self.decs:
            nx = self.next_dec_of_seat.get(id(d))
            if d["event"]["kind"] != "move" or nx is None:
                continue
            a0, z = clipped(final_score(d["out"])), clipped(final_score(nx["out"]))
            if a0 is not None and z is not None and z - a0 <= -FALL_CP:
                falls.append((z - a0, d["n"]))
        self.falls = {n: dl for dl, n in falls}
        for dl, n in sorted(falls)[:2]:
            add(n, f"the mover's score fell by {-dl} cp by its next decision")
        # overrides: the rarer reasons first, then the largest world switches (at most three)
        ovs = []
        for i, d in self.move_dec.items():
            s = d["out"]["summary"]
            if s.get("override") == "1":
                cands = (d["out"].get("coord") or {}).get("candidates", [])
                es = {x["move"]: x.get("E") for x in cands}
                main = cands[0]["move"] if cands else None
                gain = (es.get(d["event"]["uci"]) or 0) - (es.get(main) or 0)
                ovs.append((s.get("reason") == "world_switch", -gain, i, s.get("reason")))
        ovs.sort()
        for _, _, i, why in ovs[:3]:
            add(i, f"coordination changed the move ({why})")
        # feed-heavy lines, largest first (at most two)
        fed = sorted(sig.get("fed_heavy", []), key=lambda e: -abs(e["fed"]))
        for e in fed[:2]:
            add(e["n"], f"main line scored largely by feed ({e['fed']:+d} of {e['score']:+d} cp)")
        # spread: at least three key moves before the last 30% of the game
        cut = self.n_book + int(0.7 * (len(self.states) - self.n_book))
        early = [(why, i) for _, _, i, why in ovs[3:]] + [(None, e["n"]) for e in fed[2:]] + \
                [("fall", n) for dl, n in sorted(falls)[2:]]
        for why, i in early:
            if sum(k < cut for k in keys) >= 3 or len(order) >= MAX_KEY:
                break
            if i >= cut:
                continue
            if why == "fall":
                add(i, f"the mover's score fell by {-self.falls[i]} cp by its next decision")
            elif why is None:
                e = next(e for e in fed if e["n"] == i)
                add(i, f"main line scored largely by feed ({e['fed']:+d} of {e['score']:+d} cp)")
            else:
                add(i, f"coordination changed the move ({why})")
        # fill to the minimum with more overrides and falls
        for _, _, i, why in ovs[3:]:
            if len(order) >= MIN_KEY:
                break
            add(i, f"coordination changed the move ({why})")
        for dl, n in sorted(falls)[2:]:
            if len(order) >= MIN_KEY:
                break
            add(n, f"the mover's score fell by {-dl} cp by its next decision")
        return keys

    # -------------------------------------------------------------- lines

    def make_line(self, i, kind, frm, start, ucis, score_mover, mover_white, assume, facts, suffix, shift=None):
        """shift: how the search's mate count relates to the line's start.
        "own_after": the mover's own score from before its move, line starts after it;
        "reply": the opponent's score after the line's first move (the mover's)."""
        st = self.states[i]
        b = st["board"]
        other = st["before"][1 - b] if frm == "before" else st["after"][1 - b]
        walked = c.walk_line(start, other, b, ucis, MAX_LINE)
        if len(walked) < 2:
            self.dropped.append({"i": i, "kind": kind, "why": f"fewer than two legal moves ({len(walked)} of {len(ucis)})",
                                 "first": ucis[:3], "search": facts})
            return None
        # the score's side: the line's first mover is the decision's mover for
        # `instead` and `arrives` lines, the opponent for `played` / `threat`
        engine_score = score_mover
        if score_mover and "mate" in score_mover and shift:
            m = score_mover["mate"]
            if shift == "own_after" and m > 0:
                m -= 1
            elif shift == "reply" and m > 0:
                m += 1
            score_mover = {"mate": m}
        cp, mate = white_view(score_mover, mover_white)
        facts = dict(facts)
        if engine_score != score_mover:
            facts["engine_mate_count"] = engine_score["mate"]
        facts["truncated_from"] = len(ucis) if len(walked) < len(ucis) else None
        facts["score_mover_cp"] = score_mover.get("cp") if score_mover else None
        facts["score_mover_mate"] = score_mover.get("mate") if score_mover else None
        return {"id": f"m{i}-{suffix}", "kind": kind, "from": frm, "board": "AB"[b], "start": start,
                "assume": assume, "moves": [{"uci": u, "san": s, "fen": fen} for u, s, fen in walked],
                "eval": cp, "mate": mate, "note": None, "facts": facts}

    def lines_for(self, i: int) -> list[dict]:
        d = self.move_dec[i]
        st = self.states[i]
        b = st["board"]
        seat = d["seat"]
        mover_white = st["white"]
        before, after = st["before"][b], st["after"][b]
        out = d["out"]
        mpv = out.get("main_pv")
        score = final_score(out)
        nodes = self.nodes[self.role[seat]]
        played = st["uci"]
        lines = []
        letters = iter("abcdefghijklmnop")
        log_src = {"purpose": "the decision's own main line", "source": "game transcript",
                   "binary": str(self.binary(seat).relative_to(c.ROOT)),
                   "match_log": f"logs/{self.match}/engine_logs/{d['file']}",
                   "commands": [d["position"], d["go"]],
                   "options": {k: v for k, v in d["options"].items() if k != "EvalFile"}}
        # played: the main line after the move
        if mpv and mpv["moves"][0] == played and len(mpv["moves"]) >= 3:
            ln = self.make_line(i, "played", "after", after, mpv["moves"][1:], score, mover_white, "",
                                dict(log_src), next(letters), shift="own_after")
            if ln:
                lines.append(ln)
        else:
            r = self.reply_line(d, played, after, "the opponent's answer to the move played")
            ln = self.make_line(i, "played", "after", after, r["moves"][1:], r["score_mover"], mover_white, "",
                                r["facts"], next(letters))
            if ln:
                lines.append(ln)
        listed = {played}
        same_method = None

        def played_same_method():
            nonlocal same_method
            if same_method is None:
                r = self.reply_line(d, played, after, "the move played, searched the same way as the alternatives")
                same_method = {"score_mover": r["score_mover"], "search": r["facts"],
                               "line": san_list(before, st["before"][1 - b], b, r["moves"][:MAX_LINE])}
            return same_method

        # instead 1: the board's own move when coordination replaced it
        if mpv and mpv["moves"][0] != played:
            fx = dict(log_src)
            fx["why_listed"] = "the board's own search move, replaced by coordination" if out["summary"].get("override") == "1" \
                else "the main search's move, replaced after a deeper search"
            ln = self.make_line(i, "instead", "before", before, mpv["moves"], score, mover_white, "", fx, next(letters))
            if ln:
                lines.append(ln)
            listed.add(mpv["moves"][0])
        # instead 2: what a search with Coordination=false plays
        o2, f2 = self.own_search(d, nodes, coordination=False, purpose="the move a search with Coordination=false plays")
        alt = o2.get("bestmove")
        alt = alt.strip("()").split(",")[b] if alt else None
        if alt and alt != "pass" and alt not in listed:
            r = self.reply_line(d, alt, before, "the opponent's answer to the Coordination=false move")
            fx = dict(r["facts"])
            fx.update({"why_listed": "the move a search of this board with Coordination=false plays",
                       "coordination_off_search": f2,
                       "coordination_off_score_mover": final_score(o2),
                       "played_move_same_method": played_same_method()})
            ln = self.make_line(i, "instead", "before", before, r["moves"], r["score_mover"], mover_white, "", fx,
                                next(letters), shift="reply")
            if ln:
                lines.append(ln)
            listed.add(alt)
        # instead 3 / refutation: after a sharp fall
        if i in self.falls:
            o4, f4 = self.own_search(d, nodes * 4, coordination=True, purpose="the same decision with four times the nodes")
            alt4 = o4.get("bestmove")
            alt4 = alt4.strip("()").split(",")[b] if alt4 else None
            if alt4 and alt4 != "pass" and alt4 not in listed:
                r = self.reply_line(d, alt4, before, "the opponent's answer to the 4x-nodes move")
                fx = dict(r["facts"])
                fx.update({"why_listed": f"the mover's score fell by {-self.falls[i]} cp by its next decision; "
                                         "a search with four times the nodes prefers this move",
                           "four_x_search": f4, "four_x_score_mover": final_score(o4),
                           "played_move_same_method": played_same_method()})
                ln = self.make_line(i, "instead", "before", before, r["moves"], r["score_mover"], mover_white, "", fx,
                                    next(letters), shift="reply")
                if ln:
                    lines.append(ln)
                listed.add(alt4)
            # the opponent's refutation: its own main line at its next decision on this board
            opp = c.opponent_seat(seat)
            nxt = next((x for x in self.decs if x["seat"] == opp and x["n"] > i and x["out"].get("main_pv")), None)
            if nxt is not None and not any(int(t[0]) - 1 == b for t in self.toks[i + 1:nxt["n"]]):
                game = c.game_at(self.rec, nxt["n"])
                start = c.board_fen(game, b)
                assume = c.pocket_diff(start, after)
                if assume is not None:
                    fx = {"purpose": "the opponent's refutation: its own main line at its next decision on this board",
                          "source": "game transcript", "binary": str(self.binary(opp).relative_to(c.ROOT)),
                          "match_log": f"logs/{self.match}/engine_logs/{nxt['file']}",
                          "commands": [nxt["position"], nxt["go"]],
                          "assume_note": "pieces that reached this board's hands before that decision" if assume else None}
                    sc = final_score(nxt["out"])
                    ln = self.make_line(i, "played", "after", start, nxt["out"]["main_pv"]["moves"], negate(sc),
                                        mover_white, assume, fx, next(letters))
                    if ln:
                        # the line is legal from `start` on that board; its other board is the one at that decision
                        lines.append(ln)
        # arrives: the leading arrival world when it is likely
        fc = out.get("forecast") or {}
        coord = out.get("coord") or {}
        aw = [w for w in fc.get("worlds", []) if w["arrival"] != "none"]
        if aw:
            w = max(aw, key=lambda w: w["p"])
            if w["p"] >= ARRIVES_P:
                cw = next((x for x in coord.get("worlds", []) if x["arrival"] == w["arrival"]), {})
                first = cw.get("best") or played
                mine, theirs = arrival_letters(w["arrival"], mover_white)
                assume = mine + theirs
                start = c.with_pocket(before, assume)
                r = self.reply_line(d, first, start, "the line planned for the leading arrival world", world_fen=start)
                played_ln = next((x for x in lines if x["kind"] == "played"), None)
                differs = first != played or not played_ln or \
                    [m["uci"] for m in played_ln["moves"][:2]] != r["moves"][1:3]
                if differs:
                    fx = dict(r["facts"])
                    fx.update({"why_listed": f"the forecast's leading arrival world {w['arrival']} had probability {w['p']:.2f}",
                               "world_best_from_game": cw.get("best") or None,
                               "world_scores_cp_mover": cw.get("values")})
                    ln = self.make_line(i, "arrives", "before", start, r["moves"], r["score_mover"], mover_white,
                                        assume, fx, next(letters), shift="reply")
                    if ln:
                        lines.append(ln)
        # threat: after a sit, the opponent's line if it were given the move
        if self.sits_before.get(i):
            pos = chess.variant.CrazyhouseBoard(before)
            if not pos.is_check():
                pos.turn = not pos.turn
                pos.ep_square = None
                flipped = pos.fen()
                self.binary_for_search = self.binary(seat)
                game = c.game_at(self.rec, i)
                fa, fb = (flipped, c.board_fen(game, 1)) if b == 0 else (c.board_fen(game, 0), flipped)
                s = self.search_spec(c.opponent_seat(seat), f"position fen {fa}|{fb}", nodes, True, d["event"]["clocks"])
                rr = self.run(s)
                oo = c.parse_output(rr["lines"])
                if oo.get("main_pv"):
                    fx = self.describe(s, rr, "the opponent's line if it were given a free move instead of the sit")
                    ln = self.make_line(i, "threat", "before", flipped, oo["main_pv"]["moves"], negate(final_score(oo)),
                                        mover_white, "", fx, next(letters))
                    if ln:
                        lines.append(ln)
        return lines

    # -------------------------------------------------------------- build

    def build(self) -> dict:
        rec = self.rec
        self.dropped = []
        self.key_set = set()
        keys = self.key_moves()
        self.key_set = set(keys)
        res = rec["result"]
        win = None if res["winner"] is None else (0 if res["winner"] == "white" else 1)
        last_i = len(self.states) - 1
        mate_board = "AB"[self.states[last_i]["board"]] if res["termination"] == "checkmate" else None
        if mate_board:
            last = self.states[last_i]
            colour = "White" if last["white"] else "Black"
            team = " and ".join(f"{s[0]}-{s[1:].capitalize()}" for s in c.TEAMS[win])
            text = f"{colour} on board {mate_board} mates; the team of {team} wins."
        elif res["termination"] == "flag":
            text = f"A clock ran out; the team of {' and '.join(c.TEAMS[win])} wins." if win is not None else "A clock ran out."
        else:
            text = res["termination"]
        moves = []
        for i, st in enumerate(self.states):
            d = self.move_dec.get(i)
            book = i < self.n_book
            ev = d["event"] if d else None
            mv = {"i": i, "board": "AB"[st["board"]],
                  "seat": ("A" if st["board"] == 0 else "B") + ("white" if st["white"] else "black"),
                  "num": st["num"], "uci": st["uci"], "san": st["san"],
                  "fen": {"A": st["after"][0], "B": st["after"][1]},
                  "t": round(ev["t"] / 1000, 1) if ev else None,
                  "clocks": {c.SEATS[k]: round(v / 1000, 1) for k, v in enumerate(ev["clocks"])} if ev else None,
                  "eval": None, "mate": None, "book": book, "waited": None, "glyph": None, "note": None, "lines": []}
            if d and not book:
                cp, mate = white_view(final_score(d["out"]), st["white"])
                mv["eval"], mv["mate"] = cp, mate
                sits = self.sits_before.get(i)
                if sits:
                    whys = [x["out"]["summary"].get("reason") for x in sits]
                    why = max(set(whys), key=whys.count)
                    mv["waited"] = {"seconds": round((ev["t"] - sits[0]["event"]["t"]) / 1000, 1),
                                    "why": c.WAIT_CODES.get(why, why or "waited")}
                mv["facts"] = self.move_facts(i)
                if i == last_i:
                    end = self.sitting_at_end()
                    if end:
                        mv["facts"]["sitting_at_end"] = end
                if i in keys:
                    mv["facts"]["key"] = keys[i]
                    mv["lines"] = [] if NO_LINES else self.lines_for(i)
            # the last move: '#' when the referee ended the game by checkmate with it
            if i == last_i and res["termination"] == "checkmate":
                mv["san"] = mv["san"].rstrip("+") + "#"
            moves.append(mv)
        seats = {s: self.names[s] for s in c.SEATS}
        game = {"version": 1, "id": self.x["id"], "title": None, "summary": None,
                "event": c.MATCHES[self.match]["event"], "date": self.date, "seats": seats,
                "teams": c.TEAMS, "result": {"winner": win, "how": res["termination"], "board": mate_board, "text": text},
                "initial_clock": rec["clock"]["initial_ms"] / 1000,
                "start": {"A": c.start_game(rec).boards[0].fen(), "B": c.start_game(rec).boards[1].fen()},
                "moves": moves}
        game["builder"] = {"match": self.match, "game_index": self.g, "pair": rec["pair"],
                           "match_dir": f"logs/{self.match}", "selection_rank": self.x["rank"],
                           "key_moves": sorted(keys), "dropped_lines": self.dropped,
                           "nodes": self.nodes, "searches_this_build": self.searches,
                           "decisions": len(self.decs),
                           "decisions_reproduced": sum(self.reproduced(d) for d in self.decs),
                           "replay_binaries": {s: v["binary"] for s, v in self.replay.items()}}
        return game


def main():
    sel = json.loads((c.OUT / "selection.json").read_text())
    ids = [a for a in sys.argv[1:] if not a.startswith("--")] or sel["picked"]
    entries = {x["id"]: x for x in sel["games"]}
    loaded = {}
    for gid in ids:
        x = entries[gid]
        m = loaded.get(x["match"]) or loaded.setdefault(x["match"], c.load_match(x["match"]))
        gb = GameBuilder(x, m)
        game = gb.build()
        c.write_json(c.OUT / "facts" / f"{gid}.json", game)
        kinds = {}
        for mv in game["moves"]:
            for ln in mv["lines"]:
                kinds[ln["kind"]] = kinds.get(ln["kind"], 0) + 1
        print(f"{gid}: {len(game['builder']['key_moves'])} key moves, lines {kinds}, "
              f"{game['builder']['decisions_reproduced']}/{game['builder']['decisions']} decisions reproduced, "
              f"{len(game['builder']['dropped_lines'])} lines dropped", flush=True)


if __name__ == "__main__":
    main()
