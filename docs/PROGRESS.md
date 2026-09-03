# Project status & session handoff

_Last updated: 2026-09-03. Read this first when resuming in a new session._

## What this is
Co-building an elegant, symmetric **constructive Make Anything Machine (MAM)** in
Shapez 2 with John (see README + docs/architecture.md). Blueprints are authored
from code, John imports & tests them in-game, we iterate. GitHub is the source of
truth; each change is committed + pushed.

## Done so far
- Blueprint + savegame formats fully decoded (docs/conventions.md).
- Encoder validated by in-game round-trip; **from-scratch authoring confirmed**
  via `VN-00 coord test` (John verified: East-flow run turning South, single
  layer, no offset).
- Conventions locked: +X East / +Y South, R = 90 deg CW steps, 1x1 platform =
  20x20 (buildable ~[2,17], floors L0-2), the **12-lane bus** interconnect,
  cutter mechanics (Half Destroyer keeps EAST).
- `tools/shapez_bp.py` (codec) + `tools/build_modules.py` (generator).
- Repo set up and pushed.
- **Cutter/Rotator footprints extracted** from John's blueprints: `CutterHalfInternalVariant`,
  `RotatorOneQuadInternalVariant` (90 CW) and `RotatorOneQuadCCWInternalVariant` are all
  **single-cell inline** buildings (no config), `R` = flow direction. `Clockwise`/`Counter
  Clockwise` confirm CW/CCW; `Half Destroyer` confirms keep-east. NOTE: real-game exports use
  a **terser schema** (plain `Entries` list, omitted default fields, `Icon`/`BinaryVersion`,
  `V:1137/1138`); our verbose encoder still imports fine.
- **`VN-01 quad isolator 1lane`** VALIDATED in-game (John): HalfDestroy -> Rotate90 CW ->
  HalfDestroy on one lane (X9, L0, north-flow R3) correctly isolates the SE quadrant, and
  the three single-cell transforms chain inline (adjacent Y14/Y13/Y12) with no belts between.
  Lane geometry: X9 = **2nd input lane from the left** of the 4-lane space-belt input (X8-11);
  X8 free to the left, X10-X11 spare to the right. NOTE: single building per stage is
  throughput-limited (see below) - fine for the proof, must parallelize for full-speed.

## Environment / operational notes (IMPORTANT for resuming)
- Device: `jmd-486-dx4` (Windows; device_bash runs in its Linux VM).
- Game files: `C:\Users\jdeli\AppData\LocalLow\tobspr Games\shapez 2`
  (mounted at `$HOME/mnt/shapez 2`). Grant folder access to this on resume.
- **Working save**: `savegames/5589333c-...` ("Bullshitting") — fully unlocked
  (Level 107, ~44% research; NO crystals), cleared to ~28.5k structures (just the
  vortex + feeder belts). Blueprint cost = 0. `ResearchShapeCostMultiplier`=60.
- **In-game blueprint folder**: `blueprints/The Von Neumann Factory/`.
- **Repo working copy lives ON THE DEVICE** at `~/von-neumann-factory` (device VM
  home), remote `github.com/JohnDelisle/von-neumann-factory` (private).
  Git auth = a **fine-grained PAT** (Contents R/W on this repo) in `~/.git-credentials`
  on the device VM (helper=store; `user.name/email` set globally). **VM recycling wipes
  this** -> John generates a fresh fine-grained PAT and Claude re-stores it. (GitHub CLI
  device flow does NOT work here: that app has no per-repo grant -> 403 on clone.)
- **Cloud container CANNOT reach GitHub** (egress locked to configured repos):
  do all git create/push **from the device** (device_bash), not the cloud.
- Workflow per change: edit in repo -> `python3 tools/build_modules.py blueprints`
  -> `cp` the .spz2bp into the in-game VN folder -> `git add/commit/push`.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Design decisions
- **Constructive interpreter** MAM (uses Goal Receiver + Virtual Processing),
  NOT generate-and-filter.
- **12-lane bus** standard; 1 space-belt input = 12 lanes (4x3); full space belt
  = 4 inputs = 48 lanes. Build the 12-lane unit to tile x4.
- **Clean/beautiful > tangled**; consistent module shapes. Use ramps to speed
  shapes.

## Next steps
1. **Stage 1 - Quadrant isolator**: 1-lane proof (`VN-01`) VALIDATED. 12-lane build (John:
   full-12-lane-in-one-pass, per-lane selectable quadrant):
   - **`VN-02 half-destroy 12lane`** BUILT + VALIDATED (John: "great"), then John added
     **belt launchers** on the straights (traversal-speed, not throughput; launcher=sender/
     catcher=receiver mid-platform, see conventions.md) -- folded back into `build_modules.py`
     as the source of truth (186 bldgs, regen set-equal to John's saved file). Original note: `Clockwise`'s proven
     split->op->merge butterfly is operation-agnostic (each item hits exactly 1 operator), so
     we swapped its 24 RotatorOneQuad -> CutterHalf to get a 12-lane full-throughput pass-through
     Half Destroyer (2 cutters/lane, south-in Y17/north-out Y2, island R=2). Keeps world-EAST half.
   - **`VN-03 rotate90CW 12lane`** = launcher-optimized `Clockwise` (derived from VN-02's
     validated launcher layout, cutter->rotator; rotator cells == Clockwise, launchers == VN-02).
   - **Composition** (uniform, isolates orig-NE quadrant): `VN-02` -> `VN-03` -> `VN-02`
     as 3 snap-together 1x1 modules on the bus (HalfDestroy -> Rotate90CW -> HalfDestroy).
   - **Per-lane selectable quadrant** = add a SELECTABLE PRE-ROTATE stage before the isolator:
     same butterfly, per-lane operator chosen by baked k in {0:belt-pass -> orig NE, 1:RotCW ->
     orig NW, 2:RotHalf(180) -> orig SW, 3:RotCCW -> orig SE}. Needs the lane->operator-cell map
     (derive by simulating flow through the butterfly). Build AFTER VN-02 validates.
   - John TEST: import `VN-02` alone, feed any full shape on all 4 lanes x 3 floors; expect only
     the world-EAST half (e.g. `CuCuCuCu` -> the two east quadrants) out on every lane.
2. Stage 2 painter tap, Stage 3 assembler (stackers), Stage 4 brain (Goal
   Receiver + Virtual Processing), Stage 5 parallelize x4.
3. Base supply: needs this world's shape-patch locations (circle/square/star/
   windmill) + fluid patches — read from the save map or ask John.

## Reusable references in John's 2026 blueprint folder
Rotator, Pin Setter, Half Destroyer, Painter/Painter Small, Trash, Shape Filter,
Quad Splitter, Demuxer, Great Filter, "MAM working" (245 platforms / ~65k
buildings, generate-and-filter style — reference only).
