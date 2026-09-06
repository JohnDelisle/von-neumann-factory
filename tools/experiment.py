#!/usr/bin/env python3
"""
experiment.py -- the unattended throughput test (DIRECTIVE step 3).

    python tools/experiment.py --module VN20_V1                       one variant vs the reference
    python tools/experiment.py A.spz2bp B.spz2bp --module VN20_V1     batch: one game session
    python tools/experiment.py --module VN20_V1 --reference VN20 --minutes 3 --warmup 2

For every variant:  take the newest sandbox save -> delete the island in the TEST SLOT
(and the noise islands that deliver the same shape) -> stamp the variant into the slot
(same footprint, same rotation, checked) -> write it as the newest backup -> load it in
the running game (start the game if needed) -> run hot -> warm up -> pause, save, read
the sim clock (baseline) -> run N sim-minutes -> pause, save, clock -> one line:

    REF  VN-20 NE quadrant full belt: 1729.9 Ru------/s over 180 sim-s  (36.0/lane over 48 lanes)
    PASS VN-20 v3 ...: 1725.1 Ru------/s  (>= 0.95 x ref 1729.9)
    FAIL VN-20 NE quadrant full belt v1 2perlane: 1153.0 Ru------/s  (>= 0.95 x ref 1729.9)

The reference (default: compiled `VN20`, John's in-game-validated v3) is measured first
in the same session, in the same slot, so the bar is a measured full belt, not a number
from a doc. Pass `--expect-rate X` to use an absolute items/s instead.

The sandbox is left as found: the base save is re-written as the newest backup at the
end, so John's next load sees his own map, not the last variant.

## Measured facts this tool rests on (2026-09-06, this map, 11k buildings)
- The bridge verb `speed` (SimulationSpeedManager.Speed) changes NOTHING. The console
  command `time.global-setspeed N` is what accelerates the sim; use `console ...`.
- At "25x" the sim is CPU-bound and actually performs ~3.3x ticks. `TotalPlaytime`
  advances at the REQUESTED speed (23.6x), so rates per playtime-second are wrong by 7x.
- `core.SimulationSpeed.SimulationTime_G` advances with ticks actually performed (1.0x at
  1x, ~3.1x at "25x", 0 while paused): it is the honest sim clock. Delivered per
  SimulationTime_G-second came out identical at 1x and 25x (1733 vs 1730 Ru------/s).
- `pause`/`resume` (IsPaused) do work, so a save + clock read is one frozen instant.

Test slot: island (3,-1), the 1x4 R1 Quaded-Filter slot John built his VN-20 feed for
(east in, west out, into the 144-lane hub feed). Noise: island (5,5), the other VN-20,
which delivers the same shape and would mask the variant. Both are flags.
"""
import argparse, os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import save_world as sw
import stamp, brief, bridge, game
from shapez_bp import encode_bp

SAVE_CALL = ("call Game.Orchestration.GameBootstrapper.GameOrchestrator."
             "CurrentSubOrchestrator.TrySaveCurrentSync")
TOL = 0.95
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ save surgery
def compile_variant(name, outdir):
    import build_modules as bm
    m = getattr(bm, name)
    code = encode_bp(5, bm.check_configs(bm.build(m)))
    path = os.path.join(outdir, "%s [%s].spz2bp" % (m.name, name))
    open(path, "w").write(code)
    return path


def find_island(w, X, Y):
    for c, ch in w["world"].items():
        for k, i in enumerate(ch["islands"]):
            if (i["X"], i["Y"], i["Z"]) == (X, Y, 0):
                return c, k, i
    raise SystemExit("FAIL no island at (%d,%d) in %s" % (X, Y, w["path"]))


def remove_island(w, X, Y):
    c, k, i = find_island(w, X, Y)
    w["world"][c]["islands"].pop(k)
    st = w["world"][c]["state"]
    for j, r in enumerate(st):
        if (r["X"], r["Y"], r["Z"]) == (X, Y, 0):
            st.pop(j)
            break
    else:
        raise SystemExit("FAIL island (%d,%d) has no state record" % (X, Y))
    return i


