# HypeBeast: implement the new architecture, then measure it

Revision 7 — 2026-11-06. Replaces revision 6 and its phase ordering.

## 1. What to build

Build a CPU bughouse team engine using Fairy-Stockfish's existing search and
published bughouse NNUE. The first complete HypeBeast version must include
partner-board analysis, simulated incoming hands, and team-aware move selection.
Test it against **unmodified Fairy-Stockfish bughouse** and **HiveMind CPU**.

Keep existing NNUE weights, feature definitions, training tools, and datasets
unchanged. No retraining, new piece values, general pruning changes, probability
model, or full two-board search tree in this first implementation. The experiment
is whether the new controller improves team play using the existing evaluation.

Reliable operation is an acceptance requirement. Beating either opponent is an
experimental result, not a promise. Deliver losses and inconclusive results
honestly. Do not stop after building the stock baseline and call that HypeBeast.

## 2. Reuse and pin the components

- Fairy-Stockfish: resolve revision 6's `4e3d014` to a full upstream SHA and record
  it. Build an untouched reference binary and a separate HypeBeast fork with the
  same compiler and architecture flags. Freeze upstream during the experiment.
- NNUE: start with the published `bughouse-cd8cceab93fe.nnue`; verify compatibility
  and active loading. Use identical weight bytes in all FSF-based arms. Record
  filename and SHA-256. No silent classical-eval fallback or crazyhouse-net swap.
- Arena: reuse `~/Projects/Chess-Auto-Prep/tools/bughouse_arena` and
  `tools/test_bughouse_arena.py`: independent referee, virtual clocks, opening
  pairs, JSONL events, and BPGN. Read that repository's AGENTS.md before editing.
- HiveMind: pin the installed CPU binary/model used by the arena, including runtime
  backend. The checkout at `~/Projects/hivemind` may differ from the installed
  binary. Record both identities; do not modify the opponent.
- Keep engine code here and only necessary adapter/timing/reporting changes in
  Chess-Auto-Prep. No changes to the training pipeline.

Correction to revision 6: upstream training-data generation explicitly simulates
incoming pocket pieces for two-board variants. The published net's exact training
run is unverified; do not claim its pocket features were never trained.
`nnueAlias` selects a network; it does not add partner-board inputs.

## 3. Actual state and protocol

Keep the arena's one process per seat. Each HypeBeast process sees both boards;
no background search or shared-memory service is needed.

Add these options in HypeBeast arena mode:

- `HypeBeast` (default false): enables the adapter/controller. With it off, retain
  normal upstream protocols, search, and bench behavior.
- `Coordination` (default true when HypeBeast is enabled): enables the new controller.
- `Seat`: `Awhite`, `Ablack`, `Bwhite`, or `Bblack`.
- Existing `Team` and `TimeAdvantage`, plus `Clocks` in `aW,aB,bW,bB` milliseconds.

Extend the arena to send Seat and Clocks only to engines advertising them. Team
alone does not identify which board to search. Validate that Seat agrees with
Team (`white` means White A / Black B).

Accept the arena's dual FEN or start position followed by interleaved board-prefixed
moves. Replay both boards with correct transfers: a capture feeds the partner's
opposite color; a captured promoted piece becomes a pawn; en passant sends a pawn.
Preserve promotion markers, castling, en passant, counters, and actual history.
Start both actual boards with empty pockets, not pocketknight's extra knights.

Return `bestmove (moveA,moveB)` with the selected seat's move and `pass` in the unused
half. Waiting returns `pass` for the selected seat too. Handle stop/newgame/shutdown
cleanly and emit exactly one answer per go. Waiting is a returned action, never a
sleep inside the engine. Disable pondering and all computation between calls.

The pinned arena referee is authoritative. Port its exact root terminal conditions
and verify against its Python implementation, including its no-legal-moves team
condition, pockets-ignored repetition, and fifty-move rule. These are this arena's
conventions, not universal bughouse rules. If the actual game is nonterminal and
our seat has no legal move, return pass even if a local search calls it mate.

Do not port asynchronous play into every alpha-beta node in v1. Deep local terminal
scores remain approximations. A local mate is conditional; call a team win proven
only after applying the concrete moves/transfers and checking the joint referee.
Never change the referee or the unmodified opponent to favor HypeBeast.

## 4. Local searches and one total budget

Use bughouse movement and existing NNUE mapping, with captures leaving the local
board. In coordinated mode, disable upstream virtual drops of pieces not actually
in hand: explicit scenarios will supply those pieces. Add one search-context gate
covering generation and legality, including quiescence. Preserve physical drops
and upstream virtual-drop bookkeeping for normal mode. Do not replace bughouse
with another variant whose starting position or rules differ.

