#!/usr/bin/env python3
"""
save_world.py -- read and WRITE the full Shapez 2 world: islands AND the buildings
on them.  Supersedes save_islands.py (which could only write bare islands).

A `.spz2` is a ZIP.  The world lives in four kinds of entry:

    strings.bin                  intern table: layout ids, building variant ids,
                                 shape codes, label texts.  Referenced BY INDEX.
    maps/main/islands/<n>.bin    the islands *and their buildings*   <-- the world
    maps/main/buildings/<n>.bin  per-island RUNTIME STATE (cargo in flight).  An
                                 island whose belts are empty has a 30-byte record
                                 no matter how many buildings stand on it.
    savegame.json                StructureCount

Every buffer is zero-padded to max(256, next power of two >= used), so a rewrite
that grows the world just re-pads to the next size the game would have picked.

## The serializer's shape (this is the whole trick)

Everything is byte-packed little-endian with constant 4-byte marker words.  These
are the "BinaryDataCheckpoints" of savegame.json -- serializer magic, NOT checksums,
which is why hand-editing works at all.

    A = 54 0d 72 c4   opens a length-prefixed block:  A u32 N <N bytes> C
    C = 21 30 a4 84   closes a block
    E = 7c 6d 49 a4   opens a list:                   E u32 count <count items>
    I = 9a 02 21 b1   island record tag
    B = e5 8d a0 35   building record tag

### island record (islands/<n>.bin: u32 count, then `count` of these)

    I(4) | i32 X | i32 Y | i16 Z | i16 layoutStrIdx | i16 0 | u8 R | A-block:
        u8 hasIslandConfig | [A-block islandConfig]
        A-block:
            E | u32 nBuildings | nBuildings x building record
            [A-block: u32 islandNameStrIdx]         <- the platform's title

A bare island is 52 bytes.

### building record

    B(4) | i16 X | i16 Y | u8 L | u8 R | u16 variantStrIdx | u16 0 | u8 hasConfig
        | [A-block config]

15 bytes without a config.  X/Y are platform-local cells and are SIGNED -- a
multi-tile island records its origin tile, so the HUB (3x3, centred) holds
buildings from -20 to 39.  On a 1x1 the buildable window is 2..17.
L is the floor, R the rotation 0..3.

### known config blobs

    Label                 u32 strIdx                    (the text, interned)
    ConstantSignal        u8 kind, then:
                            3 -> i32 value              (integer, e.g. 123 = channel)
                            5 -> (nothing)              (null)
                            6 -> 01 01 u32 shapeStrIdx  (shape)
                            7 -> 01 u8 colourChar       ('r', 'g', 'b', ...)
    LogicGateCompare      u8 mode
    ControlledSignalRecv  00 00 00 02
"""
import json, struct, zipfile

A = bytes.fromhex("540d72c4")
C = bytes.fromhex("2130a484")
E = bytes.fromhex("7c6d49a4")
ITAG = bytes.fromhex("9a0221b1")
BTAG = bytes.fromhex("e58da035")

u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]


# ---------------------------------------------------------------- strings.bin
def read_strings(b):
    n = u32(b, 0); off = 4; out = []
    for _ in range(n):
        ln = u32(b, off); off += 4
        out.append(b[off:off + ln].decode("utf-8")); off += ln
    return out


def write_strings(S):
    out = struct.pack("<I", len(S))
    for s in S:
        e = s.encode("utf-8")
        out += struct.pack("<I", len(e)) + e
    return out


# ------------------------------------------------------------------- reading
def _block(buf, p):
    """Read an A-block at p. Returns (content, offset just past it)."""
    assert buf[p:p + 4] == A, "expected A at %d, got %s" % (p, buf[p:p + 4].hex())
    n = u32(buf, p + 4)
    assert buf[p + 8 + n:p + 12 + n] == C, "unclosed block at %d" % p
    return buf[p + 8:p + 8 + n], p + 12 + n