def make_test_save(base, bpf, slot, noise):
    """base save + variant stamped into the slot (footprint checked) -> newest backup path."""
    w = sw.read_world(base)
    old = remove_island(w, *slot)
    for xy in noise:
        remove_island(w, *xy)
    S = w["strings"]
    idx = {s: i for i, s in enumerate(S)}

    def intern(s):
        if s not in idx:
            idx[s] = len(S)
            S.append(s)
        return idx[s]

    probe = stamp.blueprint_islands(bpf, 0, 0, 0, 0, lambda s: 0)
    assert len(probe) == 1, "variant must be ONE island, got %d" % len(probe)
    rot = (old["R"] - probe[0]["R"]) % 4
    isls = stamp.blueprint_islands(bpf, slot[0], slot[1], 0, rot, intern)
    new = isls[0]
    want = sorted(stamp.island_cells(old["layout"], old["R"], old["X"], old["Y"], old["Z"]))
    got = sorted(stamp.island_cells(new["layout"], new["R"], new["X"], new["Y"], new["Z"]))
    assert got == want, ("footprint differs from the slot's %s R%d: %s vs %s"
                         % (old["layout"], old["R"], got, want))
    stamp.add_islands(w, isls)
    dst = stamp.next_backup(os.path.dirname(base))
    sw.write_world(w, dst)
    return dst, len(new["buildings"])


# ------------------------------------------------------------------ game control
def ensure_loaded(path):
    """Make the running game show the save we just wrote (start the game if it is down)."""
    if not game.is_running():
        game.start()
    out = bridge.call("load " + game.SANDBOX_UID, timeout=60).strip()
    got = game.wait_for_world()
    if got.startswith("TIMEOUT"):
        raise SystemExit("FAIL load: %s / %s" % (out, got))
    newest = brief.newest_saves(1)[0]          # the game loads the newest file by mtime
    assert os.path.samefile(newest, path), "game loaded %s, wanted %s" % (newest, path)


def set_speed(n):
    bridge.call("console time.global-setspeed %d" % n)


def sim_clock():
    return float(bridge.call("get core.SimulationSpeed.SimulationTime_G").split()[0])


def wait_sim(seconds):
    """Block until the sim clock has advanced `seconds` of ticks actually performed."""
    t0, w0 = sim_clock(), time.time()
    while sim_clock() - t0 < seconds:
        if time.time() - w0 > seconds * 3 + 60:
            raise SystemExit("FAIL sim clock advanced only %.0f of %d s in %.0f wall-s -- is it paused?"
                             % (sim_clock() - t0, seconds, time.time() - w0))
        time.sleep(1.0)


def save_now():
    before = set(brief.newest_saves(50))
    bridge.call(SAVE_CALL, timeout=90)
    deadline = time.time() + 60
    while time.time() < deadline:
        new = [p for p in brief.newest_saves(50) if p not in before]
        if new:
            time.sleep(1.0)                    # let the zip close
            return new[0]
        time.sleep(0.5)
    raise SystemExit("FAIL save: no new .spz2 appeared after %s" % SAVE_CALL)


def snapshot():
    """One frozen instant: (StoredShapes, sim clock)."""
    bridge.call("pause")
    try:
        clock = sim_clock()
        stored, _ = brief.light(save_now())
    finally:
        bridge.call("resume")
    return stored, clock


def measure(minutes, warmup, speed, shape):
    """-> (rate items/s of `shape` per sim-second, shape, sim seconds)."""
    set_speed(speed)
    bridge.call("resume")
    try:
        wait_sim(warmup * 60)
        ssa, ca = snapshot()
        wait_sim(minutes * 60)
        ssb, cb = snapshot()
    finally:
        set_speed(1)
    sim_s = cb - ca
    deltas = {k: v - ssa.get(k, 0) for k, v in ssb.items()}
    if shape is None:
        shape = max(deltas, key=deltas.get) if deltas else "?"
    return deltas.get(shape, 0) / sim_s if sim_s > 0 else 0.0, shape, sim_s


