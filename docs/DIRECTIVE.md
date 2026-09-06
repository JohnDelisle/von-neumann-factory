# DIRECTIVE — Phase 2: from research to engineering

_Written 2026-09-06 by an assessing Claude session that read the whole repo, at John's
request. Committed as `docs/DIRECTIVE.md`, linked from `CLAUDE.md` as item 0, and
standing instruction until John says otherwise. It is short on purpose; it is read
every session._

## The diagnosis, in three sentences

The research phase (formats, codec, bridge, verifiers) is done and was done well. Every
remaining cost comes from one gap: **Claude hand-places cells.** `_ne_isolator_floor()`
is hundreds of hand-written `(x, y, R, T)` tuples in a rotated frame — a language model
doing pixel-level spatial reasoning with the game as the only oracle and John as the
only eyes. That is why VN-20 cost a session and 100k tokens, and why every failure was
an unstated game fact rather than a logic error.

**The fix is an abstraction layer, not more care.** Build the three things below, in
order, before designing any further modules by hand.

## 1. The layout compiler (highest priority)

A module is a spec; deterministic code turns the spec into cells. Target:

```python
Module("NE isolator", shell=QUADED_FILTER_SHELL, lanes=48,
       per_lane=[HalfDestroy, Rot90CW, HalfDestroy, Rot90CCW])
```

The compiler must:
- Look up each building's throughput in `gamedata/rates.json` (see §3) and fan a lane
  out 1->N->1 automatically (CutterHalf needs 3 per lane, RotatorOneQuad 2, belts 1).
- Place the split/merge butterfly and route belts using `buildings.json` faces. Extract
  the routing pattern from John's proven butterflies (`Clockwise`, `Quaded Filter`
  shell); do not invent a router before reading his.
- Handle frame rotation itself. No module function should ever contain a coordinate
  transform again.
- Run `validate_layout` + `trace_lanes` and print one verdict line.

Definition of done: `vn20_ne_quadrant_full_belt()` is rewritten as a spec of <=10 lines,
compiles to a blueprint that passes `trace_lanes` with the same `(48, 576)` counts, and
diffs cell-for-cell against the validated VN-20 v2 (that file is now a regression test).
Then reproduce VN-02 and VN-03 the same way. Three modules from one compiler proves it.

## 2. The unattended experiment loop

Every ingredient exists: `stamp.py` writes a blueprint into a save, `game.py` loads it,
`bridge.py` sets speed, `brief.py` measures delivered/sec. Nobody has joined them.

Build `tools/experiment.py BLUEPRINT [--minutes N] [--expect LANES]`:
stamp into the sandbox save -> load -> speed 25 -> wait N sim-minutes -> save -> read
rate -> `PASS 47.9 units/s (expect >=48)` or `FAIL`. Then a batch mode that runs
several variants in one game session.

Definition of done: VN-20 v1 (the known-bad two-per-lane build) reports FAIL and v2
reports PASS with no human in the loop. From then on John looks at a build only to
judge beauty; throughput is measured by a script.

## 3. Game facts: complete them up front, from the wiki and the game

There is an official wiki: **https://shapez2.wiki.gg/** (MediaWiki, 78 articles,
CC-BY-SA). It has per-machine pages (`Half_Destroyer`, `Rotator`, `Stacker`,
`Belt_Launcher`, `Space_Platforms`, `Space_Transport`, `Vortex`, ...) with throughput,
footprint and mechanic text. Use it as the second source of truth alongside
`buildings.json` and John's blueprints.

- Pull it via the MediaWiki API, not page-by-page fetches:
  `https://shapez2.wiki.gg/api.php?action=query&list=allpages&aplimit=500&format=json`
  then `action=parse&page=<title>&prop=wikitext&format=json`. Cache to
  `gamedata/wiki/<title>.txt` and commit it. **If the fetch is blocked from your seat,
  stop and ask John — he will mirror the site locally.** Do not guess around a
  missing page.
- Produce `gamedata/rates.json`: every building -> items/sec (or fraction of a belt
  lane), footprint, in/out faces, floor rules. Wiki where it has it, `buildings.json`
  where it has it, John for the rest — asked as a single batched list, not one at a
  time as failures occur.
- Convert `conventions.md` into data + checks. **A game fact is a row in a table; a
  game rule is a check in `validate_layout`; prose is only for WHY.** Anything that
  remains prose in `conventions.md` after this should be history, not reference.

## Standing rules (replace the "Session economics" block in CLAUDE.md)

1. **Spec, then compile, then verify, then measure.** Never hand-place cells for
   anything the compiler can express. If the compiler can't express it, extend the
   compiler; that extension is the deliverable.
2. **Verdicts only.** Tool output is one line unless it FAILs. No `python -c` dumps
   into the main context.
3. **Big reads go to a subagent.** Decoding a blueprint, censusing John's library,
   reading wiki pages, walking a save: do it in a subagent that returns a verdict or a
   table under 30 lines. Cold-start cost is paid once; a 30k tool result in the main
   context is paid on every later turn. (This reverses the old "prefer no subagent"
   rule, which was wrong for read-heavy work.)
4. **No narration.** Do not explain what you are about to do, summarise what you just
   did, or restate results. Assistant prose was 41% of all input tokens. Answer, act,
   report the verdict.
5. **One experiment per session.** Start with `brief.py`, do the one thing PROGRESS.md
   names, commit, update PROGRESS.md, stop. Do not ride a session past ~150k context.
   Write the hand-off *before* you feel done, not after.
6. **Facts arrive before builds, not from failures.** Before laying out any module,
   print the rate/footprint row for every building type it uses. If a row is missing,
   that is the first task, and the wiki is the first place to look.
7. **Definition of done is machine-checkable.** If John's request cannot be turned into
   a script that says PASS, ask him for the missing constraint (throughput, shell,
   symmetry rule) before building. John is not the test harness.
8. **Cheap model for mechanical steps.** Regenerate, copy, `cmp`, commit, push, run
   verifiers: these do not need Opus. Use the smallest model that works.

## What John asks of you now

- Second-guess his designs; ask before trading beauty for throughput. (Unchanged.)
- Treat the compiler as the product. The MAM is what the compiler will build.
- When you want to hand-place cells, that is the signal the compiler is missing a
  primitive. Add the primitive.

## Order of work for the next sessions

1. Wiki slurp -> `gamedata/wiki/` + `gamedata/rates.json` (one session, mostly subagent).
2. Compiler v1 that reproduces VN-20 v2 cell-for-cell (one to two sessions).
3. `experiment.py` that FAILs VN-20 v1 and PASSes v2 unattended (one session).
4. Only then: the next MAM stage, written as a spec.

## Reviewer's notes (Claude, build session, 2026-09-06 — accepted with two amendments)

- **§1 definition of done.** "Diffs cell-for-cell against VN-20 v2" binds the compiler
  to one hand-routed layout; a router that reads John's butterflies will not reproduce
  it and should not have to. The regression test is functional: same shell and ports,
  `trace_lanes` PASS with the same `(lanes, operators)` counts, `validate_layout`
  clean, and `experiment.py` PASS. Cell equality is a bonus, not the bar.
- **Rule 8.** A model cannot swap itself mid-session; the cheap path for mechanical
  steps is ONE batched shell call (regenerate, copy, commit, push in one command is
  one model call at whatever context). Use a small-model subagent only when the
  mechanical work would otherwise take many turns.
- Rule 3 stands, with the corollary that a subagent's brief must carry the facts it
  needs (paths, the verdict format) so it does not re-derive them.
