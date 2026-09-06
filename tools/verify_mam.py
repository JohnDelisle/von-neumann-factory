#!/usr/bin/env python3
"""
verify_mam.py -- structural audit of a MAM assembly blueprint.

Run:  python tools/verify_mam.py "blueprints/reference/<file>.spz2bp" [...]

Checks the things that fail SILENTLY in-game -- a stamped machine looks fine and
just produces subtly wrong shapes:

  1. Every `Fancy A+B Side Overflow` unit is the LANE-FIXED version, cell for cell.
     A pre-fix copy stamped in by accident reintroduces the inner/outer lane-swap
     bug (docs/conventions.md).
  2. Every `Quaded Filter` is identical to the goal-driven reference, so no lane is
     running a stale preset-driven copy.
  3. Every Goal Receiver channel constant agrees -- a single mismatched channel
     leaves one lane deaf and silently starves a quadrant.
  4. Component ratios are self-consistent (one Demuxer and one Quad Splitter per
     filter; whole numbers of stacker clusters).
  5. No malformed building configs (the `$type` trap that makes the game discard
     the whole file).

Exit code 0 = all good, 1 = at least one FAIL.
"""
import base64, collections, os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
from shapez_bp import decode_bp
import build_modules as bm
import say

gv = bm.gv


def cells(island):
    return {(e["X"], e["Y"], e["L"]): (e["T"], e["R"]) for e in gv(island["B"]["Entries"])}


def int_signals(island):
    """Every integer ConstantSignal value on an island (channel numbers)."""
    out = []
    for e in gv(island["B"]["Entries"]):
        if e["T"] == "ConstantSignalDefaultInternalVariant" and e.get("C"):
            raw = base64.b64decode(e["C"]["$value"])
            if raw[:1] == b"\x03" and len(raw) >= 5:
                out.append(int.from_bytes(raw[1:5], "little"))
    return out


# ------------------------------------------------- island footprints & space belts
# EXTRACTED 2026-09-05, not guessed. A multi-tile foundation records only its ORIGIN
# tile in the island list, exactly like a multi-cell BUILDING records only its origin
# cell (conventions.md). The footprint below was recovered from each island's own
# building coordinates: a platform tile is 20 units of building space, so
# `floor(min/max building X or Y / 20)` gives the tile span the island really covers.
# Measured over both MAMs (1,707 islands); every span came out an exact multiple.
ISLAND_FOOTPRINT = {
    ("Foundation_1x1", 1): [(0, 0)],
    ("Foundation_1x1", 3): [(0, 0)],
    ("Foundation_1x4", 1): [(0, dy) for dy in range(-1, 3)],
    ("Foundation_2x2", 3): [(dx, dy) for dx in (0, 1) for dy in (-1, 0)],
    ("Foundation_2x2_Flipped", 1): [(dx, dy) for dx in (0, 1) for dy in (0, 1)],
    ("Foundation_2x4", 3): [(dx, dy) for dx in (0, 1) for dy in range(-2, 2)],
    ("Foundation_2x4_Flipped", 1): [(dx, dy) for dx in (0, 1) for dy in range(-1, 3)],
    # Prefab layouts carry no buildings of their own, so the span trick above cannot
    # measure them. This one is pinned by ELIMINATION instead: each lane's first space
    # belt sits at (33,y) and is fed from the east, cell (34,y) holds no island of its
    # own, and islands may not overlap -- so the unloader at (35,y) must cover (34,y)
    # and cannot reach (33,y). Two tiles wide, one tall.
    ("Layout_TrainUnloader_Shapes_Flipped", 1): [(0, 0), (-1, 0)],
}

