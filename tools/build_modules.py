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
import base64, json, os, sys
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

# ---------------------------------------------------------------- FOOTPRINTS
# **DECLARED, NOT INFERRED (2026-09-05).** `debug.export-game-data` in the in-game
# console writes `basedata-v<n>/` next to the savegames, and `buildings.json` lists
# every internal variant with its exact `Tiles` -- the cells it occupies, including
# the Z extent. `gamedata/basedata-v1138/` is a copy, so the build does not depend on
# the game folder. This REPLACED a hand-maintained (w, h, anchor) table that we had
# reverse-engineered over several sessions; see docs/PLAYBOOK.md.
#
# What the real data corrected:
#   * the controlled-signal family is **3x3x3 = 27 cells** (Z 0..2), not the 3x3 = 9
#     we had. Our validator would happily have put something on top of a receiver.
#   * 13 multi-cell types we already place were modelled as 1x1, among them
#     `PainterDefaultInternalVariant` (2 cells) -- which Phase 2a is about to use --
#     `StackerStraightInternalVariant`, every `Lift*`, and the `Pipe*/Wire*Up*`
#     variants that span Z.
#   * all three `UNKNOWN_FOOTPRINT` entries became known, so that gate is gone.
# The one thing the export does NOT carry is wire ports (`BeltInputs`/`BeltOutputs`
# only), so the analyzer's shape/colour outputs remain settled by VN-13 in-game.
BASEDATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "gamedata", "basedata-v1138")


def load_building_tiles(path=None):
    """{internal_variant_id: [(dx, dy, dz), ...]} straight from the game's own export."""
    with open(os.path.join(path or BASEDATA_DIR, "buildings.json"), encoding="utf-8") as f:
        data = json.load(f)
    return {v["Id"]: [(c["X"], c["Y"], c["Z"]) for c in v["Tiles"]]
            for b in data for v in b.get("InternalVariants", [])}


BUILDING_TILES = load_building_tiles()

# Rotation of a footprint: R counts 90-degree steps and +X is East, +Y is SOUTH, so a
# visually clockwise step maps (dx, dy) -> (-dy, dx). FITTED, not assumed: scored
# against every building in the whole library (49 blueprints, 845 islands,
# 1,028,331 placed cells) -- this convention gives **0 collisions**, its inverse gives
# 7,784 and no rotation at all gives 11,945.
def rotate_offset(dx, dy, R):
    return [(dx, dy), (-dy, dx), (-dx, -dy), (dy, -dx)][R % 4]


# ...and a label needs ONE CELL OF MARGIN inside the buildable window: its 5-cell
# body must lie within [3,16] on a 1x1, never touching the outer ring at 2 or 17.
# The 5-cell length is now confirmed by buildings.json (Tiles X-2..2, Y0); the margin
# is NOT in the export and remains ours, from John's `For Claude Labels.spz2bp` plus
# the library census (label body cells use offsets [3..7, 12..16] and never 2 or 17,
# while every other building type uses the full 2..17).
#
# The two rules produce DIFFERENT symptoms, which is why this took so long to read:
#   * a label OVERLAPPING another building  -> the game discards the whole FILE
#     (never appears in the blueprint folder) -- p6, VN-13 v1, VN-13 v2, r1, s1, s2;
#   * a label only breaking the MARGIN      -> the file imports fine but FAILS TO
#     STAMP (red X) -- VN-13t1, whose one bad label at (4,14) spans X2..6.
LABEL_EDGE_MARGIN = 1


def footprint_cells(entry):
    """Every cell a building actually occupies -- not just the origin it records.

    Returns (x, y, L) triples; a building that spans levels (a lift, a controlled
    signal receiver) contributes cells on more than one L.
    """
    T, x, y, L = entry["T"], entry["X"], entry["Y"], entry.get("L", 0)
    tiles = BUILDING_TILES.get(T)
    if tiles is None:
        raise AssertionError(
            f"{T} at ({x},{y},L{L}): not in gamedata/basedata-v1138/buildings.json. "
            f"If the game has been updated, re-run `debug.export-game-data` in the "
            f"in-game console and refresh gamedata/.")
    R = entry.get("R", 0)
    out = []
    for dx, dy, dz in tiles:
        rx, ry = rotate_offset(dx, dy, R)
        out.append((x + rx, y + ry, L + dz))
    return out


def validate_layout(buildings, where="", foundation="Foundation_1x1", windows=None):
    """Refuse a layout that the game would reject or mis-stamp.

    Catches, for every building INCLUDING the hidden cells of multi-cell ones:
      * anything outside the buildable [2,17] window;
      * two buildings sharing a cell.
    Bounds: a 1x1 is checked against the [2,17] window; a multi-platform foundation
    passes `windows=` (one (x_lo, x_hi, y_lo, y_hi) per tile, see `Shell.windows()`)
    or gets collision checks only.
    """
    problems, occupied = [], {}
    if windows is None and foundation == "Foundation_1x1":
        windows = [(PLATFORM_MIN, PLATFORM_MAX, PLATFORM_MIN, PLATFORM_MAX)]
    for e in buildings:
        for cell in footprint_cells(e):
            x, y, L = cell
            m = LABEL_EDGE_MARGIN if e["T"] == "LabelDefaultInternalVariant" else 0
            inside = windows is None or any(x0 + m <= x <= x1 - m and y0 + m <= y <= y1 - m
                                            for x0, x1, y0, y1 in windows)
            if not inside:
                lo, hi = PLATFORM_MIN + m, PLATFORM_MAX - m
                why = ("-- a label body needs one cell of margin, so it must stay "
                       f"within [{lo},{hi}] of its tile" if m else
                       f"-- outside the buildable [{lo},{hi}] window of every tile")
                problems.append(
                    f"{e['T']} at ({e['X']},{e['Y']},L{e.get('L',0)}) occupies {cell} {why}")
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


