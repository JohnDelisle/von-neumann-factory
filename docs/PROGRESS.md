# Project status & session handoff

_Last updated: **2026-09-04**. **Read this first when resuming**, then
`docs/PLAYBOOK.md` (method, patterns, gotchas), and skim `docs/architecture.md`
(the MAM design) and `docs/conventions.md` (file formats + game constraints)._

## What this is
Co-building a **Make Anything Machine (MAM)** in Shapez 2 with John. John builds
physical layouts in-game; Claude decodes, verifies, designs logic and codifies (see
PLAYBOOK "Division of labour"). GitHub is the source of truth; every change is
committed + pushed.

---

# >>> START HERE: THE FIRST QUESTION TO ATTACK NEXT SESSION <<<

## Do we refactor to the band-merge before adding paint — or keep the current architecture and use 16 painters?

**This is John's call and it blocks Phase 2.** Everything else about paint is
settled.

### Why it comes up now
A lane's partial shape can need **two different colours**. Goal `CrCgSuWu` has the
`Cu` lane supplying **NE red and SE green**, and a `Painter` colours a *whole shape*.
So with the current architecture, paint has to go **per band, before each lane's
stacker** — 4 bands x 4 lanes = **16 painters per unit**.

The **band-merge** alternative: merge the four lanes' band-P streams *per position*
first, paint once per position, then feed **one** stacker cluster. Exactly one lane
is ever active on a given band, so the merge needs no arbitration and does not
depend on the goal.

| Per 1/4-belt unit, painted | Buildings | At full belt (x4) |
|---|---|---|
| keep current architecture + **16 painters** | ~121k | ~486k |
| **band-merge** + **4 painters** | **~54k** | **~216k** |

The band-merge saves **4 stacker clusters AND 12 painters** per unit. **Note this
reverses Claude's earlier advice** — when only stacker clusters were at stake it
wasn't worth disturbing a working machine; with paint it roughly halves the factory.

### The trade
- **Keep current**: it is built, tested, and uses only validated components. A
  refactor is real work and risks a working machine.
- **Band-merge**: ~2.2x cheaper painted, and it is a re-plumb — John's territory,
  and it would be the last one. Claude's band-merge idea was never built, so it
  carries the usual unvalidated-geometry risk.

### Either way, this is Claude's job next
**The analyzer fan must be re-laid to expose the colour outputs.** The four fan
analyzers sit stacked at `X=10, Y=17..20` on the `Quaded Filter`, all facing R0, so
each one's side-output cell is occupied by the next analyzer — only the top has a
free neighbour at `(10,16)`. Getting all four colour signals out needs the fan
re-laid (or four extra analyzers placed in the free block at **X2-12 x Y24-26**,
33 cells), **plus** `ControlledSignalTransmitter`s to carry them to the paint
platforms.

---

# Phase plan

**0 base supply → 1 single-layer shape → 2 single-layer paint → 3 multi-layer →
4 pins/supports → 5 scale 4x to full belt.**
Cross-cutting, not a phase: the **goal-change flush** (John reports the machine
already self-flushes — confirm it stays true as complexity grows).

| Phase | State |
|---|---|
| 0 base supply | **DONE for testing** — rail delivery, 4 `Layout_TrainUnloader_Shapes_Flipped` per unit. Map shape/fluid patch locations when it needs to be self-sustaining. |
| 1 single-layer shape | **DONE + VALIDATED IN-GAME** (below) |
| 2 paint | **semantics settled, blocked on the decision above** |
| 3 multi-layer | designed, not built — `VirtualUnstacker` is the layer-extract primitive |
| 4 pins | not started — `VirtualPinPusher` + `Pin Setter` exist |
| 5 scale 4x | **DONE for Phase 1** — John's full-belt build is exactly 4x the unit |

---

# PHASE 1: DONE AND VALIDATED (2026-09-04)

