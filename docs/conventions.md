# Shapez 2 formats & conventions (reverse-engineered)

Game version at time of writing: **1.2.0-rc3**, save format **V1138**.

## Blueprint file format (`.spz2bp`)

A blueprint file is a single-line string:

```
SHAPEZ2-<fmt>-<base64( gzip( JSON ) )><suffix>
```

- `<fmt>` — format tag. Current game exports **5**.
- base64 is **standard** (`A–Z a–z 0–9 + /`, `=` padding).
- `<suffix>` — the current game appends `[]_2$`; older exports use just `$`.
  Both import. **Decode** by taking only the leading base64 run
  (`[A-Za-z0-9+/=]+`) so the suffix is ignored. **Encode** we emit `[]_2$`.
- JSON top object: `{"$type": "…SerializableBlueprint…", "V":1138, "BP": {...}}`.

Two `BP` shapes:
- **`Building`** — just building entries (pastes onto existing platforms).
- **`Island`** — platform tiles, each an island entry with a nested `Building`
  blueprint (`"B"`). This is what brings its own platforms.

Entry schemas (verbose form the current game emits):
- Island entry: `X,Y,Z` (island grid), `R` (0–3), `T` (island type, e.g.
  `Foundation_1x1`), `S`, `C`, `B` (nested Building blueprint or null).
- Building entry: `X,Y` (cell in platform grid), `L` (floor 0–2), `R` (0–3),
  `T` (building type), `C` (base64 config, or null).

## Savegame format (`.spz2`)

A **ZIP archive**. JSON entries: `savegame.json` (version, playtime,
`StructureCount`, difficulty, seed, name), `research.json` (unlocked upgrade
IDs, player level), `local-player.json` (viewport, tutorial flags). Binary
entries: `maps/main/buildings/*.bin`, `maps/main/islands/*.bin`,
`resource-chunks.bin`, `statistics.bin`, etc. (custom binary — not yet parsed).

## Coordinate & rotation convention (confirmed in-game)

- **+X = East (right), +Y = South (down).**
- `R` ∈ {0,1,2,3} steps **90° clockwise**. Forward belt flow:
  R0 = East, R1 = South, R2 = West, R3 = North.
- Belt turn: `BeltDefaultLeftInternalVariantMirrored` at R0 turns **East→South**
  (a right/clockwise turn). `BeltDefaultLeftInternalVariant` is the left turn.

## Platform grid

- A **1×1 platform** (`Foundation_1x1`) is a **20×20** cell grid; buildable
  region roughly **X,Y ∈ [2,17]**. **3 floors** (L0–L2).
- Larger foundations exist: `Foundation_1x2`, `1x4`, `2x2`, `2x3`, `2x4` and
  `_Flipped` variants; plus special layout islands like `Layout_ShapeMiner`
  (+`Layout_ShapeMinerExtension`), fluid miner, train stations, etc.

## The bus convention (John's standard — we build to it)

- A **bus lane group = 4 columns (X 8–11) × 3 floors (L0–2) = 12 belt lanes.**
  This equals **one space-belt input's** worth of throughput.
- Standard pass-through module: bus enters the **south** edge (Y17, ports facing
  north, R3) and exits the **north** edge (Y2). Trash-style sinks take the bus on
  the **west** edge (X2, R0).
- Ports are `BeltPortReceiverInternalVariant` (input) / `BeltPortSenderInternalVariant`
  (output), one per lane per floor.

## Throughput model

- **1 space-belt input = 12 lanes** (4×3).
- **Full space belt = 4 inputs = 48 lanes.**
- Modules come in a **1-input (12-lane)** flavor and a **4-input (48-lane)**
  flavor; design the 12-lane unit so it tiles ×4 cleanly.

## Building type IDs (extracted from John's library — partial)

Belts: `BeltDefaultForwardInternalVariant`, `BeltDefaultLeftInternalVariant`,
`BeltDefaultLeftInternalVariantMirrored`. Ports:
`BeltPortSenderInternalVariant`, `BeltPortReceiverInternalVariant`. Routing:
`Splitter1To2LInternalVariant(+Mirrored)`, `Merger2To1LInternalVariant(+Mirrored)`,
`Merger3To1InternalVariant`, `MergerTShapeInternalVariant`,
`SplitterOverflowLInternalVariant(+Mirrored)`. Processing:
`CutterDefaultInternalVariant(+Mirrored)`, `CutterHalfInternalVariant`,
`RotatorOneQuadInternalVariant`, `RotatorOneQuadCCWInternalVariant`,
`RotatorHalfInternalVariant`, `StackerStraightInternalVariant`,
`PainterDefaultInternalVariant(+Mirrored)`, `PinPusherDefaultInternalVariant`,
`TrashDefaultInternalVariant`. Vertical: `Lift1UpForwardInternalVariant`,
`Lift1DownForwardInternalVariant`, etc. Fluids: `PipeForwardInternalVariant`,
`FluidPortReceiver/Sender`, `FluidStorageDefaultInternalVariant`,
`PumpDefaultInternalVariant`. Wires/logic: `WireDefaultForwardInternalVariant`,
`WireDefaultJunctionInternalVariant`, `LogicGate*`, `ConstantSignalDefaultInternalVariant`,
`BeltReaderDefaultInternalVariant`, `VirtualRotator/AnalyzerDefaultInternalVariant`,
`ControlledSignalReceiverInternalVariant`. Space: `SpaceBelt_Forward`,
`SpaceBelt_LeftTurn`, `SpaceBelt_RightTurn`, `SpaceBelt_*Splitter/Merger`,
`SpacePipe_*`, `Rail_*`.

