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
import base64, os, sys
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

BYTE_ARRAY_TYPE = "System.Byte[], mscorlib"

def config(b64):
    """A building `C` blob. The `$type` key is NOT optional -- a config object
    without it makes the game reject the ENTIRE blueprint file silently (it just
    never appears in the in-game folder). Cost us a round-trip; see
    check_configs()."""
    return {"$type": BYTE_ARRAY_TYPE, "$value": b64}

def set_config(entry, b64):
    """Set a building entry's config value, preserving its existing `$type`."""
    if isinstance(entry.get("C"), dict):
        entry["C"]["$value"] = b64
    else:
        entry["C"] = config(b64)
    return entry

def check_configs(bp):
    """Every non-null `C` must be an object carrying `$type` (see config()).
    Run over every generated module so a malformed config fails the build instead
    of producing a file the game silently ignores."""
    bad = []
    def visit(entries, where):
        for e in gv(entries):
            c = e.get("C")
            if c is None:
                continue
            if not isinstance(c, dict) or "$type" not in c or "$value" not in c:
                bad.append(f"{where} {e.get('T')} @({e.get('X')},{e.get('Y')},{e.get('L')}): {c!r}")
    for isl in gv(bp["BP"]["Entries"]):
        visit((isl.get("B") or {}).get("Entries"), f"island({isl.get('X')},{isl.get('Y')})")
        if "B" not in isl:
            visit([isl], "island-entry")
    if bad:
        raise AssertionError("malformed building configs (missing $type):\n  " + "\n  ".join(bad))
    return bp

def label_texts(island_entry):
    """Every `LabelDefaultInternalVariant` text inside an island entry.
    Label config is base64(<len:u16 LE> + UTF-8) -- see docs/conventions.md.
    Reading John's own labels is how we identify a platform's function; never
    guess it from building counts or coordinates."""
    out = []
    for e in gv((island_entry.get("B") or {}).get("Entries")):
        if e.get("T") != "LabelDefaultInternalVariant" or not e.get("C"):
            continue
        c = e["C"]
        raw = base64.b64decode(c["$value"] if isinstance(c, dict) else c)
        try:
            out.append(raw[2:].decode("utf-8"))
        except UnicodeDecodeError:
            pass
    return out

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

# The component is FOUR bands (In A / In B x north / south = 48 lanes), one per
# island-row of the 2x4 foundation. Each band gets the same treatment; the two
# band patterns below are stamped at the four Y offsets.
#
#   In B rows  8, 9,10,11 (north, offset 0) and -12,-11,-10,-9 (south, offset -20)
#   In A rows 27,28,31,32 (north, offset 0) and -33,-32,-29,-28 (south, offset -60)
#
# (dX, dY): ((expected_type, expected_R), (new_type, new_R))
_FIX_IN_B = {
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
}
_FIX_IN_A = {
    ( 5, 27): ((_RX, 2), (_F,  2)),   # outer lane: splitter X8->X6, hop (7->5)->(9->7)
    ( 6, 27): ((_F,  3), (_SM, 2)),
    ( 7, 27): ((_TX, 2), (_RX, 2)),
    ( 8, 27): ((_SM, 2), (_F,  3)),   # now the adjacent inner lane's overflow belt
    ( 9, 27): ((_F,  2), (_TX, 2)),
    ( 6, 28): ((_SM, 2), (_F,  2)),   # inner lane: splitter X6->X8
    ( 8, 28): ((_F,  2), (_SM, 2)),
    ( 6, 31): ((_SP, 2), (_F,  2)),   # inner lane: splitter X6->X8
    ( 8, 31): ((_F,  2), (_SP, 2)),
    ( 5, 32): ((_RX, 2), (_F,  2)),   # outer lane: splitter X8->X6, hop (7->5)->(9->7)
    ( 6, 32): ((_F,  1), (_SP, 2)),
    ( 7, 32): ((_TX, 2), (_RX, 2)),
    ( 8, 32): ((_SP, 2), (_F,  1)),   # now the adjacent inner lane's overflow belt
    ( 9, 32): ((_F,  2), (_TX, 2)),
}

def _build_lane_fix():
    fix = {}
    for dy in (0, -20):          # In B: north band, south band
        for (x, y), v in _FIX_IN_B.items():
            fix[(x, y + dy)] = v
    for dy in (0, -60):          # In A: north band, south band
        for (x, y), v in _FIX_IN_A.items():
            fix[(x, y + dy)] = v
    return fix

FANCY_AB_LANE_FIX = _build_lane_fix()

# The two "SHIT - Mixes lanes up in both these" warning labels document the bug;
# once it's fixed they're stale, so the fix removes them (John did the same).
FANCY_AB_STALE_LABELS = [(12, 14, 0), (13, 22, 0)]