def parse_island_chunk(buf, S):
    n = u32(buf, 0); o = 4; out = []
    for k in range(n):
        assert buf[o:o + 4] == ITAG, "island %d @%d" % (k, o)
        X, Y = struct.unpack_from("<ii", buf, o + 4)
        Z, idx, zero = struct.unpack_from("<hhh", buf, o + 12)
        R = buf[o + 18]
        assert zero == 0
        body, end = _block(buf, o + 19)
        p = 0
        icfg = None
        if body[p]:
            p += 1
            icfg, p = _block(body, p)
        else:
            p += 1
        inner, p2 = _block(body, p)
        assert p2 == len(body), "island %d: %d trailing body bytes" % (k, len(body) - p2)
        assert inner[:4] == E
        cnt = u32(inner, 4); q = 8
        ents = []
        for i in range(cnt):
            assert inner[q:q + 4] == BTAG, "island %d building %d @%d" % (k, i, q)
            bx, by = struct.unpack_from("<hh", inner, q + 4)
            bl, br = inner[q + 8], inner[q + 9]
            d = struct.unpack_from("<H", inner, q + 10)[0]
            extra = struct.unpack_from("<H", inner, q + 12)[0]
            has = inner[q + 14]; q += 15
            cfg = None
            if has:
                cfg, q = _block(inner, q)
            ents.append(dict(X=bx, Y=by, L=bl, R=br, T=S[d], extra=extra, cfg=cfg))
        name = None
        if q < len(inner):
            nb, q = _block(inner, q)
            name = u32(nb, 0)
        assert q == len(inner), "island %d: %d trailing inner bytes" % (k, len(inner) - q)
        out.append(dict(X=X, Y=Y, Z=Z, layout=S[idx], R=R, icfg=icfg,
                        buildings=ents, name=name,
                        name_s=S[name] if name is not None else None))
        o = end
    return out, o


def parse_state_chunk(buf):
    """buildings/<n>.bin -- per-island runtime state, one record per island, in order."""
    n = u32(buf, 0); o = 4; out = []
    for k in range(n):
        X, Y = struct.unpack_from("<ii", buf, o)
        Z, idx, zero = struct.unpack_from("<hhh", buf, o + 8)
        assert zero == 0
        body, end = _block(buf, o + 14)
        out.append(dict(X=X, Y=Y, Z=Z, li=idx, body=body, raw=buf[o:end]))
        o = end
    return out, o


def read_world(path):
    with zipfile.ZipFile(path) as z:
        order = [i.filename for i in z.infolist()]
        entries = {n: z.read(n) for n in order}
    S = read_strings(entries["strings.bin"])
    chunks = sorted(int(n.split("/")[-1].split(".")[0])
                    for n in order if n.startswith("maps/main/islands/"))
    world = {}
    for c in chunks:
        isl, ie = parse_island_chunk(entries["maps/main/islands/%d.bin" % c], S)
        assert ie == len(entries["maps/main/islands/%d.bin" % c].rstrip(b"\x00"))
        st, se = parse_state_chunk(entries["maps/main/buildings/%d.bin" % c])
        assert len(isl) == len(st), "chunk %d: %d islands vs %d state" % (c, len(isl), len(st))
        world[c] = {"islands": isl, "state": st}
    return dict(path=path, order=order, entries=entries, strings=S, world=world)


# ------------------------------------------------------------------- writing
def _mkblock(content):
    return A + struct.pack("<I", len(content)) + content + C


def build_building(b, sidx):
    r = BTAG + struct.pack("<hhBBHH", b["X"], b["Y"], b["L"], b["R"],
                           sidx(b["T"]), b.get("extra", 0))
    cfg = b.get("cfg")
    return r + (b"\x01" + _mkblock(cfg) if cfg is not None else b"\x00")


