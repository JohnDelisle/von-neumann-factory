# Project status & session handoff

_Last updated: 2026-09-03. **Read this first when resuming.** Then read
`docs/PLAYBOOK.md` (how we build — method, patterns, gotchas), and skim
`docs/architecture.md` (the MAM design + ecosystem) and `docs/conventions.md`
(file formats + reverse-engineered game constraints)._

## What this is
Co-building an elegant, symmetric **constructive Make Anything Machine (MAM)** in
Shapez 2 with John. Claude authors blueprints from code (`tools/`); John imports &
tests them in-game; we iterate. GitHub is the source of truth; every change is
committed + pushed.

---

## >>> REASSEMBLY TEST: VALIDATED (2026-09-03) <<<
The quarter-scale reassembly test is **done and confirmed working in-game by John**:
one base shape -> `Quad Splitter` (-> NE/SE/SW/NW) -> `Demuxer` (normalizes
orientation) -> `Stacker supporting empty quadrants` -> reassembled, matching the
original input (tested with one blank quadrant too, per John). The
compose-and-assemble approach is proven.

- **The missing piece was `Demuxer`**: Quad Splitter's 4 outputs need normalizing
  (each output belt must carry its quadrant shape in its ORIGINAL orientation, not
  rotated) before they reach the Stacker. `Demuxer` (`Foundation_2x4_Flipped`) does
  that, sitting with **zero gap** directly against Quad Splitter's west edge —
  adjacent platform edges connect straight across the island boundary, no
  `SpaceBelt_*` tile needed, as long as ports line up.
- **`Stacker.spz2bp` (plain, 4-platform chain) is already the complete 4-quadrant
  stack as one unit** — no need to chain 3 copies (that was a wrong assumption
  from before we could read the game's own labels). For robustness (handles empty
  quadrants), John pointed to **`Stacker supporting empty quadrants.spz2bp`** (38
  islands, ~7.7k buildings, 4 distinct quadrant inputs via west-side ports, order
  irrelevant) instead — that's what's wired into `VN-07`.
- **Red X's on stamp are expected, not errors**: each Stacker platform's "Top"
  input has two alternate physical ports with a "USE ONE INPUT ONLY" label between
  them; the game flags the unused one's adjacent empty cell as a warning.