def apply_fancy_ab_lane_fix(island_entry, floors=(0, 1, 2)):
    """Apply FANCY_AB_LANE_FIX to every floor of a `Fancy A+B Side Overflow`
    island entry, in place, and drop the now-stale bug-warning labels. Asserts the
    pre-edit state matches exactly, so a changed upstream reference fails loudly
    instead of silently mis-patching."""
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
    # drop stale warning labels (only present on the un-deduplicated copy)
    stale = {k for k in FANCY_AB_STALE_LABELS
             if (k in index and index[k]["T"] == "LabelDefaultInternalVariant")}
    if stale:
        kept = [e for e in buildings
                if (e["X"], e["Y"], e["L"]) not in stale
                or e["T"] != "LabelDefaultInternalVariant"]
        island_entry["B"]["Entries"]["$values"] = kept
    return changed


def vn08_fancy_ab_lane_fixed():
    """`Fancy A+B Side Overflow` with the inner/outer lane-swap bug fixed on all
    FOUR bands (In A / In B x north / south = 48 lanes).

    Generated by applying FANCY_AB_LANE_FIX to the pre-fix reference. The result is
    byte-identical to John's own hand-mirrored fix
    (`blueprints/reference/Fancy A+B Side Overflow.spz2bp`) -- the build asserts
    that below, so this doubles as a cross-check of the patch against his version.

    Verified by tracing every lane's overflow branch: all 16 lanes (4 bands) land
    outer->outer and inner->inner, and every primary pass-through path stays
    lane-preserving.
    """
    ref = load_reference_island("Fancy A+B Side Overflow (pre-lane-fix).spz2bp")
    assert ref["T"] == "Foundation_2x4"
    apply_fancy_ab_lane_fix(ref)
    isl = island(ref["T"], X=0, Y=0, Z=0, R=ref["R"])
    isl["B"] = ref["B"]

    # cross-check: our generated fix must match John's hand-mirrored version exactly
    johns = load_reference_island("Fancy A+B Side Overflow.spz2bp")
    ours_cells = {(e["X"], e["Y"], e["L"]): (e["T"], e["R"]) for e in gv(isl["B"]["Entries"])}
    john_cells = {(e["X"], e["Y"], e["L"]): (e["T"], e["R"]) for e in gv(johns["B"]["Entries"])}
    assert ours_cells == john_cells, (
        f"lane-fix diverges from John's version: "
        f"{len(set(ours_cells.items()) ^ set(john_cells.items()))} differing cells")
    return blueprint_islands([isl])


def load_fixed_stacker_islands():
    """`Stacker supporting empty quadrants` island list with both embedded
    `Fancy A+B Side Overflow` units lane-fixed (see FANCY_AB_LANE_FIX)."""
    islands = load_reference_islands("Stacker supporting empty quadrants.spz2bp")
    patched = 0
    for isl in islands:
        if isl["T"] == "Foundation_2x4" and isl.get("B"):
            apply_fancy_ab_lane_fix(isl)
            patched += 1
    assert patched == 2, f"expected 2 Fancy A+B units, patched {patched}"
    return islands


def vn09_stacker_empty_quadrants_fixed():
    """`Stacker supporting empty quadrants` with both embedded `Fancy A+B Side
    Overflow` units lane-fixed. Drop-in replacement for the stock component;
    everything else is byte-identical to John's original."""
    return blueprint_islands(load_fixed_stacker_islands())


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

    NOTE (2026-09-03): now built on the LANE-FIXED stacker (see FANCY_AB_LANE_FIX).
    The layout is otherwise identical to the version John validated in-game, but the
    two embedded `Fancy A+B Side Overflow` units differ from what he tested, so this
    wants a re-test to confirm nothing regressed.
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
    # Stacker supporting empty quadrants (38 islands), lane-fixed, offset to match
    # John's layout (stock reference has its Overflow platform at X=-5,Y=0; here X=-6,Y=1)
    islands += translate_islands(load_fixed_stacker_islands(), dx=-1, dy=1, dz=0)
    # Demuxer (normalizes quadrant orientation) directly adjacent to Quad Splitter
    islands.append(placed("Demuxer.spz2bp", X=6, Y=0, Z=0, R=1))
    # Quad Splitter (the shape source for this test)
    islands.append(placed("Quad Splitter.spz2bp", X=8, Y=1, Z=0, R=3))
    # hand-authored SpaceBelt_* connector/test-rig wiring
    for (X, Y, Z, R, T) in VN07_WIRING:
        islands.append(island(T, X=X, Y=Y, Z=Z, R=R))

    return blueprint_islands(islands)


