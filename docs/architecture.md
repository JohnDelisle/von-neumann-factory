# MAM architecture & design principles

## Goal

Read the shape the HUB currently requests (via **Goal Receiver**), and construct
**exactly that shape** on demand at **full space-belt throughput** (48 lanes).
Beautiful and symmetric first; efficient second (but not tangled).

## Why constructive (not generate-and-filter)

The world has **Goal Receiver** (requested shape as a wire signal) and **Virtual
Processing** (simulate cut/rotate/stack/analyze in the wire layer). Together they
let us *compute the build recipe* for any shape and drive a physical synthesizer
to make just that shape — far less waste than mass-producing variety and
filtering. Crystals are **not** unlocked, so we do not require them.

## Design principles (John's)

1. **Consistency** — every module speaks the same bus convention (see
   `conventions.md`): 12-lane bus (4×3), south-in / north-out, ports at the
   standard cells. Modules snap together without adapters.
2. **Clean & beautiful over tangled** — prefer symmetric, legible layouts even at
   a small efficiency cost. No spaghetti.
3. **Ramps to accelerate** — use belt ramps / launchers to speed shapes where it
   helps travel time. (Mechanic to apply and document as we go.)
4. **Two throughput flavors** — a 1-space-belt (12-lane) unit that tiles ×4 into
   a full-space-belt (48-lane) module.

## Reusing John's proven modules

His single-function modules already follow the bus convention and are trusted
components: **Rotator** (24× RotatorHalf, full 12-lane pass-through), **Pin
Setter** (PinPusher bank), **Half Destroyer** (CutterHalf, on a 1×2), **Painter /
Painter Small** (with fluid plumbing), **Trash** (sink), **Shape Filter** (logic +
compare + display). We compose these as black boxes wired by generated glue, and
only build new modules where a gap exists.

## Pipeline (constructive core)

Per quadrant of the target shape:

1. **Base supply** — full-speed feeds of the four primitive quadrant shapes
   (circle, rect, star, windmill), uncolored, plus paint fluids (R/G/B and mixed
   secondaries via color mixing).
2. **Quadrant isolator** *(Stage 1, first build)* — reduce each incoming base
   shape to a single chosen quadrant (`Cu------`), other corners empty. Built from
   Half Destroyer (cut) + Rotator (select surviving corner).
3. **Painter tap** — paint the isolated quadrant its target color (reuse Painter).
4. **Assembler** — stack four painted single-quadrant streams into one full
   4-quadrant layer (Straight Stacker); stack layers into the final shape.
5. **The brain** — Goal Receiver + Virtual Processing decode the requested shape
   code into per-lane (quadrant, color, layer) targets that drive stages 2–4.
6. **Parallelize** the validated 12-lane line ×4 to full space-belt speed.

## Build/test loop

Author module → John imports & reports (ideally a screenshot) → fix → commit.
Each stage is validated in isolation before it feeds the next.

## Open questions to resolve as we build

