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
  gap**. Same items/min as belts -- they cut **traversal time**, not throughput.
  **The gap cells need NOT be empty** -- items fly over whatever is beneath, and John's
  own `Fancy A+B Side Overflow` fires a launcher across a cell holding a crossing belt.
  This is the standard trick for routing one lane across another on a single floor.
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
stage. **Root-caused and fixed 2026-09-03** — see below.

## Fancy A+B Side Overflow: the inner/outer lane-swap bug (fixed)

**Symptom** (John): a band's OUTER lanes overflow to the "A+B Overflow" port as the
INNER lanes, and the INNER lanes come out as the OUTER lanes. Inconsequential in
practice (a given space belt always carries the same shape in the same orientation),
but real.

**The component is FOUR bands, not two.** `In A` and `In B` each appear TWICE —
north and south — one band per island-row of the 2x4 foundation, 4 x 12 = 48 lanes
(a full space belt), with two separate "A+B Overflow" output bands (north at local
Y=37, south at Y=-38). Band Y-offsets: In B north rows 8-11, In B south rows
-12..-9 (offset -20); In A north lanes 28-31, In A south lanes -32..-29 (offset
-60). **Only the north half carried the "SHIT" labels**, which is why the first
pass at this fix covered just those two bands — John caught it and mirrored the
fix to the south half.

**Root cause** (traced by walking the belt graph, not by eye): within each 4-lane
band, the two OUTER rows tap their overflow at splitter column **X=9** (In B) /
**X=8** (In A), while the two INNER rows tap at **X=7** / **X=6**. The downstream
weave delivers the X=9/X=8 taps to the INNER final output columns and the X=7/X=6
taps to the OUTER ones — so the classes cross over. The primary (non-overflow)
pass-through is unaffected and was always lane-preserving.

**Fix**: swap the splitter columns between each band's outer and inner rows, and
shift each outer row's launcher hop one cell east so it flies over the cell the
inner row's overflow now needs. 28 cells per band-pair per floor, stamped at all
four band offsets = 168 retyped cells; no buildings added or removed (bar the two
now-stale "SHIT" labels), no belt crossings introduced, every downstream cell
untouched. Encoded as `FANCY_AB_LANE_FIX` (generated from two base patterns x four
band offsets) + `apply_fancy_ab_lane_fix()` in `build_modules.py`, which asserts
the exact pre-edit state so a changed upstream reference fails loudly rather than
silently mis-patching.

**Cross-validated against John's own fix**: `vn08_fancy_ab_lane_fixed()` applies the
patch to `Fancy A+B Side Overflow (pre-lane-fix).spz2bp` and asserts the result is
cell-for-cell identical to John's hand-mirrored `Fancy A+B Side Overflow.spz2bp`.
Zero differing cells — the build fails if that ever stops holding.

**Verified by tracing**: all 16 lanes (4 bands) land outer->outer / inner->inner,
and all 48 primary pass-through paths (16 lanes x 3 floors) stay lane-preserving.
Shipped as `VN-08 fancy A+B lane fixed` (standalone) and
`VN-09 stacker empty quadrants fixed` (both embedded copies patched); `VN-07`
now builds on the fixed stacker. **All three VALIDATED IN-GAME by John
(2026-09-03)** — the lane fix is the baseline from here on; build further stacker
work on `load_fixed_stacker_islands()`, not the stock reference.

**Launchers fly OVER belts.** The gap cells between a `BeltPortSender` and its
`BeltPortReceiver` do NOT have to be empty — John's original design already fires
a launcher across a cell occupied by a crossing belt, and the fix relies on the
same trick. (Earlier note in this file claiming the gap must be empty was wrong.)

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

## Wire-signal config encoding (decoded 2026-09-03)

`ConstantSignalDefaultInternalVariant` (and friends) store their value in `C` as
base64. Decoded bytes are `<type-tag> <payload>`:

| tag | meaning | payload | example |
|-----|---------|---------|---------|
| `03` | integer | int32 LE | `03 e8 03 00 00` = 1000 |
| `05` | null / empty signal | *(none)* | `05` |
| `06` | shape | `01 01 <len:u16 LE> <ASCII shape code>` | `06 01 01 08 00 "CuCuCuCu"` |
| `07` | colour | `01 <ASCII colour char>` | `07 01 72` = `r` |

`ButtonDefaultInternalVariant`: `C` = single byte `00` (off) / `01` (on).
`LabelDefaultInternalVariant`: `C` = `<len:u16 LE> <UTF-8 text>` (see above).
`ControlledSignalReceiverInternalVariant(+Mirrored)`: `C` = int32 LE channel/slot;
**every instance in John's library uses `2`** (18 of them across `Shape Filter`,
`Smart Filter`, `Shitty Mam v1`). This is the **Goal Receiver** — it emits the
shape the HUB currently requests. Exact meaning of the `2` is unconfirmed — ask John.

## The game's complete building-id list (extracted 2026-09-03)

`shapez 2_Data/resources.assets` contains all **98** `*InternalVariant` building
ids as plain ASCII. To re-extract, regex `[A-Za-z0-9_]{3,60}InternalVariant` over
that file (and `Managed/SPZGameAssembly.dll`). **Use this instead of assuming a
building doesn't exist because John's library doesn't use it.**

The **virtual (wire-layer)** family in full:
`VirtualAnalyzerDefault`, `VirtualRotatorDefault`, `VirtualRotatorCCW`,
`VirtualPainterDefault`, `VirtualStackerDefault`, `VirtualUnstackerDefault`,
`VirtualHalfCutterDefault`, `VirtualHalvesSwapperDefault`,
`VirtualPinPusherDefault`, `VirtualCrystalGeneratorDefault`.

Other ids worth knowing that John's library never uses:
`ControlledSignalTransmitterInternalVariant` (pairs with the Goal Receiver —
presumably what puts a shape on channel 123), `WireGlobalTransmitterReceiver`,
`LogicGateAnd/Or/XOr`, `WireDefault1Up/2Up Forward|Left` variants.

## Wire-layer port map (EXTRACTED 2026-09-03 from `For Claude Wiring Shapes`)

John's reference puts every logic/virtual/transmission building on one
`Foundation_1x2`, each with `ConstantSignal`s on its inputs and `Display`s on its
outputs. All coordinates below are relative to the building's own cell and `R`
(its facing); "left" = the `R-1` side, "right" = `R+1`.

**All virtual buildings are 1x1** except the halves-swapper.