def vn10_any_shape_maker_lane_fixed():
    """`Full Belt Any Shape Maker` with all EIGHT embedded `Fancy A+B Side
    Overflow` units lane-fixed (see FANCY_AB_LANE_FIX / VN-08).

    This is John's full-belt single-layer any-shape synthesizer, unchanged except
    for the lane fix -- 4 identical lanes of

        mixed base shapes (1/4 belt)
          -> Quad Splitter -> Demuxer -> Quaded Filter
          -> Stacker supporting empty quadrants -> the requested shape

    plus 20 `Overflow` 1x1 sinks and 4 `Trash` 1x1. `MAM working.spz2bp` is the
    same machine translated +1 in X; this supersedes both.

    The `Quaded Filter` platforms are left untouched here -- swapping their button
    /ConstantSignal preset bank for the HUB Goal Receiver is VN-11.

    Fancy A+B units are identified by John's own "Fancy" label, not by building
    count: the two variants differ (1765 vs 1763 buildings, the stale bug-warning
    labels), and the 2x4 Demuxers must NOT be patched.
    """
    islands = load_reference_islands("Full Belt Any Shape Maker.spz2bp")
    patched = 0
    for isl in islands:
        if isl["T"] == "Foundation_2x4" and "Fancy" in label_texts(isl):
            apply_fancy_ab_lane_fix(isl)
            patched += 1
    assert patched == 8, f"expected 8 Fancy A+B units, patched {patched}"

    # sanity: nothing added or removed except the stale bug-warning labels
    ref = load_reference_islands("Full Belt Any Shape Maker.spz2bp")
    before = sum(len(gv((i.get("B") or {}).get("Entries"))) for i in ref)
    after = sum(len(gv((i.get("B") or {}).get("Entries"))) for i in islands)
    assert len(islands) == len(ref), "island count changed"
    assert before - after == 8, f"building delta {before - after}, expected 8 stale labels"
    return blueprint_islands(islands)


# ---------------------------------------------------------------- VN-11 / VN-12
# The goal-driven `Quaded Filter`.
#
# The stock filter's logic block is a target-shape decomposer: one shape signal in
# -> VirtualRotator/VirtualAnalyzer fan -> four per-quadrant signals -> wire
# transmitters -> the 4 bands' 48 BeltFilters. Its input was a 6-slot preset bank
# (a ButtonDefault gating a ConstantSignal through a LogicGateIf):
#
#   button (5,14) gates const (4,15) = null        "build nothing"
#   button (5,16) gates const (4,17) = --CuCu--
#   button (5,18) gates const (4,19) = RuRuRuRu
#   button (5,20) gates const (4,21) = SuSuSuSu
#   button (5,22) gates const (4,23) = WuWuWuWu
#   button (5,24) gates const (4,25) = CuRuSuWu    <- the "arbitrary shape" slot
#
# (`--CuCu--` and `CuRuSuWu` are the proof this machine builds ARBITRARY
# single-layer shapes -- empty quadrants and four different types at once.)
#
# JOHN REPLACED THAT INPUT STAGE HIMSELF (`For Claude Filter with Signal.spz2bp`,
# 2026-09-03) after our own attempt failed twice. His version, vs the stock filter:
#   + ControlledSignalReceiverMirrored (4,22) R3 -- 3x3 over X3-5 x Y21-23
#   + ConstantSignal (6,22) = channel 123        -- origin+2 east (= R+1, mirrored)
#   + wire column north up X4 (Y16-20) from the receiver's output at (4,20)
#   + LogicGateCompareMirrored (4,15), LogicGateNot (5,16), null const (4,14)
#   + a Display2x2 at (9,22) showing the received signal
#   - the entire button/preset bank (6 buttons, 5 shape constants, 6 IF gates)
#   net 1096 -> 1082 buildings
#
# We use his platform VERBATIM as a black box (PLAYBOOK: reuse John's ecosystem,
# don't rebuild it). Our own placement attempts are gone; what they taught is in
# docs/conventions.md (receiver footprint, the two silent failure modes) and
# docs/PLAYBOOK.md (never infer a footprint from in-situ copies).
PRESET_BUTTONS = [(5, y, 0) for y in (14, 16, 18, 20, 22, 24)]
PRESET_SLOT_CURUSUWU = (5, 24, 0)   # the button gating the CuRuSuWu constant
BUTTON_ON, BUTTON_OFF = "AQ==", "AA=="


def int_signal_config(n):
    """A `ConstantSignal` integer config: tag 0x03 + int32 little-endian."""
    return config(base64.b64encode(b"\x03" + int(n).to_bytes(4, "little")).decode("ascii"))


def check_int_signal_encoding():
    """Self-check: our integer encoder must reproduce John's channel-123 constant
    from `For Claude Signal Receiver.spz2bp` byte-for-byte."""
    ref = load_reference_island("For Claude Signal Receiver.spz2bp")
    const = [e for e in gv(ref["B"]["Entries"])
             if e["T"] == "ConstantSignalDefaultInternalVariant"]
    assert len(const) == 1, "minimal receiver reference is not as described"
    ours, johns = int_signal_config(123)["$value"], const[0]["C"]["$value"]
    assert ours == johns, f"int signal encoding mismatch: ours {ours!r} vs John's {johns!r}"


