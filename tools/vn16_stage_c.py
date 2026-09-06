"""
vn16_stage_c.py -- channel 789 (SuSuSuSu) stage C, measured unattended.

    python tools/vn16_stage_c.py                 # REF (stage B) then variant L, then R if L FAILs
    python tools/vn16_stage_c.py --dry-run       # build + trace the platforms, touch nothing
    python tools/vn16_stage_c.py --variants R    # one variant only
    python tools/vn16_stage_c.py --keep          # keep the run's saves (no restore)

Stage B (`build_star_machine.cutter_platform`, in the sandbox at island (15,-22)) turns
the mined `SuSuCu--` into `--SuSu--`.  Stage C splits that lane, rotates one branch 180
(`Su----Su`), lifts it to floor 1 and stacks the two -> `SuSuSuSu`.

Why this is hand-placed although DIRECTIVE rule 1 says compile: the compiler knows
1x1 one-in/one-out operators only.  Stage C needs a 2-in stacker, a side branch, a
lift and two turns -- four primitives it lacks.  This 20-cell probe settles the game
facts those primitives need (which side a Splitter1To2L's second output leaves on,
where a Lift1UpForward hands off, whether a stacker accepts a floor-1 feed) before any
compiler work is spent on them (rule 6: facts before builds).

The side question, answered offline this time (no build cycle): buildings.json says
`Splitter1To2L` emits on local sides 0 and 3, `Mirrored` on 0 and 1; direction is
0=E 1=S 2=W 3=N and a rotation R ADDS to it (conventions.md "Direction is 0=E, 1=S, 2=W,
3=N"; the compiler's in-game-validated VN-02c pair at (9,10,R3)/(10,10,R3) fans W/E,
which only the add-R rule predicts).  So on this westbound (R2) lane the plain variant
branches to +Y (y=11) and the Mirrored one to -Y (y=9).  The old stage C assumed side 3
was +Y unrotated; with R2 that put branch B on y=9, into the trash row.  Variant L
below is the corrected plain splitter; R is the mirrored one, kept as the one bounded
repair should L still fail.

Trunk repair: the sandbox's trunk (x=-1, y=-22..-2) has lost its last two islands
(-1,-3) and (-1,-2) since VN-16 delivered its 329,364 (John built around the hub's
south side).  Every test save re-adds them; the base save is restored afterwards.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import save_world as sw
import stamp, brief, experiment
from build_star_machine import b, BAND, FLOORS, LANE, PATCH, TRUNK_Y, cutter_platform
from build_circle_delivery import check_sizes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLATFORM = (PATCH[0] - 2, PATCH[1])          # (15,-22), Foundation_1x1 R2, stage B lives here
TRUNK_GAP = [(-1, -3), (-1, -2)]             # SpaceBelt_Forward R1, missing from the sandbox
STACKER_X = 8

BELT, LEFT, RIGHT = ("BeltDefaultForwardInternalVariant", "BeltDefaultLeftInternalVariant",
                     "BeltDefaultLeftInternalVariantMirrored")


def stage_c_platform(side):
    """side=+1: plain Splitter1To2L, branch B on y=LANE+1.  side=-1: Mirrored, y=LANE-1.

    Floor 0, flow west (R2):  cutter(16) -> belt(15) -> splitter(14) -> belts 13..9 ->
    stacker(8, floors 0+1) -> belts 7..3 -> sender(2).
    Branch B on y=LANE+side:  turn(14) -> RotatorHalf(13) -> Lift1UpForward(12) hands
    off at (11, L1) -> belts 11,10 -> turn at 9 back onto y=LANE -> turn west into
    the stacker's floor-1 input.  R convention: direction = (local + R) % 4."""
    yb = LANE + side
    out = [x for x in cutter_platform()
           if not (x["T"] == BELT and x["Y"] == LANE)]        # keep ports, cutter, trash
    spl = "Splitter1To2LInternalVariant" if side > 0 else "Splitter1To2LInternalVariantMirrored"
    out.append(b(BELT, 15, LANE, R=2))
    out.append(b(spl, 14, LANE, R=2))
    for x in range(STACKER_X + 1, 14):
        out.append(b(BELT, x, LANE, R=2))
    out.append(b("StackerStraightInternalVariant", STACKER_X, LANE, R=2))
    for x in range(3, STACKER_X):
        out.append(b(BELT, x, LANE, R=2))
    # branch B, floor 0: enter from the splitter's side output, turn west
    if side > 0:
        out.append(b(RIGHT, 14, yb, R=1))     # travelling S (R1), right turn -> W
    else:
        out.append(b(LEFT, 14, yb, R=3))      # travelling N (R3), left turn -> W
    out.append(b("RotatorHalfInternalVariant", 13, yb, R=2))
    out.append(b("Lift1UpForwardInternalVariant", 12, yb, R=2))
    # branch B, floor 1: west along yb, back onto the lane, west into the stacker
    out.append(b(BELT, 11, yb, L=1, R=2))
    out.append(b(BELT, 10, yb, L=1, R=2))
    if side > 0:
        out.append(b(RIGHT, STACKER_X + 1, yb, L=1, R=2))     # W then right -> N
        out.append(b(LEFT, STACKER_X + 1, LANE, L=1, R=3))    # N then left -> W
    else:
        out.append(b(LEFT, STACKER_X + 1, yb, L=1, R=2))      # W then left -> S
        out.append(b(RIGHT, STACKER_X + 1, LANE, L=1, R=1))   # S then right -> W
    return out


