# PROGRESS archive — everything superseded as of 2026-09-05

Split out of `docs/PROGRESS.md` on 2026-09-05 so that a fresh session loads ~140
lines instead of 1,138. Nothing was deleted: this is the previous file from the
first superseded banner onward, verbatim and in its original order (newest first).
Read it when you need the WHY behind a decision; `docs/PROGRESS.md` alone is enough
to know where the work stands.

---

# (superseded) >>> START HERE (2026-09-05, night): ONE TEST STANDS BETWEEN US AND CHANNEL 789 <<<

## Resume in four commands

```
python tools/game.py up            # stop game, start it, load the NAMED sandbox
python tools/bridge.py status      # live map reachable? which world?
python tools/observe.py <newest save>   # the Vortex scoreboard = our fitness function
python tools/bridge.py speed 25    # run the sim hot
```

`tools/game.py` knows the sandbox uid (`d58e3f84-...`) and waits on the world NAME,
because the main menu renders a live background world and will happily hand you an
`IMapModel` for the wrong map.

## The scoreboard, as of backup-v98

| channel | goal | delivered | state |
|---|---|---|---|
| 123 | `CuCuCuCu` | **460,464** | DONE (target was 1,000). VN-15, a miner on island (2,0) into the Vortex east face. |
| 789 | `SuSuSuSu` | 0 | VN-16 stalls at stage C. Still open. |
| 456 | `WuWuWuWu` | 0 | Untouched. Nearest `Wu----Ru` at island (96,0), 97 tiles; a pure 4/4 patch at (544,200), 1,073 tiles (wants a train). |

VN-16 already delivers **107,724 `--SuSu--`** — mining and cutting work at volume.
Only the recombination is broken.

## THE ACTIVE TASK: VN-16 stage C

Shape algebra (measured, not predicted):

```
SuSuCu--   cut, keep delivered half  ->  --SuSu--      (WORKS, 107k delivered)
--SuSu--   rotate 180                ->  Su----Su      disjoint
stack the two                        ->  SuSuSuSu
```

Stage C is written in `tools/build_star_machine.py` and **deliberately disabled** —
`cutter_platform()` returns the working stage B. When enabled, every building places
correctly (verified cell-by-cell in the live game; the lift and the stacker both span
floors 0 and 1 as they should) and **all output stops**: the stacker waits on a second
input that never arrives.

**Prime suspect:** which side `Splitter1To2L`'s second output actually emits on. It
declares outputs on sides 0 and 3. If side 3 resolves to -Y rather than the +Y I
assumed, branch B is fed straight into the trash that catches the cutter's discarded
half — which would look exactly like this.

**Run it BATCHED.** Do not test one variant per build. Put `Splitter1To2LInternalVariant`
on one lane and `Splitter1To2LInternalVariantMirrored` (outs side 0 and side 1) on a
parallel lane in the SAME save, each feeding its own stacker, and let one restart
discriminate. Four sequential single-hypothesis cycles is what burned the last budget.

## New since the last handoff

* **Unlimited savegames are ON and autosave is OFF** (John changed both). Verified
  empirically: the folder went 26 -> 27 saves, and it had been pinned at exactly 25
  with the oldest pruned on every write. **That `Keep25` rotation is what silently
  destroyed v2-v14 earlier, including the v13 miner donor** — survivors live in
  `savegames-archive/` and `MINER_DONOR` points there. The hazard is now gone, so save
  freely and drop the reuse-one-filename workaround.
* **`settings.json` on disk is STALE while the game runs.** It still reads
  `autosave-interval = Minutes5` and `savegame-backup-count = Keep25` even though both
  were changed; the game buffers settings and flushes on exit. Trust observed behaviour
  over that file.
* **Saving on demand works**, no human needed:
  `python tools/bridge.py call Game.Orchestration.GameBootstrapper.GameOrchestrator.CurrentSubOrchestrator.TrySaveCurrentSync`
* **`token-saver` skill installed** at `~/.claude/skills/token-saver/` (personal scope,
  so it applies to every project). Its examples were patched `python3` -> `python`,
  which does not exist on Windows. It registers as a slash command on the next Claude
  Code start. Rules that bite hardest here: prefer local deterministic code over model
  calls, select passages out of this 57KB file rather than loading it whole, and batch
  in-game experiments.

## The rule that cost four builds — do not relearn it

**A platform edge port is a 12-LANE GROUP:** band cells 8, 9, 10, 11 on EACH of floors
0, 1 and 2 — all twelve, or the port never connects. Every space-belt-fed platform in
John's 72.8h factory places all twelve; not one places a subset. A partial group fails
SILENTLY: the feeding space belt fills up (1,524 bytes of cargo state against an empty
474) and the platform behind it stays empty, with no error anywhere.

**Diagnostic signal:** cargo state on the OUTGOING space belt is meaningful. A
platform's own runtime-state record is NOT — VN-15's miner reads 30 bytes (the empty
form) while delivering 28,000 shapes. I misread that for several cycles.

## The two halves, and why both stay

| offline (`save_world`, `stamp`, `observe`, `resources`) | live (`ClaudeBridge` + `bridge.py`) |
|---|---|
| design, validate, author whole machines, read the scoreboard | place, delete, control speed, save, read the running sim |
| byte-exact round trip on 18,966 islands | no reload, no human |

The offline half is the **verification oracle** for the live half: after writing to a
running world, save and re-parse it, and run the size law.

## The bridge, in one paragraph

A ShapezShifter mod (`mod/ClaudeBridge`) polls a file mailbox from inside the game's
own `Tick`, so Unity objects are only touched on the game thread. `mod/build.ps1`
builds and deploys it (it re-reads `SPZ2_*` from the USER environment every time —
they are not inherited by a fresh shell, and MSBuild then reports missing *namespaces*
rather than missing references). A new DLL needs a game restart, which `game.py up`
does in ~90s. Verbs: `ping status inspect members commands console speed pause resume
get set call find statics resolve saves load quit at place rotations resource`.

**`get`/`call`/`resolve` are the escape hatch that matters.** Every hard-coded verb is
a guess about what will turn out to matter, and a wrong guess costs a rebuild AND a
restart. With a general evaluator, new corners of the game are reachable from the
command line — and the error messages list the members that DO exist, which is how
essentially every unknown below was found, one probe at a time.

## Hard-won, in the running game

* **`GameHelper.Core` is non-null at the MAIN MENU** — the menu renders a background
  world ("Menu Background Supporter") and hands out a live `IMapModel`. Anything that
  writes MUST check which world is loaded.
* **No command-line argument loads a savegame.** The complete list is
  `--set-modding-env-vars --ignore-mods --safe-mode --disable-store-sdk
  --custom-translations --danger-bypass-modded-savegame-checks --ignore-hw-checks
  --no-dynamic-content`. Loading must happen in-process.
* **`GameBootstrapper` is a static class**, therefore abstract, therefore invisible to
  any UnityEngine.Object scan — and it is the only holder of the `GameOrchestrator`.
* **Constructing a `SavegameBlobReader` is not enough** — Blobs/Metadata/StringLUT stay
  empty and the load dies with a bare NullReferenceException. `SaveFileAccessor.Read`
  is the factory that opens the archive.
* **The `IBuildingResolver` is NOT in the DI container** (the initialization container
  has no children, so session services never appear there). It is
  `GameOrchestrator.CurrentSubOrchestrator.Mode.Buildings`.
* **`GridRotation` is a struct with static readonly fields**, not an enum.
* **`GetBuilding` throws** on a tile owned by no island — a different answer from "this
  cell is free". Use `TryGetBuilding`.
