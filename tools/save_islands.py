#!/usr/bin/env python3
"""
save_islands.py -- read and WRITE islands directly in a Shapez 2 savegame.

A `.spz2` is a ZIP. Two of its entries matter here, both fixed-capacity buffers of
custom binary (the trailing space is zero padding):

  maps/main/islands/<n>.bin    u32 count, then `count` island records
  maps/main/buildings/<n>.bin  u32 count, then `count` per-island building records

ISLAND RECORD (EXTRACTED 2026-09-05 by diffing an empty sandbox world against a
populated one; every field cross-checked on both):

    off size  field
     0   4    0xb121029a          constant tag -- also how records are located
     4   4    int32  X            island-grid coordinate
     8   4    int32  Y
    12   2    int16  Z
    14   2    int16  string index into strings.bin  -> the island layout id
    16   2    (zero)
    18   1    uint8  rotation     0..3
    19  33    constant scaffolding

A bare island (no buildings on it) is EXACTLY 52 bytes; 77 of the 86 islands in the
reference world are. The 36-byte tail is type-INDEPENDENT: across every bare island
type there are only three distinct tails and they differ in the single rotation byte.
That is what makes writing safe without decoding the rest -- we clone a known-good
record and retarget it.

BUILDINGS RECORD for an island with no buildings is exactly 30 bytes:
    int32 X, int32 Y, int16 Z, int16 strIdx, int16 zero, then the constant
    54 0d 72 c4 04 00 00 00 00 00 00 80 21 30 a4 84
(confirmed on the empty world's Layout_HUB and on all 9 empty islands of the
populated one). Those repeated 54 0d 72 c4 / 21 30 a4 84 words are the serializer's
"binary data checkpoints" (`savegame.json: BinaryDataCheckpoints: true`) -- constant
magic, not computed checksums, which is why cloning works.

We APPEND after the first record rather than at the end of the used region, because
the final record's true length may include meaningful trailing zeros. Total entry
length is preserved by trimming an equal number of pad bytes.
"""
import json, struct, zipfile, io, collections

TAG = b"\x9a\x02\x21\xb1"
ISLAND_REC = 52
EMPTY_BUILDINGS_TAIL = bytes.fromhex("540d72c404000000000000802130a484")


def read_strings(b):
    n = struct.unpack_from("<I", b, 0)[0]; off = 4; out = []
    for _ in range(n):
        ln = struct.unpack_from("<I", b, off)[0]; off += 4
        out.append(b[off:off + ln].decode("utf-8")); off += ln
    return out


def island_offsets(isl):
    offs, i = [], 4
    while True:
        j = isl.find(TAG, i)
        if j < 0:
            return offs
        offs.append(j); i = j + 4


def parse_islands(isl, S):
    out = []
    for o in island_offsets(isl):
        x, y = struct.unpack_from("<ii", isl, o + 4)
        z, idx = struct.unpack_from("<hh", isl, o + 12)
        out.append({"off": o, "X": x, "Y": y, "Z": z, "idx": idx,
                    "layout": S[idx] if 0 <= idx < len(S) else f"?{idx}",
                    "R": isl[o + 18]})
    return out


def make_island_record(template, X, Y, Z, idx, R):
    r = bytearray(template)
    struct.pack_into("<ii", r, 4, X, Y)
    struct.pack_into("<hh", r, 12, Z, idx)
    r[18] = R
    return bytes(r)


def make_buildings_record(X, Y, Z, idx):
    return struct.pack("<iihhh", X, Y, Z, idx, 0) + EMPTY_BUILDINGS_TAIL


def splice(buf, at, blob, bump_count):
    """Insert `blob` at `at`, keep the buffer's total length, bump the u32 count."""
    tail_pad = len(buf) - len(buf.rstrip(b"\x00"))
    if tail_pad < len(blob):
        raise AssertionError(f"not enough padding: need {len(blob)}, have {tail_pad}")
    out = bytearray(buf[:at] + blob + buf[at:])
    del out[len(buf):]                       # trim from the zero tail
    assert len(out) == len(buf)
    struct.pack_into("<I", out, 0, struct.unpack_from("<I", out, 0)[0] + bump_count)
    return bytes(out)


def add_islands(src_spz2, dst_spz2, new_islands, chunk="0"):
    """new_islands: list of (layout_name, X, Y, Z, R). Returns a summary dict."""
    with zipfile.ZipFile(src_spz2) as z:
        entries = {i.filename: z.read(i.filename) for i in z.infolist()}
        order = [i.filename for i in z.infolist()]
    S = read_strings(entries["strings.bin"])
    ik, bk = f"maps/main/islands/{chunk}.bin", f"maps/main/buildings/{chunk}.bin"
    isl, bld = entries[ik], entries[bk]
    islands = parse_islands(isl, S)

    idx_of = {name: i for i, name in enumerate(S)}
    # a 52-byte bare record to clone the scaffolding from
    offs = [r["off"] for r in islands]
    bare = next(o for o, nxt in zip(offs, offs[1:]) if nxt - o == ISLAND_REC)
    template = isl[bare:bare + ISLAND_REC]

    occupied = {(r["X"], r["Y"], r["Z"]) for r in islands}
    irecs, brecs = b"", b""
    placed = []
    for name, X, Y, Z, R in new_islands:
        if name not in idx_of:
            raise AssertionError(f"{name!r} is not in this save's string table; "
                                 f"pick a layout already present, or extend strings.bin")
        if (X, Y, Z) in occupied:
            raise AssertionError(f"({X},{Y},{Z}) already has an island")
        occupied.add((X, Y, Z))
        i = idx_of[name]
        irecs += make_island_record(template, X, Y, Z, i, R)
        brecs += make_buildings_record(X, Y, Z, i)
        placed.append((name, X, Y, Z, R))

    n = len(new_islands)
    entries[ik] = splice(isl, offs[0] + ISLAND_REC, irecs, n)
    # buildings records are in island order; island #0's record is the 30-byte header
    h0 = struct.pack("<iihh", islands[0]["X"], islands[0]["Y"], islands[0]["Z"], islands[0]["idx"])
    b0 = bld.find(h0, 4)
    assert b0 >= 0, "could not locate island #0 in buildings.bin"
    entries[bk] = splice(bld, b0 + 30, brecs, n)

    sg = json.loads(entries["savegame.json"])
    sg["StructureCount"] = sg.get("StructureCount", 0) + n
    entries["savegame.json"] = json.dumps(sg, indent=2).encode("utf-8")

    with zipfile.ZipFile(dst_spz2, "w", zipfile.ZIP_DEFLATED) as z:
        for name in order:
            z.writestr(name, entries[name])
    return {"placed": placed, "islands_before": len(islands), "strings": len(S)}
