# Options

`uci` lists the options a user sets and the switches that turn a version's
rules off again. Every other `HB*` option is a fitted value or an experiment
that is off. Those can still be set with `setoption`, but they are listed only
when the engine is started with `HB_EXPERIMENTAL=1` in the environment. The
match scripts and the tests set it, because the arena sends an option only
when the engine lists it.

The defaults are the strongest settings measured. Nothing here needs changing
to play.

## Listed

### What the arena sets

| Option | Default | Meaning |
|---|---|---|
| `HypeBeast` | false | Two-board mode. Without it the binary is plain Fairy-Stockfish. |
| `Seat` | Awhite | The board and colour this process plays. |
| `Team` | white | `white` is White on board A and Black on board B. |
| `Clocks` | (empty) | Four clocks in ms: A white, A black, B white, B black. The sitting rules need them. |
| `TimeAdvantage` | false | Whether the team is ahead on the clock, as the referee counts it. |
| `Coordination` | true | false: each seat plays its own board's search move. |

### Switches back to earlier versions

Each is on. Turning one off removes that version's rule and nothing else.

| Option | Since | Off gives |
|---|---|---|
| `HBFeedPrices` | v3 | captures are not priced by what the piece is worth on the other board |
| `HBStall` | v3 | no sitting to deny a fed mate |
| `HBWorlds` | v4 | no forecast of arrivals, no choice over weighted worlds |
| `HBChance` | v5 | no drops of forecast arrivals inside the search |
| `HBAvoidDraw` | v5 | moves that let the referee's threefold happen are not avoided |
| `HBSeekDraw` | v5 | a clearly lost seat does not take an available draw |
| `HBFeedCastleFix` | v6 | castling is again priced as a rook handed to the partner (a bug) |
| `HBHoldWhenMated` | v7 | a seat that is mated whatever it plays moves into the mate |
| `HBHoldPartnerMate` | v7 | a seat whose partner has a forced mate keeps playing its own board |

To play exactly as an earlier version, also set `HBHoldRace=0` (not listed):
above 0 it makes the older sitting rules, Stall and Wait, respect the arena's
one wake timer per turn as well.

| To play as | Set to false | And |
|---|---|---|
| v6 (release v1.1.0) | `HBHoldWhenMated`, `HBHoldPartnerMate` | `HBHoldRace=0` |
| v5 | those and `HBFeedCastleFix` | `HBHoldRace=0` |
| v4 | those and `HBChance`, `HBAvoidDraw`, `HBSeekDraw` | `HBHoldRace=0` |

The v6 row is checked: with those three settings this build prints the same
search output as the v1.1.0 binary on 232 fixed-node decisions.

## Not listed: fitted values

Set by measurement. Changing one needs a match.

| Option | Default | Meaning |
|---|---|---|
| `HBForecastTemp` | 250 | cp: how sharply better partner-board lines are favoured |
| `HBForecastTrust` | 85 | %: share of a forecast arrival that is believed |
| `HBForecastTrustLate` | 0 | %: the same for captures 3 to 4 plies into a line |
| `HBForecastPrice` | 50 | %: how much of a capture's value on our board counts on the partner board |
| `HBWinScale` | 1000 | cp per logistic unit of winning chances |
| `HBChanceTrustUs0`, `HBChanceTrustUs1`, `HBChanceLateUs1` | 85, 95, 45 | %: arrival trust for pieces coming to us, by turn |
| `HBChanceFloorUs0`, `HBChanceFloorUs1` | 100, 375 | basis points: the least chance given to a type our partner could take |
| `HBChanceTrustThem0`, `HBChanceTrustThem1`, `HBChanceLateThem1` | 50, 90, 30 | %: the same for pieces coming to our opponent |
| `HBChanceFloorThem0`, `HBChanceFloorThem1` | 0, 200 | basis points |
| `HBChanceHorizon` | 1 | 1: a check and its evasion do not advance the chance ply |
| `HBChanceStable` | true | no singular extension where the mover may drop an arrival |
| `HBChancePlies` | 4 | search plies where arrivals can be dropped |
| `HBChanceMinP` | 5 | %: rarer piece types are ignored |
| `HBChanceMaxCands` | 12 | candidate drop squares per type and node |
| `HBChanceMaxPerLine` | 1 | virtual pieces per side on one line |
| `HBHoldRace` | 250 | ms of clock lead a hold needs beyond 2.5 s per partner move. 0 turns the race guard off: holds when mated then sit whatever the clocks say, which lost 14 games on the flag, and the partner-mate hold does not run. |
| `HBHoldFreePlies` | 2 | a mate against us within this many plies is held without a partner mate |

## Not listed: experiments, off

Built and correct as far as tested, but with no measured gain. Not decided.

| Option | Default | What it does | Measured |
|---|---|---|---|
| `HBChanceCondition` | false | after a chance not taken, a later one uses P(arrived, given not before) | 52-47-1 against off |
| `HBChanceHold` | false | an arrival goes to the real pocket: dropped now or held | 49-51 against off |
| `HBFeedEpFix` | false | quiescence prices en passant as a pawn capture | 53-47 against off |
| `HBFeedTieBreak`, `HBFeedTieMargin` | 0, 80 | among near-equal moves, prefer the one that feeds the cheaper piece | no finished match |
| `HBChanceAspiration` | false | root window as wide as the last swing of the value | no finished match |
| `HBChanceTable` | (empty) | debug: inject the arrival table, e.g. `+N=90/90,-Q=0/80` | |

## Removed

Feed pricing by deep probes, `HBChanceVerify`, `HBTreeRepetition` and
`HBCastlePenalty` were measured, found no better or worse, and taken out
after v1.1.0. `docs/REJECTED.md` has what each was, its results and where the
code is.
