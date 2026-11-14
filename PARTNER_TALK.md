# Partner talk: five ways to use a message between partners, and how to test them

Written by Fable on 2026-11-11 for the user, to be implemented and run by Opus.
Opus: implement exactly what is written here. Where something is not decided here,
stop and write the question at the end of this file instead of choosing.

## Where we are

- Each seat is its own process. The arena shows it both boards and nothing its
  partner thinks. Everything a seat knows about the other board it works out alone:
  a forecast search of that board (about 13% of the go) and, when prices are on,
  eleven probes of it (about 19%).
- The seat that owns a board knows it better. It has searched it with most of its
  budget, it knows what it is about to capture because it chose it, and its world
  searches have scored the move it played with the forecast pieces in the hands.
- A capture is a choice, not weather. A piece our partner can take arrives if our
  team wants it. A piece the opponent can take from our partner arrives if their
  team wants it, unless our partner pays to prevent it.
- The arena side of a channel is written, not yet tested, in
  `~/.local/share/chess-prep/worktrees/hb-partner-tell` (branch
  `codex/hb-partner-tell` of Chess-Auto-Prep): a seat's last
  `info string hb_tell <text>` is sent to its partner before that partner's next
  search as `setoption name HBPartnerTell value <text>` (`none` at the start of a
  game), only to engines that advertise `HBPartnerTell`. The text is recorded as
  `tell` in the game's events. Tests are in `tools/test_bughouse_arena.py`
  (`test_a_seat_hears_what_its_partner_said_before_its_next_search`, class
  `PartnerTalk`). Run them when no match is running, fix what fails, and until that
  branch is integrated run matches with `ARENA=<that worktree>` in front of
  `scripts/run_match.sh`. Integrate by that project's own rules (its AGENTS.md)
  once the first tell match has run without errors.

## The message

One line a decision, printed after the move is chosen, numbers only:

    info string hb_tell v1 n=37 worth +N=420 +B=# +P=150 -Q=# -N=90 plan 1+N 2-B menu +N=40@1 +B=220@1 -Q=300@2 odds +N=30 -B=25

- `n`: plies played on the teller's board, its own move just chosen included (a
  seat that sits counts none). The hearer counts the plies of that board in its own
  position and ignores a message when its count is more than `n + 1`.
- Every section is optional and is printed only by the paradigm that needs it. A
  piece type that is absent is unknown and counts as 0.
- `+T` is a piece of type T in the teller's hand, `-T` one in its opponent's hand.
  Values are centipawns of the teller's board, `#` is a forced mate.
- `worth`: what one T does to the move just chosen. `+T=420`: that move scores 420
  better with a T in my hand than with nothing arriving. `-N=90`: 90 worse with a
  knight in my opponent's hand. `+B=#`: with a bishop I mate. `-Q=#`: with a queen
  they mate me. `#` is printed only when the same move without the piece is not
  already a mate that way.
- `plan`: the captures in the first 4 plies of the teller's main line after its
  move, as the forecast writes them (`<ply><sign><type>`, ply 0 is the opponent's
  reply), but with the sign from the HEARER's side: `1+N`, I intend to take a
  knight on my next move, it comes to you; `0-B`, I expect them to take a bishop
  now, it goes to your opponent.
- `menu`: captures open to the teller's team or to its opponent on this board, with
  what they cost. `+N=40@1`: I can take a knight on my next move (ply 1) and my
  best line that does so scores 40 less than my best line. `-Q=300@2`: they can
  take my queen at ply 2 of my main line, and my best line that keeps it scores
  300 less. Signs from the hearer's side, as in `plan`.
- `odds`: percent chance, by the teller's own forecast of its own board, that a
  piece of that type goes to that hand within 4 plies. Signs from the hearer's side.

For people, the report prints the same table in pawns: `N 4.2  B #  P 1.5 | they get Q: #  N: 0.9`.

