## Data and definitions

- Match: `logs/plan-vs-l50`, 100 games, `hb-plan` (contender) against `hb-l50` (baseline), both `bin/hypebeast-v8d` at
  500,000 nodes a move; hb-plan adds its partner's told main line to its forecast (`HBTell=plan`, `HBPlanTrust=60`).
  Both engines play every game (one team each), so the two sides' lost games are disjoint and their sum is the
  number of decisive games.
- Rows: one per decision, from `scripts/postmortem.py`'s `collect()` (the same matching of engine logs to games),
  plus the clocks, the full main line, the told line of `hb_forecast` and the values of every candidate in every
  coordinator world (`hb_coord`), and features of the position replayed with python-chess (`common2.py`).
- Definitions are AUTOPSY.md's, unchanged, so the counts can be set side by side:
  - **Mated seat S**: the losing seat on the board that decided the game (the flagged seat for a flag); **partner P**.
  - **Lost for good** at a decision: the seat's main score is below -300 there and at every later decision of that
    seat. A seat mated without ever being below -300 is lost for good at the end of the game.
  - **Its fall**: the step from the seat's last decision at -300 or better (**pre**) to its first lost-for-good
    decision. **Fatal piece**: of the pieces that reached the seat's opponent's hand in that step, the one whose
    world gave the move played the lowest value.
  - **Turning point**: the decision `pre` of whichever seat of the losing team fell first. It is the last
    decision of that team after which the position was not yet lost by its own score.
- **First-cause rules** (`classify2.py`, written before the counts were looked at), in this order:
  1. Events: S's fall, P's fall, the losing team's first forced mate *for* itself (W), the first missed supply (F:
     a single `+T` world mated for us, "none" did not, the partner had a legal capture of a T at its next decision
     before ours and did not take one). The earliest wins; ties S, P, W, F.
  2. A flag while the flagged seat was not yet lost for good: **clock**.
  3. W first: **e** (lost a mating race). F first: **f** (missed supply).
  4. A fall first: the falling seat's `pre` decides the class.
     - **h** (a sit went wrong): `pre` was a sit whose reason is not `hold_mated`.
     - **g** (a switch went wrong): `pre` overrode the main move and, in the coordinator world that matches what
       really arrived on that board before the next decision, the main move scored 300 cp or more above the move
       played, or survived where the move played was mated.
     - otherwise the kind of the fall: **a** sudden mate (straight from -300 or better to a forced mate) after an
       arrival in a world where the move played was already mated; **a2** the same, but the world scored the move
       survivable; **a3** the same, move not scored in that world; **b** sudden mate after an arrival in no world;
       **c2** sudden mate with nothing arriving; **a4** a drop of 400 cp or more (not a mate) after an arrival in
       a world; **b2** the same after an arrival in no world; **c** anything else: a slow loss on its own board.
     - If the falling seat is P, the class is **d** (partner's board lost first), with P's kind as a sub-class.
- **Who could have seen a fall** (`losses_q3.py`, `visibility.py`): *seat's worlds* when at `pre`, or at one of the
  seat's last two decisions no later than the partner's decision that let the piece go, a world with that piece had
  the move played mated while "none" did not (for a non-mate fall: 300 cp or more worse than "none"); otherwise
  *partner's line* when the capture was in the partner's own main line (the deepest full PV of the last two depths)
  at the partner's last decision before it; otherwise *nobody*.
- **Collapse within 3** (evaluation check): within the seat's next three decisions, a forced mate against it, or a
  score at least 600 cp lower that is also below -300.
- Intervals are 95%, from 2000 resamples of whole games (400 for the joint models). "Diff" intervals resample the
  same games for both engines.