# Space-belt direction model. R indexes E,S,W,N clockwise; for a TURN, R is the
# INCOMING heading, so `LeftTurn R3` is "running north, turn left" = exits west.
#
# The merger names are MIRRORED relative to travel: a `LeftFwdMerger` takes its side
# feed from the cell on its RIGHT as the shapes travel (i.e. the left side as you
# face the belt head-on).
#
# LIFTS ARE THE PART THIS MODEL USED TO GET WRONG. A `Lift1UpForward` at Z hands off
# at Z+1 in the cell AHEAD of it; a `Lift1DownForward` at Z hands off at Z-1 one cell
# ahead; the `Left`/`Right` variants turn 90 degrees on the way -- John's rule is that
# a Z-change unit "may rotate the entry or exit towards a different cardinal
# direction, but that's it", and it may never merge. Treating a lift as a flat
# `Forward` made this tool report 120 phantom dead ends on a machine that has none.
# With the Z hop modelled, `For Claude Working MAM 1 layer no-color FSB` comes out at
# 0 dead ends over 1,293 space belts.
BELT_VEC = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
BELT_IN = {"Forward": [2], "LeftTurn": [2], "RightTurn": [2],
           "LeftFwdSplitter": [2], "RightFwdSplitter": [2],
           "LeftFwdMerger": [2, 1], "RightFwdMerger": [2, 3],
           "TripleMerger": [1, 2, 3], "YMerger": [1, 3]}
LIFT_RE = re.compile(r"Lift(\d)(Up|Down)(Forward|Left|Right)$")


def belt_outs(t, R):
    """Where a space belt hands off, as a list of (direction, dz)."""
    if t == "LeftTurn":
        return [((R - 1) % 4, 0)]
    if t == "RightTurn":
        return [((R + 1) % 4, 0)]
    if t == "LeftFwdSplitter":
        return [(R, 0), ((R - 1) % 4, 0)]
    if t == "RightFwdSplitter":
        return [(R, 0), ((R + 1) % 4, 0)]
    m = LIFT_RE.match(t)
    if m:
        levels, updown, turn = int(m.group(1)), m.group(2), m.group(3)
        dz = levels if updown == "Up" else -levels
        return [({"Forward": R, "Left": (R - 1) % 4, "Right": (R + 1) % 4}[turn], dz)]
    return [(R, 0)]


def belt_ins(t):
    """Which sides a space belt will accept from, relative to its own R."""
    if LIFT_RE.match(t):
        return [2]                      # a lift takes its feed from behind, only
    return BELT_IN.get(t, [2])


def island_cells(i):
    """Every island-grid cell an island occupies -- not just the origin it records."""
    T, R = i["T"], i.get("R", 0)
    X, Y, Z = i.get("X", 0), i.get("Y", 0), i.get("Z", 0)
    return [(X + dx, Y + dy, Z) for dx, dy in ISLAND_FOOTPRINT.get((T, R), [(0, 0)])]


