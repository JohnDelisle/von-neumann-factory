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

## Division of labour (agreed 2026-09-03)

**John builds physical layouts in-game; Claude decodes, verifies, designs logic and
codifies.** Re-plumbing an assembly out of already-validated platforms is ~10
minutes of stamping and belt-dragging for John, and is Claude's slowest and most
error-prone path — every placement failure this project has had came from Claude
authoring unfamiliar geometry blind. Conversely Claude is fast at what John can't
easily do by eye: decoding blueprints, walking belt/wire graphs to find lane
crossings, costing designs from real building counts, and turning a working layout
into reproducible generated code.

So: **when the next step is "stamp these known platforms and wire them up", ask John
to build it and send the blueprint.** Then codify it, verify it, and generalise it.
Claude's build effort is best spent on new logic and on replication/parameterisation.

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

## Extracting a footprint: the four traps (learned the hard way, 2026-09-04)

Finding that `LabelDefaultInternalVariant` is 5 cells long, not 1x1, cost **six**
in-game round trips. Every wrong turn was a reasoning error worth naming, because
each one will recur on the next unfamiliar building.

1. **Split the census by rotation before concluding.** The first pass asked "is a
   label ever adjacent to another building?", got 364 yeses, and cleared labels
   entirely. But a label may sit beside something *perpendicular* to its axis and
   never *along* it. Re-running the identical census **split by `R`** made the answer
   jump out: 0 occurrences along the axis, thousands across it. **A footprint is
   directional; a census that ignores `R` averages the signal away.**

2. **Absence from John's library is not a game rule.** A census showed 45/45 of his
   signal-building port cells hold only a Wire/Display/ConstantSignal, so we inferred
   that a `Virtual*` may not sit there — and shipped it as a validated rule. `VN-13q1`
   put an analyzer straight on a port cell and it ran fine. **A census tells you what
   John does. Only an in-game test tells you what the game permits.**

3. **Test a footprint model against the whole library, not one example.** The decisive
   evidence was mechanical: apply an N-cell model to all 3,100 labels and count
   collisions with known-good blueprints. **0 at N=5, 2,569 at N=7.** A model that
   contradicts a working blueprint is wrong, and this costs seconds to run. Do it
   *before* asking John to stamp anything.

4. **Check the margin, not just the bounds.** A label body must stay within `[3,16]`
   on a 1x1 — one cell inside the buildable window. Nothing else needs that. Do not
   assume a building may use every buildable cell.

**And the symptom is a clue, not noise.** These two rules produce *different*
failures: an overlap makes the game discard the **whole file** (it never appears in
the folder), while a margin violation alone imports fine and **fails to stamp**. We
kept re-diagnosing because the symptom changed. **Ask John which of the two he is
seeing — "missing from the folder" and "red X on stamp" are different bugs.**

### Ask for a purpose-built reference sooner
John built `For Claude Labels.spz2bp` — labels at the corners and edges, boxed in
belt — and it settled in one read what six rounds of inference had not. This is the
same lesson the Goal Receiver taught (`For Claude Signal Receiver.spz2bp`), and we
paid it twice. **The moment a footprint is in doubt, ask for the box trick.** It is
minutes of his time and replaces a whole session of ours.

### Encode every rule as a build-time check
`validate_layout()` now refuses out-of-bounds cells, collisions **including the
invisible cells of multi-cell buildings**, label margins, and any multi-cell building
whose anchor has never been extracted. It is regression-tested against every layout
that actually failed in-game. **When a rule is learned, land it as a check the same
session, with the failing layouts as test cases** — otherwise it will be re-learned.

## Reviewing a machine John built: check the arrows, not the buildings

The FSB MAM review (2026-09-05) found its one bug in a `SpaceBelt_Forward` that
should have been a `SpaceBelt_LeftFwdSplitter`. Nothing about the file looked wrong:
the platforms were all uniform, no islands overlapped, no belt dead-ended, every lift
had its clearance. The branch it should have fed was **fully built and correctly
wired all the way to its destination** — it just had no source.

Three habits that made it findable:

1. **Trace the graph, don't read the map.** Propagate a label from every belt with no
   upstream forward through the network, then look at what arrives at each platform
   input. Fourteen of sixteen deliveries listed "16 filters"; two listed "one stray
   belt". That is a one-line diagnosis from a 1,568-island file.
2. **A dead end and an orphan are different bugs, and only one of them was checked.**
   Everything the tool looked for was "does this go somewhere". Nothing asked "does
   anything arrive here". Add the mirror of every check you write.
3. **Exploit the machine's own regularity.** Four bands doing the same job four
   different-looking ways is not a bug; four bands where three share a splitter
   pattern and one does not is. Tabulate the repeated structure and read down the
   column — the odd one out names itself.

And the anti-habit: **fix your model before you accuse the build.** The first run
reported 120 dead ends. All 120 were the tool treating a lift as a flat belt. If that
had been passed on as a finding it would have buried the one real line.

## Read the game's assemblies before theorising about the game

`tools/spz2api` loads the Shapez 2 and ShapezShifter assemblies with
`MetadataLoadContext` — reflection only, nothing executes, no Unity, game not running.

```
dotnet run --project tools/spz2api -- asms                       # every assembly + type count
dotnet run --project tools/spz2api -- types   <pattern> [asm]    # matching type names
dotnet run --project tools/spz2api -- members <pattern>          # full signatures
```

