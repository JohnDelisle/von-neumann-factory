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
