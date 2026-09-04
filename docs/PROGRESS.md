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

# >>> START HERE: PHASE 2 IS UNBLOCKED — BUILD THE BAND-MERGE <<<

## The decision is made (John, 2026-09-04): **band-merge**.

The 4 per-lane stacker clusters are removed; the four lanes' band-P streams merge
per position, get painted once per position, and feed the ONE surviving cluster.

### Why this is right, in one line
**The 4 per-lane clusters are pure redundancy.** All five clusters already run at
the full unit output rate (they must, to feed the 5th at full rate). The 5th cluster
can assemble straight from the four band streams, so the other four are doing
throw-away partial-shape assembly. Paint is what made this worth fixing; the
redundancy was always there.

### Cost, from real building counts (recomputed 2026-09-04, includes `Paint 4 Filter`)
Cluster = 2x `Fancy A+B` (1,763) + 3x `Stacker` (1,361) = **7,609**.

| Per 1/4-belt unit, painted | Buildings | At full belt (x4) |
|---|---|---|
| keep current + 16 painters | 72,832 + 16x3,041 + 16x1,066 = **138,544** | **554,176** |
| **band-merge** + 4 painters | 42,396 + 4x3,041 + 4x1,066 = **58,824** | **235,296** |

Saving **~79.7k per unit / ~319k at full belt — 2.35x**.

---

## JOHN'S JOB: the band-merge, step by step (2026-09-04)

All coordinates are **island/platform coordinates** in
`For Claude Single layer MAM, no-paint`, and all footprints below were derived from
each platform's own building coordinates, not from its foundation name.

### The shape of the machine
Four identical lane blocks at **r = -9, -3, 3, 9**, each **four platform rows tall**
(`r-1 .. r+2`), flowing **east -> west**:

```
   X:  15..14      13..12     11     10        9..8    7..6   5..3   1..0    -1
       QuadSplit   Demuxer    Ovf    FILTER    Fancy   Stkr   Fancy  Stkr    Ovf
       <--------------- keep ------------->    <----- the lane cluster ----->
```
The filter's west edge **abuts the Fancy at X=9 directly** — there is no belt between
them. Each lane cluster = 2 Fancy + 3 Stacker + 1 Overflow, occupying **X = -1..9**.

The **5th cluster is the same cluster, translated**: Fancy `(-8,-8)` and `(-13,-8)`,
Stackers `(-10,-9)` `(-10,-8)` `(-16,-8)`, Overflow `(-17,-8)`, occupying **X = -17..-7,
rows -10..-7**. **Its four inputs arrive on its EAST edge at X = -6, rows -10, -9, -8,
-7** (the belts at `(-6,-10)`, `(-6,-9)`, `(-6,-8)` R2, plus the turn at `(-6,-7)`).

Today the four lane clusters reach it on four northbound trunks in the corridor
X = -6..-3, and **they avoid crossing by column ordering** — the southernmost lane
gets the westmost trunk, so each lane's westward run stops short of the trunks
belonging to lanes further south. Remember this trick; it is why the current machine
has no belt crossings.

### STEP 1 — delete the four lane clusters
For each lane `r` in `-9, -3, 3, 9`:

| entry | occupies | what |
|---|---|---|
| `(8, r+1)` | X8-9, rows r-1..r+2 | Fancy A+B |
| `(3, r+1)` | X3-4, rows r-1..r+2 | Fancy A+B |
| `(6, r)`   | X6-7, rows r-1..r   | Stacker |
| `(6, r+1)` | X6-7, rows r+1..r+2 | Stacker (flipped) |
| `(0, r+1)` | X0-1, rows r..r+1   | Stacker |
| `(-1, r+1)`| X-1                 | Overflow |

...plus the space belts inside X0..5 of that block. **-30,436 buildings**, and it
frees the whole strip **X = -1..9** across all four lane blocks.

**Keep** everything at X=10 and east (filters, their four Overflows at X=11, demuxers,
splitters, rail), **and the whole 5th cluster**.

### STEP 2 — know where the sixteen band outputs are
Each `Quaded Filter` is a `Foundation_1x4` standing **north-south at X=10**, covering
rows `r-1 .. r+2`, **one band per row**, in your labelled north->south order. All
sixteen leave **westward at X=9**:

| band | leaves west at X=9, on rows |
|---|---|
| **NW** | `-10`, `-4`, `2`, `8` |
| **SW** | `-9`, `-3`, `3`, `9` |
| **SE** | `-8`, `-2`, `4`, `10` |
| **NE** | `-7`, `-1`, `5`, `11` |