Use sequential, single-threaded child searches initially. Every child shares the
original go deadline/node budget. Initial allocation: 60% main search, 10% partner
and candidate discovery, 25% comparison probes, 5% response reserve. Unused budget
can flow forward. The absolute deadline and total node count override all slices.
Count controller overhead in timed runs and all child nodes in node-limited runs.
These allocations are initial engineering defaults, not measured optimal values.

Select a deterministic legal fallback before searching. Interrupted or incomplete
comparisons retain the main-search best move (or fallback if no iteration finished).
Never grant a fresh full movetime to each probe. Report aggregate nodes and time.

## 5. The coordination algorithm

### 5.1 Candidate moves

Obtain up to three main-search root candidates. Add up to two legal captures that
supply useful pieces to our partner, for at most five candidates. Test each distinct
available captured type in the partner's pocket using the paired partner probes
below. Prefer a verified immediate mating/blocking delivery, then the largest
measured gain. Break ties by upstream capture ordering and then UCI lexical order.
Promoted captures supply pawns. Include these delivery candidates even when absent
from the local top three; otherwise useful sacrifices can never be discovered.

If discovery expires, retain completed main candidates and log partial coverage.
Extra candidates need a root-restricted main search before numerical comparison.
Use scores at a common completed main-search depth. An extra candidate without
such a score is ineligible for numerical re-ranking.

### 5.2 Simulated hands

V1 examines immediate legal captures on the partner board for its actual side to
move. No invented arrival probabilities or assumed cooperative two-ply trades.
For each candidate on our board:

1. Apply our candidate and its outgoing transfer to a fresh joint-state copy.
2. Enumerate immediate captures on the resulting partner board.
3. Each donor capture creates one scenario: update that donor board and add the
   captured piece to the correct receiving pocket. Preserve the receiver's turn.
4. Probe our resulting local board. Always include a no-arrival scenario.

The modeled ordering is our move, then one donor capture, then the opponent's
local reply. This is a vulnerability stress test, not a claim that every local ply
corresponds to one partner ply. The no-arrival case represents waiting or choosing
another move. Deduplicate identical hand additions for local probes, retaining
donor provenance for verification. Never combine mutually exclusive captures into
one hand, count the same piece twice, or forget promoted-piece demotion.

Optional friendly arrivals supply no guaranteed numerical upside. Enemy arrivals
can expose vulnerabilities. Friendly scenarios inform waiting and diagnostics.
Multiple successive arrivals and two-ply forecasts are deferred.

### 5.3 Probe contract and selection rule

Start with three local plies after our candidate, plus normal quiescence. This
covers their reply, our possible drop, and a response to that drop. Compare each
scenario with a no-arrival probe at the same completed depth and resource cap.
Partner probes likewise compare the same board/turn with and without the delivered
piece at equal depth. Require completed exact root scores; interrupted searches
and fail-high/fail-low bounds are not exact values.

Normalize every score to our team's perspective, including board B. Convert
upstream internal values consistently to UCI centipawns. Let `finite(x)` clip to
[-2000, 2000], mapping local mate reports to the corresponding endpoint. These
are heuristic scores, not calibrated win probabilities or proven team mates.

For each candidate m:

```
L(m) = finite(main local-search score)
P0(m) = finite(no-arrival local probe after m)
Pe(m) = finite(local probe after enemy arrival e)
R(m) = min(0, min_e(Pe(m) - P0(m)))   # zero if no enemy scenarios
F(m) = finite(partner probe with m's outgoing delivery)
       - finite(partner probe without that delivery)
       # zero for a non-capture
S(m) = L(m) + clamp(R(m), -150, 0) + clamp(F(m), -100, 100)
```

Use shallow probe differences to adjust deep scores, not shallow absolute scores
to replace them. The caps prevent an uncertain scenario from buying an arbitrary
sacrifice. Friendly hypothetical arrivals do not add speculative upside to S.

Replace the main choice only if another candidate exceeds its S by at least 20 cp.
Ties retain the main choice, then use UCI order. A verified immediate team win can
override numerical ranking, but a local mate score alone cannot. For such a proof,
apply the candidate and check the actual joint referee immediately; do not assume
an unplayed future partner move happens before an opponent response.

Use deterministic round-robin scheduling across candidates and scenarios. If the
eligible comparison set lacks any required completed probe, keep the main choice
for that decision. Log coverage and fallback. Freeze coefficients for the first
matches; do not quietly tune on the reported test games.

This is intentionally limited: later opponent captures feeding their partner,
longer transfer chains, and mating races can defeat it. Preserve such losses for
the next iteration rather than claiming v1 implements complete joint search.

### 5.4 Waiting

Mandatory waiting: return pass when our seat has no legal move and the actual joint
state is nonterminal. Do not incorrectly require TimeAdvantage for this case.

Voluntary waiting is restricted in v1. Require all of:

