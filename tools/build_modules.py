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
from shapez_bp import encode_bp, decode_bp

REF_DIR = os.path.join(os.path.dirname(__file__), "..", "blueprints", "reference")

def gv(container):
    """Unwrap a SerializableXEntry[] container's $values list."""
    if container is None:
        return []
    v = container.get("$values")
    return v if v is not None else (container if isinstance(container, list) else [])

def load_reference_island(filename, index=0):
    """Decode a reference .spz2bp from blueprints/reference/ and return its Nth
    raw island entry dict (used as a black box: we reuse its 'B' verbatim and
    only change the island entry's own X/Y/Z when placing it in our assembly)."""
    path = os.path.join(REF_DIR, filename)
    ver, d = decode_bp(path)
    islands = gv(d["BP"]["Entries"])
    return islands[index]

def load_reference_islands(filename):
    """Decode a reference .spz2bp and return its full list of raw island entries
    (for multi-island assemblies like 'Stacker supporting empty quadrants')."""
    path = os.path.join(REF_DIR, filename)
    ver, d = decode_bp(path)
    return gv(d["BP"]["Entries"])

def translate_islands(islands, dx, dy, dz=0):
    """Return a deep-enough copy of `islands` with every entry's X/Y/Z shifted by
    (dx,dy,dz). Building-local coords (inside each entry's 'B') are untouched --
    only island-grid placement moves, so the whole group stays rigid internally."""
    out = []
    for isl in islands:
        moved = dict(isl)
        moved["X"] = isl["X"] + dx
        moved["Y"] = isl["Y"] + dy
        moved["Z"] = isl["Z"] + dz
        out.append(moved)
    return out

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

    3 StackerStraight chained up column X8 (L0, north flow). Each stacker takes its
    BOTTOM from behind (south, L0) and its TOP from the cell above (L1), fed by John's
    validated pattern: east-edge L0 input -> belts west -> Lift1UpForward (at col+1)
    -> L1 -> BeltDefaultLeftMirrored turn -> north into the stacker's top port.
      q1 (main)  : south edge L0 (X8,Y17) -> s1 bottom
      q2/q3/q4   : east edge L0 (X17), rows Y15/Y12/Y9 -> lifted to each stacker top
    Output: north edge L0 (X8,Y2). Chain s1=q1+q2, s2=+q3, s3=+q4. Feed 4 DISJOINT
    single-quadrant pieces (distinct positions) -> one 4-quadrant layer out.
    """
    SX=8
    stackers=[14,11,8]            # s1,s2,s3 Y rows
    b=[]
    # ---- main chain up column SX (L0) ----
    b.append(be("BeltPortReceiverInternalVariant", X=SX, Y=17, L=0, R=3))
    for y in range(16, 2, -1):
        if y in stackers:
            b.append(be("StackerStraightInternalVariant", X=SX, Y=y, L=0, R=3))
        else:
            b.append(be("BeltDefaultForwardInternalVariant", X=SX, Y=y, L=0, R=3))
    b.append(be("BeltPortSenderInternalVariant", X=SX, Y=2, L=0, R=3))
    # ---- top feed per stacker (replicates John's StackerStraight ref) ----
    for sy in stackers:
        fr=sy+1                                  # feed row (just south of stacker)
        b.append(be("Lift1UpForwardInternalVariant", X=SX+1, Y=fr, L=0, R=2))       # up to (SX,fr,L1)
        for x in range(SX+2, 17):                                                   # belts west X10..X16
            b.append(be("BeltDefaultForwardInternalVariant", X=x, Y=fr, L=0, R=2))
        b.append(be("BeltPortReceiverInternalVariant", X=17, Y=fr, L=0, R=2))       # east-edge top input
        b.append(be("BeltDefaultLeftInternalVariantMirrored", X=SX, Y=fr, L=1, R=2))# L1 turn -> north into (SX,sy,L1)
    return blueprint_islands([island("Foundation_1x1", buildings=b)])


def vn06_quad_splitter_test():
    """Standalone validation assembly for John's real `Quad Splitter` (Foundation_2x4,
    reused verbatim/black-box from blueprints/reference/Quad Splitter.spz2bp).

    Port map extracted by decoding the reference (see conventions.md "Multi-unit
    foundation footprint & port bands"): footprint is island X[ix,ix+1] Y[iy,iy+3]
    (literal 2x4, not rotated by R). Input = EAST edge, row3 only (island cell
    ix+1,iy+3), 12 lanes, flows west. Output = WEST edge, ALL 4 rows (ix,iy+0..3),
    12 lanes each (one quadrant per row), flows west.

    This assembly places the component at island (0,0,0) with its original R=3,
    plus one input stub (island X=2,Y=3, feeding west into the east-edge port) and
    four output stubs (island X=-1,Y=0..3, continuing west out of each west-edge
    port) so John can extend real supply/sinks and watch the quadrant split.
    """
    ref = load_reference_island("Quad Splitter.spz2bp")
    assert ref["T"] == "Foundation_2x4"
    quad_splitter = island("Foundation_2x4", X=0, Y=0, Z=0, R=ref["R"])
    quad_splitter["B"] = ref["B"]  # reuse verbatim, black-box

    islands = [quad_splitter]
    islands.append(island("SpaceBelt_Forward", X=2, Y=3, Z=0, R=2))          # input stub (east side)
    for row in range(4):                                                     # 4 output stubs (west side)
        islands.append(island("SpaceBelt_Forward", X=-1, Y=row, Z=0, R=2))
    return blueprint_islands(islands)


# Pure SpaceBelt_* wiring extracted verbatim from John's tested, working assembly
# "For Claude Splitter and Stacker.spz2bp" (2026-09-03): a splitter/trash disposal
# stage on the west end (for a self-contained testable loop) and the 4 connector
# belts between the Stacker cluster's east edge and the Demuxer. (X,Y,Z,R,T)
VN07_WIRING = [
    (-8, -1, 0, 3, 'SpaceBelt_LeftTurn'),
    (-8,  0, 0, 3, 'SpaceBelt_LeftFwdSplitter'),
    (-8,  1, 0, 2, 'SpaceBelt_TripleSplitter'),
    (-8,  2, 0, 1, 'SpaceBelt_RightTurn'),
    ( 5, -1, 0, 2, 'SpaceBelt_Forward'),
    ( 5,  0, 0, 2, 'SpaceBelt_Forward'),
    ( 5,  1, 0, 2, 'SpaceBelt_Forward'),
    ( 5,  2, 0, 2, 'SpaceBelt_Forward'),
    (10,  2, 0, 2, 'SpaceBelt_Forward'),
]

# --- Fancy A+B Side Overflow: inner/outer lane-swap fix ---------------------
# John's `Fancy A+B Side Overflow` (Foundation_2x4) carries a self-documented bug
# ("SHIT - Mixes lanes up in both these"): a band's OUTER lanes overflow to the
# "A+B Overflow" port as the INNER lanes, and the INNER lanes come out as OUTER.
#
# Cause (traced 2026-09-03): within each 4-lane band, the two OUTER rows tap their
# overflow at splitter column X=9 (In B) / X=8 (In A), while the two INNER rows tap
# at X=7 / X=6. The downstream weave delivers the X=9/X=8 taps to the INNER final
# output columns and the X=7/X=6 taps to the OUTER ones -- hence the crossover.
#
# Fix: swap the splitter columns between each band's outer and inner rows, and shift
# each outer row's launcher hop one cell east so it flies over the cell the inner
# row's overflow now needs (launchers fly OVER belts -- John's original relies on
# that too). No belt crossings required; every downstream cell is untouched, and the
# primary (non-overflow) pass-through stays lane-preserving.
_F  = 'BeltDefaultForwardInternalVariant'
_SM = 'SplitterOverflowLInternalVariantMirrored'
_SP = 'SplitterOverflowLInternalVariant'
_TX = 'BeltPortSenderInternalVariant'
_RX = 'BeltPortReceiverInternalVariant'

# (X,Y): ((expected_type, expected_R), (new_type, new_R))
FANCY_AB_LANE_FIX = {
    # In B band, rows 8-11
    ( 6,  8): ((_RX, 2), (_F,  2)),   # row 8 OUTER: splitter X9->X7, hop (8->6)->(10->8)
    ( 7,  8): ((_F,  3), (_SM, 2)),
    ( 8,  8): ((_TX, 2), (_RX, 2)),
    ( 9,  8): ((_SM, 2), (_F,  3)),   # now row 9's northbound overflow belt
    (10,  8): ((_F,  2), (_TX, 2)),
    ( 7,  9): ((_SM, 2), (_F,  2)),   # row 9 INNER: splitter X7->X9
    ( 9,  9): ((_F,  2), (_SM, 2)),
    ( 7, 10): ((_SP, 2), (_F,  2)),   # row 10 INNER: splitter X7->X9
    ( 9, 10): ((_F,  2), (_SP, 2)),
    ( 6, 11): ((_RX, 2), (_F,  2)),   # row 11 OUTER: splitter X9->X7, hop (8->6)->(10->8)
    ( 7, 11): ((_F,  1), (_SP, 2)),
    ( 8, 11): ((_TX, 2), (_RX, 2)),
    ( 9, 11): ((_SP, 2), (_F,  1)),   # now row 10's southbound overflow belt
    (10, 11): ((_F,  2), (_TX, 2)),
    # In A band, rows 28-31 (their splitter sections sit in rows 27/28/31/32)
    ( 5, 27): ((_RX, 2), (_F,  2)),   # row 28 OUTER: splitter X8->X6, hop (7->5)->(9->7)
    ( 6, 27): ((_F,  3), (_SM, 2)),
    ( 7, 27): ((_TX, 2), (_RX, 2)),
    ( 8, 27): ((_SM, 2), (_F,  3)),   # now row 29's northbound overflow belt
    ( 9, 27): ((_F,  2), (_TX, 2)),
    ( 6, 28): ((_SM, 2), (_F,  2)),   # row 29 INNER: splitter X6->X8
    ( 8, 28): ((_F,  2), (_SM, 2)),
    ( 6, 31): ((_SP, 2), (_F,  2)),   # row 30 INNER: splitter X6->X8
    ( 8, 31): ((_F,  2), (_SP, 2)),
    ( 5, 32): ((_RX, 2), (_F,  2)),   # row 31 OUTER: splitter X8->X6, hop (7->5)->(9->7)
    ( 6, 32): ((_F,  1), (_SP, 2)),
    ( 7, 32): ((_TX, 2), (_RX, 2)),
    ( 8, 32): ((_SP, 2), (_F,  1)),   # now row 30's southbound overflow belt
    ( 9, 32): ((_F,  2), (_TX, 2)),
}

def apply_fancy_ab_lane_fix(island_entry, floors=(0, 1, 2)):
    """Apply FANCY_AB_LANE_FIX to every floor of a `Fancy A+B Side Overflow`
    island entry, in place. Asserts the pre-edit state matches exactly, so a
    changed upstream reference fails loudly instead of silently mis-patching."""
    buildings = gv(island_entry["B"]["Entries"])
    index = {(e["X"], e["Y"], e["L"]): e for e in buildings}
    changed = 0
    for (x, y), ((et, er), (nt, nr)) in FANCY_AB_LANE_FIX.items():
        for L in floors:
            e = index.get((x, y, L))
            if e is None:
                raise AssertionError(f"lane-fix: missing cell X={x} Y={y} L={L}")
            if e["T"] != et or e["R"] != er:
                raise AssertionError(
                    f"lane-fix: X={x} Y={y} L={L} is {e['T']} R={e['R']}, expected {et} R={er}")
            e["T"], e["R"] = nt, nr
            changed += 1
    return changed


def vn08_fancy_ab_lane_fixed():
    """John's `Fancy A+B Side Overflow` with the inner/outer lane-swap bug fixed.

    Standalone component (Foundation_2x4), for side-by-side comparison against the
    original. Verified by tracing every lane's overflow branch: all 8 lanes (both
    bands) now land outer->outer and inner->inner, and all 24 primary pass-through
    paths (8 rows x 3 floors) remain lane-preserving. See FANCY_AB_LANE_FIX above.
    """
    ref = load_reference_island("Fancy A+B Side Overflow.spz2bp")
    assert ref["T"] == "Foundation_2x4"
    apply_fancy_ab_lane_fix(ref)
    isl = island(ref["T"], X=0, Y=0, Z=0, R=ref["R"])
    isl["B"] = ref["B"]
    return blueprint_islands([isl])


def vn09_stacker_empty_quadrants_fixed():
    """`Stacker supporting empty quadrants` with both embedded `Fancy A+B Side
    Overflow` units lane-fixed (see FANCY_AB_LANE_FIX). Drop-in replacement for the
    stock component; everything else is byte-identical to John's original."""
    islands = load_reference_islands("Stacker supporting empty quadrants.spz2bp")
    patched = 0
    for isl in islands:
        if isl["T"] == "Foundation_2x4" and isl.get("B"):
            apply_fancy_ab_lane_fix(isl)
            patched += 1
    assert patched == 2, f"expected 2 Fancy A+B units, patched {patched}"
    return blueprint_islands(islands)