## The five paradigms

Each is an option on one binary. With every option at its default the binary must
choose the same move with the same score, reason, node count and depth as
`bin/hypebeast-v8a` on the 12 seat decisions of `coord5.py` (in
`logs/loss-analysis/`; copy it there from the session scratchpad if it is missing).
Build and check each stage before starting the next. One stage, one binary name:
`bin/hypebeast-v8b` (stage 1), `v8c`, and so on.

All options are new. Common to all: `HBTell` (string, default `off`) names the
paradigm the TELLER prints and the HEARER uses; both seats of a team get the same
setting. `HBPartnerTell` (string, default `none`) is what the arena fills in.

### 1. Alarm: only the pieces that mate (`HBTell=alarm`)

*The idea.* "A queen mates me. A bishop mates for me." Nothing else is said. The
partner does not let the fatal piece go and takes the mating one.

*Teller.* In `coordinate()` (hb_coordinator.cpp), at every exit through `finish`,
when the worlds were scored for this go: for the move decided (for a sit: the main
search's move), for every scored arrival world, compare that move's value there
with its value in the "nothing arrives" world. A world mated against us (value
<= -90000 there, > -90000 with nothing) marks every `-T` in its package `#`. A
world mating for us (>= 90000 there, < 90000 with nothing) marks every `+T` in its
package `#`. Print `worth` with those entries only. When the worlds were not run
or not scored, print `hb_tell v1 n=<n>` alone, so an old message does not linger.

*Hearer.* In `prepare_feed_prices`, when `HBTell` is not `off`: run no probes at
all. If the message is fresh: the teller's `-T=#` (a T in its opponent's hand
mates it) is a T that OUR opponent captures on our board, so it sets `theirs[T]` =
`Coef::MatePriceTheirs` (1500), which becomes `FedGain[~ctx.us][T]`. The teller's
`+T=#` is a T that WE capture, so it sets `ours[T]` = `Coef::MatePriceOurs` (800),
which becomes `FedGain[ctx.us][T]`. Everything else is 0. Then the
existing code from `std::ostringstream ps` on, with the hash table kept as
`HBPriceKeepTable=true` does (clear only when a price is non-zero now or was when
the table was written). Skip the `hb_values` line. `HBFeedPrices` is ignored when
`HBTell` is not `off`. With no price set, the search must be node-for-node the
search without prices: check that on the 12 decisions with `HBTell=alarm` and
`HBPartnerTell=none`.

### 2. Worth: the whole table, and how much of it the partner honours (`HBTell=worth`)

*The idea.* "A knight is worth 4.2 to me, a pawn 1.5; a knight for them costs me
0.9." The partner's search adds a share of that to every capture it considers, so
it takes the knight when the knight is worth more to me than taking costs it, and
not otherwise. It does not sell its board: the share and the cap decide how far it
goes, and they are what this stage measures.

*Teller.* As Alarm, and for every other piece in a scored world the difference in
cp (clamped at 0 from below). A type in several worlds takes the world whose
package is that one piece alone if there is one, else the largest difference.

*Hearer.* As Alarm, and for a number: `clamp(value * HBPriceScale / 100, 0,
HBPriceCap)`, the existing two options (50 and 500). `#` as in Alarm.

*Ablation inside the stage.* `HBPriceScale` 25, 50, 100 at `HBPriceCap=500`, and
`HBPriceScale=100,HBPriceCap=250`. `HBPriceScale=0` is Alarm.

### 2b. Table: the whole table the user asked for (`HBTell=table`)

*The idea (the user, 2026-11-11).* "Just report to the partner: our search eval,
our eval after different pieces appear for us, like US: Q +5, N ..., OPP: Q -10,
and our no trades eval." Every piece type for us and for the opponent, not only
the ones the forecast happened to put in a world. Worth says nothing about a piece
that is in no world; Table always says all ten. Its cost is ten small searches a
go, and that cost against that completeness is what the stage measures.