# ------------------------------------------------------------------ offline trace
DELTA = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
_RATES = None


def rates():
    global _RATES
    if _RATES is None:
        _RATES = json.load(open(os.path.join(ROOT, "gamedata", "rates.json"), encoding="utf-8"))
    return _RATES


def rot(x, y, R):
    for _ in range(R % 4):
        x, y = -y, x
    return x, y


def trace(buildings):
    """Follow every belt output to the cell it feeds; FAIL text or None.

    Checks: no two buildings share a cell; every output lands on a building whose
    input face points back at it (ports and trash excepted); the sender at (2,LANE,0)
    is reached from the cutter; the stacker sees both inputs fed."""
    cells, fed = {}, {}
    for k in buildings:
        row = rates()[k["T"]]
        for tx, ty, tz in row["tiles"]:
            gx, gy = rot(tx, ty, k["R"])
            c = (k["X"] + gx, k["Y"] + gy, k["L"] + tz)
            if c in cells:
                return "FAIL cell %s used by %s and %s" % (c, cells[c]["T"], k["T"])
            cells[c] = k
    for k in buildings:
        row = rates()[k["T"]]
        for tx, ty, tz, d in row["outputs"]:
            gx, gy = rot(tx, ty, k["R"])
            d = (d + k["R"]) % 4
            dx, dy = DELTA[d]
            tgt = (k["X"] + gx + dx, k["Y"] + gy + dy, k["L"] + tz)
            t = cells.get(tgt)
            if k["T"].startswith("BeltPort") and (t is None or t["T"].startswith("Cutter")):
                continue                          # idle port lanes feed nothing (or a machine flank)
            if t is None:
                return "FAIL %s at %s outputs into empty %s" % (k["T"], (k["X"], k["Y"], k["L"]), tgt)
            trow = rates()[t["T"]]
            faces = set()
            for ix, iy, iz, idr in trow["inputs"]:
                fx, fy = rot(ix, iy, t["R"])
                faces.add((t["X"] + fx, t["Y"] + fy, t["L"] + iz, (idr + t["R"]) % 4))
            if (tgt[0], tgt[1], tgt[2], (d + 2) % 4) not in faces:
                return "FAIL %s at %s -> %s at %s has no input face there" % (
                    k["T"], (k["X"], k["Y"], k["L"]), t["T"], tgt)
            fed.setdefault((t["X"], t["Y"], t["L"], t["T"]), set()).add(tgt)
    st = next((k for k in buildings if k["T"].startswith("StackerStraight")), None)
    if st is not None:
        n = len(fed.get((st["X"], st["Y"], st["L"], st["T"]), ()))
        if n != 2:
            return "FAIL stacker at %s fed on %d of 2 inputs" % ((st["X"], st["Y"]), n)
    if not any(x for x in fed if x[3].startswith("BeltPortSender") and x[1] == LANE and x[2] == 0):
        return "FAIL the lane never reaches the sender at (2,%d,0)" % LANE
    return None