def colour_brain_platform(quadrant, labels=True):
    """One quadrant's colour chain on its own 1x1, flowing NORTH (everything R3).

    The first three buildings are John's validated receiver arrangement, cell for
    cell -- and cells (7,10)/(9,10)/(9,8)/(9,7)/(8,7)/(9,6) are EXACTLY `VN-13q2`,
    which John confirmed imports and runs. The only additions are this quadrant's
    rotators, which `VN-13p5` separately confirmed.

    Labels are on and correctly placed. A label is 5 cells centred on its entry along
    its facing axis AND needs one cell of margin, so its body must stay within
    [3,16]. `VN-13t1` failed to stamp on exactly one label -- `(4,14)` R0, body X2-6,
    touching the outer ring -- while its `(5,7)` label (body X3-7) was fine. The title
    label now sits at `(10,13)` (body X8-12), well clear.
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
        # body X3-7, clear of the colour display at (8,y) and inside the [3,16] margin
        b.append(be("LabelDefaultInternalVariant", X=5, Y=y, R=0,
                    C=label_config("COLOUR ->")))
        # body X8-12 on an empty row -- (4,14) was what killed VN-13t1 (body X2-6)
        b.append(be("LabelDefaultInternalVariant", X=10, Y=13, R=0,
                    C=label_config("VN-13 " + quadrant)))
    return b


def _colour_brain_module(quadrant):
    def build():
        check_int_signal_encoding()
        # labels=False: these four are VALIDATED IN-GAME exactly as they are
        # (John, 2026-09-04). Do not add anything to them -- if labels are wanted,
        # that is what `VN-13t1` and `VN-13 colour brain all` are for.
        return blueprint_islands([our_island("Foundation_1x1",
                                             colour_brain_platform(quadrant, labels=False),
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


# --- what is left of the packaging puzzle ------------------------------------
# The label footprint explains p6, VN-13 v1, VN-13 v2, r1, s1 and s2: every one of
# them ran a label into a neighbouring building (and p6's also off the platform edge).
# `VN-13r2` -- two label-free islands, each of which imports standalone -- is NOT
# explained by it and is still open. These two separate the last question.
def vn13_colour_brain_all():
    """All four quadrants on one blueprint: four islands, labels placed legally.

    A clean test of the one thing still open. Each island is byte-for-byte one of the
    four `VN-13 * colour` platforms that John validated in-game, so if this fails the
    cause is multi-island blueprints whose islands WE author -- VN-07/VN-10/VN-12 are
    multi-island and validated, but every one of those lifts its islands from John's
    files rather than building them. If it works it replaces the four separate files."""
    check_int_signal_encoding()
    check_label_encoding()
    return blueprint_islands([
        our_island("Foundation_1x1", colour_brain_platform(q), X=n, Y=0, where=f"all {q}")
        for n, q in enumerate(("NE", "SE", "SW", "NW"))])


def vn13t2_one_island_labelled():
    """Control: one island, the confirmed NE chain plus two CORRECTLY placed labels.
    Separates "labels are fixed" from "multi-island works" -- if this stamps and
    `VN-13 colour brain all` does not, the remaining problem is multi-island."""
    check_label_encoding()
    return blueprint_islands([our_island("Foundation_1x1",
                                         colour_brain_platform("NE"), where="t2")])


# ---------------------------------------------------------------- VN-14
# THE BAND-MERGE AGGREGATOR, per unit. 16 filter band outputs -> 4 trunks, one per
# quadrant POSITION -> 4 outputs into the unit's single surviving stacker cluster.
# Paint goes on the trunks: each is uniform in colour by construction, which is the
# whole reason for merging by position rather than by lane.
#
# JOHN FIXED CLAUDE'S FIRST ATTEMPT (`For Claude Fixed Pipes.spz2bp`, 2026-09-04) and
# this generator reproduces his layout **cell for cell** -- the build asserts it, so
# his fix is now a regression test for ours (PLAYBOOK).
#
# THE BUG HE FOUND, and the rule that comes with it:
#   **A Z-change unit cannot also merge, and the cell DIRECTLY BELOW a lift must be
#   EMPTY.** Claude's first version spaced the trunks one column apart and dropped
#   `Lift1DownForward` at (8,y,Z1) straight onto the NW trunk running at (8,y,Z0).
#   In all 12 lifts of John's fixed version the Z0 cell under the lift is empty --
#   no exceptions. Spacing the trunks TWO apart is what buys that clearance: odd
#   columns carry trunks, even columns are free for lifts to land through.
#
# The three input patterns, all extracted, none invented:
#   nearest band, no hop          (8,y) Forward R2            -> (7,y) LeftFwdMerger R3
#   hop then MERGE                (8,y) Lift1UpForward R2
#                                 (7..tx+2, y, Z1) Forward R2
#                                 (tx+1, y, Z1) Lift1DownForward R2
#                                                              -> (tx,y) LeftFwdMerger R3
#   hop then START a trunk        (8,y) Lift1UpForward R2
#     (the southernmost group)    (7..tx+1, y, Z1) Forward R2
#                                 (tx, y, Z1) Lift1DownRight R2
#                                                              -> (tx,y-1) Forward R3
# `Lift1DownForward` lands one cell WEST at Z0; `Lift1DownRight` lands one cell NORTH
# at Z0 -- the "rotate the exit 90 degrees" John described. The Right variant is how a
# hopped stream starts a trunk without needing a separate turn, since a lift may turn
# but may not merge.
#
# LAYOUT (John's). Trunks on odd columns, lift clearance on even ones:
#   band  trunk X  merges at rows      starts at   exits west along  delivery X  out at
#   NW    7        -8, -2,  4          (7,10)      -12               -6          (-7,-8)
#   SW    5        -7, -1,  5          (5,10)      -11               -5          (-7,-7)
#   SE    3        -6,  0,  6          (3,11)      -10               -4          (-7,-6)
#   NE    1        -5,  1,  7          (1,12)       -9               -3          (-7,-5)
#
# Only the 12 input hops ever leave Z=0. Everything else is flat, because each band's
# northernmost source is one row south of the previous band's: trunk NW leaves west
# along row -12, north of where SW/SE/NE begin, and the delivery columns nest the same
# way -- the "outermost gets the longest run" trick John already uses to keep the lane
# cluster outputs from crossing.
#
# !! The row/column anchors above are JOHN'S, from his fixed blueprint. They sit 2
# rows south and 1 column east of where Claude derived the real machine's filter rows
# (lane blocks at r-1..r+2 for r = -9,-3,3,9, cluster inputs at X=-6 rows -10..-7).
# Translate before stamping, or confirm which anchoring is right.
AGG_INPUT_X = 8
AGG_TRUNK_X = (7, 5, 3, 1)              # by band offset: NW, SW, SE, NE
AGG_GROUP_BASE = (-8, -2, 4, 10)        # row of the NW band in each lane block
AGG_EXIT_ROW = (-12, -11, -10, -9)
AGG_DELIVERY_X = (-6, -5, -4, -3)
AGG_CLUSTER_ROW = (-8, -7, -6, -5)
AGG_CLUSTER_X = -7

SB_W = ("SpaceBelt_Forward", 2)
SB_N = ("SpaceBelt_Forward", 3)
SB_S = ("SpaceBelt_Forward", 1)
SB_MERGE_N = ("SpaceBelt_LeftFwdMerger", 3)
SB_UP = ("SpaceBelt_Lift1UpForward", 2)
SB_DOWN_FWD = ("SpaceBelt_Lift1DownForward", 2)
SB_DOWN_RIGHT = ("SpaceBelt_Lift1DownRight", 2)
SB_W_TO_N = ("SpaceBelt_RightTurn", 2)
SB_N_TO_W = ("SpaceBelt_LeftTurn", 3)
SB_W_TO_S = ("SpaceBelt_LeftTurn", 2)
SB_S_TO_W = ("SpaceBelt_RightTurn", 1)


def sb(piece, X, Y, Z=0):
    T, R = piece
    return island(T, X=X, Y=Y, Z=Z, R=R)


def _aggregator_islands():
    """John's fixed per-unit aggregator, generated from the pattern."""
    out = []
    tail_base = AGG_GROUP_BASE[-1]
    for k in range(4):
        tx, exit_row = AGG_TRUNK_X[k], AGG_EXIT_ROW[k]
        merge_rows = [b + k for b in AGG_GROUP_BASE[:-1]]
        tail_row = tail_base + k                       # this band's row in the last block
        trunk_start = tail_row if k == 0 else tail_row - 1

        # --- the four inputs
        for b in AGG_GROUP_BASE:
            y = b + k
            if k == 0:
                out.append(sb(SB_W, AGG_INPUT_X, y))
                continue
            out.append(sb(SB_UP, AGG_INPUT_X, y))
            last_hop = tx + 1 if y == tail_row else tx + 2
            for x in range(AGG_INPUT_X - 1, last_hop - 1, -1):
                out.append(sb(SB_W, x, y, Z=1))
            # a lift may TURN but may not MERGE, and needs the cell below it empty
            if y == tail_row:
                out.append(sb(SB_DOWN_RIGHT, tx, y, Z=1))      # lands (tx, y-1) at Z0
            else:
                out.append(sb(SB_DOWN_FWD, tx + 1, y, Z=1))    # lands (tx, y) at Z0

        # --- the trunk, north from where it starts up to its exit row
        for y in range(exit_row, trunk_start + 1):
            if y == exit_row:
                out.append(sb(SB_N_TO_W, tx, y))
            elif y in merge_rows:
                out.append(sb(SB_MERGE_N, tx, y))
            elif y == trunk_start and k == 0:
                out.append(sb(SB_W_TO_N, tx, y))               # unhopped band turns in
            else:
                out.append(sb(SB_N, tx, y))

        # --- west along the exit row, south down the delivery column, into the cluster
        dx, cy = AGG_DELIVERY_X[k], AGG_CLUSTER_ROW[k]
        for x in range(tx - 1, dx, -1):
            out.append(sb(SB_W, x, exit_row))
        out.append(sb(SB_W_TO_S, dx, exit_row))
        for y in range(exit_row + 1, cy):
            out.append(sb(SB_S, dx, y))
        out.append(sb(SB_S_TO_W, dx, cy))
        for x in range(dx - 1, AGG_CLUSTER_X - 1, -1):
            out.append(sb(SB_W, x, cy))
    return out