def vn07_reassembly_test():
    """Quarter-scale reassembly test: Quad Splitter -> Demuxer -> Stacker supporting
    empty quadrants -> (test-rig) Trash. Reproduces, from code, John's tested and
    CONFIRMED WORKING hand-built assembly "For Claude Splitter and Stacker.spz2bp"
    (2026-09-03) -- one base shape splits into 4 quadrants, reassembles back into
    the original shape (tested with one blank quadrant too, per John).

    Key fix vs. the first (untested) VN-07: Quad Splitter's 4 outputs need
    NORMALIZING before they reach the Stacker -- each output belt must carry its
    quadrant shape in its ORIGINAL orientation (don't let e.g. NW rotate into SW).
    That's what `Demuxer` (Foundation_2x4_Flipped) does; it sits directly adjacent
    to Quad Splitter's west edge (zero-gap, ports connect straight across the
    island boundary -- no SpaceBelt tile needed between them).

    Also per John: the red X's this blueprint shows on stamp are EXPECTED/benign --
    each Stacker platform's "Top" input has two alternate physical ports with a
    "USE ONE INPUT ONLY" label between them (see conventions.md); the unused one's
    adjacent empty SpaceBelt cell is what the game flags, not a real error.

    All foundations reused verbatim/black-box from blueprints/reference/; only the
    SpaceBelt_* routing tiles (VN07_WIRING above) are hand-authored, copied exactly
    from John's tested layout.
    """
    def placed(filename, X, Y, Z, R):
        ref = load_reference_island(filename)
        isl = island(ref["T"], X=X, Y=Y, Z=Z, R=R)
        isl["B"] = ref["B"]
        return isl

    islands = []
    # west-end test rig: 4x Trash sinks + a splitter stage feeding them
    for i, y in enumerate((-1, 0, 1, 2)):
        islands.append(placed("Trash.spz2bp", X=-9, Y=y, Z=0, R=3))
    # Stacker supporting empty quadrants (38 islands), offset to match John's layout
    # (original reference has its Overflow platform at X=-5,Y=0; here it's X=-6,Y=1)
    stacker_islands = load_reference_islands("Stacker supporting empty quadrants.spz2bp")
    islands += translate_islands(stacker_islands, dx=-1, dy=1, dz=0)
    # Demuxer (normalizes quadrant orientation) directly adjacent to Quad Splitter
    islands.append(placed("Demuxer.spz2bp", X=6, Y=0, Z=0, R=1))
    # Quad Splitter (the shape source for this test)
    islands.append(placed("Quad Splitter.spz2bp", X=8, Y=1, Z=0, R=3))
    # hand-authored SpaceBelt_* connector/test-rig wiring
    for (X, Y, Z, R, T) in VN07_WIRING:
        islands.append(island(T, X=X, Y=Y, Z=Z, R=R))

    return blueprint_islands(islands)


MODULES = {
    "VN-00 coord test": vn00_coord_test,
    "VN-01 quad isolator 1lane": vn01_quad_isolator_1lane,
    "VN-02 half-destroy 12lane": vn02_halfdestroy_12lane,
    "VN-03 rotate90CW 12lane": vn03_rotate90cw_12lane,
    "VN-04 stacker 2in 1lane": vn04_stacker_2in_1lane,
    "VN-05 assembler 1lane 4quad": vn05_assembler_1lane_4quad,
    "VN-06 quad splitter test": vn06_quad_splitter_test,
    "VN-07 reassembly test": vn07_reassembly_test,
    "VN-08 fancy A+B lane fixed": vn08_fancy_ab_lane_fixed,
    "VN-09 stacker empty quadrants fixed": vn09_stacker_empty_quadrants_fixed,
}

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "blueprints"
    os.makedirs(outdir, exist_ok=True)
    for name, fn in MODULES.items():
        code = encode_bp(5, fn())
        with open(os.path.join(outdir, name + ".spz2bp"), "w") as f:
            f.write(code)
        print("wrote", name, f"({len(code)} bytes)")
