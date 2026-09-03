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
| `VirtualAnalyzerDefault` | behind | **forward + left** (two) |
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
is the same 3x3 shape. **The channel here is 1111** (`03 57 04 00 00`), vs 123 in
the goal-driven filter — so the channel number is per-link, not a global constant.

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