* **`global tile = island * 20 + local cell`**, and savegame `R` 0..3 indexes
  `NoRotate / RotateCW / Rotate180 / RotateCCW` in that same order.

## Still missing

**`place_blueprint`** is the primitive that would change the economics. The blueprint
to world mapping is already verified cell-for-cell (314/315), so a one-entry blueprint
is one building and a 1,567-entry blueprint is a whole MAM, through one code path. An
MCP server was agreed as a LATER thin wrapper over the same local JSON API, for
shipping to other players — explicitly not built into the mod.

## Rules of engagement (unchanged)

* **Sandbox only** (`d58e3f84-...`). **Never** the 72.8h save (`5589333c-...`) — read-only.
* **Never modify or delete an existing save.** Write a new one; undo is deleting a file.
* `CreateBuilding` sits under the interactive placement pipeline and does not appear to
  validate — our checks are the only thing between a generator bug and a corrupt map.
* **Re-parse your own output and run the size law before it goes near the save folder.**
  A round trip proves only that the writer agrees with the reader; both were wrong in
  the same place once and it crashed John's game.

# (superseded) PHASE 2 IS UNBLOCKED — BUILD THE BAND-MERGE

## The decision is made (John, 2026-09-04): **band-merge**.

The 4 per-lane stacker clusters are removed; the four lanes' band-P streams merge
per position, get painted once per position, and feed the ONE surviving cluster.

### Why this is right, in one line
**The 4 per-lane clusters are pure redundancy.** All five clusters already run at
the full unit output rate (they must, to feed the 5th at full rate). The 5th cluster
can assemble straight from the four band streams, so the other four are doing
throw-away partial-shape assembly. Paint is what made this worth fixing; the
redundancy was always there.

### Cost, from real building counts (recomputed 2026-09-04, includes `Paint 4 Filter`)
Cluster = 2x `Fancy A+B` (1,763) + 3x `Stacker` (1,361) = **7,609**.

| Per 1/4-belt unit, painted | Buildings | At full belt (x4) |
|---|---|---|
| keep current + 16 painters | 72,832 + 16x3,041 + 16x1,066 = **138,544** | **554,176** |
| **band-merge** + 4 painters | 42,396 + 4x3,041 + 4x1,066 = **58,824** | **235,296** |

Saving **~79.7k per unit / ~319k at full belt — 2.35x**.

---

# THE VISION (John, 2026-09-05): a closed build/measure/iterate loop, no human in it

> "I want a chat interface to have you build things in-game, from scratch, and work to
> optimize your own work by directly interfacing with the game, with as little of me as
> possible."

Recorded here so it survives session boundaries. **This is a direction, not the active
objective** — the active objective is still Phase 2a.

## Why this is more achievable than it sounds
The loop is design -> generate -> validate -> place -> simulate -> measure -> iterate.
Claude already does steps 1-2. `tools/spz2api` proved steps 3-6 are reachable: the
game's assemblies are readable, `BlueprintImporter.TryImport` is a one-call validator,
and `Game.Core.Map.Simulation` / `statistics.bin` are where measurement lives.

**The thing that makes it actually work is that this project has a fitness function.**
`tools/verify_mam.py` already decides mechanically whether a machine is correct, and a
MAM either hits its output rate or it does not. Autonomous iteration needs a
machine-checkable success criterion, and most creative work has none. This one does.

## The floor on "as little of me as possible"
Honest limits, so nobody plans around a fantasy:
* **The game must be running with a save loaded, on John's PC.** A mod lives inside the
  process; Claude cannot launch past the menus. The floor is "John starts it and leaves
  it running" — per *session*, not per experiment. That is the whole win.
* **Claude cannot see.** No rendering feedback, ever. Everything must arrive as
  structured state, so the mod's readout surface bounds what can be evaluated. This
  project happens to be about *structural* correctness, which is exactly the part that
  is machine-readable — a lucky fit, not a general one.
* **Simulation speed is iteration speed.** If evaluating one candidate costs 5 minutes
  of wall clock, a 100-candidate search costs 8 hours. Whether the sim can be ticked
  headlessly / fast-forwarded is the single biggest unknown, and it is worth answering
  EARLY because it decides whether stage 3 is worth building at all.
* **Never point this at the 72.8h save.** Autonomous place/delete belongs in a
  dedicated sandbox savegame.

## Staged path — each stage is useful on its own
| stage | what it is | risk | pays for itself? |
|---|---|---|---|
| **1. Read-only oracle** | mod watches a folder, answers "is this blueprint valid, and if not, which `BlueprintException`" + state queries. No writes to the world. | low | **yes, alone** — kills the round trips that cost us six on VN-13 |
| **2. Sandboxed writes** | placement + deletion in a dedicated sandbox save (`Game.Interaction.EntitiesPlacement`) | medium | Claude builds without John |
| **3. Closed loop** | sim control + metrics readout; propose, build, measure, iterate | high | the actual vision |

Stage 1 is worth doing even if 2 and 3 never happen. Start there.

## 2026-09-05 update: the console is the unlock, and the speed question is ANSWERED

**`IDebugConsole.ParseAndExecute(string command, Action<string> output)`** — arbitrary
console command in, text output back. And ShapezShifter exposes registration through
its *friendly* layer:

```csharp
// ShapezShifter.Flow.ModConsoleCommandsCreator
static ModConsoleRewirer AddModCommands(IMod mod);   // -> AddCommand / RegisterCommands
// IDebugConsole
void Register(String id, Action<CommandContext> handler, Boolean isCheat);   // + 2 overloads
List<String> GetAutoCompletions(String start);       // enumerate the REAL command list
```

So the stage-1 bridge is now small and well-defined: an `IMod` that calls
`AddModCommands(this)`, keeps the `IDebugConsole`, and watches a folder — each command
file goes to `ParseAndExecute`, its output comes back as a result file. That hands
Claude **every console command the game has**, plus a place to register custom ones.
`GetAutoCompletions("")` means the command surface can be discovered at runtime instead
of guessed.

### Speed: answered, and it changes the stage-3 economics
John found **`time.global-setspeed`, tested to 25x**. Also present:
`time.setspeed`, `debug.ultra-speed` / `fast-speed` / `normal-speed` / `slow-speed`, and
**`debug.step-speed`** — stepped advance, i.e. *deterministic* experiments rather than
wall-clock racing. A settle that takes 10 minutes becomes ~24 seconds at 25x.

The "is stage 3 worth building" unknown is resolved in favour of yes.

Other levers seen in the assemblies: `debug.statistics`, `debug.performance-chart`,
`debug.export-game-data`, `research.unlock-all` / `set-points` (sandbox setup).
Note the string scan mixes command ids with localization keys — trust
`GetAutoCompletions` over that list once the bridge exists.

### CORRECTION (same night): placement is NOT the hard part

The paragraph below was wrong and is kept only so the mistake is legible.
`BlueprintPlacer<,,,,,,,,,>` is the **HUD/interaction pipeline** — the thing that
follows your mouse and previews a stamp. Underneath it is a plain creation API:

```csharp
// Game.Core.Map.Model.IMapModel   (MapModel implements it)
BuildingModel CreateBuilding(IBuildingDefinition, ref GlobalTileTransform, IBuildingConfiguration);
IslandModel   CreateIsland  (IIslandDefinition,  GlobalChunkTransform,     IIslandConfiguration);
void DeleteBuilding(ref BuildingId);
void DeleteIsland(ref IslandId);
// : IBunchEditor  ->  FinishBunchEdit(BunchEditScope)   // batch 1,567 islands in one edit
// prop ISimulator Simulator
```

and the id -> definition step is one call each:

