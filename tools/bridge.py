#!/usr/bin/env python3
"""
bridge.py -- talk to the RUNNING game through the ClaudeBridge mod's mailbox.

    python tools/bridge.py ping
    python tools/bridge.py status
    python tools/bridge.py inspect
    python tools/bridge.py members IMapModel

A request is a file; the reply is a file.  The mod polls `in/` four times a second
from inside the game's own Tick, so every game object is touched on the only thread
where that is safe -- no listener thread, no Unity calls from off-thread.

    <persistent>/claude-bridge/in/<id>.txt    written here
    <persistent>/claude-bridge/out/<id>.txt   written by the mod
    <persistent>/claude-bridge/log.txt        every request, with timing

Ugly on purpose: a file mailbox is trivially inspectable when something goes wrong,
and the transport can become a loopback socket later without any of the verbs
changing.  If this times out, the usual causes are (a) the game is not running,
(b) no save is loaded, (c) the mod did not load -- check log.txt, which the mod
writes on load before anything else can fail.
"""
import os, sys, time, uuid

PERSISTENT = os.environ.get(
    "SPZ2_PERSISTENT",
    os.path.expandvars(r"C:\Users\jdeli\AppData\LocalLow\tobspr Games\shapez 2"))
ROOT = os.path.join(PERSISTENT, "claude-bridge")


def call(command, timeout=20.0):
    """Send one command, wait for its reply. Raises TimeoutError with a diagnosis."""
    ind, outd = os.path.join(ROOT, "in"), os.path.join(ROOT, "out")
    if not os.path.isdir(ind):
        raise RuntimeError(
            "no mailbox at %s -- the mod has not loaded. Is the game running with "
            "ClaudeBridge enabled?" % ROOT)
    rid = "%d-%s" % (time.time() * 1000, uuid.uuid4().hex[:6])
    tmp = os.path.join(ind, rid + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(command)
    os.replace(tmp, os.path.join(ind, rid + ".txt"))     # atomic: never a half-written request

    reply = os.path.join(outd, rid + ".txt")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(reply):
            with open(reply, encoding="utf-8") as f:
                out = f.read()
            try: os.remove(reply)
            except OSError: pass
            return out
        time.sleep(0.05)
    raise TimeoutError(
        "no reply in %.0fs. The mod loads its mailbox before anything else, so if "
        "%s exists but nothing answers, the game is paused, not running, or has no "
        "save loaded." % (timeout, ROOT))


def tail_log(n=15):
    p = os.path.join(ROOT, "log.txt")
    if not os.path.exists(p):
        return "(no log.txt -- the mod has never loaded)"
    with open(p, encoding="utf-8", errors="replace") as f:
        return "".join(f.readlines()[-n:])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--log":
        print(tail_log(int(sys.argv[2]) if len(sys.argv) > 2 else 15)); sys.exit(0)
    cmd = " ".join(sys.argv[1:]) or "ping"
    try:
        print(call(cmd))
    except Exception as e:
        print("%s: %s" % (type(e).__name__, e))
        print("\n--- claude-bridge/log.txt ---\n" + tail_log())
        sys.exit(1)
