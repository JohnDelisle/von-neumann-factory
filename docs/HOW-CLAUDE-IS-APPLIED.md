# How Claude is applied to this problem

Written for an agent assessing HOW John applies Claude here, so it can guide him to a
more effective use of the model. Everything below is either measured in this repo or
happened in a session that the git history and `docs/history/` record. Where a number
is quoted, the file that produced it is named so it can be re-run.

## The problem

Build a Make Anything Machine in Shapez 2: John broadcasts a target shape on a signal
channel, and the factory has to mine, cut, rotate, paint, stack and deliver that shape
to the Vortex at space-belt throughput. The score is `research.json ->
Shapes.StoredShapes`, read off the save file. See `docs/architecture.md`.

## The setup

- **Two seats for Claude.** Claude Code on John's Windows PC (direct access to the
  repo, the game's blueprint and savegame folders, and local git), or a Cowork cloud
  session linked to the PC (folder mounts, a fine-grained PAT). `CLAUDE.md` tells a
  fresh session which seat it is in and what to do first.
- **A live bridge into the running game** since 2026-09-05: a ShapezShifter mod
  (`mod/ClaudeBridge`) plus `tools/bridge.py` / `tools/game.py` let Claude stop and
  start Shapez 2, load a named save, read and write the map, set sim speed and trigger
  a save with no human in the loop.
- **Offline tools as the oracle.** `tools/save_world.py`, `verify_mam.py`,
  `verify_miners.py`, `brief.py` and the blueprint codec (`tools/shapez_bp.py`) decode
  saves and blueprints deterministically. Anything the live half writes is checked by
  the offline half. ~4,300 lines of Python, all Claude-authored, all committed.