```csharp
// Game.Core.Logic.IBuildingResolver / IIslandResolver
//   (via Game.Core.Content.Buildings.IGameBuildingsRegistry / ...Islands.IGameIslandsRegistry)
bool TryGetDefinition(BuildingDefinitionId id, out IBuildingDefinition definition);
bool TryGetDefinition(IslandDefinitionId  id, out IIslandDefinition  definition);
```

**Our blueprint JSON maps onto those parameters one-for-one**: `T` -> DefinitionId ->
resolver -> definition; `X,Y,Z,R` -> transform; `C` -> configuration; `B.Entries` ->
nested `CreateBuilding` calls. That is exactly what a stamp does, minus the mouse.

### The entry point into a live session
`ShapezShifter.Kit.GameHelper.Core` -> `IGameSessionManagers`, which exposes
`Savegame`, **`SimulationSpeed` (`SimulationSpeedManager` — speed control from code, no
console needed)**, `ShapeRegistry`, `EntityPlacementRunner`, `Research`, `LocalPlayer`,
`Mode`, `Viewport`, `InteractionMode`, `DataSerializers`.

### What is still unknown (be honest about this)
* **How to reach `IMapModel` at runtime.** It is not on `Savegame` (metadata only) nor
  on `GameMode` (config only). One more hop, not yet found.
* Whether `CreateBuilding` skips affordability/placement validation. Probably — which
  suits us, but it means **our** validator is the only thing standing between a
  generator bug and a corrupted map.
* Main-thread / bunch-edit-scope constraints, and whether the simulator picks up new
  entities without an explicit notification.
* **None of this has been executed.** It is a read of the API surface. A signature
  existing is not the same as it working when called.

### Prior art: there is none
Searched the Workshop, mod.io and GitHub. Known Shapez 2 mods are content and QoL
(Blueprint Search, Time Control, Better Trash); nothing places entities
programmatically. So there is no worked example to copy — and no evidence it is
blocked either. We would be first.

### Old (WRONG) assessment, kept deliberately
### Placement is the hard part — the opposite of the naive guess
There is **no console command that places a blueprint**, and the code path is
`Game.Interaction.EntitiesPlacement.BlueprintPlacement.BlueprintPlacer<,,,,,,,,,>` — a
**ten**-type-parameter generic built out of `BuildInputModules` / `BuildProcessorModules`,
i.e. an interactive placement pipeline, not a `Place(blueprint, at)` function. Drivable
from a mod, probably; cheap, no.

**So the cost curve is inverted from the obvious assumption:** stage 1 (console bridge,
read-only + validation) is now *small*, and stage 2 (autonomous building) is the
expensive one. Plan accordingly — do stage 1, get the whole console, and only then
decide whether stage 2 is worth the placement work.

## The caution
This is plausibly a **bigger project than the remaining MAM work**. Stage 1 is clearly
worth it and is well-scoped. Stages 2-3 are a separate project that happens to serve
this one. Decide to start them deliberately — do not drift into them because stage 1
went well.

---

# PHASE 2 FRONT END IS BUILT AND VALIDATED — `For Claude Working MAM 1 layer no-color FSB`

**Closed out 2026-09-05.** John built the band-merge at full space belt, Claude
reviewed it, John fixed both findings, re-exported, and the re-export is **clean on
all twelve structural checks**. The blueprint is in `blueprints/reference/`.

**1,567 islands, 163,044 buildings = 40,761 per 1/4-belt unit** — better than the
42,396 the band-merge decision was costed at, because both redundant filter ranks
came out too.

| | Phase 1 per-lane | band-merge FSB |
|---|---|---|
| buildings / unit | 72,832 | **40,761** |
| stacker clusters / unit | 5 | **1** |
| painters / unit (Phase 2) | 16 | **4** |

### What was found and fixed
1. **`(-9,2,Z0)` was a `SpaceBelt_Forward` where it had to be a
   `SpaceBelt_LeftFwdSplitter R2`.** Band B had one trunk splitter where every other
   band has two; its inner distribution column was built, correctly wired all the way
   to clusters 3 and 4, and fed by nothing. Those two clusters never received band B.
2. **Both west ranks of Quaded Filters were redundant** (8 platforms at `x = -15` and
   `x = -16`). Stage 1 on the east already gates every quadrant against the goal and
   the merge cannot introduce material the goal did not ask for. John removed both;
   the band trunks now run from the merge straight into the stacker clusters.
   He also trimmed a stray rail spur (the 17th train station and its turn pair).

### The close-out evidence (re-export, 2026-09-05)
* all twelve `verify_mam.py` checks pass: 0 island overlaps, 0 belt dead ends,
  **0 orphan chains**, 0 blocked Z-change units, 16/16 filters identical on channel
  123, 8/8 Fancy A+B lane-fixed, 1 cluster per 4-lane unit = band-merge.
* **flow trace, the check that actually proves the rework:** all 16 cluster
  deliveries now carry **16 sources each**, each a single clean band offset, and the
  four offsets `-1/0/+1/+2` land in row order on every cluster. Band identity is
  preserved from the 16 east filters through the merge to all four stacker clusters.
* the distribution fan is regular on all four bands again: two adjacent
  `LeftFwdSplitter R2` per trunk plus one splitter down each inner column.
  (New origin; the fixed cell is `(-10,1)` in the re-export.)

**NEXT: Phase 2a — the `Paint 4 Filter` button swap.** Drive cells `(16,5)`, `(18,5)`,
`(20,5)`, `(22,5)` from `colour[band] == r/g/b/null`, then insert
`Paint 4 Filter` -> `Painter` on each of the four trunks' straight runs. The colour
brain is already validated in-game (VN-13). Open question still unanswered:
`Painter` (3,041 bldgs, 192 painters) vs `Painter Small` (812, 48) for a merged band.

---

## AUDIT: the review as filed (2026-09-05), kept for the reasoning

John built the band-merge for real, at full space belt, and asked for a review.
**1,568 islands, 171,700 buildings.** Everything structural passes except one belt.

### THE BUG: a splitter that got placed as a plain belt

**`(-9, 2, Z0)` is `SpaceBelt_Forward R2`. It must be `SpaceBelt_LeftFwdSplitter R2`.**

That is the whole fix — one belt, same rotation, same cell.

**What it costs today:** band B (trunk row 2) has only *one* trunk splitter where
every other band has two. Its inner distribution column (x = -9) is fully built and
correctly wired all the way down to cluster 3 at row 14 and on to cluster 4 at row
20 — and **nothing feeds it**. Clusters 3 and 4 never receive band B at all, so half
the machine can only ever emit shapes missing that quadrant. The three other bands
are perfect, which is why it does not look broken from the map.