Merge the four rows in each table row together. **No arbitration needed**: band P of
lane T only passes when `goal[P] == T`, so exactly one of the four is ever flowing and
the other three are hard-blocked. A plain merger is correct for every goal.

### STEP 3 — SOLVED BY JOHN: `For Claude Space Belt` (2026-09-04)
In `blueprints/reference/`. 1,526 space-belt islands, and it answers the crossing
problem: **each band hops over the trunks east of it at Z=1, then drops into its own
merger at Z=0.** 90 `Lift1UpForward` + 97 `Lift1DownForward` + 373 islands at Z=1.
**Multi-level space belts work** — that was the open question and it is now closed.

Verified against the machine:
- **64 inputs (east, X=16) and 64 outputs (west, X=-15)**, in **16 groups of 4
  consecutive rows** — exactly 16 filters x 4 bands. Groups sit **6 rows apart**
  within a block and there are **4 blocks**, matching the four lanes per unit and the
  four units. The row geometry is right.
- **Band -> trunk mapping is consistent across all 16 groups**: group-offset 0 (the
  northmost row of a filter, = NW) merges into the trunk at X=15, offset 1 (SW) into
  X=13, offset 2 (SE) into X=11, offset 3 (NE) into X=9. Trunk heads take the first
  group directly, so 15 merge points each (14 on the column plus one at the crossover
  at `(12,0)`, `(10,1)`, `(8,2)`). Symmetric splitters on the west.
- The south half mirrors the north half, so the trunk order reverses across the
  crossover rows -1..2 — expected, not a fault.

### !! STEP 3a — THE ONE PROBLEM: the trunks are a 4x throughput bottleneck
**Each trunk is a single space-belt column, but it aggregates all four UNITS.**

Within one unit, exactly one of four lanes is active on a given band, so that band is
**12 lanes = one space belt**. But the four units are independent parallel copies that
all run at once, so **four of the sixteen inputs on each trunk are active
simultaneously = 4 x 12 = 48 lanes** on a 12-lane belt. The full-belt machine would
back up and run at unit speed.

**Recommended fix: aggregate PER UNIT, not across units.** Four separate aggregators,
each **16 in -> 4 trunks -> 4 out**, feeding that unit's single surviving cluster.
No trunk ever carries more than the 12 lanes it already carries today.