def check_islands_and_belts(isls, check):
    """Four structural checks that the game does NOT warn about.

    1. No two islands may claim the same island-grid cell. A 2x4 foundation covers
       eight cells and only records one, so an overlap is invisible in the file and
       shows up in-game as a platform that refuses to stamp.
    2. Every space belt must deliver into something that accepts from that side.
       A belt whose output faces an empty cell, or faces a neighbour that has no
       input port there, silently dead-ends.
    3. Every space belt must be FED by something -- a belt upstream, or the platform
       it leaves. An ORPHAN chain is the signature of a splitter that got placed as a
       plain `Forward`: the branch it was meant to feed is built, connected all the
       way to its destination, and completely dead. Found exactly that in the FSB MAM
       at (-9,2) on 2026-09-05 -- two of the sixteen band deliveries were starved and
       nothing else in the file looked wrong.
    4. Nothing may sit directly above or below a Z-change unit (John's rule).
    """
    occupied, overlaps = {}, []
    for i in isls:
        for c in island_cells(i):
            if c in occupied:
                overlaps.append(f"{i['T']} at ({i.get('X')},{i.get('Y')}) overlaps "
                                f"{occupied[c]} at cell {c}")
            occupied[c] = i["T"]
    check(not overlaps, f"island footprints do not overlap ({len(overlaps)} clashes)")
    say.some(overlaps, label="more clashes")

    belts = {(i.get("X", 0), i.get("Y", 0), i.get("Z", 0)):
             (i["T"][len("SpaceBelt_"):], i.get("R", 0))
             for i in isls if i["T"].startswith("SpaceBelt_")}
    if not belts:
        return
    # platform cells: everything that is not itself a space belt. A belt may hand off
    # into one (that is how a module is fed) but only at ground level.
    platforms = {(x, y) for (x, y, z), T in occupied.items()
                 if not T.startswith("SpaceBelt_")}

    dangling, fed = [], collections.defaultdict(list)
    for (x, y, z), (t, R) in belts.items():
        for o, dz in belt_outs(t, R):
            dx, dy = BELT_VEC[o]
            n = (x + dx, y + dy, z + dz)
            if n in belts:
                nt, nR = belts[n]
                if ((o + 2) % 4 - nR) % 4 in belt_ins(nt):
                    fed[n].append((x, y, z))
                else:
                    dangling.append(f"{t} R{R} at ({x},{y},Z{z}) feeds {nt} R{nR} "
                                    f"at {n}, which has no input port on that side")
            elif not (n[2] == 0 and (n[0], n[1]) in platforms):
                dangling.append(f"{t} R{R} at ({x},{y},Z{z}) outputs into empty space "
                                f"at {n}")
    check(not dangling, f"space belts all deliver somewhere ({len(dangling)} dead ends)")
    say.some(dangling, label="more dead ends")

    orphans = []
    for (x, y, z), (t, R) in belts.items():
        if fed[(x, y, z)]:
            continue
        by_platform = False
        for rel in belt_ins(t):
            dx, dy = BELT_VEC[(rel + R) % 4]
            if z == 0 and (x + dx, y + dy) in platforms:
                by_platform = True
        if by_platform:
            continue
        dx, dy = BELT_VEC[(R + 2) % 4]
        b = (x + dx, y + dy, z)
        why = (f"{belts[b][0]} R{belts[b][1]} at {b} does not output here"
               if b in belts else f"{b} is empty")
        orphans.append(f"{t} R{R} at ({x},{y},Z{z}) is fed by nothing -- {why}")
    check(not orphans, f"space belt chains all have a source ({len(orphans)} orphans)")
    say.some(orphans, label="more orphans")

    stacked = []
    for (x, y, z), (t, R) in belts.items():
        if not LIFT_RE.match(t):
            continue
        for oz in (z - 1, z + 1):
            if (x, y, oz) in belts:
                stacked.append(f"{t} at ({x},{y},Z{z}) has {belts[(x, y, oz)][0]} "
                               f"directly {'below' if oz < z else 'above'} it")
    check(not stacked, f"Z-change units have clear space ({len(stacked)} blocked)")
    say.some(stacked, label="more blocked")


