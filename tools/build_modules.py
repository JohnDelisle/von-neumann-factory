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

MODULES = {
    "VN-00 coord test": vn00_coord_test,
    "VN-01 quad isolator 1lane": vn01_quad_isolator_1lane,
}

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "blueprints"
    os.makedirs(outdir, exist_ok=True)
    for name, fn in MODULES.items():
        code = encode_bp(5, fn())
        with open(os.path.join(outdir, name + ".spz2bp"), "w") as f:
            f.write(code)
        print("wrote", name, f"({len(code)} bytes)")