| Building | Inputs | Outputs |
|---|---|---|
| `VirtualRotatorDefault` / `CCW` | behind | forward |
| `VirtualPinPusherDefault` | behind | forward |
| `VirtualHalfCutterDefault` | behind | forward |
| `VirtualAnalyzerDefault` | behind | **forward = uncoloured SHAPE, left = COLOUR** (confirmed 2026-09-04) |
| `VirtualUnstackerDefault` | behind | **forward + left** (two) |
| `VirtualPainterDefault` | shape behind, **colour from left** | forward |
| `VirtualCrystalGeneratorDefault` | shape behind, **colour from left** | forward |
| `VirtualStackerDefault` | behind + **left** | forward |
| `VirtualHalvesSwapperDefault` | **2 wide**, one input per column, from behind | one per column, forward |
| `LogicGateNot` | behind | forward |
| `LogicGateCompare` / `And` / `Or` / `XOr` | **left and right sides** | forward |
| `LogicGateIf` | value behind, **condition from the side** | forward |

`LogicGateCompare` carries a config byte (`01` in the reference) — presumably the
comparison mode.

**Confirms the 3x3 signal-building geometry** derived earlier: in this reference
`ControlledSignalReceiver` at `(-5,7)` R3 has its channel constant at `(-7,7)`
(origin-2, left) and its display at `(-5,5)` (origin-2, forward);
`ControlledSignalTransmitter` at `(-5,12)` R3 takes its shape from `(-5,14)`
(origin+2, behind) and its channel from `(-7,12)`. `WireGlobalTransmitterReceiver`
is the same 3x3 shape.

**Updated 2026-09-03 (2nd revision):** John repurposed this blueprint from a pure
reference into the **goal source for testing** — both channel constants are now
**123** (`03 7b 00 00 00`), matching the MAM's filters, and the transmitter's shape
input is the test goal **`Su--WuCu`**. So the goal is hand-set from this platform
rather than read from the HUB, which is exactly the Phase 1 validation path.

Note the config byte `2` appears on the **transmitter** as well as the receiver, and
the channel is a separate wire input — so `2` is **not** a goal-slot index as we
first recorded. It is identical in all instances, so copy it verbatim and don't
attach meaning to it.

## Virtual (wire-layer) processing semantics (inferred 2026-09-03)

- `VirtualAnalyzerDefaultInternalVariant` — given a shape signal, yields that
  shape's **NE quadrant**. To extract an arbitrary quadrant: rotate the shape so
  that quadrant lands in NE, analyze, then rotate back by the inverse.
- `VirtualRotatorDefaultInternalVariant` / `...CCWInternalVariant` — rotate a shape
  signal 90 CW / CCW in the wire layer.
- `WireTransmitterSenderInternalVariant` / `...Receiver` — wireless signal relay
  pair; John uses them to carry a signal between bands of a tall foundation instead
  of running wire the whole length.
- `LogicGateIfInternalVariant(+Mirrored)` chained with `ButtonDefault` +
  `ConstantSignalDefault` = John's standard **priority-select / preset bank**
  (first enabled button wins).

## A building config `C` MUST carry `$type` (learned the hard way 2026-09-03)

`C` is either `null` or the object
`{"$type": "System.Byte[], mscorlib", "$value": "<base64>"}`.
**Omitting `$type` makes the game reject the ENTIRE blueprint file — silently.**
No error, no red X: the file simply never appears in the in-game blueprint folder,
which reads as a failed folder refresh. VN-11/VN-12 shipped this way once (a button
config was rebuilt as `{"$value": ...}`); John spotted the missing entries.

=> use `config()` / `set_config()` in `build_modules.py`, which preserve `$type`,
and never rebuild a config dict from scratch. `check_configs()` runs over every
generated module in the build loop so this fails the build instead of the game.