The regular pattern, confirmed on bands A/C/D (see conventions.md "band-merge
distribution fan"): two `LeftFwdSplitter R2` on the trunk at `x = tx` and `x = tx+1`,
inner column first as you travel west, then one more splitter down the inner column.
Band B has `(-10,2)` and is missing `(-9,2)`.

### Everything else is clean
| check | result |
|---|---|
| island footprints overlap | **0** over 1,568 islands |
| space belts that dead-end | **0** over 1,293 belts |
| Z-change units with something above/below | **0** of 120 lifts |
| the 64 filter band outputs reach the right trunk | **yes** — each of the four trunks collects exactly its own 16 rows, band offsets `-1/0/+1/+2` preserved end to end |
| band -> west filter row identity | preserved: east offset `k` lands on west filter row `k`, so quadrant identity survives the merge |
| platform contents | 24/24 Quaded Filters identical, all channel 123; 8/8 Fancy A+B lane-fixed; every 2x2 / 2x4 / 1x1 module uniform |
| the four cluster cores | cell-for-cell identical across rows 2/8/14/20 |
| the four product columns | -29/-30/-31/-32, merged at -34, split at -35 into the four `Trash` read platforms (48 belt readers = the throughput rig) |

### Two observations, not bugs
* **The second rank of Quaded Filters at `x = -16` looks redundant.** Stage 1 (east,
  `x = 25`) already gates each lane's quadrant against the goal, and the band-merge
  cannot introduce material the goal did not ask for — so the `x = -16` rank should
  never reject anything. 8 platforms; harmless, but if it *is* load-bearing I have
  missed something and would like to know what.
* The 21 `LeftFwdMerger` / 21 `RightFwdMerger` with an unused side input are just
  belts with a spare port. Fine, and handy if paint later needs a tap-in point.

### Tooling: `tools/verify_mam.py` now catches this class of bug
* **lifts are modelled** — `Lift<n>Up/Down Forward/Left/Right` hand off at `Z±n` one
  cell ahead (or 90 degrees off). Without this the tool cried 120 phantom dead ends.
* **new check: orphan chains.** Every space belt must be fed by a belt or by the
  platform behind it. This is what isolates `(-9,2)` — it prints exactly one line.
* **new check: Z-change clearance** (nothing above or below a lift).
* `Layout_TrainUnloader_Shapes_Flipped` R1 footprint pinned to 2 tiles by elimination.
* the component-ratio check no longer assumes `filters == lanes` (the band-merge adds
  a second rank), and units are now counted from Quad Splitters.
* Both Phase 1 MAMs still pass all twelve checks — no regressions.

---

## AUDIT: `For Claude Working Full Belt Single Layer MAM no-paint` (2026-09-05)

John asked for a review of the working full-belt machine. **1,373 islands, 289,828
buildings. It is clean** — every structural check passes, including the two new ones
in `tools/verify_mam.py` (island-footprint overlaps, space-belt dead ends).

### What was checked, and what it proves
| check | result |
|---|---|
| island footprints overlap | **0** clashes over 1,373 islands |
| space belts that dead-end | **0** over 1,022 edges (the only 16 belts with no belt feeder are the ones fed by train unloaders) |
| the four units are copies | units B/C/D are **exact translations** of A, `+32` in Y, cell for cell |
| the four lanes are copies | identical except their feed/exit belt runs, which necessarily differ in length |
| filters | 16/16 identical to the goal-driven reference, all on channel 123, all with the same `null` compare constant |
| scaling | 289,828 = **4 x 72,332 + 500**. Exactly four copies of the validated unit, plus one shared trash block |

That last row is the important one: **a unit is a cell-for-cell copy of the validated
1/4-belt MAM.** It is not running faster; there are simply four of it. So nothing
inside a unit is carrying more throughput than what was already tested, and the whole
per-lane module chain (`Quad Splitter` -> `Demuxer` -> Overflow -> `Quaded Filter` ->
lane cluster) is unchanged and unstressed.

### Where the product goes: **into the trash, by design**
```
unit A --(-17,-56)--> southbound trunk --+                     units A+B = 1/2 belt
unit B --(-17,-24)--> ................. -+--> YMerger (-17,-10) --> W --> 4x Trash
unit D --(-17, 40)--> northbound trunk --+                     units C+D = 1/2 belt
unit C --(-17,  8)--> ..................-+
```
Each Trash platform carries **12 `BeltReader`s** — this west end is a throughput
meter, not an output. Two consequences:

1. **There is no product take-off.** Stamping this into the factory means replacing
   the whole `X = -23..-17` strip. That is the test rig, not the machine.
2. **The collector is exactly one space belt wide, with zero headroom.** 4 units x
   1/4 belt = 1 belt, and the meter reads a full belt — which is also a *good* test,
   because a dead unit would show up immediately as 3/4. But nothing can be added to
   the output rate without widening `X = -17`.

The trash block itself was **not** scaled (identical 500 buildings in both machines):
4 platforms x 12 lanes = 48 lanes of disposal behind a 12-lane belt. Harmless, but
it is 4x more platform than the meter needs.

### The one thing worth reconsidering: **16 train stations**
The 1/4-belt unit is fed by **one** station platform with **four unloaders stacked on
it** (Y `-2..1`, station at `2`) and a belt fan out to the four lanes. The full-belt
machine instead gives every lane **its own 5-tile platform** — 16 stations, 48
spacers, and one unloader each, placed at exactly the row its lane needs.

Since a unit is a cell-for-cell copy of the unit that one station demonstrably fed,
**4 stations (one per unit, four unloaders each) would deliver the same shapes at the
same rate** — 4 trains and 4 schedules instead of 16. The counter-argument is real
though: one dock serves one train at a time, so four stations means 4x the docking
frequency at each, and the dead time between trains is not free. **John's call** —
but if the 16 stations were for placement convenience rather than for docking
throughput, 12 of them are spare.

### Two things the blueprint does NOT carry (post-stamp checklist)
* **The goal.** 16 `ControlledSignalReceiver`s on channel **123**, and **zero
  transmitters** — the goal must be broadcast from outside the blueprint.
* **The train schedules.** Every unloader's shape filter is empty (`S` = four zero
  bytes). **Within each unit the four lanes must be fed four DISTINCT base shapes.**
  Two lanes on the same shape would both pass the same quadrant position, and the 5th
  cluster would get an overlap — a second layer — instead of a disjoint merge.

### Coordinate translation: small MAM -> full-belt machine
Every coordinate in the band-merge build sheet below is in
`For Claude Single layer MAM, no-paint`. To apply it to the full-belt machine, add:

| unit | lane rows (filter) | offset from the small MAM |
|---|---|---|
| A | -57, -51, -45, -39 | **(+5, -48)** |
| B | -25, -19, -13,  -7 | **(+5, -16)** |
| C |   7,  13,  19,  25 | **(+5, +16)** |
| D |  39,  45,  51,  57 | **(+5, +48)** |

Spot check: small `FILTER` at `X=10` -> `X=15`; small lane `r=-9` -> `-57` in unit A.
The X shift is `+5` for all four; only Y differs, `32` apart.

---

## JOHN'S JOB: the band-merge, step by step (2026-09-04)

All coordinates are **island/platform coordinates** in
`For Claude Single layer MAM, no-paint`, and all footprints below were derived from
each platform's own building coordinates, not from its foundation name.

### The shape of the machine
Four identical lane blocks at **r = -9, -3, 3, 9**, each **four platform rows tall**
(`r-1 .. r+2`), flowing **east -> west**:

```
   X:  15..14      13..12     11     10        9..8    7..6   5..3   1..0    -1
       QuadSplit   Demuxer    Ovf    FILTER    Fancy   Stkr   Fancy  Stkr    Ovf
       <--------------- keep ------------->    <----- the lane cluster ----->
```
The filter's west edge **abuts the Fancy at X=9 directly** — there is no belt between
them. Each lane cluster = 2 Fancy + 3 Stacker + 1 Overflow, occupying **X = -1..9**.

The **5th cluster is the same cluster, translated**: Fancy `(-8,-8)` and `(-13,-8)`,
Stackers `(-10,-9)` `(-10,-8)` `(-16,-8)`, Overflow `(-17,-8)`, occupying **X = -17..-7,
rows -10..-7**. **Its four inputs arrive on its EAST edge at X = -6, rows -10, -9, -8,
-7** (the belts at `(-6,-10)`, `(-6,-9)`, `(-6,-8)` R2, plus the turn at `(-6,-7)`).

Today the four lane clusters reach it on four northbound trunks in the corridor
X = -6..-3, and **they avoid crossing by column ordering** — the southernmost lane
gets the westmost trunk, so each lane's westward run stops short of the trunks
belonging to lanes further south. Remember this trick; it is why the current machine
has no belt crossings.

