# Annotated games: the fact pipeline

These scripts turn arena match logs into the game files of the website's
annotated bughouse games (`/bughouse-games`, data contract version 1). They
produce the facts; people or agents write the prose from the fact sheets, and
nobody needs to compute any chess to do it.

Inputs: `logs/v7-vs-v110-sanity`, `logs/v7b-vs-v110-sanity`,
`logs/v7-selfplay-flags` (results, transcripts, manifests), the binaries in
`bin/` and `engine/src/stockfish`, the net in `nets/`, the arena's referee
from a Chess-Auto-Prep checkout (`HB_ARENA_TOOLS`, default
`~/Projects/Chess-Auto-Prep/tools`) and the post-mortem script
(`HB_POSTMORTEM`, default `~/Projects/HypeBeast-v5/scripts/postmortem.py`).
Everything is written under `logs/collection/`.

## Steps, in order

```
python3 scripts/collection/select.py            # 1. rank the 124 games, pick 10   -> selection.json
python3 scripts/collection/replay.py [--check]  # 2. replay every engine process of the picks (cached)
python3 scripts/collection/build_game.py        # 3. fact sheets with key moves and lines -> facts/<id>.json
python3 scripts/collection/notes_template.py    # 4. the annotator's to-do lists     -> notes/<id>.todo.json
#    annotators copy notes/<id>.todo.json to notes/<id>.json and fill it in
python3 scripts/collection/merge.py             # 5. publishable files               -> site/<id>-<hash>.json, site/index.json
python3 scripts/collection/check.py             # 6. contract, referee and notes checks (exit 1 on any failure)
```

Each step takes game ids (e.g. `selfplay-g45`) to work on some games only.
Engine runs are single-process, fixed-node, at `nice -n 19`, one at a time;
every search is cached in `logs/collection/cache/` by its exact commands and
binary hash, so a rerun of steps 2 and 3 costs nothing. Step 2 runs inside
step 3 anyway; running it first only separates the long part.

## For the annotator

You fill in `notes/<id>.json` (a copy of `<id>.todo.json`): `title` (at most
60 characters), `summary` (one to three sentences), and for each key move a
`glyph` (null or `!`, `!!`, `?`, `??`, `!?`, `?!`), a `note` (plain text, at
most 500 characters), a `note` per line, and `drop: true` on a line you want
left out. `extra_notes` takes `{"<move index>": "text"}` for a note on a move
that is not key. Nothing else is read.

Write moves in SAN exactly as the fact sheet has them (`N@f3+`, `Qxd4`,
`P@e5`). `check.py` fails a note that names a piece move, capture, drop,
castling or promotion which is not a move of the game, a move of that move's
lines, or a move named in that move's `facts`. `ANNOTATING.md` has the full
instructions for writing the notes; `annotator_view.py` writes the compact
`view/<id>.json` an annotator reads. If a fact is not in the sheet, do not state it.

Two points of view occur, and every number says which:

- **White's view**: the contract's `eval`/`mate` on moves and lines, and
  every `*_white_*` field. Positive is good for White *on that board*.
- **The mover's view** (`*_mover_*`): positive is good for the side that made
  the move. The engine reports its scores this way; the builder converts.
  For a black move, `score_white_cp = -score_mover_cp`.

Board A's White and board B's Black are partners (team 0); board A's Black
and board B's White are team 1. "The partner" is the mover's partner on the
other board; "the opponent's partner" (the "diagonal" seat in sit details) is
the seat of the mover's own colour on the other board.

Centipawns (cp): 100 is about a pawn. Bughouse scores move far more than in
chess: a piece in hand that can be dropped is often worth several pawns, and
a score of 2000 or more usually means a mating attack.

## The fact sheet

`facts/<id>.json` is the contract's game file with `title`, `summary`,
`glyph` and `note` left null, a `builder` object (provenance: match, game
index, key move indexes, lines that were dropped and why, how many decisions
the replay reproduced) and a `facts` object on every move after the opening
book. `merge.py` removes `builder` and every `facts`.

Opening moves (`book: true`) are the arena's fixed openings (16 half-moves),
not engine choices: they have no facts.

### `facts` on a move

The engine numbers are those the mover's engine printed for this decision in
the match transcript (`logs/<match>/engine_logs/`), unless a field says
otherwise. Where each meaning was confirmed is given in brackets.