**Diagnostic rule: a blueprint that doesn't show up in-game at all is a malformed
file, not a stale folder.** Files that merely place badly still appear (with red X's).

## Multi-cell buildings record only their ORIGIN cell (2026-09-03)

A blueprint entry gives one `X,Y,L` even for buildings larger than 1x1 — the extra
cells are implicit and simply absent from the entry list. Seen with
`Display2x2*` and `ControlledSignalReceiver*`. **So an "empty" cell next to a big
building may not be free.** Derive a footprint by finding the gap between a
building's origin and the wire/belt cell that actually connects to it.

**`ControlledSignalReceiver` (the Goal Receiver) footprint**, extracted from John's
two working instances:
- `Shape Filter`: origin `(4,35)` R3 (north), consumer wire at `(4,33)`, `(4,34)` absent.
- `Smart Filter`: origin `(13,19)` R0 (east), consumer wire at `(15,19)`, `(14,19)` absent.

We first inferred "origin + the next cell along R". **That was wrong** and stamped a
blank platform. **RESOLVED** by John's minimal reference
`For Claude Signal Receiver.spz2bp` — a bare receiver on an empty 1x1 with a belt
box drawn around it on L1 so the footprint is directly readable:

- **3x3, CENTRED on the recorded origin cell.** (L1 box outlines X7-11 x Y8-12 =>
  interior X8-10 x Y9-11; origin recorded as `(9,10)` R3.)
- **Output** leaves the centre-front cell into `origin + 2 along R` — the wire run
  at `(9,8)/(9,7)/(9,6)`.
- **Channel input** arrives at the centre-side cell from `origin + 2 across`, on
  the **`R-1` side** for the plain variant (const at `(7,10)`, west of an R3
  receiver) and the **`R+1` side** for `...Mirrored` — which is exactly what the
  in-situ copies show (`Shape Filter` mirrored R3: const EAST at `(6,35)`;
  `Smart Filter` mirrored R0: const SOUTH at `(13,21)`).
- **The receiver's own `C` (`AAAAAg==`, value 2) is NOT the channel** — it is the
  same in all 19 instances across John's library. **The channel is a wire input**
  from a `ConstantSignal` integer: 123 in the reference, 11 in `Shape Filter`,
  1000 in `Smart Filter`.

Integer signal config = tag `03` + int32 **little-endian**; `int_signal_config()`
in `build_modules.py` is asserted at build time to reproduce John's channel-123
constant byte-for-byte.

**Placement of the 3x3 is still an open constraint.** Centred at local `(3,25)` on
a `Foundation_1x4` — footprint X2-4 x Y24-26, every cell verified empty — the game
called it **out of bounds**, "one unit too far towards the edge". It is **not** a
reserved-column rule: a census over John's whole library finds **12,219 non-port
buildings on local X2/X17**, so those columns are ordinary for belts, pipes,
rotators, cutters and mixers. Whatever the rule is (a margin for large buildings?),
we have no reference that isolates it. **Do not assume local X2/X17 is usable by a
multi-cell building.**

## Same invalid building, two different symptoms

The out-of-bounds receiver produced a **warning** in the single-island VN-11 but
**silently blanked the island** in the multi-island VN-12. So the "platform stamps
but is empty" symptom in a large assembly can be an ordinary placement error that a
standalone blueprint would have reported properly. **Isolate a suspect building on
its own single-island blueprint to get the real error message.**

## One invalid building blanks the WHOLE island (2026-09-03)

If a single building entry in an island's nested `B` blueprint is invalid, the game
places the **foundation** and **silently discards every building on it** — you get
a bare platform, not a red X on the offending cell. Distinct from the malformed-
config failure above, which discards the whole *file*.

**Two silent failure modes, two different symptoms:**
| Symptom | Cause |
|---|---|
| Blueprint absent from the in-game folder | malformed file (e.g. a `C` without `$type`) |
| Platform stamps but is completely empty | one invalid building entry on that island |
| Platform stamps with red X's | placement conflicts — the file itself is fine |

## `Quaded Filter` (`Filter.spz2bp` / `Quaded Filter.spz2bp`) port map

`Foundation_1x4`, 1068-1096 buildings. **4 bands x 12 lanes = 48 lanes (full belt).**
- Band order north->south: **NW, SW, SE, NE** (labelled in-blueprint).
- Band `k` (0..3) occupies local `Y = 20k - 12 .. 20k - 9` (= -12..-9, 8..11,
  28..31, 48..51), floors L0-L2, 4 lanes each.
- **Input**: EAST edge, local `X=17`, `R2` (flows west). **Output**: WEST edge,
  local `X=2`, `R2`. One `BeltFilterDefault` per lane sits mid-band.
- Logic block: local X3-16, Y15-23, L0 — preset bank -> quadrant decomposer ->
  wire transmitters (see architecture.md for what it computes).

`Quaded Color Filter` is the same 4-band `Foundation_1x4` shell (R2) with **four
independent** per-band selectors over `r` / `g` / `b` / null.

**Red X's on stamp are EXPECTED for this design, not errors.** Each Stacker
platform's "Top" input has two alternate physical entry points with a
`"USE ONE INPUT ONLY"` label between them (see above) — the game flags the unused
one's adjacent empty `SpaceBelt` cell as a warning. That's intentional per John,
not a bug.

## `Paint 4 Filter` / `Paint 3 Filter` selector bank (EXTRACTED 2026-09-04)

`Foundation_1x4` **R2**, buildings span local **X-35..32, Y2..17** (the 1x4 runs
along X; Y is a single platform). 1,066 buildings: 396 `PipeForward`, 144
`PipeLeft`, 84 `FluidPortSender` + 84 `FluidPortReceiver`, **48
`PipeGateDefaultInternalVariantMirrored`**, and a small wire bank.

**The bank is a first-wins priority selector over four signal constants:**

| cell | building | note |
|---|---|---|
| `(15,4)` `(17,4)` `(19,4)` `(21,4)` R1 | `ConstantSignal` | `r`, `g`, `b`, **null** (`05`) |
| `(15,5)` `(17,5)` `(19,5)` `(21,5)` R1 | `LogicGateIf` | value from behind (the constant), **condition from its LEFT side**, output forward |
| `(16,5)` `(18,5)` `(20,5)` `(22,5)` R2 | `ButtonDefault` | **the four enable inputs — this is the swap point** |
| rows 6-8 `(19,6)/(20,6)`, `(17,7)/(18,7)`, `(15,8)/(16,8)` | `LogicGateIf` + `LogicGateNot` | priority chain: a later slot passes only if no earlier one fired |
| `(21,10)` `(22,11)` `(23,12)` R2 | `LogicGateIfMirrored` | tail of the chain |
| row 16, `(25,16)` west | wire bus | carries the winning colour to all 48 `PipeGate`s; relayed across platforms by `WireTransmitterSender/Receiver` |
| `(26,4)` | `Display2x2` | shows the selected colour — free probe point |

- **No slot enabled => the bus carries nothing => every gate shuts.** That is the
  correct no-paint behaviour, so an empty/pin quadrant (analyzer colour = null)
  needs no special case.
- **`Paint 3 Filter` has the SAME four constants** (`r`, `g`, `b`, null) at
  `(26,3)`..`(32,3)` with buttons at `(27,4)`..`(33,4)`. **The 3/4 in the names is
  not the palette size** — both select 3 paints + off.
- Free build space: **L1 has 246 free cells and L2 247** in X13-32/Y2-17. John
  already bridges floors here with `WireDefault1UpBackward` `(26,5)` /
  `WireDefault2UpBackward` `(27,5)`.

## `LogicGateIf` condition side — CONFIRMED (2026-09-04)

`LogicGateIfInternalVariant` takes its **condition from its LEFT (`R-1`) side**;
`...Mirrored` from the right. Value in from behind, result out forward. Confirmed
independently on two of John's platforms:
- `Quaded Filter` `(5,17)` R0: constant behind at `(4,17)`, button routed up column
  X3 and along row 16 to enter at `(5,16)` = north = left of R0.
- `Paint 4 Filter` `(15,5)` R1: constant behind at `(15,4)`, button at `(16,5)` =
  east = left of R1.

## `Quaded Filter` analyzer fan: row -> quadrant mapping (DECODED 2026-09-04)

The fan sits at local **X8-12, Y17-20, L0**, four `VirtualAnalyzer`s stacked in
column **X=10**, all **R0**. Each row rotates the goal so its quadrant lands in NE,
analyzes, then rotates back by the inverse:

| row | pre-rotators | quadrant |
|---|---|---|
| `Y=17` | `(8,17)` + `(9,17)` `VirtualRotator` (2x CW) | **SW** |
| `Y=18` | `(9,18)` `VirtualRotatorCCW` (1x CCW) | **SE** |
| `Y=19` | none | **NE** |
| `Y=20` | `(9,20)` `VirtualRotator` (1x CW) | **NW** |

(k CW rotations bring the quadrant k steps CCW from NE into NE: 1 CW <- NW,
2 CW <- SW, 1 CCW <- SE.)

**The colour outputs are unreachable here and we are not going to free them.** R0's
left side is **north**, so each analyzer's colour output cell is the next analyzer;
only the top has a free neighbour at `(10,16)`. **Re-laying the fan is unnecessary
anyway** — the colour signals are goal-derived, identical on all 16 filters, so the
colour logic belongs on the paint platform instead. See PROGRESS "START HERE".

## `ControlledSignalTransmitter` carries a NULL config (2026-09-04)

In `For Claude Wiring Shapes` the transmitter at `(-5,12)` R3 has `C = null`; only
the **receiver** (and `WireGlobalTransmitterReceiver`) carry `00 00 00 02`. The
earlier note that "the config byte 2 appears on the transmitter as well" was wrong.
Channel is a separate wire input from the left (`(-7,12)`), shape input from behind
(`(-5,14)`).

## Controlled-signal buildings: 3x3 body + the PORT-CELL RULE (CENSUS 2026-09-04)

Measured over **all 45 `ControlledSignal*` / `WireGlobalTransmitterReceiver`
buildings in John's library**, not inferred from one example:

1. **The body is 3x3, centred on the recorded entry cell.** In every one of the 45
   instances the **eight cells immediately around the entry are empty**. Only the
   origin is recorded in the entry list, so those eight are invisible — see
   "Multi-cell buildings record only their ORIGIN cell".
2. **Ports are at exactly +-2** along the axes: signal out **forward**, channel in
   from the **left** (`R-1`; the `Mirrored` variant takes it from the right).
3. **!! A port cell may hold ONLY a `Wire*`, `Display*` or `ConstantSignal*`.**
   In all 45 instances the occupied +-2 cells are `WireDefaultForward`,
   `WireDefaultJunction`, `DisplayDefault` or `ConstantSignalDefault` — **never** a
   `Virtual*` or `LogicGate*`. To feed a virtual building, route out through a wire
   first, exactly as John does at `(9,8)` in `For Claude Signal Receiver.spz2bp`.

**This rule is what killed VN-13 v1** — it put a `VirtualAnalyzer` directly on a
receiver's output port cell, and the game rejected the **entire file** (never
appeared in the blueprint folder; no error, no red X). A fourth silent failure mode,
alongside the three already listed. `validate_layout()` in `build_modules.py` now
refuses all of 1-3 at build time.

