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
  Git credential is stored on the device (`~/.git-credentials`, token in
  `/tmp/ghtoken`; may need re-auth via GitHub device flow if the VM was recycled).
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
1. **Stage 1 - Quadrant isolator** (IN PROGRESS): build a narrow (1-lane) proof of
   HalfDestroy -> Rotate90 -> HalfDestroy to validate cutter/rotator footprints +
   isolation logic, then scale to the 12-lane bus. Needs: exact port cells of
   `CutterHalfInternalVariant` and `RotatorOneQuadInternalVariant` (extract from
   John's Half Destroyer / MAM blueprints, or test empirically).
2. Stage 2 painter tap, Stage 3 assembler (stackers), Stage 4 brain (Goal
   Receiver + Virtual Processing), Stage 5 parallelize x4.
3. Base supply: needs this world's shape-patch locations (circle/square/star/
   windmill) + fluid patches — read from the save map or ask John.

## Reusable references in John's 2026 blueprint folder
Rotator, Pin Setter, Half Destroyer, Painter/Painter Small, Trash, Shape Filter,
Quad Splitter, Demuxer, Great Filter, "MAM working" (245 platforms / ~65k
buildings, generate-and-filter style — reference only).