def load_goal_driven_filter():
    """John's goal-driven `Quaded Filter` island, used verbatim as a black box."""
    isl = load_reference_island("For Claude Filter with Signal.spz2bp")
    assert isl["T"] == "Foundation_1x4", f"unexpected foundation {isl['T']}"
    assert "Quaded Filter" in label_texts(isl), "not a Quaded Filter platform"
    types = {e["T"] for e in gv(isl["B"]["Entries"])}
    assert "ControlledSignalReceiverInternalVariantMirrored" in types, "no Goal Receiver"
    assert "ButtonDefaultInternalVariant" not in types, \
        "preset buttons still present -- this is not the goal-driven version"
    return isl


def extract_quaded_filter():
    """The stock (preset-driven) `Quaded Filter` from `Full Belt Any Shape
    Maker.spz2bp`, placed alone at the origin. Extracted from the embedded copy
    (6 preset slots), NOT from standalone `Filter.spz2bp` (5 slots, different
    shapes)."""
    islands = load_reference_islands("Full Belt Any Shape Maker.spz2bp")
    qf = [i for i in islands
          if i["T"] == "Foundation_1x4" and "Quaded Filter" in label_texts(i)]
    assert len(qf) == 4, f"expected 4 Quaded Filter platforms, found {len(qf)}"

    # all four lanes must carry an identical filter platform
    def cells(i):
        return sorted((e["X"], e["Y"], e["L"], e["T"], e["R"]) for e in gv(i["B"]["Entries"]))
    assert all(cells(i) == cells(qf[0]) for i in qf[1:]), \
        "the 4 embedded Quaded Filters are not identical"

    isl = island(qf[0]["T"], X=0, Y=0, Z=0, R=qf[0]["R"])
    isl["B"] = qf[0]["B"]
    return isl


def vn11a_quaded_filter_verbatim():
    """CONTROL: the stock preset-driven `Quaded Filter` extracted and re-placed at
    the origin with ZERO edits. Kept as the known-good baseline to A/B against."""
    return blueprint_islands([extract_quaded_filter()])


def vn11_quaded_filter_goal_driven():
    """The goal-driven `Quaded Filter` platform -- John's own
    `For Claude Filter with Signal.spz2bp`, used VERBATIM as a black box.

    He rebuilt the input stage himself after our two attempts failed: receiver at
    (4,22) R3 (3x3 over X3-5 x Y21-23), channel constant 123 at (6,22), a wire
    column north up X4 into a Compare/Not stage, and the whole button/preset bank
    removed. Component blueprint; VN-12 stamps four of these.
    """
    check_int_signal_encoding()
    src = load_goal_driven_filter()
    isl = island(src["T"], X=0, Y=0, Z=0, R=src["R"])
    isl["B"] = src["B"]
    return blueprint_islands([isl])


def _lane_fixed_any_shape_maker():
    """`Full Belt Any Shape Maker` islands with all 8 `Fancy A+B` units lane-fixed."""
    islands = load_reference_islands("Full Belt Any Shape Maker.spz2bp")
    fancy = 0
    for isl in islands:
        if isl["T"] == "Foundation_2x4" and "Fancy" in label_texts(isl):
            apply_fancy_ab_lane_fix(isl)
            fancy += 1
    assert fancy == 8, f"expected 8 Fancy A+B units, patched {fancy}"
    return islands


def select_preset(island_entry, button_cell):
    """Enable exactly one slot of a `Quaded Filter`'s preset bank."""
    index = {(e["X"], e["Y"], e["L"]): e for e in gv(island_entry["B"]["Entries"])}
    for cell in PRESET_BUTTONS:
        e = index[cell]
        assert e["T"] == "ButtonDefaultInternalVariant", f"no button at {cell}"
        set_config(e, BUTTON_ON if cell == button_cell else BUTTON_OFF)
    return island_entry


def vn12_mam_preset_curusuwu():
    """The lane-fixed `Full Belt Any Shape Maker` with all four `Quaded Filter`
    platforms switched to the `CuRuSuWu` preset -- a circle, a rect, a star and a
    windmill, one per quadrant.

    Button edits only: no Goal Receiver, no buildings added or removed, so it
    carries none of the risk that blanked the goal-driven build. This is the
    strongest thing we can test today -- if it produces `CuRuSuWu` at full belt,
    the whole arbitrary-single-layer-shape claim is proven in-game and only the
    goal wiring is left.
    """
    islands = _lane_fixed_any_shape_maker()
    n = 0
    for isl in islands:
        if isl["T"] == "Foundation_1x4" and "Quaded Filter" in label_texts(isl):
            select_preset(isl, PRESET_SLOT_CURUSUWU)
            n += 1
    assert n == 4, f"expected 4 Quaded Filter platforms, switched {n}"
    return blueprint_islands(islands)


