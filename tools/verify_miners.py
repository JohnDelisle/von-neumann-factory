#!/usr/bin/env python3
"""
verify_miners.py -- does every miner platform actually fire into something?

    python tools/verify_miners.py SAVE.spz2 [--full]

## The bug this exists to catch

VN-18 built twelve boosted miners and delivered ONE lane. Every platform placed
correctly, every rotation read back exactly as written, the size law passed, and the
layout looked right in-game -- but all twelve fired their 12-lane sender band into
their own booster row, because of a rule we had backwards:

    WRONG: "the platform's 12 output lanes leave on edge R" (the island's rotation)
    RIGHT: the SENDER BUILDING'S OWN R is the world direction it fires, and the band
           must physically sit on the edge it fires through. The ISLAND's R does not
           steer the output at all -- rotating eleven islands 180 degrees changed the
           delivered rate by 0.5%.

Nothing else in the toolchain notices this: a miner whose output lands in a booster
field is byte-identical in every check we had. So this one asks the only question
that matters -- for each miner, take its senders' rotation, step one island that way,
and see whether anything is there to receive.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import save_world as sw
import say

VEC = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}     # 0=+X E 1=+Y S 2=-X W 3=-Y N
NAME = {0: "east", 1: "south", 2: "west", 3: "north"}


def audit(path):
    w = sw.read_world(path)
    g = {(i["X"], i["Y"]): i for ch in w["world"].values() for i in ch["islands"]}
    rows = []
    for (x, y), i in sorted(g.items()):
        if i["layout"] != "Layout_ShapeMiner":
            continue
        snd = [b for b in i["buildings"] if "Sender" in b["T"]]
        if not snd:
            rows.append((x, y, 0, None, "no sender band at all", False))
            continue
        rs = sorted(set(b["R"] for b in snd))
        dx, dy = VEC[rs[0]]
        t = g.get((x + dx, y + dy))
        tl = t["layout"] if t else "EMPTY"
        # A platform cannot receive from a miner; only a space belt can.
        rows.append((x, y, len(snd), rs, tl, tl.startswith("SpaceBelt")))
    return rows


def main(argv):
    paths = say.args(argv)
    if not paths:
        print(__doc__.strip().splitlines()[2]); return 2
    fails = 0
    for p in paths:
        rows = audit(p)
        bad = [r for r in rows if not r[5]]
        fails += len(bad)
        for x, y, n, rs, tl, ok in rows:
            if ok:
                say.detail("  ok  (%3d,%3d) %2d senders R%s fires %-5s -> %s"
                           % (x, y, n, rs, NAME[rs[0]], tl))
            else:
                print("  BAD (%3d,%3d) %2d senders %s fires %-5s -> %s"
                      % (x, y, n, rs, NAME[rs[0]] if rs else "?", tl))
        # 12 senders = the full 4-cell band on all three floors; fewer never connects.
        thin = [r for r in rows if r[2] and r[2] != 12]
        say.verdict(not bad and not thin,
                    "%s -- %d miners, %d firing into a space belt, %d with a partial band"
                    % (os.path.basename(p), len(rows), len(rows) - len(bad), len(thin)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
