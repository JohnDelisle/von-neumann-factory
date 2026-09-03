# The Von Neumann Factory

A collaboration to build an elegant, symmetric **Make Anything Machine (MAM)** in
Shapez 2 — a factory that reads the shape currently requested by the HUB and
*constructs exactly that shape on demand*, at full space-belt throughput.

The name is the spirit of the thing: a machine that builds the machine. Not
literal self-replication — a general constructor whose parts are clean, reusable
blueprint modules.

## How this project works

- Claude authors Shapez 2 blueprints as `.spz2bp` files (generated from code in
  `tools/`), which John imports and tests in-game. Blueprints don't touch a live
  save, so they're safe to iterate on freely.
- The live game and the save file are edited by John; Claude reads the save to
  understand game state. We "take turns" on the save; blueprints are the shared
  design surface.
- Every module, tool, and note is versioned here.

## Layout

- `tools/` — blueprint/save codec and the module builder library.
- `docs/` — reverse-engineered file formats, in-game conventions, and the MAM
  architecture + design principles.
- `blueprints/` — the modules we build, mirrored into the in-game
  `blueprints/The Von Neumann Factory/` folder for testing.

## Status

Foundations complete: blueprint/save formats decoded, an encoder validated by
in-game round-trip, coordinate + rotation + bus conventions confirmed. Next:
building the constructive MAM pipeline stage by stage (see
`docs/architecture.md`).
