# How HypeBeast works

This describes the engine as released in v1.1.1 (engine v7), with the default
options. The README has the short version. `PLAN.md` has the history: why each
part was built and every match behind it. `docs/OPTIONS.md` lists the options
named here, and `docs/REJECTED.md` the ideas that were measured and removed.

## The problem

In bughouse a captured piece goes to the capturer's partner, who may drop it
on the other board instead of moving. So a position cannot be judged from one
board alone: a quiet position is lost if a knight is about to arrive for the
opponent, and a bad trade is good if the piece mates on the other board.

Fairy-Stockfish searches one board. Its bughouse mode handles the other board
with "virtual drops": a side may drop pieces it does not hold, under fixed
rules that do not look at the other board. HypeBeast turns that mechanism off
and puts a forecast in its place: it looks at the other board, estimates which
pieces are likely to arrive and when, and uses those probabilities both inside
the search and when it chooses the move.

Everything else is Fairy-Stockfish: the alpha-beta search and the published
bughouse network (NNUE), which evaluates one board with its pockets. The
network was not retrained.

## Terms

| Term | Meaning |
|---|---|
| Seat | One player: a board and a colour. Each seat is its own engine process and is given both boards. |
| Our board, partner board | The board this seat plays on, and the other one. |
| Partner | The team-mate. On the partner board they play the opposite colour to ours. |
| Diagonal seat | The opponent on the partner board. They play our colour. |
| Arrival | A piece captured on the partner board that lands in a pocket on our board. |
| Feed | To let a piece be captured, which hands it to the capturer's partner. |
| Sit | To decline to move while on turn. Our clock runs and our board is frozen: nobody can capture or drop on it. |
| Winning chance | A score turned into a probability: `1 / (1 + exp(-cp / 1000))`. A forced mate is 1 or 0. |

A captured piece keeps its colour and goes to the player of that colour on the
other board. If we are White on board A, our partner is Black on board B:

```
Board A:  we play White          against  our opponent (Black)
Board B:  our partner (Black)    against  the diagonal seat (White)

Our partner takes a white piece on B     ->  it arrives in our pocket
The diagonal seat takes a black piece    ->  it arrives in our opponent's pocket
We take a black piece on A               ->  our partner gets it
Our opponent takes a white piece on A    ->  the diagonal seat gets it
```

The two partners do not exchange messages. Each seat forecasts the other
board for itself. Because both run the same checks, a seat can sometimes rely
on what its partner will do (see "Waits" below).

## One move, start to finish

For each `go` the seat works through these steps in order, one at a time, all
out of one budget of time or nodes.

1. **Sit without searching?** If a sit from an earlier call still applies and
   nothing has moved, keep sitting. If the partner is about to hand us a
   winning piece, wait for it.
2. **Price the pieces** on the partner board (feed prices).
3. **Forecast** the partner board: which captures are likely, and so which
   pieces arrive on our board.
4. **Main search** of our board. It is ordinary alpha-beta with two changes:
   captures carry their feed price, and likely arrivals can be dropped at
   chance nodes.
5. **Worlds.** Search our board again once per likely package of arrivals and
   choose the move with the best expected winning chance.
6. **Team rules** on the chosen move: take a verified win, do not feed a
   mating drop, sit when sitting is better than any move, handle the referee's
   draws.

With the forecast on, about 13% of the budget goes to the forecast, about 45%
to the main search and the rest to the worlds. The main search runs on the
engine's thread pool with the main hash table. Every other search (the
probes, the forecast, the arrival worlds) runs on a separate single-threaded
worker with its own small hash table, so it cannot disturb the main search.

A search under 500 ms or of 200,000 nodes or fewer skips steps 2, 3 and 5 and
the chance nodes. See "Short searches".

## Is anything sampled?

No. There is no random sampling and no Monte Carlo playout. Uncertainty about
arrivals is handled in two ways, and both enumerate the outcomes and weigh
them:

- **At the root (worlds):** up to four concrete outcomes ("nothing arrives",
  "we get a knight", "they get a queen", ...) each with a probability. Every
  candidate move is searched in every one of them.
- **Inside the tree (chance nodes):** at a node, the value is the weighted
  average of two cases, "the piece has arrived and is dropped" and "it has
  not", using that piece's probability.

Both averages are taken over winning chances, not centipawns. Averaging
centipawns breaks on mates: half of a mate score is still an enormous number.
As a winning chance a mate is exactly 1, and a 50% chance of mating from an
equal position is 0.75.