That is also far cheaper. Splitting one shared trunk set back out to 16 destinations
means keeping **16 stacker clusters**; per-unit aggregation needs **4** (each unit's
existing 5th cluster, which already handles that unit's full 12-lane output today):

| | clusters | buildings |
|---|---|---|
| aggregate across units, re-split to 16 | 16 | 121,744 |
| **aggregate per unit** | **4** | **30,436** |

**~91,300 buildings saved**, plus a much shorter belt run — the per-unit aggregator is
16-in/4-out instead of 64-in/64-out, so roughly a quarter of the islands.

**Why the re-split exists at all:** merging across units combines streams that were
never in conflict, and then has to undo it. Merging within a unit is the part that
matters, because that is where "exactly one lane is active" holds.

### STEP 3b — `VN-14 band merge aggregator` (Claude, 2026-09-04) — the per-unit version
**198 islands** (174 at Z=0, 24 at Z=1) vs 1,526 for John's four-unit version. Every
piece is lifted from `For Claude Space Belt.spz2bp` with its exact rotation, and the
build asserts each one still exists there:

| role | piece |
|---|---|
| west-flowing belt / north trunk / south run | `SpaceBelt_Forward` R2 / R3 / R1 |
| merge an east input onto a north trunk | `SpaceBelt_LeftFwdMerger` R3 |
| hop up, across, down | `Lift1UpForward` R2 -> `Forward` R2 at **Z=1** -> `Lift1DownForward` R2 |
| W->N, N->W, W->S, S->W | `RightTurn` R2, `LeftTurn` R3, `LeftTurn` R2, `RightTurn` R1 |

**Interface** — inputs on the filters' west edge at **X=9**, outputs into the surviving
cluster's east edge at **X=-6**:

| band | trunk X | input rows | exits west along | delivery column | into cluster at |
|---|---|---|---|---|---|
| NW | 8 | -10, -4, 2, 8 | -14 | -5 | `(-6,-10)` |
| SW | 7 | -9, -3, 3, 9 | -13 | -4 | `(-6,-9)` |
| SE | 6 | -8, -2, 4, 10 | -12 | -3 | `(-6,-8)` |
| NE | 5 | -7, -1, 5, 11 | -11 | -2 | `(-6,-7)` |

**Only the 12 input hops ever change level.** Everything else is flat, because each
band's northernmost source is one row further south than the previous band's: trunk NW
leaves west along row -14, north of where SW/SE/NE even begin (-13/-12/-11); SW leaves
along -13, north of SE and NE; and the delivery columns nest the same way. Same
"outermost gets the longest run" trick John already uses to stop the four lane-cluster
outputs crossing — it just falls out in the other direction here.

**Paint goes on the four trunks**, anywhere along their straight runs. A trunk is
uniform in colour by construction — that is the entire point of merging by position.

**Not yet verified:** which cluster input row wants which quadrant. Because stacking is
rigid-body and the four streams are disjoint single quadrants, the order should not
matter — but confirm with Step 4's single-quadrant goals before trusting it.

### STEP 3c — TWO WORKING AGGREGATORS, one decision left (2026-09-04)
Both are in `blueprints/reference/`. Both merge by POSITION, so both give **4 painters
per unit** — the actual Phase 2 goal — and both obey the lift rules. They differ in
one thing: **how many stacker clusters survive.**

| | `VN-14` (= `For Claude Fixed Pipes`) | `For Claude Johns Version Pipes` |
|---|---|---|
| islands | **216** | 368 |
| topology | 16 in -> 4 trunks -> **4 out** | 16 in -> 4 trunks -> **16 out** (4 groups of 4) |
| clusters kept per unit | **1** (the 5th) | **4** (the lane clusters), 5th deleted |
| cluster buildings/unit | **7,609** | 30,436 |
| rework | filters and clusters both move | **nothing moves** — same 16 rows in, same 16 rows out |

**John's is the minimal-disturbance design and that is a real virtue.** The 16 filter
outputs and 16 cluster inputs stay exactly where they are; only the belts between them
change, and each of those rows now carries a per-POSITION stream instead of a
per-lane-band one. His southernmost block needs no lifts at all — each trunk simply
starts there, so those four inputs run west along their own row and turn north.

**The cost is three redundant clusters per unit.** A trunk carries one band = 12 lanes;
split four ways each cluster sees 3 lanes per input and emits 3 lanes, so four
clusters at quarter load do exactly what one at full load does. The surviving 5th
cluster already eats 4 x 12-lane inputs today, which is the proof one is enough.

**~22,800 buildings per unit, ~91,300 at full belt.** Same trade-off as the original
band-merge decision, one level down.

**JOHN'S CALL.** Cheap and slow to build vs lean and more rework. If the four lane
clusters stay, their outputs are complete shapes and merge on a plain belt into the
existing output path — no stacking needed, which removes most of the re-plumb.
Claude can generate either; `VN-14` currently generates the 4-out version and asserts
it cell-for-cell against John's fixed file.

### STEP 4 — validate ONE band before building four
Do **NE only**: merge rows `-7, -1, 5, 11` into a single stream and feed it into the
5th cluster's input at `(-6,-7)`. Leave the other three inputs unfed.

Set a goal whose **NE quadrant** is the only non-empty one — e.g. **`Cu------`** — and
confirm the machine still produces it. Then try `Ru------`, `Su------`, `Wu------` so
all four lanes take a turn on that one band. **If those four pass, the merge concept
is proven** and the other three bands are the same construction.

### STEP 5 — the other three bands, then re-test unpainted
Build SW, SE, NW the same way into `(-6,-8)`, `(-6,-9)`, `(-6,-10)`.

**Careful — confirm which input row is which band.** I know the four inputs are at
rows -10..-7 and that the cluster is a translated copy of a lane cluster, but I have
NOT verified which physical input corresponds to which quadrant position. Get this
wrong and the machine builds mirrored/rotated shapes that still look plausible. Feed
the single-quadrant goals from Step 4 one at a time and watch which input row carries
traffic.

Then re-run the **3 random single-layer goals** that validated Phase 1, plus a
goal-change to confirm it still self-flushes. At this point the unit should be
**~42,400 buildings** and behave exactly as before.

### STEP 6 — only then, paint
Per band: merged stream -> `Paint 4 Filter` -> `Painter` -> the 5th cluster input.
Do **not** start this until Step 5 passes. See "CLAUDE'S JOB" below for the button
swap that makes the paint filter goal-driven, and the open `Painter` vs
`Painter Small` question.

### Do NOT touch the full-belt machine
`For Claude Working Full Belt Single Layer MAM no-paint` stays as it is until one unit
is proven end to end. It is exactly 4x this unit, so the same procedure replicates.

## CLAUDE'S JOB: the colour brain — and it is smaller than PROGRESS assumed

### !! The analyzer fan does NOT need re-laying. That task is cancelled.
The colour signals are derived from the **goal**, not from the lane — so all four
lanes' `Quaded Filter`s (and all sixteen at full belt) compute the same thing. The
colour logic therefore does not belong in the filter at all. It goes **on the
`Paint 4 Filter` platform**, replacing its button bank:

```
ControlledSignalReceiver (channel 123)      <- the goal shape, same channel the filters use
  -> rotate so this band's quadrant lands NE  (NE: none / SE: 1x CCW / SW: 2x CW / NW: 1x CW)
  -> VirtualAnalyzer
  -> its LEFT output = colour[band]          (forward output is the uncoloured shape; ignore it)
  -> 4x LogicGateCompare against r / g / b / null
  -> the four booleans replace the four Buttons
```
No fan surgery, no new platform, **no new signal channels**, and the 16 validated
filters are untouched. Four blueprint variants, one per band.

### The interface to preserve on `Paint 4 Filter` (decoded 2026-09-04)
`Foundation_1x4` R2, spans X-35..32, Y2..17. The selector is a **priority bank**:
- constants `(15,4)`=`r`, `(17,4)`=`g`, `(19,4)`=`b`, `(21,4)`=**null** (`05`), all R1
- `LogicGateIf` at `(15,5)`, `(17,5)`, `(19,5)`, `(21,5)` R1 — value from behind
  (the constant), **condition from the LEFT side**, output forward (south)
- **`ButtonDefault` at `(16,5)`, `(18,5)`, `(20,5)`, `(22,5)` R2 — these are the
  four cells to replace.**
- `LogicGateIf`/`Not` at rows 6-8 and `IfMirrored` at `(21,10)`,`(22,11)`,`(23,12)`
  chain them first-wins; the winner leaves west along the row-16 wire bus to the
  48 `PipeGate`s. `Display2x2` at `(26,4)` shows the selected colour — a free probe.
- If **no** slot is enabled the bus carries nothing and the gates stay shut. That is
  exactly the wanted behaviour for a quadrant that needs no paint (the analyzer's
  colour output is **null** for an empty or pin quadrant), so it needs no special case.
- **Room to build in: L1 above the bank has 246 free cells** in X13-32/Y2-17
  (L2 has 247). Drop to L0 with `WireDefault1Up/2UpBackward`, as John already does
  at `(26,5)`/`(27,5)`.

### >>> THE COLOUR BRAIN IS DONE — VALIDATED IN-GAME (2026-09-04) <<<
John stamped `VN-13 NE/SE/SW/NW colour` and read them against live goals:

| goal | NE | SE | SW | NW |
|---|---|---|---|---|
| `CrCgCbCu` | **red** | **green** | **blue** | **uncoloured** |
| `Cr--CbCu` | red | **null** | blue | uncoloured |

Exactly as predicted, including the **null for an empty quadrant** — the no-paint
flag the whole of Phase 2 depends on. Settled and not to be revisited:
- **analyzer: forward = uncoloured shape, LEFT = colour** (John named the compass
  directions: "grey out its top (**West**)", "shape on the **North**"; west is the
  left side of an R3 analyzer);
- **rotation mapping: NE none / SE 1x CCW / SW 2x CW / NW 1x CW.**

Each platform is 6-8 buildings: `ConstantSignal`(123) `(7,10)` ->
`ControlledSignalReceiver` `(9,10)` -> wire `(9,8)` -> rotators -> `VirtualAnalyzer`,
west display = colour. **This is the block to copy for the paint filters.**

### A rule I invented that John's game disproved
The p6 post-mortem claimed a `Virtual*` may not sit on a `ControlledSignal*` port
cell, inferred from a census where 45/45 of John's port cells hold only
`Wire`/`Display`/`ConstantSignal`. **`VN-13q1` shows an analyzer directly on the
output port works fine.** The census described John's habits, not the game's rules.
Removed from `validate_layout()`. **Absence from John's library is not a game rule.**

### LABELS: SOLVED. Two rules, and they have two different symptoms
Settled by John's purpose-built `For Claude Labels.spz2bp` (now in
`blueprints/reference/`). Full write-up in `conventions.md`:

