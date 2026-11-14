# How HypeBeast chooses a move

This is the algorithm as the code stands on this branch (binary `hypebeast-v8d`),
written for someone who wants to read the match data or change the engine. The
design history and the reasons are in `PLAN.md`; every experiment and its result
is in `EXPERIMENTS.md`; the partner-message designs are in `PARTNER_TALK.md`.

## The game and the set-up

Bughouse is played on two boards by two teams of two. A piece captured on one
board goes to the hand of the capturer's partner, who may drop it on the other
board instead of moving. A game ends when either king is mated or a clock runs out.

Each of the four seats is its own engine process. It is told both boards and the
four clocks, searches when its seat is on turn, and answers with a move or with
`pass` (it sits and lets its clock run). The referee is the
[bughouse arena](https://github.com/Zinkelburger/Chess-Auto-Prep/tree/dev/tools/bughouse_arena);
`README.md` shows the protocol. Two rules of the referee matter below: a mate does
not stand while the mated seat's partner could still feed a piece that blocks it,
and a seat that sits is asked again whenever the other board moves.

The engine is Fairy-Stockfish (alpha-beta, the stock bughouse NNUE network) with a
coordinator around it, all in `engine/src/hb_*.cpp`. With `HypeBeast=false` the
binary is plain Fairy-Stockfish.

## One decision

A decision has a budget (nodes or milliseconds) that is divided in advance
(`Budget`, `hb_probe.cpp`): by default 66% for everything up to and including the
main search, the rest for the searches after it, 2% held back.

1. **Wait?** (`consider_voluntary_wait`) Before any search, a seat may sit for up
   to 3 s when the conditions of `PLAN.md` 5.4 hold.
2. **Feed prices** (`prepare_feed_prices`, option `HBFeedPrices`). Eleven small
   searches of the partner's board: as it is, and with one more piece of each type
   in each hand. Half of what a piece gains there (capped at 500 cp; 800 or 1500
   when it makes or allows a mate) is added, inside the main search, to every
   capture of that piece type. Off in the current candidate: it lost matches.
3. **Forecast** (`make_forecast`, `hb_forecast.cpp`). What is likely to arrive
   from the partner's board:
   - a MultiPV search of that board, 4 lines, 7% of the budget;
   - a second search, 3%, of up to 4 captures that are not in those lines (a
     capture that is poor on that board may be played for what the piece does on
     ours);
   - with `HBTell=plan`, one more line: the partner's own main line, from its
     message (see "Talking" below);
   - each line's captures in its first 2 plies are an arrival package ("we get a
     knight, they get a bishop": `+N-B`), those in plies 3-4 a later package;
   - 3% for small searches of our own board that say what each such piece is worth
     here, used to tilt the line weights.
4. **Worlds** (`weigh`). Lines are weighted by a softmax of their scores
   (temperature 250 cp). 85% of a line's weight goes to its package; with
   `HBForecastTrustLate=50`, half of that to the package including its later
   captures. Equal packages are merged. At most 4 worlds are kept, "nothing
   arrives" always among them; a package under 4% is folded into it.
5. **Main search.** Ordinary alpha-beta on our own board with the hands as they
   are. Its move is the default.
6. **Coordinator** (`coordinate`, `hb_coordinator.cpp`), in this order:
   - a move that wins the game at once by the referee's rules is played;
   - the referee's draw by repetition is taken when lost and avoided otherwise;
   - holds: a seat that is mated by force sits while its partner can still win the
     race, and a seat sits while its partner is about to mate (`HBHold`,
     `HBPlayOn`); the clocks decide whether sitting is affordable;
   - candidates: the main search's best moves, moves that deliver a piece the
     partner needs, and each world's own best move;
   - exposure: a candidate after which a piece the opponent's partner can capture
     would mate us is avoided, or the seat stalls when its clock allows;
   - for each arrival world, the position with the package already in the hands is
     searched for its best move, then every candidate is scored in every world;
     the "nothing arrives" world is scored by a MultiPV search of the candidates;
   - a candidate's expected winning chance is `E = sum over worlds of p(world) *
     win(score in that world)`, with `win` a logistic of the score (1000 cp per
     unit) and a mate counted as 0 or 1. The main move is replaced when another
     candidate's `E`, turned back into centipawns, is at least 25 better
     (`world_switch`);
   - whatever budget is left deepens the main search.

Every decision prints what it used: `hb_forecast` (lines, weights, worlds),
`hb_coord` (candidates, their value in each world, `E`), `hb_summary` (the move,
the reason, depth, nodes), and `hb_tell` when talking is on.

## Talking (`HBTell`, `PARTNER_TALK.md`)

A seat's last `info string hb_tell ...` is passed by the arena to its partner
before the partner's next search (`HBPartnerTell`). Modes tried:

| mode | what is said | what the hearer does | result against the same engine without it |
|---|---|---|---|
| `alarm` | which piece, in which hand, mates on my board | prices that capture in its main search | 51-49 |
| `table` | what each of the ten pieces is worth on my board (ten small extra searches) | prices every capture by a share of it | 5-19 at half share (stopped), 47-53 at a quarter |
| `minimal` | the best lines of my main search's last iterations | uses them INSTEAD of searching my board | 4-11 (stopped) |
| `plan` | the same lines | adds my first line to its own search's lines, weight 60% | see `EXPERIMENTS.md` |

What those matches taught: the seat's own search of its partner's board is not
redundant with the partner's search. The first asks broadly "what can arrive", the
second narrowly "what is my best move". The partner's line names the move that is
then played 62 times in 100, the hearer's own first line 46 times; but the move
played is in one of the hearer's own lines 85 times in 100, and in a told line 65
to 69 times.

## What is known not to work, and what is open

`EXPERIMENTS.md` has the numbers. In short:

- Pricing captures by the partner's need, from our own probes or from its table:
  lost every time. The prices are noisy and enter every capture in the search.
- Putting a forecast piece into the hand only at the ply it can arrive
  (`HBArrivalTiming`): lost. Having it at once makes the seat defend a move early.
- Open: choosing moves by both boards' scores together. The team's result follows
  the two scores about equally (`analysis/two-board-surface/`), and a seat today
  weighs its moves by its own board alone.
- Open: sudden mates after an arrival are the largest single cause of lost games
  (`AUTOPSY.md`), and in most of them the capture was in the partner's own line.