## Buildable window on a 1x1 is EXACTLY [2,17] in both axes (MEASURED 2026-09-04)

Over **85,372 buildings on `Foundation_1x1` platforms** across `blueprints/2026` and
`blueprints/reference`: X range 2..17, Y range 2..17, with the extremes genuinely in
use (X=2 appears 2,804 times, Y=17 856 times). The old "~[2,17]" tilde can go.

**On a MULTI-platform foundation the seam is buildable**, so in-platform offsets
0, 1, 18 and 19 do occur there. Do not carry the 1x1 bound across to a `1x2`/`1x4`.

## SETTLED: analyzer forward = shape, left = COLOUR (2026-09-04)

John, reading `VN-13q1`/`q2` in-game: "the analyzer outputs Grey color (uncolored)
out its **top (West)** to a display, and a shape (`Wu------`) to a display on the
**North**." The analyzer is R3 (north-facing), so **west is its left side** and
north is forward. The table above was right all along; an earlier reading of
"colour out the top" was the angled camera, not a contradiction. It also agrees with
the `Quaded Filter` fan, whose post-rotators hang off the **forward** output — you
can only rotate a shape.

The colour maths was separately validated by `VN-13p5`: `CrCgCbCu` through 1x CW
returned colour `u` and shape `Cu------`, exactly the original **NW** quadrant. So
the rotation mapping **NE none / SE 1x CCW / SW 2x CW / NW 1x CW** is correct.

## REFUTED: "a port cell may only hold a Wire/Display/ConstantSignal"

Recorded so it is not re-derived. The census above is real — across all 45
controlled-signal buildings in John's library, the occupied ±2 port cells only ever
hold a `Wire*`, `Display*` or `ConstantSignal*`, never a `Virtual*` or `LogicGate*`
— and we inferred a game rule from it. **`VN-13q1` disproves the rule**: an analyzer
placed directly on a receiver's output port cell imports and runs fine. John simply
never happens to do it.

**The lesson is the one PLAYBOOK already gives for footprints, and it cost a round
trip here: absence from John's library is not a game rule.** A census tells you what
he does, not what the game permits. Only an in-game test tells you the latter.

## LABELS — SOLVED (2026-09-04). Two rules, two different symptoms

`LabelDefaultInternalVariant` is **not 1x1**, and it also needs a margin.

### Rule 1 — the body is FIVE cells, centred, along the facing axis
R0/R2 run horizontally (`x-2 .. x+2`), R1/R3 vertically (`y-2 .. y+2`). The size is
**fixed — it does not scale with the text.**

Two independent confirmations:
- **John's `For Claude Labels.spz2bp`** (built for this): every belt box has a 5-cell
  interior for texts of 10, 16 and 22 characters.
- **Whole-library test**: applying an N-cell model to all **3,100** labels gives
  **0 collisions at N=5** (and at N=3), but **2,569 collisions at N=7** and 5,172 at
  N=9. So the body is at most 5, and John's snug boxes make it exactly 5.

### Rule 2 — a label needs ONE CELL OF MARGIN from the platform edge
Its body must stay within **[3,16]** on a 1x1 — never the outer ring at 2 or 17.
- John's reference demonstrates the extremes deliberately: every label he named
  "North West **Corner**", "South West Corner", "North side", "South side" sits
  **exactly one cell in** from the buildable edge.
- Census: on `Foundation_1x1` platforms, label body cells occupy offsets
  **[3..7, 12..16] and never 2 or 17**, while every other building type uses the
  full 2..17.

### The two rules have DIFFERENT symptoms — which is why this took four rounds
| violation | symptom |
|---|---|
| label body **overlaps another building** | the game discards the **whole FILE** — it never appears in the blueprint folder |
| label body only **breaks the edge margin** | the file imports fine but **fails to stamp** (red X) |

That matches the file-vs-placement distinction already documented above. Every
observation is now accounted for:

| blueprint | label | body | outcome |
|---|---|---|---|
| `p1` | `(9,9)` R0 alone | X7-11 | **imported** |
| `p6` | `(2,13)` R2 + display `(3,13)` | X0-4 | overlap + margin -> **file discarded** |
| `VN-13 v1`, `v2` | several over displays | — | overlap -> **file discarded** |
| `r1`,`s1`,`s2` | `(7,7)` + display `(8,7)` | X5-9 | overlap -> **file discarded** |
| `t1` | `(4,14)` R0 | X2-6 | margin only -> **failed to stamp** |
| `t1` | `(5,7)` R0 | X3-7 | legal — this one was innocent |

