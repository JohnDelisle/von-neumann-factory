#!/usr/bin/env python3
"""
wiki_slurp.py -- mirror every article of https://shapez2.wiki.gg/ into gamedata/wiki/.

    python tools/wiki_slurp.py            # fetch all pages (skips ones already cached)
    python tools/wiki_slurp.py --refresh  # refetch everything

Uses the MediaWiki API (allpages, then parse&prop=wikitext), never page-by-page HTML.
Output: gamedata/wiki/<title>.txt (raw wikitext, first line is the title) and
gamedata/wiki/_index.json (title -> pageid, revid). Content is CC-BY-SA, see wiki.
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import say

API = "https://shapez2.wiki.gg/api.php"
OUT = os.path.join(os.path.dirname(__file__), "..", "gamedata", "wiki")
UA = "von-neumann-factory wiki mirror (github.com/JohnDelisle/von-neumann-factory)"


def get(params, tries=6):
    """One API call; backs off on 429 (the wiki rate-limits ~1 req/s)."""
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    wait = 3.0
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == tries - 1:
                raise
            time.sleep(wait)
            wait *= 2


def all_pages():
    pages, cont = [], {}
    while True:
        d = get(dict(action="query", list="allpages", aplimit=500, **cont))
        pages += d["query"]["allpages"]
        if "continue" not in d:
            return pages
        cont = d["continue"]


def safe(title):
    return re.sub(r'[\/:*?"<>|]', "_", title)


def main():
    refresh = "--refresh" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    pages = all_pages()
    index, fetched, cached, failed = {}, 0, 0, []
    for p in pages:
        title = p["title"]
        path = os.path.join(OUT, safe(title) + ".txt")
        if os.path.exists(path) and not refresh:
            cached += 1
            index[title] = {"pageid": p["pageid"], "file": os.path.basename(path)}
            continue
        try:
            d = get(dict(action="parse", page=title, prop="wikitext|revid"))
            text = d["parse"]["wikitext"]["*"]
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("= %s =\n" % title)
                f.write(text if text.endswith("\n") else text + "\n")
            index[title] = {"pageid": p["pageid"], "revid": d["parse"].get("revid"),
                            "file": os.path.basename(path)}
            fetched += 1
            say.detail("fetched %s (%d chars)" % (title, len(text)))
            time.sleep(1.5)
        except Exception as e:  # noqa
            failed.append("%s: %s" % (title, e))
    with open(os.path.join(OUT, "_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1, sort_keys=True)
    for x in failed:
        print("  FAIL " + x.encode("ascii", "replace").decode())
    say.verdict(not failed, "%d pages: %d fetched, %d cached, %d failed -> gamedata/wiki/"
                % (len(pages), fetched, cached, len(failed)))


if __name__ == "__main__":
    main()
