# Von Neumann Factory — Claude entry point

Co-building a constructive **Make Anything Machine (MAM)** in Shapez 2 with John.

## Start a session like this
1. **`python tools/brief.py`** — measured state in ~14 lines: game up?, newest sandbox
   save, delivered counts + per-second rates, the broadcast goals, the active task.
   This replaces reading history to find out where you are.
2. **`docs/PROGRESS.md`** — current state and the active objective ONLY (~170 lines).
   Superseded material lives in `docs/history/`; read it only when you need a WHY.
3. **`docs/PLAYBOOK.md`** — how we build: method, design patterns, gotchas.
4. `docs/HOW-CLAUDE-IS-APPLIED.md` — how the model is used on this project, for an
   assessing agent; update it when the working method changes, not per session.
5. `docs/architecture.md` (MAM design + John's modules) and `docs/conventions.md`
   (file formats + game constraints) are **references — grep them for the thing you
   need; do not read them front to back.**

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
**A BUILD session, and Claude drives the game directly.** Since 2026-09-05 there is a
live bridge: a ShapezShifter mod (`mod/ClaudeBridge`) plus `tools/bridge.py` and
`tools/game.py` let Claude stop/start Shapez 2, load a named savegame, read and write
the running map, control sim speed, and trigger a save — with no human in the loop.
The offline savegame tools (`tools/save_world.py` et al.) remain the verification
oracle for anything the live half writes.

John broadcasts shape goals on in-game signal channels; Claude builds machines that
deliver them to the Vortex, and `research.json -> Shapes.StoredShapes` is the score.

- **Channel 123 `CuCuCuCu` — DONE** (target was 1,000; we are past a million).
- **Channel 789 `SuSuSuSu` — ACTIVE.** Mining and cutting work; recombination stalls.
  One batched test is queued and specified in PROGRESS.md.
- **Channel 456 `WuWuWuWu`** — untouched.

**Do not quote delivered counts from memory or from a doc — `python tools/brief.py`
measures them.** Numbers written into prose go stale within one sim hour.

**FIRST THING NEXT SESSION — run `brief.py`, then read PROGRESS.md ">>> START HERE".**
It names the exact next experiment, the 12-lane port rule that cost four builds, and
the rules of engagement (sandbox save only; never touch the 72.8h save).

Phases: 0 supply / **1 single-layer DONE** / 2 paint / 3 multi-layer / 4 pins /
**5 scale-4x DONE**. Phase 2's open decision (band-merge at 4 painters/unit, ~54k, vs
the current 16 painters/unit, ~121k) is still John's call and still unmade.

**Division of labour (agreed):** John builds physical layouts in-game — stamping
known platforms and wiring them is minutes for him and is Claude's slowest, most
error-prone path. Claude decodes, verifies (`tools/verify_mam.py`), designs logic,
and codifies. See PLAYBOOK "Division of labour".

## Session economics — these are measured, not vibes
Cost per model call is **(context size) x (turns)**, and context never shrinks inside a
session. Across the first seven sessions: 2,685 calls, 802M input tokens re-read,
average context 299k per call; every session spent ~a third of its entire input budget
on its last quarter of turns. See `docs/token-economics.md`.

* **Batch experiments.** One restart should discriminate between several hypotheses,
  never one. Sequential single-hypothesis builds is what burns a budget.
* **Stop the session at ~200k context** — commit, update PROGRESS.md, hand off, clear.
  Riding a session to 500k costs 3x per turn for the same work.
* **Tools print verdicts, not data.** `PASS 118/118 islands, 0 rotation rewrites` beats
  a table. Anything piped through `head` afterwards was already paid for in full.
* **Prefer local deterministic code over a model call** — and over a subagent, which
  starts cold and re-derives context this project has already paid for.

## Workflow per change
Edit `tools/build_modules.py` -> regenerate -> copy the `.spz2bp` into the in-game
"The Von Neumann Factory" folder -> `git add/commit/push`. John forces an in-game
blueprint-folder refresh to see new files. Give John a test recipe + ask for a screenshot.
Commit trailer: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## Working with John
Author blueprints from code (never hand-edit .spz2bp). **Extract geometry from his
reference blueprints instead of guessing.** Validate narrow, then scale. **Second-guess
his designs freely** (he asked) — but **ask before trading elegance/readability for
performance.** Keep the four docs current every session.