- Partner is on turn and EVERY legal partner move captures a piece that enables
  the needed legal local block or an immediate winning drop. Enumerate the moves;
  a good PV is not proof of a forced delivery. Verify the resulting joint states.
- No currently legal local move already wins the actual game immediately.
- Partner does not lose in the proposed continuation; a bounded tactical safety
  check finds no immediate opposing team win. Incomplete checks disallow sitting.
- Full clocks are supplied and TimeAdvantage is true. Our clock exceeds a 3000 ms
  wait plus 1000 ms reserve, and exceeds the opposing seat's clock on the partner
  board by that same 4000 ms margin. This is a conservative policy, not an exact
  solution to four-clock timing.

Allow at most one voluntary 3000 ms wait per own-board turn. Add an opt-in output
`info string hb_wake_after_ms=3000`; the seat adapter exposes it as a virtual wake
deadline. The arena wakes at the earliest of that deadline, its existing reaction
event, or an advantage flip. Keep the original expiry through intervening wakes;
do not renew indefinitely. At expiry play the legal fallback if one exists.
Mandatory waiting can continue if no legal move exists. No real-time sleep and no
new waiting policy for FSF or HiveMind. Test the timer with no other-board events.

## 6. Isolation and safeguards

- Hypothetical material never enters authoritative game state. Each probe owns
  valid Position/StateInfo storage; never shallow-copy pointer-linked state.
- Rebuilding probes from validated FEN is acceptable. Its missing pre-root
  repetition history is an explicit approximation used consistently for paired
  probes. Actual referee history remains intact outside those probes.
- Refresh NNUE state after pocket changes. Compare incremental and fresh evaluation
  through drops, captures, promotions, and undo. Check keys and pockets restore.
- Initially clear TT and search heuristics between distinct child searches. A
  sequential reusable worker is sufficient. Include clearing overhead in budgets.
  Do not share bounds between different hands, contexts, or modes.
- Never store combined S scores in the alpha-beta TT; they are root heuristics.
- Fixed-node determinism requires identical build/net/options, full game and wait
  state, and clean search state. Timed search is not necessarily reproduced by
  replaying the observed node count. Log each child request/result for diagnosis.
- Retain upstream bench behavior with HypeBeast off. Also test bughouse positions;
  a standard chess bench alone does not verify variant-specific hooks.

## 7. Required opponents and controls

### A. Unmodified Fairy-Stockfish bughouse

Build the untouched upstream source. Use UCI_Variant=bughouse, the pinned bughouse
NNUE, normal virtual drops, and upstream search/evaluation without HypeBeast patches.

Add a plain-FSF arena Player that launches its normal UCI binary without HiveMind's
--model argument. Send the seat's actual FEN including transferred pockets and
counters via normal `position fen`, then `go`. Parse ordinary `bestmove`, not a
joint response. If the referee says play continues but the seat has no legal move,
return a sit as necessary protocol plumbing. Unexpected null/illegal output with
legal moves available is a failure, not an invitation to invent a replacement.

Label it **unmodified FSF bughouse via UCI snapshot adapter**. It receives actual
hands but no pre-root repetition history or CECP partner messages. Disclose these
limitations; this is not a measurement of every native CECP team-play feature.
Do not change the binary or add a custom advisor to strengthen/weaken this control.
A native CECP comparison can be a later experiment.

### B. HypeBeast coordination off

Same HypeBeast binary, net, actual-state handling, and frozen-hand local search,
but Coordination=false: no partner analysis, simulated hands, delivery re-ranking,
or voluntary waiting. Give the main search the full budget. This ablation tests
whether coordination earns its computation; a win against A alone cannot show that.

### C. HiveMind CPU

Use the installed arena opponent and model unchanged. Preserve its existing
ponder/permanent-brain disabling and stop-after-bestmove compatibility behavior.
Use concurrency 1 initially to avoid CPU backend oversubscription.

Generalize engine specs to explicit fsf/hypebeast/hivemind player kinds while
preserving existing CLI compatibility. Model/runtime-library arguments apply only
to engines needing them. Record all binary/model/net hashes and settings.

## 8. Verification and matches

Before measured games, automate real-binary checks for:

- Default upstream bench and bughouse fixed-node agreement with HypeBeast off;
  active NNUE loading and identical static NNUE scores on identical real positions.
- Both-board replay against the referee: all seats, promotions, en passant,
  transfers, drops, counters, and repetition. Randomized make/undo restoration.
- Root terminal/wait fixtures: blockable/unblockable/double checks, pawn blocks on
  back ranks, no moves on both boards, clock advantage changes, and draw cases.
- Delivery outside the local top three; enemy arrival threats; unavailable friendly
  supply; exclusive donor outcomes; correct score perspective and unchanged turn.
- Probes leave actual state untouched; cancellation, stale output, budget exhaustion,
  incomplete scores, and fixed-node determinism. Always return a legal fallback.