**Why it hid:** a label may sit beside another building, just never along its own
axis, so a census that did not split by rotation cleared them; and the 3-cell reading
that followed was one ring short. **When censusing a footprint, split by `R`, and
prefer a purpose-built reference over inference.** `validate_layout()` now encodes
both rules and reproduces every row of that table.

## Multi-island blueprints we author: CONFIRMED WORKING (2026-09-04)

`VN-13 colour brain all` — four `Foundation_1x1` islands we construct ourselves,
each carrying its own chain — stamps correctly in-game. So authoring islands rather
than lifting them from John's files is fine, and the earlier `VN-13r2` failure (two
label-free islands) is **unexplained but superseded**: the same construction, scaled
up to four islands, works. It was most likely mis-read during a batch check of six
files. Do not build a theory on it; if it recurs, bisect it fresh.

## Space-belt Z changes: the lift rules (EXTRACTED 2026-09-04, `For Claude Fixed Pipes`)

Multi-level space belts work — islands carry a `Z` field and John routes over
crossings at `Z=1`. But the lift units are strict, and John named the constraint:
**a Z-change unit cannot also merge.** Doing both takes two units — the lift, then a
separate merger. A lift *may* rotate its exit 90 degrees, which is what the `Right`
variants are for.

| unit | sits at | delivers to |
|---|---|---|
| `SpaceBelt_Lift1UpForward` R2 | `(x,y,Z0)` | `(x-1, y, Z1)` — up one level, one cell forward |
| `SpaceBelt_Lift1DownForward` R2 | `(x,y,Z1)` | `(x-1, y, Z0)` — down one level, one cell forward |
| `SpaceBelt_Lift1DownRight` R2 | `(x,y,Z1)` | `(x, y-1, Z0)` — down one level, exit turned 90° right |

**!! The cell directly above/below a lift must be EMPTY.** True of all 12 lifts in
John's fixed blueprint, with no exceptions — a trunk may not run underneath one.
**This is what broke Claude's first aggregator**: it spaced the trunks one column
apart and dropped a `Lift1DownForward` at `(8,y,Z1)` straight onto the trunk running
at `(8,y,Z0)`.

**The fix is a spacing discipline: trunks on every OTHER column.** Odd columns carry
trunks, even columns stay clear so lifts have somewhere to land through. A plain
`Forward` at `Z=1` may pass over an occupied `Z=0` cell — only lifts need clearance.

### The three input patterns (use verbatim; do not re-derive)
```
nearest band, no hop   (8,y) Forward R2                      -> (7,y) LeftFwdMerger R3
hop then MERGE         (8,y) Lift1UpForward R2
                       (7 .. tx+2, y, Z1) Forward R2
                       (tx+1, y, Z1) Lift1DownForward R2      -> (tx,y) LeftFwdMerger R3
hop then START a trunk (8,y) Lift1UpForward R2
                       (7 .. tx+1, y, Z1) Forward R2
                       (tx,   y, Z1) Lift1DownRight R2        -> (tx,y-1) Forward R3
```
The `Right` variant is how a hopped stream starts a trunk without a separate turn —
a lift may turn but may not merge, so there is no unit that could do both.

## Island footprints: a foundation records only its ORIGIN tile (EXTRACTED 2026-09-05)

The same trap as multi-cell buildings, one level up. A `Foundation_2x4` covers eight
island-grid cells and stores exactly one — so two foundations can overlap in the file
with nothing to show for it, and the platform simply refuses to stamp in-game.

Recovered from the islands' **own building coordinates**, not from the names: a
platform tile is **20 units of building space**, so `floor(building X / 20)` gives the
tile. Measured across both MAMs (1,707 islands); every span came out an exact multiple.

| island | R | tile span (dx, dy from origin) |
|---|---|---|
| `Foundation_1x1` | 1, 3 | `(0,0)` |
| `Foundation_1x4` | 1 | `dx 0`, `dy -1..2` |
| `Foundation_2x2` | 3 | `dx 0..1`, `dy -1..0` |
| `Foundation_2x2_Flipped` | 1 | `dx 0..1`, `dy 0..1` |
| `Foundation_2x4` | 3 | `dx 0..1`, `dy -2..1` |
| `Foundation_2x4_Flipped` | 1 | `dx 0..1`, `dy -1..2` |

**The anchor is not the corner and is not consistent between variants** — `2x2` R3
grows north, `2x2_Flipped` R1 grows south. Never assume; look it up, or re-derive it
from the building coordinates the way the table above was derived.
`tools/verify_mam.py` (`ISLAND_FOOTPRINT`, `island_cells`) now checks for overlaps.

Only the rotations actually used are listed. `Layout_Train*` islands carry **no
buildings at all** in a blueprint, so their footprint cannot be recovered this way.

## Space-belt direction model (FITTED 2026-09-05, `Working Full Belt ... MAM`)

Fitted, not assumed: 32 candidate conventions were scored against every belt-to-belt
edge in the working machine, and one wins outright — then explains **100%** of the
network once island footprints are taken into account (0 dead ends over 1,022 edges).

* `R` indexes **E, S, W, N clockwise** (`R0`=E, `R1`=S, `R2`=W, `R3`=N).
* `Forward` and every merger: `R` is the **output** direction.
* `LeftTurn` / `RightTurn`: `R` is the **INCOMING heading**, and the exit is `R-1` /
  `R+1`. So `LeftTurn R3` = "running north, turn left" = **exits west**.
* `RightFwdSplitter R`: outputs both `R` and `R+1`.

**Merger names are mirrored relative to travel.** A `LeftFwdMerger` takes its side
feed from the cell on its **right as the shapes travel** — i.e. the left side as you
face the belt head-on. Confirmed on 40 of the machine's 42 mergers.

| unit | accepts input from (relative to its `R`) |
|---|---|
| `Forward`, both turns, `RightFwdSplitter` | behind only |
| `LeftFwdMerger` | behind + the cell at `R+1` |
| `RightFwdMerger` | behind + the cell at `R+3` |
| `TripleMerger` | behind + both sides |
| `YMerger` | both sides only — **not** from behind |

### Lifts: the Z hand-off (EXTRACTED 2026-09-05, FSB MAM)

The model above was fitted before any Z-change unit was in play, and it treated a
lift as a flat `Forward`. That is wrong, and it made `verify_mam.py` report **120
phantom dead ends** on a machine that has none.