- Exact footprints & port cells of Cutter / Stacker / Painter (extract from
  John's modules as needed).
- Base-shape supply: where the map's shape/fluid patches are in this world, and
  how the kept vortex feeder network is arranged.
- Ramp/launcher mechanic specifics and where they most help.

---

## Working design — single-layer constructive MAM (agreed 2026-09-03)

Decisions with John: **start single-layer** (grow to multi-layer later),
**quarter throughput first** (12-lane / 1×1 unit, tile ×4 to 48 after it works),
**brain-driven color mixer** (one configurable paint path, any color on demand).

### Target
Build any **single-layer** shape the HUB requests: 4 quadrant positions
(NE/SE/SW/NW), each either empty or a (shape-type ∈ {circle, square, star,
windmill}, color ∈ 8 non-crystal). No crystals, no pins yet.

### Per-slot synthesis (4 slots, one per quadrant position)
Because base shapes are uniform (every quadrant of a circle is a circle), each
slot is simply:
1. **Shape-type mux** — 4→1 select the base shape for this slot (brain-gated;
   gate OFF if the slot is empty in the requested shape).
2. **Isolate** one quadrant → a single-quadrant piece at the SE position
   (our `VN-02` → `VN-03` → `VN-02` isolator).
3. **Rotate to position** — fixed per slot (0/1/2/3 × 90°) so the piece lands in
   this slot's target quadrant. (`VN-03`-style rotate; fixed, not brain-driven.)
4. **Paint** — brain-mixed target color (reuse `Painter` + a controllable color
   mixer). Uncolored = bypass paint.

### Assemble
Stack the 4 positioned+painted single-quadrant pieces → one full layer → deliver.
Relies on the Shapez mechanic that **stacking single-quadrant pieces at different
positions merges them into one layer** (each top quadrant falls to the empty
column below it). THIS IS THE KEY UNVALIDATED ASSUMPTION — validate first.

### The brain
Goal Receiver → requested shape code. Virtual Processing / logic decodes it into,
per slot: shape-type select (2 bits or gate) + color-mixer control. Drives the 4
muxes and 4 mixers. Build after the mechanical stages work.

### Throughput note
Single layer = 4:1 assembly (4 quadrant-syntheses per output shape). A 12-lane
output unit ⇒ ~48 lanes of internal quadrant synthesis. Build the quarter unit,
validate, then tile ×4 for full space belt.

### Module roadmap / status
- [x] Quadrant isolator: `VN-01` (1-lane proof), `VN-02`/`VN-03` (12-lane,
      launcher-optimized). Isolator = `VN-02` → `VN-03` → `VN-02`.
- [ ] **Assembler** (NEXT): validate stacking single-quadrant pieces → one layer,
      then a 4-quadrant layer assembler. Needs exact `StackerStraight` port layout
      (main vs "top/stack" input) — get a minimal 2-in→1-out stacker reference
      from John, like we did for launchers.
- [ ] Positioning: fixed per-slot rotate (reuse `VN-03` mechanics).
- [ ] Painter tap + controllable color mixer (reuse `Painter`/`Paint Mixer`).
- [ ] Shape-type 4→1 mux (brain-gated).
- [ ] Brain: Goal Receiver decode → per-slot type+color control.
- [ ] Base supply: map shape/fluid patch locations (read save or ask John).

---

## John's proven full-throughput ecosystem (use as black-box primitives)

Compose these validated modules with connecting glue rather than rebuilding
(architecture principle: compose black boxes). All are full-throughput, ¼-belt
(12-lane) or full-belt scale, launcher-optimized, with labeled I/O:

- **`Quad Splitter`** (Foundation_2x4): 1 shape input (¼ space belt = 12 lanes) ->
  4 quadrant outputs labeled **NE / SE / SW / NW** (opposite edge). `Full Belt Quad
  Splitter` = 4 of these + Demuxer + Overflow -> full belt.
- **`Demuxer`** (2x4_Flipped): normalizes/routes the NE-SE-SW-NW quadrant streams.
- **`Stacker`** (multi-platform, SpaceBelt I/O): full-throughput **2-input stacker**,
  inputs labeled **Bottom** + **Top** -> **Stacked** (also `Passthrough` /
  `USE ONE INPUT ONLY`). => the assembler is a CHAIN of 3 Stacker modules.
- **`Painter`** (2x4 + pipes): **Shapes** + **Paint** -> **Painted Shapes**.
- **`Overflow`** (1x1): eats excess to keep belts compressed.

### Revised assembler / synthesizer plan (quarter scale, uncolored first)
1. Base shape -> **Quad Splitter** -> NE/SE/SW/NW quadrant streams.
2. (Type select per position: brain-driven mux across base types — later.)
3. **Assemble** = chain 3 **Stacker** modules: Stacked(NE,SE) -> +SW -> +NW -> layer.
4. Validate a fixed-recipe reassembly first (e.g. quad-split a circle and stack it
   back), then a 2-type mix, then add type-select, then Painter, then the brain.

NOTE: my hand-built VN-04 (2-in stacker) and VN-05 (4-quad assembler) were mechanic
proofs; SUPERSEDED by John's `Stacker` module for the real full-throughput build.
Composition needs each module's foundation footprint + port map (extract next).


---

## Design philosophy: discrete-function platforms + blueprint-of-blueprints (John)

- **One function per platform.** Each discrete function (quad-split, stack, rotate,
  paint, demux, overflow, type-select, ...) is its own platform with its own
  blueprint. Do NOT fuse two functions on one platform (e.g. rotate+stack) UNLESS
  that fused function is itself a named MAM building-block.
- **Assemblies are blueprints of blueprints.** A complex machine is a multi-island
  blueprint that PLACES the discrete platforms and connects them with space belts
  (like `Full Belt Quad Splitter` = 4 Quad Splitters + Demuxer + Overflow + belts).
  Ship BOTH: the component-platform blueprints AND the assembled-machine blueprint.
- **Result:** a reusable component library (single-function platforms) + assemblies
  that compose them. Repo `blueprints/` holds both kinds; `build_modules.py` generates
  components and assemblies.

Capability needed for assemblies: place islands (foundation/space-belt tiles at
island X,Y,Z,R) and route SpaceBelt_* tiles between module ports. (Studying John's
multi-island blueprints to learn the island-grid + space-belt conventions.)

---

## >>> BIG FINDING (2026-09-03): John already has ~85% of the MAM built <<<

Decoding `Full Belt Any Shape Maker.spz2bp` (and `Quaded Filter` / `Filter` /
`Quaded Color Filter` / `Smart Filter`) changed the picture completely. **Most of
the "missing building blocks" PROGRESS.md listed already exist in John's library.**

### `Full Belt Any Shape Maker` == `MAM working` (same machine, two names)
Byte-level: identical island composition and building total (64 972), the second
just translated +1 in X. It is a **full-belt, single-layer, uncolored any-shape
synthesizer**, and it is **exactly VN-07 plus one platform** — the `Quaded Filter`.

Four identical lanes (one per quarter-belt), each:

```
mixed base shapes (1/4 belt, 12 lanes)
  -> Quad Splitter   (2x4_Flipped, 3097)   -> 4 quadrant streams (48 lanes)
  -> Demuxer         (2x4, 2739)           -> orientation normalized
  -> Quaded Filter   (1x4, 1096)  <<< THE BRAIN + PER-POSITION SELECT
  -> Stacker supporting empty quadrants
       (2 x "Fancy A+B" 2x4 + 3 x 2x2 stackers + Overflow 1x1)
  -> 1/4 belt of the requested shape
```
Plus 20 `Overflow` 1x1 sinks (eat rejected quadrants) and 4 `Trash` 1x1.
x4 lanes = full space belt in, full space belt out.

### What `Quaded Filter` actually is (the decode we thought we had to invent)
A `Foundation_1x4`, 4 bands of 12 lanes (48 total). Band order north->south =
**NW, SW, SE, NE**; band k occupies local `Y = 20k-20+8 .. 20k-20+11` (i.e. -12..-9,
8..11, 28..31, 48..51), EAST in (X17, R2), WEST out (X2, R2), floors L0-L2.
One `BeltFilterDefault` per lane (48 total) gates each lane.

Its logic block (local X3-16, Y15-23, L0) is **a target-shape decomposer**:
1. **Target shape signal in.** Today: 4 `ConstantSignalDefault` presets
   (`CuCuCuCu`, `RuRuRuRu`, `SuSuSuSu`, `WuWuWuWu`) selected by 4 `ButtonDefault`
   through a `LogicGateIf` priority chain. **These are a manual stand-in for the
   Goal Receiver — nothing else about the machine is hardcoded.**
2. **Decompose into 4 quadrant signals.** A symmetric `VirtualRotator` /
   `VirtualAnalyzer` fan at X8-12, Y17-20: four paths applying 0 / 1 CW / 1 CCW /
   2 rotations, each into a `VirtualAnalyzer` (which yields the NE quadrant), then
   the inverse rotation back. Result: the target shape's NE, SE, SW, NW quadrants
   as four independent shape signals.
3. **Distribute.** 6 `WireTransmitterSender`/`Receiver` pairs carry each band's
   quadrant signal to that band's 12 `BeltFilter`s.

=> **A band passes only quadrants matching the corresponding quadrant of the
target shape.** The stacker then assembles exactly the requested shape, and empty
target quadrants simply pass nothing (which is why the empty-quadrant-tolerant
stacker is the one wired in).

**So the per-position type SELECT and the shape-decode brain are BOTH already
built and validated.** What's hardcoded is only *where the target shape comes from*.

### `Quaded Color Filter` — per-position colour select, also already built
Same `Foundation_1x4` 4-band shape, but **4 independent selectors, one per band**,
each choosing between `r`, `g`, `b` and `null` (`ConstantSignal` tags `07 01 <char>`
and the bare `05` null). It **filters painted quadrants by colour per position** —
it does not paint. Only 3 primaries + none, not the full 8-colour palette.

### `Smart Filter` / `Shape Filter` — the Goal Receiver plumbing, already proven
Both contain `ControlledSignalReceiverInternalVariantMirrored` with config
`00 00 00 02` (an int32 channel/slot = 2, identical in all 18 instances across
`Shape Filter`, `Smart Filter` and `Shitty Mam v1`). `Shape Filter` pairs it with
12 `BeltReader` + 12 `LogicGateCompare` + 12 `BeltFilter` = "pass only the shape
the HUB currently wants". **This is the Goal-Receiver wiring we said we had to
design.** (Confirm with John exactly what the `2` selects.)

---

## Revised architecture (proposal, 2026-09-03) — needs John's call

The honest reframing: **architecture.md's "constructive vs generate-and-filter"
dichotomy was the wrong axis.** John's machine is *constructive at the shape level*
(it stacks the output from selected quadrants) and *filter-based at the quadrant
level* (it picks the quadrants it needs out of a mixed supply). That hybrid is
already built, full-belt, and mostly validated.

### The remaining gap list (real, after the finding above)
| # | Gap | Status |
|---|-----|--------|
| 1 | Target shape from the HUB, not buttons | `ControlledSignalReceiver` proven in `Shape Filter`; needs grafting into `Quaded Filter` |
| 2 | Colour | `Quaded Color Filter` filters r/g/b/none per position; needs a coloured supply, and 8 colours not 3 |
| 3 | Multi-layer | unbuilt; needs layer decompose + a layer stacker chain |
| 4 | Base supply | mixed uncoloured belt of the 4 base types; patches in the working save still TBD |
| 5 | Quadrant waste / throughput | with a 4-type mixed supply each band rejects ~3/4 of arrivals |
| 6 | Goal-change transient | belts full of old quadrants when the HUB request changes |
| 7 | Pins / crystals | out of scope for v1 (no crystals in the working save) |

### Proposed sequencing (smallest validated step first, per PLAYBOOK)
- **Step 1 — `VN-10`: lane-fix + adopt `Full Belt Any Shape Maker`.** It embeds 4
  copies of the buggy `Fancy A+B Side Overflow` (the "SHIT" labels are still in
  there). Regenerate it from code on top of `load_fixed_stacker_islands()`. Cheap,
  purely mechanical, and gives us the whole machine under version control.
- **Step 2 — `VN-11`: Goal-driven `Quaded Filter`.** Replace the button +
  `ConstantSignal` bank with `ControlledSignalReceiver` (copy the exact wiring from
  `Shape Filter`). One platform changed; everything downstream untouched. **This is
  the single edit that turns "Any Shape Maker" into a MAM.**
- **Step 3 — validate end-to-end uncoloured**, single layer, against live HUB goals.
- **Step 4 — colour.** Decide paint-before-assembly vs filter-a-coloured-supply
  (see the open question below).
- **Step 5 — multi-layer.**

---

## What VN-12 actually is: a ONE-LAYER engine (analysis 2026-09-03)

John asked the two right questions: what feeds the Quad Splitters, and does this
only make one layer? Traced from the island topology of `Full Belt Any Shape Maker`.

### The four lanes share ONE input — they are throughput parallelism, not type
The machine has a **single** full-belt entry point at island `(12,-6)` heading west.
It turns north up X11, west along Y-11, then south down the **X9 distribution
column**, which peels off one lane at each `SpaceBelt_RightFwdSplitter`
(`(9,-10)`, `(9,-4)`, `(9,2)`) with the tail turning at `(9,8)` into the fourth.
Outputs mirror this on the west side: three `SpaceBelt_TripleMerger`s recombine the
four lanes into one belt, which in this blueprint runs into 4 `Trash` platforms —
test scaffolding, like VN-07's sinks.

**So "one shape type per Quad Splitter" is not how it works, and would not work.**
Each lane is a complete, independent shape maker: its own splitter, demuxer,
filter and stacker cluster. There is **no cross-lane path**, so a lane fed only
circles can only ever emit shapes built from circle quadrants. Every Quad Splitter
must therefore receive a stream containing **every type the target needs** — a
mixed belt.

### The consumption ratio = the number of DISTINCT types in the target layer
A base shape is uniform, so one circle yields a `Cu` quadrant at all four
positions. The target needs `Cu` at some subset S of positions, so one circle
contributes |S| useful quadrants and the rest go to the `Overflow` sinks. Summing
over types, the subsets partition the 4 positions — so:

| Target layer | Inputs per output | Example |
|---|---|---|
| 1 distinct type | **1:1** | `CuCuCuCu` — a pass-through |
| 2 distinct types | **2:1** | `CuCuRuRu` |
| 3 distinct types | 3:1 | `CuCuRuSu` |
| 4 distinct types | **4:1** | `CuRuSuWu` |

This is **inherent to decompose-then-select**, not a flaw in the design. Full belt
in gives between a full belt and a quarter belt out, depending on the goal.

### YES — it builds exactly ONE LAYER
One Quad Splitter decomposes one shape into 4 quadrants; the stacker merges 4
**disjoint** single-quadrant pieces, and by the rigid-body rule disjoint pieces
merge into the **same** layer. Nothing in VN-12 ever stacks a full layer onto
another full layer, so the output is strictly single-layer.

### Proposed multi-layer architecture
The rigid-body rule also gives the answer: stacking two **overlapping** shapes puts
the top one on a NEW layer. So a full MAM is

```
  goal -> layer 1 target -> [VN-12 engine] --+
          layer 2 target -> [VN-12 engine] --+-> stack L2 on L1 -> stack L3 -> ...
          layer 3 target -> [VN-12 engine] --+
          layer 4 target -> [VN-12 engine] --+
```

**N single-layer engines + a layer-stacking chain**, where the chain is plain
2-input stackers (John's `Stacker`) fed two complete layers that overlap.

Two consequences worth deciding on:
1. **Cost scales with layers.** A 4-layer goal needs 4 engines, each eating up to a
   full belt: up to 16 belts of base shapes per belt of output.
2. **The brain needs a layer-extract.** Each engine must be told *layer k of the
   goal*, not the whole goal. Today the `Quaded Filter` decomposes one shape signal
   into 4 quadrant signals; we need to feed it one layer at a time. **Open: which
   in-game virtual building isolates a layer?** John's library only uses
   `VirtualRotator` and `VirtualAnalyzer`; the game may have more we haven't seen.

## AGREED DIRECTION (John, 2026-09-03): pure-type lanes, merged per position

John's proposal, confirmed correct: feed `CuCuCuCu` / `RuRuRuRu` / `SuSuSuSu` /
`WuWuWuWu` into four separate Quad Splitters, let each lane's `Quaded Filter` match
the goal layer, then **merge the four lanes into ONE stacker**.

**Note this is a re-plumb, not just a supply change.** VN-12 as built has ONE input
(split four ways down the X9 column) and ONE output (merged by three
`TripleMerger`s). The new unit needs four *separate* inputs and a per-position
merge before a single stacker.

### The merge is the elegant part — and it's cheap
Merge **band-by-band, not lane-by-lane**: every lane's NE band into the stacker's NE
input, every lane's SE band into SE, and so on. For any goal, exactly **one** lane
passes on a given band (the lane whose type the goal wants at that position) and the
other three are silent — so each merged stream carries exactly the right quadrant at
full rate, with no arbitration and **no dependence on the goal**. Four 4-way merges
of 12-lane space belts = ~12 merger tiles. The `Quaded Filter` platforms need **no
change at all** — they already all read the same goal on channel 123.

### Yes — FOUR units per layer for full-belt output
Each `Stacker supporting empty quadrants` consumes 4 x 12 lanes of quadrants and
emits **12 lanes (1/4 belt)** of assembled shapes. (Confirmed by VN-12's own
topology: four stacker clusters merge into one output belt.) So a full belt of one
layer = **4 units**, each eating 1/4 belt of each of the four base types => **4 full
belts of base shapes in, 1 full belt of single-layer output**.

### Cost, from real building counts
Per unit (1/4 belt of one layer, uncoloured):

| Component | x | Buildings | Cells |
|---|---|---|---|
| `Quad Splitter` | 4 | 12,388 | 32 |
| `Demuxer` | 4 | 10,956 | 32 |
| `Quaded Filter` | 4 | 4,328 | 16 |
| `Stacker supporting empty quadrants` | 1 | 7,926 | 29 |
| `Overflow` sinks | ~20 | 6,300 | 20 |
| **Total** | | **~41,900** | **~129** |

**vs VN-12's 64,972 for the same 1/4 belt** on a 4-distinct-type goal — so the
re-plumb is **~1.55x cheaper**. The whole saving is using **one** saturated stacker
instead of four running at quarter utilisation; the splitter/demuxer/filter front
end (27.7k) is identical either way and is **irreducible** — a 4-type layer
fundamentally needs four source streams, whether taken in parallel (John's design)
or interleaved in time (VN-12's mixed belt).

Scaling out:

| Target | Buildings |
|---|---|
| 1/4 belt, 1 layer | ~42k |
| Full belt, 1 layer | ~168k |
| Full belt, 4 layers + layer-stacking chain | ~765k |
| **+ paint (4 painters/unit @ 3,041)** | **~960k** |
| **1/4 belt, 4 layers, painted** | **~240k** |

**The dominant lever is throughput, not cleverness.** Full-belt 4-layer coloured is
~960k buildings; the same machine at 1/4 belt is ~240k — 4x smaller, and 1/4 belt of
4-layer shapes is still a lot of product. **Recommend sizing for demand and scaling
later**; the design tiles cleanly either way.

### The scale-up: replicate the WHOLE machine, not the single-layer engine
Confirmed: one unit emits a **saturated 1/4 belt**, so **4 replicas = one full space
belt**, fed by 4 full belts of base shapes (one belt per type). Note the difference
between plumbing and saturation — VN-12 already has full-belt output *plumbing*, but
on a 4-distinct-type goal it runs at 25% density. The redesign's win is a saturated
1/4 belt from one stacker instead of a quarter-full belt from four.

**Make the replication unit the complete painted, multi-layer machine** — not the
single-layer engine. Stacking layers at 1/4 belt and then replicating 4x costs
exactly the same as replicating each layer 4x and then stacking at full belt (12
layer-stack stages either way), but it means we build and validate ONE complete
~220k-building MAM end to end before committing to ~880k. That is the PLAYBOOK's
"validate narrow, then scale" applied at the factory level.

### Corrected cost: the layer-stack chain is cheap
Earlier estimate used a whole `Stacker supporting empty quadrants` cluster (7,926)
per layer join. Wrong — layer stacking only needs **2 inputs**, and a single
`Foundation_2x2` stacker platform (**1,361 buildings**, `Bottom` east + `Top` north
-> `Stacked` west) does that at 12 lanes. So joining 4 layers is **3 x 1,361 =
~4,100**, not ~24k. (Not yet validated standalone — worth a small test blueprint.)

Revised: **1/4 belt, 4 layers, painted ~= 220k buildings**
(4 x 41.9k engines + 4 x 4 x 3,041 painters + 3 x 1,361 layer joins).

### !! Layer stacking is only safe when the upper layer is supported
Rigid-body again: an upper-layer quadrant with **no occupied quadrant beneath it**
falls through and merges into the lower layer instead of forming a new one. So
`CuCuCuCu` + `--Ru--Ru` stacks correctly (both Ru sit on Cu), but `Cu--Cu--` +
`--Ru--Ru` would collapse into a single layer. This matches the game's own shape
support rule, so real goal shapes should be safe — **but confirm with John before
the layer chain is built.**

### !! Paint has a brain problem, not just a plumbing problem
Painting per position **after** the merge and before the stacker is the cheap
placement — 4 `Painter`s per unit, each needing one colour signal, and the goal is
already decomposed into 4 quadrant signals.

**But the `Quaded Filter` matches the goal quadrant INCLUDING its colour.** With an
uncoloured supply and a goal of `Cr` (red circle), every band would reject `Cu` and
the machine would output nothing. So the filter must be fed a **colour-stripped**
goal while the painters get the colour.

=> **Open question: how do we strip colour from a shape signal in the wire layer?**
If no virtual building does it, the fallback is the filter-based route (a
pre-coloured supply + `Quaded Color Filter`), which multiplies the supply by the
number of colours. **This decides the colour architecture — worth checking the
in-game virtual building list before committing.**

---

## PHASED BUILD PLAN (John, 2026-09-03) + the Phase 1 circuit

**Phases**: 0 base supply -> 1 single-layer shape -> 2 single-layer paint ->
3 multi-layer -> 4 pins/supports -> 5 scale 4x to full belt.
(John proposed 1-4; **Phase 0 and Phase 5 added** — the machine can't run
continuously without four uniform base-shape belts, and the 4x replication is real
work. Cross-cutting, not a phase: the **goal-change flush** — stale quadrants sit on
the belts when the HUB request changes.)

### The complete virtual (wire-layer) building list
Extracted from `shapez 2_Data/resources.assets` — 98 `*InternalVariant` building ids
in total, of which the virtual ones are:

| Building | Use to us |
|---|---|
| `VirtualUnstackerDefault` | **layer extract — Phase 3 unblocked** |
| `VirtualPainterDefault` | **colour normalisation — Phase 2 unblocked** |
| `VirtualAnalyzerDefault` | quadrant extract (already used by the filter) |
| `VirtualRotatorDefault` / `CCW` | rotate a shape signal (already used) |
| `VirtualHalfCutterDefault`, `VirtualHalvesSwapperDefault` | cut/swap halves |
| `VirtualPinPusherDefault` | Phase 4 |
| `VirtualCrystalGeneratorDefault` | out of scope (no crystals in this save) |

Also present and not yet used: `ControlledSignalTransmitter` (the sender that pairs
with our channel-123 receiver), `WireGlobalTransmitterReceiver`, and
`LogicGateAnd/Or/XOr` alongside the `If/Not/Compare` John already uses.

### >>> Phase 1 needs NO new circuit <<<
With each lane fed a uniform uncoloured `TTTT`, band `P` of lane `T` carries exactly
one thing: **"T at position P"**. The existing fan already drives that band with
**Q_P = the goal's quadrant at position P**, as a single-quadrant shape. The
`BeltFilter` passes on equality, so

```
band P of lane T passes  <=>  "T at P" == "goal[P] at P"  <=>  goal[P] == T
```

which is precisely the wanted behaviour, for all four lanes, from the **unmodified**
goal-driven `Quaded Filter`. Phase 1 is therefore **pure space-belt re-plumbing**:
cut the X9 distribution column into four separate inputs, and merge the filter
outputs band-by-band into one stacker.

**Caveat — that holds only for an uncoloured, single-layer goal.** A real level-107
HUB goal is coloured and multi-layer, and then `Q_P` matches no uncoloured
single-quadrant item and the machine emits nothing. So Phase 1 validates against a
hand-set simple goal; running against the live HUB needs the conditioner below.

### The GOAL CONDITIONER — one small block, serves Phases 1-3
Sits between the Goal Receiver and the existing rotate/analyze fan.

```
   Vortex goal (ch.123)
        |
        v
   [VirtualUnstacker] x k   -> isolate layer L          (Phase 3; pass-through in Phase 1)
        |
        v
   [VirtualPainter] <- const colour X                   (colour normalisation)
        |
        v
   existing rotate/analyze fan  ->  Q_P^X   (4 bands, all forced to colour X)
        |
        v   per band P:
   Compare( Q_P^X , const "T at P painted X" )  ->  bool
        |
   If( bool ) -> const "T at P UNCOLOURED"      -> band P's BeltFilters
```

**Why painting both sides works:** the painter overwrites whatever colour the goal
carries, so the comparison becomes colour-blind, while the value the `If` emits is
the *uncoloured* constant the physical uncoloured items actually match. Empty goal
quadrants paint to empty, fail the compare, and emit null — bands pass nothing,
which the empty-tolerant stacker already handles.

**Size: ~18 cells** — 1 `VirtualPainter` + 1 colour constant + 4 x (`Compare` +
`If` + 2 constants). The eight shape constants are **fixed per lane** (`Cu`/`Ru`/
`Su`/`Wu` at each of the 4 positions), so it is one generated blueprint parameterised
by type — trivial from `build_modules.py`.

**It fits.** John's goal-driven filter has a contiguous free block at
**X2-12 x Y24-26 (33 cells)** on L0, plus X2-12 x Y13-14, exactly where the preset
bank used to be.

For Phase 2 the same painter gives the colour signal the physical `Painter`s need;
for Phase 3 the unstacker chain feeds one conditioner per layer engine.

### Port map: RESOLVED — `For Claude Wiring Shapes.spz2bp` (John, 2026-09-03)
Every logic/virtual/transmission building on one `Foundation_1x2`, constants on the
inputs and displays on the outputs. Full table in conventions.md. The three that
matter here, all **1x1**:

- **`VirtualPainter`** — shape from **behind**, colour from the **left**, out **forward**.
- **`VirtualUnstacker`** — in from behind, **two** outputs: **forward + left**.
- **`VirtualAnalyzer`** — in from behind, **two** outputs: **forward + left**
  (the second output is what the existing fan never uses).
- **`LogicGateCompare`** — inputs **left and right**, out forward, config byte `01`.
- **`LogicGateIf`** — value from **behind**, condition from the **side**, out forward.

### Verified insertion point for the colour normaliser
The painter goes **in the receiver's own wire column**: John's goal-driven filter
runs a wire north up X4 from the receiver output at `(4,20)`. Replace the wire cell
at **`(4,18)` with `VirtualPainter` R3** — its shape input is then the wire below at
`(4,19)`, its output feeds the existing `(4,17)` junction — and put the colour
`ConstantSignal` at **`(3,18)` R0**, which is free. **A two-cell change.**

The four per-band `Compare`/`If` blocks (16 cells) go in the contiguous free block at
**X2-12 x Y24-26**. *Authoring detail still to settle:* exactly where to tap each of
the four band signals out of John's fan-to-transmitter routing — four cuts, to be
chosen when the blueprint is written, not guessed now.

### Cheaper alternative worth weighing: pure-type lanes, merged before the stacker
Instead of one mixed belt into four independent lanes, give each lane a **pure**
base type and merge the four lanes' surviving quadrant streams into **one** stacker.
The ratio is unchanged (still 1:1 .. 4:1), but the supply is far easier — four
single-type belts instead of one perfectly-mixed one — and each type's supply can
be throttled to demand instead of mined and thrown away. Costs a re-plumb of the
merge stage. **Worth John's opinion before either path is built.**

---

### OUTCOME: built and validated in-game, 2026-09-03
`VN-12 MAM goal driven` works. The constructive-vs-generate-and-filter debate this
document opened with was the wrong axis: the machine is **constructive at the shape
level** (it stacks the output from selected quadrants) and **filter-based at the
quadrant level** (it picks the quadrants it needs out of a mixed supply), and that
hybrid was already 85% built in John's library. What we actually contributed was
the lane fix, the decode of how it works, and the composition — not a new design.

The one platform John had to build himself was the goal-driven `Quaded Filter`
front end (`For Claude Filter with Signal.spz2bp`), after two failed attempts on
our side to place the 3x3 Goal Receiver.

### Decisions taken (John, 2026-09-03)
- **Build VN-10 then VN-11.** Both done, plus `VN-12` = the two combined = the MAM.
- **Colour = paint per quadrant stream**, not filter-a-coloured-supply. A
  brain-controlled `Painter` goes between the `Quaded Filter` and the stacker on
  each quadrant stream. Needs a signal-driven paint selector, which doesn't exist
  yet — that's the next real design problem. `Quaded Color Filter` stays as the
  filter-based fallback if the paint selector turns out ugly.
- **`ControlledSignalReceiver` config `2` = a HUB goal slot index.**

### Still open
- **Supply mix vs waste.** A single mixed belt makes every band throw away ~3/4 of
  what it sees. Alternative: a signal-driven type router upstream so each Quad
  Splitter is fed the type that lane needs. Worth it, or is overflow-and-recycle
  fine at this scale?
- **Multi-layer**: is v1 single-layer, or do we design the layer stack in now?
- **`Full Belt Any Shape Maker` vs `MAM working`** — which name survives? (They're
  the same machine; we should keep one.)
- **Goal-change transient**: stale quadrants sit on the belts when the HUB request
  changes. Tolerable, or does it need a purge?
