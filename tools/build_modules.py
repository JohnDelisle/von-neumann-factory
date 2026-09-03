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


# --- VN-02: 12-lane half-destroy stage ---------------------------------------
# Built by operator-substitution on John's proven `Clockwise` module: its
# split -> operator -> merge butterfly is operation-agnostic (each item passes
# exactly ONE operator cell), so swapping the 24 RotatorOneQuad cells for
# CutterHalf yields a 12-lane, full-throughput, pass-through Half Destroyer with
# identical proven routing. 2 cutters/lane; south-in Y17 / north-out Y2; island
# R=2 (matches Clockwise so it snaps into the same bus). Keeps world-EAST half.
VN02_CELLS = [
    (8,2,0,3,'BeltPortSenderInternalVariant'),
    (9,2,0,3,'BeltPortSenderInternalVariant'),
    (10,2,0,3,'BeltPortSenderInternalVariant'),
    (11,2,0,3,'BeltPortSenderInternalVariant'),
    (8,3,0,3,'BeltDefaultForwardInternalVariant'),
    (9,3,0,3,'BeltDefaultForwardInternalVariant'),
    (10,3,0,3,'BeltDefaultForwardInternalVariant'),
    (11,3,0,3,'BeltDefaultForwardInternalVariant'),
    (8,4,0,3,'BeltDefaultForwardInternalVariant'),
    (9,4,0,3,'BeltDefaultForwardInternalVariant'),
    (10,4,0,3,'BeltDefaultForwardInternalVariant'),
    (11,4,0,3,'BeltDefaultForwardInternalVariant'),
    (8,5,0,3,'BeltDefaultForwardInternalVariant'),
    (9,5,0,3,'BeltDefaultForwardInternalVariant'),
    (10,5,0,3,'BeltDefaultForwardInternalVariant'),
    (11,5,0,3,'BeltDefaultForwardInternalVariant'),
    (7,6,0,3,'BeltDefaultLeftInternalVariantMirrored'),
    (8,6,0,0,'BeltDefaultLeftInternalVariant'),
    (9,6,0,3,'BeltDefaultForwardInternalVariant'),
    (10,6,0,3,'BeltDefaultForwardInternalVariant'),
    (11,6,0,2,'BeltDefaultLeftInternalVariantMirrored'),
    (12,6,0,3,'BeltDefaultLeftInternalVariant'),
    (7,7,0,3,'BeltDefaultForwardInternalVariant'),
    (8,7,0,3,'BeltDefaultLeftInternalVariantMirrored'),
    (9,7,0,0,'BeltDefaultLeftInternalVariant'),
    (10,7,0,2,'BeltDefaultLeftInternalVariantMirrored'),
    (11,7,0,3,'BeltDefaultLeftInternalVariant'),
    (12,7,0,3,'BeltDefaultForwardInternalVariant'),
    (7,8,0,3,'BeltDefaultForwardInternalVariant'),
    (8,8,0,3,'Merger2To1LInternalVariantMirrored'),
    (9,8,0,3,'BeltDefaultLeftInternalVariant'),
    (10,8,0,3,'BeltDefaultLeftInternalVariantMirrored'),
    (11,8,0,3,'Merger2To1LInternalVariant'),
    (12,8,0,3,'BeltDefaultForwardInternalVariant'),
    (7,9,0,3,'BeltDefaultForwardInternalVariant'),
    (8,9,0,3,'CutterHalfInternalVariant'),
    (9,9,0,3,'CutterHalfInternalVariant'),
    (10,9,0,3,'CutterHalfInternalVariant'),
    (11,9,0,3,'CutterHalfInternalVariant'),
    (12,9,0,3,'BeltDefaultForwardInternalVariant'),
    (7,10,0,3,'BeltDefaultForwardInternalVariant'),
    (8,10,0,2,'BeltDefaultLeftInternalVariantMirrored'),
    (9,10,0,3,'Splitter1To2LInternalVariant'),
    (10,10,0,3,'Splitter1To2LInternalVariantMirrored'),
    (11,10,0,0,'BeltDefaultLeftInternalVariant'),
    (12,10,0,3,'BeltDefaultForwardInternalVariant'),
    (7,11,0,3,'Merger2To1LInternalVariantMirrored'),
    (8,11,0,3,'BeltDefaultLeftInternalVariant'),
    (9,11,0,3,'BeltDefaultForwardInternalVariant'),
    (10,11,0,3,'BeltDefaultForwardInternalVariant'),
    (11,11,0,3,'BeltDefaultLeftInternalVariantMirrored'),
    (12,11,0,3,'Merger2To1LInternalVariant'),
    (7,12,0,3,'CutterHalfInternalVariant'),
    (8,12,0,3,'CutterHalfInternalVariant'),
    (9,12,0,3,'BeltDefaultForwardInternalVariant'),
    (10,12,0,3,'BeltDefaultForwardInternalVariant'),
    (11,12,0,3,'CutterHalfInternalVariant'),
    (12,12,0,3,'CutterHalfInternalVariant'),
    (7,13,0,2,'BeltDefaultLeftInternalVariantMirrored'),
    (8,13,0,3,'Splitter1To2LInternalVariant'),
    (9,13,0,3,'BeltDefaultForwardInternalVariant'),
    (10,13,0,3,'BeltDefaultForwardInternalVariant'),
    (11,13,0,3,'Splitter1To2LInternalVariantMirrored'),
    (12,13,0,0,'BeltDefaultLeftInternalVariant'),
    (8,14,0,3,'BeltDefaultForwardInternalVariant'),
    (9,14,0,3,'BeltDefaultForwardInternalVariant'),
    (10,14,0,3,'BeltDefaultForwardInternalVariant'),
    (11,14,0,3,'BeltDefaultForwardInternalVariant'),
    (8,15,0,3,'BeltDefaultForwardInternalVariant'),
    (9,15,0,3,'BeltDefaultForwardInternalVariant'),
    (10,15,0,3,'BeltDefaultForwardInternalVariant'),
    (11,15,0,3,'BeltDefaultForwardInternalVariant'),
    (8,16,0,3,'BeltDefaultForwardInternalVariant'),
    (9,16,0,3,'BeltDefaultForwardInternalVariant'),
    (10,16,0,3,'BeltDefaultForwardInternalVariant'),
    (11,16,0,3,'BeltDefaultForwardInternalVariant'),
    (8,17,0,3,'BeltPortReceiverInternalVariant'),
    (9,17,0,3,'BeltPortReceiverInternalVariant'),
    (10,17,0,3,'BeltPortReceiverInternalVariant'),
    (11,17,0,3,'BeltPortReceiverInternalVariant'),
    (8,2,1,3,'BeltPortSenderInternalVariant'),
    (9,2,1,3,'BeltPortSenderInternalVariant'),
    (10,2,1,3,'BeltPortSenderInternalVariant'),
    (11,2,1,3,'BeltPortSenderInternalVariant'),
    (8,3,1,3,'BeltDefaultForwardInternalVariant'),
    (9,3,1,3,'BeltDefaultForwardInternalVariant'),
    (10,3,1,3,'BeltDefaultForwardInternalVariant'),
    (11,3,1,3,'BeltDefaultForwardInternalVariant'),
    (8,4,1,3,'BeltDefaultForwardInternalVariant'),
    (9,4,1,3,'BeltDefaultForwardInternalVariant'),
    (10,4,1,3,'BeltDefaultForwardInternalVariant'),
    (11,4,1,3,'BeltDefaultForwardInternalVariant'),
    (8,5,1,3,'BeltDefaultForwardInternalVariant'),
    (9,5,1,3,'BeltDefaultForwardInternalVariant'),
    (10,5,1,3,'BeltDefaultForwardInternalVariant'),
    (11,5,1,3,'BeltDefaultForwardInternalVariant'),
    (7,6,1,3,'BeltDefaultLeftInternalVariantMirrored'),
    (8,6,1,0,'BeltDefaultLeftInternalVariant'),
    (9,6,1,3,'BeltDefaultForwardInternalVariant'),
    (10,6,1,3,'BeltDefaultForwardInternalVariant'),
    (11,6,1,2,'BeltDefaultLeftInternalVariantMirrored'),
    (12,6,1,3,'BeltDefaultLeftInternalVariant'),
    (7,7,1,3,'BeltDefaultForwardInternalVariant'),
    (8,7,1,3,'BeltDefaultLeftInternalVariantMirrored'),
    (9,7,1,0,'BeltDefaultLeftInternalVariant'),
    (10,7,1,2,'BeltDefaultLeftInternalVariantMirrored'),
    (11,7,1,3,'BeltDefaultLeftInternalVariant'),
    (12,7,1,3,'BeltDefaultForwardInternalVariant'),
    (7,8,1,3,'BeltDefaultForwardInternalVariant'),
    (8,8,1,3,'Merger2To1LInternalVariantMirrored'),
    (9,8,1,3,'BeltDefaultLeftInternalVariant'),
    (10,8,1,3,'BeltDefaultLeftInternalVariantMirrored'),
    (11,8,1,3,'Merger2To1LInternalVariant'),
    (12,8,1,3,'BeltDefaultForwardInternalVariant'),
    (7,9,1,3,'BeltDefaultForwardInternalVariant'),
    (8,9,1,3,'CutterHalfInternalVariant'),
    (9,9,1,3,'CutterHalfInternalVariant'),
    (10,9,1,3,'CutterHalfInternalVariant'),
    (11,9,1,3,'CutterHalfInternalVariant'),
    (12,9,1,3,'BeltDefaultForwardInternalVariant'),
    (7,10,1,3,'BeltDefaultForwardInternalVariant'),
    (8,10,1,2,'BeltDefaultLeftInternalVariantMirrored'),
    (9,10,1,3,'Splitter1To2LInternalVariant'),
    (10,10,1,3,'Splitter1To2LInternalVariantMirrored'),
    (11,10,1,0,'BeltDefaultLeftInternalVariant'),
    (12,10,1,3,'BeltDefaultForwardInternalVariant'),
    (7,11,1,3,'Merger2To1LInternalVariantMirrored'),
    (8,11,1,3,'BeltDefaultLeftInternalVariant'),
    (9,11,1,3,'BeltDefaultForwardInternalVariant'),
    (10,11,1,3,'BeltDefaultForwardInternalVariant'),
    (11,11,1,3,'BeltDefaultLeftInternalVariantMirrored'),
    (12,11,1,3,'Merger2To1LInternalVariant'),
    (7,12,1,3,'CutterHalfInternalVariant'),
    (8,12,1,3,'CutterHalfInternalVariant'),
    (9,12,1,3,'BeltDefaultForwardInternalVariant'),
    (10,12,1,3,'BeltDefaultForwardInternalVariant'),
    (11,12,1,3,'CutterHalfInternalVariant'),
    (12,12,1,3,'CutterHalfInternalVariant'),
    (7,13,1,2,'BeltDefaultLeftInternalVariantMirrored'),
    (8,13,1,3,'Splitter1To2LInternalVariant'),
    (9,13,1,3,'BeltDefaultForwardInternalVariant'),
    (10,13,1,3,'BeltDefaultForwardInternalVariant'),
    (11,13,1,3,'Splitter1To2LInternalVariantMirrored'),
    (12,13,1,0,'BeltDefaultLeftInternalVariant'),
    (8,14,1,3,'BeltDefaultForwardInternalVariant'),
    (9,14,1,3,'BeltDefaultForwardInternalVariant'),
    (10,14,1,3,'BeltDefaultForwardInternalVariant'),
    (11,14,1,3,'BeltDefaultForwardInternalVariant'),
    (8,15,1,3,'BeltDefaultForwardInternalVariant'),
    (9,15,1,3,'BeltDefaultForwardInternalVariant'),
    (10,15,1,3,'BeltDefaultForwardInternalVariant'),
    (11,15,1,3,'BeltDefaultForwardInternalVariant'),
    (8,16,1,3,'BeltDefaultForwardInternalVariant'),
    (9,16,1,3,'BeltDefaultForwardInternalVariant'),
    (10,16,1,3,'BeltDefaultForwardInternalVariant'),
    (11,16,1,3,'BeltDefaultForwardInternalVariant'),
    (8,17,1,3,'BeltPortReceiverInternalVariant'),
    (9,17,1,3,'BeltPortReceiverInternalVariant'),
    (10,17,1,3,'BeltPortReceiverInternalVariant'),
    (11,17,1,3,'BeltPortReceiverInternalVariant'),
    (8,2,2,3,'BeltPortSenderInternalVariant'),
    (9,2,2,3,'BeltPortSenderInternalVariant'),
    (10,2,2,3,'BeltPortSenderInternalVariant'),
    (11,2,2,3,'BeltPortSenderInternalVariant'),
    (8,3,2,3,'BeltDefaultForwardInternalVariant'),
    (9,3,2,3,'BeltDefaultForwardInternalVariant'),
    (10,3,2,3,'BeltDefaultForwardInternalVariant'),
    (11,3,2,3,'BeltDefaultForwardInternalVariant'),
    (8,4,2,3,'BeltDefaultForwardInternalVariant'),
    (9,4,2,3,'BeltDefaultForwardInternalVariant'),
    (10,4,2,3,'BeltDefaultForwardInternalVariant'),
    (11,4,2,3,'BeltDefaultForwardInternalVariant'),
    (8,5,2,3,'BeltDefaultForwardInternalVariant'),
    (9,5,2,3,'BeltDefaultForwardInternalVariant'),
    (10,5,2,3,'BeltDefaultForwardInternalVariant'),
    (11,5,2,3,'BeltDefaultForwardInternalVariant'),
    (7,6,2,3,'BeltDefaultLeftInternalVariantMirrored'),
    (8,6,2,0,'BeltDefaultLeftInternalVariant'),
    (9,6,2,3,'BeltDefaultForwardInternalVariant'),
    (10,6,2,3,'BeltDefaultForwardInternalVariant'),
    (11,6,2,2,'BeltDefaultLeftInternalVariantMirrored'),
    (12,6,2,3,'BeltDefaultLeftInternalVariant'),
    (7,7,2,3,'BeltDefaultForwardInternalVariant'),
    (8,7,2,3,'BeltDefaultLeftInternalVariantMirrored'),
    (9,7,2,0,'BeltDefaultLeftInternalVariant'),
    (10,7,2,2,'BeltDefaultLeftInternalVariantMirrored'),
    (11,7,2,3,'BeltDefaultLeftInternalVariant'),
    (12,7,2,3,'BeltDefaultForwardInternalVariant'),
    (7,8,2,3,'BeltDefaultForwardInternalVariant'),
    (8,8,2,3,'Merger2To1LInternalVariantMirrored'),
    (9,8,2,3,'BeltDefaultLeftInternalVariant'),
    (10,8,2,3,'BeltDefaultLeftInternalVariantMirrored'),
    (11,8,2,3,'Merger2To1LInternalVariant'),
    (12,8,2,3,'BeltDefaultForwardInternalVariant'),
    (7,9,2,3,'BeltDefaultForwardInternalVariant'),
    (8,9,2,3,'CutterHalfInternalVariant'),
    (9,9,2,3,'CutterHalfInternalVariant'),
    (10,9,2,3,'CutterHalfInternalVariant'),
    (11,9,2,3,'CutterHalfInternalVariant'),
    (12,9,2,3,'BeltDefaultForwardInternalVariant'),
    (7,10,2,3,'BeltDefaultForwardInternalVariant'),
    (8,10,2,2,'BeltDefaultLeftInternalVariantMirrored'),
    (9,10,2,3,'Splitter1To2LInternalVariant'),
    (10,10,2,3,'Splitter1To2LInternalVariantMirrored'),
    (11,10,2,0,'BeltDefaultLeftInternalVariant'),
    (12,10,2,3,'BeltDefaultForwardInternalVariant'),
    (7,11,2,3,'Merger2To1LInternalVariantMirrored'),
    (8,11,2,3,'BeltDefaultLeftInternalVariant'),
    (9,11,2,3,'BeltDefaultForwardInternalVariant'),
    (10,11,2,3,'BeltDefaultForwardInternalVariant'),
    (11,11,2,3,'BeltDefaultLeftInternalVariantMirrored'),
    (12,11,2,3,'Merger2To1LInternalVariant'),
    (7,12,2,3,'CutterHalfInternalVariant'),
    (8,12,2,3,'CutterHalfInternalVariant'),
    (9,12,2,3,'BeltDefaultForwardInternalVariant'),
    (10,12,2,3,'BeltDefaultForwardInternalVariant'),
    (11,12,2,3,'CutterHalfInternalVariant'),
    (12,12,2,3,'CutterHalfInternalVariant'),
    (7,13,2,2,'BeltDefaultLeftInternalVariantMirrored'),
    (8,13,2,3,'Splitter1To2LInternalVariant'),
    (9,13,2,3,'BeltDefaultForwardInternalVariant'),
    (10,13,2,3,'BeltDefaultForwardInternalVariant'),
    (11,13,2,3,'Splitter1To2LInternalVariantMirrored'),
    (12,13,2,0,'BeltDefaultLeftInternalVariant'),
    (8,14,2,3,'BeltDefaultForwardInternalVariant'),
    (9,14,2,3,'BeltDefaultForwardInternalVariant'),
    (10,14,2,3,'BeltDefaultForwardInternalVariant'),
    (11,14,2,3,'BeltDefaultForwardInternalVariant'),
    (8,15,2,3,'BeltDefaultForwardInternalVariant'),
    (9,15,2,3,'BeltDefaultForwardInternalVariant'),
    (10,15,2,3,'BeltDefaultForwardInternalVariant'),
    (11,15,2,3,'BeltDefaultForwardInternalVariant'),
    (8,16,2,3,'BeltDefaultForwardInternalVariant'),
    (9,16,2,3,'BeltDefaultForwardInternalVariant'),
    (10,16,2,3,'BeltDefaultForwardInternalVariant'),
    (11,16,2,3,'BeltDefaultForwardInternalVariant'),
    (8,17,2,3,'BeltPortReceiverInternalVariant'),
    (9,17,2,3,'BeltPortReceiverInternalVariant'),
    (10,17,2,3,'BeltPortReceiverInternalVariant'),
    (11,17,2,3,'BeltPortReceiverInternalVariant'),
]

def vn02_halfdestroy_12lane():
    b = [be(T, X=X, Y=Y, L=L, R=R) for (X, Y, L, R, T) in VN02_CELLS]
    return blueprint_islands([island("Foundation_1x1", R=2, buildings=b)])

MODULES = {
    "VN-00 coord test": vn00_coord_test,
    "VN-01 quad isolator 1lane": vn01_quad_isolator_1lane,
    "VN-02 half-destroy 12lane": vn02_halfdestroy_12lane,
}

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "blueprints"
    os.makedirs(outdir, exist_ok=True)
    for name, fn in MODULES.items():
        code = encode_bp(5, fn())
        with open(os.path.join(outdir, name + ".spz2bp"), "w") as f:
            f.write(code)
        print("wrote", name, f"({len(code)} bytes)")