- **`vn07_reassembly_test()` in `build_modules.py` reproduces John's tested layout
  from code**, diffed byte-for-byte against his hand-built
  `blueprints/The Von Neumann Factory/For Claude Splitter and Stacker.spz2bp` —
  exact match on every foundation and every wiring tile except the 4 disposal-only
  `Trash` sinks (same building count, trivially different internal content,
  harmless — they're test scaffolding, not reassembly logic).
- **Key technique unlocked this session: read the labels, don't guess.**
  `LabelDefaultInternalVariant` buildings carry real base64-encoded text (decode:
  `raw = base64.b64decode(C["$value"]); text = raw[2:].decode("utf-8")` — 2-byte
  length prefix then UTF-8). John's reference blueprints are fully annotated
  ("Bottom", "Top", "Stacked", "Passthrough", "USE ONE INPUT ONLY"). Pair a label
  to its port by nearest-neighbor distance on the same floor. Use this on every
  future reference blueprint before attempting to reverse-engineer ports from
  coordinates alone.

## >>> ARCHITECTURE SESSION (2026-09-03): the gap list collapsed <<<
Read `docs/architecture.md` ">>> BIG FINDING <<<" for the full write-up. Summary:

**Decoding `Full Belt Any Shape Maker.spz2bp` showed John already has ~85% of the
MAM built.** It is byte-for-byte the same machine as `MAM working` (64 972
buildings, same islands, translated +1 in X), and it is **exactly VN-07 plus one
platform**: the `Quaded Filter`.

Per lane (x4 = full belt):
`mixed base shapes -> Quad Splitter -> Demuxer -> Quaded Filter -> Stacker
supporting empty quadrants -> the requested shape`.

The `Quaded Filter` (`Foundation_1x4`, 4 bands NW/SW/SE/NE x 12 lanes, 48
`BeltFilter`s) contains **both** things PROGRESS.md called missing:
- **the brain** — a `VirtualRotator`/`VirtualAnalyzer` fan that decomposes ONE
  target-shape signal into its four quadrant signals;
- **per-position type select** — each band's 12 filters gated by its quadrant signal.

The only hardcoded part is *where the target shape comes from*: 4 `ButtonDefault` +
4 `ConstantSignalDefault` presets (`CuCuCuCu` / `RuRuRuRu` / `SuSuSuSu` / `WuWuWuWu`)
through a `LogicGateIf` priority chain. `Shape Filter` and `Smart Filter` already
show the replacement — `ControlledSignalReceiver` (config = int32 `2`), the **Goal
Receiver**. `Quaded Color Filter` likewise already does **per-position colour
select** (r/g/b/null, independently per band).

### Real remaining gaps
1. Target shape from the HUB, not buttons (graft `ControlledSignalReceiver` in).
2. Colour — filter a coloured supply vs paint each quadrant stream (John's call);
   `Quaded Color Filter` covers only 3 of 8 colours.
3. Multi-layer assembly — unbuilt.
4. Base supply — patch locations in the working save still TBD.
5. Quadrant waste — a 4-type mixed supply means each band rejects ~3/4 of arrivals.
6. Goal-change transient — stale quadrants on the belts when the HUB request changes.
7. Pins / crystals — out of scope for v1 (no crystals in the working save).

### BUILT THIS SESSION — awaiting John's in-game test
John's calls: **VN-10 then VN-11**; colour later via **paint-per-quadrant-stream**;
`ControlledSignalReceiver` config `2` = **a HUB goal slot index**.

- **`VN-10 any shape maker lane fixed`** — `Full Belt Any Shape Maker` with all
  **eight** embedded `Fancy A+B Side Overflow` units lane-fixed. Nothing else
  touched; asserted at build time that the island count is unchanged and exactly
  the 8 stale bug-warning labels were dropped. Fancy A+B units are found by John's
  own `"Fancy"` label so the 2x4 Demuxers are never patched by accident.
- **`VN-11 quaded filter goal driven`** — the `Quaded Filter` platform alone, with
  its **last preset slot replaced by the HUB Goal Receiver**. The five shape
  presets survive as manual overrides; only the enabled button moved.
- **`VN-12 MAM goal driven`** — VN-10 + VN-11 on all four lanes. **This is the MAM**:
  full belt of mixed uncoloured base shapes in, full belt of whatever single-layer
  shape the HUB requests out.

**How the preset bank works** (embedded copy, 6 slots — decoded, not guessed):
button `(5, 2k+14)` gates ConstantSignal `(4, 2k+15)` through a `LogicGateIf`:
null / `--CuCu--` / `RuRuRuRu` / `SuSuSuSu` / `WuWuWuWu` / `CuRuSuWu`. **The
`--CuCu--` and `CuRuSuWu` presets are the proof this machine builds arbitrary
single-layer shapes** — empty quadrants, and four different types at once.
VN-11 removes the `CuRuSuWu` constant and puts the Goal Receiver at `(3,25) R0`.

**The one thing extracted-but-unconfirmed: the Goal Receiver's footprint.** Both of
John's working instances (`Shape Filter` origin `(4,35)` R3 -> wire at `(4,33)`;
`Smart Filter` origin `(13,19)` R0 -> wire at `(15,19)`) show it occupying its
origin cell plus the next along R, driving the wire cell at origin+2. VN-11 places
it accordingly. **If it red-X's, it's a one-cell footprint error — shift the origin
and rebuild.** Everything else in VN-11/VN-12 is John's own verbatim.

**First cut of VN-11/VN-12 was a dud — fixed.** They didn't appear in the in-game
folder at all: the button config had been rebuilt as `{"$value": ...}`, dropping
`"$type": "System.Byte[], mscorlib"`, and the game **silently discards a blueprint
file with a malformed config**. Rebuilt via `set_config()`, and `check_configs()`
now runs over every module in the build loop so it can't recur. Remember the
diagnostic: **missing from the folder = malformed file, not a stale refresh.**

### TEST RECIPE for John
1. Refresh the in-game blueprint folder; stamp **`VN-12 MAM goal driven`**.
2. Feed its east input a full belt of **mixed uncoloured base shapes** (Cu/Ru/Su/Wu).
3. Set a HUB goal to a single-layer uncoloured shape and watch the west output.
4. Change the HUB goal; the output should follow (expect a transient while stale
   quadrants clear the belts).
5. Sanity fallback: switch the enabled button back to a preset slot (e.g.
   `CuRuSuWu`) — the machine should behave exactly as John's original did.
Screenshot of the output belt + any red X's, please.

### Still open (not blocking the test)
- Colour: **decided — paint each quadrant stream** between `Quaded Filter` and the
  stacker. Needs a signal-driven paint selector (doesn't exist yet); `Quaded Color
  Filter` stays available as the filter-based fallback.
- Mixed supply and ~3/4 quadrant waste — acceptable, or a type router upstream?
- Single-layer v1, or design the layer stack in now?
- `Full Belt Any Shape Maker` vs `MAM working` — same machine; which name survives?

Reference blueprints for all of the above are now committed under
`blueprints/reference/` (Full Belt Any Shape Maker, Filter, Quaded Filter, Quaded
Color Filter, Smart Filter, Shape Filter, Painter, Overflow).
2. ~~**Refactor pass on known-buggy components**: the "Fancy A+B Side Overflow"
   unit's self-documented lane-swap bug.~~ **DONE 2026-09-03** — root-caused and
   fixed; see below and conventions.md "Fancy A+B Side Overflow: the inner/outer
   lane-swap bug (fixed)". **Awaiting John's in-game confirmation.**

## Fancy A+B lane-swap bug: FIXED + VALIDATED IN-GAME (2026-09-03)
_John confirmed VN-08, VN-09 and VN-07 all working in-game._
- **Symptom** (John): outer lanes of In A / In B overflow to "A+B Overflow" as the
  inner lanes, and vice versa. Inconsequential in practice, fixed for cleanliness.
- **Root cause**: each band's OUTER rows tap overflow at splitter column X=9 (In B)
  / X=8 (In A); INNER rows tap at X=7 / X=6. The downstream weave sends the X=9/X=8
  taps to the INNER final outputs and X=7/X=6 to the OUTER ones.
- **Fix**: swap the splitter columns between outer and inner rows in each band, and
  shift each outer row's launcher hop one cell east (launchers fly over belts — a
  trick John's own design already uses). 168 retyped cells across all four bands,
  no buildings added or removed (bar 2 stale warning labels), no crossings introduced.
- **The component has FOUR bands** (In A / In B x north / south = 48 lanes), one per
  island-row of the 2x4 foundation. The first pass only fixed the north half,
  because only that half carried the "SHIT" warning labels; **John caught this and
  mirrored the fix to the south half.** The patch is now generated from two base
  patterns stamped at four band offsets (In B: 0, -20; In A: 0, -60).
- **Cross-validated against John's own fix**: the generated patch is asserted at
  build time to be cell-for-cell identical to his hand-mirrored version. Zero
  differing cells; the build breaks if that ever stops holding.
- **Verified by graph-walking the belts**: all 16 lanes map outer->outer /
  inner->inner, and all 48 primary pass-through paths (16 lanes x 3 floors) stay
  lane-preserving.
- **Shipped + VALIDATED IN-GAME**: `VN-08 fancy A+B lane fixed` (standalone),
  `VN-09 stacker empty quadrants fixed` (both embedded copies patched), and
  `VN-07` rebuilt on top of the fixed stacker — John confirmed all three working.
- **The lane fix is now the baseline.** Build any further stacker work on
  `load_fixed_stacker_islands()`, not the stock reference.

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
- `VN-06 quad splitter test` — John's real `Quad Splitter` (Foundation_2x4, reused
  verbatim/black-box) + 5 SpaceBelt stub tiles (1 input east, 4 outputs west, one per
  quadrant row). Structurally validated (round-tripped, building count intact); NOT
  yet in-game confirmed. See PROGRESS "NEXT SESSION OBJECTIVE" for status.
- `VN-08 fancy A+B lane fixed` — `Fancy A+B Side Overflow` with the inner/outer
  lane-swap bug fixed on all 4 bands (see above). Generated from the pre-fix
  reference and asserted identical to John's own fixed version. **VALIDATED IN-GAME.**
- `VN-09 stacker empty quadrants fixed` — `Stacker supporting empty quadrants`
  with both embedded Fancy A+B units lane-fixed. Drop-in replacement; everything
  else byte-identical to John's original. **VALIDATED IN-GAME.**
- `VN-10 any shape maker lane fixed` — John's `Full Belt Any Shape Maker` with all
  8 embedded `Fancy A+B` units lane-fixed. **NOT yet in-game confirmed.**
- `VN-11 quaded filter goal driven` — `Quaded Filter` platform with its last preset
  slot replaced by the HUB Goal Receiver. **NOT yet in-game confirmed.**
- `VN-12 MAM goal driven` — VN-10 + VN-11 x4 lanes. **The MAM.** **NOT yet
  in-game confirmed** — see the test recipe above.
- `VN-07 reassembly test` — `Quad Splitter` -> `Demuxer` -> `Stacker supporting
  empty quadrants` (LANE-FIXED) -> test-rig `Trash` sinks. **VALIDATED IN-GAME by
  John**, both before and after the lane fix
  (2026-09-03): full round-trip, reassembles the original shape, tolerates one
  blank quadrant. All foundations verbatim/black-box from `blueprints/reference/`;
  wiring in `VN07_WIRING`, diffed byte-for-byte against John's tested file.

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
