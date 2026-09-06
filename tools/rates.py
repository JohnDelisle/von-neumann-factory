#!/usr/bin/env python3
"""
rates.py -- build and check gamedata/rates.json, the one table of building facts.

    python tools/rates.py            # (re)build rates.json, print the verdict
    python tools/rates.py --full     # ...plus every row and the open questions for John

Sources, in priority order for `lane_fraction`:
  1. gamedata/rates_measured.json   -- measured in-game / stated by John   (source "measured"/"john")
  2. gamedata/wiki_rates_draft.json -- items/s from the wiki mirror, divided by the wiki's belt
                                        speed at the same upgrade level   (source "wiki")
  3. nothing                         -- lane_fraction null, listed as an open question
Geometry (tiles, faces, footprint) always comes from the game's own
gamedata/basedata-v1138/buildings.json, never from prose.

rates.json is keyed by INTERNAL variant id (the id generators place), e.g.
"CutterHalfInternalVariant". Fields: building, tiles, footprint, inputs, outputs,
lane_fraction, per_lane, items_per_second, wiki_page, source, note.
"""
import json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
import say

ROOT = os.path.join(os.path.dirname(__file__), "..")
BUILDINGS = os.path.join(ROOT, "gamedata", "basedata-v1138", "buildings.json")
MEASURED = os.path.join(ROOT, "gamedata", "rates_measured.json")
WIKI = os.path.join(ROOT, "gamedata", "wiki_rates_draft.json")
OUT = os.path.join(ROOT, "gamedata", "rates.json")

# Buildings that never carry belt items: no lane_fraction is expected and they are
# not open questions. Anything with zero BeltInputs and zero BeltOutputs.
def moves_items(v):
    return bool(v.get("BeltInputs")) or bool(v.get("BeltOutputs"))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def footprint(tiles):
    xs = [t["X"] for t in tiles]; ys = [t["Y"] for t in tiles]; zs = [t["Z"] for t in tiles]
    return "%dx%dx%d" % (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, max(zs) - min(zs) + 1)


def faces(lst):
    return [[p["Position_L"]["X"], p["Position_L"]["Y"], p["Position_L"]["Z"], p["Direction_L"]]
            for p in (lst or [])]


def wiki_lookup(wiki, building_id):
    """Wiki page whose buildings_json_ids names this top-level building id."""
    for title, row in wiki.items():
        if title.startswith("_"):
            continue
        if building_id in (row.get("buildings_json_ids") or []):
            return title, row
    return None, None


def wiki_lane_fraction(row):
    """lane_fraction from the wiki when it states both a machine rate and belt speed."""
    if not row:
        return None
    lf = row.get("lane_fraction")
    return float(lf) if isinstance(lf, (int, float)) else None


def build():
    buildings = load(BUILDINGS)
    meas_all = load(MEASURED)
    measured, questions = meas_all["rows"], meas_all.get("questions", [])
    wiki = load(WIKI) if os.path.exists(WIKI) else {}
    out, n_meas, n_wiki, n_john, open_q = {}, 0, 0, 0, []
    for b in buildings:
        title, wrow = wiki_lookup(wiki, b["Id"])
        for v in b["InternalVariants"]:
            vid = v["Id"]
            row = {
                "building": b["Id"],
                "tiles": [[t["X"], t["Y"], t["Z"]] for t in v["Tiles"]],
                "footprint": footprint(v["Tiles"]),
                "inputs": faces(v.get("BeltInputs")),
                "outputs": faces(v.get("BeltOutputs")),
                "lane_fraction": None, "per_lane": None,
                "items_per_second": (wrow or {}).get("items_per_second"),
                "wiki_page": title,
                "source": None, "note": None,
            }
            m = next((r for r in measured if vid.startswith(r["prefix"])), None)
            if m:
                row.update(lane_fraction=m["lane_fraction"], source=m["source"], note=m["note"])
                if m["source"] == "measured": n_meas += 1
                elif m["source"] == "wiki": n_wiki += 1
                else: n_john += 1
            elif wiki_lane_fraction(wrow) is not None:
                row.update(lane_fraction=wiki_lane_fraction(wrow), source="wiki",
                           note=(wrow.get("rate_text") or "")[:160])
                n_wiki += 1
            elif moves_items(v):
                open_q.append(vid)
            if row["lane_fraction"]:
                row["per_lane"] = int(math.ceil(1.0 / row["lane_fraction"] - 1e-3))
            out[vid] = row
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    return out, n_meas, n_wiki, n_john, open_q, questions


def main():
    out, n_meas, n_wiki, n_john, open_q, questions = build()
    item_rows = [k for k, r in out.items() if r["inputs"] or r["outputs"]]
    for vid in item_rows:
        r = out[vid]
        say.detail("  %-44s %-6s lane=%-6s per_lane=%-4s %s" % (
            vid, r["footprint"], r["lane_fraction"], r["per_lane"], r["source"] or "OPEN"))
    if open_q or questions:
        say.detail("OPEN QUESTIONS FOR JOHN (one batched list):")
        for q in open_q:
            say.detail("  - %s: lane fraction unknown, wiki has no rate" % q)
        for q in questions:
            say.detail("  - " + q)
    say.verdict(True, "%d variants (%d move items): %d measured, %d from John, %d from wiki, %d open, %d questions for John -> gamedata/rates.json"
                % (len(out), len(item_rows), n_meas, n_john, n_wiki, len(open_q), len(questions)))


if __name__ == "__main__":
    main()
