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

MODULES = {
    "VN-00 coord test": vn00_coord_test,
}

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "blueprints"
    os.makedirs(outdir, exist_ok=True)
    for name, fn in MODULES.items():
        code = encode_bp(5, fn())
        with open(os.path.join(outdir, name + ".spz2bp"), "w") as f:
            f.write(code)
        print("wrote", name, f"({len(code)} bytes)")
