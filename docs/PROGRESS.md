# Project status & session handoff

_Last updated: **2026-09-06** (night). This file is the **current state only** —
everything superseded now lives in `docs/history/`. Read this, then `docs/PLAYBOOK.md`
(method, patterns, gotchas). `docs/architecture.md` and `docs/conventions.md` are
**references: grep them for the thing you need, do not read them front to back**._

## What this is
Co-building a **Make Anything Machine (MAM)** in Shapez 2 with John. John builds
physical layouts in-game; Claude decodes, verifies, designs logic and codifies (see
PLAYBOOK "Division of labour"). GitHub is the source of truth; every change is
committed + pushed.

## Resume in three commands

```
python tools/brief.py              # where everything stands, measured, in ~14 lines
python tools/game.py up            # stop game, start it, load the NAMED sandbox
python tools/bridge.py speed 25    # run the sim hot
```

`brief.py` reads the newest sandbox save plus the running game: delivered counts and
per-second rates out of `research.json`, goals out of the ConstantSignals actually on
the map, nothing remembered. It exists so a session does not spend its first 20k
tokens reading history. `game.py` knows the sandbox uid (`d58e3f84-...`) and waits on
the world NAME, because the main menu renders a live background world and will happily
hand you an `IMapModel` for the wrong map.

---

# >>> START HERE (2026-09-06, evening): DIRECTIVE step 3 — `experiment.py` <<<

**Step 2 is DONE (2026-09-06):** the layout compiler lives in `tools/build_modules.py`
("layout compiler" section). A module is a spec:

    VN20 = Module("VN-20 NE quadrant full belt", QUADED_FILTER_SHELL, [HD, CW, HD, CCW],
                  labels=["VN-20 NE only  E in / W out"] + ["NE only"] * 3)

`compile_module()` reads `per_lane` for every operator from `gamedata/rates.json`,
fans each lane 1->N->1 (N = max per_lane), lays the VN-20 v2 butterfly (1->2 and 1->3
templates, greedy row-sharing for the lane walks), places it once per tile of the
`Shell` (the Shell owns the frame rotation: `bus_1x1(R)` and `QUADED_FILTER_SHELL`),
then runs `validate_layout` (per-tile windows) + `trace_lanes` and prints ONE line.

    python tools/build_modules.py blueprints
    REGRESSION VN-20 v2 validated.spz2bp: PASS 1636 cells identical
    REGRESSION For Claude VN-02 1to3 splitter.spz2bp: PASS 240 cells identical
    COMPILE VN-20 ...: -> fan 3; 1300 buildings; TRACE PASS 48 lanes, 576 operators
    COMPILE VN-02c half-destroy 12lane compiled: CutterHalf(3/lane) -> fan 3; 240 buildings; TRACE PASS 12 lanes, 36 operators
    COMPILE VN-03c rotate90CW 12lane compiled: RotatorOneQuad(2/lane) -> fan 2; 180 buildings; TRACE PASS 12 lanes, 24 operators

- **Two 1->3 butterflies, both in-game-validated, both regression fixtures** in
  `blueprints/reference/`: `VN-20 v2 validated.spz2bp` (Claude's 1->2->3 cascade,
  `fan="cascade"`) and `For Claude VN-02 1to3 splitter.spz2bp` (John's, same evening:
  `Splitter1To3`/`Merger3To1` for the outer lanes -- the game balances 1/3 per output --
  and an edge-entry sideways `Splitter1To2L` pair for the inner lanes, chains aligned,
  launcher hops on the home straight; `fan="sp3"`, the default). The compiler
  reproduces BOTH cell for cell from `Module(name, shell, [ops])`; the build fails if
  either drifts. John's pattern is 240 vs 336 buildings for one cutter.
- The hand-placed `_ne_isolator_floor()` / `_bus_to_quaded_filter_frame()` are deleted.
- **All three compiled modules VALIDATED in-game by John (2026-09-06, night):
  "VN-20 is working nicely. VN-03c is working nicely. VN-02c is working nicely."**
  VN-20 v3 (sp3 template, 1300 buildings, (48, 576)), VN-02c (cell-identical to John's
  own layout) and VN-03c (rotators 2/lane, 1->2 butterfly + launchers). Every one is
  now a frozen fixture in `blueprints/reference/` and a cell-for-cell regression --
  four fixtures, two shells, three butterflies (1->2, 1->3 cascade, 1->3 sp3). The
  compiler has produced three modules from specs and zero placement failures.
