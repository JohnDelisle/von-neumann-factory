#!/usr/bin/env python3
"""
build_star_machine.py -- VN-16.  Channel 789: make `SuSuSuSu`.

    python tools/build_star_machine.py SRC.spz2 DST.spz2 [--assay]

## The shape algebra
This is the first goal that cannot be mined.  The nearest star-bearing patch is
`SuSuCu--` at island (17,-22) -- 40 tiles from the Vortex, NOT the 210 a first pass
suggested, because ranking sources by usable-quadrant-count before distance buries
the near ones.  A quadrant code reads NE SE SW NW, so:

    SuSuCu--                 NE=Su SE=Su SW=Cu NW=--
      cut, keep the east half     ->  SuSu----
      rotate that 180             ->  ----SuSu
      stack the two: DISJOINT     ->  SuSuSuSu

Rigid-body stacking merges disjoint pieces and layers overlapping ones, so the
disjointness is the whole trick -- it is why the 180 rotation is the right one and
a 90 would not do.

## Two passes, because one fact is not known yet
`CutterDefaultInternalVariant` has TWO belt outputs -- at its own tile and at the
tile behind it -- and the game's data does not say which carries the east half.
Rather than guess, `--assay` builds a machine that delivers ONE output and trashes
the other.  Whatever turns up in `research.json -> Shapes.StoredShapes` names it:
`SuSu----` means the delivered output is the east half, `----Cu--` means it is the
west half and the two should be swapped.  The Vortex is a shape assay instrument.

## Geometry, all declared by the game (`gamedata/.../buildings.json`)
    Extractor            1 tile,  out side 0
    Cutter               tiles (0,0,0) and (0,-1,0); in side 2; outs side 0 on BOTH
    RotatorHalf          1 tile,  in side 2, out side 0
    StackerStraight      tiles (0,0,0) and (0,0,+1) -- two FLOORS, one input each,
                         output on the lower one.  This is why John's notes say a
                         stacker's top feed needs a lift rather than a side belt.

Directions are 0=+X 1=+Y 2=-X 3=-Y, and a savegame `R` indexes that same order.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import save_world as sw
from build_circle_delivery import check_sizes

PATCH = (17, -22)            # nearest SuSuCu-- tile
HUB = (-1, 0)                # Vortex origin; occupies (-2..0, -1..1)
BAND = (8, 9, 10, 11)        # the 4-lane edge port band
FLOORS = (0, 1, 2)
LANE = 10                    # the single lane this machine uses
TRUNK_Y = -22


def b(T, X, Y, L=0, R=0, cfg=None):
    return dict(T=T, X=X, Y=Y, L=L, R=R, extra=0, cfg=cfg)


def machine_platform(assay):
    """STAGE A: a VERBATIM clone of John's validated miner, and nothing else.

    Two hand-authored miners produced nothing at all -- an extractor at local
    (16,10), then one at (8,5) copying his ore cells -- while every building read
    back from the live game at the right cell with the right rotation, and 40 tiles
    of trunk stayed empty.  Ruled out along the way: the tile does carry ore
    (GetResourceAt_GC returns a ShapeMapResourceSource for it), and simulation range
    is not the cause (VN-15 runs happily 30 islands from the camera).

    So rather than keep bisecting hypotheses about a layout, use the source that is
    already proven -- the same 160-building platform VN-15 mines circles with -- and
    let the result split the problem in one cycle: if `SuSuCu--` now reaches the
    Vortex, the fault was in my hand-authored platform; if it does not, the fault is
    in the new trunk or the Vortex's south face, and the miner was never the issue.

    That is PLAYBOOK's own rule, applied late: extract, don't invent."""
    from build_circle_delivery import miner_buildings
    return miner_buildings()


def cutter_platform():
    """WORKING (stage B): SuSuCu-- in, `--SuSu--` out and delivered to the Vortex.

    PORTS ARE 12-LANE GROUPS -- band cells 8..11 on each of floors 0,1,2, all twelve,
    or the port never connects.  Every one of the thousands of space-belt-fed
    platforms in John's 72.8h factory places all twelve; not one places a subset.
    With one or two receivers the feeding space belt just fills up (1524 bytes of
    cargo state against an empty 474) and the platform behind it stays empty.  That
    single rule was behind four failed attempts, including the "miner that produced
    nothing", which had a single sender and was almost certainly extracting fine.

    MEASURED: the cutter's delivered half is `--SuSu--`, not the `SuSu----` predicted
    from reading the quadrant code as NE-SE-SW-NW.  Good news either way, since the
    kept pair is still opposite-adjacent:

        --SuSu--   rotate 180  ->  Su----Su   (disjoint)   stack -> SuSuSuSu

    STAGE C IS BUILT BUT NOT WORKING and is therefore not enabled here.  Adding
    splitter -> turn -> RotatorHalf -> Lift1UpForward -> L1 -> two-floor stacker
    placed every building correctly (verified cell by cell in the live game, lift and
    stacker both spanning floors 0 and 1) and stopped all output: the stacker waits
    on a second input that never arrives, so nothing leaves the platform at all.
    The prime suspect is which side the splitter's second output actually emits
    on -- `Splitter1To2L` declares outputs on sides 0 and 3, and if side 3 resolves
    to -Y rather than the +Y assumed, branch B is being fed straight into the trash
    that catches the cutter's discarded half.  Testing that is one build cycle."""
    out = []
    for L in FLOORS:
        for y in BAND:
            out.append(b("BeltPortReceiverInternalVariant", 17, y, L, R=2))
            out.append(b("BeltPortSenderInternalVariant", 2, y, L, R=2))
    out.append(b("CutterDefaultInternalVariantMirrored", 16, LANE, R=2))
    out.append(b("TrashDefaultInternalVariant", 15, LANE - 1))
    for x in range(3, 16):
        out.append(b("BeltDefaultForwardInternalVariant", x, LANE, R=2))
    return out


