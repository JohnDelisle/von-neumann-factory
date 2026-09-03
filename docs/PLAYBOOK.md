# Design playbook — how we build in this project

_The reusable method, patterns, and gotchas — distinct from `conventions.md`
(game facts/constraints) and `architecture.md` (the MAM design). Add a pattern
here the moment it recurs; keep it practical. Read this + PROGRESS on resume._

## Working method (the collaboration loop)
1. Claude authors blueprints **from code** in `tools/build_modules.py` (never by
   hand-editing .spz2bp). John imports & tests **in-game**; we iterate.
2. **Extract, don't guess.** For any unfamiliar mechanic/footprint, decode one of
   John's reference blueprints (`blueprints/2026/`) and replicate the exact cells,
   rather than inventing geometry. Every blind guess this project made was wrong;
   every extraction was right.
3. **Validate narrow, then scale.** Prove a mechanic on 1 lane / 1 platform, get
   John's in-game confirmation, THEN widen to 12-lane / compose. (VN-00 -> VN-01 ->
   VN-02 followed this; it works.)
4. **Second-guess John's designs freely** — he asked for it. Critique, redesign,
   discard. But **ask before trading elegance/readability for performance.**
5. Commit + push **every** change (from the device VM), mirror the .spz2bp into the
   in-game folder, and tell John to force an in-game folder refresh.
6. Keep the docs current every session: game facts -> conventions.md, design
   choices -> architecture.md, patterns/gotchas -> here, state/handoff -> PROGRESS.md.

## Design patterns
- **Compose, don't fuse.** One function per platform (discrete-function platforms).
  Build complex machines as **assemblies** (blueprint-of-blueprints): place function
  platforms + `SpaceBelt_*` routing. Ship BOTH component and assembly blueprints.
- **Reuse John's ecosystem as black boxes** (`Quad Splitter`, `Demuxer`, `Stacker`,
  `Painter`, `Overflow`) — don't rebuild what he's already validated.
- **Operation-agnostic routing.** A proven split/merge butterfly (e.g. `Clockwise`)
  can have its operator cells swapped (rotator<->cutter) to make a new module with
  the same validated routing. Verify each item passes exactly ONE operator.
- **No waste.** Decompose base shapes with `Quad Splitter` (use all 4 quadrants);
  never isolate-one-and-discard-three.
- **Launchers on straight runs** for traversal speed (not throughput). Only where a
  real >=1-tile gap exists; never zero-span; avoid launcher spaghetti.
- **Assemble a layer only from DISJOINT single-quadrant pieces** (distinct
  positions) — rigid-body stacking merges disjoint, stacks overlapping onto a new layer.

## Build & verify checklist (run before declaring a blueprint done)
- Regenerate: `python3 tools/build_modules.py blueprints`.
- **Round-trip**: decode the generated file; confirm building count + layout.
- **Structural**: no two buildings share (X,Y,L); all cells within buildable [2,17].
- **Port bands**: every edge port on its band — N/S at X8-11, E/W at Y8-11 (per
  floor). Off-band => won't stamp (red X). This bit us on VN-05.
- **Grid render** each floor (ASCII) and eyeball flow: inputs, operators, outputs,
  turns, lifts. (See /tmp grid helpers or re-create.)
- **Config sanity**: every non-null building `C` must be
  `{"$type": "System.Byte[], mscorlib", "$value": ...}`. A config missing `$type`
  makes the game drop the whole file **silently** — it just never shows up in the
  blueprint folder. `check_configs()` enforces this in the build loop; never
  rebuild a `C` dict from scratch, use `set_config()`.
- Mirror to the in-game VN folder and `cmp` to confirm the copy is identical.
- Give John a crisp test recipe (what to feed, what to expect) + ask for a screenshot.

## Reverse-engineering John's modules (method that works)
0. **Census the whole library BEFORE designing anything new.** Run a building-type
   census over `blueprints/2026/` and decode the labels of every big blueprint. We
   spent a session planning to invent "the brain" and a "per-position type select"
   — both already existed, built and working, inside `Quaded Filter` /
   `Full Belt Any Shape Maker`. A 200-line decode script beat a session of design.
   Cheap tells: `Virtual*` = wire-layer shape maths, `ControlledSignalReceiver` =
   the HUB goal signal, `BeltFilter` = a gated lane, `Button`+`ConstantSignal` =
   a manual stand-in for a signal we're meant to supply.
