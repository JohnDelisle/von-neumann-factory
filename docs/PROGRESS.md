# Project status & session handoff

_Last updated: 2026-09-03. **Read this first when resuming.** Then skim
`docs/architecture.md` (design + ecosystem) and `docs/conventions.md` (file
formats + reverse-engineered game mechanics)._

## What this is
Co-building an elegant, symmetric **constructive Make Anything Machine (MAM)** in
Shapez 2 with John. Claude authors blueprints from code (`tools/`); John imports &
tests them in-game; we iterate. GitHub is the source of truth; every change is
committed + pushed.

---

## >>> NEXT SESSION OBJECTIVE <<<
Build the first **assembly** ("blueprint of blueprints"): a fixed-recipe,
quarter-scale **reassembly test**.

- **What:** one base shape -> John's **`Quad Splitter`** platform (-> NE/SE/SW/NW)
  -> a chain of **three `Stacker` platforms** (Bottom+Top->Stacked) -> back to the
  original shape. If a circle goes in and a circle comes out, the compose-and-assemble
  approach is proven.
- **How:** a single multi-island Island blueprint that PLACES the `Quad Splitter` and
  three `Stacker` foundation-platforms and wires them with `SpaceBelt_*` tiles
  (see conventions.md "Assemblies"). Ship BOTH the component blueprints and the assembly.
- **First steps:** extract the exact port positions of `Quad Splitter` (its 4 quadrant
  outputs) and `Stacker` (Bottom / Top / Stacked ports), then lay space belts between them.
- **After it validates:** 2-type mix -> brain-driven type-select per position ->
  `Painter` for color -> the brain (Goal Receiver decode). Then tile quarter -> full belt.

---

## ACCESS / SETUP CHECKLIST (do these first on resume)

1. **Device**: this session is linked to `jmd-486-dx4` (Windows; `device_bash` runs in
   its Linux VM). If `mcp__remote-devices__*` tools are absent/failing, ask John to open
   the Claude desktop app on that computer.