def check_aggregator_matches_john():
    """Assert our generated aggregator is John's `For Claude Fixed Pipes` cell for
    cell. He hand-fixed our first attempt, so this turns his fix into a regression
    test -- if either drifts, the build says exactly which cells differ."""
    ours = {(i["X"], i["Y"], i["Z"]): (i["T"], i["R"]) for i in _aggregator_islands()}
    johns = {(i["X"], i["Y"], i.get("Z", 0)): (i["T"], i.get("R", 0))
             for i in load_reference_islands("For Claude Fixed Pipes.spz2bp")}
    if ours != johns:
        diff = []
        for cell in sorted(set(ours) | set(johns)):
            if ours.get(cell) != johns.get(cell):
                diff.append(f"{cell}: ours={ours.get(cell)} johns={johns.get(cell)}")
        raise AssertionError(f"aggregator differs from John's fix in {len(diff)} cells:\n  "
                             + "\n  ".join(diff[:25]))


def vn14_band_merge_aggregator():
    """VN-14: the per-unit band-merge aggregator, space-belt only.

    16 filter band outputs -> 4 per-position trunks -> 4 streams into the surviving
    stacker cluster. Insert `Paint 4 Filter` -> `Painter` anywhere on a trunk's
    straight run for Phase 2a.
    """
    check_aggregator_matches_john()
    out = _aggregator_islands()
    seen = {}
    for i in out:
        key = (i["X"], i["Y"], i["Z"])
        assert key not in seen, f"island collision at {key}: {i['T']} vs {seen[key]}"
        seen[key] = i["T"]
    for i in out:
        if "Lift1Down" in i["T"] or "Lift1Up" in i["T"]:
            other = (i["X"], i["Y"], 1 - i["Z"])
            assert other not in seen, (
                f"{i['T']} at ({i['X']},{i['Y']},Z{i['Z']}) has {seen[other]} directly "
                f"below/above it -- a Z-change unit needs that cell clear")
    return blueprint_islands(out)