### STEP 1 — delete the four lane clusters
For each lane `r` in `-9, -3, 3, 9`:

| entry | occupies | what |
|---|---|---|
| `(8, r+1)` | X8-9, rows r-1..r+2 | Fancy A+B |
| `(3, r+1)` | X3-4, rows r-1..r+2 | Fancy A+B |
| `(6, r)`   | X6-7, rows r-1..r   | Stacker |
| `(6, r+1)` | X6-7, rows r+1..r+2 | Stacker (flipped) |
| `(0, r+1)` | X0-1, rows r..r+1   | Stacker |
| `(-1, r+1)`| X-1                 | Overflow |

...plus the space belts inside X0..5 of that block. **-30,436 buildings**, and it
frees the whole strip **X = -1..9** across all four lane blocks.

**Keep** everything at X=10 and east (filters, their four Overflows at X=11, demuxers,
splitters, rail), **and the whole 5th cluster**.

### STEP 2 — know where the sixteen band outputs are
Each `Quaded Filter` is a `Foundation_1x4` standing **north-south at X=10**, covering
rows `r-1 .. r+2`, **one band per row**, in your labelled north->south order. All
sixteen leave **westward at X=9**:

| band | leaves west at X=9, on rows |
|---|---|
| **NW** | `-10`, `-4`, `2`, `8` |
| **SW** | `-9`, `-3`, `3`, `9` |
| **SE** | `-8`, `-2`, `4`, `10` |
| **NE** | `-7`, `-1`, `5`, `11` |

Merge the four rows in each table row together. **No arbitration needed**: band P of
lane T only passes when `goal[P] == T`, so exactly one of the four is ever flowing and
the other three are hard-blocked. A plain merger is correct for every goal.

### STEP 3 — SOLVED BY JOHN: `For Claude Space Belt` (2026-09-04)
In `blueprints/reference/`. 1,526 space-belt islands, and it answers the crossing
problem: **each band hops over the trunks east of it at Z=1, then drops into its own
merger at Z=0.** 90 `Lift1UpForward` + 97 `Lift1DownForward` + 373 islands at Z=1.
**Multi-level space belts work** — that was the open question and it is now closed.

Verified against the machine:
- **64 inputs (east, X=16) and 64 outputs (west, X=-15)**, in **16 groups of 4
  consecutive rows** — exactly 16 filters x 4 bands. Groups sit **6 rows apart**
  within a block and there are **4 blocks**, matching the four lanes per unit and the
  four units. The row geometry is right.
- **Band -> trunk mapping is consistent across all 16 groups**: group-offset 0 (the
  northmost row of a filter, = NW) merges into the trunk at X=15, offset 1 (SW) into
  X=13, offset 2 (SE) into X=11, offset 3 (NE) into X=9. Trunk heads take the first
  group directly, so 15 merge points each (14 on the column plus one at the crossover
  at `(12,0)`, `(10,1)`, `(8,2)`). Symmetric splitters on the west.
- The south half mirrors the north half, so the trunk order reverses across the
  crossover rows -1..2 — expected, not a fault.

### !! STEP 3a — THE ONE PROBLEM: the trunks are a 4x throughput bottleneck
**Each trunk is a single space-belt column, but it aggregates all four UNITS.**

Within one unit, exactly one of four lanes is active on a given band, so that band is
**12 lanes = one space belt**. But the four units are independent parallel copies that
all run at once, so **four of the sixteen inputs on each trunk are active
simultaneously = 4 x 12 = 48 lanes** on a 12-lane belt. The full-belt machine would
back up and run at unit speed.

**Recommended fix: aggregate PER UNIT, not across units.** Four separate aggregators,
each **16 in -> 4 trunks -> 4 out**, feeding that unit's single surviving cluster.
No trunk ever carries more than the 12 lanes it already carries today.

