#!/usr/bin/env python3
"""
stamp.py -- write a blueprint straight into a savegame. No mouse, no stamping.

    python tools/stamp.py SAVE.spz2 OUT.spz2 "blueprints/x.spz2bp" X Y [Z] [R]

The blueprint JSON and the savegame binary carry the SAME logical content, and the
mapping was verified cell-for-cell against a platform that exists in both (68
`Overflow` platforms, 315 buildings each): 314 of 315 buildings matched exactly,
and the one that did not was the label -- the only field where the two formats
genuinely differ.

    blueprint island   {X, Y, Z, R, T, S, C, B.Entries}
    savegame island    X, Y, Z, R, layout, icfg(=S), buildings

    blueprint building {X, Y, L, R, T, C}
    savegame building  X, Y, L, R, T, cfg(=C)          <- config bytes VERBATIM

The one exception is strings.  A savegame interns text into `strings.bin` and
refers to it by index; a blueprint inlines it as `u16 len + UTF-8`.  Two configs
carry text and must be re-encoded (`translate_config`):

    LabelDefaultInternalVariant       u16+utf8       ->  u32 strIdx
    ConstantSignal (kind 6, a shape)  06 01 01 u16+utf8 -> 06 01 01 u32 strIdx

### Rotation
Rotating an island by +1 rotates its contents:  (x, y) -> (N-1-y, x), R -> R+1,
where N = 20 * (tile span of the island along that axis).  Verified against the
same pair of platforms, which sit at R1 in the blueprint and R2 in the world.
"""
import struct, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import save_world as sw
from shapez_bp import decode_bp
from verify_mam import ISLAND_FOOTPRINT

TILE = 20


def gv(x):
    """Blueprint lists come as a plain list or as {'$values': [...]}"""
    if isinstance(x, dict):
        return x.get("$values", [])
    return x or []


def b64(c):
    import base64
    return base64.b64decode(c["$value"]) if c else None


# ------------------------------------------------------------- config translate
def translate_config(T, raw, intern):
    """Blueprint config bytes -> savegame config bytes."""
    if raw is None:
        return None
    if T == "LabelDefaultInternalVariant":
        n = struct.unpack_from("<H", raw, 0)[0]
        return struct.pack("<I", intern(raw[2:2 + n].decode("utf-8")))
    if T.startswith("ConstantSignal") and raw[:1] == b"\x06":
        n = struct.unpack_from("<H", raw, 3)[0]
        return raw[:3] + struct.pack("<I", intern(raw[5:5 + n].decode("utf-8")))
    return raw


def untranslate_config(T, raw, S):
    """savegame config bytes -> blueprint config bytes (the inverse)."""
    if raw is None:
        return None
    if T == "LabelDefaultInternalVariant":
        s = S[struct.unpack_from("<I", raw, 0)[0]].encode("utf-8")
        return struct.pack("<H", len(s)) + s
    if T.startswith("ConstantSignal") and raw[:1] == b"\x06":
        s = S[struct.unpack_from("<I", raw, 3)[0]].encode("utf-8")
        return raw[:3] + struct.pack("<H", len(s)) + s
    return raw


# -------------------------------------------------------------------- rotation
def island_span(T, R):
    """(width, height) of an island layout in tiles, from the footprint table."""
    fp = ISLAND_FOOTPRINT.get((T, R))
    if fp is None:
        return 1, 1
    xs = [d[0] for d in fp]; ys = [d[1] for d in fp]
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def rotate_buildings(bldgs, T, R, times):
    """Rotate an island's contents `times` x 90 degrees CW."""
    out = list(bldgs)
    w, h = island_span(T, R)
    for _ in range(times % 4):
        n = h * TILE                       # the axis that becomes the new X
        out = [dict(b, X=n - 1 - b["Y"], Y=b["X"], R=(b["R"] + 1) % 4) for b in out]
        w, h = h, w
    return out