*Message.* `base=<cp>` is added after `n=` in every mode whenever the `worth`
section is printed: the judged move's value with nothing arriving (the "no trades
eval"). The `worth` entries stay differences from it, so the eval with a queen for
us is `base` plus `+Q`. The report prints the absolute values in pawns:
`no trades +1.2 | us: Q +6.2 R +4.0 B +3.1 N +2.9 P +1.9 | opp: Q # R -2.2 ...`.

*Teller.* As Worth, and in the worlds block, after the arrival worlds are scored
and before the "compare" search: for each of the ten (side, type) that has no
scored world whose package is exactly that one piece, one search made exactly as a
world's "score_" search is (the position with that one piece added to that hand,
`searchMoves` and `multiPV` the candidates, phase PROBES, `clear=false`,
`fed=true`, no arrival timing), capped at `HBTableShare` permille of the go (new
option, default 5, 0 to 50) in nodes and in time, tag `table_<sign><type>`. A
search that scores every candidate is kept for the message as a single-piece
world. It is NOT added to `runs`: the move choice, `E` and `S` must not see it.
A type that already has a single-piece world among the scored worlds is not
searched again.

*Hearer.* As Worth (`table` counts as `worth` for hearing numbers).

*Limit.* When the forecast finds no arrival at all, the worlds block does not run
and the line is `hb_tell v1 n=<n>` alone, as in Worth.

*Two-piece packages.* The forecast's own worlds are the pairs that can really
happen (`+N-B`, `+B+N`), and they are already in the message through Worth's
rules. A table of every pair is 45 more searches; not built unless T2 says the
single-piece table earns its cost.

### 3. Plan: what I am about to take, said as a fact (`HBTell=plan`, or `worth+plan`)

*The idea.* "Next move I take a knight for you. I expect them to take a bishop."
The hearer stops guessing its partner's choice: the plan becomes a world with a
fixed belief and the plies of the plan as its timing.

*Teller.* After the move is chosen, read the first 4 plies of the main search's PV
after that move (the PV from ply 1 on when the move is the PV's first move; when
the move was switched, print no plan). Print the captures as `plan`.

*Hearer.* In `weigh()` (hb_forecast.cpp): when a fresh plan with at least one
capture is present and the partner board's moves since `n` are the plan's first
moves (0 or 1 of them), add one more line, source `"plan"`, with the plan's
remaining captures at their remaining plies, and give it the weight
`HBPlanTrust / 100` (new option, default 70) of the whole, scaling the forecast's
own lines down to share the rest. Nothing else changes: the same worlds code turns
lines into packages, and `HBArrivalTiming` times them.

*Ablation inside the stage.* `HBPlanTrust` 50, 70, 90.

### 4. Odds: the partner's own forecast instead of mine (`HBTell=odds`)

*The idea.* "30% a knight for you, 25% a bishop for them", from the seat that owns
the board. The same numbers as today, from the better source, and the hearer keeps
the 13% of its go that its own forecast cost.

*Teller.* After the move is chosen, run today's forecast code (`make_forecast`'s
two searches, same shares of the go) on its OWN board with its opponent to move,
and print each world of the result except "nothing arrives" as
`odds <package>=<percent>@<ply of the first capture>`, package written as a world
key is (`+N-B`), signs from the hearer's side.

*Hearer.* When a fresh `odds` section is present, `make_forecast` runs no search of
the partner board: its worlds are the message's, with those probabilities and
plies. The price probes of its own board for the pieces named still run. When no
fresh message is present it forecasts as today.

*Note.* The teller's forecast is one ply older than the hearer's own would be. That
is the cost this stage measures against the saved budget.

### 5. Menu: "I can get you a knight for 0.4" (`HBTell=menu`, needs `worth`)