`<pattern>` is a case-insensitive substring, or `/regex/`. **In Git Bash, export
`MSYS_NO_PATHCONV=1` before using the `/regex/` form** or MSYS rewrites it into a
Windows path and you silently get zero matches.

Ten minutes with this replaced a model we had built over several sessions and six
round trips: we believed a malformed blueprint made the game discard the whole file,
and the truth is `BlueprintSanitizer` quietly strips the offending entries and imports
the rest. Every "silent failure" symptom in conventions.md is that one behaviour.

The lesson generalises past this project: when a closed system keeps surprising you,
check whether its own source of truth is *readable* before you spend more round trips
inferring it from the outside.

## Ask whether the system will just tell you

Two hours after `tools/spz2api` read the game's assemblies, `debug.export-game-data`
turned out to dump the building definitions as JSON — footprints and ports, declared.
Between them they replaced two models we had built over several sessions and paid for
in round trips: the blueprint failure model (`BlueprintSanitizer` strips entries, it
does not discard files) and the footprint table (the controlled-signal family is
3x3x**3**, and thirteen multi-cell types we place were modelled as 1x1).

The measuring we did was not wasted — it is what let us *check* the real data instead
of trusting it, and the fitted belt model came out confirmed. But the ordering was
backwards, and the cost was six round trips on VN-13 alone.

So, before reverse-engineering a closed system: **check what it will hand over.**
Debug consoles, data exports, schema dumps, its own assemblies. Then measure to
validate what you were given — the export omitted wire ports and the label edge
margin, both of which we only have because we measured.

And when the real data arrives, **re-fit rather than retro-fit**. `Tiles` gave exact
per-cell offsets including Z, which the old `(w, h, anchor)` table could not express at
all; replacing it outright was less work than patching it and caught the Z bugs for
free. Every blueprint then regenerated byte-identical to the in-game-validated files —
which is how you know a stricter model is a safe swap.

## A round-trip does not validate a format (2026-09-05, one crash)

`save_world.py` re-serialized 18,966 islands byte-identically across three worlds,
including a 660,476-building factory. Then the first written world crashed the game
on load, because the writer emitted a trailing island-title block that **does not
exist in the format**.

The round-trip could not possibly have caught it. It proves the writer agrees with
the reader, and both were wrong in the same place: an early exploratory pass walked
buildings at a fixed 15-byte stride, mis-read a Label's own config as a trailing
island field, and the real parser inherited the belief as a branch that **never
fires on real data**. Unexercised branches are invisible to round-trips by
construction.

Three habits from it:

1. **Census every optional field before you write one.** "How many of the 18,966
   real islands actually have this?" took one line and answered it: zero. Any parser
   branch that fires zero times is a claim about the format that nothing has tested.
2. **Find an invariant outside your own code.** The record size law
   (`52 + [12+len(icfg)] + sum(15 + [12+len(cfg)])`) is derived from the grammar, not
   from the serializer, so it can disagree with both. It now runs over the whole
   world before any write. The first draft of the law was itself 4 bytes light on
   islands carrying an island-config -- and the same census caught *that*, which is
   the point: check the law against reality before trusting it.
3. **Read the game's own error.** `Checkpoint mismatch, expected 2225352737 but got
   3295808852` is not noise -- 0x84A43021 is the close marker and 0xC4720D54 is the
   open marker, so it says "I wanted this block to end and found another beginning",
   and it names the island type. That is a one-line diagnosis. Always pull
   `AppData/LocalLow/tobspr Games/shapez 2/Player.log` before theorising.

## Ask what the system will just tell you -- the sequel

Two files nobody had opened held what several sessions of decoding were aimed at:

* `research.json -> Shapes.StoredShapes` is the Vortex scoreboard, as plain JSON.
  We were about to reverse-engineer `statistics.bin` for it.
* `maps/main/resource-chunks.bin` gives every shape patch and its exact tiles, which
  is what decides whether a requested shape is even makeable on this map.

The general move: **before decoding a binary, open every JSON in the archive.**

## Tool output is a verdict, not a table (2026-09-05)

Every read tool here now obeys one rule, enforced by `tools/say.py`:

> **The default output fits in ~15 lines and ends in a verdict. Detail moves behind
> `--full`, and the tool always says how many rows it held back.**

    import say
    say.detail("one row of evidence")                 # only under --full
    say.some(rows, fmt=str, cap=5, label="more")      # capped, and honest about it
    say.verdict(ok, "118/118 islands accepted")       # the last line
    path = say.args()[0]                              # argv minus the flags

Measured effect on the tools we had: `verify_mam.py` 13 lines -> **1**, `observe.py`
~40 -> **8**, `resources.py` ~270 -> **17**, `save_world.py` round trip 2 -> **1**.
Nothing was deleted; `--full` still prints every line it ever printed.

**Why it matters more than it looks.** Cost per model call is (context size) x (turns),
and a tool result is re-read by every later call in the session — so a 270-line table
is paid for hundreds of times, and a table that gets piped through `head` was paid for
in full before the `head` ran. `docs/token-economics.md` has the measurements.

The same rule applies to anything typed ad hoc: **do not print a table and then read
it — write the assertion, and print PASS/FAIL plus the two or three numbers that decide
it.** If a verdict ever surprises you, `--full` is right there.
