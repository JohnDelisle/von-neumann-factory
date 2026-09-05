#!/usr/bin/env python3
"""
build_rect_delivery.py -- VN-17.  Mine `RuRuRuRu` and deliver it into the Vortex at
FULL SPACE BELT SPEED: four independent 12-lane bands = 48 lanes.

    python tools/build_rect_delivery.py SRC.spz2 [DST.spz2]

## Why this shape is cheap
`RuRuRuRu` is one of the shapes this map mines DIRECTLY -- no cutting, no
recombination, none of VN-16's stage-C problem.  `tools/resources.py` finds pure
`RuRuRuRu` island tiles hard against the Vortex:

    north cluster  (-2,-4) (-2,-3) (-1,-3) (-1,-2)
    south cluster  (-1, 2) (-2, 3) (-1, 3) (-2, 4)

(-1,-2) and (-1,-3) already carry VN-16's space belt, so six sites are free and we
need four -- one per band, because **one Layout_ShapeMiner = one space belt = 12
lanes**, and "full space belt" = 4 of them = 48 lanes.

## The Vortex, all twelve edges of it
The 3x3 `Layout_HUB` at (-1,0) has 12 outward tile edges; each carries one 4-lane
edge-port band per floor = 12 lanes, so 144 lanes in total.  Only the CENTRE tile's
own perimeter feeds the vortex mouth (senders sit at local x or y in 4..15), so the
eight off-axis edges have to jog inwards.

John's 72.8h factory has that wiring already built and proven: **4,272 buildings,
144 receivers, 144 senders, 192 belt corners**, with receivers at exactly the
edge-port band cells this map's geometry predicts.  So we do not author a jog: we
copy his hub feed verbatim.  It is a superset of the two bands the sandbox hub
already has -- VN-15's east-middle at (37,8..11) and VN-16's north-middle at
(8..11,-18) -- both of which appear unchanged in his receiver set.

## The four bands
    A  miner (-1, 2) R3  ->                                     hub (-1, 1) S
    B  miner (-2, 3) R3  -> F R3 (-2, 2)                     -> hub (-2, 1) S
    C  miner (-2,-3) R1  -> F R1 (-2,-2)                     -> hub (-2,-1) N
    D  miner (-1, 3) R1  -> L R1 (-1,4), L R0 (0,4),
                            F R3 (0,3), F R3 (0,2)           -> hub ( 0, 1) S

## Space belt turn semantics, derived from the eight distinct turns in this world
A `SpaceBelt_{Left,Right}Turn` at rotation R takes cargo travelling on heading R and
emits it on heading R-1 (Left) or R+1 (Right), headings being 0=+X east, 1=+Y south,
2=-X west, 3=-Y north.  Checked against all eight (layout, R) pairs present in the
sandbox by asking which neighbouring belt points in and which points out.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import save_world as sw
from build_circle_delivery import miner_buildings, check_sizes

HUB_XY = (-1, 0)
JOHNS_FACTORY = (r"C:/Users/jdeli/AppData/LocalLow/tobspr Games/shapez 2/savegames/"
                 r"5589333c-0f3b-4632-a804-45f1af1fd3ec")

MINERS = [(-1, 2, 3), (-2, 3, 3), (-2, -3, 1), (-1, 3, 1)]
BELTS = [(-2, 2, "SpaceBelt_Forward", 3),
         (-2, -2, "SpaceBelt_Forward", 1),
         (-1, 4, "SpaceBelt_LeftTurn", 1),
         (0, 4, "SpaceBelt_LeftTurn", 0),
         (0, 3, "SpaceBelt_Forward", 3),
         (0, 2, "SpaceBelt_Forward", 3)]

# The four edge-port bands this build lights up, and the two already in service.
# Asserted present in the donor hub so a different reference save cannot pass
# unnoticed, and re-asserted after the write so a band cannot vanish silently.
WANT_RECEIVERS = ([(x, 37, 3) for x in (8, 9, 10, 11)] +          # S of (-1, 1)
                  [(x, 37, 3) for x in (-12, -11, -10, -9)] +     # S of (-2, 1)
                  [(x, -18, 1) for x in (-12, -11, -10, -9)] +    # N of (-2,-1)
                  [(x, 37, 3) for x in (28, 29, 30, 31)])         # S of ( 0, 1)
KEEP_RECEIVERS = ([(37, y, 2) for y in (8, 9, 10, 11)] +          # VN-15, circles
                  [(x, -18, 1) for x in (8, 9, 10, 11)])          # VN-16, stars


def newest(d):
    fs = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".spz2")]
    return max(fs, key=os.path.getmtime)


def johns_hub_feed(path=None):
    """The 4,272-building, 144-lane vortex feed, read out of John's own factory."""
    w = sw.read_world(path or newest(JOHNS_FACTORY))
    hub = next(i for c in w["world"].values() for i in c["islands"]
               if i["layout"] == "Layout_HUB")
    b = [dict(x) for x in hub["buildings"]]
    rec = {(x["X"], x["Y"], x["R"]) for x in b if "Receiver" in x["T"]}
    snd = [x for x in b if "Sender" in x["T"]]
    assert len(rec) == 48 and len(snd) == 144, "donor hub is not the 144-lane feed"
    missing = [r for r in WANT_RECEIVERS + KEEP_RECEIVERS if r not in rec]
    assert not missing, "donor hub lacks edge bands %s" % missing
    assert all(x.get("cfg") is None for x in b), "donor hub has configured buildings"
    return b