1. **A label body is 5 cells**, centred on its entry, along its facing axis
   (R0/R2 horizontal, R1/R3 vertical) — fixed size, independent of text length.
   Applying an N-cell model to all 3,100 labels in the library: **0 collisions at
   N=5, 2,569 at N=7.**
2. **A label needs one cell of margin** — its body must stay within **[3,16]** on a
   1x1, never the outer ring. John's reference demonstrates this on purpose: every
   label he named "Corner" / "North side" / "South side" sits exactly one cell in.
   The census agrees: label bodies use offsets [3..7, 12..16], **never 2 or 17**,
   while every other building type uses the full 2..17.

**Overlap → the whole FILE is discarded** (never appears in the folder: p6, v1, v2,
r1, s1, s2). **Margin violation alone → the file imports but FAILS TO STAMP** (t1).
That is why the symptom kept changing under us. `validate_layout()` now encodes both
rules and reproduces every observed outcome — including that `t1`'s `(5,7)` label was
innocent and only its `(4,14)` one (body X2-6) was at fault.

Labels are back on and correctly placed: `COLOUR ->` at `(5,y)` (body X3-7) and the
title at `(10,13)` (body X8-12). **The four validated `VN-13 * colour` blueprints are
untouched and asserted byte-identical to what John tested.**

