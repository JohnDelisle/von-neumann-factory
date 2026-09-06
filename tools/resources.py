#!/usr/bin/env python3
"""
resources.py -- what this map can actually make, read from `maps/main/resource-chunks.bin`.

    python tools/resources.py SAVE.spz2 [SHAPE ...]

Answers the question that decides every build: *is the requested shape reachable
from anything on this map, and where?*

## The file, and the trap in it

    u32 nChunks
    per chunk:  CH(4) | i32 chunkX | i32 chunkY | A-block of:
                    SH(4) | u32 nPatches | patches
                    FL(4) | u32 nPatches | fluid patches
                C(4)

    shape patch  u8 1 | i32 X | i32 Y | u16 0 | i32 n
                 | n x i32 shapeStrIdx | n x (i32 dx, i32 dy)
    fluid patch  u8 1 | i32 X | i32 Y | u16 0 | u8 1 | u8 colour | i32 n
                 | n x (i32 dx, i32 dy)

Tiles are `(X+dx, Y+dy)`.  Note the shape array is PER TILE -- one patch can mix
shapes -- while a fluid patch has a single colour for the whole patch.

**The trap:** the leading u32 is the number of CHUNKS, not a version or a section
count.  Reading only the first chunk makes a map look nearly empty, and made me tell
John that a goal shape had no source anywhere when the real answer was "that region
has never been generated".

**A chunk is 64x64 island tiles and only exists once the game has generated it** --
in practice, once something has been built there.  The same sandbox went from 8
chunks (MAM sprawling to x=-100) to 2 after being cleared back to spawn, and two
shape types vanished with the chunks that held them.  So an absent shape means
"not generated yet", never "not on this map".  To reveal a region, build in it.
"""
import struct, sys, zipfile, os
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from save_world import read_strings

A = bytes.fromhex("540d72c4"); C = bytes.fromhex("2130a484")
CH = bytes.fromhex("ee7446a6"); SH = bytes.fromhex("da7cf209"); FL = bytes.fromhex("513a4716")
CHUNK_TILES = 64


import say


def read_resources(path):
    z = zipfile.ZipFile(path)
    S = read_strings(z.read("strings.bin"))
    b = z.read("maps/main/resource-chunks.bin")
    used = len(b.rstrip(b"\x00"))
    n = struct.unpack_from("<I", b, 0)[0]; o = 4
    chunks = {}
    for k in range(n):
        assert b[o:o + 4] == CH, "chunk %d @%d" % (k, o)
        cx, cy = struct.unpack_from("<ii", b, o + 4); o += 12
        assert b[o:o + 4] == A
        ln = struct.unpack_from("<I", b, o + 4)[0]; end = o + 8 + ln; p = o + 8
        assert b[p:p + 4] == SH
        ns = struct.unpack_from("<I", b, p + 4)[0]; p += 8
        tiles = []
        for _ in range(ns):
            X, Y = struct.unpack_from("<ii", b, p + 1)
            m = struct.unpack_from("<i", b, p + 11)[0]
            v = struct.unpack_from("<%di" % (m * 3), b, p + 15)
            for j in range(m):
                tiles.append((S[v[j]], X + v[m + 2 * j], Y + v[m + 2 * j + 1]))
            p += 15 + 12 * m
        assert b[p:p + 4] == FL
        nf = struct.unpack_from("<I", b, p + 4)[0]; p += 8
        fluids = []
        for _ in range(nf):
            X, Y = struct.unpack_from("<ii", b, p + 1)
            col = b[p + 11]
            m = struct.unpack_from("<i", b, p + 13)[0]
            v = struct.unpack_from("<%di" % (m * 2), b, p + 17)
            for j in range(m):
                fluids.append((col, X + v[2 * j], Y + v[2 * j + 1]))
            p += 17 + 8 * m
        assert b[p:p + 4] == C, "chunk %d close" % k
        p += 4
        assert p == end + 4, "chunk %d: %d trailing" % (k, end + 4 - p)
        chunks[(cx, cy)] = {"shapes": tiles, "fluids": fluids}
        o = end + 4
    assert o == used, "consumed %d of %d" % (o, used)
    return chunks


def quadrants(code):
    """A shape code is 4 quadrants of 2 chars, in order NE SE SW NW."""
    return [code[i:i + 2] for i in range(0, 8, 2)]


def sources_for(chunks, target):
    """Every patch shape that supplies at least one quadrant of `target`, best first.

    A uniform target like SuSuSuSu needs only ONE quadrant of the right kind: the MAM
    splits a shape into quadrants, keeps the ones it wants, rotates them into the four
    positions and stacks.  So the figure of merit is how many of a patch shape's four
    quadrants are usable, and how many tiles of it exist."""
    want = set(q for q in quadrants(target) if q != "--")
    assert len(want) == 1, "sources_for handles uniform targets; got %s" % target
    q = want.pop()
    by = defaultdict(int)
    where = {}
    for tiles in (c["shapes"] for c in chunks.values()):
        for code, x, y in tiles:
            k = sum(1 for z in quadrants(code) if z == q)
            if k:
                by[code] += 1
                where.setdefault(code, []).append((x, y))
    return sorted(((code, sum(1 for z in quadrants(code) if z == q), n, where[code])
                   for code, n in by.items()), key=lambda r: (-r[1], -r[2]))


def main(path, targets):
    ch = read_resources(path)
    tiles = [t for c in ch.values() for t in c["shapes"]]
    print("%s" % os.path.basename(path))
    print("  %d generated chunks (64x64 island tiles each), %d shape tiles, %d fluid tiles"
          % (len(ch), len(tiles), sum(len(c["fluids"]) for c in ch.values())))
    for (cx, cy), c in sorted(ch.items()):
        xs = [x for _, x, _ in c["shapes"]]; ys = [y for _, _, y in c["shapes"]]
        span = ("x %d..%d  y %d..%d" % (min(xs), max(xs), min(ys), max(ys))) if xs else "no shape patches"
        say.detail("    chunk (%3d,%3d)  covers x %d..%d y %d..%d   %4d tiles   %s"
              % (cx, cy, cx * CHUNK_TILES - 32, cx * CHUNK_TILES + 31,
                 cy * CHUNK_TILES - 32, cy * CHUNK_TILES + 31, len(c["shapes"]), span))
    pres = Counter(s for s, _, _ in tiles).most_common()
    print("  SHAPES PRESENT: %d distinct" % len(pres))
    say.some(pres, fmt=lambda r: "%-12s %5d tiles" % r, cap=6, label="more shapes")
    for t in targets:
        print("\n  SOURCES FOR %s" % t)
        rows = sources_for(ch, t)
        if not rows:
            print("    none in any GENERATED chunk -- build in an unexplored region to reveal more")
        for code, k, n, w in rows[:6]:
            xs = [p[0] for p in w]; ys = [p[1] for p in w]
            print("    %-12s %d/4 usable quadrants, %4d tiles   x %d..%d y %d..%d"
                  % (code, k, n, min(xs), max(xs), min(ys), max(ys)))


if __name__ == "__main__":
    a = say.args()
    main(a[0], a[1:] or ["CuCuCuCu", "WuWuWuWu", "SuSuSuSu"])