# ---------------------------------------------------------------- VN-20
# NE-QUADRANT ISOLATOR at full belt: `Foundation_1x4`, east-in / west-out, 4 bands x
# 12 lanes = 48 lanes -- the same shell as John's `Quaded Filter` (island R=1, ports
# at local X=17 / X=2, R2, lane Y = 20k-12..20k-9), copied from it, not chosen.
# The layout inside is Claude's own, at John's request (2026-09-06).
#
# Shape math per item (cut plane is world-vertical; HalfDestroy keeps world-EAST):
#   {NE,SE,SW,NW} -HD-> {NE,SE} -Rot90CW-> {SE,SW} -HD-> {SE} -Rot90CCW-> {NE}
# i.e. the original NE quadrant, back in its original position.
#
# Throughput -- MEASURED BY JOHN IN-GAME (2026-09-06, v1 rejected): a Half Destroyer
# keeps up with only ONE THIRD of a belt lane, so it takes THREE in parallel per lane;
# a one-quad Rotator keeps up with half a lane (John's `Clockwise` spends two per
# lane). v1 split each lane in two and bottlenecked on the cutters. v2 splits every
# lane THREE ways into three parallel HD->CW->HD->CCW chains and merges back, so each
# operator sees a third of a lane: enough for the cutter, over-provisioned for the
# rotators. 48 operators per floor, 144 per band, 576 on the platform. RULE, from
# John: for every building placed, know its throughput and put as many in parallel
# as the lane needs.
#
# Designed in the 1x1 bus frame (south-in Y17 / north-out Y2, lanes X8-11, R3). The
# four lanes fan out to centre columns 5, 8, 11, 14 (rows Y16/Y15), each splits
# 1->2->3 into columns c-1, c, c+1 (rows Y14/Y13), the chains run four cells straight,
# two mergers (Y8, Y7) rejoin the lane, and rows Y6/Y5 bring it back to its home
# column. Then rotated one step CCW into the Quaded Filter frame and repeated on
# L0-2 and on the four rows. `trace_lanes()` walks every lane through the finished
# geometry; it, not this comment, is the verdict.
FWD = "BeltDefaultForwardInternalVariant"
LT = "BeltDefaultLeftInternalVariant"            # left turn: enters heading R, exits R-1
RT = "BeltDefaultLeftInternalVariantMirrored"    # right turn: enters heading R, exits R+1
SPL, SPR = "Splitter1To2LInternalVariant", "Splitter1To2LInternalVariantMirrored"
MGL, MGR = "Merger2To1LInternalVariant", "Merger2To1LInternalVariantMirrored"
HD, CW, CCW = "CutterHalfInternalVariant", "RotatorOneQuadInternalVariant", "RotatorOneQuadCCWInternalVariant"
RX, TX = "BeltPortReceiverInternalVariant", "BeltPortSenderInternalVariant"
SP3, MG3 = "Splitter1To3InternalVariant", "Merger3To1InternalVariant"
NE_OPS = [HD, CW, HD, CCW]


# The hand-placed `_ne_isolator_floor()` / `_bus_to_quaded_filter_frame()` that
# built VN-20 v2 are gone (2026-09-06): the layout compiler below produces the same
# cells from a spec, and `blueprints/reference/VN-20 v2 validated.spz2bp` is the
# frozen regression fixture. See `docs/history/` for the hand-placed version.