- Voluntary wait expiry, repeated wakeups, missing supply, low clocks, and mandatory
  waiting. An ordinary upstream-versus-upstream adapter symmetry smoke test.

Use the existing virtual timing initially: 120 s per seat, seeded 1.5–2.5 s move
cost, 0.5 s reaction cost. Same timing for every arm. Virtual-clock results are
separate from real-time latency claims.

Preflight HiveMind on fixed representative positions at its existing 400-node
budget. If movetime is reliably honored, use the same movetime for all arms.
Otherwise pin that HiveMind node budget and give FSF/HypeBeast its measured mean
preflight latency as TOTAL movetime. Label this matched mean compute, and report
median/p95/total latency and overruns. Do not infer the budget from old NPS figures.
Record hardware, cores, thread counts, hash, backend, and warmup. NPS across these
architectures is not a direct playing-strength comparison.

Use held-out legal openings with real pockets from existing games where available.
Each opening plays twice with teams swapped and matching seeded move costs.
Balance board roles across the set. Pin the opening file/hash before testing;
keep debug/tuning positions separate. Each engine controls both seats of its team.

Run all three comparisons with one frozen HypeBeast configuration:

| Match | Contender | Opponent | Question |
|---|---|---|---|
| 1 | HypeBeast coordination on | Unmodified FSF bughouse (A) | Does it beat upstream? |
| 2 | HypeBeast coordination on | HiveMind CPU (C) | Does it beat the target? |
| 3 | HypeBeast coordination on | HypeBeast coordination off (B) | Does coordination help? |

Start with 20 opening pairs per match for screening. After correctness fixes,
freeze again and run a fresh held-out 200 pairs per match for the first strength
report. Complete the declared sample; never stop when results look favorable.
An inconclusive result remains inconclusive. Declare any additional sample before
running it. Test HiveMind GPU separately if a working installation is available;
missing GPU access does not block the required CPU comparisons or count as passed.

Disable the arena's current SPRT stopping rule: although it records pentanomial
counts, its stopping calculation uses total points rather than their distribution.
For these fixed-size runs report W/D/L, score, paired outcome distribution, and a
95% interval treating opening pairs as the sampling unit. Use a tested pair-aware
interval with sensible boundary behavior: identical/all-winning pair scores must
not imply zero uncertainty. Elo is secondary; do not print finite Elo at 0%/100%.

Crashes, timeouts, and illegal moves invalidate a reliability claim. Report them;
do not silently drop those games and promote the remaining score. Preserve old
runs, fix the cause, and start a new frozen run. Infrastructure-error replays need
a documented cause and policy.

Retain JSONL, protocol logs, BPGN, manifests, and representative losses. Report
flags, waiting time, overrides, completed-probe fraction, fallback rate, search
and probe depths, aggregate nodes/latency, and realized versus simulated transfers.
If comparisons seldom finish, say the new architecture was mostly bypassed.

## 9. Implementation order and deliverables for Opus

1. Pin sources/net/opponents; build unchanged FSF and the fork. Add player kinds,
   Seat/Clocks, and baseline smoke tests.
2. Implement joint replay, root rules, frozen-hand search context, isolated child
   state, aggregate budgets, and fallback.
3. Implement candidate discovery, incoming scenarios, the specified probe/score
   rule, and bounded waiting. This is required for the first complete build.
4. Finish fixtures and smoke games, then run all three comparison matches and
   deliver results even if they are negative.

Suggested modules: arena, team_state, coordinator, probe, decisionlog. Combine
files where clearer. Keep upstream hooks narrow without promising they are only
a few lines. Follow each repository's integration/test requirements.

Deliver exact build/match commands, commits, binary/net/model hashes, configuration,
checks, match artifacts, and a concise strength/reliability report with limitations.
Do not describe this plan edit as an implementation or completed match.

Deferred: retraining, partner NNUE inputs, probabilistic arrival trees, longer
forecasts, deep transfer eval terms, general search tuning, custom piece values,
a new mate solver, and native CECP team benchmarking. Select later work from
observed losses rather than a mandatory training phase.

## Sources and entry points

- https://github.com/fairy-stockfish/Fairy-Stockfish
- https://fairy-stockfish.github.io/nnue/
- https://github.com/fairy-stockfish/variant-nnue-tools/blob/master/src/tools/training_data_generator.cpp
- https://github.com/aminwoo/hivemind
- https://github.com/fairy-stockfish/fairyfishtest
- ~/Projects/Chess-Auto-Prep/tools/bughouse_arena/{players,sim,referee,match,stats}.py
- ~/Projects/Chess-Auto-Prep/tools/test_bughouse_arena.py

Verify interfaces against the pinned sources; revision 6's line numbers are not
a compatibility contract. This document is the implementation scope.