* `Lift<n>UpForward R` at `Z` hands off at **`Z+n`, one cell ahead** (direction `R`).
* `Lift<n>DownForward R` at `Z` hands off at **`Z-n`, one cell ahead**.
* The `Left` / `Right` variants do the same but exit at `R-1` / `R+1` — John's rule:
  a Z-change unit "may rotate the entry or exit towards a different cardinal
  direction, but that's it", and it may **never merge**.
* A lift accepts input from **behind only**.
* Nothing may sit directly above or below a lift. (Confirmed again on the FSB MAM:
  0 of its 120 lifts has anything in the cell above or below.)

With the hop modelled, `For Claude Working MAM 1 layer no-color FSB` comes out at
**0 dead ends over 1,293 space belts**.

### `Layout_TrainUnloader_Shapes_Flipped` R1 is 2 tiles wide (x-1..x, 1 tall)

Prefab layouts carry no buildings, so the span trick cannot measure them. This one is
pinned by **elimination**: each lane's first space belt sits at `(33,y)` and is fed
from the east, `(34,y)` holds no island of its own, and islands may not overlap — so
the unloader recorded at `(35,y)` must cover `(34,y)` and cannot reach `(33,y)`.

## The band-merge distribution fan (FSB MAM, 2026-09-05)

How one merged band trunk reaches four stacker clusters. Per band `k` (0..3), with
the trunk running **west** along row `1+k` and the clusters anchored at rows 2/8/14/20:

| band | trunk row | trunk splitters | inner column | outer column |
|---|---|---|---|---|
| A | 1 | `(-12,1)`, `(-13,1)` | -12 | -13 |
| B | 2 | `(-9,2)`, `(-10,2)` | -9 | -10 |
| C | 3 | `(-6,3)`, `(-7,3)` | -6 | -7 |
| D | 4 | `(-3,4)`, `(-4,4)` | -3 | -4 |

Both trunk splitters are `SpaceBelt_LeftFwdSplitter R2` — running west, peel off
**south**. Travelling west you meet the **inner** column's splitter first. Then:

* **main line** continues west, lifts to Z1 to cross the rows below it, and drops
  into cluster 1's filter at `(-15, 1+k)`;
* **outer column** runs south and turns west into cluster 2;
* **inner column** runs south to cluster 3's row, turns west, and hits one more
  splitter that feeds cluster 3 and continues south as the outer column's lower
  segment to cluster 4.

So each band needs **exactly two splitters on its trunk plus one more down the inner
column** = four destinations. A band with only one trunk splitter silently starves
clusters 3 and 4.

## The game's own blueprint importer (EXTRACTED 2026-09-05 via `tools/spz2api`)

With Shapez Shifter installed and `--set-modding-env-vars` run, the game's assemblies
are readable with `MetadataLoadContext` — no Unity, nothing executed. `tools/spz2api`
does this. What it found rewrites our model of why blueprints fail.

### The validator is ONE method

```csharp
// Game.Core.Blueprint.Importer.BlueprintImporter : IBlueprintImporter
bool TryImport(string serializedBlueprint,
               out IAnnotatedBlueprint blueprint,
               out int version,
               out BlueprintException exception);
```

String in, typed failure out. Its pipeline is exposed as properties: `Deserializer`,
`Migrator`, `Sanitizer`, `Disassembler`, `Writer`.

### **The game does not reject a bad blueprint. It SILENTLY STRIPS the bad parts.**

```csharp
// Game.Blueprints.BlueprintSanitizer : IBlueprintSanitizer
bool TrySanitize(BlueprintCandidate, out BlueprintException);
bool TryRemoveUnknownEntries(BlueprintCandidate, out BlueprintException);
void RemoveOverlappingEntries(BlueprintCandidate, out BlueprintException);
```

This is the mechanism behind every silent failure we have paid round trips for. A
blueprint with one bad entry is not discarded — the sanitizer **removes that entry and
imports the rest**. So the symptoms we catalogued (file never appears; stamps but a
platform is blank; stamps wrong) are all the same event at different severities, and
"the whole file was discarded" was the wrong model: strip enough entries and you hit
`BlueprintEmptyException`, which is what *looks* like a discarded file.

`RemoveOverlappingEntries` uses a `ScopedHashSet<GlobalChunkCoordinate> occupiedChunks`
with separate `BuildingEntryOverlaps` / `IslandEntryOverlaps` predicates — confirming
that building-cell overlap and island-tile overlap are checked independently, exactly
as `validate_layout()` and `check_islands_and_belts()` model them.

### Every rejection reason is a named exception

`BlueprintSerializationUnknownTypeException` (our bad type ids) ·
`BlueprintOverlappingTilesException` (our footprint clashes) · `BlueprintEmptyException` ·
`BlueprintSerializationJsonException` / `SyntaxException` / `ParsingException` /
`ConvertBase64Exception` / `ZipException` · `BlueprintSerializationBlueprintVersionException` /
`BlacklistedSavegameVersionException` / `OutOfBoundsSavegameVersionException` ·
`AggregateBlueprintException` · `UnexpectedBlueprintException` ·
`BlueprintDefinitionsNotAvailableForMode`.

So the information we spent six round trips guessing at on VN-13 **exists, typed, at
the moment of failure** — it is just never surfaced to the player.

### Mod entry point

