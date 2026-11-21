# Writing the notes for one game

You annotate one bughouse game played by the engine HypeBeast, for a public
page on chessautoprep.com where bughouse players come to learn. The page
shows both boards, the moves in the order played, your note on a move, and the
engine's variations for it, which the reader can click through.

Your reader plays bughouse and knows the rules: a captured piece goes to the
partner's hand, a drop is written `N@f3`, you may sit and wait for a piece.
They do not know this engine, its logs or its vocabulary.

## What you read

1. `scripts/collection/README.md`, the section "For the annotator" and
   everything after it: what every fact means, its unit and whose point of
   view it is from.
2. `logs/collection/view/<id>.json`: the whole game as a move list (`game`),
   and each move to annotate (`key_moves`) with both boards before and after
   it, the mover's engine facts and the engine's lines.
3. `logs/collection/notes/<id>.todo.json`: what you fill in.

Read the whole move list first, so you know the story of the game: who was
attacking on which board, where it turned, how it ended. The title and
summary come from that.

## What a good note does

It says why the move was played, in bughouse terms, using the facts:

- **What the move does to the other board.** A capture hands a piece to the
  partner; allowing a capture hands one to the opponent's partner. When the
  facts show this decided the move (the engine's own-board choice was
  replaced, `own_best_exposed_to`, large `fed_cp_mover`, the prices or piece
  values), say which piece, to whom, and what it would do there.
- **What the mover expected to arrive** and whether it came (`forecast`,
  `arrived`), when the move depends on it: a drop of a piece that had just
  arrived, a move that only works with a piece in hand, a wait for a piece.
- **Why a seat sat**, when it did (`waited`, `sat_before`, `sitting_at_end`):
  what it was waiting for or denying, and what the clocks allowed.
- **What the alternative was and what is wrong with it**, pointing at the
  `instead` line. The line's own note says in a sentence what that line
  shows; the move's note carries the reasoning.
- **When the engine was wrong.** If the mover's score fell sharply afterwards
  and a line shows the refutation or a better move, say so plainly and give
  the move a `?` or `??`. A collection that only praises is useless for
  learning. The mated side's last moves are usually forced or lost anyway:
  say that, and do not blame them.

Write as a strong player explaining to a club player: plain sentences,
specific, one idea at a time. Two or three sentences for most notes, and
never more than 500 characters. A line's note is one sentence, or null when
the move's note already covers it.

**Lead with the bughouse idea, then give the evidence for it.** The best
notes in the pilot game read like this: "Its first choice was Q@e2, but the
knight on f4 could take it with Nxe2, sending the queen to Black on board B,
who could then mate with Q@f3. So it played Nxe3+, taking a pawn with check."
The weakest read like the engine's ledger: three cases with a percentage and
two scores each. A reader learns from which piece went where and what it did
there, not from the arithmetic. So:

- At most one score comparison in a note, and only when the size of the gap
  is the point. Often "much better by its count" or "nearly the same" says
  enough.
- Chances in words, and only for the case that mattered: "it thought a pawn
  would probably come", "it gave that about one chance in six". Do not list
  the cases.
