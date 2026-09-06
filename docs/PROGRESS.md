# Project status & session handoff

_Last updated: **2026-09-05** (evening). This file is the **current state only** —
everything superseded now lives in `docs/history/`. Read this, then `docs/PLAYBOOK.md`
(method, patterns, gotchas). `docs/architecture.md` and `docs/conventions.md` are
**references: grep them for the thing you need, do not read them front to back**._

## What this is
Co-building a **Make Anything Machine (MAM)** in Shapez 2 with John. John builds
physical layouts in-game; Claude decodes, verifies, designs logic and codifies (see
PLAYBOOK "Division of labour"). GitHub is the source of truth; every change is
committed + pushed.

## Resume in three commands

```
python tools/brief.py              # where everything stands, measured, in ~14 lines
python tools/game.py up            # stop game, start it, load the NAMED sandbox
python tools/bridge.py speed 25    # run the sim hot
```

`brief.py` reads the newest sandbox save plus the running game: delivered counts and
per-second rates out of `research.json`, goals out of the ConstantSignals actually on
the map, nothing remembered. It exists so a session does not spend its first 20k
tokens reading history. `game.py` knows the sandbox uid (`d58e3f84-...`) and waits on
the world NAME, because the main menu renders a live background world and will happily
hand you an `IMapModel` for the wrong map.

---

# >>> START HERE (2026-09-05, late): CHEAPER TOOLS FIRST, THEN THE THROUGHPUT QUESTION <<<

**You are a fresh session on purpose.** The previous one was ending near 200k context,
where every turn costs three to four times what the same turn cost at the start. The
handoff below is the whole state; you do not need that session's transcript, and you
should not go looking for it.

## Minute one

```
python tools/brief.py          # measured state in ~14 lines. Do not read history first.
```

Nothing in the game moved in the previous session — it was spent on session economics.
`docs/token-economics.md` has the measurements (2,732 model calls, 806M input tokens
re-read, 302k average context per call, ~a third of every session's input spend landing
in its last quarter of turns). New since you last looked: `tools/brief.py`,
`tools/token_report.py`, this file cut from 1,138 lines to ~220 with the remainder in
`docs/history/`, and a start-a-session procedure at the top of `CLAUDE.md`.

## Task 1 — DONE (2026-09-05, late)

Every read tool now obeys one rule, enforced by `tools/say.py`: **the default output
fits in ~15 lines and ends in a verdict; detail moves behind `--full`, and the tool
says how many rows it held back.** Measured: `verify_mam.py` 13 lines -> **1**
(`PASS ... -- 11/11 checks, 1567 islands, 163044 buildings [band-merge, 4 unit(s)]`),
`observe.py` ~40 -> **8**, `resources.py` ~270 -> **17**, `save_world.py` round trip
-> **1**. Nothing was deleted; `--full` still prints every line it used to.

`say.py` is the whole convention: `say.detail()`, `say.some(rows, cap=5)`,
`say.verdict(ok, msg)`, `say.args()` for argv minus the flags. New tools use it. See
PLAYBOOK "Tool output is a verdict, not a table".

**The rule survives the tools it was written for:** anything typed ad hoc obeys it too
— do not print a table and then read it; write the assertion and print PASS/FAIL plus
the two or three numbers that decide it. `python tools/token_report.py --top` is the
acceptance test: no single tool result much above 4k chars.

## Task 2 — ANSWERED (2026-09-05, late): we are supply-capped at ONE mining unit

**VN-18 delivers exactly one lane, not twelve.** Not the belt, not the hub — the mine.

### The experiment (one build variant, one load, one 200 s run)

`RuRuRuRu` had been measured at 4.00x the single unboosted `CuCuCuCu` miner in two
separate intervals (433.8/108.9 = 3.98, then 478.9/119.7 = 4.001). That is not "four
miner-equivalents, suspiciously close to 4" — under our own law (1 miner + 3 boosters
= 1 lane) it is **exactly one lane**, since an unboosted miner is a quarter lane.

So: cut collector B out of the save (one `SpaceBelt_Forward` island at (10,-13)),
load, run, and normalise against the Cu miner, which no variant touches.

| | Ru / Cu ratio | predicted if supply-capped |
|---|---|---|
| 12 lanes intact (v109) | **4.001** | — |
| collector B severed, 7 lanes (v111) | **3.934** | 2.33 |

**Removing five of the twelve lanes changed delivery by 1.7%.** And after 200 s of
running severed, collector B's nineteen `Forward` belts still read **474 B — the empty
form**. If the N-block miners were producing anything, those belts had nowhere to send
it and would have filled.

