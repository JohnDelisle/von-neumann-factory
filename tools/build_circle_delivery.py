#!/usr/bin/env python3
"""
build_circle_delivery.py -- VN-15.  The first machine Claude builds in the world
itself, with no stamping: mine `CuCuCuCu` and deliver it into the Vortex.

    python tools/build_circle_delivery.py SRC.spz2 [DST.spz2]

## The task
John broadcasts a goal shape on a wireless channel from a platform beside the "HI"
message.  Channel 123 carries `CuCuCuCu`, and `CuCuCuCu` is the one broadcast shape
this map can mine directly: `maps/main/resource-chunks.bin` puts circle patches on
island tiles (1,-1) (1,0) (1,1) (2,0) -- immediately east of the Vortex.

## The geometry, all of it extracted rather than guessed

    Vortex (Layout_HUB) origin (-1,0), 3x3 tiles, so it covers (-2..0, -1..1).
    Its island-local cells run -20..39; the CENTRE tile (local 0..19) is the
    vortex mouth itself.

Delivery, read cell-for-cell off John's 72.8h factory (which has 144 of these):

    BeltPortSender on the centre tile's own perimeter, pointing INWARD, is what
    feeds the vortex.  Nothing catches on the other side -- the vortex does.

The approach lane, likewise copied from that factory's east side:

    x=37   BeltPortReceiver  R2      <- edge port of hub tile (0,0), band y 8..11
    x=36..20  BeltDefaultForward R2  <- straight run west
    x=19   BeltPortSender    R2      <- into the vortex

## The machine

    (2,0)  Layout_ShapeMiner R2   -- 160 buildings cloned VERBATIM from the seven
                                     identical miners in the v13 sandbox, so the
                                     one part with real internal geometry is a copy
                                     of something that ran.  12 lanes out its west
                                     edge (x=2, y 8..11, floors 0-2).
    (1,0)  SpaceBelt_Forward  R2  -- one hop west into the Vortex's east face.
    HUB    +228 buildings          -- 12 lanes x (receiver + 17 belts + sender).

The miner is the low-risk half and the hub lanes are the hand-authored half, so a
single load tells us both whether the game accepts written buildings at all and
whether Claude's coordinate/rotation semantics are right.
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import save_world as sw

MINER_DONOR = (r"C:/Users/jdeli/AppData/LocalLow/tobspr Games/shapez 2/savegames/"
               r"d58e3f84-b198-411f-9f46-78fcbfe7dae4/"
               r"backup-v13-2026-9-05--02-25-08--6806500.spz2")

HUB_XY = (-1, 0)
BAND = (8, 9, 10, 11)          # the 4-lane edge port band
FLOORS = (0, 1, 2)


def miner_buildings(donor=MINER_DONOR):
    """The 160 buildings of a validated Layout_ShapeMiner, verbatim."""
    w = sw.read_world(donor)
    miners = [i for ch in w["world"].values() for i in ch["islands"]
              if i["layout"] == "Layout_ShapeMiner"]
    assert miners, "no Layout_ShapeMiner in the donor save"
    keys = {tuple(sorted((b["X"], b["Y"], b["L"], b["R"], b["T"]) for b in m["buildings"]))
            for m in miners}
    assert len(keys) == 1, "the donor's miners are not identical -- pick one deliberately"
    assert all(m["R"] == 2 for m in miners), "donor miners are not all R2"
    return [dict(b) for b in miners[0]["buildings"]]


def hub_delivery_lanes():
    """One straight delivery lane per band row per floor, east face into the vortex."""
    out = []
    for L in FLOORS:
        for y in BAND:
            out.append(dict(X=37, Y=y, L=L, R=2, T="BeltPortReceiverInternalVariant",
                            extra=0, cfg=None))
            for x in range(20, 37):
                out.append(dict(X=x, Y=y, L=L, R=2, T="BeltDefaultForwardInternalVariant",
                                extra=0, cfg=None))
            out.append(dict(X=19, Y=y, L=L, R=2, T="BeltPortSenderInternalVariant",
                            extra=0, cfg=None))
    return out


def build(src, dst):
    w = sw.read_world(src)
    S = w["strings"]; index = {s: i for i, s in enumerate(S)}

    def intern(s):
        if s not in index:
            index[s] = len(S); S.append(s)
        return index[s]

    islands = [i for ch in w["world"].values() for i in ch["islands"]]
    occupied = set()
    for i in islands:
        span = (3, 3) if i["layout"] == "Layout_HUB" else (1, 1)
        for dx in range(-(span[0] // 2), span[0] // 2 + 1):
            for dy in range(-(span[1] // 2), span[1] // 2 + 1):
                occupied.add((i["X"] + dx, i["Y"] + dy, i["Z"]))
    for cell in ((1, 0, 0), (2, 0, 0)):
        assert cell not in occupied, "%s is not free" % (cell,)

    # ---- 1. the Vortex feed, added to the existing HUB island
    hub = next(i for i in islands if i["layout"] == "Layout_HUB")
    assert (hub["X"], hub["Y"]) == HUB_XY, "hub moved: %s" % ((hub["X"], hub["Y"]),)
    assert not hub["buildings"], "the hub already carries %d buildings" % len(hub["buildings"])
    hub["buildings"] = hub_delivery_lanes()
    hub["name"] = intern("Vortex feed - Claude")

    # ---- 2. the miner, verbatim, plus a label so the write is visible at a glance
    mb = miner_buildings()
    text = "CLAUDE BUILT THIS".encode("utf-8")
    mb.append(dict(X=14, Y=16, L=0, R=2, T="LabelDefaultInternalVariant", extra=0,
                   cfg=struct.pack("<I", intern(text.decode("utf-8")))))
    miner = dict(X=2, Y=0, Z=0, layout="Layout_ShapeMiner", R=2, icfg=None,
                 buildings=mb, name=intern("CuCuCuCu miner - Claude"), name_s=None)

    # ---- 3. one space belt from the miner into the Vortex's east face
    belt = dict(X=1, Y=0, Z=0, layout="SpaceBelt_Forward", R=2, icfg=None,
                buildings=[], name=None, name_s=None)

    target = max(w["world"], key=lambda c: len(w["world"][c]["islands"]))
    for isl in (miner, belt):
        w["world"][target]["islands"].append(isl)
        w["world"][target]["state"].append(dict(X=isl["X"], Y=isl["Y"], Z=isl["Z"],
                                                layout=isl["layout"], raw=None))

    n = sw.write_world(w, dst)
    return n, len(hub["buildings"]), len(mb), target


def verify(dst, src):
    """Re-parse our own output before it goes anywhere near the save folder."""
    a = sw.read_world(src); b = sw.read_world(dst)
    na = sum(len(c["islands"]) for c in a["world"].values())
    nb = sum(len(c["islands"]) for c in b["world"].values())
    ba = sum(len(i["buildings"]) for c in a["world"].values() for i in c["islands"])
    bb = sum(len(i["buildings"]) for c in b["world"].values() for i in c["islands"])
    for c in a["world"]:
        assert len(b["world"][c]["islands"]) == len(b["world"][c]["state"]), \
            "chunk %d: islands and state records disagree" % c
        for x, y in zip(a["world"][c]["islands"], b["world"][c]["islands"]):
            assert (x["X"], x["Y"], x["Z"], x["layout"]) == (y["X"], y["Y"], y["Z"], y["layout"]), \
                "an original island moved in chunk %d" % c
    return na, nb, ba, bb


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src.replace(".spz2", "-OUT.spz2")
    n, nhub, nminer, target = build(src, dst)
    na, nb, ba, bb = verify(dst, src)
    print("wrote %s" % dst)
    print("  islands   %d -> %d   (+miner, +space belt, appended to chunk %d)" % (na, nb, target))
    print("  buildings %d -> %d   (hub feed %d, miner %d)" % (ba, bb, nhub, nminer))
    print("  every original island still present, in order, with its state record")
