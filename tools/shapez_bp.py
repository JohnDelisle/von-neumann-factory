#!/usr/bin/env python3
"""
shapez_bp.py — Shapez 2 blueprint (.spz2bp) and savegame (.spz2) codec.

Blueprint string envelope:  SHAPEZ2-<ver>-<base64(gzip(JSON))><suffix>
  where <suffix> is "$" (older) or "[]_2$" (current 1.2 game exports).
The base64 is standard (A-Za-z0-9+/ with = padding). We parse only the
leading base64 run so the trailing "[]_2" marker is ignored on decode.

Savegame .spz2 files are ZIP archives containing savegame.json, research.json,
local-player.json (JSON) plus several *.bin (custom binary) entries.
"""
import base64, gzip, json, re, io, zipfile

BP_RE = re.compile(r"SHAPEZ2-(\d+)-([A-Za-z0-9+/=]*)")

def decode_bp(text_or_path):
    s = text_or_path
    if "\n" not in s and s.strip().startswith("SHAPEZ2") is False:
        # treat as path
        with open(text_or_path, encoding="utf-8", errors="replace") as f:
            s = f.read()
    s = s.strip()
    m = BP_RE.match(s)
    if not m:
        raise ValueError("Not a SHAPEZ2 blueprint string")
    ver = int(m.group(1))
    raw = gzip.decompress(base64.b64decode(m.group(2)))
    return ver, json.loads(raw)

def encode_bp(ver, obj, suffix="[]_2$"):
    js = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
        g.write(js)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"SHAPEZ2-{ver}-{b64}{suffix}"

def read_save(path):
    """Return dict of {entry_name: bytes} from a .spz2 ZIP savegame."""
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}

if __name__ == "__main__":
    import sys
    ver, d = decode_bp(sys.argv[1])
    print(f"version={ver}")
    print(json.dumps(d, indent=1))