## Cutter / Half Destroyer mechanics (confirmed)

- Cut is **always vertical (east/west)**; building rotation does NOT change which
  halves are processed.
- **Half Destroyer** (`CutterHalfInternalVariant`): destroys the **west** half,
  keeps the **east** half. 1 in, 1 out, 1x1x1.
- **Full Cutter** (`CutterDefaultInternalVariant`): east half -> main output,
  west half -> secondary output. 1x2x1.
- Quadrants NE,SE,SW,NW; east half = NE+SE, west half = SW+NW.
- **Isolate one quadrant:** HalfDestroy (-> NE,SE) -> Rotate 90 CW -> HalfDestroy
  (-> a single quadrant). Pre-rotate the shape to choose which original quadrant
  survives.

## Belt launchers / catchers (speed, not throughput)

- A **belt launcher** serializes as `BeltPortSenderInternalVariant` and a **catcher**
  as `BeltPortReceiverInternalVariant` -- the SAME types as platform edge ports. The
  game treats a port as a launcher/catcher when it sits **mid-platform** (not on the
  Y2/Y17 edge). No config (`C`=null); `R` = launch direction (R3 = north).
- A launcher throws to the nearest catcher **ahead in its column**, across a **1-4 tile
  gap** (leave the gap cells empty). Same items/min as belts -- they cut **traversal
  time**, not throughput.