*The idea.* The partner lists what it can take and what each costs its board, and
what the opponent can take and what preventing it costs. The hearer believes a
piece is coming when its team would want it: when what the piece is worth here
(from its own world search) times the share is more than what it costs there. For
the opponent's captures the same from their side: likely when it hurts us a lot
and costs them little.

*Teller.* The menu is made before the move, from the current position, where the
teller is on turn and its captures are root moves: a root-restricted MultiPV
search of every capture among its
legal moves (at most 6, by captured value), 3% of the go, as
`forecast_captures` does. Cost = main search's score - that capture's score,
clamped at 0. Print `+T=<cost>@1`, the cheapest capture of each type. For the
opponent's captures: the first capture of each type by the opponent in the main
PV (`-T=0@<ply>`: it is in my best line, keeping the piece costs nothing known),
no further search.

*Hearer.* In `weigh()`: a world whose package is one `+T` on the menu gets, instead
of its forecast weight, `HBMenuYes / 100` (new option, default 80) when the
hearer's last known worth of `+T` (its own previous go's world value for the main
move, kept in a static) times `HBPriceScale / 100` exceeds the menu cost, and
`HBMenuNo / 100` (default 5) when it does not. Other worlds keep their forecast
weights, then all are scaled to sum to at most 1.

### 6. Minimal Talk: the partner's own lines instead of my search of its board (`HBTell=minimal`)

*The idea (the user, 2026-11-11 14:05).* "Remove the redundant search, and include
the info from the main search. Don't run extra searches. Just collect data about
captures as we progress through our searches. Plan, odds, can't happen." A seat
spends about 13% of every go guessing its partner's board: 7% on its best lines,
3% on captures outside them, 3% on prices that weigh those guesses. The partner has
searched that board with most of its own go. It says what it found, the hearer
uses that and searches nothing there, and the 13% goes to the hearer's own main
search. Built by Fable as `bin/hypebeast-v8c`; this section is the record.