### Multi-island: CONFIRMED WORKING — `VN-13 colour brain all` stamps
Four islands we authored ourselves, each with its own chain, labels included. So the
tooling is fully unblocked. `VN-13r2`'s earlier failure is unexplained but superseded
— same construction, more islands, works. Not worth chasing.

### VN-13 STATUS: COMPLETE
| blueprint | state |
|---|---|
| `VN-13 NE/SE/SW/NW colour` | validated in-game; byte-frozen |
| `VN-13 colour brain all` | validated in-game — all four quadrants, one stamp |
| `VN-13t2 one island labelled` | validated in-game |

**Phase 2's colour front end is done.** `VN-13 colour brain all` is the block to graft
onto the paint filters.

### !! Palette correction: it is 3 paints + off, not 4
Both `Paint 3 Filter` and `Paint 4 Filter` carry the **same** four constants —
`r`, `g`, `b`, and **null**. The "3"/"4" is not the palette size. So:
- **Phase 2a — r/g/b + none.** Complete and testable with `Paint 4 Filter`'s fluid
  side untouched. Do this first.
- **Phase 2b — the full 8.** Needs pre-mixed colours fed in (`Paint Mixer` exists in
  John's library) AND a wider selector + wider fluid routing. Deferred.

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
| 2 paint | **UNBLOCKED — band-merge chosen 2026-09-04.** John: re-plumb. Claude: signal-driven `Paint 4 Filter`. Phase 2a = r/g/b+none. |
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

# PHASE 2 (paint): semantics settled — background

_The decision this section used to block on is made; see START HERE._

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

**Caveat, corrected 2026-09-04: it selects among `r` / `g` / `b` / `null` — 3
paints plus off, not 4 paints.** `Paint 3 Filter` carries the identical constant
set, so the 3/4 in the names is not the palette size. Full colour needs pre-mixed
colours fed in plus a wider selector and wider fluid routing (Phase 2b).

---

# Remaining gaps after Phase 2

| # | Gap | Notes |
|---|-----|-------|
| 1 | **Multi-layer** | `VirtualUnstacker` (1x1, in behind, **two outputs: forward + left**) is the layer extract. Architecture: **N single-layer engines + a layer-stacking chain**. A layer join is a single `Foundation_2x2` stacker platform (**1,361 buildings**), *not* a whole cluster — so joining 4 layers is ~4,100. **Layer stacking is only safe when every upper-layer quadrant sits above an occupied lower-layer quadrant**, else it falls through and merges — matches the game's own support rule, but confirm with John. |
| 2 | **Base supply self-sufficiency** | Rail delivery works for testing. Shape/fluid patch locations in the working save still TBD. |
| 3 | **Quadrant waste** | Consumption ratio = **the number of distinct types in the target layer** (1:1 for `CuCuCuCu` up to 4:1 for `CuRuSuWu`). Inherent to decompose-then-select, not a defect. |
| 4 | **8-colour palette** | `Paint 4 Filter` selects **r/g/b + null**, i.e. 3 paints + off — *not* 4 paints (`Paint 3 Filter` has the identical constant set). Full 8 needs pre-mixed feeds (`Paint Mixer`) plus a wider selector AND wider fluid routing. Phase 2b. |
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
| `VN-13 NE/SE/SW/NW colour` | VALIDATED — one goal quadrant colour each; byte-frozen |
| `VN-13 colour brain all` | VALIDATED — all four quadrant colours, four islands, one stamp |
| `VN-13t2 one island labelled` | VALIDATED — the label-placement control |

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