John hand-built the re-plumb and tested both machines against **3 random
single-layer goal signals — all passed, and the machine self-flushes on a goal
change**.

- **`For Claude Single layer MAM, no-paint`** — 334 islands, **72,832 buildings**,
  ~1/4 belt out. 4 lanes, each fed its own uniform uncoloured base shape by **rail**.
- **`For Claude Working Full Belt Single Layer MAM no-paint`** — 1,373 islands,
  **289,828 buildings**, saturates one full space belt. Exactly **4x** the unit
  (16 filters, 16 splitters, 40 Fancy A+B, 20 stacker clusters).

Both in `blueprints/reference/`.

### How it works
```
lane T: rail -> Quad Splitter -> Demuxer -> Quaded Filter -> its own stacker cluster
        -> a PARTIAL shape: type T in the positions the goal wants T, empty elsewhere
4 lanes -> 5th stacker cluster -> the four partials are DISJOINT, so rigid-body
        stacking merges them into ONE layer = the complete goal shape
```
**John's merge beat the one Claude proposed** — it reuses the same rigid-body rule
the whole design rests on, with no new belt geometry and only validated components.

### Why the filter needs no per-lane logic
With each lane fed a uniform uncoloured `TTTT`, band `P` of lane `T` carries exactly
`"T at position P"`. The fan drives that band with `Q_P` = the goal's quadrant at
`P`. The `BeltFilter` passes on equality, so
`band P of lane T passes  <=>  goal[P] == T` — the desired behaviour on all four
lanes, from **one unmodified filter design**.

### Verified by `tools/verify_mam.py`
Audits what fails **silently** in-game (a stamped machine looks fine and just makes
subtly wrong shapes): every `Fancy A+B` is the lane-FIXED version cell-for-cell, no
stale warning labels, every `Quaded Filter` identical to the goal-driven reference,
all Goal Receiver channels agree, component ratios consistent, no malformed configs.
**All three machines pass** (10 / 40 / 8 Fancy units, all fixed; all channels 123).
Re-run it on any new MAM variant:
```
python tools/verify_mam.py "blueprints/reference/<file>.spz2bp"
```

---

# PHASE 2 (paint): semantics settled

**John confirmed the Shape Analyzer contract:** it reads the **NE** part of the input
shape and emits the **uncoloured shape signal** on the top/forward output and that
part's **colour signal** on the side output. For a **Pin or empty** part the colour
output is **null**.