# ---------------------------------------------------------------- belt tracing
def load_building_io(path=None):
    """{variant: (inputs, outputs)} as (dx, dy, dz, face) from the game's export."""
    with open(os.path.join(path or BASEDATA_DIR, "buildings.json"), encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for bd in data:
        for v in bd.get("InternalVariants", []):
            conv = lambda lst: [(p["Position_L"]["X"], p["Position_L"]["Y"],
                                 p["Position_L"]["Z"], p["Direction_L"]) for p in lst]
            out[v["Id"]] = (conv(v.get("BeltInputs", [])), conv(v.get("BeltOutputs", [])))
    return out


BUILDING_IO = load_building_io()
FACE = [(1, 0), (0, 1), (-1, 0), (0, -1)]       # local direction index -> local vector


def trace_lanes(buildings, expect_ops, is_in, is_out, lane_key, where="", quiet=False):
    """Walk every lane from its edge receiver to an edge sender; print a verdict.

    Every path must (1) reach a sender on the platform's out edge, on the SAME row,
    lane Y and floor it entered on (lane-preserving), (2) pass exactly `expect_ops`
    in order, and (3) between them all paths must cover every operator cell.
    Splitters fork the walk; mergers just join it. A sender that is NOT on the out
    edge is a belt launcher: the walk jumps to the first catcher 1-4 cells ahead in
    its column (conventions: "Belt launchers / catchers"). Raises on the first
    violation. `is_in(e)` / `is_out(e)` pick the edge ports; `lane_key(e)` is what a
    lane must preserve between them, e.g. `lambda e: (e["Y"], e["L"])`.
    """
    by_cell, ops_all = {}, set()
    for e in buildings:
        for cell in footprint_cells(e):
            by_cell[cell] = e
        if e["T"] in expect_ops:
            ops_all.add((e["X"], e["Y"], e["L"]))

    def ports(e, which):
        ins, outs = BUILDING_IO[e["T"]]
        res = []
        for dx, dy, dz, d in (ins if which == "in" else outs):
            rx, ry = rotate_offset(dx, dy, e["R"])
            fx, fy = rotate_offset(*FACE[d], e["R"])
            cell = (e["X"] + rx, e["Y"] + ry, e["L"] + dz)
            res.append((cell, (cell[0] + fx, cell[1] + fy, cell[2])))
        return res

    receivers = [e for e in buildings if e["T"] == RX and is_in(e)]
    seen_ops, n_paths = set(), 0
    for r in receivers:
        stack = [(r, [], {(r["X"], r["Y"], r["L"])})]
        while stack:
            e, path, visited = stack.pop()
            if e["T"] == TX and not is_out(e):            # a launcher: hop 1-4 cells
                fx, fy = rotate_offset(1, 0, e["R"])
                hop = [by_cell.get((e["X"] + fx * n, e["Y"] + fy * n, e["L"])) for n in (2, 3, 4, 5)]
                hop = [h for h in hop if h is not None and h["T"] == RX]
                assert hop, f"{where}: launcher at ({e['X']},{e['Y']},L{e['L']}) has no catcher"
                stack.append((hop[0], path, visited | {(hop[0]["X"], hop[0]["Y"], hop[0]["L"])}))
                continue
            if e["T"] == TX:
                assert lane_key(e) == lane_key(r), (
                    f"{where}: lane from ({r['X']},{r['Y']},L{r['L']}) ends at "
                    f"({e['X']},{e['Y']},L{e['L']})")
                assert [t for _, t in path] == expect_ops, (
                    f"{where}: lane from ({r['X']},{r['Y']},L{r['L']}) passes "
                    f"{[t[:12] for _, t in path]}")
                seen_ops.update(c for c, _ in path)
                n_paths += 1
                continue
            nxt = []
            for cell, ahead in ports(e, "out"):
                e2 = by_cell.get(ahead)
                if e2 is not None and any(a == cell for _, a in ports(e2, "in")):
                    nxt.append(e2)
            assert nxt, f"{where}: dead end after {e['T']} at ({e['X']},{e['Y']},L{e['L']})"
            for e2 in nxt:
                key = (e2["X"], e2["Y"], e2["L"])
                assert key not in visited, f"{where}: loop at {key}"
                p2 = path + ([(key, e2["T"])] if e2["T"] in expect_ops else [])
                stack.append((e2, p2, visited | {key}))
    assert seen_ops == ops_all, f"{where}: {len(ops_all - seen_ops)} operator cells never visited"
    if not quiet:
        print(f"TRACE {where}: PASS {len(receivers)} lanes, {n_paths} paths, "
              f"{len(ops_all)} operators all on-path, every lane "
              f"{'>'.join(t[:6] for t in expect_ops)}")
    return len(receivers), len(ops_all)


# ---------------------------------------------------------------- layout compiler
# DIRECTIVE step 2 (2026-09-06). A module is a SPEC; this code turns it into cells.
#
#   Module("VN-20 ...", shell=QUADED_FILTER_SHELL, per_lane=[HD, CW, HD, CCW])
#
# Everything is designed in ONE frame, the 1x1 "bus" frame (south-in Y17, north-out
# Y2, lanes X8-11, flow north = R3, floors L0-2); the Shell says how many copies of
# that 20x20 tile the foundation holds and how each is rotated/offset into the
# platform's local frame. No module function carries a coordinate transform.
#
# Fan-out N per lane = max(per_lane) over the chain's operators, read from
# gamedata/rates.json (rule 6: facts before builds). The butterfly is the one
# VALIDATED IN-GAME as VN-20 v2: each lane walks to the entry column of a group of
# N adjacent columns, splits 1->2(->3) through Splitter1To2L(+Mirrored), runs N
# parallel operator chains, rejoins through Merger2To1L(+Mirrored), and walks home.
# Lane-to-group walks share rows greedily (disjoint spans on one row), which is
# exactly the outer-lanes-first arrangement of VN-20 v2 and John's `Clockwise`.
#
# The compiler is not trusted: every compile runs validate_layout (bounds per tile,
# collisions) and trace_lanes (the game's own BeltInputs/BeltOutputs) and prints
# one verdict line. `check_vn20_regression()` diffs the compiled VN-20 cell-for-cell
# against the frozen `blueprints/reference/VN-20 v2 validated.spz2bp`.
RATES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "gamedata", "rates.json")
with open(RATES_PATH, encoding="utf-8") as _f:
    RATES = json.load(_f)

BUS_LANES = (8, 9, 10, 11)          # home columns in the bus frame
BUS_IN_Y, BUS_OUT_Y = 17, 2          # receiver row / sender row
FLOORS = (0, 1, 2)
LABEL = "LabelDefaultInternalVariant"


class Shell:
    """How a foundation is tiled with bus-frame 20x20 tiles.

    `tiles` = [(ccw_steps, dx, dy), ...]: each tile is the bus frame rotated
    `ccw_steps` quarter-turns counter-clockwise about the 1x1 centre, then shifted.
    `label_at` is the (x, y) of a per-tile label in the PLATFORM frame (before dy).
    """
    def __init__(self, name, foundation, island_R, tiles, is_in, is_out, lane_key, label_at=None):
        self.name, self.foundation, self.island_R = name, foundation, island_R
        self.tiles, self.is_in, self.is_out, self.lane_key = tiles, is_in, is_out, lane_key
        self.label_at = label_at

    @staticmethod
    def _ccw(x, y, R):
        return y, 19 - x, (R + 3) % 4

    def place(self, x, y, R, tile):
        steps, dx, dy = tile
        for _ in range(steps):
            x, y, R = self._ccw(x, y, R)
        return x + dx, y + dy, R

    def windows(self):
        """Buildable rectangles (x_lo, x_hi, y_lo, y_hi), one per tile."""
        return [(PLATFORM_MIN + dx, PLATFORM_MAX + dx, PLATFORM_MIN + dy, PLATFORM_MAX + dy)
                for _, dx, dy in self.tiles]