- **Game data exported by the game itself.** `gamedata/basedata-v1138/buildings.json`
  (every building's footprint and belt in/out faces) came from the in-game console
  command `debug.export-game-data`. Tools read it instead of hard-coding geometry.
- **Blueprints are generated, never hand-edited.** `tools/build_modules.py` holds one
  function per module (`VN-00` .. `VN-20`); running it regenerates `blueprints/`. John's
  own 41 hand-built modules in the game's `blueprints/2026/` folder are the reference
  library Claude decodes.

## The operating model

**Session start is a procedure, not a read.** `python tools/brief.py` prints the
measured state in about fourteen lines (game up, newest save, delivered counts and
rates, goals, active task). Then `docs/PROGRESS.md` (current state and the next
experiment only, ~440 lines), `docs/PLAYBOOK.md` (method and gotchas), and the two
reference docs grepped, never read front to back.

**The loop** (`docs/PLAYBOOK.md`, "Working method"):
1. Claude writes a module SPEC (operators per lane + shell); the layout compiler in
   `tools/build_modules.py` fans lanes by the measured rates, routes, validates and
   traces it (since 2026-09-06 -- before that Claude hand-placed cells, which is where
   every placement failure came from). Regenerate, copy the `.spz2bp` into the
   in-game folder, commit and push.
2. John refreshes the blueprint folder, stamps the module, plumbs it, runs it, and
   reports what he sees (a sentence, sometimes a screenshot).
3. Claude codifies the outcome: a verdict tool, a docs entry, a rule.

**Division of labour** (agreed 2026-09-03, `docs/PLAYBOOK.md`): John builds physical
layouts in-game; Claude decodes, verifies, designs logic and codifies. The reason is
measured, not preference: every placement failure in the project came from Claude
authoring unfamiliar geometry blind, while re-plumbing validated platforms is ten
minutes of stamping for John. Claude is fast at what John cannot do by eye: decoding
blueprints, walking belt and wire graphs, costing designs from building counts,
turning a working layout into parameterised code.

**John's standing instructions to Claude:** extract geometry from his reference
blueprints instead of guessing; validate on one lane before scaling to twelve or
forty-eight; second-guess his designs freely, but ask before trading readability for
performance; keep the four docs current every session; commit every change.

**Memory lives in the repo, not the model.** Four docs carry state across sessions
(`PROGRESS.md` state, `PLAYBOOK.md` method, `conventions.md` game facts,
`architecture.md` design). Superseded material is archived to `docs/history/`, not
deleted. Claude also keeps a small private memory directory outside the repo (three
entries as of 2026-09-06: token cost matters, session economics, design for building
throughput).

## What it costs, measured

`docs/token-economics.md`, produced by `tools/token_report.py` over the first seven
sessions:

| | |
|---|---|
| model calls | 2,732 |
| input tokens read | 806 M |
| average context per call | 302 k |
| share of a session's input spent on its last quarter of turns | 33-40 % |
| largest single context filler | Claude's own prose, 41 % |
| second | Bash tool results, 34 % |

Rules derived from that and now in force: batch experiments so one restart tests
several hypotheses; stop a session at ~200k context and hand off; tools print verdicts
(`PASS 48 lanes, 144 paths`) not tables; prefer local deterministic code over a model
call or a subagent; shorter answers.

## Three cases that show the pattern

**VN-13, the colour brain (2026-09-04).** The first build never appeared in the game's
blueprint folder, silently. Claude bisected it with John across seven cut-down builds
(p0..p6, each one stamp for John) and found two causes, both Claude's: a 3x3 receiver
whose invisible body was overlapped, and a label laid through it. The fix was not the
layout but `validate_layout()`, which now refuses that whole class at build time using
the game's own footprint export. Lesson recorded: "a round-trip does not validate a
format"; ask what the system will just tell you.

**The 12-lane port rule (2026-09-05).** Four consecutive builds of a mining unit
delivered one lane instead of twelve. The cause was a model of where a miner's output
band sits (island rotation) that was wrong; the senders' own rotation is the truth and
the island's is inert. Once the rule was measured off John's 72.8-hour factory (144
miners, all consistent), the next build worked and throughput went up seven times.
Lesson: measure the rule off John's existing factory before the first build, not after
the fourth.

**VN-20, this session (2026-09-06).** John asked Claude to design a platform of its own:
full belt in, NE quadrant out. Claude built and offline-traced it in one session (a new
`trace_lanes()` walks every lane through the game's belt faces and was first checked
against John's known-good modules). v1 stamped and ran, and John saw at once that it
bottlenecked: Claude had copied "two operators per lane" from a rotator module onto a
half destroyer, which needs three. v2 was traced, shipped and validated the same day.
Lesson, now a rule and a rate table in `PROGRESS.md`: know every building's
throughput before laying it out.

The common shape: Claude's failures are unstated game facts, not logic or code; each
one costs John a stamp-and-look; each one ends as a verdict tool or a table so it
cannot recur.

## What has worked

- Extraction over invention. Every blind geometry guess was wrong; every extraction
  from John's blueprints was right (`PLAYBOOK.md`, "Working method" item 2).
- Deterministic verifiers that print a verdict: `validate_layout`, `verify_mam.py`,
  `verify_miners.py`, `trace_lanes`. They turned days of bisection into build-time
  errors.
- `brief.py` and the `PROGRESS.md` split, which cut session start from reading
  1,100 lines of history to reading a measured summary.
- John's one-sentence in-game observations. A single "it takes three, you have two"
  was worth more than any amount of Claude reasoning about rates.
- The game's own exports (`debug.export-game-data`, the save format) as ground truth.

## Where it is weak, for the assessor

1. **Game facts used to arrive by failure.** Building rates, port bands, footprint
   anchors, launcher gaps: each was learned from a failed stamp. Since 2026-09-06
   `gamedata/rates.json` (wiki + John + measurements, 131 variants) is read by the
   compiler before any cell is placed; the remaining prose rules in `conventions.md`
   are still being converted to checks as the compiler needs them.
2. **The human loop is the bottleneck, not the model.** Claude can now run the game,
   but stamping a blueprint and reading a throughput problem by eye is still John's
   job. Whether the bridge can stamp and measure a module unattended has not been
   tried.
3. **Context growth.** Sessions still run past 200k despite the rule; the last quarter
   of every session is the most expensive. The hand-off procedure exists but is
   applied by the model's judgment, not enforced.
4. **Documentation volume.** The four docs total ~2,750 lines. They are the project's
   memory, but reading them is a cost every session; the grep-not-read rule mitigates
   this only if followed.
5. **Design authority.** John has explicitly asked Claude to second-guess his designs,
   but until VN-20 every Claude-authored layout was a derivative of one of his. VN-20
   is the first original design and needed one correction.

## Where to look

| question | file |
|---|---|
| what state are we in | `python tools/brief.py`, `docs/PROGRESS.md` |
| how do we work, what bit us | `docs/PLAYBOOK.md` |
| what the game actually does | `docs/conventions.md` (grep it) |
| what we are building and why | `docs/architecture.md` |
| what sessions cost | `docs/token-economics.md`, `python tools/token_report.py` |
| every module Claude authored | `tools/build_modules.py`, `MODULES` at the bottom |
| the live bridge | `mod/ClaudeBridge/`, `tools/bridge.py`, `tools/game.py` |
| what happened before 2026-09-05 | `docs/history/` |
| session-by-session narrative | `git log` (99 commits over 2026-09-03 .. 09-06) |