Consequences:
1. **The filter is ALREADY colour-blind.** The fan's band signals are analyzer
   forward outputs, so they carry no colour. **The Phase 1 machine already builds the
   correct shape for a coloured goal, today.** Phase 2 needs **no filter-logic
   change**. (Claude's paint-both-sides normaliser circuit is dropped — obsolete.)
2. **The colour signal is free** on the analyzer's side output, currently unused, and
   `null` for empty is a ready-made "this quadrant needs no paint" flag.

### The paint router already exists — `Paint 4 Filter`
`Painter` (3,041 buildings, 192 painters) has **no logic at all** — it paints with
whatever fluid arrives. So brain-driven colour is a **fluid routing** problem.

`Paint 4 Filter` is the router: `Foundation_1x4`, 1,066 buildings, 84 fluid ports,
**48 signal-driven `PipeGateDefaultInternalVariantMirrored`**, selected by a 4-way
`Button`/`ConstantSignal`/`LogicGateIf` bank — **the same 4-band shape as the
`Quaded Filter`**, so swap its button bank for the analyzer's colour signal exactly
as John did for the shape filter. (`Paint 3 Filter` is the 3-way version.)

**Caveat: it selects among 4 paints; the palette is 8.** Full colour needs chaining,
a wider selector, or feeding pre-mixed colours in.

---

# Remaining gaps after Phase 2

| # | Gap | Notes |
|---|-----|-------|
| 1 | **Multi-layer** | `VirtualUnstacker` (1x1, in behind, **two outputs: forward + left**) is the layer extract. Architecture: **N single-layer engines + a layer-stacking chain**. A layer join is a single `Foundation_2x2` stacker platform (**1,361 buildings**), *not* a whole cluster — so joining 4 layers is ~4,100. **Layer stacking is only safe when every upper-layer quadrant sits above an occupied lower-layer quadrant**, else it falls through and merges — matches the game's own support rule, but confirm with John. |
| 2 | **Base supply self-sufficiency** | Rail delivery works for testing. Shape/fluid patch locations in the working save still TBD. |
| 3 | **Quadrant waste** | Consumption ratio = **the number of distinct types in the target layer** (1:1 for `CuCuCuCu` up to 4:1 for `CuRuSuWu`). Inherent to decompose-then-select, not a defect. |
| 4 | **8-colour palette** | `Paint 4 Filter` selects 4. |
| 5 | **Pins / crystals** | Pins are Phase 4. **No crystals in the working save** — out of scope. |

---

# Environment & workflow (LOCAL Windows session — the normal case)

- Repo: this working directory. Game folder:
  `C:\Users\jdeli\AppData\LocalLow\tobspr Games\shapez 2`
  (`blueprints\2026\` = John's library, `blueprints\The Von Neumann Factory\` = ours,
  `savegames\`). Read/write directly; git is local — commit and push normally.
- Regenerate: `python tools\build_modules.py blueprints`, then copy the `.spz2bp`
  into the in-game folder and hash-compare. John forces an in-game blueprint-folder
  refresh to see new files.
- Commit trailer: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` plus
  `Claude-Session: <session url>`.
- **The Cowork/cloud access checklist (device_bash, `$HOME/mnt`, PAT-in-VM) is
  IRRELEVANT to a local session** — it was for cloud sessions only. If you are a
  cloud session, see git history for `docs/PROGRESS.md` before 2026-09-04.

## Working save & world
- **`savegames/5589333c-...`** ("Bullshitting") — fully unlocked (Level 107, ~44%
  research; **NO crystals**), cleared to ~28.5k structures. Blueprint cost = 0.
  `ResearchShapeCostMultiplier` = 60.

---

# Hard-won facts worth not relearning

### Three SILENT failure modes (full detail in conventions.md)
1. A building `C` **without `$type`** => the game discards the **whole file**; it
   never appears in the blueprint folder, which reads like a failed refresh.
   `check_configs()` guards this over every generated module.
2. **One invalid building** => the game places the foundation and discards **every
   building on that island**. A bare platform, no red X.
3. The **same** invalid building warns normally in a single-island blueprint but
   blanks the island in a multi-island assembly. **Isolate a suspect building on its
   own blueprint to get the real error message.**

### Method rules that were learned the hard way
- **Never infer a building's footprint from in-situ copies** — ask John for a minimal
  reference, ideally with the building outlined in belt **on the floor above**. That
  trick settled the 3x3 Goal Receiver in one read after two failed guesses.
- **Read the labels, don't guess.** `LabelDefaultInternalVariant` `C` =
  base64(2-byte LE length + UTF-8). John annotates everything.
- **Enumerate from the game, not from John's library**: all 98 `*InternalVariant`
  building ids are plain ASCII in
  `shapez 2_Data/resources.assets`. That is how `VirtualUnstacker` and
  `VirtualPainter` were found.

### Fancy A+B lane-swap bug — FIXED, VALIDATED, and now the baseline
Outer/inner lanes crossed over in the overflow tap. Root cause: outer rows tapped at
splitter column X=9/X=8, inner at X=7/X=6, and the downstream weave delivered them to
the opposite classes. Fixed by swapping those columns per band and shifting each
outer row's launcher hop one cell east. **Four bands, not two** — John caught that the
first pass only fixed the labelled north half. 168 retyped cells, no buildings added
or removed (bar 2 stale labels). The generated patch is asserted **cell-for-cell
identical to John's own hand-mirrored fix** at build time. **Build all further stacker
work on `load_fixed_stacker_islands()`, never the stock reference.**

### Key game facts (full detail in conventions.md)
- Blueprint = `SHAPEZ2-5-<base64(gzip(JSON))>[]_2$`.
- +X East / +Y South; R = 90 CW steps (R0 E, R1 S, R2 W, R3 N). 1x1 platform =
  20x20, buildable ~[2,17], floors L0-2. Bus = 4 cols x 3 floors = 12 lanes.
- **1 space belt = 12 lanes; "full belt" = 4 of them = 48 lanes.**
- **Stacking is rigid-body**: DISJOINT quadrants merge into one layer; any overlap
  puts the top shape on a NEW layer. Both halves of this rule are load-bearing —
  disjoint for the 5th-cluster merge, overlapping for multi-layer.
- **Multi-cell buildings record only their ORIGIN cell**; the other cells are absent
  from the entry list, so an "empty" neighbour may not be free.
- Edge ports only on the 4-lane band per edge (N/S at X8-11, E/W at Y8-11, per floor).
- Wire-layer port map (analyzer, painter, unstacker, gates): **conventions.md**.

---

# Module inventory (`blueprints/`, generated by `tools/build_modules.py`)

| Module | State |
|---|---|
| `VN-00 coord test` | VALIDATED — coordinate/rotation sanity check |
| `VN-01 quad isolator 1lane` | VALIDATED — HalfDestroy->Rot90CW->HalfDestroy |
| `VN-02 half-destroy 12lane` | VALIDATED — John's launcher-optimised redesign |
| `VN-03 rotate90CW 12lane` | launcher-optimised `Clockwise` (VN-02 layout, cut->rot) |
| `VN-04`, `VN-05` | **SUPERSEDED** hand-built mechanic proofs. Keep for reference; don't build on them |
| `VN-06 quad splitter test` | structural only, never in-game confirmed |
| `VN-07 reassembly test` | VALIDATED — Quad Splitter -> Demuxer -> lane-fixed Stacker |
| `VN-08 fancy A+B lane fixed` | VALIDATED — asserted identical to John's own fix |
| `VN-09 stacker empty quadrants fixed` | VALIDATED — drop-in replacement |
| `VN-10 any shape maker lane fixed` | VALIDATED — all 8 embedded Fancy units fixed |
| `VN-11 quaded filter goal driven` | VALIDATED — **John's own platform, used verbatim** |
| `VN-11a filter verbatim` | control: stock preset-driven filter, known-good baseline |
| `VN-12 MAM goal driven` | VALIDATED — superseded by John's Phase 1 build |
| `VN-12 MAM preset CuRuSuWu` | VALIDATED — preset-driven A/B |

**Superseded by John's Phase 1 machines** (`blueprints/reference/For Claude Single
layer MAM, no-paint` and `... Working Full Belt ...`) — the VN-1x series is history
now, but keep it: it is what the verifier diffs against.

## Reference blueprints (`blueprints/reference/`)
John's, used verbatim as black boxes: `Quad Splitter`, `Demuxer`, `Stacker`,
`Stacker supporting empty quadrants`, `Fancy A+B Side Overflow` (+ pre-lane-fix),
`Filter`, `Quaded Filter`, `Quaded Color Filter`, `Smart Filter`, `Shape Filter`,
`Painter`, `Overflow`, `Trash`, `Full Belt Any Shape Maker`, and the four
purpose-built `For Claude *` references (`Signal Receiver`, `Filter with Signal`,
`Wiring Shapes`, and the two Phase 1 MAMs).

`For Claude Wiring Shapes` doubles as the **goal source for testing** — a
`ControlledSignalTransmitter` on **channel 123** sending a hand-set shape, which is
what the MAM's filters listen to.