- Use them to replace **straight belt runs** only; the dense butterfly (turns, splits,
  cutters) stays as belts. See `VN-02` (John's launcher pass): middle lanes X9/X10 use
  the full 4-tile hop, outer lanes the shorter hops.

## Module widths vary in John's library (don't assume uniform)

- **Rotator, Pin Setter**: full **12-lane bus** (cols X8-11, floors L0-2),
  south-in (Y17, R3) / north-out (Y2, R3).
- **Half Destroyer**: only **4 lanes, L0**, west-in on a 1x2 / south-out.
- **Trash**: 12-lane sink, west-in (X2, R0).
- Standard going forward: **12-lane bus (4x3), purpose-built modules**.

## Belt launchers & catchers (reverse-engineered 2026-09-03)

- A **belt launcher** is a `BeltPortSenderInternalVariant` and a **catcher** is a
  `BeltPortReceiverInternalVariant` placed **mid-platform** (same building type as
  the platform edge I/O ports). A launcher fires the shape across a gap to the
  next catcher in line; **span 1-4 tiles** (never zero gap). Same throughput as a
  belt (60-180/min by tier) - they cut **travel time**, not items/sec.
- Use to replace straight belt runs. Keep layouts legible; avoid launcher webs
  unless performance needs it (John's rule).

## Stacker (`StackerStraightInternalVariant`) ports (from John's ref)

- 1x1 building, R = facing (R3 = output North). Inputs:
  - **Bottom (main)** shape: from directly **behind** (South when R3), same floor.
  - **Top (stack)** shape: from the cell **directly above** it (floor L+1) - route
    the second stream up one floor (Lift1UpForward) and over the stacker cell.
  - **Output**: forward (North when R3), same floor = bottom stacked, top on top.
- Stacking is rigid-body: the top shape descends until ANY quadrant collides.
  Disjoint pieces (no shared occupied quadrant) merge into ONE layer; any overlap
  puts the whole top shape on a NEW layer above. => assemble a layer only from
  single-quadrant pieces at DISTINCT positions.
- **Top-feed geometry (validated)**: to feed a stacker's top port at (sx,sy,L1),
  route the top shape on L0 to the stacker's east, then `Lift1UpForwardInternalVariant`
  at (sx+1, sy+1, L0, R2) lifts it to (sx, sy+1, L1), and a
  `BeltDefaultLeftInternalVariantMirrored` at (sx, sy+1, L1, R2) turns it north into
  (sx, sy, L1). Feeding the top port sideways on L1 (no lift) does NOT connect.


## Platform edge port bands (1x1, confirmed)

Edge ports (space-belt / platform-to-platform I/O) exist ONLY on the 4-lane band
of each edge, per floor:
- NORTH (Y2) and SOUTH (Y17): lanes at X = 8,9,10,11
- EAST (X17) and WEST (X2): lanes at Y = 8,9,10,11
A blueprint with a port off these bands will NOT stamp (red X). Larger foundations
have their own bands (TBD). => a 1x1 has at most 4 lanes x 3 floors = 12 port-lanes
per edge-direction.
## Assemblies: island grid + space belts (from John's Stacker module)

A multi-platform machine ("blueprint of blueprints") is an **Island** blueprint whose
entries are:
- **Foundation platforms** (`Foundation_2x2`, `_2x3`, `_2x4`, `_1x1`, ... with `_Flipped`
  variants), each a single island entry at island-grid `X,Y,Z,R` carrying its own
  building blueprint `B` (the function's internals). A 2x2 foundation is ONE entry
  occupying a 2x2 block of island cells.
- **Space-belt tiles** routing between platform ports, 1x1 island tiles:
  `SpaceBelt_Forward`, `SpaceBelt_LeftTurn`, `SpaceBelt_RightTurn`,
  `SpaceBelt_LeftFwdSplitter`, `SpaceBelt_RightFwdSplitter`,
  `SpaceBelt_LeftFwdMerger`, `SpaceBelt_RightFwdMerger`, each at island `X,Y,Z,R`.
  (Fluids use `SpacePipe_*`; rails use `Rail_*`.)
- Island coords are integer grid units (each unit = one 1x1 platform footprint);
  `Z` is elevation (0 = ground). `R` orients the tile/platform.

To build an assembly: place the function foundations, then lay `SpaceBelt_*` tiles
connecting each source platform's output port band to the next platform's input band.

## Multi-unit foundation footprint & port bands (extracted 2026-09-03, `Quad Splitter.spz2bp`)

- **Island footprint = literal `WxH` from the type name, NOT rotated by `R`.** A
  `Foundation_2x4` island entry at `(ix,iy,iz,R)` occupies island cells
  `X∈[ix,ix+1], Y∈[iy,iy+3]` regardless of R (confirmed: adjacent SpaceBelt tiles in
  John's `Full Belt Quad Splitter.spz2bp` sit exactly 2 columns east of a `2x4`'s `ix`).
- **A multi-tall foundation repeats the 1x1 port-band pattern once per island-row.**
  Building-local coordinates run continuously across the whole foundation (NOT
  reset per row): row `k` (0-indexed from `iy`) occupies local `Y ∈ [k*20-38, k*20-38+19]`
  when the foundation is vertically centered around local Y≈0 (John's `Quad Splitter`
  is 4 rows: local Y bands `[-38,-21]`,`[-18,-1]`,`[2,17]`,`[22,37]`, i.e. row0..row3 =
  island rows `iy+0..iy+3`). Local edge-band convention (X/Y 8-11 within a row, at the
  row's own local 2/17 boundary) still applies per-row.
- **`Quad Splitter` (`Foundation_2x4`, 3097 buildings) port map** — confirmed by
  decoding John's reference (treat internals as a black box; only ports matter):
  - **Input**: EAST edge (local X=37), **row3 only** (island row `iy+3`, local Y
    28-31), `BeltPortReceiverInternalVariant`, R=2 (flows west into the platform).
    12 lanes (4 cols x 3 floors) = one quarter-belt in, matching "1/4-belt in".
  - **Output**: WEST edge (local X=2), **all 4 rows** (island rows `iy+0..iy+3`,
    local Y bands as above), `BeltPortSenderInternalVariant`, R=2 (flows west out).
    Each row = its own independent 12-lane band = one quadrant's output (4 x 12 =
    48 lanes total, spread across 4 separate island cells on the shared west edge).
  - So in island terms: input arrives at `(ix+2, iy+3, iz)` heading west; the 4
    outputs depart from `(ix-1, iy+0..iy+3, iz)` heading west, one quadrant per row.
  - Internal receivers at local Y 5/7 (interior, not on-edge) are launcher/catcher
    pairs, not cross-platform ports — ignore them; they're inside the black box.

## Stacker is NOT a single platform (discovered 2026-09-03)

`Stacker.spz2bp` is itself a **28-island assembly**: 4 chained foundations
(`Foundation_2x2`/1361 bldgs -> `Foundation_2x2`/1386 -> `Foundation_2x3`/1652 ->
`Foundation_2x4`/1918, ~6300 buildings total) wired together with `SpaceBelt_*`
routing tiles. Each successive platform's internal port structure roughly doubles
in complexity (binary-tree-like mux/demux), suggesting this is full 48-lane-scale
merge infrastructure, not a simple pluggable 2-input stacker cell.

**Blueprints carry real labels — read them before guessing.** Building type
`LabelDefaultInternalVariant` has a `C` config: `base64(2-byte-LE-length-prefix +
UTF-8 text)`. Decode with `raw = base64.b64decode(C["$value"]); text =
raw[2:].decode("utf-8")`. John annotates every hand-built module this way
(`"Bottom"`, `"Top"`, `"Stacked"`, `"Passthrough"`, `"USE ONE INPUT ONLY"`, even
`"SHIT - Mixes lanes up in both these"` on a known-buggy spot). **Always check for
labels before reverse-engineering port semantics from coordinates alone** — it
turns guessing into reading. Pair a label to its port by nearest-neighbor distance
on the same floor (labels sit right next to the port/cluster they describe).

Per John (confirmed 2026-09-03), each of the 4 chained platforms in `Stacker.spz2bp`
is one incremental stage that stacks in one quadrant:
- **Bottom** input: EAST edge, one 12-lane band, floor 0.
- **Top** input: NORTH-ish edge, with a redundant second entry point right next to
  a `"USE ONE INPUT ONLY"` label — use exactly one.
- **Stacked** output: WEST edge, floor **1** (not floor 0).
- **Passthrough** bands (WEST and EAST edges, same Y, floor 0): a full-belt supply
  of "Bottom" shapes enters at the EAST edge of the most-eastern (last) platform (4
  ports = 1 full space belt); each stage peels off its own 12-lane share and passes
  the rest further down the chain (P4 has 3 passthrough bands, P3 has 2, P2 has 1,
  P1 has 0 — a clean 4-way peel-off). Each platform's own Top comes from an
  independent external supply on its north edge. Output of one stage's Stacked port
  feeds the next stage's Bottom via the connecting `SpaceBelt_*` run.
- **This works only when every quadrant has a shape** — an empty quadrant blocks
  the stack (physical jam, not a soft failure).

## Stacker supporting empty quadrants (better primitive, confirmed 2026-09-03)

`Stacker supporting empty quadrants.spz2bp` (38 islands, ~7.7k buildings: a
`Foundation_1x1`/315 "Overflow" sink + 3 plain-Stacker `Foundation_2x2` cells (one
`_Flipped`) + 2 `Foundation_2x4` "**Fancy A+B Side Overflow**" merge units) is the
version John actually recommends for composing shapes from independent quadrant
supplies. Per John: **takes 4 distinct quadrant inputs via 4 west-side ports (order
irrelevant — just needs one NE/SE/SW/NW, any assignment)** and emits **one full
space belt of stacked output**. Tolerates empty quadrants (that's the whole point);
this is what should sit downstream of `Quad Splitter`'s 4-band output.

The "Fancy A+B Side Overflow" component (also shipped standalone as its own
reference file) merges two streams with overflow-to-side logic; John left himself
a `"SHIT - Mixes lanes up in both these"` label on a known bug in its lane-merge
stage — flagged as a target for the "refactor into better components" work, not
yet root-caused.

**CONFIRMED WORKING, wired by John in-game (2026-09-03).** `Quad Splitter`'s 4
outputs need a **`Demuxer`** (`Foundation_2x4_Flipped`, from `Demuxer.spz2bp`)
between them and the Stacker's input — each output belt must carry its quadrant
shape in its ORIGINAL orientation (don't let e.g. NW rotate into SW when it exits
Quad Splitter); Demuxer normalizes that. Demuxer sits with **zero gap** directly
against Quad Splitter's west edge — adjacent platform edges connect straight
across the island boundary with no `SpaceBelt_*` tile needed between them, as long
as the ports line up. From there, 4 `SpaceBelt_Forward` tiles bridge Demuxer's
west edge to the Stacker cluster's east-most extent (the `Foundation_2x4` "Fancy
A+B" unit).

John tested this end-to-end (including with one blank quadrant) and confirmed: one
base shape → Quad Splitter → Demuxer → Stacker supporting empty quadrants →
reassembled, matching the original input. The exact wiring is now baked into
`vn07_reassembly_test()` in `build_modules.py` (`VN07_WIRING` for the hand-authored
SpaceBelt tiles; all foundations loaded verbatim from `blueprints/reference/`) —
diffed byte-for-byte against John's tested file, exact match on every foundation
except the 4 disposal-only `Trash` sinks (same building count, trivially different
internal content — harmless, they're test scaffolding, not reassembly logic).

**Red X's on stamp are EXPECTED for this design, not errors.** Each Stacker
platform's "Top" input has two alternate physical entry points with a
`"USE ONE INPUT ONLY"` label between them (see above) — the game flags the unused
one's adjacent empty `SpaceBelt` cell as a warning. That's intentional per John,
not a bug.