def vn12_mam_goal_driven():
    """THE MAM: lane-fixed `Full Belt Any Shape Maker` with all four `Quaded
    Filter` platforms swapped for John's goal-driven version (VN-11).

    Full belt of mixed uncoloured base shapes in; full belt of whatever
    single-layer shape the HUB requests out. Each filter island keeps its own
    X/Y/Z/R and only its building payload `B` is replaced -- building-local
    coordinates are independent of island placement, and both foundations are
    `Foundation_1x4` at the same R (asserted below).
    """
    check_int_signal_encoding()
    islands = _lane_fixed_any_shape_maker()
    n = 0
    for isl in islands:
        if isl["T"] == "Foundation_1x4" and "Quaded Filter" in label_texts(isl):
            src = load_goal_driven_filter()   # fresh copy per island, no aliasing
            assert src["T"] == isl["T"] and src["R"] == isl["R"], (
                f"filter mismatch: John's {src['T']} R{src['R']} vs "
                f"embedded {isl['T']} R{isl['R']}")
            isl["B"] = src["B"]
            n += 1
    assert n == 4, f"expected 4 Quaded Filter platforms, swapped {n}"
    return blueprint_islands(islands)


# ------------------------------------------------- platform bounds & footprints
# John asked for this after VN-13p4 stamped with the signal generator clashing into
# the receiver: "maybe add some platform size/boundary detection to prevent future
# issues like that?" (2026-09-04).
#
# The buildable window is [2,17] in BOTH axes on a 1x1 -- not a guess: measured over
# **85,372 buildings on Foundation_1x1 platforms** across John's whole library
# (blueprints/2026 + blueprints/reference). X range 2..17, Y range 2..17, and he uses
# the extremes himself (X=2 2,804 times, Y=17 856 times). So the edge is NOT what
# broke VN-13p4.
#
# What broke it is the second rule below: **a multi-cell building records only its
# ORIGIN cell** (conventions.md), so its other cells are invisible in the entry list
# and nothing stops us dropping another building on top of them. A
# `ControlledSignalReceiver` is 3x3 centred on its entry, so the receiver at (4,15)
# occupies X3-5/Y14-16 -- and VN-13's chain was laid straight through that body.
#
# FOOTPRINTS: (width, height, anchor). Anchor "c" = entry cell is the centre;
# "o" = entry cell is the origin corner (extends +X/+Y). Only list what we have
# EXTRACTED; anything unknown that is not plainly 1x1 goes in UNKNOWN_FOOTPRINT and
# raises rather than being assumed 1x1 -- assuming is exactly how VN-13 shipped broken.
PLATFORM_MIN, PLATFORM_MAX = 2, 17

FOOTPRINTS = {
    # 3x3 centred -- from `For Claude Signal Receiver.spz2bp`, where John outlined
    # the receiver at (9,10) with an L1 belt ring at X7-11/Y8-12. That ring is the
    # border of a 5x5, i.e. exactly the cells adjacent to a 3x3 core at X8-10/Y9-11,
    # and his own output wire sits at (9,8) ON the ring. Ports are at origin +-2.
    "ControlledSignalReceiverInternalVariant": (3, 3, "c"),
    "ControlledSignalReceiverInternalVariantMirrored": (3, 3, "c"),
    "ControlledSignalTransmitterInternalVariant": (3, 3, "c"),
    "ControlledSignalTransmitterInternalVariantMirrored": (3, 3, "c"),
    "WireGlobalTransmitterReceiverInternalVariant": (3, 3, "c"),
}

# The 3x3 body is now strongly evidenced, not inferred from one reference: across
# **all 45 controlled-signal buildings in John's library**, the eight cells
# immediately around the entry are EMPTY in every single instance, and the only
# occupied cells within 2 sit exactly on the ports at +-2.
#
# A SECOND rule was proposed here and then REFUTED -- recorded so nobody re-derives
# it. The census also showed that a port cell (+-2) is only ever occupied by a
# Wire*/Display*/ConstantSignal* in John's library, never a Virtual* or LogicGate*,
# so we guessed that a virtual building may not sit on a port cell and that this was
# what killed VN-13 v1. **VN-13q1 disproves it**: an analyzer placed directly on the
# receiver's output port cell imports and runs fine (John, 2026-09-04). John simply
# never happens to do it. Absence from his library is not a game rule -- the same
# trap PLAYBOOK warns about for footprints.

# Multi-cell buildings whose anchor we have NOT established. Placing one is refused
# until someone extracts it (PLAYBOOK: ask John for a minimal reference, ideally with
# the building outlined in belt on the floor above).
UNKNOWN_FOOTPRINT = {
    "Display2x2InternalVariant", "Display2x2InternalVariantMirrored",
    "Display3x3InternalVariant",
    "VirtualHalvesSwapperDefaultInternalVariant",
}