# ------------------------------------------------------------------ save surgery
def make_save(base, buildings, dst=None):
    """base + platform buildings replaced + trunk gap re-added -> path."""
    w = sw.read_world(base)
    _, _, isl = experiment.find_island(w, *PLATFORM)
    assert isl["layout"] == "Foundation_1x1" and isl["R"] == 2, isl["layout"]
    isl["buildings"] = list(buildings)
    have = {(i["X"], i["Y"]) for ch in w["world"].values() for i in ch["islands"]}
    gap = [dict(X=x, Y=y, Z=0, layout="SpaceBelt_Forward", R=1, icfg=None, buildings=[])
           for x, y in TRUNK_GAP if (x, y) not in have]
    if gap:
        stamp.add_islands(w, gap)
    dst = dst or stamp.next_backup(os.path.dirname(base))
    sw.write_world(w, dst)
    bad = check_sizes(sw.read_world(dst))
    assert not bad, "size law violated: %s" % bad[:3]
    return dst, len(gap)


# ------------------------------------------------------------------ driver
def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variants", default="L,R", help="L = plain splitter (branch +Y), R = mirrored (-Y)")
    ap.add_argument("--minutes", type=float, default=3.0)
    ap.add_argument("--warmup", type=float, default=2.0)
    ap.add_argument("--speed", type=int, default=25)
    ap.add_argument("--no-ref", action="store_true", help="skip the stage B reference run")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--base", default=None)
    a = ap.parse_args(argv)

    variants = [("stage C " + v, stage_c_platform(+1 if v == "L" else -1)) for v in a.variants.split(",")]
    plans = ([] if a.no_ref else [("stage B (reference)", cutter_platform())]) + variants
    for label, bl in plans:
        v = trace(bl)
        print("TRACE %-20s %d buildings: %s" % (label, len(bl), v or "PASS"))
        if v:
            return 1

    base = os.path.abspath(a.base) if a.base else brief.newest_saves(1)[0]
    mult = brief.shape_multiplier(base)
    if a.dry_run:
        out = os.path.join(ROOT, "blueprints", "experiments")
        os.makedirs(out, exist_ok=True)
        for label, bl in plans:
            dst, ng = make_save(base, bl, os.path.join(out, label.replace(" ", "_") + ".spz2"))
            print("DRY  %s -> %s (+%d trunk islands)" % (label, os.path.basename(dst), ng))
        return 0

    # stacker keeps up with 1/6 of a lane: 0.5 items/s = the most stage C can deliver.
    cap = 3.0 / 6 * mult
    bar = 0.5 * cap
    before = set(brief.newest_saves(500))
    print("base save %s (Shape Multiplier x%d; stage C cap %.1f/s, bar %.1f/s)"
          % (os.path.basename(base), mult, cap, bar))
    verdicts = []
    try:
        for label, bl in plans:
            test, ng = make_save(base, bl)
            print("wrote %s: %d buildings, +%d trunk islands" % (label, len(bl), ng))
            experiment.ensure_loaded(test)
            shape = "--SuSu--" if label.startswith("stage B") else "SuSuSuSu"
            rate, shape, sim_s = experiment.measure(a.minutes, a.warmup, a.speed, shape)
            if label.startswith("stage B"):
                v = "REF " if rate > 0 else "FAIL"
                print("%s %s: %.1f %s/s over %.0f sim-s (%.2f items/s)" % (v, label, rate, shape, sim_s, rate / mult))
                if rate <= 0:
                    print("FAIL stage B delivers nothing even with the trunk repaired -- fix the feed first")
                    return 1
                continue
            v = "PASS" if rate >= bar else "FAIL"
            verdicts.append(v)
            print("%s %s: %.1f %s/s over %.0f sim-s (%.2f items/s; bar %.1f)"
                  % (v, label, rate, shape, sim_s, rate / mult, bar))
            if v == "PASS":
                break                          # one bounded repair: R runs only if L fails
    finally:
        if not a.keep:
            experiment.restore_sandbox(base, before)
    return 0 if "PASS" in verdicts else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