# 1x1 in the plain bus frame. VN-02/VN-03 sit at island R=2 so they snap into John's
# bus the way his `Clockwise` does; the R is the island's, the cells are unchanged.
def bus_1x1(island_R=2):
    return Shell("bus 1x1", "Foundation_1x1", island_R, tiles=[(0, 0, 0)],
                 is_in=lambda e: e["Y"] == BUS_IN_Y, is_out=lambda e: e["Y"] == BUS_OUT_Y,
                 lane_key=lambda e: (e["X"], e["L"]))


# John's `Quaded Filter` shell: Foundation_1x4 at island R=1, four rows 20 apart, EAST
# in at local X17 and WEST out at X2 -- one CCW step of the bus frame per row.
QUADED_FILTER_SHELL = Shell(
    "Quaded Filter 1x4", "Foundation_1x4", 1, tiles=[(1, 0, 20 * k - 20) for k in range(4)],
    is_in=lambda e: e["X"] == 17, is_out=lambda e: e["X"] == 2,
    lane_key=lambda e: (e["Y"], e["L"]), label_at=(6, 16))


class Module:
    """`fan`: "sp3" (default; John's Splitter1To3/Merger3To1 butterfly, 2026-09-06) or
    "cascade" (the 1->2->3 splitter cascade of VN-20 v2). `launchers`: replace the
    home straight after the return row with launcher->catcher hops (speed only)."""
    def __init__(self, name, shell, per_lane, labels=None, fan="sp3", launchers=True, N=None):
        self.name, self.shell, self.per_lane, self.labels = name, shell, list(per_lane), labels
        self.fan, self.launchers = fan, launchers
        # N: fan-out OVERRIDE, for experiment.py's deliberately-wrong variants only.
        # Production modules leave it None and take the measured per_lane from rates.json.
        self.N = N


def op_row(T):
    """The rates.json row for an operator, checked to be a 1-in/1-out lane operator."""
    row = RATES.get(T)
    assert row is not None, f"{T}: no row in gamedata/rates.json (rule 6: facts first)"
    assert row.get("per_lane"), f"{T}: rates.json has no per_lane -- ask John / the wiki"
    assert len(row["inputs"]) == 1 and len(row["outputs"]) == 1 and row["footprint"] == "1x1x1", (
        f"{T}: {row['footprint']} with {len(row['inputs'])} in / {len(row['outputs'])} out -- "
        f"the compiler only chains 1x1 one-in/one-out operators; extend it (DIRECTIVE 1)")
    return row


def _belt_path(points, heading, exit_heading=3):
    """Belt cells along a rectilinear polyline of waypoints, entered on `heading` and
    leaving the last waypoint on `exit_heading`.

    Returns (x, y, R, T) for every cell from the first waypoint to the last, INCLUDING
    both ends. Corners get a Left/Right turn piece with R = incoming heading; straights
    get Forward. Consecutive waypoints share x or y.
    """
    def step(a, b):
        dx, dy = (b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1])
        return FACE.index((dx, dy))

    def piece(h, h2):
        if h2 == h:
            return FWD
        if h2 == (h - 1) % 4:
            return LT
        assert h2 == (h + 1) % 4, f"U-turn {h}->{h2}"
        return RT
    cells, h = [], heading
    for i, p in enumerate(points):
        if i + 1 == len(points):
            cells.append((p[0], p[1], h, piece(h, exit_heading)))
            break
        h2 = step(p, points[i + 1])
        cells.append((p[0], p[1], h, piece(h, h2)))
        x, y = p[0] + FACE[h2][0], p[1] + FACE[h2][1]
        while (x, y) != tuple(points[i + 1]):
            cells.append((x, y, h2, FWD))
            x, y = x + FACE[h2][0], y + FACE[h2][1]
        h = h2
    return cells


def _assign_rows(spans, first_row, direction):
    """Greedy row sharing: each (lane, lo, hi) span takes the first row (from
    `first_row`, stepping `direction`) where it overlaps no span already there."""
    rows, out = [], {}
    for lane, lo, hi in spans:
        for i, taken in enumerate(rows):
            if all(hi < a or lo > b for a, b in taken):
                taken.append((lo, hi))
                out[lane] = first_row + direction * i
                break
        else:
            rows.append([(lo, hi)])
            out[lane] = first_row + direction * (len(rows) - 1)
    return out, len(rows)


def _dedupe(pts):
    return [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]


