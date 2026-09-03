# Von Neumann Factory — Claude entry point

Co-building a constructive **Make Anything Machine (MAM)** in Shapez 2 with John.
Read these first, in order:
1. `docs/PROGRESS.md` — current state, the active objective, resume steps.
2. `docs/PLAYBOOK.md` — how we build: method, design patterns, gotchas.
3. `docs/architecture.md` — the MAM design + John's reusable module ecosystem.
4. `docs/conventions.md` — file formats + reverse-engineered game constraints.

## Environment — you may be in either of two setups
- **Claude Code on John's Windows PC (local)** — you have DIRECT access:
  - Repo = this working directory (remote `github.com/JohnDelisle/von-neumann-factory`, private).
  - Shapez 2 game folder = `C:\Users\jdeli\AppData\LocalLow\tobspr Games\shapez 2`
    (`blueprints\2026\` = John's reference library; `blueprints\The Von Neumann Factory\`
    = our in-game folder; `savegames\`). Read/write it directly.
  - Git is local (John's credentials) — commit + push normally, no PAT dance.
  - Python: `python tools\build_modules.py blueprints` (use `python`/`py` on Windows).
  - **IGNORE** PROGRESS.md's Cowork access steps (`device_bash`, `$HOME/mnt`, PAT-in-VM) —
    those are only for cloud sessions. Use the real Windows paths + local git above.
- **Cowork cloud session linked to John's PC** — follow PROGRESS.md's ACCESS CHECKLIST
  (device_bash, folder mounts, fine-grained PAT, git-on-device).

## Active objective
**An ARCHITECTURE session, not a build session.** The reassembly test is done and
validated in-game (`VN-07`: `Quad Splitter` -> `Demuxer` -> lane-fixed
`Stacker supporting empty quadrants`), as is the Fancy A+B lane fix (`VN-08`/`VN-09`).
Everything built so far is a **fixed recipe** — nothing chooses anything yet.

Next session John wants to settle, together: **MAM architecture, the missing building
blocks, and logical next steps.** Don't start implementing (no 2-type mix, no new
blueprints) until that's agreed. Read PROGRESS.md ">>> NEXT SESSION OBJECTIVE" first —
it carries the have/missing inventory and the open questions. Bring a proposed
architecture and trade-offs, not a blank page.

## Workflow per change
Edit `tools/build_modules.py` -> regenerate -> copy the `.spz2bp` into the in-game
"The Von Neumann Factory" folder -> `git add/commit/push`. John forces an in-game
blueprint-folder refresh to see new files. Give John a test recipe + ask for a screenshot.
Commit trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Working with John
Author blueprints from code (never hand-edit .spz2bp). **Extract geometry from his
reference blueprints instead of guessing.** Validate narrow, then scale. **Second-guess
his designs freely** (he asked) — but **ask before trading elegance/readability for
performance.** Keep the four docs current every session.