def build(src, dst, donor_hub=None):
    w = sw.read_world(src)
    islands = [i for ch in w["world"].values() for i in ch["islands"]]

    occupied = set()
    for i in islands:
        span = 3 if i["layout"] == "Layout_HUB" else 1
        for dx in range(-(span // 2), span // 2 + 1):
            for dy in range(-(span // 2), span // 2 + 1):
                occupied.add((i["X"] + dx, i["Y"] + dy, i["Z"]))
    new = [(x, y) for x, y, _ in MINERS] + [(x, y) for x, y, _, _ in BELTS]
    assert len(set(new)) == len(new), "two new islands claim the same tile"
    for x, y in new:
        assert (x, y, 0) not in occupied, "tile (%d,%d) is not free" % (x, y)

    # ---- 1. the vortex feed: John's 144-lane wiring replaces our 2-band stub.
    hub = next(i for i in islands if i["layout"] == "Layout_HUB")
    assert (hub["X"], hub["Y"]) == HUB_XY, "hub moved: %s" % ((hub["X"], hub["Y"]),)
    old = len(hub["buildings"])
    hub["buildings"] = donor_hub if donor_hub is not None else johns_hub_feed()

    # ---- 2. four miners, 160 donor buildings each, aimed by island rotation.
    mb = miner_buildings()
    made = [dict(X=x, Y=y, Z=0, layout="Layout_ShapeMiner", R=r, icfg=None,
                 buildings=[dict(b) for b in mb]) for x, y, r in MINERS]
    made += [dict(X=x, Y=y, Z=0, layout=lay, R=r, icfg=None, buildings=[])
             for x, y, lay, r in BELTS]

    # Everything goes in the chunk that already holds the hub, not the biggest one.
    target = next(c for c, ch in w["world"].items()
                  if any(i is hub for i in ch["islands"]))
    for isl in made:
        w["world"][target]["islands"].append(isl)
        w["world"][target]["state"].append(dict(X=isl["X"], Y=isl["Y"], Z=isl["Z"],
                                                layout=isl["layout"], raw=None))
    sw.write_world(w, dst)
    return old, len(hub["buildings"]), len(made), target


def verify(dst, src):
    """Re-parse our own output before it goes anywhere near the game."""
    a = sw.read_world(src); b = sw.read_world(dst)
    for c in a["world"]:
        assert len(b["world"][c]["islands"]) == len(b["world"][c]["state"]), \
            "chunk %d: islands and state records disagree" % c
        for x, y in zip(a["world"][c]["islands"], b["world"][c]["islands"]):
            assert (x["X"], x["Y"], x["Z"], x["layout"]) == (y["X"], y["Y"], y["Z"], y["layout"]), \
                "an original island moved in chunk %d" % c
    bad = check_sizes(b)
    assert not bad, "island records violate the size law: %s" % bad[:5]
    hub = next(i for c in b["world"].values() for i in c["islands"]
               if i["layout"] == "Layout_HUB")
    rec = {(x["X"], x["Y"], x["R"]) for x in hub["buildings"] if "Receiver" in x["T"]}
    for r in WANT_RECEIVERS + KEEP_RECEIVERS:
        assert r in rec, "band %s did not survive the write" % (r,)
    n = {(i["X"], i["Y"]): (i["layout"], i["R"])
         for c in b["world"].values() for i in c["islands"]}
    for x, y, r in MINERS:
        assert n[(x, y)] == ("Layout_ShapeMiner", r), "miner (%d,%d) wrong" % (x, y)
    for x, y, lay, r in BELTS:
        assert n[(x, y)] == (lay, r), "belt (%d,%d) wrong" % (x, y)
    return (sum(len(c["islands"]) for c in a["world"].values()),
            sum(len(c["islands"]) for c in b["world"].values()))


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src.replace(".spz2", "-OUT.spz2")
    old, nhub, nnew, target = build(src, dst)
    na, nb = verify(dst, src)
    print("wrote %s" % dst)
    print("  hub feed   %d -> %d buildings (John's 144-lane wiring, verbatim)" % (old, nhub))
    print("  islands    %d -> %d  (+%d: 4 miners, 6 space belts, chunk %d)"
          % (na, nb, nnew, target))
    print("  4 bands x 12 lanes = 48 lanes of RuRuRuRu into the Vortex")
