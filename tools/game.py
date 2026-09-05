#!/usr/bin/env python3
"""
game.py -- start, stop and steer Shapez 2 without a human.

    python tools/game.py status
    python tools/game.py stop
    python tools/game.py start
    python tools/game.py restart                 stop, start, wait for the mod
    python tools/game.py up [uid]                restart AND open a world (the usual one)
    python tools/game.py load <uid>              open a world in the running game
    python tools/game.py saves                   what worlds exist

## Why `up` is the interesting one

The game has NO command-line argument that loads a savegame -- the whole list is
--set-modding-env-vars, --ignore-mods, --safe-mode, --disable-store-sdk,
--custom-translations, --danger-bypass-modded-savegame-checks, --ignore-hw-checks,
--no-dynamic-content.  So launching the exe only ever reaches a main menu, and an
agent that can start the game but not open a world has gained nothing.

`up` closes that: it relaunches, waits for ClaudeBridge to report in, then asks the
mod to call GameOrchestrator.LoadSession from inside the process.

## The trap the main menu sets

At the menu the game is not idle -- it renders a background world, so the bridge
answers, GameHelper.Core is non-null, and a live IMapModel is reachable.  It is the
menu's own decorative save, "Menu Background Supporter".  ANY code that writes must
confirm which world is loaded first; `status` prints the name for exactly that
reason, and `wait_for_world` below checks it rather than merely checking that a map
exists.
"""
import os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge

STEAM_APPID = "2162800"
SANDBOX_UID = "d58e3f84-b198-411f-9f46-78fcbfe7dae4"
MENU_WORLD = "Menu Background Supporter"


def _ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-Command", script],
                          capture_output=True, text=True).stdout.strip()


def is_running():
    return _ps("(Get-Process | Where-Object { $_.ProcessName -like '*shapez*' } "
               "| Measure-Object).Count") not in ("", "0")


def stop():
    if not is_running():
        return "not running"
    _ps("Get-Process | Where-Object { $_.ProcessName -like '*shapez*' } | Stop-Process -Force")
    for _ in range(20):
        if not is_running():
            return "stopped"
        time.sleep(0.5)
    return "STILL RUNNING"


def start(timeout=180):
    """Launch through Steam (a direct exe launch trips the store SDK) and wait for
    the mod to announce itself in its own log -- which is a far better readiness
    signal than the process existing."""
    log = os.path.join(bridge.ROOT, "log.txt")
    before = os.path.getsize(log) if os.path.exists(log) else 0
    _ps("Start-Process 'steam://rungameid/%s'" % STEAM_APPID)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(log) and os.path.getsize(log) > before:
            with open(log, encoding="utf-8", errors="replace") as f:
                tail = f.read()[before:]
            if "loaded" in tail:
                # the mod is up; the game still needs a moment to finish its menu
                for _ in range(40):
                    try:
                        return "up: " + bridge.call("ping", timeout=3).strip()
                    except Exception:
                        time.sleep(1)
        time.sleep(1)
    return "TIMEOUT waiting for the mod to load"


def current_world():
    try:
        return bridge.call("get core.Savegame.Name", timeout=8).strip().strip('"')
    except Exception as e:
        return "<%s>" % type(e).__name__


def wait_for_world(uid=SANDBOX_UID, timeout=180):
    """Poll until a world that is NOT the menu background is loaded."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        name = current_world()
        if name and not name.startswith("<") and name != MENU_WORLD:
            islands = bridge.call("get map.IslandCount").strip()
            return "loaded %r  (%s)" % (name, islands)
        time.sleep(2)
    return "TIMEOUT: still %r" % current_world()


def up(uid=SANDBOX_UID):
    out = [stop(), start()]
    out.append(bridge.call("load " + uid, timeout=30).strip())
    out.append(wait_for_world(uid))
    return "\n".join(out)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    arg = sys.argv[2] if len(sys.argv) > 2 else SANDBOX_UID
    if cmd == "status":
        print("process running :", is_running())
        print("world loaded    :", current_world())
    elif cmd == "stop":    print(stop())
    elif cmd == "start":   print(start())
    elif cmd == "restart": print(stop()); print(start())
    elif cmd == "up":      print(up(arg))
    elif cmd == "load":    print(bridge.call("load " + arg, timeout=30)); print(wait_for_world(arg))
    elif cmd == "saves":   print(bridge.call("saves"))
    else:                  print(__doc__)