- Compiler limits (each is a missing primitive, not a workaround): 1x1 one-in/one-out
  operators only; fan-out N<=3; launchers only on the home straight; labels only on
  shells with a `label_at`. `op_row()` refuses anything else with the reason.

**Next session does step 3 ONLY**: `tools/experiment.py BLUEPRINT [--minutes N]
[--expect LANES]`: stamp into the sandbox (`stamp.py`) -> `game.py up` -> `bridge.py
speed 25` -> wait N sim-minutes -> save -> `brief.py`-style rate -> `PASS x/s
(expect >= y)` or `FAIL`; then a batch mode for several variants in one game session.
Definition of done: VN-20 v1 (two per lane; regenerate it with `compile_floor` at
N=2 for the test) reports FAIL and v2 PASS with no human in the loop.
DIRECTIVE §3's last bullet (conventions.md prose -> rows + checks) stays open; do it
as the compiler needs each rule.

The stage C material below is superseded by this order; keep it for the WHY.

## (superseded 2026-09-06) BUILD STAGE C — TASKS 1 AND 2 ARE DONE

**You are a fresh session on purpose.** The previous one was ending near 200k context,
where every turn costs three to four times what the same turn cost at the start. The
handoff below is the whole state; you do not need that session's transcript, and you
should not go looking for it.

## Minute one

```
python tools/brief.py          # measured state in ~14 lines. Do not read history first.
```

**Tasks 1 and 2 are finished and committed** (details in their sections below):
Task 1 gave every read tool a verdict-only default via `tools/say.py`; Task 2 proved
VN-18 delivers ONE lane, not twelve, and that the mine is the cap, not the belt.

**Your job is Task 3: build stage C.** It is fully specified below, including every
piece's geometry read out of the game's own `buildings.json`, the exact lane layout,
the two unknowns to settle first, and why it must run as two saves rather than two
lanes. Expect to write the generator, produce two variant saves, load each, and
measure — one game session.

The previous session stopped at 211k context rather than start this build there; that
is the rule working, not an interruption. Read the sections in order and go.

## VN-20 — NE-quadrant isolator at full belt, Claude's own layout (2026-09-06)

John asked for a platform of Claude's design: full space belt in, only the NE
quadrant out. **v2** is in the in-game folder and `blueprints/` as
`VN-20 NE quadrant full belt.spz2bp` — **VALIDATED in-game by John (2026-09-06):
"that worked."** A full belt in, the NE quadrant out, no bottleneck.

- **v1 REJECTED by John in-game**: it split each lane in two, and a **Half Destroyer
  keeps up with only a THIRD of a belt lane — three per lane, not two.** A one-quad
  Rotator keeps up with half a lane (two per lane, as in his `Clockwise`).
  **John's rule: for every building placed, know its throughput and put as many in
  parallel as the lane needs.** Now in the PLAYBOOK's building-rate table below.
- **v2**: same shell (`Foundation_1x4` R1, the `Quaded Filter` shell verbatim — 4 rows
  x 12 lanes, EAST in at local X17, WEST out at X2), every lane split 1->2->3 into
  three parallel HalfDestroy -> Rot90CW -> HalfDestroy -> Rot90CCW chains and merged
  back through two mergers. 576 operators (288 cutters, 288 rotators), 1,636 buildings.
