#!/usr/bin/env python3
"""
verify_mam.py -- structural audit of a MAM assembly blueprint.

Run:  python tools/verify_mam.py "blueprints/reference/<file>.spz2bp" [...]

Checks the things that fail SILENTLY in-game -- a stamped machine looks fine and
just produces subtly wrong shapes:

  1. Every `Fancy A+B Side Overflow` unit is the LANE-FIXED version, cell for cell.
     A pre-fix copy stamped in by accident reintroduces the inner/outer lane-swap
     bug (docs/conventions.md).
  2. Every `Quaded Filter` is identical to the goal-driven reference, so no lane is
     running a stale preset-driven copy.
  3. Every Goal Receiver channel constant agrees -- a single mismatched channel
     leaves one lane deaf and silently starves a quadrant.
  4. Component ratios are self-consistent (one Demuxer and one Quad Splitter per
     filter; whole numbers of stacker clusters).
  5. No malformed building configs (the `$type` trap that makes the game discard
     the whole file).

Exit code 0 = all good, 1 = at least one FAIL.
"""
import base64, collections, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from shapez_bp import decode_bp
import build_modules as bm

gv = bm.gv


def cells(island):
    return {(e["X"], e["Y"], e["L"]): (e["T"], e["R"]) for e in gv(island["B"]["Entries"])}


def int_signals(island):
    """Every integer ConstantSignal value on an island (channel numbers)."""
    out = []
    for e in gv(island["B"]["Entries"]):
        if e["T"] == "ConstantSignalDefaultInternalVariant" and e.get("C"):
            raw = base64.b64decode(e["C"]["$value"])
            if raw[:1] == b"\x03" and len(raw) >= 5:
                out.append(int.from_bytes(raw[1:5], "little"))
    return out


def verify(path):
    name = os.path.basename(path)
    ver, d = decode_bp(path)
    isls = gv(d["BP"]["Entries"])
    total = sum(len(gv((i.get("B") or {}).get("Entries"))) for i in isls)
    print(f"\n=== {name}")
    print(f"    {len(isls)} islands, {total} buildings")

    fails = []

    def check(ok, msg):
        print(f"    [{'PASS' if ok else 'FAIL'}] {msg}")
        if not ok:
            fails.append(msg)

    FIXED = cells(bm.load_reference_island("Fancy A+B Side Overflow.spz2bp"))
    PREFIX = cells(bm.load_reference_island("Fancy A+B Side Overflow (pre-lane-fix).spz2bp"))
    GOALF = cells(bm.load_reference_island("For Claude Filter with Signal.spz2bp"))

    fancy = [i for i in isls if i["T"].startswith("Foundation_2x4") and "Fancy" in bm.label_texts(i)]
    good = sum(1 for i in fancy if cells(i) == FIXED)
    buggy = sum(1 for i in fancy if cells(i) == PREFIX)
    odd = len(fancy) - good - buggy
    check(buggy == 0 and odd == 0,
          f"Fancy A+B lane fix: {len(fancy)} units, {good} fixed, {buggy} PRE-FIX, {odd} unrecognised")

    stale = sum(1 for i in isls for L in bm.label_texts(i) if "SHIT" in L)
    check(stale == 0, f"stale bug-warning labels: {stale}")

    filt = [i for i in isls if i["T"] == "Foundation_1x4" and "Quaded Filter" in bm.label_texts(i)]
    same = sum(1 for i in filt if cells(i) == GOALF)
    check(filt and same == len(filt),
          f"Quaded Filters: {len(filt)}, {same} identical to the goal-driven reference")

    chans = collections.Counter(c for i in filt for c in int_signals(i))
    check(len(chans) == 1, f"Goal Receiver channels: {dict(chans)}")

    demux = sum(1 for i in isls if "Demuxer" in bm.label_texts(i))
    qsplit = sum(1 for i in isls if "Quad Splitter" in bm.label_texts(i))
    check(demux == len(filt) and qsplit == len(filt),
          f"component ratio: {qsplit} Quad Splitters / {demux} Demuxers / {len(filt)} filters")

    # a stacker cluster = 2x Foundation_2x2 + 1x Foundation_2x2_Flipped + 2x Fancy A+B
    n22 = sum(1 for i in isls if i["T"] == "Foundation_2x2")
    n22f = sum(1 for i in isls if i["T"] == "Foundation_2x2_Flipped")
    clusters = n22f
    check(n22 == 2 * clusters and len(fancy) == 2 * clusters,
          f"stacker clusters: {clusters} (from {n22} 2x2, {n22f} 2x2_Flipped, {len(fancy)} Fancy A+B)")
    if clusters and len(filt):
        print(f"           -> {clusters / (len(filt) / 4):.0f} clusters per 4-lane unit "
              f"({len(filt) // 4} unit(s))")

    bad = []
    for i in isls:
        for e in gv((i.get("B") or {}).get("Entries")):
            c = e.get("C")
            if c is not None and (not isinstance(c, dict) or "$type" not in c):
                bad.append((i.get("X"), i.get("Y"), e.get("T")))
    check(not bad, f"building configs well-formed (missing $type: {len(bad)})")

    return fails


if __name__ == "__main__":
    allfails = []
    for p in sys.argv[1:]:
        allfails += verify(p)
    print()
    if allfails:
        print(f"{len(allfails)} CHECK(S) FAILED")
        sys.exit(1)
    print("all checks passed")