| Field | Meaning |
|---|---|
| `engine`, `nodes` | The mover's engine and its node budget for every move. [manifest.json] |
| `score_mover_cp` / `score_mover_mate` | The engine's score at the end of its main search, from the mover's side: centipawns, or moves to a forced mate on this board (negative: the mover is mated). Exactly what the arena wrote into `[%eval]`. [arena players.py `_last_score`; hb_arena.cpp prints the main search's exact score last] |
| `score_white_cp` / `score_white_mate` | The same from this board's White; equals the move's `eval`/`mate`. |
| `score_is_for` | Which move the score belongs to. The score is the main search's, so when the move played is not the board's own search move it is the score of `own_best`, not of the move played. |
| `depth` | Completed depth (plies) of the main search. Near a forced mate it can read hundreds: the search finishes iterations instantly. [hb_arena.cpp `main_depth`] |
| `reason`, `reason_meaning` | Why this move (or sit) was chosen: the engine's reason code and a one-line meaning. [hb_coordinator.cpp `coordinate`, `draw_policy`, `consider_voluntary_wait`] Codes: see below. |
| `override` | True when coordination replaced the board's own search move (hb_summary `override=1`). |
| `own_best_san` / `own_best_uci` | The board's own search move (the first move of the main search's line) when it is not the move played. With `override` false this happens only when the leftover budget deepened the search and changed the move (`own_best_note`). |
| `own_best_exposed_to` | For `exposure_veto` / `soft_switch`: the capture the opponent could make after `own_best` (`opponent_capture_san`/`_uci`, this board) and the mating drop its partner would then have (`then_drop_board`, `then_drop_san`/`_uci`; the SAN is null when the drop becomes legal only after a move of the mover's partner on that board). [hb_coordinator.cpp `exposure_tier`, `resolve_tier`] |
| `forecast.partner_board_on_turn` | Who was to move on the partner board when the forecast was made. |
| `forecast.worlds[]` | What the engine expected to arrive on this board from the other one before its next move. `arrival` is the engine's key: `+N` a knight for the mover (its partner captures one), `-Q` a queen for the mover's opponent (the opponent's partner captures one), `none` nothing; `pieces_for_mover`/`pieces_for_opponent` spell it out; `probability` is the engine's (85% of a line's weight is believed, packages under 4% fold into `none`, at most three arrival worlds). The packages are the captures in the first two plies of the best partner-board lines, weighted by score. [hb_forecast.cpp `weigh`, `make_forecast`] |
| `forecast.worlds[].candidate_scores_cp_mover` | On key and overridden moves: each candidate's score in that world, mover's view, cp (mate: ±(100000 − plies)). The `none` world is a search of the real position; an arrival world is a search with those pieces in hand, where the mover's own arrival cannot be dropped on the first move. [hb_coordinator.cpp, WorldRun] |
| `candidates[]` | On key and overridden moves: the moves coordination compared (`source`: `main` = the board's own search move, `root` = the next move of that search, `delivery` = a capture that sends the partner something useful, `world` = the best move of an arrival world, `safety` = a move found safe from a fed mate), with `weighted_win_chance`: the probability-weighted winning chance over the worlds (logistic in cp with 1000 cp per unit; a mate is 0 or 1; in the `none` world no candidate counts as better than the main move). A replacement needs a lead of 25 cp-equivalent. [hb_coordinator.cpp lines on E, S, WorldSwitchMargin] |
| `arrived[]` | What really reached either hand on this board after the move, until the mover's next move here: `piece`, `hand` (`mover` or `opponent`), `by` (the capture on the other board, SAN), `board`, `i` (its move index), `when` (`before the opponent's reply` or `before the mover's next move`). Computed by replaying the game with the referee (a promoted piece arrives as a pawn). |
| `prices` | Shown when the move captures or the main line carries feed. The feed prices the search used: `mover_captures_cp[T]` is added to the mover's score whenever the mover captures a T on this board (half of what one more T in hand gains the partner on the other board by a 3-ply probe, at most 500; 800 when that piece lets the partner mate); `opponent_captures_cp[T]` is subtracted whenever the opponent captures the mover's T (half of what it gains the opponent's partner, at most 500; 1500 when it lets them mate the partner; 0 when the partner already looks lost). `partner_board_score_cp_partner`: the partner board's 3-ply probe score from the partner's side, clipped to ±2000 (given only where a replay confirmed the probe finished: the transcript prints 0 for an unfinished one); `partner_lost`: that score is −2000 or worse. [hb_coordinator.cpp `prepare_feed_prices`; position.cpp `do_move`] |
| `piece_values_partner_board` | v1.1.1 seats, when the decision was reproduced: what one more piece in hand is worth on the partner board, unhalved, uncapped, from each receiver's own side, in cp, or `"mate"` (the piece turns the probe into a mate): `one_more_for_partner_cp` (the partner receives it), `one_more_for_opponents_partner_cp` (the opponent's partner does). 3-ply probes, each score clipped to ±2000; a value can be negative (a shallow probe is noisy; the prices clamp it to 0). The prices above are derived from the same probes. [README "three reports"; hb_coordinator.cpp `PieceValues`] |
| `fed_cp_mover` | How much of the main line's score is feed prices: the prices summed over the captures along the main line, mover's view, cp. [search.cpp `hb_fed_along`] `own_board_cp_mover` = `score_mover_cp − fed_cp_mover`, the board's own score along that line. `fed_source` says whether the engine printed it in a replay of the decision (`engine`) or it is the same sum done from the logged prices and line (`estimate`; within 2 cp of the engine's figure on all 947 decisions where both exist, rounding). |
| `sat_before[]` | The sits by the mover before this move, in this turn: game time `t` (s), `reason` and `meaning`, `searched` (whether that decision ran a search: holds and stalls are decided after one; a voluntary wait, and a hold or stall that continues while nothing has moved, are decided without), and `detail`: for `hold_mated` the plies to the mate against the mover, the partner board's score for the partner, the mover's clock and the diagonal seat's (ms), the lead, the lead needed and the partner's mate length when one was needed; for `hold_partner_mate` the partner's mate length (moves) and the clocks; for `stall_deny` the capture and the mating drop it denies. [hb_coordinator.cpp `hold_mated`, `hold_guard`] |
| `sitting_at_end` | On the game's last move only: seats that were sitting when the game ended (their sit is followed by no move, so no `waited` can carry it): `seat`, `engine`, `since_t` (s), `sits` (decisions), `reason`, `meaning`, `detail` as in `sat_before`. |
| `replay` | `reproduced`: replaying the engine process printed the same move, score, depth and node count as in the match; `differs`; `not replayed` (v1.1.0's seats are replayed only in `v111-v110-g10` and `v111pre-v110-g28`, as a check: no v1.1.0 fact uses a replay). v1.1.1's seats in `v111pre-*` games were played by a pre-release build that is no longer on this machine and are replayed with the release binary. |
| `key` | On key moves: why the move is key (rules below). |

The move's `waited` (contract field) is `{"seconds": time from the first sit of the turn to the move, "why": code}`; codes:
`partner_mate` (hold_partner_mate), `mated` (hold_mated), `deny_feed` (stall_deny), `wait_delivery` (voluntary_wait).

### Reason codes

| Code | Meaning |
|---|---|
| `kept_main` | the board's own search move was kept: no candidate had a probability-weighted winning chance over the forecast worlds at least 25 cp-equivalent better |
| `world_switch` | another candidate replaced it: over the forecast worlds its weighted winning chance was at least 25 cp-equivalent better |
| `no_arrivals` | nothing was forecast to arrive; the board's own move was played (the leftover budget may deepen that search and change the move) |
| `only_move` | the only legal move |
| `team_win_main`, `team_win_override` | a move ends the game at once by the referee's rules (the board's own move, or another that replaced it) |
| `delivery_win_main`, `delivery_win` | a capture lets the partner, on turn, drop the piece for an immediate team mate (the board's own move, or another that replaced it) |
| `exposure_veto` | the board's own move let the opponent capture a piece that its partner can drop for mate on the other board, at once or whatever the mover's partner (in check there) replies; a safer candidate was played |
| `soft_switch` | the same danger, but only if the mover's partner fails to move away (or a short probe scored the arrival as mate); a safe candidate within 600 cp was played |
| `stall_deny` | sat: every reasonable move is exposed like that, and the clocks allowed sitting (the opponent cannot capture until the mover moves) |
| `hold_mated` | sat: every move is mated on this board, the partner is still in the game, and the mover's clock outlasts the seat it races |
| `hold_partner_mate` | sat: the partner has a forced mate on the other board; while the mover sits, its opponent captures nothing to send to the side being mated |
| `voluntary_wait` | sat a few seconds: the partner, on turn, can capture a piece that gives the mover a winning drop (or a block in check) |
| `avoid_draw`, `seek_draw` | the referee's threefold repetition: avoided while not losing, taken when clearly lost |

### Key moves

8 to 15 per game, by rule, in this order until 15: the mating side's last
three moves on the mating board; up to two moves preceded by a sit; up to two
drops of a piece that a forecast world (probability 0.25 or more) named and
that arrived before the move; the two decisions after which the mover's score
fell most by its next decision (500 cp or more, mates counted as 2000); up to
three moves where coordination replaced the board's own move (rarer reasons
first, then the largest gain in weighted winning chance); up to two moves
whose main line was at least half feed price (|fed| ≥ 150 cp and |fed| ≥
|score − fed|); then enough of the remaining overrides, feed-heavy moves and
falls from the first 70% of the game to have three key moves there, and to
reach eight.

### Lines

Every line is the engine's, legal from its `start` with the referee (the
other board frozen, so this board's reserves change only by its own drops,
except the pieces in `assume`), at most eight moves, at least two. A line is
cut at the first move that is not legal on that board alone: a main line can
drop a piece the forecast only expected to arrive. Each line's `facts` names
the search that produced it: `source` (`game transcript` or `fresh-process
search`), binary and hash, the exact commands, `purpose`, `why_listed`,
`score_mover_cp`/`score_mover_mate` (the line's score from the mover's
side; the contract's `eval`/`mate` give it from White's), and
`truncated_from` (the engine line's length when it was cut).

A line's `mate` counts the mating side's moves from the line's `start`
(the engine counts from the position it searched, which can be one move
earlier or later; `facts.engine_mate_count` keeps the engine's number when
the two differ). A move's own `mate` is the engine's count from the position
before the move, the move itself included. A line can end before the mate:
it is cut at eight moves or at a move not legal on the board alone.

- `played`, from `after`: the mover's own main line after the move, from the
  transcript, when it begins with the move played. Otherwise (coordination
  replaced the move) the move played followed by the opponent's answer: the
  mover's engine searching for the opponent's seat after the move, full
  coordination, the game's node budget, in a fresh process. After a sharp
  fall a second `played` line may give the opponent's refutation: its own
  main line at its next decision on this board, from the transcript; its
  `start` is the board at that decision, and `assume` names the pieces that
  had reached this board's hands by then.
- `instead`, from `before`: (1) the board's own search move when
  coordination replaced it, with the main line from the transcript (score:
  the decision's own score); (2) the move a search of this board with
  `Coordination=false` plays, if different; (3) after a sharp fall, the move
  a search with four times the nodes plays, if different. (2) and (3) are
  the move followed by the opponent's answer, searched as for `played`, and
  their `facts.played_move_same_method` holds the move played searched the
  same way, so the two scores compare like with like. Do not compare them
  with the decision's own `score_mover_cp`: that search ran in the game's
  process with its history; these run in a fresh one.
- `arrives`, from `before`: when the forecast's likeliest arrival world has
  probability 0.5 or more, the best move the engine found for that world in
  the game (`world_best_from_game`, else the move played) followed by the
  opponent's answer in that world; `start` holds the arriving pieces
  (`assume`), and the other board is as it was. Listed when its first two
  moves differ from the played line's.
- `threat`, from `before`, on moves preceded by a sit: the opponent's main
  line had it been given the move instead of the sit (the same position with
  the turn passed; not when the mover was in check).

## Engine behaviour these scripts rely on (checked by running)

- In HypeBeast mode `go ... searchmoves` is ignored: the arena's `go` parser
  (hb_arena.cpp `parse_go`) does not read it, with or without coordination.
  So no search can be restricted to one first move; `instead` lines play the
  move and search the reply instead.
- With `Coordination=false` the main search honours `MultiPV`. With
  coordination on, setting `MultiPV` changes the decision itself; it is
  never set here.
- A fresh process reproduces only a process's first decision exactly; later
  ones depend on the search history of the earlier searches. `replay.py`
  therefore replays each engine process as a whole.