- **Verified offline**: `trace_lanes()` in `build_modules.py` walks every lane through
  the game's own `BeltInputs`/`BeltOutputs` — `PASS 48 lanes, 144 paths, 576
  operators all on-path`, lane-preserving. Checked first against John's VN-02 and
  VN-03 (launchers included); both pass.
- **Verified in-game**: v2 keeps up with the belt. The 1x4 shell copied from the
  Quaded Filter and direct operator-to-operator chaining are both confirmed at scale.

### Building rates per belt lane (John, in-game, 2026-09-06)
| building | keeps up with | per lane |
|---|---|---|
| `CutterHalf` (Half Destroyer) | 1/3 lane | **3** |
| `RotatorOneQuad` / `CCW` | 1/2 lane | **2** (John's `Clockwise`) |
| belts, splitters, mergers, ports | full lane | 1 |

## VN-19 — the mine works; the Vortex end is now the cap (2026-09-05, night)

John re-stamped all twelve miners. Normalised against VN-15's untouched Cu miner:

| build | Ru / Cu | what it means |
|---|---|---|
| twelve miners as Claude built them | 4.001 | one working miner out of twelve |
| after John fixed ONE | 7.871 | one platform = one lane = 4 Cu-units |
| after Claude rotated the other eleven islands 180 deg | 7.83 | **no effect — island R is inert** |
| **all twelve re-stamped by John** | **27.985** | **7x the original build; Ru at 2,896/s** |

### Both collectors are now saturated, and that is the new bottleneck

Every belt on collector A and collector B reads **3,162 B** of cargo state against the
empty **474 B**, and the mergers read 4,047-6,427 B. Before the fix they were all at
474 B. The mine is now out-producing the delivery.

**This is John's rule arriving on schedule: emptying a full space belt takes FOUR
Vortex ports.** Each collector currently lands on ONE hub edge — A on hub tile (0,-1)
EAST, B on (0,-1) NORTH — so each is draining at roughly a quarter of what it carries.

### The next build

Split each collector into **four branches near the hub and land them on four separate
edge ports**. The hub has 12 outward edges x 12 lanes and VN-17 already copied John's
full 144-lane feed, so every edge is live and any machine only has to reach one.

Two collectors, both full, therefore want **eight ports** between them. Belts only —
no platform internals — which is the kind of generation that has worked reliably
(VN-18 wrote 118 belt islands and the game accepted all 118 unchanged).

Expected if the rule holds and the mine can feed it: 12 lanes = 48 Cu-units, against
27.985 today.

### Verify before measuring, every time

`python tools/verify_miners.py <save>` — steps one island the way each miner's senders
point and checks something is there to receive. It passes all twelve now, and flags the
leftover miner at **(-2,-3)** beside the Vortex, which fires west into empty space.

## Task 1 — DONE (2026-09-05, late)

Every read tool now obeys one rule, enforced by `tools/say.py`: **the default output
fits in ~15 lines and ends in a verdict; detail moves behind `--full`, and the tool
says how many rows it held back.** Measured: `verify_mam.py` 13 lines -> **1**
(`PASS ... -- 11/11 checks, 1567 islands, 163044 buildings [band-merge, 4 unit(s)]`),
`observe.py` ~40 -> **8**, `resources.py` ~270 -> **17**, `save_world.py` round trip
-> **1**. Nothing was deleted; `--full` still prints every line it used to.

`say.py` is the whole convention: `say.detail()`, `say.some(rows, cap=5)`,
`say.verdict(ok, msg)`, `say.args()` for argv minus the flags. New tools use it. See
PLAYBOOK "Tool output is a verdict, not a table".

**The rule survives the tools it was written for:** anything typed ad hoc obeys it too
— do not print a table and then read it; write the assertion and print PASS/FAIL plus
the two or three numbers that decide it. `python tools/token_report.py --top` is the
acceptance test: no single tool result much above 4k chars.

## Task 2 — ANSWERED (2026-09-05, late): we are supply-capped at ONE mining unit

**VN-18 delivers exactly one lane, not twelve.** Not the belt, not the hub — the mine.

### The experiment (one build variant, one load, one 200 s run)

`RuRuRuRu` had been measured at 4.00x the single unboosted `CuCuCuCu` miner in two
separate intervals (433.8/108.9 = 3.98, then 478.9/119.7 = 4.001). That is not "four
miner-equivalents, suspiciously close to 4" — under our own law (1 miner + 3 boosters
= 1 lane) it is **exactly one lane**, since an unboosted miner is a quarter lane.

So: cut collector B out of the save (one `SpaceBelt_Forward` island at (10,-13)),
load, run, and normalise against the Cu miner, which no variant touches.

| | Ru / Cu ratio | predicted if supply-capped |
|---|---|---|
| 12 lanes intact (v109) | **4.001** | — |
| collector B severed, 7 lanes (v111) | **3.934** | 2.33 |

**Removing five of the twelve lanes changed delivery by 1.7%.** And after 200 s of
running severed, collector B's nineteen `Forward` belts still read **474 B — the empty
form**. If the N-block miners were producing anything, those belts had nowhere to send
it and would have filled.

### What that means

The N block was contributing nothing before it was cut, and the whole 48-tile build
delivers 4 unboosted-miner-equivalents = one miner + three boosters = **one unit**.

**Best-supported reading: contiguous miner platforms merge into ONE mining unit.** The
48 islands form a solid rectangle; the game keeps them as `Layout_ShapeMiner` (the
rotations are right, so nothing was rewritten this time) but produces as though there
is a single miner with three effective boosters. This is the adjacency trap already in
these notes — "contiguous miners are silently rewritten to extensions" — one level up:
**even when the islands survive as miners, touching units share one production group.**

Not yet proven as a mechanism, and the honest alternative is that both collectors are
mis-wired AND collector A also passes only one lane. That needs two coincidences to
explain one exact 4.00x, so it is the weaker story — but it is testable.

### The next build, which settles it

Rebuild the patch as **12 SEPARATED units**: each a miner + its 3 boosters in a chain,
with at least one empty island tile between every unit and the next, each emitting into
the collector on its own port. If the merge story is right the rate goes to ~12 lanes
(~48 Cu-units); if it does not move, the cap is in the collector and the merge chain is
next. Either way the answer arrives in one build.

**Do not scale anything on the current numbers.** Every throughput figure in the Phase 2
cost model assumed 12 boosted miners = one saturated belt. What we have actually
demonstrated is one lane from 48 ore tiles.

### State left behind

* `backup-v112` = the intact VN-18 build with all progress kept (`RuRuRuRu` 2,658,480);
  the severed variant is `v110`/`v111`, kept for the record. Nothing was modified in
  place — every step wrote a new file.
* The game is loaded on v112 at speed 1.

## Task 3 — SPECIFIED, NOT BUILT: VN-16 stage C

Stage C was never committed — only described — so it has to be written. The expensive
half is done: every piece's geometry below is read out of
`gamedata/basedata-v1138/buildings.json`, not guessed.

### Declared geometry (`Tiles`, `BeltInputs`, `BeltOutputs`, all local)

| building | tiles | in | out |
|---|---|---|---|
| `CutterDefaultInternalVariantMirrored` | (0,0,0) (0,1,0) | (0,0,0) side 2 | (0,1,0) side 0 **and** (0,0,0) side 0 |
| `Splitter1To2LInternalVariant` | (0,0,0) | side 2 | side 0 **and side 3** |
| `Splitter1To2LInternalVariantMirrored` | (0,0,0) | side 2 | side 0 **and side 1** |
| `RotatorHalfInternalVariant` | (0,0,0) | side 2 | side 0 |
| `Lift1UpForwardInternalVariant` | (0,0,0) (0,0,1) | (0,0,0) side 2 | **(0,0,1) side 0** |
| `StackerStraightInternalVariant` | (0,0,0) (0,0,1) | side 2 on **both floors** | (0,0,0) side 0 |
| `TrashDefaultInternalVariant` | (0,0,0) | all four sides | none |

Rotation `R` rotates those directions: R1 = CW = d+1, R2 = 180 = d+2, R3 = d+3, with
0=+X 1=+Y 2=-X 3=-Y. **The whole machine flows west, so everything is R=2** and a
declared side-2 input faces world +X (accepts from the east), a side-0 output emits
world -X (west).

**This settles the question that stalled stage C.** At R=2 the plain variant's second
output (local side 3, -Y) emits to world **+Y**, and the mirrored variant's (local side
1) emits to world **-Y**. The trash sits at (15,9) — which is -Y of the lane and is
where the cutter's discarded half goes — so the old suspicion was right in shape:
one of the two variants throws branch B towards the trash side. It is the MIRRORED one
that goes -Y, so **the plain variant is the one whose branch B goes +Y**, into clear
space at (14,11). Verify by building, do not take this paragraph as measured.

### The layout to build (lane y=10, all R=2 unless noted)

    (16,10)+(16,9)  cutter mirrored   kept half -> west (15,10); discard -> trash (15,9)
    (15,10)         belt west         -> splitter
    (14,10)         Splitter1To2L     branch A -> (13,10) west ; branch B -> (14,11)
    (13..10, 10)    belts west        branch A, floor 0
    (14,11) ...     branch B: RotatorHalf (180 -> Su----Su), then
                    Lift1UpForward to floor 1, then belts west along floor 1
    (9,10,L1)       branch B arrives from the east on floor 1
    (8,10)          StackerStraight   floor 0 in from (9,10,L0), floor 1 in from (9,10,L1)
    (7..3, 10)      belts west        stacker output -> senders at x=2

### Two unknowns to settle before writing the generator

1. **Turn-belt variant ids.** Stage B only ever used `BeltDefaultForwardInternalVariant`.
   Branch B has to turn west after (14,11); grep `buildings.json` for the left/right
   belt variants and read their declared in/out rather than assuming.
2. **Whether a rotator accepts on a rotated face** — i.e. can `RotatorHalf` at (14,11)
   with R=1 take the item the splitter pushes +Y into it, or does branch B need a belt
   tile first. The declaration answers the geometry; only the game answers the
   acceptance.

### Run it as TWO SAVES, not two lanes

The queued plan was both splitter variants in one save on parallel lanes. **Don't** —
`StoredShapes` counts shapes, not lanes, so if `SuSuSuSu` appears you still cannot tell
which variant produced it. Instead write two saves identical but for the splitter
variant, load them one after the other in the same running game (a load is ~15 s), and
run each for 90 s. Attribution is then unambiguous and it is still one game session.

**Normalise the result against VN-15's Cu miner**, per PLAYBOOK — absolute rates spread
21% across intervals with nothing changed.

## How to run this session

* **Batch.** One restart should discriminate between several hypotheses, never one.
* **Watch your own context.** Around 200k: commit, rewrite this banner for the next
  agent, and stop. A clean handoff costs a few thousand tokens; riding the session to
  500k costs a few hundred thousand.
* **Prefer local deterministic code** over a model call, and over a subagent (which
  starts cold and re-derives context we have already paid for).
* **Keep prose short.** Assistant prose is the single largest line item at 41%.
* The rules of engagement below have not moved: **sandbox `d58e3f84-…` only, never the
  72.8h save, never modify or delete an existing save, re-parse your own output before
  it goes near the save folder.**

---

# Background: the throughput law, and VN-18 (`RuRuRuRu`, built and running)

> **CORRECTED 2026-09-05 by the Task 2 experiment above: this build delivers ONE
> lane, not twelve. The "12 boosted miners = one saturated space belt" law is not
> wrong about the game, but our contiguous 48-tile rectangle is not 12 units — it
> behaves as one. Read the section below as the design intent, not as measured fact.**

## The law that VN-17 got wrong and VN-18 gets right
**A `Layout_ShapeMiner` is not a space belt.** John's rule, confirmed against his
72.8h factory (144 miners, 432 `Layout_ShapeMinerExtension` -- *exactly 3 each* --
feeding 144 hub lanes):

> **1 miner + 3 boosters = ONE lane. TWELVE boosted miners = 12 lanes = one
> saturated space belt.** A full belt therefore costs **48 ore tiles**.
> Boosters chain node-to-node, each pointing at the next node towards the miner;
> up to 3 per miner. The same holds for fluid miners.

Corollaries, both learned the hard way this session:
* Contiguous `Layout_ShapeMiner` islands written with the wrong rotation are
  **silently rewritten by the game into `Layout_ShapeMinerExtension`** on load. Our
  first four "miners" beside the Vortex became one 4-tile unit. Check the layout
  back out of the save after every load.
* The six free ore tiles beside the Vortex can never exceed ~1.5 lanes. Anything
  that wants throughput has to move to a patch.

## VN-18 -- `RuRuRuRu` at full space belt (built, loaded, running)
`tools/build_rect_full_belt.py`. 118 islands, **all 118 accepted by the game
unchanged**. 70 pure `RuRuRuRu` tiles at x 18..27, y -12..-3 (previously unbuilt)
carry 12 boosted miners = 48 ore tiles, plus 22 tiles of belt run:

| block | miners | boosters | collector |
|---|---|---|---|
| S | (22..26, -3) R1 | rows -4/-5/-6, R1 | A |
| N | (19..23, -12) R3 | rows -11/-10/-9, R3 | B |
| M | (20,-7) (21,-7) R1 | L-chains along row -8 | A, via belt columns x=20,21 |

* **Collector A** (7 lanes): `RightTurn R1` cap at (26,-2), `LeftFwdMerger R2` under
  each feeder, west along y=-2, down x=3, west along y=-1 -> hub tile (0,-1) **EAST**.
* **Collector B** (5 lanes): `LeftTurn R3` cap at (23,-13), `RightFwdMerger R2` over
  each miner, west along y=-13, down x=0 -> hub tile (0,-1) **NORTH**.

Two collectors because no single straight row on a ragged patch touches 12 miners;
7 + 5 lanes is the same 12 lanes of shapes, landing on two edges the hub already wires.

### Space belt port rules -- measured off John's factory, none guessed
    Forward R                     travels on heading R  (0=+X E, 1=+Y S, 2=-X W, 3=-Y N)
    RightTurn R / LeftTurn R      enters on heading R, leaves on R+1 / R-1
    LeftFwdMerger R               main flow R, SIDE INPUT from the neighbour at R+1
    RightFwdMerger R              main flow R, SIDE INPUT from the neighbour at R-1
    Layout_ShapeMiner             WRONG BELOW -- see the correction under Task 2.
                                  The SENDERS' own R is the direction, and the band
                                  must sit on the edge it fires through. Island R is inert.
    Layout_ShapeMinerExtension R  points at the next node in the chain to the miner

### The Vortex, and why VN-17 was still worth it
The 3x3 `Layout_HUB` has 12 outward tile edges x 12 lanes = **144 lanes**, but only
the CENTRE tile's own perimeter feeds the mouth (senders at local x or y in 4..15),
so the eight off-axis edges must jog inwards. Rather than author that, VN-17 copied
**John's 4,272-building, 144-lane hub feed verbatim** out of the 72.8h save. Every
edge is now live, so any future machine just has to reach an edge port.

### Measured (backup-v104 -> v105, 353 s of playtime at 25x)
| shape | delivered | rate |
|---|---|---|
| `RuRuRuRu` | 1,104 -> **185,664** | **433.8 / s** |
| `CuCuCuCu` (VN-15, one unboosted miner) | +38,448 | 108.9 / s |
| `--SuSu--` (VN-16) | +8,484 | 24.0 / s |

**Open question, not yet answered:** Ru is 3.98x the single unboosted Cu miner --
suspiciously *exactly* 4x. Whether 12 boosted miners genuinely saturate the belt, or
something downstream caps us at 4 miner-equivalents, is unproven. Next session:
compare a per-collector count (feed A and B to different edges of *different* hub
tiles and read the two edges separately), or read a collector belt's cargo state to
see whether it is backed up.

---

# Still queued: the VN-16 stage C test (channel 789)


Shape algebra (measured, not predicted):

```
SuSuCu--   cut, keep delivered half  ->  --SuSu--      (WORKS, 107k delivered)
--SuSu--   rotate 180                ->  Su----Su      disjoint
stack the two                        ->  SuSuSuSu
```

Stage C is written in `tools/build_star_machine.py` and **deliberately disabled** —
`cutter_platform()` returns the working stage B. When enabled, every building places
correctly (verified cell-by-cell in the live game; the lift and the stacker both span
floors 0 and 1 as they should) and **all output stops**: the stacker waits on a second
input that never arrives.

**Prime suspect:** which side `Splitter1To2L`'s second output actually emits on. It
declares outputs on sides 0 and 3. If side 3 resolves to -Y rather than the +Y I
assumed, branch B is fed straight into the trash that catches the cutter's discarded
half — which would look exactly like this.

**Run it BATCHED.** Do not test one variant per build. Put `Splitter1To2LInternalVariant`
on one lane and `Splitter1To2LInternalVariantMirrored` (outs side 0 and side 1) on a
parallel lane in the SAME save, each feeding its own stacker, and let one restart
discriminate. Four sequential single-hypothesis cycles is what burned the last budget.

---

# Standing rules — the expensive ones, kept out of the archive on purpose


**A platform edge port is a 12-LANE GROUP:** band cells 8, 9, 10, 11 on EACH of floors
0, 1 and 2 — all twelve, or the port never connects. Every space-belt-fed platform in
John's 72.8h factory places all twelve; not one places a subset. A partial group fails
SILENTLY: the feeding space belt fills up (1,524 bytes of cargo state against an empty
474) and the platform behind it stays empty, with no error anywhere.

**Diagnostic signal:** cargo state on the OUTGOING space belt is meaningful. A
platform's own runtime-state record is NOT — VN-15's miner reads 30 bytes (the empty
form) while delivering 28,000 shapes. I misread that for several cycles.

## Rules of engagement (unchanged)

* **Sandbox only** (`d58e3f84-...`). **Never** the 72.8h save (`5589333c-...`) — read-only.
* **Never modify or delete an existing save.** Write a new one; undo is deleting a file.
* `CreateBuilding` sits under the interactive placement pipeline and does not appear to
  validate — our checks are the only thing between a generator bug and a corrupt map.
* **Re-parse your own output and run the size law before it goes near the save folder.**
  A round trip proves only that the writer agrees with the reader; both were wrong in
  the same place once and it crashed John's game.

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

---

# History

Everything superseded is in `docs/history/`, verbatim and in original order:

* `2026-09-05-progress-archive.md` — the first 1,138-line PROGRESS.md, from the
  VN-16 handoff back through the vision, Phase 1/2 validation, the live-bridge
  notes and the module inventory.
