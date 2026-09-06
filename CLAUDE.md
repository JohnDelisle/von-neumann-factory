# Von Neumann Factory — Claude entry point

Co-building a constructive **Make Anything Machine (MAM)** in Shapez 2 with John.

## Start a session like this
0. **`docs/DIRECTIVE.md`** — standing instruction (2026-09-06): spec -> compile ->
   verify -> measure; the compiler is the product. Its 8 rules override anything below.
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

## Standing rules (from `docs/DIRECTIVE.md`; the measurements are in `docs/token-economics.md`)
1. **Spec, then compile, then verify, then measure.** Never hand-place cells for anything
   the compiler can express; if it can't, extending the compiler is the deliverable.
2. **Verdicts only.** Tool output is one line unless it FAILs. No `python -c` dumps.
3. **Big reads go to a subagent** (decode a blueprint, census the library, read wiki
   pages, walk a save) that returns a verdict or a table under 30 lines.
4. **No narration.** Answer, act, report the verdict. Prose was 41% of all input.
5. **One experiment per session.** `brief.py`, the one thing PROGRESS.md names, commit,
   update PROGRESS.md, stop. Never past ~150k context; write the hand-off early.
6. **Facts arrive before builds.** Print the rate/footprint row for every building a
   module uses before laying it out; a missing row is the first task (wiki first).
7. **Definition of done is machine-checkable.** No PASS script = ask John for the
   missing constraint first. John is not the test harness.
8. **Mechanical steps are one batched shell call**, or a small-model subagent when
   they would take many turns.

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