1. **Read the labels first.** `LabelDefaultInternalVariant` buildings carry real
   text: `raw = base64.b64decode(C["$value"]); text = raw[2:].decode("utf-8")`
   (2-byte LE length prefix, then UTF-8). John annotates everything — "Bottom",
   "Top", "Stacked", "Passthrough", "USE ONE INPUT ONLY", even a candid
   "SHIT - Mixes lanes up in both these" on a known bug. Pair a label to its port
   by nearest-neighbour distance on the same floor. This turns guessing into reading.
2. **Walk the belt graph in code; never trace a dense maze by eye.** A ~60-line
   walker (type+R -> output direction; launcher -> nearest catcher ahead in the
   column with matching R) settles questions that hours of squinting won't. Turn
   semantics: `BeltDefaultLeftInternalVariant` = CCW (out = R-1),
   `...Mirrored` = CW (out = R+1); input direction = R for both.
   `SplitterOverflowL` = primary out R, overflow out R-1 (plain) / R+1 (mirrored).
3. **Map the component's FULL extent before generalizing.** Modules are often
   symmetric or repeated N times, and a partial view reads as complete. The
   `Fancy A+B Side Overflow` has FOUR bands (In A/In B x north/south, one per
   island-row of its 2x4); the first fix pass covered only the two that carried
   warning labels. **Absence of a label is not absence of the problem** — check the
   whole Y/X range, then diff your patch against every repeat.
4. **An in-situ instance does NOT give you a footprint.** Reading a building's
   size off two working blueprints by looking at which neighbouring cells are
   empty is a guess wearing a costume — several footprints fit the same gaps.
   For any building we have never placed ourselves, **ask John for a minimal
   reference**: that building alone on an empty platform (as
   `StackerStraight.spz2bp` did for the stacker ports). We broke this rule for the
   Goal Receiver in VN-11 and burned a round-trip on a blank platform; the
   reference (`For Claude Signal Receiver.spz2bp`) settled it in one read.
   **Ask for the box trick**: John outlined the building with a belt rectangle on
   the floor ABOVE, so the footprint is directly readable without interfering with
   the building itself. Request that framing explicitly next time — it turns a
   footprint question into a measurement.
5. **When patching a reference, assert the exact pre-edit state** of every cell you
   touch, so an upstream change fails loudly instead of silently mis-patching. And
   where John has fixed something himself, assert your generated result matches his
   cell-for-cell — that turns his work into a regression test for yours.

## Hard-won gotchas (the game's non-obvious rules)
- **Launchers fly OVER belts.** The gap cells between a `BeltPortSender` and its
  `BeltPortReceiver` need NOT be empty. This is the standard trick for crossing one
  lane over another on a single floor (belts can't cross otherwise), and John's own
  designs rely on it.
- **Stacker top-feed needs a lift**, not a sideways belt: east L0 input ->
  `Lift1UpForward`(col+1,row+1) -> L1 -> `BeltDefaultLeftMirrored` turn -> into the
  top-port cell above the stacker. Feeding the top port from the side does nothing.
- **Ports only on the 4-lane edge bands** (above). Upper-floor buildings may float
  (no L0 beneath) — that's allowed — but PORTS must be on-band.
- **Cut is always world-vertical**, keeps world-EAST half, regardless of building R.
- **Rigid-body stacking** (see patterns): disjoint merge, overlap = new layer.
- **Launchers = `BeltPortSender`/`Receiver` mid-platform**, span 1-4 tiles, belt-speed.
- **Real-game blueprints use a terser JSON schema** than our encoder emits; our
  verbose form still imports. Parse both (Entries may be a plain list or {$values}).
- **Cloud container can't reach GitHub; the device VM can.** Do all git on-device.
- **VM recycling wipes the working copy + git creds** -> re-clone with a fresh
  fine-grained PAT (see PROGRESS access checklist).

## When stuck / an approach fails
- Re-read the relevant reference blueprint and replicate its exact cells.
- Shrink to the smallest failing case; validate that in-game before scaling.
- If a design fork is genuinely John's call (platform size, throughput target,
  what "clean" means here), ask him — he's the Shapez logistics expert.