def compile_floor(ops, N, fan="sp3", launchers=False):
    """One floor of a 4-lane bus tile: (x, y, R, T) cells, flow north.

    Two 1->3 butterflies are known, both validated in-game:
      "cascade" -- VN-20 v2: every lane walks to its group's CENTRE column, splits
                   1->2->3 through two Splitter1To2L rows, chains staggered by one row,
                   two Merger2To1L rows. K+4 rows, two lane-walk rows each way.
      "sp3"     -- John's VN-02 variant (`For Claude VN-02 1to3 splitter.spz2bp`): the
                   outer lanes walk to a centre column and use Splitter1To3/Merger3To1
                   (the game balances 1/3 per output); the inner lanes enter their group
                   at its EDGE column and fan sideways through a Splitter1To2L pair, so
                   they never leave their home column. All chains aligned. K+2 rows,
                   one lane-walk row each way. 240 vs 336 buildings for one cutter.
    """
    K = len(ops)
    assert 1 <= N <= 3, f"fan-out {N} per lane: the compiler knows 1->2 and 1->3 butterflies only"
    assert fan in ("sp3", "cascade"), fan
    x0 = 10 - 2 * N                                   # 4 groups of N columns, centred
    groups = [list(range(x0 + N * i, x0 + N * (i + 1))) for i in range(4)]
    # entry column of each group. N=2: the inner column (west half splits west, east
    # half splits east). N=3 cascade: the centre. N=3 sp3: centre for the outer groups,
    # the home-side edge for the inner ones (lane 9 -> column 9, lane 10 -> column 10).
    if N == 3 and fan == "sp3":
        entry = [groups[0][1], groups[1][2], groups[2][0], groups[3][1]]
    else:
        entry = [g[1] if N == 3 else (g[-1] if i < 2 else g[0]) if N == 2 else g[0]
                 for i, g in enumerate(groups)]
    cells = []

    # --- distribution: home column -> entry column, rows just below the receiver
    spans = sorted(((h, min(h, c), max(h, c)) for h, c in zip(BUS_LANES, entry)),
                   key=lambda s: -(s[2] - s[1]))
    d_rows, D = _assign_rows([s for s in spans if s[1] != s[2]], BUS_IN_Y - 1, -1)
    y_s = BUS_IN_Y - 1 - D                            # first butterfly row
    for h, c in zip(BUS_LANES, entry):
        cells.append((h, BUS_IN_Y, 3, RX))
        if D:
            r = d_rows.get(h)
            pts = [(h, BUS_IN_Y - 1), (h, r), (c, r), (c, y_s + 1)] if r is not None \
                else [(h, BUS_IN_Y - 1), (h, y_s + 1)]
            cells += _belt_path(_dedupe(pts), 3)

    # --- butterfly + chains + merge, per group
    def chain(x, y_top):
        cells.extend((x, y_top - i, 3, t) for i, t in enumerate(ops))

    y_m = None
    for i, c in enumerate(entry):
        if N == 1:
            chain(c, y_s)
            y_m = y_s - K
        elif N == 2:
            mirror = i >= 2
            side = c + 1 if mirror else c - 1
            cells += [(c, y_s, 3, SPR if mirror else SPL),
                      (side, y_s, 0 if mirror else 2, LT if mirror else RT)]
            chain(side, y_s - 1)
            chain(c, y_s - 1)
            e = y_s - K
            cells += [(side, e - 1, 3, LT if mirror else RT), (c, e - 1, 3, MGR if mirror else MGL)]
            y_m = e - 2
        elif fan == "cascade":
            cells += [(c, y_s, 3, SPL), (c - 1, y_s, 2, RT), (c, y_s - 1, 3, SPR), (c + 1, y_s - 1, 0, LT)]
            chain(c - 1, y_s - 1)
            chain(c, y_s - 2)
            chain(c + 1, y_s - 2)
            e = y_s - K                               # last op row of the c-1 chain
            cells += [(c - 1, e - 1, 3, FWD), (c - 1, e - 2, 3, RT), (c, e - 2, 3, MGL),
                      (c + 1, e - 2, 3, FWD), (c + 1, e - 3, 3, LT), (c, e - 3, 3, MGR)]
            y_m = e - 4
        else:                                         # sp3: chains aligned at y_s-1
            g0, g1, g2 = groups[i]
            e = y_s - K - 1                           # merge row
            if c == g1:                               # centre entry: 1->3 in one cell
                cells += [(c, y_s, 3, SP3), (g0, y_s, 2, RT), (g2, y_s, 0, LT),
                          (g0, e, 3, RT), (c, e, 3, MG3), (g2, e, 3, LT)]
            elif c == g2:                             # east-edge entry, fan west
                cells += [(g2, y_s, 3, SPL), (g1, y_s, 2, SPR), (g0, y_s, 2, RT),
                          (g0, e, 3, RT), (g1, e, 0, MGR), (g2, e, 3, MGL)]
            else:                                     # west-edge entry, fan east
                cells += [(g0, y_s, 3, SPR), (g1, y_s, 0, SPL), (g2, y_s, 0, LT),
                          (g0, e, 3, MGR), (g1, e, 2, MGL), (g2, e, 3, LT)]
            for x in (g0, g1, g2):
                chain(x, y_s - 1)
            y_m = e - 1

    # --- return: entry column -> home column, then straight to the sender
    spans = sorted(((h, min(h, c), max(h, c)) for h, c in zip(BUS_LANES, entry)),
                   key=lambda s: (s[2] - s[1]))
    r_rows, Dr = _assign_rows([s for s in spans if s[1] != s[2]], y_m, -1)
    assert y_m - Dr >= BUS_OUT_Y, f"{K} ops x{N} do not fit the tile: return rows reach {y_m - Dr}"
    for h, c in zip(BUS_LANES, entry):
        r = r_rows.get(h)
        pts = [(c, y_m), (c, r), (h, r), (h, BUS_OUT_Y + 1)] if r is not None \
            else [(c, y_m), (h, BUS_OUT_Y + 1)]
        cells += _belt_path(_dedupe(pts), 3)
        cells.append((h, BUS_OUT_Y, 3, TX))
    if launchers:
        cells = _launch_home_straights(cells, y_m - Dr)
    return cells


LAUNCH_GAP_MAX = 4      # conventions: a launcher throws 1-4 tiles to the next catcher


def _launch_home_straights(cells, y_top):
    """Replace each lane's straight run from `y_top` down to row 3 (all Forward R3
    cells in the home column) with launcher->catcher hops, greedy MAX gap from the
    exit end -- John's chunking in `For Claude VN-02 1to3 splitter`: rows 11..3 become
    sender 11 / catcher 9, sender 8 / catcher 3. Runs under 3 cells stay belts."""
    by = {(x, y): i for i, (x, y, R, T) in enumerate(cells)}
    drop, add = set(), []
    for h in BUS_LANES:
        run = [y for y in range(y_top, BUS_OUT_Y, -1)
               if (h, y) in by and cells[by[(h, y)]][2:] == (3, FWD)]
        if len(run) < 3 or run != list(range(y_top, y_top - len(run), -1)):
            continue
        lo, hi = run[-1], run[0]
        while hi - lo + 1 >= 3:
            snd = min(lo + LAUNCH_GAP_MAX + 1, hi)
            drop.update(by[(h, y)] for y in range(lo, snd + 1))
            add += [(h, lo, 3, RX), (h, snd, 3, TX)]
            lo = snd + 1
    return [c for i, c in enumerate(cells) if i not in drop] + add


