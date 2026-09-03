#!/usr/bin/env python3
"""
build_modules.py — generates our MAM blueprint modules as .spz2bp files.

Run:  python3 tools/build_modules.py [OUTDIR]
Writes each module to OUTDIR (default: blueprints/). The same files are mirrored
into the in-game blueprints/The Von Neumann Factory/ folder for testing.

Conventions (see docs/conventions.md):
  +X East, +Y South. R steps 90deg CW (R0 fwd=East, R1=South, R2=West, R3=North).
  1x1 platform = 20x20 grid, buildable ~[2,17], floors L0-2.
  Standard bus = 4 cols (X8-11) x 3 floors = 12 lanes, south-in(Y17)/north-out(Y2).
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from shapez_bp import encode_bp

SB = "Game.Core.Blueprint.Serialization."

def be(T, X=0, Y=0, L=0, R=0, C=None):
    return {"$type": SB + "SerializableBuildingEntry, Game.Core.Blueprint.Serialization",
            "X": X, "Y": Y, "L": L, "R": R, "T": T, "C": C}

def island(T, X=0, Y=0, Z=0, R=0, buildings=None, S=None, C=None):
    B = None
    if buildings is not None:
        B = {"$type": "Building",
             "Entries": {"$type": SB + "SerializableBuildingEntry[], Game.Core.Blueprint.Serialization",
                         "$values": buildings}}
    return {"$type": SB + "SerializableIslandEntry, Game.Core.Blueprint.Serialization",
            "X": X, "Y": Y, "Z": Z, "R": R, "T": T, "S": S, "C": C, "B": B}

def blueprint_islands(islands, V=1138):
    return {"$type": SB + "SerializableBlueprint, Game.Core.Blueprint.Serialization", "V": V,
            "BP": {"$type": "Island",
                   "Entries": {"$type": SB + "SerializableIslandEntry[], Game.Core.Blueprint.Serialization",
                               "$values": islands}}}

# ---------------------------------------------------------------- modules

def vn00_coord_test():
    """8 belts: East-flowing run turning South. Coordinate/rotation sanity check."""
    b = []
    for x in (5, 6, 7, 8):
        b.append(be("BeltDefaultForwardInternalVariant", X=x, Y=8, R=0))
    b.append(be("BeltDefaultLeftInternalVariantMirrored", X=9, Y=8, R=0))  # East->South
    for y in (9, 10, 11):
        b.append(be("BeltDefaultForwardInternalVariant", X=9, Y=y, R=1))
    return blueprint_islands([island("Foundation_1x1", buildings=b)])

def vn01_quad_isolator_1lane():
    """Stage 1 proof: isolate a single quadrant on ONE lane.

    Sequence (north-flowing, bus convention south-in Y17 / north-out Y2, all R3):
        HalfDestroy -> Rotate 90 CW -> HalfDestroy

    Shape math (Half Destroyer keeps the WORLD-EAST half; Rotate is 90 CW in
    world space; cut plane is always world-vertical regardless of building R):
        full {NE,SE,SW,NW}
          -HalfDestroy->  {NE,SE}          (keep east)
          -Rotate90CW->   {SE,SW}          (NE->SE, SE->SW)
          -HalfDestroy->  {SE}             (keep east) => one quadrant

    Feed any full single-layer shape; expect a single SE (bottom-right) quadrant
    out. Pre-rotating the input selects which original quadrant survives.
    All three transforms are single-cell inline buildings placed adjacently to
    also validate that they chain directly without intermediate belts.
    """
    X = 9  # a central bus column (bus cols are X8-11)
    b = []
    b.append(be("BeltPortReceiverInternalVariant", X=X, Y=17, R=3))   # input from south
    b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=16, R=3))
    b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=15, R=3))
    b.append(be("CutterHalfInternalVariant",         X=X, Y=14, R=3)) # keep east {NE,SE}
    b.append(be("RotatorOneQuadInternalVariant",     X=X, Y=13, R=3)) # 90 CW -> {SE,SW}
    b.append(be("CutterHalfInternalVariant",         X=X, Y=12, R=3)) # keep east {SE}
    for y in range(11, 2, -1):                                        # belts Y11..Y3
        b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=y, R=3))
    b.append(be("BeltPortSenderInternalVariant",     X=X, Y=2,  R=3)) # output north
    return blueprint_islands([island("Foundation_1x1", buildings=b)])


# --- VN-02: 12-lane half-destroy stage (with belt launchers) -----------------
# Base built by operator-substitution on John's proven `Clockwise` module: its
# split -> operator -> merge butterfly is operation-agnostic (each item passes
# exactly ONE operator cell), so swapping the 24 RotatorOneQuad cells for
# CutterHalf yields a 12-lane, full-throughput, pass-through Half Destroyer with
# identical proven routing. 2 cutters/lane; south-in Y17 / north-out Y2; island
# R=2 (matches Clockwise so it snaps into the same bus). Keeps world-EAST half.
#
# John then replaced the STRAIGHT belt runs with belt launcher->catcher hops to
# cut traversal time (same throughput). Launcher = BeltPortSenderInternalVariant,
# catcher = BeltPortReceiverInternalVariant placed mid-platform (no config; the
# game infers launcher/catcher from a non-edge port), R3, gap 1-4 tiles. Middle
# lanes X9/X10 use the full 4-tile hop (Y16->Y11); outer lanes X8/X11 hop Y16->Y14;
# input/output straights and the X7/X12 side runs are launched too. The butterfly
# (cutters, splitters, mergers, turns) is untouched, so logic is unchanged.
# VN02_CELLS below is the exact cell list extracted from John's saved blueprint.
VN02_CELLS = [
    (8,2,0,3,'BeltPortSenderInternalVariant'),
    (9,2,0,3,'BeltPortSenderInternalVariant'),
    (10,2,0,3,'BeltPortSenderInternalVariant'),
    (11,2,0,3,'BeltPortSenderInternalVariant'),
    (8,3,0,3,'BeltPortReceiverInternalVariant'),
    (9,3,0,3,'BeltPortReceiverInternalVariant'),
    (10,3,0,3,'BeltPortReceiverInternalVariant'),
    (11,3,0,3,'BeltPortReceiverInternalVariant'),
    (8,5,0,3,'BeltPortSenderInternalVariant'),
    (9,5,0,3,'BeltPortSenderInternalVariant'),
    (10,5,0,3,'BeltPortSenderInternalVariant'),
    (11,5,0,3,'BeltPortSenderInternalVariant'),
    (7,6,0,3,'BeltDefaultLeftInternalVariantMirrored'),
    (8,6,0,0,'BeltDefaultLeftInternalVariant'),
    (9,6,0,3,'BeltDefaultForwardInternalVariant'),
    (10,6,0,3,'BeltDefaultForwardInternalVariant'),
    (11,6,0,2,'BeltDefaultLeftInternalVariantMirrored'),
    (12,6,0,3,'BeltDefaultLeftInternalVariant'),
    (7,7,0,3,'BeltPortReceiverInternalVariant'),
    (8,7,0,3,'BeltDefaultLeftInternalVariantMirrored'),
    (9,7,0,0,'BeltDefaultLeftInternalVariant'),
    (10,7,0,2,'BeltDefaultLeftInternalVariantMirrored'),
    (11,7,0,3,'BeltDefaultLeftInternalVariant'),
    (12,7,0,3,'BeltPortReceiverInternalVariant'),
    (8,8,0,3,'Merger2To1LInternalVariantMirrored'),
    (9,8,0,3,'BeltDefaultLeftInternalVariant'),
    (10,8,0,3,'BeltDefaultLeftInternalVariantMirrored'),
    (11,8,0,3,'Merger2To1LInternalVariant'),
    (8,9,0,3,'CutterHalfInternalVariant'),
    (9,9,0,3,'CutterHalfInternalVariant'),
    (10,9,0,3,'CutterHalfInternalVariant'),
    (11,9,0,3,'CutterHalfInternalVariant'),
    (7,10,0,3,'BeltPortSenderInternalVariant'),
    (8,10,0,2,'BeltDefaultLeftInternalVariantMirrored'),
    (9,10,0,3,'Splitter1To2LInternalVariant'),
    (10,10,0,3,'Splitter1To2LInternalVariantMirrored'),
    (11,10,0,0,'BeltDefaultLeftInternalVariant'),
    (12,10,0,3,'BeltPortSenderInternalVariant'),
    (7,11,0,3,'Merger2To1LInternalVariantMirrored'),
    (8,11,0,3,'BeltDefaultLeftInternalVariant'),
    (9,11,0,3,'BeltPortReceiverInternalVariant'),
    (10,11,0,3,'BeltPortReceiverInternalVariant'),
    (11,11,0,3,'BeltDefaultLeftInternalVariantMirrored'),
    (12,11,0,3,'Merger2To1LInternalVariant'),
    (7,12,0,3,'CutterHalfInternalVariant'),
    (8,12,0,3,'CutterHalfInternalVariant'),
    (11,12,0,3,'CutterHalfInternalVariant'),
    (12,12,0,3,'CutterHalfInternalVariant'),
    (7,13,0,2,'BeltDefaultLeftInternalVariantMirrored'),
    (8,13,0,3,'Splitter1To2LInternalVariant'),
    (11,13,0,3,'Splitter1To2LInternalVariantMirrored'),
    (12,13,0,0,'BeltDefaultLeftInternalVariant'),
    (8,14,0,3,'BeltPortReceiverInternalVariant'),
    (11,14,0,3,'BeltPortReceiverInternalVariant'),
    (8,16,0,3,'BeltPortSenderInternalVariant'),
    (9,16,0,3,'BeltPortSenderInternalVariant'),
    (10,16,0,3,'BeltPortSenderInternalVariant'),
    (11,16,0,3,'BeltPortSenderInternalVariant'),
    (8,17,0,3,'BeltPortReceiverInternalVariant'),
    (9,17,0,3,'BeltPortReceiverInternalVariant'),
    (10,17,0,3,'BeltPortReceiverInternalVariant'),
    (11,17,0,3,'BeltPortReceiverInternalVariant'),
    (8,2,1,3,'BeltPortSenderInternalVariant'),
    (9,2,1,3,'BeltPortSenderInternalVariant'),
    (10,2,1,3,'BeltPortSenderInternalVariant'),
    (11,2,1,3,'BeltPortSenderInternalVariant'),
    (8,3,1,3,'BeltPortReceiverInternalVariant'),
    (9,3,1,3,'BeltPortReceiverInternalVariant'),
    (10,3,1,3,'BeltPortReceiverInternalVariant'),
    (11,3,1,3,'BeltPortReceiverInternalVariant'),
    (8,5,1,3,'BeltPortSenderInternalVariant'),
    (9,5,1,3,'BeltPortSenderInternalVariant'),
    (10,5,1,3,'BeltPortSenderInternalVariant'),
    (11,5,1,3,'BeltPortSenderInternalVariant'),
    (7,6,1,3,'BeltDefaultLeftInternalVariantMirrored'),
    (8,6,1,0,'BeltDefaultLeftInternalVariant'),
    (9,6,1,3,'BeltDefaultForwardInternalVariant'),
    (10,6,1,3,'BeltDefaultForwardInternalVariant'),
    (11,6,1,2,'BeltDefaultLeftInternalVariantMirrored'),
    (12,6,1,3,'BeltDefaultLeftInternalVariant'),
    (7,7,1,3,'BeltPortReceiverInternalVariant'),
    (8,7,1,3,'BeltDefaultLeftInternalVariantMirrored'),
    (9,7,1,0,'BeltDefaultLeftInternalVariant'),
    (10,7,1,2,'BeltDefaultLeftInternalVariantMirrored'),
    (11,7,1,3,'BeltDefaultLeftInternalVariant'),
    (12,7,1,3,'BeltPortReceiverInternalVariant'),
    (8,8,1,3,'Merger2To1LInternalVariantMirrored'),
    (9,8,1,3,'BeltDefaultLeftInternalVariant'),
    (10,8,1,3,'BeltDefaultLeftInternalVariantMirrored'),
    (11,8,1,3,'Merger2To1LInternalVariant'),
    (8,9,1,3,'CutterHalfInternalVariant'),
    (9,9,1,3,'CutterHalfInternalVariant'),
    (10,9,1,3,'CutterHalfInternalVariant'),
    (11,9,1,3,'CutterHalfInternalVariant'),
    (7,10,1,3,'BeltPortSenderInternalVariant'),
    (8,10,1,2,'BeltDefaultLeftInternalVariantMirrored'),
    (9,10,1,3,'Splitter1To2LInternalVariant'),
    (10,10,1,3,'Splitter1To2LInternalVariantMirrored'),
    (11,10,1,0,'BeltDefaultLeftInternalVariant'),
    (12,10,1,3,'BeltPortSenderInternalVariant'),
    (7,11,1,3,'Merger2To1LInternalVariantMirrored'),
    (8,11,1,3,'BeltDefaultLeftInternalVariant'),
    (9,11,1,3,'BeltPortReceiverInternalVariant'),
    (10,11,1,3,'BeltPortReceiverInternalVariant'),
    (11,11,1,3,'BeltDefaultLeftInternalVariantMirrored'),
    (12,11,1,3,'Merger2To1LInternalVariant'),
    (7,12,1,3,'CutterHalfInternalVariant'),
    (8,12,1,3,'CutterHalfInternalVariant'),
    (11,12,1,3,'CutterHalfInternalVariant'),
    (12,12,1,3,'CutterHalfInternalVariant'),
    (7,13,1,2,'BeltDefaultLeftInternalVariantMirrored'),
    (8,13,1,3,'Splitter1To2LInternalVariant'),
    (11,13,1,3,'Splitter1To2LInternalVariantMirrored'),
    (12,13,1,0,'BeltDefaultLeftInternalVariant'),
    (8,14,1,3,'BeltPortReceiverInternalVariant'),
    (11,14,1,3,'BeltPortReceiverInternalVariant'),
    (8,16,1,3,'BeltPortSenderInternalVariant'),
    (9,16,1,3,'BeltPortSenderInternalVariant'),
    (10,16,1,3,'BeltPortSenderInternalVariant'),
    (11,16,1,3,'BeltPortSenderInternalVariant'),
    (8,17,1,3,'BeltPortReceiverInternalVariant'),
    (9,17,1,3,'BeltPortReceiverInternalVariant'),
    (10,17,1,3,'BeltPortReceiverInternalVariant'),
    (11,17,1,3,'BeltPortReceiverInternalVariant'),
    (8,2,2,3,'BeltPortSenderInternalVariant'),
    (9,2,2,3,'BeltPortSenderInternalVariant'),
    (10,2,2,3,'BeltPortSenderInternalVariant'),
    (11,2,2,3,'BeltPortSenderInternalVariant'),
    (8,3,2,3,'BeltPortReceiverInternalVariant'),
    (9,3,2,3,'BeltPortReceiverInternalVariant'),
    (10,3,2,3,'BeltPortReceiverInternalVariant'),
    (11,3,2,3,'BeltPortReceiverInternalVariant'),
    (8,5,2,3,'BeltPortSenderInternalVariant'),
    (9,5,2,3,'BeltPortSenderInternalVariant'),
    (10,5,2,3,'BeltPortSenderInternalVariant'),
    (11,5,2,3,'BeltPortSenderInternalVariant'),
    (7,6,2,3,'BeltDefaultLeftInternalVariantMirrored'),
    (8,6,2,0,'BeltDefaultLeftInternalVariant'),
    (9,6,2,3,'BeltDefaultForwardInternalVariant'),
    (10,6,2,3,'BeltDefaultForwardInternalVariant'),
    (11,6,2,2,'BeltDefaultLeftInternalVariantMirrored'),
    (12,6,2,3,'BeltDefaultLeftInternalVariant'),
    (7,7,2,3,'BeltPortReceiverInternalVariant'),
    (8,7,2,3,'BeltDefaultLeftInternalVariantMirrored'),
    (9,7,2,0,'BeltDefaultLeftInternalVariant'),
    (10,7,2,2,'BeltDefaultLeftInternalVariantMirrored'),
    (11,7,2,3,'BeltDefaultLeftInternalVariant'),
    (12,7,2,3,'BeltPortReceiverInternalVariant'),
    (8,8,2,3,'Merger2To1LInternalVariantMirrored'),
    (9,8,2,3,'BeltDefaultLeftInternalVariant'),
    (10,8,2,3,'BeltDefaultLeftInternalVariantMirrored'),
    (11,8,2,3,'Merger2To1LInternalVariant'),
    (8,9,2,3,'CutterHalfInternalVariant'),
    (9,9,2,3,'CutterHalfInternalVariant'),
    (10,9,2,3,'CutterHalfInternalVariant'),
    (11,9,2,3,'CutterHalfInternalVariant'),
    (7,10,2,3,'BeltPortSenderInternalVariant'),
    (8,10,2,2,'BeltDefaultLeftInternalVariantMirrored'),
    (9,10,2,3,'Splitter1To2LInternalVariant'),
    (10,10,2,3,'Splitter1To2LInternalVariantMirrored'),
    (11,10,2,0,'BeltDefaultLeftInternalVariant'),
    (12,10,2,3,'BeltPortSenderInternalVariant'),
    (7,11,2,3,'Merger2To1LInternalVariantMirrored'),
    (8,11,2,3,'BeltDefaultLeftInternalVariant'),
    (9,11,2,3,'BeltPortReceiverInternalVariant'),
    (10,11,2,3,'BeltPortReceiverInternalVariant'),
    (11,11,2,3,'BeltDefaultLeftInternalVariantMirrored'),
    (12,11,2,3,'Merger2To1LInternalVariant'),
    (7,12,2,3,'CutterHalfInternalVariant'),
    (8,12,2,3,'CutterHalfInternalVariant'),
    (11,12,2,3,'CutterHalfInternalVariant'),
    (12,12,2,3,'CutterHalfInternalVariant'),
    (7,13,2,2,'BeltDefaultLeftInternalVariantMirrored'),
    (8,13,2,3,'Splitter1To2LInternalVariant'),
    (11,13,2,3,'Splitter1To2LInternalVariantMirrored'),
    (12,13,2,0,'BeltDefaultLeftInternalVariant'),
    (8,14,2,3,'BeltPortReceiverInternalVariant'),
    (11,14,2,3,'BeltPortReceiverInternalVariant'),
    (8,16,2,3,'BeltPortSenderInternalVariant'),
    (9,16,2,3,'BeltPortSenderInternalVariant'),
    (10,16,2,3,'BeltPortSenderInternalVariant'),
    (11,16,2,3,'BeltPortSenderInternalVariant'),
    (8,17,2,3,'BeltPortReceiverInternalVariant'),
    (9,17,2,3,'BeltPortReceiverInternalVariant'),
    (10,17,2,3,'BeltPortReceiverInternalVariant'),
    (11,17,2,3,'BeltPortReceiverInternalVariant'),
]

def vn02_halfdestroy_12lane():
    b = [be(T, X=X, Y=Y, L=L, R=R) for (X, Y, L, R, T) in VN02_CELLS]
    return blueprint_islands([island("Foundation_1x1", R=2, buildings=b)])


def vn03_rotate90cw_12lane():
    """Launcher-optimized 12-lane 90-CW rotate stage (= John's `Clockwise`, sped up).

    Derived from VN-02's VALIDATED launcher layout by swapping the operator cells
    CutterHalf -> RotatorOneQuad. Same proven butterfly + same launcher/catcher
    placement John hand-tuned on VN-02 (straight runs launched, 1-4 tile gaps,
    butterfly untouched). Function is identical to `Clockwise` (each item rotated
    90 CW exactly once); only traversal time improves. island R=2.
    """
    swap = {"CutterHalfInternalVariant": "RotatorOneQuadInternalVariant"}
    b = [be(swap.get(T, T), X=X, Y=Y, L=L, R=R) for (X, Y, L, R, T) in VN02_CELLS]
    return blueprint_islands([island("Foundation_1x1", R=2, buildings=b)])



def vn04_stacker_2in_1lane():
    """1-lane 2-input stacker primitive (validates StackerStraight ports).

    From John's StackerStraight ref: bottom (main) enters from behind (south, same
    floor); top (stack) enters from the cell directly ABOVE the stacker (L1);
    output exits forward (north), same floor. Here both inputs enter the south edge
    - bottom on L0, top on L1 - so the module snaps onto a 2-floor bus; output north
    on L0. Feed two DISJOINT single-quadrant pieces => one merged layer out.
    Column X9. Belts (no launchers) since runs are short - this is a port proof.
    """
    X=9; SY=9  # stacker row
    b=[]
    # L0 bottom path: south-edge receiver -> up -> stacker -> up -> north-edge sender
    b.append(be("BeltPortReceiverInternalVariant", X=X, Y=17, L=0, R=3))
    for y in range(16, SY, -1):                       # Y16..Y10 belts up
        b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=y, L=0, R=3))
    b.append(be("StackerStraightInternalVariant", X=X, Y=SY, L=0, R=3))
    for y in range(SY-1, 2, -1):                      # Y8..Y3 belts up
        b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=y, L=0, R=3))
    b.append(be("BeltPortSenderInternalVariant", X=X, Y=2, L=0, R=3))
    # L1 top path: south-edge receiver -> up -> into stacker top cell (X,SY,L1)
    b.append(be("BeltPortReceiverInternalVariant", X=X, Y=17, L=1, R=3))
    for y in range(16, SY, -1):                       # Y16..Y10 belts up; Y9(L1) left EMPTY = stacker top port
        b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=y, L=1, R=3))
    return blueprint_islands([island("Foundation_1x1", buildings=b)])



def vn05_assembler_1lane_4quad():
    """1-lane single-layer assembler: 4 separate quadrant inputs -> stacked layer.

    Chain of 3 StackerStraight on L0, column X9, flowing north. Each stacker takes
    its BOTTOM from behind (south, L0) and its TOP from the cell above it (L1).
    Four SEPARATE inputs (no shape-mixing on one belt):
      q1 (main)  : south edge, L0  (X9,Y17)
      q2,q3,q4   : east edge, L1, one per stacker row, run west into the top port
    Output: north edge, L0 (X9,Y2). Feed four DISJOINT single-quadrant pieces (one
    per position NE/SE/SW/NW) -> one merged 4-quadrant layer out.
    Chain: s1=q1+q2 -> p; s2=p+q3 -> p; s3=p+q4 -> layer.
    """
    X=9
    rows=[14,11,8]   # stacker Y rows (s1,s2,s3)
    b=[]
    # L0 main chain
    b.append(be("BeltPortReceiverInternalVariant", X=X, Y=17, L=0, R=3))
    b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=16, L=0, R=3))
    b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=15, L=0, R=3))
    b.append(be("StackerStraightInternalVariant", X=X, Y=14, L=0, R=3))  # s1
    b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=13, L=0, R=3))
    b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=12, L=0, R=3))
    b.append(be("StackerStraightInternalVariant", X=X, Y=11, L=0, R=3))  # s2
    b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=10, L=0, R=3))
    b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=9, L=0, R=3))
    b.append(be("StackerStraightInternalVariant", X=X, Y=8, L=0, R=3))   # s3
    for y in range(7, 2, -1):
        b.append(be("BeltDefaultForwardInternalVariant", X=X, Y=y, L=0, R=3))
    b.append(be("BeltPortSenderInternalVariant", X=X, Y=2, L=0, R=3))
    # L1 top feeds: east edge receiver -> west belts -> into (X9,row,L1) top port (left empty)
    for row in rows:
        b.append(be("BeltPortReceiverInternalVariant", X=17, Y=row, L=1, R=2))  # east edge, faces west
        for x in range(16, X, -1):   # X16..X10 belts west; X9 left empty = stacker top port
            b.append(be("BeltDefaultForwardInternalVariant", X=x, Y=row, L=1, R=2))
    return blueprint_islands([island("Foundation_1x1", buildings=b)])


MODULES = {
    "VN-00 coord test": vn00_coord_test,
    "VN-01 quad isolator 1lane": vn01_quad_isolator_1lane,
    "VN-02 half-destroy 12lane": vn02_halfdestroy_12lane,
    "VN-03 rotate90CW 12lane": vn03_rotate90cw_12lane,
    "VN-04 stacker 2in 1lane": vn04_stacker_2in_1lane,
    "VN-05 assembler 1lane 4quad": vn05_assembler_1lane_4quad,
}

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "blueprints"
    os.makedirs(outdir, exist_ok=True)
    for name, fn in MODULES.items():
        code = encode_bp(5, fn())
        with open(os.path.join(outdir, name + ".spz2bp"), "w") as f:
            f.write(code)
        print("wrote", name, f"({len(code)} bytes)")