def trunk():
    """Space belts from the machine's west edge to the Vortex's south face.

    West along y=-22 to x=-1, turn north, then up x=-1 to y=-2, which abuts the
    hub tile (-1,-1).  A LeftTurn's R is its INCOMING heading and it exits R-1, so
    a westbound R2 turn exits R1 = +Y."""
    isl = []
    for x in range(0, PATCH[0] - 3):                  # 0..13 heading west
        isl.append(dict(X=x, Y=TRUNK_Y, Z=0, layout="SpaceBelt_Forward", R=2,
                        icfg=None, buildings=[]))
    isl.append(dict(X=-1, Y=TRUNK_Y, Z=0, layout="SpaceBelt_LeftTurn", R=2,
                    icfg=None, buildings=[]))
    for y in range(TRUNK_Y + 1, -1):                  # -21..-2 heading +Y
        isl.append(dict(X=-1, Y=y, Z=0, layout="SpaceBelt_Forward", R=1,
                        icfg=None, buildings=[]))
    return isl


def hub_south_face():
    """The Vortex's south approach, mirroring the east one VN-15 already uses.

    Hub tile (-1,-1) is island-local X 0..19, Y -20..-1; its south edge port cell is
    Y=-18 and the band on a N/S edge runs X 8..11.  The centre tile (local 0..19) is
    the vortex mouth, so the senders sit on its own south edge at Y=0 pointing +Y --
    which is exactly what John's 72.8h factory does (senders at Y=0, R1)."""
    out = []
    for L in FLOORS:
        for x in BAND:
            out.append(b("BeltPortReceiverInternalVariant", x, -18, L, R=1))
            for y in range(-17, 0):
                out.append(b("BeltDefaultForwardInternalVariant", x, y, L, R=1))
            out.append(b("BeltPortSenderInternalVariant", x, 0, L, R=1))
    return out


def build(src, dst, assay=True):
    w = sw.read_world(src)
    islands = [i for ch in w["world"].values() for i in ch["islands"]]

    occ = {}
    for i in islands:
        cells = ([(i["X"] + dx, i["Y"] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
                 if i["layout"] == "Layout_HUB" else [(i["X"], i["Y"])])
        for c in cells:
            occ[c] = i["layout"]

    new = trunk()
    new.append(dict(X=PATCH[0], Y=PATCH[1], Z=0, layout="Layout_ShapeMiner", R=2,
                    icfg=None, buildings=machine_platform(assay)))
    # miner -> space belt -> processing platform -> space belt -> trunk: every hop is
    # a link that has actually been observed to carry shapes.
    new.append(dict(X=PATCH[0] - 1, Y=PATCH[1], Z=0, layout="SpaceBelt_Forward", R=2,
                    icfg=None, buildings=[]))
    new.append(dict(X=PATCH[0] - 2, Y=PATCH[1], Z=0, layout="Foundation_1x1", R=2,
                    icfg=None, buildings=cutter_platform()))
    new.append(dict(X=PATCH[0] - 3, Y=PATCH[1], Z=0, layout="SpaceBelt_Forward", R=2,
                    icfg=None, buildings=[]))
    for i in new:
        assert (i["X"], i["Y"]) not in occ, \
            "(%d,%d) is taken by %s" % (i["X"], i["Y"], occ[(i["X"], i["Y"])])

    hub = next(i for i in islands if i["layout"] == "Layout_HUB")
    have = {(x["X"], x["Y"], x["L"]) for x in hub["buildings"]}
    added = [x for x in hub_south_face() if (x["X"], x["Y"], x["L"]) not in have]
    clash = [x for x in hub_south_face() if (x["X"], x["Y"], x["L"]) in have]
    assert not clash, "south face would overwrite %d existing hub cells" % len(clash)
    hub["buildings"].extend(added)

    target = max(w["world"], key=lambda c: len(w["world"][c]["islands"]))
    for i in new:
        w["world"][target]["islands"].append(i)
        w["world"][target]["state"].append(dict(X=i["X"], Y=i["Y"], Z=i["Z"],
                                                layout=i["layout"], raw=None))

    n = sw.write_world(w, dst)
    bad = check_sizes(sw.read_world(dst))
    assert not bad, "size law violated: %s" % bad[:3]
    return n, len(new), len(added)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    n, ni, nh = build(src, dst, assay="--assay" in sys.argv)
    print("wrote %s" % dst)
    print("  +%d islands (trunk + machine), +%d buildings on the Vortex's south face"
          % (ni, nh))
    print("  %d islands total; every record obeys the size law" % n)