def restore_sandbox(base, before):
    """Leave the sandbox as found: every save this run wrote goes, then the base is
    re-written as the newest file so the game's next load is John's map."""
    mine = [p for p in brief.newest_saves(500) if p not in before]
    for p in mine:
        os.remove(p)
    back = stamp.next_backup(os.path.dirname(base))
    shutil.copyfile(base, back)
    print("sandbox restored: %d run saves removed; %s re-written as %s"
          % (len(mine), os.path.basename(base), os.path.basename(back)))


# ------------------------------------------------------------------ driver
def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("blueprints", nargs="*", help=".spz2bp files, one island each")
    ap.add_argument("--module", action="append", default=[],
                    help="build_modules Module name to compile and test (repeatable)")
    ap.add_argument("--reference", default="VN20",
                    help="Module name or .spz2bp measured first as the bar (default VN20 = v3); 'none' to skip")
    ap.add_argument("--expect-rate", type=float, default=None,
                    help="absolute items/s bar instead of a measured reference")
    ap.add_argument("--minutes", type=float, default=3.0, help="measured sim-minutes (default 3)")
    ap.add_argument("--warmup", type=float, default=2.0,
                    help="sim-minutes before the baseline snapshot (default 2)")
    ap.add_argument("--speed", type=int, default=25)
    ap.add_argument("--lanes", type=int, default=48, help="lanes the slot carries, for the per-lane fact")
    ap.add_argument("--shape", default=None, help="shape code to count (default: the one that grew most)")
    ap.add_argument("--slot", type=int, nargs=2, default=(3, -1), metavar=("X", "Y"))
    ap.add_argument("--noise", type=int, nargs=2, action="append", default=None, metavar=("X", "Y"),
                    help="islands to delete because they deliver the same shape (default (5,5))")
    ap.add_argument("--base", default=None,
                    help="the save to build on (default: newest in the sandbox folder -- make sure that is John's map)")
    ap.add_argument("--keep", action="store_true",
                    help="keep every save the run wrote and do not restore the base at the end")
    a = ap.parse_args(argv)
    noise = a.noise if a.noise is not None else [(5, 5)]

    outdir = os.path.join(ROOT, "blueprints", "experiments")
    os.makedirs(outdir, exist_ok=True)

    def resolve(x):
        return x if x.endswith(".spz2bp") else compile_variant(x, outdir)

    variants = list(a.blueprints) + [resolve(n) for n in a.module]
    if not variants:
        ap.error("nothing to test")
    ref = None if (a.expect_rate is not None or a.reference == "none") else resolve(a.reference)

    base = os.path.abspath(a.base) if a.base else brief.newest_saves(1)[0]
    before = set(brief.newest_saves(500))
    print("base save %s" % os.path.basename(base))
    bar, shape, verdicts = a.expect_rate, a.shape, []

    def run(bpf):
        label = os.path.splitext(os.path.basename(bpf))[0]
        test, nb = make_test_save(base, bpf, tuple(a.slot), noise)
        print("stamped %s (%d buildings) into slot %s -> %s"
              % (label, nb, tuple(a.slot), os.path.basename(test)))
        ensure_loaded(test)
        return (label,) + measure(a.minutes, a.warmup, a.speed, shape)

    try:
        if ref is not None:
            label, rate, shape, sim_s = run(ref)
            bar = rate * TOL
            mult = brief.shape_multiplier(base)
            print("REF  %s: %.1f %s/s over %.0f sim-s  (%.1f/lane over %d lanes = %.2f items/s/lane physical, Shape Multiplier x%d)"
                  % (label, rate, shape, sim_s, rate / a.lanes, a.lanes, rate / a.lanes / mult, mult))
        for bpf in variants:
            label, rate, shape, sim_s = run(bpf)
            v = "PASS" if rate >= bar else "FAIL"
            verdicts.append(v)
            print("%s %s: %.1f %s/s over %.0f sim-s  (bar %.1f)" % (v, label, rate, shape, sim_s, bar))
    finally:
        if not a.keep:
            restore_sandbox(base, before)
    return 0 if verdicts and all(v == "PASS" for v in verdicts) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