def footprint_cells(entry):
    """Every cell a building actually occupies -- not just the origin it records."""
    T, x, y, L = entry["T"], entry["X"], entry["Y"], entry.get("L", 0)
    if T in UNKNOWN_FOOTPRINT:
        raise AssertionError(
            f"{T} at ({x},{y},L{L}): multi-cell building with an UNEXTRACTED anchor. "
            f"Get a minimal reference from John (box-trick: outline it in belt on the "
            f"floor above) and add it to FOOTPRINTS before placing one.")
    w, h, anchor = FOOTPRINTS.get(T, (1, 1, "o"))
    if anchor == "c":
        x0, y0 = x - (w - 1) // 2, y - (h - 1) // 2
    else:
        x0, y0 = x, y
    return [(x0 + dx, y0 + dy, L) for dx in range(w) for dy in range(h)]


def validate_layout(buildings, where="", foundation="Foundation_1x1"):
    """Refuse a layout that the game would reject or mis-stamp.

    Catches, for every building INCLUDING the hidden cells of multi-cell ones:
      * anything outside the buildable [2,17] window;
      * two buildings sharing a cell.
    Only 1x1 foundations are bounds-checked -- for a multi-platform foundation the
    local-coordinate window depends on the island rotation (a Foundation_1x4 at R1
    runs along Y, not X), which we have not pinned down, so bounds are skipped and
    only collisions are checked.
    """
    problems, occupied = [], {}
    check_bounds = foundation == "Foundation_1x1"
    for e in buildings:
        for cell in footprint_cells(e):
            x, y, L = cell
            if check_bounds and not (PLATFORM_MIN <= x <= PLATFORM_MAX
                                     and PLATFORM_MIN <= y <= PLATFORM_MAX):
                problems.append(
                    f"{e['T']} at ({e['X']},{e['Y']},L{e.get('L',0)}) occupies {cell} "
                    f"-- outside the buildable [{PLATFORM_MIN},{PLATFORM_MAX}] window")
            if cell in occupied:
                problems.append(
                    f"{e['T']} at ({e['X']},{e['Y']},L{e.get('L',0)}) and "
                    f"{occupied[cell]} both occupy {cell}")
            occupied[cell] = f"{e['T']} at ({e['X']},{e['Y']},L{e.get('L',0)})"
    if problems:
        raise AssertionError(f"invalid layout {where}:\n  " + "\n  ".join(problems))
    return buildings


def our_island(foundation, buildings, **kw):
    """`island()` for platforms WE author -- validated before it can ship."""
    validate_layout(buildings, where=kw.get("where", foundation), foundation=foundation)
    kw.pop("where", None)
    return island(foundation, buildings=buildings, **kw)


# ---------------------------------------------------------------- VN-13 (v2)
# The COLOUR BRAIN: extract the goal's per-quadrant COLOUR from the goal signal.
#
# Phase 2 needs, for each band P, the colour the goal wants at position P. The
# analyzer reads its input shape's NE part and emits that part's shape on one output
# and its COLOUR on the other -- and the colour is `null` for an empty or pin
# quadrant, a ready-made "this quadrant needs no paint" flag.
#
# So: rotate the goal so the wanted quadrant lands in NE, analyze, read the colour.
# No post-rotation, unlike the filter's shape fan -- rotating a colour is a no-op.
#
#   quadrant | rotation before the analyzer
#   NE       | none
#   SE       | 1x VirtualRotatorCCW
#   SW       | 2x VirtualRotator      (CW)
#   NW       | 1x VirtualRotator      (CW)
#
# v1 WAS REJECTED BY THE GAME -- it never appeared in the blueprint folder. The
# bisection (VN-13p0..p6, John 2026-09-04) found why, and both causes were mine:
#
#   p0-p3 present  => our encoder, our label/int encodings, the receiver itself and
#                     John's own receiver coordinates are all fine.
#   p4 PRESENT BUT INVALID  => receiver (4,15) + channel constant (2,15). Not an edge
#                     problem: [2,17] is confirmed buildable in both axes over 85,372
#                     of John's own buildings on 1x1s. The receiver is **3x3 centred**,
#                     so it occupies X3-5/Y14-16 and the layout clashed with its own
#                     invisible body.
#   p5 present     => the virtual chain and the shape-signal encoding are fine, and
#                     it read `CrCgCbCu` -> 1x CW -> colour `u` + shape `Cu------`,
#                     which is EXACTLY the predicted NW quadrant. **The colour maths
#                     is validated.**
#   p6 MISSING     => one chain at those same cells: the analyzer/displays/label were
#                     laid straight through the receiver's 3x3 body.
#
# v2 therefore does two things differently:
#   1. every platform reproduces JOHN'S OWN validated arrangement verbatim --
#      constant (7,10) R0, receiver (9,10) R3, and a wire on the output port cell
#      (9,8), exactly as in `For Claude Signal Receiver.spz2bp` -- and only then
#      grows the chain north from (9,7), well clear of the 3x3 body at X8-10/Y9-11;
#   2. one chain per platform, four separate 1x1 islands, so no chain can ever reach
#      into another's receiver.
# And `validate_layout()` now refuses this class of bug at build time.
#
# SETTLED (John, VN-13q1/q2, 2026-09-04): the analyzer emits the **COLOUR on its LEFT
# output** and the **uncoloured SHAPE on its FORWARD output**. His reading -- "grey
# (uncoloured) out its top (**West**)" and "shape Wu------ to a display on the
# **North**" -- names the compass directions, and for an R3 (north-facing) analyzer
# west IS the left side. So docs/conventions.md was right all along and the earlier
# "colour out the top" reading was just the angled camera. Colour = LEFT.
QUADRANT_ROTATIONS = {
    "NE": [],
    "SE": ["VirtualRotatorCCWInternalVariant"],
    "SW": ["VirtualRotatorDefaultInternalVariant"] * 2,
    "NW": ["VirtualRotatorDefaultInternalVariant"],
}
GOAL_CHANNEL = 123
# John's own, from `For Claude Signal Receiver.spz2bp` -- reused verbatim, not chosen.
RX_CELL, RX_CHANNEL_CELL, RX_OUT_CELL = (9, 10), (7, 10), (9, 8)