2. **Folder access** (via `device_request_folder_access`):
   - **Shapez 2 game folder** — `C:\Users\jdeli\AppData\LocalLow\tobspr Games\shapez 2`
     (mounts at `$HOME/mnt/shapez 2`). Holds `blueprints/2026/` (John's reference library),
     `blueprints/The Von Neumann Factory/` (our in-game folder), and `savegames/`.
   - NOTE: the repo is NOT under `~/source/repos` (that's empty). Don't go hunting other
     folders — John declined broad folder browsing before.

3. **GitHub access** (this has been the recurring friction — do it right):
   - The repo working copy lives ON THE DEVICE VM at `~/von-neumann-factory`, remote
     `github.com/JohnDelisle/von-neumann-factory` (**private**).
   - **The cloud container CANNOT reach GitHub** (egress locked). The **device VM CAN**.
     => run ALL git (clone/pull/commit/push) via `device_bash`, never cloud `bash`.
   - **VM recycling wipes the working copy + credentials.** If `~/von-neumann-factory` is
     gone or `git` auth fails: ask John for a **fine-grained PAT** (Repository access =
     only `von-neumann-factory`; Repository permission = **Contents: Read and write**;
     Metadata auto-included). Then on the device VM:
     ```
     git config --global user.name "John Delisle"
     git config --global user.email "jdelisle@gmail.com"
     git config --global credential.helper store
     umask 077; printf 'https://x-access-token:%s@github.com\n' "<PAT>" > ~/.git-credentials
     git clone https://github.com/JohnDelisle/von-neumann-factory.git ~/von-neumann-factory
     git -C ~/von-neumann-factory remote set-url origin https://github.com/JohnDelisle/von-neumann-factory.git
     ```
   - Do NOT use the GitHub CLI device flow: that app has no per-repo grant -> 403 on clone.
   - The injected `GITHUB_TOKEN`/`GH_TOKEN` in the cloud container are invalid; ignore them.

4. **Reading a private repo without a PAT** (fallback, read-only): John can log into GitHub
   in the built-in browser pane; then blob pages are readable (raw.githubusercontent needs a
   token). But for real work you need the PAT + device VM clone above.

5. **Per-change workflow** (once set up):
   ```
   edit tools/build_modules.py  ->  python3 tools/build_modules.py blueprints
   cp "blueprints/<name>.spz2bp" "$HOME/mnt/shapez 2/blueprints/The Von Neumann Factory/"
   git add -A && git commit && git push        # all via device_bash
   ```
   Verify the copy landed (`cmp`). John must **force an in-game blueprint-folder refresh**
   to see newly added files (the game scans on startup / panel reopen).
   - Commit trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
     plus `Claude-Session: <session url>`.

---

## Working save & world
- **`savegames/5589333c-...`** ("Bullshitting") — fully unlocked (Level 107, ~44%
  research; **NO crystals**), cleared to ~28.5k structures (vortex + feeder belts).
  Blueprint cost = 0. `ResearchShapeCostMultiplier`=60.
- Base-supply shape/fluid patch locations in this world: still TBD (read the save map
  or ask John) — needed once we wire real base supply.

## Design decisions (see architecture.md for detail)
- **Constructive interpreter** MAM (Goal Receiver + Virtual Processing), NOT
  generate-and-filter.
- **Single-layer first**, grow to multi-layer. **Quarter (12-lane) scale first**, tile
  x4 to full 48-lane belt. **Brain-driven color** (really discrete N-select; build the
  first version UNCOLORED).
- **No isolator waste**: decompose base shapes with the `Quad Splitter` (use all 4
  quadrants), do NOT isolate-and-discard 3/4.
- **Discrete-function platforms** (one function per platform) + **blueprint-of-blueprints
  assemblies**. Ship both component and assembly blueprints.
- Clean/beautiful > tangled. Use launchers on straight runs (traversal speed). **Ask John
  before trading elegance for performance.** Second-guess/critique his designs freely (he
  asked for it).

## John's proven ecosystem = the primitives to COMPOSE (in `blueprints/2026/`)
- **`Quad Splitter`** (Foundation_2x4): shape -> NE/SE/SW/NW (1/4-belt in, 4 outs).
- **`Demuxer`** (2x4_Flipped): normalizes NE-SE-SW-NW streams.
- **`Stacker`** (multi-platform, SpaceBelt I/O): 2-input stacker, **Bottom + Top ->
  Stacked** (also Passthrough / USE-ONE-INPUT-ONLY). Assembler = chain 3 of these.
- **`Painter`** (2x4 + pipes): **Shapes + Paint -> Painted Shapes**.
- **`Overflow`** (1x1): eats excess to keep belts compressed.
- `Full Belt Quad Splitter` = 4 Quad Splitters + Demuxer + Overflow -> full belt
  (reference for how John composes a full-throughput assembly).
- Also: `Rotator`, `Clockwise`/`Counter Clockwise` (12-lane 90 CW/CCW), `Pin Setter`,
  `Half Destroyer`, `Trash`, `Shape Filter`, `Paint Mixer`, `Lift*`. "MAM working" =
  245-platform generate-and-filter MAM (reference only).

## Our module inventory (`blueprints/`, generated by `tools/build_modules.py`)
- `VN-00 coord test` — coordinate/rotation sanity check. VALIDATED.
- `VN-01 quad isolator 1lane` — HalfDestroy->Rot90CW->HalfDestroy, isolates SE. VALIDATED.
- `VN-02 half-destroy 12lane` — 12-lane launcher-optimized half-destroy (John's redesign,
  186 bldgs; = `Clockwise` butterfly with cutters). VALIDATED.
- `VN-03 rotate90CW 12lane` — launcher-optimized `Clockwise` (VN-02 layout, cut->rot).
- `VN-04 stacker 2in 1lane`, `VN-05 assembler 1lane 4quad` — hand-built stacker/assembler
  **mechanic proofs; SUPERSEDED** by composing John's `Stacker` module. (VN-05's earlier
  bugs taught us: stacker top-feed needs a lift; platform ports only exist on the 4-lane
  edge bands — see conventions.md.) Keep for reference; don't build on them.

## Key reverse-engineered facts (full detail in conventions.md)
- Blueprint = `SHAPEZ2-5-<base64(gzip(JSON))>[]_2$`; our verbose encoder imports fine.
- +X East / +Y South; R = 90 CW steps (R0 E, R1 S, R2 W, R3 N). 1x1 = 20x20, buildable
  ~[2,17], floors L0-2. Bus = 4 cols (X8-11) x 3 floors = 12 lanes, south-in/north-out.
- Cutter/Rotator/Stacker are single-cell inline (no config). HalfDestroy keeps world-EAST.
- **Stacking is rigid-body**: pieces merge into one layer only if DISJOINT quadrants;
  any overlap puts the top shape on a new layer.
- **StackerStraight ports**: bottom from behind (south), top from the cell ABOVE (L1) via
  a `Lift1UpForward`(col+1,row+1)->L1->`BeltDefaultLeftMirrored` turn; output forward.
- **Launchers** = `BeltPortSender`(launcher)/`BeltPortReceiver`(catcher) placed
  mid-platform; span 1-4 tiles; same throughput as belts (cut travel time only).
- **Edge ports only on the 4-lane band per edge**: N/S at X8-11, E/W at Y8-11, per floor.
  Off-band ports won't stamp (red X).
- **Assemblies** = Island blueprint of foundation-platforms (each carrying its `B`) +
  `SpaceBelt_*` routing tiles at island X,Y,Z,R.