### What that means

The N block was contributing nothing before it was cut, and the whole 48-tile build
delivers 4 unboosted-miner-equivalents = one miner + three boosters = **one unit**.

**Best-supported reading: contiguous miner platforms merge into ONE mining unit.** The
48 islands form a solid rectangle; the game keeps them as `Layout_ShapeMiner` (the
rotations are right, so nothing was rewritten this time) but produces as though there
is a single miner with three effective boosters. This is the adjacency trap already in
these notes — "contiguous miners are silently rewritten to extensions" — one level up:
**even when the islands survive as miners, touching units share one production group.**

Not yet proven as a mechanism, and the honest alternative is that both collectors are
mis-wired AND collector A also passes only one lane. That needs two coincidences to
explain one exact 4.00x, so it is the weaker story — but it is testable.

### The next build, which settles it

Rebuild the patch as **12 SEPARATED units**: each a miner + its 3 boosters in a chain,
with at least one empty island tile between every unit and the next, each emitting into
the collector on its own port. If the merge story is right the rate goes to ~12 lanes
(~48 Cu-units); if it does not move, the cap is in the collector and the merge chain is
next. Either way the answer arrives in one build.

**Do not scale anything on the current numbers.** Every throughput figure in the Phase 2
cost model assumed 12 boosted miners = one saturated belt. What we have actually
demonstrated is one lane from 48 ore tiles.

### State left behind

* `backup-v112` = the intact VN-18 build with all progress kept (`RuRuRuRu` 2,658,480);
  the severed variant is `v110`/`v111`, kept for the record. Nothing was modified in
  place — every step wrote a new file.
* The game is loaded on v112 at speed 1.

## Task 3 — VN-16 stage C, batched

Still queued, still specified below under "Still queued: the VN-16 stage C test". Run it
as ONE build with both splitter variants side by side, each feeding its own stacker.
Four sequential single-hypothesis cycles is what burned an earlier budget.

## How to run this session

* **Batch.** One restart should discriminate between several hypotheses, never one.
* **Watch your own context.** Around 200k: commit, rewrite this banner for the next
  agent, and stop. A clean handoff costs a few thousand tokens; riding the session to
  500k costs a few hundred thousand.
* **Prefer local deterministic code** over a model call, and over a subagent (which
  starts cold and re-derives context we have already paid for).
* **Keep prose short.** Assistant prose is the single largest line item at 41%.
* The rules of engagement below have not moved: **sandbox `d58e3f84-…` only, never the
  72.8h save, never modify or delete an existing save, re-parse your own output before
  it goes near the save folder.**

---

# Background: the throughput law, and VN-18 (`RuRuRuRu`, built and running)

> **CORRECTED 2026-09-05 by the Task 2 experiment above: this build delivers ONE
> lane, not twelve. The "12 boosted miners = one saturated space belt" law is not
> wrong about the game, but our contiguous 48-tile rectangle is not 12 units — it
> behaves as one. Read the section below as the design intent, not as measured fact.**

## The law that VN-17 got wrong and VN-18 gets right
**A `Layout_ShapeMiner` is not a space belt.** John's rule, confirmed against his
72.8h factory (144 miners, 432 `Layout_ShapeMinerExtension` -- *exactly 3 each* --
feeding 144 hub lanes):

> **1 miner + 3 boosters = ONE lane. TWELVE boosted miners = 12 lanes = one
> saturated space belt.** A full belt therefore costs **48 ore tiles**.
> Boosters chain node-to-node, each pointing at the next node towards the miner;
> up to 3 per miner. The same holds for fluid miners.

Corollaries, both learned the hard way this session:
* Contiguous `Layout_ShapeMiner` islands written with the wrong rotation are
  **silently rewritten by the game into `Layout_ShapeMinerExtension`** on load. Our
  first four "miners" beside the Vortex became one 4-tile unit. Check the layout
  back out of the save after every load.
* The six free ore tiles beside the Vortex can never exceed ~1.5 lanes. Anything
  that wants throughput has to move to a patch.

## VN-18 -- `RuRuRuRu` at full space belt (built, loaded, running)
`tools/build_rect_full_belt.py`. 118 islands, **all 118 accepted by the game
unchanged**. 70 pure `RuRuRuRu` tiles at x 18..27, y -12..-3 (previously unbuilt)
carry 12 boosted miners = 48 ore tiles, plus 22 tiles of belt run:

