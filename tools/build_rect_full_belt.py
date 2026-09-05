#!/usr/bin/env python3
"""
build_rect_full_belt.py -- VN-18.  A FULL space belt of `RuRuRuRu` into the Vortex.

    python tools/build_rect_full_belt.py SRC.spz2 [DST.spz2]

## The throughput law VN-17 got wrong
A `Layout_ShapeMiner` is not a space belt.  John's rule, confirmed against his 72.8h
factory (144 miners, 432 extensions -- exactly 3 each, feeding 144 hub lanes):

    1 miner + 3 boosters (`Layout_ShapeMinerExtension`, chained node-to-node,
    each pointing at the next node towards the miner) = ONE lane.
    TWELVE such boosted miners = 12 lanes = ONE saturated space belt.

So a full belt costs **48 ore tiles**, not 4.  The four free ore tiles beside the
Vortex can never be more than a third of a lane; the build has to move to the patch.

## The patch
`tools/resources.py` finds 70 pure `RuRuRuRu` tiles at x 18..27, y -12..-3, and the
region is completely unbuilt.  70 tiles is 12 units (48) plus 22 for belt runs:

        x  1111111111222222222
           8901234567890123456
    y -13  <-------- collector B (west) ---------
      -12  . M M M M M . . . .        N block: 5 miners, boosters below
      -11  . x x x x x . . . .
      -10  . x x x x x . . . .
       -9  . x x x x x . . . .
       -8  b b b M b b b . . .        M block: 2 miners at y=-7, L-shaped chains
       -7  . . M M . . . . . .
       -6  . . | | x x x x x .        S block: 5 miners at y=-3, boosters above
       -5  . . | | x x x x x .
       -4  . . | | x x x x x .
       -3  . . | | M M M M M .
       -2  <-------- collector A (west) ---------

## Why two collectors
Every unit's miner must touch its collector, and the patch is a ragged parallelogram
-- no single straight row is adjacent to twelve miners.  Two collector rows of 7 and
5 lanes carry the same 12 lanes of shapes and land on two different Vortex edges,
both already wired by the 144-lane hub feed VN-17 installed:

    A (7 lanes)  y=-2 west, down x=3, west along y=-1  -> hub tile (0,-1) EAST edge
    B (5 lanes)  y=-13 west, down x=0                  -> hub tile (0,-1) NORTH edge

## Space belt port rules, all measured off John's factory, none guessed
    Forward R                    travels on heading R  (0=+X E, 1=+Y S, 2=-X W, 3=-Y N)
    RightTurn R / LeftTurn R     enters on heading R, leaves on R+1 / R-1
    LeftFwdMerger R              main flow R, SIDE INPUT from the neighbour at R+1
    RightFwdMerger R             main flow R, SIDE INPUT from the neighbour at R-1
    Layout_ShapeMiner R          the platform's 12 output lanes leave on edge R
    Layout_ShapeMinerExtension R points at the next node in the chain to the miner
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import save_world as sw
from build_circle_delivery import miner_buildings, check_sizes

HUB_XY = (-1, 0)
MINER = "Layout_ShapeMiner"
BOOST = "Layout_ShapeMinerExtension"
F, LT, RT = "SpaceBelt_Forward", "SpaceBelt_LeftTurn", "SpaceBelt_RightTurn"
LM, RM = "SpaceBelt_LeftFwdMerger", "SpaceBelt_RightFwdMerger"

# Hub edges this build lands on; both belong to hub tile (0,-1).
WANT_RECEIVERS = ([(37, y, 2) for y in (-12, -11, -10, -9)] +      # EAST  <- collector A
                  [(x, -18, 1) for x in (28, 29, 30, 31)])         # NORTH <- collector B


def units():
    """The twelve boosted miners: (tile, layout, R) for every platform."""
    out = []
    for x in range(22, 27):                      # S block: miners face south (R1)
        out.append((x, -3, MINER, 1))
        out += [(x, y, BOOST, 1) for y in (-4, -5, -6)]
    for x in range(19, 24):                      # N block: miners face north (R3)
        out.append((x, -12, MINER, 3))
        out += [(x, y, BOOST, 3) for y in (-11, -10, -9)]
    out += [(20, -7, MINER, 1), (21, -7, MINER, 1),
            (20, -8, BOOST, 1), (19, -8, BOOST, 0), (18, -8, BOOST, 0),
            (21, -8, BOOST, 1), (22, -8, BOOST, 2), (23, -8, BOOST, 2)]
    return out


def collector_a():
    """7 lanes: the S block's five miners plus the M block's two, into hub (0,-1) E."""
    out = [(26, -2, RT, 1)]                                  # east cap, from (26,-3)
    out += [(x, -2, LM, 2) for x in (25, 24, 23, 22, 21, 20)]  # side input from north
    out += [(x, -2, F, 2) for x in range(19, 3, -1)]         # run west, x 19..4
    out += [(3, -2, LT, 2), (3, -1, RT, 1), (2, -1, F, 2), (1, -1, F, 2)]
    for x in (20, 21):                                       # M block drops south
        out += [(x, y, F, 1) for y in (-6, -5, -4, -3)]
    return out


def collector_b():
    """5 lanes: the N block, west along y=-13 then south down x=0 into hub (0,-1) N."""
    out = [(23, -13, LT, 3)]                                 # east cap, from (23,-12)
    out += [(x, -13, RM, 2) for x in (22, 21, 20, 19)]       # side input from south
    out += [(x, -13, F, 2) for x in range(18, 0, -1)]        # run west, x 18..1
    out += [(0, -13, LT, 2)]
    out += [(0, y, F, 1) for y in range(-12, -1)]            # south, y -12..-2
    return out


def plan():
    p = units() + collector_a() + collector_b()
    seen = {}
    for x, y, lay, r in p:
        assert (x, y) not in seen, "tile (%d,%d) claimed twice" % (x, y)
        seen[(x, y)] = (lay, r)
    return p


def build(src, dst):
    w = sw.read_world(src)
    islands = [i for ch in w["world"].values() for i in ch["islands"]]

    occupied = set()
    for i in islands:
        span = 3 if i["layout"] == "Layout_HUB" else 1
        for dx in range(-(span // 2), span // 2 + 1):
            for dy in range(-(span // 2), span // 2 + 1):
                occupied.add((i["X"] + dx, i["Y"] + dy))
    p = plan()
    for x, y, lay, r in p:
        assert (x, y) not in occupied, "tile (%d,%d) is not free" % (x, y)

    hub = next(i for i in islands if i["layout"] == "Layout_HUB")
    assert (hub["X"], hub["Y"]) == HUB_XY, "hub moved"
    rec = {(b["X"], b["Y"], b["R"]) for b in hub["buildings"] if "Receiver" in b["T"]}
    missing = [r for r in WANT_RECEIVERS if r not in rec]
    assert not missing, "hub is not carrying the edges we land on: %s" % missing

    mb = miner_buildings()
    made = [dict(X=x, Y=y, Z=0, layout=lay, R=r, icfg=None,
                 buildings=[dict(b) for b in mb] if lay == MINER else [])
            for x, y, lay, r in p]

    target = next(c for c, ch in w["world"].items()
                  if any(i is hub for i in ch["islands"]))
    for isl in made:
        w["world"][target]["islands"].append(isl)
        w["world"][target]["state"].append(dict(X=isl["X"], Y=isl["Y"], Z=isl["Z"],
                                                layout=isl["layout"], raw=None))
    sw.write_world(w, dst)
    return made, target


def verify(dst, src, made):
    a = sw.read_world(src); b = sw.read_world(dst)
    for c in a["world"]:
        assert len(b["world"][c]["islands"]) == len(b["world"][c]["state"]), \
            "chunk %d: islands and state records disagree" % c
        for x, y in zip(a["world"][c]["islands"], b["world"][c]["islands"]):
            assert (x["X"], x["Y"], x["Z"], x["layout"]) == (y["X"], y["Y"], y["Z"], y["layout"]), \
                "an original island moved in chunk %d" % c
    bad = check_sizes(b)
    assert not bad, "island records violate the size law: %s" % bad[:5]
    g = {(i["X"], i["Y"]): (i["layout"], i["R"])
         for c in b["world"].values() for i in c["islands"]}
    for isl in made:
        assert g[(isl["X"], isl["Y"])] == (isl["layout"], isl["R"]), \
            "island (%d,%d) did not survive the write" % (isl["X"], isl["Y"])
    return (sum(len(c["islands"]) for c in a["world"].values()),
            sum(len(c["islands"]) for c in b["world"].values()))


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src.replace(".spz2", "-OUT.spz2")
    made, target = build(src, dst)
    na, nb = verify(dst, src, made)
    nm = sum(1 for i in made if i["layout"] == MINER)
    nx = sum(1 for i in made if i["layout"] == BOOST)
    print("wrote %s" % dst)
    print("  islands  %d -> %d  (+%d in chunk %d)" % (na, nb, len(made), target))
    print("  %d boosted miners (%d miners + %d boosters) = %d lanes = one full space belt"
          % (nm, nm, nx, nm))
    print("  collector A 7 lanes -> hub (0,-1) EAST ; collector B 5 lanes -> hub (0,-1) NORTH")