# ------------------------------------------------------------------- occupancy
def island_cells(T, R, X, Y, Z):
    fp = ISLAND_FOOTPRINT.get((T, R))
    if fp is None:
        fp = ISLAND_FOOTPRINT.get((T, 1)) or [(0, 0)]
    return [(X + dx, Y + dy, Z) for dx, dy in fp]


def world_occupancy(w):
    occ = {}
    for c, ch in w["world"].items():
        for i in ch["islands"]:
            for cell in island_cells(i["layout"], i["R"], i["X"], i["Y"], i["Z"]):
                occ[cell] = i
    return occ


# ---------------------------------------------------------------------- adding
def add_islands(w, new_islands, check_overlap=True):
    """new_islands: dicts as produced by blueprint_islands(). Appends to whichever
    chunk still has buffer room, and appends the matching empty state record."""
    occ = world_occupancy(w) if check_overlap else {}
    for isl in new_islands:
        for cell in island_cells(isl["layout"], isl["R"], isl["X"], isl["Y"], isl["Z"]):
            if cell in occ:
                raise AssertionError("island %s at %s would overlap the existing %s"
                                     % (isl["layout"], cell, occ[cell]["layout"]))
            occ[cell] = isl

    # pick the chunk with the most free island-buffer space
    def free(c):
        k = "maps/main/islands/%d.bin" % c
        return len(w["entries"][k]) - len(w["entries"][k].rstrip(b"\x00"))

    target = max(w["world"], key=free)
    for isl in new_islands:
        w["world"][target]["islands"].append(isl)
        w["world"][target]["state"].append(dict(X=isl["X"], Y=isl["Y"], Z=isl["Z"],
                                                layout=isl["layout"], raw=None))
    return target


# ------------------------------------------------------------------- blueprint
def blueprint_islands(path, dX=0, dY=0, dZ=0, rot=0, intern=None):
    """Decode a blueprint into savegame-shaped island dicts at the given offset."""
    ver, bp = decode_bp(path)
    out = []
    for e in gv(bp["BP"]["Entries"]):
        T, R = e["T"], e["R"]
        bl = [dict(X=b["X"], Y=b["Y"], L=b["L"], R=b["R"], T=b["T"],
                   cfg=translate_config(b["T"], b64(b.get("C")), intern), extra=0)
              for b in gv(e.get("B", {}).get("Entries") if e.get("B") else [])]
        bl = rotate_buildings(bl, T, R, rot)
        x, y = e["X"], e["Y"]
        for _ in range(rot % 4):
            x, y = -y, x
        out.append(dict(X=x + dX, Y=y + dY, Z=e["Z"] + dZ, layout=T, R=(R + rot) % 4,
                        icfg=b64(e.get("S")), buildings=bl))
    return out


def next_backup(savedir):
    """The filename the game will consider newest."""
    import re, glob
    n = 0
    for p in glob.glob(os.path.join(savedir, "backup-v*.spz2")):
        m = re.search(r"backup-v(\d+)-", os.path.basename(p))
        if m:
            n = max(n, int(m.group(1)))
    return os.path.join(savedir, "backup-v%d-2026-9-05--12-00-00--1000001.spz2" % (n + 1))


if __name__ == "__main__":
    src, dst, bpf = sys.argv[1], sys.argv[2], sys.argv[3]
    X, Y = int(sys.argv[4]), int(sys.argv[5])
    Z = int(sys.argv[6]) if len(sys.argv) > 6 else 0
    R = int(sys.argv[7]) if len(sys.argv) > 7 else 0
    w = sw.read_world(src)
    S = w["strings"]; idx = {s: i for i, s in enumerate(S)}

    def intern(s):
        if s not in idx:
            idx[s] = len(S); S.append(s)
        return idx[s]

    isls = blueprint_islands(bpf, X, Y, Z, R, intern)
    chunk = add_islands(w, isls)
    n = sw.write_world(w, dst)
    print("stamped %d islands / %d buildings into chunk %d -> %s (%d islands total)"
          % (len(isls), sum(len(i["buildings"]) for i in isls), chunk, dst, n))
