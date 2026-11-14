# Match data

Every version-against-version match played while building HypeBeast, kept so that
someone else (or a later, better tool) can look for what we missed.

- `data/matches.md`: one row per match: who played, with which options, the score.
- `data/matches/<match>/summary.json` and `postmortem.md`: the result and the
  report of each match, small enough to live in the repository.
- The full logs are too large for git. They are the files of the GitHub release
  named `data-<date>` of this repository: one `<match>.tar.zst` per match, and
  `loss-analysis.tar.zst` with the analysis scripts and their outputs. Unpack with
  `tar --zstd -xf <match>.tar.zst`.

Read `docs/ALGORITHM.md` first (what the engine does in one decision), then
`EXPERIMENTS.md` (what each match was for and what came of it; search it for the
match name).

## What is in a match archive

| file | what it is |
|---|---|
| `results.jsonl` | one game per line: the opening, which engine sat where, the result, and `result.events`: every move, sit and wake with its time, the four clocks, the engine's own score (`eval`) and what it told its partner (`tell`) |
| `games.bpgn` | the same games as BPGN |
| `summary.json` | both engines' options and the score |
| `manifest.json` | the exact command, the sha256 of each binary, network and opening file, the arena's version |
| `engine_logs/w<worker>-<contender or baseline>-<A or B>.log` | everything sent to (`>>>`) and received from one engine process: each position, each search line, and the engine's reports of each decision (below) |
| `postmortem.jsonl` | one row per decision, made from the files above by `scripts/postmortem.py`: the score, the move, the reason, each forecast world with its stated probability and the ply at which it came true or did not, what arrived afterwards, the game's result |
| `postmortem.md` | the tables `scripts/postmortem.py` makes from those rows |
| `<match>.log` | the arena's progress lines |

The engine's reports inside `engine_logs`, one per decision:

- `info string hb_forecast {json}`: the lines of the partner-board search (`move`,
  `source`, `score`, `pv`, `captures` as `<ply><+|-><piece>`, `weight`) and the
  `worlds` made from them (`arrival` such as `+N-B`, `p`). `+` is a piece for the
  seat, `-` one for its opponent.
- `info string hb_coord {json}`: the candidates, each with its value in every
  world (`worlds[].values`), its expected winning chance `E`, and the reason for
  the choice.
- `info string hb_summary key=value ...`: the decision, `coord_reason`, the main
  search's score, depth and nodes, the budget.
- `info string hb_tell v1 ...`: the message to the partner (`PARTNER_TALK.md`).

A move is written with its board: `1e2e4` is e2e4 on board A, `2N@f3` drops a
knight on board B. Team white is White on board A and Black on board B.

Searches were made with a fixed number of nodes, so they are deterministic: the
same binary given the same position and options makes the same decision. The
binaries are not published; `manifest.json` has their sha256, and the engine
source of this branch builds the last one (`README.md`, "Build").

Host names, the user name and home directory of the machine that ran the matches
have been replaced (`host`, `user`, `/home/user`) by `scripts/package_logs.py`.

## Things worth looking for

- Which positions the evaluation gets most wrong, and what they share (`AUTOPSY.md`
  and `AUTOPSY2.md` are two attempts).
- A better forecast of what arrives and when: `postmortem.jsonl` has every stated
  probability beside what happened.
- How a team's winning chance depends on both boards' scores together
  (`analysis/two-board-surface/`).
- When sitting wins or loses games: every sit and wake is in `results.jsonl`.
- Whether anything a partner could say would have changed a lost game: the
  `hb_tell` lines and the partner's next decision are both in the logs.
