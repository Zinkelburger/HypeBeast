# HypeBeast

A bughouse engine that runs on a CPU. It is a fork of
[Fairy-Stockfish](https://github.com/fairy-stockfish/Fairy-Stockfish) with a
coordinator on top: each seat searches its own board with alpha-beta and the
stock Fairy-Stockfish bughouse network, and decides its move knowing what is
likely to arrive from the other board.

## What it adds to Fairy-Stockfish

- **Forecast.** Before searching its own board, a seat searches its partner's
  board and reads off the captures likely in the next two plies: pieces coming
  to it, and pieces coming to its opponent.
- **Worlds.** It searches its own board once for "nothing arrives" and once
  for each likely package of arrivals, then plays the move with the best
  probability-weighted winning chance.
- **Chance inside the search (v5).** In the first plies of its own search, a
  side may also drop a piece that the forecast says is likely to have
  arrived by then; the position's value mixes, in winning chances, the line
  where it arrives with the line where it does not.
- **Referee draws (v5).** The arena draws on a threefold repetition of the
  board with the pockets ignored. When ahead, HypeBeast avoids moves that
  complete one or let the opponent complete one; when clearly lost, it takes
  one.
- **Feed prices.** A capture is priced by what the captured piece is worth to
  the player who receives it on the other board.
- **Exposure and stalling.** A move that lets the opponent's partner feed a
  mating drop is avoided, or the seat sits when the clocks allow it.

`PLAN.md` has the design, the reasons and every measurement.

## Results so far

All matches use a virtual clock (a move costs 1.5–2.5 s of game time whatever
the search took) and are small. Treat them as screens.

| Match | Result |
|---|---|
| v4 against v3, 100 games | 69–31, Elo +139 (95% +68 to +210) |
| v4 against [HiveMind](https://github.com/aminwoo/hivemind) on CPU at 400 nodes, 10 games | 8–2 (95% interval on the score 49.5% to 94.2%) |
| v4 against HiveMind on CPU at 1500 nodes, 1 game | won |
| v5 settings (chance4 build) against HiveMind at 1500 nodes, 40 games, 4.5M nodes a move | 28–9–3, 73.8% (95% 62.2% to 85.3%) |
| v4 source (bin/hypebeast-base) against HiveMind at 1500 nodes, same 40 openings | 20–17–3, 53.7% (95% 35.2% to 72.3%) |
| v5's chance settings (chance2 build) against v4 source, 100 held-out games, 500k nodes | 67–31–2, Elo +131 (95% +73 to +197) |
| v5 against HiveMind at 5000 nodes, 20 games | 13–7, 65.0% (95% 48.0% to 78.9%) |
| v6's change (castling earns no feed price) against v5, 100 held-out games, 500k nodes | 61–38–1, Elo +81 (95% +12 to +151) |

## Download and run

Binaries for Linux, Windows and macOS are on the
[releases page](../../releases). Use the `bmi2` build on a CPU from 2013 or
later (Intel Haswell, AMD Zen 3 and newer) and `modern` otherwise.

The engine needs the Fairy-Stockfish bughouse network, which is not part of
the release. Download the **bughouse** row from
<https://fairy-stockfish.github.io/nnue/> (`bughouse-cd8cceab93fe.nnue`,
sha256 `cd8cceab93fed185b79932414d1a0823f40e15a09ca9776ceab7c9c5272ddc13`)
and pass its path as `EvalFile`.

HypeBeast speaks UCI with the two-board extensions of the
[bughouse arena](https://github.com/Zinkelburger/Chess-Auto-Prep/tree/dev/tools/bughouse_arena).
One process plays one seat and is given both boards:

```
setoption name HypeBeast value true
setoption name EvalFile value bughouse-cd8cceab93fe.nnue
setoption name Seat value Awhite
setoption name Team value white
setoption name TimeAdvantage value false
setoption name Clocks value 120000,120000,120000,120000
position startpos moves 1e2e4 2d2d4 1e7e5 2d7d5
go movetime 5000
```

- A move is the board number and the UCI move: `1e2e4` is e2e4 on board A,
  `2N@f3` drops a knight on board B. `position fen <A>|<B> moves ...` starts
  from two FENs.
- `Team white` is White on board A and Black on board B. `Seat` is the board
  and colour this process plays.
- `Clocks` is the four clocks in milliseconds: A white, A black, B white, B
  black. `TimeAdvantage` says whether the team is ahead on the clock.
- The answer is `bestmove (moveA,moveB)` with `pass` for the board this seat
  does not play, or for both when it chooses to sit.
- `go movetime` and `go nodes` are supported. Searches under 500 ms or
  200,000 nodes skip the forecast, and with it the chance search.
- v5's settings are the defaults (`HBChance`, `HBChanceStable`,
  `HBChanceHorizon=1`, the fitted `HBChanceTrust*`/`Late*`/`Floor*` values,
  `HBAvoidDraw`, `HBSeekDraw`). `HBChance=false HBAvoidDraw=false
  HBSeekDraw=false` plays exactly as v4.
- v6 adds `HBFeedCastleFix` (on): castling is no longer priced as handing a
  rook to the partner. `HBFeedCastleFix=false` plays exactly as v5.

Without `HypeBeast=true` the binary is ordinary Fairy-Stockfish, and it still
reports itself as Fairy-Stockfish in `id name`.

## Build

```
cd engine/src
make -j build ARCH=x86-64-bmi2 COMP=gcc
```

The binary is `engine/src/stockfish`. After adding or changing a header,
delete `engine/src/.depend` first; the Makefile only writes it when missing.

## Tests and matches

`tests/run_all.sh` runs the engine-side checks. They import the referee from a
[Chess-Auto-Prep](https://github.com/Zinkelburger/Chess-Auto-Prep) checkout
(`HB_ARENA_TOOLS`, default `~/Projects/Chess-Auto-Prep/tools`).
`tests/test_chance.py` and `tests/test_draw.py` check the chance search and
the draw policy on crafted and real positions. `tests/loss_set.py` and
`tests/feed_set.py` replay decisive positions from lost games (the feed set:
seven moves that handed HiveMind's side the mating piece);
`tests/flag_report.py` sorts out games that ended on the clock.
`scripts/run_hivemind_benchmark.sh` and `scripts/hm_match.sh` play a binary
against HiveMind through the arena. The arena needs a local patch for
HiveMind's occasional `bestmove (none)`; PLAN.md (revision 10) describes it.

## License

The engine under `engine/` is Fairy-Stockfish with HypeBeast's changes and is
licensed under the GNU GPL version 3 or later (`engine/Copying.txt`). The
rest of the repository is under the license in `LICENSE`.