- When all the sheet gives you is scores with no reason behind them, say the
  one thing that is known ("the engine preferred it in case a knight
  arrived, and none did") and stop. A short honest note beats a long one
  that recites numbers.
- Follow the pieces. When a piece captured on one board is dropped on the
  other and matters later, say so at the capture and again at the drop: that
  thread is what makes a bughouse game readable.

## What you must not do

- **No chess of your own.** Do not state a variation, a threat, a mate, or a
  judgement of a position that the facts do not contain. Every move you name
  must be a move of this game (anywhere in it, either board), a move of one
  of the annotated move's lines, or a move named in its facts; `check.py`
  rejects anything else. If you want to
  say something and the sheet does not have it, leave it out.
- **Judge a line by its score, not its label.** A second `played` line after
  a sharp fall is labelled as the opponent's refutation, but if its score
  still favours the mover it refutes nothing: say what it shows, or drop it.
  The "fell by" figure in `key` counts every score as at most 20 pawns either
  way, and for a move that replaced the board's own move it starts from the
  score of that other move (`score_is_for`), so part of such a fall is only
  the difference between the two moves. Do not quote the figure.
- **Do not explain what the sheet cannot.** Scores from these short searches
  sometimes jump with no cause in the facts. Say that the engine's score
  changed and leave it there; do not invent a reason.
- **Careful with the board.** You may say what stands where only after
  checking it in the FEN (`fen_before`, `fen_after`, a line's `start`), and
  what is in hand from the bracketed reserve. When unsure, leave it out.
- **No engine vocabulary.** The reader has never heard of "worlds",
  "coordination", "override", "exposure veto", "feed price", "main search",
  "candidates", "probe" or "centipawns". Say what happened instead: "its
  first choice was Q@e2", "it expected a pawn to arrive", "it counts what
  the capture gives the other board". Reason codes and field names never
  appear in a note.
- **Two different alternatives, two different phrases.** The board's own
  move that was replaced (`own_best`, `instead` line of kind (1) in the
  README) is "its first choice": that search already counts what captures
  are worth on the other board, but not what might arrive or the danger of a
  fed mate. The `Coordination=false` line (kind (2)) is "a search that
  ignores the other board": it knows nothing of the partner at all. Kind (3)
  is "a longer search".
- **Numbers sparingly, in pawns.** "About nine pawns down" for 910 cp. Always
  say whose favour. These are the engine's own scores from a short search,
  not truth: write "the engine scored", "by its own count", and never present
  a score as a fact about the position. Scores of the `instead` lines compare
  only with `played_move_same_method`, as the README says.
- **No praise words** ("brilliant", "stunning", "masterful") and no
  commentary filler ("In this position", "It is worth noting", "Interestingly").
  No rhetorical questions. No dashes used as punctuation; write a full
  sentence or use a comma or a colon.
- **Glyphs only with support.** `?`/`??`: the mover's score fell and a line
  shows why. `!`: the move differed from what its own board's search wanted,
  for a reason the facts state, and what followed bore it out. `!?`/`?!`: a
  real choice whose outcome the facts leave open. Most key moves get no
  glyph.
- Plain text only: no markdown, no quotes around moves, SAN exactly as in
  the sheet.

## Bughouse rules the facts take for granted

A seat may sit instead of moving, even when in check: the clock runs but
nothing else happens, and the opponent cannot move on that board. A check
that a dropped piece could block is not mate while the partner might still
supply one. When the facts say one more piece is worth "mate" to a side, a
very short search with that piece in hand found a forced mate: write "by the
engine's count that piece was enough to mate", not that it was certain.

"The mated side" in these instructions means the losing team's moves on
either board near the end: lost by their own count, usually without a better
move. Describe what they tried and what it handed over; give no `?` unless a
line shows a move that would have held.

## Title and summary

The title names what the game shows, at most 60 characters, no "A game of",
no exclamation mark: "A queen held back so the partner could mate". The
summary is one to three sentences on how the game went and what to watch for,
naming the boards ("on board A"). Say who played only if it matters to the
story; the page shows the players.

## Other moves

`extra_notes` is for a move outside the key list that the story needs: the
first capture that starts an attack, a quiet move the game list shows was
replaced (`own_best` in the move list), a wait. Use it a few times at most,
and only for what the move list itself tells you (the full facts for such a
move are in `logs/collection/facts/<id>.json` under that move's `facts`, if
you need them: read just that move with a short script, the file is large).

You may set `drop: true` on a line that adds nothing (a line that only
repeats the game, or one you cannot explain from the facts).

## Finishing

Copy `notes/<id>.todo.json` to `notes/<id>.json` and fill it in. Then, from
`~/Projects/HypeBeast`:

```
HB_COLLECTION_SITE=logs/collection/try/<id> python3 scripts/collection/merge.py <id>
python3 scripts/collection/check.py logs/collection/try/<id>
```

Fix every failure and read every warning (a bare square like "e4" is a
warning only). Do not edit anything but `notes/<id>.json`. Do not run the
engine, the other collection scripts, or anything heavy.

Then read your notes once more as the reader: for each note, could a
bughouse player who has never seen an engine log follow it, and is every
claim in it in the sheet?
