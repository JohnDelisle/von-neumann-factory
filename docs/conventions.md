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