`Game.Core.Modding.IMod` is `: System.IDisposable` with **no declared members**. A mod
DLL must contain exactly one `IMod` implementation (the loader logs "could not find a
single IMod implementation" otherwise) and does its work in the constructor —
ShapezShifter logs "Initialized" immediately on load.

ShapezShifter's `Flow` namespace is entirely building/island authoring
(`BuildingBuilder`, `IIdentifiableConnectable...BuildingBuilder`, localization,
toolbars). Nothing there is aimed at inspection or automation, so a validator mod sits
on `Hijack` / `SharpDetours`, off the documented path.

## `debug.export-game-data` — the game hands you its own definitions

Typing `debug.export-game-data` in the in-game console writes `basedata-v<n>/` beside
the savegames. `gamedata/basedata-v1138/` is a copy so the build does not depend on the
game folder. Re-run it and refresh that directory after a game update.

```
buildings.json     67 buildings / 131 internal variants
identifiers.json   BuildingVariantIds 67 · BuildingInternalVariantIds 131 ·
                   IslandLayoutIds 163 · WikiEntryIds · ImageIds · VideoIds · IconIds
scenarios/         7 scenarios      json-schemas/  3 schemas (ScenarioSchema is 59 KB)
difficulty-presets/  scenario-parameter-presets/    version
```

Each internal variant carries exactly five fields:
`Id`, `MirroredDefinitionId`, **`Tiles`**, **`BeltInputs`**, **`BeltOutputs`** —
where a port is `{Position_L, Direction_L}`, `Position_L` being the port's own local
cell and `Direction_L` the face it exits through (the receiver is the ADJACENT cell in
that direction). Direction is `0=E, 1=S, 2=W, 3=N`, confirming our fitted convention.

### What it confirmed
* **Label = 5 tiles**, `X-2..2, Y0`. Exactly the rule that cost six round trips.
* **Lift hand-off**: `Lift1UpForward` in `(0,0,0)d2`, out `(0,0,1)d0` — Z+1 and one
  cell ahead. `Lift<n>` gives `Z±n`. Our `verify_mam.py` model was right.
* `0=E,1=S,2=W,3=N`, and `Left`/`Mirrored` on a belt = left/right turn.

### What it CORRECTED
* **The controlled-signal family is 3x3x3 = 27 cells, spanning Z 0..2** — not the 3x3
  we had inferred from John's belt outline. That outline showed the ground floor only.
  Our validator would have allowed a building on top of a receiver.
* **13 multi-cell types we already place were modelled as 1x1**, including
  `PainterDefaultInternalVariant` (2 cells, `Y0..1`) — the one Phase 2a needs —
  `StackerStraightInternalVariant`, `CutterDefault*`, `FluidStorageDefault*`, every
  `Lift*`, and the `Pipe*Up*` / `Wire*Up*` variants that span Z.
* All three `UNKNOWN_FOOTPRINT` entries became known: `Display2x2` (origin, +X/-Y),
  `Display3x3` (origin, +X/-Y, NOT centred), `VirtualHalvesSwapper` (2 cells, `Y-1..0`).

### Footprint rotation (FITTED 2026-09-05)
`Tiles` are unrotated local offsets. `R` counts 90-degree steps with +X East and +Y
**South**, so a visually clockwise step is `(dx, dy) -> (-dy, dx)`. Scored over the
whole library — 49 blueprints, 845 islands, **1,028,331 placed cells**: this
convention gives **0 collisions**, its inverse 7,784, no rotation 11,945.

### What the export does NOT carry
**Wire ports.** `BeltInputs`/`BeltOutputs` are empty for every `Virtual*` building, so
the analyzer's shape/colour outputs are not settled here — VN-13's in-game result
(forward = shape, left = colour) remains the source of truth. The label EDGE MARGIN is
likewise not in the export and stays ours.

## Savegame binary: THE WHOLE WORLD (EXTRACTED 2026-09-05, tools/save_world.py)

Read and write, round-trip **byte-identical** on every world tried: the 24-island
sandbox, the 1,651-island one, and the 17,291-island / 660,476-building 72.8h save.

### Where things actually live
| entry | holds |
|---|---|
| `maps/main/islands/<n>.bin` | the islands **and every building on them** |
| `maps/main/buildings/<n>.bin` | per-island RUNTIME STATE (cargo in flight) |
| `strings.bin` | intern table: layout ids, variant ids, shape codes, label text |
| `maps/main/resource-chunks.bin` | the shape patches |
| `research.json` | `Shapes.StoredShapes` -- **the Vortex delivery scoreboard** |

The names mislead. `buildings/<n>.bin` is *state*: an island with 315 belts on it
has a **30-byte** record when nothing is moving, and a `Layout_ShapeMiner` with 160
buildings likewise. A record longer than 30 bytes means cargo is in flight -- which
is a free "is this machine alive" signal (`tools/observe.py`).

### The serializer (one rule walks the whole file)
Byte-packed little-endian with constant 4-byte markers. `savegame.json`'s
`BinaryDataCheckpoints: true` refers to these; they are **magic words, not
checksums**, which is the only reason hand-editing works.

    A = 54 0d 72 c4   opens a length-prefixed block:  A u32 N <N bytes> C
    C = 21 30 a4 84   closes a block
    E = 7c 6d 49 a4   opens a counted list:           E u32 count <items>
    I = 9a 02 21 b1   island record tag
    B = e5 8d a0 35   building record tag

    island   I | i32 X | i32 Y | i16 Z | i16 layoutIdx | i16 0 | u8 R | A-block of:
                 u8 hasIslandCfg | [A-block cfg] | A-block of: E u32 n | n buildings
    building B | i16 X | i16 Y | u8 L | u8 R | u16 variantIdx | u16 0 | u8 hasCfg
                 | [A-block cfg]

**Nothing follows the building list.** A bare island is exactly 52 bytes.

### Two traps that cost a crash between them
* **Building X/Y are SIGNED int16.** A multi-tile island records only its origin
  tile, so the 3x3 HUB carries buildings from -20 to 39. Reading them unsigned makes
  -17 look like 65519.
* **There is no island-title field.** Emitting one crashes the load with
  `Checkpoint mismatch, expected 2225352737 but got 3295808852` (0x84A43021 = close,
  0xC4720D54 = open). Zero of 18,966 islands across all worlds carry anything there.

### The size law -- run this, a round-trip is not enough
An island record's length follows from its contents, independently of both reader
and writer. **18,966 of 18,966 real islands obey it.**

    52 + [12 + len(icfg)] + SUM over buildings of ( 15 + [12 + len(cfg)] )

### Buffer capacity
Every `.bin` entry is zero-padded to `max(256, next power of two >= used)` --
166/166 entries across three saves. So a written world may **grow**; it just has to
land on a size the game's own serializer would pick.

### Chunk assignment is NOT spatial
Chunks are arbitrary buckets (a 24-island world splits 7/6/2/5/3/1 with no
geographic pattern). Append an island to any chunk, and append its matching state
record at the same index -- the two files are parallel, in order.

### Config blobs are the SAME BYTES as a blueprint's `C`, with one exception
Verified cell-for-cell on a platform present in both a blueprint and the world
(`Overflow`, 315 buildings): 314 matched exactly. The exception is **text**, which a
savegame interns and a blueprint inlines as `u16 len + UTF-8`:

| building | savegame config |
|---|---|
| `LabelDefaultInternalVariant` | `u32 strIdx` |
| `ConstantSignal` kind `03` | `i32` value -- **channel numbers** (`03 7b 00 00 00` = 123) |
| `ConstantSignal` kind `05` | null |
| `ConstantSignal` kind `06` | `01 01` + `u32 strIdx` -- a **shape** |
| `ConstantSignal` kind `07` | `01` + colour char (`r`/`g`/`b`) |
| `LogicGateCompare` | `u8` mode |
| `ControlledSignalReceiver` | `00 00 00 02` |

Island-level config (blueprint field `S`) is verbatim: `Rail_Forward` = `01 00 00 00 00`,
`Layout_TrainUnloader_Shapes_Flipped` = `00 00 00 00` (its empty shape filter).

Island rotation rotates contents: `(x,y) -> (N-1-y, x)`, `R -> R+1`, N = 20 x tile span.

### `maps/main/resource-chunks.bin` -- the shape patches (see tools/resources.py)

    u32 nChunks
    per chunk:  CH(4) | i32 chunkX | i32 chunkY | A-block of:
                    SH(4) | u32 nPatches | shape patches
                    FL(4) | u32 nPatches | fluid patches
                C(4)
    shape patch  u8 1 | i32 X | i32 Y | u16 0 | i32 n
                 | n x i32 shapeStrIdx | n x (i32 dx, i32 dy)
    fluid patch  u8 1 | i32 X | i32 Y | u16 0 | u8 1 | u8 colour | i32 n
                 | n x (i32 dx, i32 dy)
    CH = ee 74 46 a6   SH = da 7c f2 09   FL = 51 3a 47 16

Tiles are `(X+dx, Y+dy)`. The shape array is **per tile** -- one patch may mix
shapes -- while a fluid patch carries one colour for the whole patch.

**The leading u32 is the number of CHUNKS, not a version.** Reading only the first
chunk makes a map look nearly empty; it is what made Claude tell John a goal shape
had "no source anywhere" when the truth was "that region has never been generated".

**A chunk is 64x64 island tiles and exists only once the game has generated it** --
in practice once something has been built there. The same sandbox held 8 chunks
while the MAM sprawled to x=-100, and 2 after being cleared back to spawn; two shape
types vanished with the chunks that held them. So an absent shape means "not
generated yet", NEVER "not on this map". **To reveal a region, build in it.**

A uniform target needs only ONE quadrant of the right kind -- the MAM splits a shape
into quadrants, keeps what it wants, rotates them into the four positions and stacks
-- so the figure of merit for a source patch is how many of its four quadrants are
usable. `tools/resources.py SAVE SHAPE` ranks them.

## How the Vortex accepts shapes (EXTRACTED from the 72.8h factory)
`Layout_HUB` is **3x3 island tiles centred on its origin**, and its island-local
cells run -20..39. **The centre tile (local 0..19) is the vortex mouth.**

Delivery is a `BeltPortSender` on that centre tile's own perimeter **pointing
inward**, with nothing catching on the far side -- the vortex catches. John's
factory has 144: rows `y=0` R1 and `y=19` R3, columns `x=0` R0 and `x=19` R2, each
at positions 4..15, on floors 0-2.

The approach lane, per 4-lane edge band, copied cell-for-cell:

    x=37      BeltPortReceiver   R2      edge port of hub tile (0,0), band y 8..11
    x=36..20  BeltDefaultForward R2      straight run west
    x=19      BeltPortSender     R2      into the vortex

### Platforms connect edge-to-edge -- no space belt needed
1,792 adjacent platform pairs in the 72.8h save both carry buildings, with senders
on one edge facing receivers on the other (e.g. `Foundation_1x4(100,-542)` ->
`(99,-542)`: 16 senders facing, 12 receivers). Space belts are for spanning
distance, not for making a connection possible.

## The scoreboard: `research.json -> Shapes.StoredShapes`
A plain JSON dict of shape code -> count; the Vortex's inventory of everything ever
delivered. The 72.8h save reads `"CuCuCuCu": 1108`, `"RbRbRbRb:CrCrCrCr": 414745`.
No decoding required. This is the project's machine-checkable fitness function.

## (superseded, kept for the record) the first island-only decode
## Savegame binary: the island and building records (EXTRACTED 2026-09-05)

A `.spz2` is a ZIP of JSON plus fixed-capacity binary buffers (trailing space is zero
padding). `savegame.json: BinaryDataCheckpoints: true` refers to the repeated constant
words below — they are serializer **magic markers, not computed checksums**, which is
what makes hand-editing possible at all.

Recovered by diffing an empty sandbox world (1 island) against a populated one (86),
with every field cross-checked on both. `tools/save_islands.py` implements it.

### `maps/main/islands/<n>.bin`
`u32 count`, then `count` records. A record is located by its constant tag.

| off | size | field |
|---|---|---|
| 0 | 4 | `0xb121029a` constant tag |
| 4 | 4 | `int32 X` island-grid coordinate |
| 8 | 4 | `int32 Y` |
| 12 | 2 | `int16 Z` |
| 14 | 2 | `int16` **index into `strings.bin`** -> island layout id |
| 16 | 2 | zero |
| 18 | 1 | `uint8` rotation 0..3 |
| 19 | 33 | constant scaffolding |

**A bare island — one with no buildings on it — is exactly 52 bytes** (77 of the
reference world's 86). The 36-byte tail is **type-independent**: across every bare
island type there are only three distinct tails, differing solely in the rotation
byte. That is why a known-good record can be cloned and retargeted without decoding
the remainder.

### `maps/main/buildings/<n>.bin`
`u32 count`, then one record per island, **in island order**, keyed by the same
header. For an island with no buildings the record is exactly 30 bytes:
`int32 X, int32 Y, int16 Z, int16 strIdx, int16 zero`, then the constant
`54 0d 72 c4 04 00 00 00 00 00 00 80 21 30 a4 84`.

### `strings.bin`
`u32 count`, then `u32 length` + UTF-8 per entry. A plain intern table holding island
layout ids (`Foundation_1x1`, `SpaceBelt_Forward`, `Layout_HUB`), shape codes
(`Su--WuCu`) and type names. **References are by index, not by hash** — an early
attempt to crack `0xb121029a` as a hash of `Layout_HUB` failed against FNV/CRC/xxHash/
djb2/.NET precisely because it is a constant tag, and the layout id lives two fields
later as an index.

### Writing safely
Append **after the first record**, not at the end of the used region: the final
record's true length may include meaningful trailing zeros. Preserve each entry's
total length by trimming an equal number of pad bytes, bump the `u32 count` in *both*
files, and add to `savegame.json: StructureCount`. Reuse a layout id already in
`strings.bin` and the string table needs no edit at all.