def build_island(isl, sidx):
    inner = E + struct.pack("<I", len(isl["buildings"]))
    for b in isl["buildings"]:
        inner += build_building(b, sidx)
    if isl.get("name") is not None:
        inner += _mkblock(struct.pack("<I", isl["name"]))
    body = (b"\x01" + _mkblock(isl["icfg"])) if isl.get("icfg") is not None else b"\x00"
    body += _mkblock(inner)
    return (ITAG + struct.pack("<iihhh", isl["X"], isl["Y"], isl["Z"],
                               sidx(isl["layout"]), 0)
            + bytes([isl["R"]]) + _mkblock(body))


EMPTY_STATE_BODY = bytes.fromhex("0000008021 30a484".replace(" ", ""))[:4]


def build_state(rec, sidx):
    """An island with nothing in flight: 30 bytes."""
    if rec.get("raw") is not None:
        return rec["raw"]
    return (struct.pack("<iihhh", rec["X"], rec["Y"], rec["Z"], sidx(rec["layout"]), 0)
            + _mkblock(b"\x00\x00\x00\x80"))


def _fit(buf, cap, what):
    """Zero-pad to the capacity the GAME itself would have chosen.

    Every .bin entry in every save examined -- 166 of 166, across a 24-island
    sandbox, a 1,651-island one and the 17,291-island factory -- is padded to
    max(256, next power of two >= used).  So a buffer may grow past the size it
    arrived at; it just has to land on a size the game's own serializer would pick.
    `cap` is the size it arrived at, kept for the message when something is wrong."""
    want = max(256, 1 << max(8, (len(buf) - 1).bit_length()))
    assert want >= len(buf), "%s: %d bytes" % (what, len(buf))
    return buf + b"\x00" * (want - len(buf))


def write_world(w, dst):
    S = list(w["strings"])
    index = {s: i for i, s in enumerate(S)}

    def sidx(s):
        if s not in index:
            index[s] = len(S); S.append(s)
        return index[s]

    ent = dict(w["entries"])
    n_islands = 0
    for c, ch in sorted(w["world"].items()):
        ib = struct.pack("<I", len(ch["islands"]))
        for isl in ch["islands"]:
            ib += build_island(isl, sidx)
        sb = struct.pack("<I", len(ch["state"]))
        for st in ch["state"]:
            sb += build_state(st, sidx)
        ik = "maps/main/islands/%d.bin" % c
        bk = "maps/main/buildings/%d.bin" % c
        ent[ik] = _fit(ib, len(ent[ik]), ik)
        ent[bk] = _fit(sb, len(ent[bk]), bk)
        n_islands += len(ch["islands"])

    ent["strings.bin"] = _fit(write_strings(S), len(ent["strings.bin"]), "strings.bin")
    sg = json.loads(ent["savegame.json"])
    sg["StructureCount"] = n_islands
    ent["savegame.json"] = json.dumps(sg, indent=2).encode("utf-8")

    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name in w["order"]:
            z.writestr(name, ent[name])
    return n_islands


# ---------------------------------------------------------------- round-trip
def roundtrip_check(path):
    """Re-serialize every chunk from the parse and require byte-identical output."""
    w = read_world(path)
    S = list(w["strings"])
    index = {s: i for i, s in enumerate(S)}

    def sidx(s):
        assert s in index, s
        return index[s]

    bad = []
    for c, ch in sorted(w["world"].items()):
        ib = struct.pack("<I", len(ch["islands"]))
        for isl in ch["islands"]:
            ib += build_island(isl, sidx)
        orig = w["entries"]["maps/main/islands/%d.bin" % c]
        if ib != orig[:len(ib)] or orig[len(ib):].strip(b"\x00"):
            bad.append(c)
    return w, bad


if __name__ == "__main__":
    import sys
    w, bad = roundtrip_check(sys.argv[1])
    ni = sum(len(c["islands"]) for c in w["world"].values())
    nb = sum(len(i["buildings"]) for c in w["world"].values() for i in c["islands"])
    print("%d chunks, %d islands, %d buildings" % (len(w["world"]), ni, nb))
    print("round-trip: " + ("BYTE-IDENTICAL on every chunk" if not bad else "MISMATCH %s" % bad))