That is also far cheaper. Splitting one shared trunk set back out to 16 destinations
means keeping **16 stacker clusters**; per-unit aggregation needs **4** (each unit's
existing 5th cluster, which already handles that unit's full 12-lane output today):

| | clusters | buildings |
|---|---|---|
| aggregate across units, re-split to 16 | 16 | 121,744 |
| **aggregate per unit** | **4** | **30,436** |

**~91,300 buildings saved**, plus a much shorter belt run — the per-unit aggregator is
16-in/4-out instead of 64-in/64-out, so roughly a quarter of the islands.

**Why the re-split exists at all:** merging across units combines streams that were
never in conflict, and then has to undo it. Merging within a unit is the part that
matters, because that is where "exactly one lane is active" holds.

### STEP 3b — `VN-14 band merge aggregator` (Claude, 2026-09-04) — the per-unit version
**198 islands** (174 at Z=0, 24 at Z=1) vs 1,526 for John's four-unit version. Every
piece is lifted from `For Claude Space Belt.spz2bp` with its exact rotation, and the
build asserts each one still exists there:

| role | piece |
|---|---|
| west-flowing belt / north trunk / south run | `SpaceBelt_Forward` R2 / R3 / R1 |
| merge an east input onto a north trunk | `SpaceBelt_LeftFwdMerger` R3 |
| hop up, across, down | `Lift1UpForward` R2 -> `Forward` R2 at **Z=1** -> `Lift1DownForward` R2 |
| W->N, N->W, W->S, S->W | `RightTurn` R2, `LeftTurn` R3, `LeftTurn` R2, `RightTurn` R1 |

**Interface** — inputs on the filters' west edge at **X=9**, outputs into the surviving
cluster's east edge at **X=-6**:

| band | trunk X | input rows | exits west along | delivery column | into cluster at |
|---|---|---|---|---|---|
| NW | 8 | -10, -4, 2, 8 | -14 | -5 | `(-6,-10)` |
| SW | 7 | -9, -3, 3, 9 | -13 | -4 | `(-6,-9)` |
| SE | 6 | -8, -2, 4, 10 | -12 | -3 | `(-6,-8)` |
| NE | 5 | -7, -1, 5, 11 | -11 | -2 | `(-6,-7)` |

**Only the 12 input hops ever change level.** Everything else is flat, because each
band's northernmost source is one row further south than the previous band's: trunk NW
leaves west along row -14, north of where SW/SE/NE even begin (-13/-12/-11); SW leaves
along -13, north of SE and NE; and the delivery columns nest the same way. Same
"outermost gets the longest run" trick John already uses to stop the four lane-cluster
outputs crossing — it just falls out in the other direction here.

**Paint goes on the four trunks**, anywhere along their straight runs. A trunk is
uniform in colour by construction — that is the entire point of merging by position.

**Not yet verified:** which cluster input row wants which quadrant. Because stacking is
rigid-body and the four streams are disjoint single quadrants, the order should not
matter — but confirm with Step 4's single-quadrant goals before trusting it.

### STEP 3c — TWO WORKING AGGREGATORS, one decision left (2026-09-04)
Both are in `blueprints/reference/`. Both merge by POSITION, so both give **4 painters
per unit** — the actual Phase 2 goal — and both obey the lift rules. They differ in
one thing: **how many stacker clusters survive.**

| | `VN-14` (= `For Claude Fixed Pipes`) | `For Claude Johns Version Pipes` |
|---|---|---|
| islands | **216** | 368 |
| topology | 16 in -> 4 trunks -> **4 out** | 16 in -> 4 trunks -> **16 out** (4 groups of 4) |
| clusters kept per unit | **1** (the 5th) | **4** (the lane clusters), 5th deleted |
| cluster buildings/unit | **7,609** | 30,436 |
| rework | filters and clusters both move | **nothing moves** — same 16 rows in, same 16 rows out |

**John's is the minimal-disturbance design and that is a real virtue.** The 16 filter
outputs and 16 cluster inputs stay exactly where they are; only the belts between them
change, and each of those rows now carries a per-POSITION stream instead of a
per-lane-band one. His southernmost block needs no lifts at all — each trunk simply
starts there, so those four inputs run west along their own row and turn north.

**The cost is three redundant clusters per unit.** A trunk carries one band = 12 lanes;
split four ways each cluster sees 3 lanes per input and emits 3 lanes, so four
clusters at quarter load do exactly what one at full load does. The surviving 5th
cluster already eats 4 x 12-lane inputs today, which is the proof one is enough.

**~22,800 buildings per unit, ~91,300 at full belt.** Same trade-off as the original
band-merge decision, one level down.

**JOHN'S CALL.** Cheap and slow to build vs lean and more rework. If the four lane
clusters stay, their outputs are complete shapes and merge on a plain belt into the
existing output path — no stacking needed, which removes most of the re-plumb.
Claude can generate either; `VN-14` currently generates the 4-out version and asserts
it cell-for-cell against John's fixed file.

### STEP 4 — validate ONE band before building four
Do **NE only**: merge rows `-7, -1, 5, 11` into a single stream and feed it into the
5th cluster's input at `(-6,-7)`. Leave the other three inputs unfed.

Set a goal whose **NE quadrant** is the only non-empty one — e.g. **`Cu------`** — and
confirm the machine still produces it. Then try `Ru------`, `Su------`, `Wu------` so
all four lanes take a turn on that one band. **If those four pass, the merge concept
is proven** and the other three bands are the same construction.

### STEP 5 — the other three bands, then re-test unpainted
Build SW, SE, NW the same way into `(-6,-8)`, `(-6,-9)`, `(-6,-10)`.

**Careful — confirm which input row is which band.** I know the four inputs are at
rows -10..-7 and that the cluster is a translated copy of a lane cluster, but I have
NOT verified which physical input corresponds to which quadrant position. Get this
wrong and the machine builds mirrored/rotated shapes that still look plausible. Feed
the single-quadrant goals from Step 4 one at a time and watch which input row carries
traffic.

Then re-run the **3 random single-layer goals** that validated Phase 1, plus a
goal-change to confirm it still self-flushes. At this point the unit should be
**~42,400 buildings** and behave exactly as before.

### STEP 6 — only then, paint
Per band: merged stream -> `Paint 4 Filter` -> `Painter` -> the 5th cluster input.
Do **not** start this until Step 5 passes. See "CLAUDE'S JOB" below for the button
swap that makes the paint filter goal-driven, and the open `Painter` vs
`Painter Small` question.

### Do NOT touch the full-belt machine
`For Claude Working Full Belt Single Layer MAM no-paint` stays as it is until one unit
is proven end to end. It is exactly 4x this unit, so the same procedure replicates.

## CLAUDE'S JOB: the colour brain — and it is smaller than PROGRESS assumed

### !! The analyzer fan does NOT need re-laying. That task is cancelled.
The colour signals are derived from the **goal**, not from the lane — so all four
lanes' `Quaded Filter`s (and all sixteen at full belt) compute the same thing. The
colour logic therefore does not belong in the filter at all. It goes **on the
`Paint 4 Filter` platform**, replacing its button bank:

```
ControlledSignalReceiver (channel 123)      <- the goal shape, same channel the filters use
  -> rotate so this band's quadrant lands NE  (NE: none / SE: 1x CCW / SW: 2x CW / NW: 1x CW)
  -> VirtualAnalyzer
  -> its LEFT output = colour[band]          (forward output is the uncoloured shape; ignore it)
  -> 4x LogicGateCompare against r / g / b / null
  -> the four booleans replace the four Buttons
```
No fan surgery, no new platform, **no new signal channels**, and the 16 validated
filters are untouched. Four blueprint variants, one per band.

### The interface to preserve on `Paint 4 Filter` (decoded 2026-09-04)
`Foundation_1x4` R2, spans X-35..32, Y2..17. The selector is a **priority bank**:
- constants `(15,4)`=`r`, `(17,4)`=`g`, `(19,4)`=`b`, `(21,4)`=**null** (`05`), all R1
- `LogicGateIf` at `(15,5)`, `(17,5)`, `(19,5)`, `(21,5)` R1 — value from behind
  (the constant), **condition from the LEFT side**, output forward (south)
- **`ButtonDefault` at `(16,5)`, `(18,5)`, `(20,5)`, `(22,5)` R2 — these are the
  four cells to replace.**
- `LogicGateIf`/`Not` at rows 6-8 and `IfMirrored` at `(21,10)`,`(22,11)`,`(23,12)`
  chain them first-wins; the winner leaves west along the row-16 wire bus to the
  48 `PipeGate`s. `Display2x2` at `(26,4)` shows the selected colour — a free probe.
- If **no** slot is enabled the bus carries nothing and the gates stay shut. That is
  exactly the wanted behaviour for a quadrant that needs no paint (the analyzer's
  colour output is **null** for an empty or pin quadrant), so it needs no special case.
- **Room to build in: L1 above the bank has 246 free cells** in X13-32/Y2-17
  (L2 has 247). Drop to L0 with `WireDefault1Up/2UpBackward`, as John already does
  at `(26,5)`/`(27,5)`.

### >>> THE COLOUR BRAIN IS DONE — VALIDATED IN-GAME (2026-09-04) <<<
John stamped `VN-13 NE/SE/SW/NW colour` and read them against live goals:

| goal | NE | SE | SW | NW |
|---|---|---|---|---|
| `CrCgCbCu` | **red** | **green** | **blue** | **uncoloured** |
| `Cr--CbCu` | red | **null** | blue | uncoloured |

Exactly as predicted, including the **null for an empty quadrant** — the no-paint
flag the whole of Phase 2 depends on. Settled and not to be revisited:
- **analyzer: forward = uncoloured shape, LEFT = colour** (John named the compass
  directions: "grey out its top (**West**)", "shape on the **North**"; west is the
  left side of an R3 analyzer);
- **rotation mapping: NE none / SE 1x CCW / SW 2x CW / NW 1x CW.**

Each platform is 6-8 buildings: `ConstantSignal`(123) `(7,10)` ->
`ControlledSignalReceiver` `(9,10)` -> wire `(9,8)` -> rotators -> `VirtualAnalyzer`,
west display = colour. **This is the block to copy for the paint filters.**

### A rule I invented that John's game disproved
The p6 post-mortem claimed a `Virtual*` may not sit on a `ControlledSignal*` port
cell, inferred from a census where 45/45 of John's port cells hold only
`Wire`/`Display`/`ConstantSignal`. **`VN-13q1` shows an analyzer directly on the
output port works fine.** The census described John's habits, not the game's rules.
Removed from `validate_layout()`. **Absence from John's library is not a game rule.**

### LABELS: SOLVED. Two rules, and they have two different symptoms
Settled by John's purpose-built `For Claude Labels.spz2bp` (now in
`blueprints/reference/`). Full write-up in `conventions.md`:

1. **A label body is 5 cells**, centred on its entry, along its facing axis
   (R0/R2 horizontal, R1/R3 vertical) — fixed size, independent of text length.
   Applying an N-cell model to all 3,100 labels in the library: **0 collisions at
   N=5, 2,569 at N=7.**
2. **A label needs one cell of margin** — its body must stay within **[3,16]** on a
   1x1, never the outer ring. John's reference demonstrates this on purpose: every
   label he named "Corner" / "North side" / "South side" sits exactly one cell in.
   The census agrees: label bodies use offsets [3..7, 12..16], **never 2 or 17**,
   while every other building type uses the full 2..17.