def label_config(text):
    """A `LabelDefaultInternalVariant` config: u16 LE length + UTF-8 (conventions)."""
    raw = text.encode("utf-8")
    return config(base64.b64encode(len(raw).to_bytes(2, "little") + raw).decode("ascii"))


def check_label_encoding():
    """Self-check: reproduce John's 'Quaded Filter' label byte-for-byte."""
    isl = load_reference_island("Quaded Filter.spz2bp")
    lbl = [e for e in gv(isl["B"]["Entries"]) if e["T"] == "LabelDefaultInternalVariant"]
    assert len(lbl) == 1 and label_texts(isl) == ["Quaded Filter"]
    ours = label_config("Quaded Filter")["$value"]
    assert ours == lbl[0]["C"]["$value"], f"label encoding mismatch: {ours!r}"


def shape_signal_config(code):
    """A `ConstantSignal` shape config: tag 06 01, then 01 <len:u16 LE> <ASCII>."""
    raw = code.encode("ascii")
    return config(base64.b64encode(
        b"\x06\x01\x01" + len(raw).to_bytes(2, "little") + raw).decode("ascii"))


def check_shape_signal_encoding():
    """Self-check: reproduce John's `Su--WuCu` goal constant byte-for-byte."""
    isl = load_reference_island("For Claude Wiring Shapes.spz2bp")
    want = {e["C"]["$value"] for e in gv(isl["B"]["Entries"])
            if e["T"] == "ConstantSignalDefaultInternalVariant" and isinstance(e.get("C"), dict)}
    ours = shape_signal_config("Su--WuCu")["$value"]
    assert ours in want, f"shape signal encoding mismatch: ours {ours!r} not among John's"


def goal_receiver_config():
    """The `ControlledSignalReceiver` config, taken VERBATIM from John's minimal
    reference rather than hardcoded, with his L1 footprint outline asserted still
    present -- that ring is our only evidence for the 3x3 body."""
    isl = load_reference_island("For Claude Signal Receiver.spz2bp")
    rx = [e for e in gv(isl["B"]["Entries"])
          if e["T"] == "ControlledSignalReceiverInternalVariant"]
    assert len(rx) == 1 and (rx[0]["X"], rx[0]["Y"]) == RX_CELL, \
        "minimal receiver reference is not as described"
    ring = {(e["X"], e["Y"]) for e in gv(isl["B"]["Entries"]) if e["L"] == 1}
    assert ring == {(x, y) for x in range(7, 12) for y in range(8, 13)
                    if x in (7, 11) or y in (8, 12)}, \
        "the L1 footprint outline in For Claude Signal Receiver has changed"
    return rx[0]["C"]["$value"]


