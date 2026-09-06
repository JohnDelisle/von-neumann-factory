#!/usr/bin/env python3
"""
brief.py -- the whole session state in ~30 lines, so a fresh agent does not have
to read the doc corpus to find out where it is.

    python tools/brief.py            newest sandbox save + live game + scoreboard
    python tools/brief.py --save X   pin a specific .spz2
    python tools/brief.py --nogame   skip the bridge probe (no 3s wait when down)

## Why this exists

Cost per model call is (context size) x (turns), and context never shrinks inside a
session.  The old bootstrap -- read PROGRESS.md, PLAYBOOK.md, architecture.md and
conventions.md -- put 3,370 lines into every session's context before the first
useful thought, and every later turn re-read all of it.  Almost all of that is
history.  This prints only what is TRUE RIGHT NOW, deterministically, from the save
and the running game.  Read the docs when you need the why; read this to know where
you are.

Everything here is measured, nothing is remembered: delivered counts come from
`research.json -> Shapes.StoredShapes`, goals from the ConstantSignals actually
placed on the map, rates from the playtime delta against the previous save.
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import save_world as sw
import observe

PERSISTENT = os.environ.get(
    "SPZ2_PERSISTENT",
    r"C:\Users\jdeli\AppData\LocalLow\tobspr Games\shapez 2")
SANDBOX_UID = "d58e3f84-b198-411f-9f46-78fcbfe7dae4"
SAVES = os.path.join(PERSISTENT, "savegames", SANDBOX_UID)


def newest_saves(n=2):
    """The n most recent .spz2 in the sandbox folder, newest first."""
    if not os.path.isdir(SAVES):
        return []
    f = [os.path.join(SAVES, x) for x in os.listdir(SAVES) if x.endswith(".spz2")]
    return sorted(f, key=os.path.getmtime, reverse=True)[:n]


def light(path):
    """research.json + savegame.json only -- no world parse. Cheap enough to run on
    the previous save purely to get a delta."""
    import zipfile
    with zipfile.ZipFile(path) as z:
        return (json.loads(z.read("research.json"))["Shapes"]["StoredShapes"],
                json.loads(z.read("savegame.json")))


def game_state():
    try:
        import game
        running = game.is_running()
        if not running:
            return "not running", "-"
        import bridge
        return "running", bridge.call("get core.Savegame.Name", timeout=4).strip().strip('"')
    except Exception as e:
        return "unknown (%s)" % type(e).__name__, "-"


def goals(w):
    """Channel ints and shape codes are separate ConstantSignals; John puts the pair
    on one island, so island coords are the join key."""
    ints, shapes = observe.broadcasts(w)
    by_isl = {}
    for x, y, v in ints:
        by_isl.setdefault((x, y), [None, None])[0] = v
    for x, y, c in shapes:
        by_isl.setdefault((x, y), [None, None])[1] = c
    return sorted(by_isl.items(), key=lambda kv: (kv[1][0] is None, kv[1][0] or 0))


def active_task():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "docs", "PROGRESS.md")
    try:
        for line in open(p, encoding="utf-8"):
            if ">>> START HERE" in line and "superseded" not in line:
                return line.strip().lstrip("# ")
    except OSError:
        pass
    return "(no START HERE banner in docs/PROGRESS.md)"


def main(argv):
    pin = argv[argv.index("--save") + 1] if "--save" in argv else None
    recent = newest_saves(2)
    path = pin or (recent[0] if recent else None)
    if not path:
        print("no savegame found under", SAVES); return 1

    print("BRIEF  %s" % time.strftime("%Y-%m-%d %H:%M"))
    if "--nogame" not in argv:
        proc, world = game_state()
        print("  game      : %-14s world: %s" % (proc, world))

    w = sw.read_world(path)
    sg = json.loads(w["entries"]["savegame.json"])
    ss = observe.stored_shapes(w)
    isl = [i for ch in w["world"].values() for i in ch["islands"]]
    built = [i for i in isl if i["buildings"]]
    print("  save      : %s" % os.path.basename(path))
    print("              saved %s   playtime %.0fs   %d built islands / %d buildings"
          % (sg["LastSaved"][:19], sg["TotalPlaytime"], len(built),
             sum(len(i["buildings"]) for i in isl)))

    prev = {}
    dt = 0.0
    if not pin and len(recent) > 1:
        try:
            prev, psg = light(recent[1])
            dt = sg["TotalPlaytime"] - psg["TotalPlaytime"]
            print("              delta vs %s (%.0fs of sim)"
                  % (os.path.basename(recent[1])[:12], dt))
        except Exception:
            prev = {}

    print("\n  VORTEX  (research.json Shapes.StoredShapes)")
    if not ss:
        print("    nothing delivered yet")
    for k, v in sorted(ss.items(), key=lambda kv: -kv[1])[:8]:
        d = v - prev.get(k, v)
        rate = "  %8.1f/s" % (d / dt) if dt > 0 and d else ""
        print("    %-14s %10d %+9d%s" % (k, v, d, rate))

    print("\n  GOALS  (ConstantSignals on the map)")
    for (x, y), (ch, code) in goals(w)[:6]:
        got = ss.get(code, 0) if code else 0
        print("    ch %-6s %-10s delivered %-10d  island (%d,%d)"
              % (ch if ch is not None else "?", code or "?", got, x, y))

    # NO liveness line here on purpose: a platform runtime-state record is not a
    # liveness signal (VN-15 read the empty 30-byte form while delivering 28,000
    # shapes). The per-second rates above are the honest proof that a machine runs.
    print("  ACTIVE    : %s" % active_task())
    print("  detail in docs/PROGRESS.md (START HERE only); history in docs/history/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