**Overlap → the whole FILE is discarded** (never appears in the folder: p6, v1, v2,
r1, s1, s2). **Margin violation alone → the file imports but FAILS TO STAMP** (t1).
That is why the symptom kept changing under us. `validate_layout()` now encodes both
rules and reproduces every observed outcome — including that `t1`'s `(5,7)` label was
innocent and only its `(4,14)` one (body X2-6) was at fault.

Labels are back on and correctly placed: `COLOUR ->` at `(5,y)` (body X3-7) and the
title at `(10,13)` (body X8-12). **The four validated `VN-13 * colour` blueprints are
untouched and asserted byte-identical to what John tested.**

### Multi-island: CONFIRMED WORKING — `VN-13 colour brain all` stamps
Four islands we authored ourselves, each with its own chain, labels included. So the
tooling is fully unblocked. `VN-13r2`'s earlier failure is unexplained but superseded
— same construction, more islands, works. Not worth chasing.

### VN-13 STATUS: COMPLETE
| blueprint | state |
|---|---|
| `VN-13 NE/SE/SW/NW colour` | validated in-game; byte-frozen |
| `VN-13 colour brain all` | validated in-game — all four quadrants, one stamp |
| `VN-13t2 one island labelled` | validated in-game |

**Phase 2's colour front end is done.** `VN-13 colour brain all` is the block to graft
onto the paint filters.

### !! Palette correction: it is 3 paints + off, not 4
Both `Paint 3 Filter` and `Paint 4 Filter` carry the **same** four constants —
`r`, `g`, `b`, and **null**. The "3"/"4" is not the palette size. So:
- **Phase 2a — r/g/b + none.** Complete and testable with `Paint 4 Filter`'s fluid
  side untouched. Do this first.