def verify(path):
    name = os.path.basename(path)
    ver, d = decode_bp(path)
    isls = gv(d["BP"]["Entries"])
    total = sum(len(gv((i.get("B") or {}).get("Entries"))) for i in isls)
    say.detail(f"\n=== {name}")
    say.detail(f"    {len(isls)} islands, {total} buildings")

    # A passing check is not news; a failing one is. Under --full every check
    # prints, which is what you want when a verdict surprises you.
    fails, ran, notes = [], [], []

    def check(ok, msg):
        ran.append(ok)
        if ok:
            say.detail(f"    [PASS] {msg}")
        else:
            print(f"    [FAIL] {msg}")
            fails.append(msg)

    FIXED = cells(bm.load_reference_island("Fancy A+B Side Overflow.spz2bp"))
    PREFIX = cells(bm.load_reference_island("Fancy A+B Side Overflow (pre-lane-fix).spz2bp"))
    GOALF = cells(bm.load_reference_island("For Claude Filter with Signal.spz2bp"))

    fancy = [i for i in isls if i["T"].startswith("Foundation_2x4") and "Fancy" in bm.label_texts(i)]
    good = sum(1 for i in fancy if cells(i) == FIXED)
    buggy = sum(1 for i in fancy if cells(i) == PREFIX)
    odd = len(fancy) - good - buggy
    check(buggy == 0 and odd == 0,
          f"Fancy A+B lane fix: {len(fancy)} units, {good} fixed, {buggy} PRE-FIX, {odd} unrecognised")

    stale = sum(1 for i in isls for L in bm.label_texts(i) if "SHIT" in L)
    check(stale == 0, f"stale bug-warning labels: {stale}")

    filt = [i for i in isls if i["T"] == "Foundation_1x4" and "Quaded Filter" in bm.label_texts(i)]
    same = sum(1 for i in filt if cells(i) == GOALF)
    check(filt and same == len(filt),
          f"Quaded Filters: {len(filt)}, {same} identical to the goal-driven reference")

    chans = collections.Counter(c for i in filt for c in int_signals(i))
    check(len(chans) == 1, f"Goal Receiver channels: {dict(chans)}")

    demux = sum(1 for i in isls if "Demuxer" in bm.label_texts(i))
    qsplit = sum(1 for i in isls if "Quad Splitter" in bm.label_texts(i))
    # One Quad Splitter and one Demuxer per INPUT lane. The filter count is not tied
    # to the lane count any more: the band-merge puts a second rank of Quaded Filters
    # on the merged trunks, so `filters > lanes` is expected there and is printed
    # rather than failed.
    check(demux == qsplit,
          f"component ratio: {qsplit} Quad Splitters / {demux} Demuxers "
          f"/ {len(filt)} Quaded Filters ({len(filt) - qsplit} beyond the input lanes)")

    # a stacker cluster = 2x Foundation_2x2 + 1x Foundation_2x2_Flipped + 2x Fancy A+B
    n22 = sum(1 for i in isls if i["T"] == "Foundation_2x2")
    n22f = sum(1 for i in isls if i["T"] == "Foundation_2x2_Flipped")
    clusters = n22f
    check(n22 == 2 * clusters and len(fancy) == 2 * clusters,
          f"stacker clusters: {clusters} (from {n22} 2x2, {n22f} 2x2_Flipped, {len(fancy)} Fancy A+B)")
    if clusters and qsplit:
        units = qsplit // 4
        per_unit = clusters / (qsplit / 4)
        # 5/unit = the Phase 1 per-lane architecture (4 lane clusters + 1 merge);
        # 1/unit = the band-merge (bands merged per position, then ONE cluster).
        arch = {5.0: "Phase 1 per-lane", 1.0: "band-merge"}.get(
            round(per_unit, 3), "UNRECOGNISED -- expected 5 (per-lane) or 1 (band-merge)")
        notes.append(f"{arch}, {units} unit(s)")
        say.detail(f"           -> {per_unit:.0f} clusters per 4-lane unit "
                   f"({units} unit(s)) = {arch}")
        painters = sum(1 for i in isls if "Painter" in bm.label_texts(i)
                       or "Paint" in " ".join(bm.label_texts(i)))
        if painters:
            notes.append(f"{painters} paint platform(s)")

    bad = []
    for i in isls:
        for e in gv((i.get("B") or {}).get("Entries")):
            c = e.get("C")
            if c is not None and (not isinstance(c, dict) or "$type" not in c):
                bad.append((i.get("X"), i.get("Y"), e.get("T")))
    check(not bad, f"building configs well-formed (missing $type: {len(bad)})")

    check_islands_and_belts(isls, check)

    say.verdict(not fails, "%s -- %d/%d checks, %d islands, %d buildings%s"
                % (name, sum(ran), len(ran), len(isls), total,
                   ("  [" + "; ".join(notes) + "]") if notes else ""))
    return fails


if __name__ == "__main__":
    paths = say.args()
    allfails = []
    for p in paths:
        allfails += verify(p)
    if len(paths) > 1:
        say.verdict(not allfails, "%d file(s), %d failed check(s)"
                    % (len(paths), len(allfails)))
    sys.exit(1 if allfails else 0)
