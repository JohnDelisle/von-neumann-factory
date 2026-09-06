#!/usr/bin/env python3
"""
observe.py -- the read-back half of the build/run/observe loop.

    python tools/observe.py SAVE.spz2 [SHAPE ...]

Claude writes a world, John loads and runs it, and this reads the result out.  It
answers three questions and nothing else:

  1. WHAT WAS DELIVERED.  `research.json -> Shapes.StoredShapes` is a plain JSON
     dict of shape code -> count: the Vortex's own inventory of everything ever
     delivered.  No decoding needed at all -- it was hiding in the one file nobody
     had opened.  This is the project's fitness function: "deliver 1000 CuCuCuCu"
     is exactly StoredShapes["CuCuCuCu"] >= 1000.

  2. WHAT IS RUNNING.  `maps/main/buildings/<n>.bin` holds per-island runtime
     state.  An island with nothing in flight has a 30-byte record no matter how
     many buildings stand on it, so any island with a LONGER record has cargo
     moving on it.  That is a direct "is this machine alive" signal.

  3. WHAT THE GOALS ARE.  Every ConstantSignal carrying a shape, and every integer
     ConstantSignal (channel numbers), so the broadcast goals can be re-read after
     John changes them.
"""
import json, struct, sys, zipfile, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import save_world as sw
import say


def stored_shapes(w):
    return json.loads(w["entries"]["research.json"])["Shapes"]["StoredShapes"]


def broadcasts(w):
    """(channel constants, shape constants) seen anywhere in the world."""
    S = w["strings"]
    ints, shapes = [], []
    for ch in w["world"].values():
        for i in ch["islands"]:
            for b in i["buildings"]:
                c = b["cfg"]
                if c is None or not b["T"].startswith("ConstantSignal"):
                    continue
                if c[:1] == b"\x03":
                    ints.append((i["X"], i["Y"], struct.unpack_from("<i", c, 1)[0]))
                elif c[:1] == b"\x06":
                    shapes.append((i["X"], i["Y"], S[struct.unpack_from("<I", c, 3)[0]]))
    return ints, shapes


def live_islands(w):
    """Islands whose runtime-state record is bigger than the empty 30-byte form."""
    out = []
    for c, ch in sorted(w["world"].items()):
        for i, s in zip(ch["islands"], ch["state"]):
            if len(s["raw"]) != 30:
                out.append((i["X"], i["Y"], i["Z"], i["layout"], len(s["raw"])))
    return out


def main(path, wanted):
    w = sw.read_world(path)
    sg = json.loads(w["entries"]["savegame.json"])
    isl = [i for ch in w["world"].values() for i in ch["islands"]]
    print("%s" % os.path.basename(path))
    print("  saved %s   playtime %.0fs   %d islands, %d buildings"
          % (sg["LastSaved"][:19], sg["TotalPlaytime"], isl and len(isl),
             sum(len(i["buildings"]) for i in isl)))

    ss = stored_shapes(w)
    print("\n  DELIVERED TO THE VORTEX (research.json Shapes.StoredShapes)")
    if not ss:
        print("    nothing yet")
    rows = sorted(ss.items(), key=lambda kv: -kv[1])
    shown = rows if say.FULL else rows[:5]
    for k, v in shown:
        mark = "  <-- goal" if k in wanted else ""
        print("    %-30s %8d%s" % (k, v, mark))
    if len(rows) > len(shown):
        print("    (%d more shapes behind --full)" % (len(rows) - len(shown)))
    for k in wanted:
        if k not in ss:
            print("    %-30s %8d  <-- goal" % (k, 0))

    ints, shapes = broadcasts(w)
    say.detail("\n  BROADCAST GOALS")
    for (x, y, s) in shapes:
        chans = [c for (cx, cy, c) in ints if (cx, cy) == (x, y)]
        say.detail("    (%d,%d)  channel %-6s shape %s"
              % (x, y, chans[0] if chans else "?", s))

    live = live_islands(w)
    say.detail("\n  ISLANDS WITH CARGO IN FLIGHT  (%d)" % len(live))
    for x, y, z, t, n in live[:20]:
        say.detail("    (%d,%d,z%d) %-28s state %d bytes" % (x, y, z, t, n))
    if not live:
        say.detail("    none -- nothing was moving when this was saved")

    # The lists above are evidence; this is the answer. A state record bigger than
    # the empty form is NOT proof a machine runs (VN-15 read the empty form while
    # delivering 28,000 shapes) -- the rates in tools/brief.py are.
    print("  %d shape(s) delivered, %d broadcast goal(s), %d island(s) with a "
          "non-empty state record  (--full for the lists)"
          % (len(ss), len(shapes), len(live)))


if __name__ == "__main__":
    a = say.args()
    main(a[0], a[1:] or ["CuCuCuCu"])