- **Phase 2b — the full 8.** Needs pre-mixed colours fed in (`Paint Mixer` exists in
  John's library) AND a wider selector + wider fluid routing. Deferred.

---

# Phase plan

**0 base supply → 1 single-layer shape → 2 single-layer paint → 3 multi-layer →
4 pins/supports → 5 scale 4x to full belt.**
Cross-cutting, not a phase: the **goal-change flush** (John reports the machine
already self-flushes — confirm it stays true as complexity grows).

| Phase | State |
|---|---|
| 0 base supply | **DONE for testing** — rail delivery, 4 `Layout_TrainUnloader_Shapes_Flipped` per unit. Map shape/fluid patch locations when it needs to be self-sustaining. |
| 1 single-layer shape | **DONE + VALIDATED IN-GAME** (below) |
| 2 paint | **UNBLOCKED — band-merge chosen 2026-09-04.** John: re-plumb. Claude: signal-driven `Paint 4 Filter`. Phase 2a = r/g/b+none. |
| 3 multi-layer | designed, not built — `VirtualUnstacker` is the layer-extract primitive |
| 4 pins | not started — `VirtualPinPusher` + `Pin Setter` exist |
| 5 scale 4x | **DONE for Phase 1** — John's full-belt build is exactly 4x the unit |

---

# PHASE 1: DONE AND VALIDATED (2026-09-04)

John hand-built the re-plumb and tested both machines against **3 random
single-layer goal signals — all passed, and the machine self-flushes on a goal
change**.

- **`For Claude Single layer MAM, no-paint`** — 334 islands, **72,832 buildings**,
  ~1/4 belt out. 4 lanes, each fed its own uniform uncoloured base shape by **rail**.
- **`For Claude Working Full Belt Single Layer MAM no-paint`** — 1,373 islands,
  **289,828 buildings**, saturates one full space belt. Exactly **4x** the unit
  (16 filters, 16 splitters, 40 Fancy A+B, 20 stacker clusters).

Both in `blueprints/reference/`.

### How it works
```
lane T: rail -> Quad Splitter -> Demuxer -> Quaded Filter -> its own stacker cluster
        -> a PARTIAL shape: type T in the positions the goal wants T, empty elsewhere
4 lanes -> 5th stacker cluster -> the four partials are DISJOINT, so rigid-body
        stacking merges them into ONE layer = the complete goal shape
```
**John's merge beat the one Claude proposed** — it reuses the same rigid-body rule
the whole design rests on, with no new belt geometry and only validated components.

### Why the filter needs no per-lane logic
With each lane fed a uniform uncoloured `TTTT`, band `P` of lane `T` carries exactly
`"T at position P"`. The fan drives that band with `Q_P` = the goal's quadrant at
`P`. The `BeltFilter` passes on equality, so
`band P of lane T passes  <=>  goal[P] == T` — the desired behaviour on all four
lanes, from **one unmodified filter design**.

### Verified by `tools/verify_mam.py`
Audits what fails **silently** in-game (a stamped machine looks fine and just makes
subtly wrong shapes): every `Fancy A+B` is the lane-FIXED version cell-for-cell, no
stale warning labels, every `Quaded Filter` identical to the goal-driven reference,
all Goal Receiver channels agree, component ratios consistent, no malformed configs.
**All three machines pass** (10 / 40 / 8 Fancy units, all fixed; all channels 123).
Re-run it on any new MAM variant:
```
python tools/verify_mam.py "blueprints/reference/<file>.spz2bp"
```

---

# PHASE 2 (paint): semantics settled — background

_The decision this section used to block on is made; see START HERE._

**John confirmed the Shape Analyzer contract:** it reads the **NE** part of the input
shape and emits the **uncoloured shape signal** on the top/forward output and that
part's **colour signal** on the side output. For a **Pin or empty** part the colour
output is **null**.

Consequences:
1. **The filter is ALREADY colour-blind.** The fan's band signals are analyzer
   forward outputs, so they carry no colour. **The Phase 1 machine already builds the
   correct shape for a coloured goal, today.** Phase 2 needs **no filter-logic
   change**. (Claude's paint-both-sides normaliser circuit is dropped — obsolete.)
2. **The colour signal is free** on the analyzer's side output, currently unused, and
   `null` for empty is a ready-made "this quadrant needs no paint" flag.

### The paint router already exists — `Paint 4 Filter`
`Painter` (3,041 buildings, 192 painters) has **no logic at all** — it paints with
whatever fluid arrives. So brain-driven colour is a **fluid routing** problem.

`Paint 4 Filter` is the router: `Foundation_1x4`, 1,066 buildings, 84 fluid ports,
**48 signal-driven `PipeGateDefaultInternalVariantMirrored`**, selected by a 4-way
`Button`/`ConstantSignal`/`LogicGateIf` bank — **the same 4-band shape as the
`Quaded Filter`**, so swap its button bank for the analyzer's colour signal exactly
as John did for the shape filter. (`Paint 3 Filter` is the 3-way version.)

**Caveat, corrected 2026-09-04: it selects among `r` / `g` / `b` / `null` — 3
paints plus off, not 4 paints.** `Paint 3 Filter` carries the identical constant
set, so the 3/4 in the names is not the palette size. Full colour needs pre-mixed
colours fed in plus a wider selector and wider fluid routing (Phase 2b).

---

# Remaining gaps after Phase 2

| # | Gap | Notes |
|---|-----|-------|
| 1 | **Multi-layer** | `VirtualUnstacker` (1x1, in behind, **two outputs: forward + left**) is the layer extract. Architecture: **N single-layer engines + a layer-stacking chain**. A layer join is a single `Foundation_2x2` stacker platform (**1,361 buildings**), *not* a whole cluster — so joining 4 layers is ~4,100. **Layer stacking is only safe when every upper-layer quadrant sits above an occupied lower-layer quadrant**, else it falls through and merges — matches the game's own support rule, but confirm with John. |
| 2 | **Base supply self-sufficiency** | Rail delivery works for testing. Shape/fluid patch locations in the working save still TBD. |
| 3 | **Quadrant waste** | Consumption ratio = **the number of distinct types in the target layer** (1:1 for `CuCuCuCu` up to 4:1 for `CuRuSuWu`). Inherent to decompose-then-select, not a defect. |
| 4 | **8-colour palette** | `Paint 4 Filter` selects **r/g/b + null**, i.e. 3 paints + off — *not* 4 paints (`Paint 3 Filter` has the identical constant set). Full 8 needs pre-mixed feeds (`Paint Mixer`) plus a wider selector AND wider fluid routing. Phase 2b. |
| 5 | **Pins / crystals** | Pins are Phase 4. **No crystals in the working save** — out of scope. |

---

# Environment & workflow (LOCAL Windows session — the normal case)

- Repo: this working directory. Game folder:
  `C:\Users\jdeli\AppData\LocalLow\tobspr Games\shapez 2`
  (`blueprints\2026\` = John's library, `blueprints\The Von Neumann Factory\` = ours,
  `savegames\`). Read/write directly; git is local — commit and push normally.
- Regenerate: `python tools\build_modules.py blueprints`, then copy the `.spz2bp`
  into the in-game folder and hash-compare. John forces an in-game blueprint-folder
  refresh to see new files.
- Commit trailer: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` plus
  `Claude-Session: <session url>`.
- **The Cowork/cloud access checklist (device_bash, `$HOME/mnt`, PAT-in-VM) is
  IRRELEVANT to a local session** — it was for cloud sessions only. If you are a
  cloud session, see git history for `docs/PROGRESS.md` before 2026-09-04.

## Working save & world
- **`savegames/5589333c-...`** ("Bullshitting") — fully unlocked (Level 107, ~44%
  research; **NO crystals**), cleared to ~28.5k structures. Blueprint cost = 0.
  `ResearchShapeCostMultiplier` = 60.

---

# Hard-won facts worth not relearning

### Three SILENT failure modes (full detail in conventions.md)
1. A building `C` **without `$type`** => the game discards the **whole file**; it
   never appears in the blueprint folder, which reads like a failed refresh.
   `check_configs()` guards this over every generated module.
2. **One invalid building** => the game places the foundation and discards **every
   building on that island**. A bare platform, no red X.
3. The **same** invalid building warns normally in a single-island blueprint but
   blanks the island in a multi-island assembly. **Isolate a suspect building on its
   own blueprint to get the real error message.**

### Method rules that were learned the hard way
- **Never infer a building's footprint from in-situ copies** — ask John for a minimal
  reference, ideally with the building outlined in belt **on the floor above**. That
  trick settled the 3x3 Goal Receiver in one read after two failed guesses.
- **Read the labels, don't guess.** `LabelDefaultInternalVariant` `C` =
  base64(2-byte LE length + UTF-8). John annotates everything.
- **Enumerate from the game, not from John's library**: all 98 `*InternalVariant`
  building ids are plain ASCII in
  `shapez 2_Data/resources.assets`. That is how `VirtualUnstacker` and
  `VirtualPainter` were found.

### Fancy A+B lane-swap bug — FIXED, VALIDATED, and now the baseline
Outer/inner lanes crossed over in the overflow tap. Root cause: outer rows tapped at
splitter column X=9/X=8, inner at X=7/X=6, and the downstream weave delivered them to
the opposite classes. Fixed by swapping those columns per band and shifting each
outer row's launcher hop one cell east. **Four bands, not two** — John caught that the
first pass only fixed the labelled north half. 168 retyped cells, no buildings added
or removed (bar 2 stale labels). The generated patch is asserted **cell-for-cell
identical to John's own hand-mirrored fix** at build time. **Build all further stacker
work on `load_fixed_stacker_islands()`, never the stock reference.**

### Key game facts (full detail in conventions.md)
- Blueprint = `SHAPEZ2-5-<base64(gzip(JSON))>[]_2$`.
- +X East / +Y South; R = 90 CW steps (R0 E, R1 S, R2 W, R3 N). 1x1 platform =
  20x20, buildable ~[2,17], floors L0-2. Bus = 4 cols x 3 floors = 12 lanes.
- **1 space belt = 12 lanes; "full belt" = 4 of them = 48 lanes.**
- **Stacking is rigid-body**: DISJOINT quadrants merge into one layer; any overlap
  puts the top shape on a NEW layer. Both halves of this rule are load-bearing —
  disjoint for the 5th-cluster merge, overlapping for multi-layer.
- **Multi-cell buildings record only their ORIGIN cell**; the other cells are absent
  from the entry list, so an "empty" neighbour may not be free.
- Edge ports only on the 4-lane band per edge (N/S at X8-11, E/W at Y8-11, per floor).
- Wire-layer port map (analyzer, painter, unstacker, gates): **conventions.md**.

---

# Module inventory (`blueprints/`, generated by `tools/build_modules.py`)

| Module | State |
|---|---|
| `VN-00 coord test` | VALIDATED — coordinate/rotation sanity check |
| `VN-01 quad isolator 1lane` | VALIDATED — HalfDestroy->Rot90CW->HalfDestroy |
| `VN-02 half-destroy 12lane` | VALIDATED — John's launcher-optimised redesign |
| `VN-03 rotate90CW 12lane` | launcher-optimised `Clockwise` (VN-02 layout, cut->rot) |
| `VN-04`, `VN-05` | **SUPERSEDED** hand-built mechanic proofs. Keep for reference; don't build on them |
| `VN-06 quad splitter test` | structural only, never in-game confirmed |
| `VN-07 reassembly test` | VALIDATED — Quad Splitter -> Demuxer -> lane-fixed Stacker |
| `VN-08 fancy A+B lane fixed` | VALIDATED — asserted identical to John's own fix |
| `VN-09 stacker empty quadrants fixed` | VALIDATED — drop-in replacement |
| `VN-10 any shape maker lane fixed` | VALIDATED — all 8 embedded Fancy units fixed |
| `VN-11 quaded filter goal driven` | VALIDATED — **John's own platform, used verbatim** |
| `VN-11a filter verbatim` | control: stock preset-driven filter, known-good baseline |
| `VN-12 MAM goal driven` | VALIDATED — superseded by John's Phase 1 build |
| `VN-12 MAM preset CuRuSuWu` | VALIDATED — preset-driven A/B |
| `VN-13 NE/SE/SW/NW colour` | VALIDATED — one goal quadrant colour each; byte-frozen |
| `VN-13 colour brain all` | VALIDATED — all four quadrant colours, four islands, one stamp |
| `VN-13t2 one island labelled` | VALIDATED — the label-placement control |

**Superseded by John's Phase 1 machines** (`blueprints/reference/For Claude Single
layer MAM, no-paint` and `... Working Full Belt ...`) — the VN-1x series is history
now, but keep it: it is what the verifier diffs against.

## Reference blueprints (`blueprints/reference/`)
John's, used verbatim as black boxes: `Quad Splitter`, `Demuxer`, `Stacker`,
`Stacker supporting empty quadrants`, `Fancy A+B Side Overflow` (+ pre-lane-fix),
`Filter`, `Quaded Filter`, `Quaded Color Filter`, `Smart Filter`, `Shape Filter`,
`Painter`, `Overflow`, `Trash`, `Full Belt Any Shape Maker`, and the four
purpose-built `For Claude *` references (`Signal Receiver`, `Filter with Signal`,
`Wiring Shapes`, and the two Phase 1 MAMs).

`For Claude Wiring Shapes` doubles as the **goal source for testing** — a
`ControlledSignalTransmitter` on **channel 123** sending a hand-set shape, which is
what the MAM's filters listen to.