## 1. Feed prices

*What a capture is worth on the other board. Since v3; switch `HBFeedPrices`.*

Before the main search, the seat searches the partner board 11 times at depth
3: once as it stands, then with one extra pawn, knight, bishop, rook or queen
in our partner's pocket, and the same for the diagonal seat's pocket. The
difference from the base score is what that piece is worth there.

| Piece goes to | Price |
|---|---|
| Our partner | half the gain, at most 500 cp; 800 cp if it gives our partner a mate |
| The diagonal seat | half our partner's loss, at most 500 cp; 1500 cp if it lets them mate our partner; 0 if our partner already looks lost |

Half, because a piece in hand cannot always be used at once.

In the main search every capture adds its price to a running total for the
line: plus when we capture (our partner gets the piece), minus when our
opponent does. The total is added to the evaluation at the end of the line.
So the search prefers to win the piece its partner needs, and avoids losing
the piece that hurts on the other board, without searching two boards
together. A promoted piece counts as a pawn, since that is what arrives.
Castling counts as nothing (v6 fixed a bug that priced it as a rook).

Prices are measured afresh for each move, so the main hash table is cleared
for each move. The engine prints them as `info string hb_prices`.

## 2. The forecast

*Which pieces are about to arrive. Since v4; `hb_forecast.cpp`.*

**Lines.** The seat searches the partner board for its four best lines (7% of
the budget). Captures that are not the first move of any of those lines, up to
four of them, most valuable victim first, are searched as well (3%): a
capture can be poor on that board alone and still be played for what the piece
does on ours.

**Arrivals.** In each line, the captures in the first two plies form a
package of arrivals, written like `+N` (we get a knight), `-Q` (our opponent
gets a queen) or `+N-B`. Captures in plies 3 and 4 are read too and used only
for the chance table below.

**What a package is worth to us.** For each piece type in a package, our own
board is searched at depth 5 with and without that piece in the pocket (3% of
the budget). The difference is the piece's value on our board.

**Weights.** A line's weight says how likely the partner board is to follow
it:

```
adjusted = line score + 0.5 * (value on our board of the mover's team's
                               arrivals, minus the other team's)
weight   = exp((adjusted - best adjusted) / 250 cp), scaled to sum to 1
```

So a line 250 cp worse than the best gets about 37% of the best line's
weight. The second term says that players capture partly for what the piece
does on the other board.

**Worlds.** Lines with the same package are added together, and 85% of that
weight is believed (`HBForecastTrust`); forecasts are wrong often enough that
the rest goes to "nothing arrives". Packages under 4% are dropped, the three
likeliest are kept, and "nothing arrives" gets what is left.

An example with made-up numbers. The partner-board search gives:

| Line starts with | Package | Weight |
|---|---|---|
| our partner takes a knight | `+N` | 0.60 |
| a quiet move | none | 0.30 |
| our partner takes a pawn | `+P` | 0.10 |

Then the worlds are `+N` with 0.60 × 0.85 = 51%, `+P` with 8.5%, and "nothing
arrives" with 40.5%.

The temperature, the trust and the price weight were fitted by log loss
against what actually arrived on the next turn in logged games (PLAN.md,
revision 9). The engine prints the forecast as `info string hb_forecast`.

## 3. Chance inside the search

*Arrivals in the first plies of our own search. Since v5; switch `HBChance`;
`hb_chance.cpp` and `chance_pass()` in `search.cpp`.*

The worlds put pieces in hand only at the start. Most losses to HiveMind were
drop mates with a piece that arrived a move or two later, and by the move
before the mate there was often no escape. So arrivals also have to be
possible inside the search.