def compile_module(m):
    """Spec -> validated, traced building list. Prints the verdict; raises on FAIL."""
    rows = [op_row(T) for T in m.per_lane]
    N = m.N or max(r["per_lane"] for r in rows)
    facts = ("FORCED N=%d; " % N if m.N else "") + " ".join(f"{T.replace('InternalVariant', '')}({r['per_lane']}/lane,{r['source']})"
                     for T, r in zip(m.per_lane, rows))
    floor = compile_floor(m.per_lane, N, fan=m.fan, launchers=m.launchers)
    sh, b = m.shell, []
    for k, tile in enumerate(sh.tiles):
        for L in FLOORS:
            for x, y, R, T in floor:
                lx, ly, lR = sh.place(x, y, R, tile)
                b.append(be(T, X=lx, Y=ly, L=L, R=lR))
        if m.labels:
            assert sh.label_at, f"{sh.name} has no label anchor"
            text = m.labels[k] if isinstance(m.labels, (list, tuple)) else m.labels
            b.append(be(LABEL, X=sh.label_at[0], Y=sh.label_at[1] + tile[2], L=0, R=0,
                        C=label_config(text)))
    validate_layout(b, where=m.name, foundation=sh.foundation, windows=sh.windows())
    n_lanes, n_ops = trace_lanes(b, m.per_lane, is_in=sh.is_in, is_out=sh.is_out,
                                 lane_key=sh.lane_key, where=m.name, quiet=True)
    lanes = len(BUS_LANES) * len(FLOORS) * len(sh.tiles)
    want = (lanes, lanes * N * len(m.per_lane))
    assert (n_lanes, n_ops) == want, f"{m.name}: traced {(n_lanes, n_ops)}, spec says {want}"
    print(f"COMPILE {m.name}: {facts} -> fan {N}; {len(b)} buildings; "
          f"TRACE PASS {n_lanes} lanes, {n_ops} operators")
    return b


def build(m):
    return blueprint_islands([our_island(m.shell.foundation, compile_module(m),
                                         R=m.shell.island_R, where=m.name)])


# ---------------------------------------------------------------- compiled modules
# VN-20: full belt in (east), only the NE quadrant out (west), Quaded Filter shell.
# Shape math per item (cut plane is world-vertical; HalfDestroy keeps world-EAST):
#   {NE,SE,SW,NW} -HD-> {NE,SE} -Rot90CW-> {SE,SW} -HD-> {SE} -Rot90CCW-> {NE}
VN20 = Module("VN-20 NE quadrant full belt", QUADED_FILTER_SHELL, [HD, CW, HD, CCW],
              labels=["VN-20 NE only  E in / W out"] + ["NE only"] * 3)
# The in-game-validated v2 layout, kept compilable as the regression fixture's spec.
VN20_V2 = Module(VN20.name, VN20.shell, VN20.per_lane, labels=VN20.labels,
                 fan="cascade", launchers=False)
# VN-02c / VN-03c: the 12-lane half-destroy and rotate-CW stages compiled from one
# operator each. John's hand-tuned VN-02/VN-03 (launcher runs, 2 cutters/lane) stay as
# the in-game A/B reference; the compiled ones fan by the measured rate (HD 3, Rot 2).
# The known-bad two-per-lane VN-20 (v1 starved in-game). NOT in MODULES: it exists so
# tools/experiment.py has a build that must FAIL the throughput check.
VN20_V1 = Module(VN20.name + " v1 2perlane", VN20.shell, VN20.per_lane, labels=VN20.labels, N=2)
VN02C = Module("VN-02c half-destroy 12lane compiled", bus_1x1(2), [HD])
VN03C = Module("VN-03c rotate90CW 12lane compiled", bus_1x1(2), [CW])


REGRESSIONS = [
    # in-game-validated blueprint            spec that must reproduce it cell for cell
    ("VN-20 v2 validated.spz2bp",            VN20_V2),   # John, 2026-09-06 afternoon
    ("For Claude VN-02 1to3 splitter.spz2bp", VN02C),    # John's own layout, same day
    ("VN-20 v3 validated.spz2bp",            VN20),      # John, 2026-09-06 night: "working nicely"
    ("VN-03c validated.spz2bp",              VN03C),     # John, 2026-09-06 night: "working nicely"
]


def check_regressions():
    """Every fixture is an in-game-validated layout; the compiler must reproduce each
    CELL FOR CELL from its spec. A fixture that stops matching is a compiler change
    that needs a new in-game test, not a tolerance."""
    def key(e):
        return (e["X"], e["Y"], e["L"], e["R"], e["T"], json.dumps(e.get("C"), sort_keys=True))
    for fixture, m in REGRESSIONS:
        ref = load_reference_island(fixture)
        want = sorted(key(e) for e in gv(ref["B"]["Entries"]))
        got = sorted(key(e) for e in compile_module(m))
        assert (ref["T"], ref["R"]) == (m.shell.foundation, m.shell.island_R), (ref["T"], ref["R"])
        assert got == want, (f"REGRESSION {fixture}: FAIL {len(set(want) - set(got))} cells "
                             f"missing, {len(set(got) - set(want))} extra")
        print(f"REGRESSION {fixture}: PASS {len(got)} cells identical")


check_vn20_regression = check_regressions


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
    "VN-13 colour brain all": vn13_colour_brain_all,
    "VN-13t2 one island labelled": vn13t2_one_island_labelled,
    "VN-14 band merge aggregator": vn14_band_merge_aggregator,
    "VN-20 NE quadrant full belt": lambda: build(VN20),
    "VN-02c half-destroy 12lane compiled": lambda: build(VN02C),
    "VN-03c rotate90CW 12lane compiled": lambda: build(VN03C),
}

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "blueprints"
    check_regressions()
    os.makedirs(outdir, exist_ok=True)
    for name, fn in MODULES.items():
        code = encode_bp(5, check_configs(fn()))
        with open(os.path.join(outdir, name + ".spz2bp"), "w") as f:
            f.write(code)
        print("wrote", name, f"({len(code)} bytes)")