def colour_brain_platform(quadrant, labels=False):
    """One quadrant's colour chain on its own 1x1, flowing NORTH (everything R3).

    The first three buildings are John's validated receiver arrangement, cell for
    cell -- and cells (7,10)/(9,10)/(9,8)/(9,7)/(8,7)/(9,6) are EXACTLY `VN-13q2`,
    which John confirmed imports and runs. The only additions are this quadrant's
    rotators, which `VN-13p5` separately confirmed.

    `labels` defaults to FALSE: v2 was label-free nowhere and went missing, while
    every blueprint John has successfully imported from us either had no label or a
    single isolated one. Labels are not proven guilty -- `VN-13r1` tests them -- but
    they buy nothing here, since the blueprint's own NAME says which quadrant it is.
    """
    rx_x, rx_y = RX_CELL
    b = [be("ConstantSignalDefaultInternalVariant", X=RX_CHANNEL_CELL[0],
            Y=RX_CHANNEL_CELL[1], R=0, C=int_signal_config(GOAL_CHANNEL)),
         be("ControlledSignalReceiverInternalVariant", X=rx_x, Y=rx_y, R=3,
            C=config(goal_receiver_config())),
         be("WireDefaultForwardInternalVariant", X=RX_OUT_CELL[0], Y=RX_OUT_CELL[1], R=3)]
    y = RX_OUT_CELL[1] - 1
    for rot in QUADRANT_ROTATIONS[quadrant]:
        b.append(be(rot, X=rx_x, Y=y, R=3))
        y -= 1
    b.append(be("VirtualAnalyzerDefaultInternalVariant", X=rx_x, Y=y, R=3))
    # LEFT (west) = the COLOUR; FORWARD (north) = the uncoloured shape. Settled by
    # John's q1/q2 reading, which named the compass directions.
    b.append(be("DisplayDefaultInternalVariant", X=rx_x - 1, Y=y, R=2))
    b.append(be("DisplayDefaultInternalVariant", X=rx_x, Y=y - 1, R=3))
    if labels:
        b.append(be("LabelDefaultInternalVariant", X=rx_x - 2, Y=y, R=2,
                    C=label_config(quadrant + " colour")))
    return b


def _colour_brain_module(quadrant):
    def build():
        check_int_signal_encoding()
        return blueprint_islands([our_island("Foundation_1x1",
                                             colour_brain_platform(quadrant),
                                             where=f"VN-13 {quadrant}")])
    build.__doc__ = f"""VN-13 {quadrant}: the goal's {quadrant} quadrant colour, on one platform.

    `ControlledSignalReceiver`(ch 123) -> wire -> {len(QUADRANT_ROTATIONS[quadrant])}x rotator
    -> `VirtualAnalyzer`. West display = **colour**, north display = uncoloured shape.

    Shipped as four separate single-island blueprints rather than one four-platform
    one: the four-island version went missing from the folder and the cause is not
    yet pinned, whereas this layout is `VN-13q2` (confirmed working) plus rotators
    (confirmed by `VN-13p5`). Nothing here is unproven.
    """
    return build


# --- two probes: why did the four-island VN-13 go missing? -------------------
# `VN-13q2` (one island, no labels) imports. The four-island VN-13 v2 does not, and
# its NE platform is EXACTLY q2 plus three labels. Two candidates remain, and these
# separate them. Everything else in v2 was already proven piecewise.
def vn13r1_label_by_display():
    """q2 plus ONE label sitting next to a display -- the only thing v2's NE platform
    added. In John's library a `DisplayDefault` is adjacent to a label **0 times out
    of 3,089 labels**, which is suggestive but is only absence of evidence.
    Missing => labels (or labels beside displays) are the cause."""
    b = colour_brain_platform("NE", labels=True)
    return blueprint_islands([our_island("Foundation_1x1", b, where="VN-13r1")])


def vn13r2_two_islands():
    """Two label-free q2 platforms side by side. John's own library has blueprints
    with up to 88 `Foundation_1x1` islands, so multi-island is normal -- but we have
    never shipped one whose islands we authored ourselves rather than lifting from
    him. Missing => that is the cause."""
    return blueprint_islands([
        our_island("Foundation_1x1", colour_brain_platform("NE"), X=0, Y=0, where="r2 a"),
        our_island("Foundation_1x1", colour_brain_platform("SE"), X=1, Y=0, where="r2 b")])


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
    "VN-10 any shape maker lane fixed": vn10_any_shape_maker_lane_fixed,
    "VN-11a filter verbatim": vn11a_quaded_filter_verbatim,
    "VN-11 quaded filter goal driven": vn11_quaded_filter_goal_driven,
    "VN-12 MAM preset CuRuSuWu": vn12_mam_preset_curusuwu,
    "VN-12 MAM goal driven": vn12_mam_goal_driven,
    "VN-13 NE colour": _colour_brain_module("NE"),
    "VN-13 SE colour": _colour_brain_module("SE"),
    "VN-13 SW colour": _colour_brain_module("SW"),
    "VN-13 NW colour": _colour_brain_module("NW"),
    "VN-13r1 label by display": vn13r1_label_by_display,
    "VN-13r2 two islands": vn13r2_two_islands,
}

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "blueprints"
    os.makedirs(outdir, exist_ok=True)
    for name, fn in MODULES.items():
        code = encode_bp(5, check_configs(fn()))
        with open(os.path.join(outdir, name + ".spz2bp"), "w") as f:
            f.write(code)
        print("wrote", name, f"({len(code)} bytes)")