| block | miners | boosters | collector |
|---|---|---|---|
| S | (22..26, -3) R1 | rows -4/-5/-6, R1 | A |
| N | (19..23, -12) R3 | rows -11/-10/-9, R3 | B |
| M | (20,-7) (21,-7) R1 | L-chains along row -8 | A, via belt columns x=20,21 |

* **Collector A** (7 lanes): `RightTurn R1` cap at (26,-2), `LeftFwdMerger R2` under
  each feeder, west along y=-2, down x=3, west along y=-1 -> hub tile (0,-1) **EAST**.
* **Collector B** (5 lanes): `LeftTurn R3` cap at (23,-13), `RightFwdMerger R2` over
  each miner, west along y=-13, down x=0 -> hub tile (0,-1) **NORTH**.

Two collectors because no single straight row on a ragged patch touches 12 miners;
7 + 5 lanes is the same 12 lanes of shapes, landing on two edges the hub already wires.

### Space belt port rules -- measured off John's factory, none guessed
    Forward R                     travels on heading R  (0=+X E, 1=+Y S, 2=-X W, 3=-Y N)
    RightTurn R / LeftTurn R      enters on heading R, leaves on R+1 / R-1
    LeftFwdMerger R               main flow R, SIDE INPUT from the neighbour at R+1
    RightFwdMerger R              main flow R, SIDE INPUT from the neighbour at R-1
    Layout_ShapeMiner R           the platform's 12 output lanes leave on edge R
    Layout_ShapeMinerExtension R  points at the next node in the chain to the miner

### The Vortex, and why VN-17 was still worth it
The 3x3 `Layout_HUB` has 12 outward tile edges x 12 lanes = **144 lanes**, but only
the CENTRE tile's own perimeter feeds the mouth (senders at local x or y in 4..15),
so the eight off-axis edges must jog inwards. Rather than author that, VN-17 copied
**John's 4,272-building, 144-lane hub feed verbatim** out of the 72.8h save. Every
edge is now live, so any future machine just has to reach an edge port.

### Measured (backup-v104 -> v105, 353 s of playtime at 25x)
| shape | delivered | rate |
|---|---|---|
| `RuRuRuRu` | 1,104 -> **185,664** | **433.8 / s** |
| `CuCuCuCu` (VN-15, one unboosted miner) | +38,448 | 108.9 / s |
| `--SuSu--` (VN-16) | +8,484 | 24.0 / s |

**Open question, not yet answered:** Ru is 3.98x the single unboosted Cu miner --
suspiciously *exactly* 4x. Whether 12 boosted miners genuinely saturate the belt, or
something downstream caps us at 4 miner-equivalents, is unproven. Next session:
compare a per-collector count (feed A and B to different edges of *different* hub
tiles and read the two edges separately), or read a collector belt's cargo state to
see whether it is backed up.

---

# Still queued: the VN-16 stage C test (channel 789)


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

---

# Standing rules — the expensive ones, kept out of the archive on purpose


**A platform edge port is a 12-LANE GROUP:** band cells 8, 9, 10, 11 on EACH of floors
0, 1 and 2 — all twelve, or the port never connects. Every space-belt-fed platform in
John's 72.8h factory places all twelve; not one places a subset. A partial group fails
SILENTLY: the feeding space belt fills up (1,524 bytes of cargo state against an empty
474) and the platform behind it stays empty, with no error anywhere.

**Diagnostic signal:** cargo state on the OUTGOING space belt is meaningful. A
platform's own runtime-state record is NOT — VN-15's miner reads 30 bytes (the empty
form) while delivering 28,000 shapes. I misread that for several cycles.

## Rules of engagement (unchanged)

* **Sandbox only** (`d58e3f84-...`). **Never** the 72.8h save (`5589333c-...`) — read-only.
* **Never modify or delete an existing save.** Write a new one; undo is deleting a file.
* `CreateBuilding` sits under the interactive placement pipeline and does not appear to
  validate — our checks are the only thing between a generator bug and a corrupt map.
* **Re-parse your own output and run the size law before it goes near the save folder.**
  A round trip proves only that the writer agrees with the reader; both were wrong in
  the same place once and it crashed John's game.

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

---

# History

Everything superseded is in `docs/history/`, verbatim and in original order:

* `2026-09-05-progress-archive.md` — the first 1,138-line PROGRESS.md, from the
  VN-16 handoff back through the vision, Phase 1/2 validation, the live-bridge
  notes and the module inventory.