**The table.** The forecast becomes a table of probabilities: for us and for
our opponent, for each piece type, the chance that one has arrived by that
side's first turn in the search and by its second. Counting plies from our
move at the root, the first turns are ply 1 (our opponent's reply) and ply 2
(our next move), the second turns plies 3 and 4. With `W01` the weight of forecast lines that capture
that type in partner plies 0 to 1, and `W23` the weight of lines that capture
it only in plies 2 to 3:

| Receiver | By the first turn | By the second turn |
|---|---|---|
| Us | 1% + 99% × min(1, 0.85 × W01) | 3.75% + 96.25% × min(1, 0.95 × W01 + 0.45 × W23) |
| Our opponent | min(1, 0.50 × W01) | 2% + 98% × min(1, 0.90 × W01 + 0.30 × W23) |

The floors (1%, 3.75%, 2%) are for arrivals no forecast line shows. A type
gets one only if such a piece stands on the partner board to be taken. No
probability goes above 95%. The numbers were fitted on 5,130 self-play
decisions (`tests/arrival_rates.py`). The engine prints the table as `info
string hb_chance`.

**The chance node.** At a node within the first four plies after the root
move, with at least two plies of depth left, once the real moves have been
searched, the side to move may also drop a piece it does not hold:

1. Take the piece types with probability of at least 5% that the side has
   none of, likeliest first. (A type it already holds is dropped by the
   normal search.)
2. For each, try drops in this order: checks next to the enemy king, other
   checks, other squares next to the enemy king, and when in check the
   remaining squares that block it. At most 12 squares per type.
3. The drop is played as a virtual piece: the pocket count goes to −1. Each
   side gets at most one virtual piece on a line.
4. The node's value is the mix of the best drop and the best real move:

```
W = p * win(value with the drop) + (1 - p) * win(value of the best real move)
value = the score whose winning chance is W, never below the real-move value
```

Example: it is our turn two plies in, a knight for us has p = 0.5, our best
real move is worth 0 cp (winning chance 0.5) and a knight drop mates
(winning chance 1). Then W = 0.75 and the node is worth about +1100 cp. The
same happens for the opponent one ply in, against us. That is how the search
sees "if they get a knight I am mated, and they probably will" while there is
still a move that avoids it.

A mate with a virtual piece counts as a mate, weighted by `p` as above. The
network keeps evaluating positions with a virtual piece.

**Keeping it affordable.** Before searching a drop, the node works out the
value the drop would need for the mix to change anything. If even a mate
would not be enough, no drop is searched. Otherwise each drop is first tested
against that value with a null window at reduced depth, searched at full
depth only if it passes, and searched for an exact value only on the
principal variation.

**Three details that matter in play.**

- *Checks do not use up the chance plies* (`HBChanceHorizon`). A check and
  its evasion do not count toward the four plies, for at most six plies of a
  line. Otherwise a side could push an arrival beyond the last chance ply
  with spite checks.
- *Separate hash entries.* A value at a chance ply includes arrivals due at
  that ply, so the hash key carries the ply. The same position reached at
  another ply is a different entry.
- *No singular extension where a drop is possible* (`HBChanceStable`). The
  test for that extension has no drop pass, so it called nearly every hash
  move singular and the tree grew: on one position 210k nodes to depth 11
  fell to 57k with the rule.

**Where it applies.** Only in searches on the main thread pool (the main
search and the later searches of our real position), and only when the
forecast ran.

**Known approximations.**

- When the real moves fail low, their value is only an upper bound, and the
  mix uses it as if it were exact. Checking it properly cost 1.4 to 2.6 times
  the nodes for no gain (`docs/REJECTED.md`).
- If a side passes up a chance on its first turn and gets another on its
  second, the second uses the plain table value, which counts the same
  arrival twice. `HBChanceCondition` corrects this and is off: 52–47–1
  against off, inside the noise.
- A virtual piece is dropped at once or not at all; it is not held for a
  later move. `HBChanceHold` allows holding and is off: 49–51.

## 4. Worlds: choosing the move

*Since v4; switch `HBWorlds`; the `WorldsOn` block of `coordinate()` in
`hb_coordinator.cpp`.*

After the main search the seat has a main choice. It then asks whether
another move does better once the arrivals are counted.

1. **Candidates.** The main choice, the next move in the main search's root
   order, and one capture that helps our partner (it lets them mate, gives
   them a block when they are stuck in check, or its piece gains them
   something).
2. **Each arrival world's own best move.** Our board is searched with the
   world's pieces added to the pockets. The root moves are the moves legal
   now: a piece of ours that has not arrived cannot be dropped on this move.
   The best move joins the candidates. These searches use the feed prices
   and have no chance nodes.
3. **Every candidate in every world.** Each arrival world is searched once
   more, restricted to the candidates, so each gets an exact score there. The
   "nothing arrives" world is scored on the main thread pool, which has the
   warm hash table and whatever budget is left. That search keeps its chance
   nodes: "nothing arrives" means nothing has arrived yet, and later arrivals
   are still weighed inside it.
4. **Expected winning chance.** For a move `m`:

```
E(m) = P(nothing) * win(score of m with nothing arriving)
     + sum over arrival worlds of P(world) * win(score of m in that world)
```

   In the "nothing arrives" term no move may score above the main choice,
   because the main search ranked the moves there at a greater depth than
   this comparison.
5. **Switch only with a margin.** `E` is turned back into a score, and
   another move replaces the main choice only if it leads by 25 cp. A move
   more exposed to a fed mate than the main choice (next section) is not
   eligible.

Chance nodes and worlds are used together, and that is measured. The chance
search without the worlds scored 14–26 against v4. With both it scored
67–31–2 against v4 on held-out openings.

## 5. Team rules on the chosen move

These checks play out concrete moves on both boards under the referee's
rules. The engine has an exact port of the arena referee, including its rule
that a checkmate does not count while the mated side's partner can still
supply a blocking piece.

**Verified wins.** If a legal move ends the game for our team under the
referee's rules, it is played. A *delivery win* is also played: a capture of
ours that gives our partner, who is on turn, a mating drop, when our opponent
cannot win first.

**Exposure tiers** (since v3). For each candidate: after this move, can the
opponents capture a piece and drop it for mate on the other board?

| Tier | Meaning |
|---|---|
| CERTAIN | Our opponent can capture on our board and the diagonal seat, on turn, drops that piece with mate (or our partner is on turn there, in check, and the drop mates after every reply). Or the diagonal seat, on turn, can capture a piece that our opponent then drops with mate on our board. |
| SOFT | The same capture and drop, but our partner is on turn on the other board and may move out of it first. |
| SAFE | Neither. |

A capture of a piece type the receiver already holds in hand is not counted:
they could drop it without our move, so the move does not create the mate.

A CERTAIN main choice gives way to any safer candidate that is not itself
mated. If every candidate is CERTAIN, the other legal moves are scanned for a
safe one. A SOFT main choice gives way only to a safe move within 600 cp. If
a CERTAIN choice has no safe alternative, or only one more than 600 cp worse,
the seat may sit instead (next section).

## 6. Sitting

A seat on turn may decline to move. Its clock runs, but its board is frozen:
the opponent cannot capture there, so the diagonal seat receives nothing
new. Sitting is a race. If we sit and the diagonal seat sits too, both clocks
run and the lower one loses on time. So each rule below is tied to the
clocks, which the arena sends with every move.

To the arena, sitting is `bestmove (pass,pass)` with an optional wake timer
(`info string hb_wake_after_ms=N`). The arena asks the seat again after any
move on the other board, when the time advantage changes sides, or when the
timer fires. It allows one timer per turn, and the rules share it.

| Rule | When | Clock condition |
|---|---|---|
| **Stall** (v3, `HBStall`) | The main choice is CERTAIN to feed a mating drop and no acceptable safe move exists. | At least 8 s on our clock and 0.5 s more than the diagonal seat (3 s more if our partner must move first). |
| **Hold when mated** (v7, `HBHoldWhenMated`) | The main search says we are mated whatever we play, and our partner is not lost. | Mate in one: while we lead the diagonal seat, or through one partner move without a lead. Longer mate: only if our partner has a forced mate that our lead covers. Otherwise the seat plays the longest defence and holds at the end. |
| **Hold on a partner mate** (v7, `HBHoldPartnerMate`) | We are not mated, have no mate of our own, and the forecast's best line is a forced mate for our partner in `pm` moves. While we sit, the seat being mated gets no new piece from our board. | Lead of at least 250 ms + (`pm` − 1) × 2500 ms. |
| **Wait for a delivery** | Our partner, on turn, has a capture that hands us a mating drop. It runs the same delivery check and will play it. | 3 s, once per turn, with more than 4 s on our clock. No lead needed. |
| **Wait for a block** | We are in check and every legal partner move is a capture that gives us a blocking piece. | 3 s, once per turn, and our clock stays ahead of the diagonal seat's by more than 4 s. |

A hold or stall continues without a new search while nothing has moved on
either board. A hold ends at any wake where the clock lead no longer covers
it, and after any move the position is searched again.

The first hold-when-mated rule looked only at the length of the mate and lost
14 games on time against HiveMind, which sits when its team is ahead on the
clock. The clock race above (`HBHoldRace`) is the fix.

## 7. Referee draws

*Since v5; switches `HBAvoidDraw`, `HBSeekDraw`.*

The arena draws the game when a board position occurs for the third time,
with the pockets ignored, or after 100 half-moves without progress. The
search counts pockets as part of the position and does not see that
repetition: a lost opponent can repeat the board with a drop-and-capture
cycle. So the root checks it directly, when a position on our board has
already occurred twice or the half-move clock is at 98.

- For every legal move: does it complete a draw, or can a reply by the
  opponent complete one, with the pieces they hold or one their partner can
  capture at once?
- **Not losing** (our board at least −100 cp and the partner board above
  −600 cp): a chosen move that draws or allows a draw is replaced by the best
  move that does neither, found by a root search in budget reserved for it
  (12%), if that move also scores at least −100 cp.
- **Clearly losing** (our board at most −600 cp and no forced mate for our
  partner): a move that draws at once is played.

Verified wins and moves forced by the exposure tiers are left alone.

## Short searches

A `go` under 500 ms or of 200,000 nodes or fewer has no room for the
forecast, so it runs the older rule. Candidates are the main choice, two more
root moves and up to two captures that help our partner. For each candidate
the seat lists the captures the diagonal seat could make at once on the other
board, probes our board with each such piece in our opponent's pocket, and
takes the worst change `R`. The score is

```
S = L + max(R / 2, -400) + F
```

with `L` the candidate's score at a common depth and `F` what its capture
gives our partner (within ±100 cp). Another move replaces the main choice at
20 cp or more. Verified wins, exposure tiers, stalling, waits and the draw
rules still apply. The holds do not: they need the price probes or the
forecast to know how our partner stands. A longer search with
`HBWorlds=false` uses this rule with feed prices in `L` and no `F`.

## What it does not do

- It does not search the two boards together. The partner board gets about a
  tenth of the budget, for prices and the forecast.
- Partners do not talk. Each seat forecasts for itself.
- The forecast reads two plies ahead for the worlds and four for the chance
  table. A piece that arrives later than that is not anticipated.
- The network is the stock Fairy-Stockfish bughouse net. Pieces in hand are
  valued by search, not by a net trained for this.
- It does not manage its own time. `go movetime` and `go nodes` are
  supported; with other limits the main search runs alone.
- The numbers above come from small matches (100 games is about ±9 points)
  on a virtual clock. PLAN.md gives each match and its interval.

## What each version added

| Version | Added | Switch |
|---|---|---|
| v3 | feed prices, exposure tiers, stalling, delivery wins and waits | `HBFeedPrices`, `HBStall` |
| v4 | forecast and worlds | `HBWorlds` |
| v5 | chance inside the search, referee draws | `HBChance`, `HBAvoidDraw`, `HBSeekDraw` |
| v6 | castling earns no feed price | `HBFeedCastleFix` |
| v7 (release v1.1.1) | holds, with the clock race | `HBHoldWhenMated`, `HBHoldPartnerMate` |

## Seeing it think

Each step prints what it found as an `info string` line of JSON:

| Line | Content |
|---|---|
| `hb_prices`, `hb_values` | feed prices, and the unhalved piece values behind them |
| `hb_forecast` | partner-board lines, weights, piece values on our board, worlds |
| `hb_chance`, `hb_chance_stats` | the arrival table; how many drops were tried and how many changed a value |
| `hb_coord` | candidates, tiers, each world's scores, the reason for the final choice |
| `hb_draw` | drawing moves and what the draw policy did |
| `hb_summary` | one line per decision |

## Where it is in the code

All under `engine/src/`.

| File | Part |
|---|---|
| `hb_arena.cpp` | UCI adapter: both boards, the seat options, the order of steps for one `go` (`controller()`) |
| `hb_team_state.cpp` | the two boards with transfers; the port of the referee's mate and draw rules |
| `hb_probe.cpp` | the budget and its phases; the main search runner; the single-threaded worker for all other searches |
| `hb_forecast.cpp` | partner-board lines, weights, worlds |
| `hb_chance.cpp` | the arrival table and the winning-chance mix |
| `search.cpp` | `chance_pass()`: the chance node; the chance ply and hash key in `search()` |
| `position.cpp`, `evaluate.cpp` | the running feed-price total and its place in the evaluation |
| `hb_coordinator.cpp` | feed prices, candidates, worlds, exposure tiers, sitting, draws |