*Message.* Added to the line, for the move decided (for a sit: the main search's move):

    hb_tell v1 n=33 at=32 d=14 score=577 mate=0 hands=NP/NP lines 4:h4e7,d8e7,N@d5,e7e8 3:h4e7,d8e7,d3e4,e7e4

- `lines`: the best line of each of the main search's last four completed
  iterations that begins with that move, the deepest counting 4 and the fourth 1,
  equal lines added together, each cut to `HBForecastScan` + 2 moves. The search
  that deepens the main one (`extension`) is used when it ran and went as deep.
  When the move came from somewhere else (a world's move), the one line the
  comparison search has for it. No search is made for the message.
- `at`: plies played on the teller's board before the lines' first move. `d`,
  `score`, `mate` (plies, + the teller mates): the first line's, from the teller's
  side. `hands`: both hands on its board when it searched, White's then Black's.
- That is Plan (the first line), Odds (how many of the last iterations agree on a
  capture) and "can't happen" (a piece in no line gets no world) in one section.

*Hearer.* In `make_forecast`, before anything is searched: the message is used
(`"talk":"told"` in `hb_forecast`) when
1. the hands on the partner board are the told hands less the pieces dropped there
   since (a capture on our own board since changes them: `own_hands`), and
2. the moves played there since `at` are the first moves of at least one told
   line (`own_reply` when of none).
Each line that fits becomes a forecast line from the current position with the
weight it was told with; the others are dropped. `weigh` then makes worlds as
before (`HBForecastTrust`, `HBForecastTrustLate`, `HBMaxWorlds`), without the
softmax and without prices. `teamMate` and the "partner is lost" test read the
told score and mate. When the message cannot be used (`own_none`, `own_no_lines`,
`own_stale`, `own_hands`, `own_reply`) the seat forecasts by its own search, as
without talk.

*Checks.* `logs/loss-analysis/coord7.py` (the same decisions as v8b with `HBTell`
off, and with `minimal` and nothing heard) and `coord8.py` (what the partner makes
of a message 0, 1 and 2 plies old, after another reply, and after a capture on its
own board). The post-mortem has a section "Minimal Talk: was the partner's message
used?".

*Match.* `ARENA=~/.local/share/chess-prep/worktrees/hb-partner-tell scripts/run_match.sh
minimal-vs-l50 "L50c,HBTell=minimal,name=hb-minimal" "L50c,name=hb-l50" 50 6`, with
`L50c` = `L50b` on `bin/hypebeast-v8c`.

*Result (14:30).* Stopped at 15 games, 4-11: narrower and surer than the seat's own
search, and surprised twice as often (`EXPERIMENTS.md`, T7). Kept in the code, off.

### 7. Plan, on top of the seat's own search (`HBTell=plan`, `bin/hypebeast-v8d`)

*The idea (the user, 14:40).* "We should be searching broadly for what can arrive
and narrowly for what is my best move." The seat keeps its own search of the
partner board, all of it. The partner's message (the same `lines` section as
Minimal Talk) adds one line: the first told line that still fits, by the checks of
section 6, with `HBPlanTrust` percent of the weight (new option, default 60: the
told line's next move was the one played in 62% of 654 decisions, the first line of
the seat's own search in 46%). The seat's own lines share the rest by their scores
as before. Mates and the "partner is lost" test stay the own search's. Nothing is
saved and nothing extra is searched: the only change is one better-informed line.
`hb_forecast` says `"talk":"plan"`, or `"own_<why>"` when the message was refused.

## What to measure before any code (Opus, from logs that exist)

- **Missed supplies.** With `postmortem.jsonl` of `late50-vs-np-b`,
  `late50-vs-late25` and `worlds5-vs-l50`: decisions where a scored world with a
  single `+T` had the move played at >= 90000 (it mates with that piece) and the
  position without it did not; of those, how often the partner had a legal capture
  of a T at its next decision (replay the game to that point), whether it made it,
  and the game's result. This is the most the "for me" half of Alarm and Worth
  can win.
- **`HBForecastPrice`** (exists: how much a capture's value on our board moves its
  forecast weight, default 50): matches at 0 and at 150 against the candidate. No
  build. It says whether "a capture is likelier when it helps their team" is worth
  anything, which is paradigm 5's second half, before paradigm 5 is built.

## The ablation plan

Baseline `C` = the candidate when the stage starts (today `L50a`, with
`HBArrivalTiming=2` added if F12 won). Every match: 100 games, `dev100.txt`, 6 games
at once, against `C`, then `scripts/postmortem.py`. A stage's best setting gets a
second 100 games on `openings/dev100b.txt` before it is believed.

| step | match | contender | reads |
|---|---|---|---|
| T1 | `alarm-vs-c` | `C,HBTell=alarm` | collapses and fatal queens against F13's (the same warning by probes) |
| T2a-d | `worth25/50/100/100cap250-vs-c` | `C,HBTell=worth,HBPriceScale=..` | score against T1; sell-outs (below) |
| T2e | `table-vs-c` | `C,HBTell=table` at T2's best share and cap | against the same share with `worth`: does saying all ten pieces pay for ten searches? Node counts of the main search in both |
| T3 | `plan-vs-c`, then the best of T1/T2 with `+plan` | `C,HBTell=plan` | world calibration: do plan worlds come true at their stated 70%? |
| T4 | `odds-vs-c` | `C,HBTell=odds` | Brier score of the worlds against the hearer's own in the baseline |
| T5 | `menu-vs-best` | best so far with `+menu` | missed supplies, sell-outs |
| T6 | the winners together against `C`, both opening sets | | score |

Add to `scripts/postmortem.py`, as each stage needs them:

- **Sell-outs:** the log does not say which move the search would have chosen
  without prices. So compare two groups of captures: those made while the partner's
  `worth` entry for that piece was non-zero, and those made with no price. For
  each, the capturing seat's own score at its next decision minus its score now. A
  partner that sells its board shows a larger drop in the first group.
- **Told and happened:** for `worth` entries marked `#`, whether that piece reached
  that hand before the teller's next move, by engine. Alarm should make `-T=#`
  arrivals rarer than in the baseline, and `+T=#` arrivals commoner.
- **Missed supplies**, as measured above, by engine.

Judging: a paradigm is kept when it scores above 50% on both opening sets and its
table moves the way its idea says. One that moves its table but not the score
(F6 did: 12 collapses against 29, 51-49) is paying somewhere else; say where the
post-mortem shows it before dropping it.

## Ideas not yet specified (the user, 2026-11-11 12:20)

Not for Opus to build yet. Each needs a spec from Fable first.

**Play for the team's result, not the board's.** Today a seat weighs its moves by
its own board's winning chance and never looks at its partner's score. The user:
"ideally we would have our partner's score and our score considered, to try to
maximize the combined score." The message already carries what is needed: `base`
is the partner's own eval of its board, measured by the seat that searched it.

- *Team winning chance.* In the coordinator's `E`, replace the winning chance of
  our board alone by one of both boards: the partner's `base` enters beside our
  value in each world. `AUTOPSY.md` found the partner's score predicts the result
  as well as the seat's own (log loss 0.651 each, 0.636 together) and suggested
  the same (its item 5).
- *Sell out for the partner's mate.* "If the partner has mate, sell out for the
  partner's mate as long as we don't get mated." When the partner's `base` is a
  forced mate for it, or `+T=#` and we can supply the T, our only job is not to be
  mated first and to send what it needs: a material loss here costs nothing. Parts
  exist (`HBHold` sits while the partner mates, `delivery_win` plays a capture that
  mates there); what is missing is choosing among ordinary moves by "am I mated
  before the partner's mate lands", using the partner's told mate distance.
- *Two boards a little ahead, or one board far ahead?* "One board at +3 and one at
  0.00, against two boards at +1.5: I'm not sure which is better." Which is the
  right way to combine two scores is a question the logs can answer before any
  code: for every pair of decisions of one team close in time, the game's result
  against (a) the sum of the two scores, (b) the smaller, (c) the larger, (d) both
  separately. If the smaller predicts best, the team is as strong as its weaker
  board and a seat should give up some of its lead to help a struggling partner;
  if the sum does, +3 and 0 is as good as +1.5 twice. Bughouse reasons to expect
  the weaker board to matter: a game ends when either king is mated, and a lost
  board feeds the pieces that mate the other one.

**Measured 12:40** (`logs/loss-analysis/team/combine.md`): the team's result follows
the sum of the two scores (log loss 0.539 against 0.596 for the seat's own score and
0.603 for the smaller of the two); the weaker and the stronger board weigh the same.
(+600, 0) wins more than (+300, +300), 70.8% against 59.0% with all engines pooled;
(+300, 0) and (+150, +150) cannot be told apart. So: maximise the combined score,
and a lead on one board is worth as much as the same lead split in two, or a little
more. The spec to write next is the team winning chance: `E` from our value in each
world plus the partner's `base`, at about 1130 cp per unit.

**The user, 12:45: not the sum either. "Find how the 2 board eval correlates to win
rate, whatever that line is, maximize that ... 0.00 and +6 is better than two +3,
but -1 and +7 might not be. Find the shape of the curve, then we can have engines
try to optimize that."** An Opus agent is fitting the whole surface, win rate against
(own score, partner's score), from about 800 games of engines whose scores carry no
prices: raw cells, simple formulas against a shape-free fit under cross-validation by
game, the lopsided-against-equal curves at fixed totals, and a lookup grid the
engine can embed (`logs/loss-analysis/surface/`: SURFACE.md, surface.json,
surface.png). The engine spec follows the fitted surface, not the sum.

**Measure first (Opus may, from `postmortem.jsonl` of the finished matches):** the
table just described, resampled by game, for the candidate's seats: predicted
result under (a) to (d) at the best scale for each, and the log loss of each.

## What the 13:40 conversation changed (the user and Fable; not yet a spec)

**Why the table lost at half share (measured on the 24 games, 13:30).** The values
told are mostly the ordinary worth of a piece in hand: medians +Q 729, +R 449,
+B 348, +N 356, +P 168; -Q 758 with `#` in 16%, -R 481, -N 392, -P 207. The hearer
added half of each to every capture, so all material on its board was worth about
half as much again and its scores carried about 551 cp of prices. The user's first
description already had the fix: "P: 1.5, good, because normally a pawn would be
1": only the difference from the usual worth is news. The values are also unstable:
from one tell to the same seat's next, the median change is 151 (+N) to 200 (-Q),
and `-Q=#` appears or disappears in 10.5% of consecutive tells. Each comes from
0.5% of the go (about 2,500 nodes) set against the main search, and negative
differences are cut to 0, so noise only pushes the values up. The table searches'
depth is not logged: log it.

**Arrivals are not chance (the user: "the pieces we receive are not random at all
... it should be related to the partner's board").** What my opponent can receive
is what my partner can lose. Per piece type, three cases:
1. It cannot happen: the partner has none on the board, or none can be taken within
   the horizon. Exact and nearly free. Then lines that only a queen punishes are
   allowed ("if a queen is not coming, it is ok to allow Nxf2, Kxf2, N@e4").
2. The partner decides (it can decline the trade; the Bg5 against Nf6 case): a
   promise, not a probability. "I keep my queen", "a knight when you ask".
3. The opponent decides (the piece is being won, the trade can be forced): it is
   coming, and the fact worth sending is when.
A small allowance stays on cases 2 and 3 for what neither search saw (the user:
"we should still give some probability to pieces the partner doesn't say it plans
to capture"); none on case 1. The message per piece: the earliest ply it can
arrive or never, who controls it, and what holding it costs the holder. A promise
lasts one move and is sent again each move, so a broken promise is said before it
happens. Support from the logs: in 33 of the 41 sudden collapses the fatal capture
was in the partner's own line.

**Whose move it is when the piece lands (the user, 13:40: "stalling until it's our
partner's move ... don't trade queens unless it's our partner's move").** With a
queen mating in one for both sides of board A, the queen trade on board B wins for
the team whose player is on move on A and loses for the other. So a piece's worth
has two values, "lands on my move" and "lands on their move", and the giver has
three choices, not two: take now, take when the partner is on move, never. The
table as built searches only "in my hand, I am to move" and "in their hand, I am
to move": it cannot say that the opponent mates with a queen that lands on the
opponent's move. Test case, written before any build: `tests/tempo_trade_check.py`
(the user's position on A, a defended queen trade on B, the four combinations of
who is to move, both clock leads; reports what each seat on move does with no talk
and with the table heard). Any message design must pass it.

## Questions from Opus

Asked while implementing stages 1 and 2 (2026-11-11). The code does what each
question calls "meanwhile" until it is answered.

1. **`need_main`.** A seat that is waiting for its partner's mate calls
   `coordinate()` twice in one go. The first call ends through `finish` with
   reason `need_main` when it is not going to sit, and the second call makes the
   decision. Printing at both would give two lines for one decision. Meanwhile:
   no line at `need_main`, so there is one line for each decision.
2. **`PricesOn` with no price.** "The existing code from `ps` on" sets
   `PricesOn = true` even when the message sets no price. The main search is still
   node-for-node the same, because every `FedGain` is 0. Two other things change,
   though. (a) On the v3 path (no worlds) `S` leaves out `F` while `PricesOn` is
   set. (b) In `prepare_forecast`, when the partner sits mated, `price_rescues`
   runs its probes and sets `ours` prices. Should the tell path leave `PricesOn`
   off while every price is 0, and should rescues run with `HBTell` on?
   Meanwhile: as written, so `PricesOn` is set and rescues run as they do today.
3. **Mate scores in a number.** A world can lift the move out of a mate. For
   example, nothing arriving is mated (-99990) and with +N the move is +50. The
   difference is then about 100000 cp. Meanwhile: the raw difference is printed,
   and the hearer's `HBPriceCap` clamps it. Should the teller clip it first
   (to +/-2000, as `finite_cp` does)?
4. **`#` against a single-piece world.** Suppose +N is `#` in the world `+N-B`
   and 120 in the world `+N`. Meanwhile: `#` wins, so Worth's `#` entries are
   exactly Alarm's, as "`HBPriceScale=0` is Alarm" requires. The single-piece
   rule only picks among the numbers.
5. **"Scored".** Meanwhile: `worth` is printed only when (a) the nothing-arrives
   world scored every candidate, (b) at least one arrival world was scored, and
   (c) the judged move has a value with nothing arriving. Otherwise the line is
   `hb_tell v1 n=<n>` alone. (c) fails only when draw avoidance in `finish`
   swaps in a move that was not a candidate.
6. **Other `HBTell` values** (`plan`, `odds`, `menu`, and combinations without
   `alarm` or `worth`) are not built yet. Meanwhile: the teller prints
   `hb_tell v1 n=<n>` alone. The hearer runs no probes and uses only the `#`
   entries. Numbers are used only when `HBTell` contains `worth`
   (`+`-separated). Entries are printed in the order + then -, each in the order
   Q R B N P.

### Answers (Fable, 2026-11-11 12:00; the code already has 2 and 3)

1. Right as it is: one line a decision, none at `need_main`.
2. With `HBTell` on and no price set by the message, the go is the go without
   prices in every respect: `PricesOn` stays off, no `hb_prices` line, no rescue
   probes, and the table is cleared only if the last go's prices were non-zero.
   Then a tell build and the baseline play the same game until the first message
   that prices something, and a difference in the result is the message's doing.
   Rescues (`HBRescue`) stay as they are for a seat without `HBTell`.
3. The teller clips a difference at `Coef::FiniteCap` (2000): across a mate score
   it means "decisive", and the report prints it in pawns.
4. Right as it is: `#` wins.
5. Right as it is.
6. Right as it is. Stages 3 to 5 define those values when they are built.

### More questions from Opus (stage 2b, 2026-11-11)

7. **`base` across a mate.** `base=` is the judged move's raw value with nothing
   arriving, so it can be a mate score (for example `base=-99990`). Answer 3 clips
   only the differences. Meanwhile: `base` is printed raw, not clipped. The hearer
   does not read it.
8. **The table's cost reaches the choice.** The table searches run before
   "compare". The compare search absorbs whatever budget is left, so with
   `HBTell=table` it runs with up to 10 x `HBTableShare` permille less of the go.
   That can change its depth, and with it `L`, `E`, `S` and possibly the move.
   This happens even though the table worlds are not in `runs`. Meanwhile: as
   written, the cost is simply spent; nothing is held back for compare. Is that
   the cost the stage means to measure?
9. **Table searches whose result is not printed.** The ten searches run as soon
   as the arrival worlds are scored. If "compare" then fails to score the
   nothing-arrives world, the line is `n` alone and the table is thrown away.
   Meanwhile: as written. The searches are not skipped and not reported anywhere
   else; the `hb_coord` JSON does not list table worlds.

### Answers to 7-9 (Fable, 2026-11-11)

7. Right as it is: `base` raw. A mate score there tells the partner the seat is
   already mated (or mating) with nothing arriving, which is worth knowing.
8. Yes. The table's searches come out of the same go, and what that does to the
   comparison search and so to the move is the cost T2e measures.
9. Right as it is.
