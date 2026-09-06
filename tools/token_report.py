#!/usr/bin/env python3
"""
token_report.py -- what our sessions actually cost, and what filled the context.

    python tools/token_report.py            per-session totals + attribution
    python tools/token_report.py --top      also: the biggest single tool results

Reads the Claude Code transcripts under ~/.claude/projects/<this project>/*.jsonl.
Every assistant message carries a `usage` record, so none of this is estimated.

## The one equation

Cost = (context size) x (turns). Each model call re-sends the whole conversation, so
a 500-token paragraph written at turn 100 of 700 is paid for 600 more times. That is
why the attribution table below weights every chunk of context by the number of calls
that came AFTER it -- bytes alone under-rate anything written early.

The dollar figure uses Opus list prices and is a scale indicator, not a bill.
"""
import collections, glob, json, os, sys

PRICE = {"in": 15.0, "cache_w": 18.75, "cache_r": 1.5, "out": 75.0}   # $ per Mtok


def project_dirs():
    base = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    here = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
    hits = [d for d in glob.glob(os.path.join(base, "*")) if "von-neumann" in d]
    return hits or [d for d in glob.glob(os.path.join(base, "*")) if here in d]


def rows(path):
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            yield json.loads(line)
        except ValueError:
            continue


def text_of(content):
    """Flatten one message's content blocks to the text that occupies context."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    out = []
    for b in content:
        if not isinstance(b, dict):
            out.append(str(b)); continue
        t = b.get("type")
        if t == "text":         out.append(b.get("text", ""))
        elif t == "thinking":   out.append(b.get("thinking", ""))
        elif t == "tool_use":   out.append(json.dumps(b.get("input", {})))
        elif t == "tool_result":out.append(text_of(b.get("content", "")))
        else:                   out.append(json.dumps(b)[:200])
    return "\n".join(out)


def usage(files):
    per, tot = [], collections.Counter()
    for p in files:
        s = collections.Counter()
        for d in rows(p):
            if d.get("type") != "assistant":
                continue
            u = (d.get("message") or {}).get("usage") or {}
            if not u:
                continue
            s["calls"]   += 1
            s["in"]      += u.get("input_tokens", 0)
            s["cache_w"] += u.get("cache_creation_input_tokens", 0)
            s["cache_r"] += u.get("cache_read_input_tokens", 0)
            s["out"]     += u.get("output_tokens", 0)
        if s["calls"]:
            per.append((os.path.basename(p)[:8], s)); tot.update(s)
    return per, tot


def growth(p):
    """Context size at the start of a session vs at its end -- the cost of riding one
    session too long, which is invisible in a per-session total."""
    v = []
    for d in rows(p):
        if d.get("type") != "assistant":
            continue
        u = (d.get("message") or {}).get("usage") or {}
        if u:
            v.append(u.get("cache_read_input_tokens", 0) + u.get("input_tokens", 0)
                     + u.get("cache_creation_input_tokens", 0))
    if len(v) < 40:
        return None
    q = len(v) // 4
    return len(v), sum(v[:q]) / q, sum(v[-q:]) / q, sum(v[-q:]) / sum(v)


def attribution(files):
    """chars, and chars x later-calls, grouped by what produced them."""
    W, G, N = collections.Counter(), collections.Counter(), collections.Counter()
    big = []
    for p in files:
        rs = list(rows(p))
        ncalls = sum(1 for d in rs
                     if d.get("type") == "assistant" and (d.get("message") or {}).get("usage"))
        seen, names = 0, {}
        for d in rs:
            t = d.get("type")
            c = (d.get("message") or {}).get("content")
            if t == "assistant":
                if (d.get("message") or {}).get("usage"):
                    seen += 1
                for b in (c if isinstance(c, list) else []):
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        names[b.get("id")] = (b.get("name"), b.get("input", {}))
                key = "assistant prose"
            elif t == "user":
                key = "user / system msg"
                for b in (c if isinstance(c, list) else []):
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        nm, inp = names.get(b.get("tool_use_id"), ("?", {}))
                        key = "tool:" + str(nm)
                        sig = str(inp.get("command") or inp.get("file_path") or "")[:80]
                        big.append((len(text_of(b.get("content", ""))), nm, sig.replace("\n", " ")))
            elif t == "attachment":
                key, c = "attachments", json.dumps(d.get("attachment"))
            elif t == "system":
                key, c = "system", str(d.get("content", ""))
            else:
                continue
            n = len(text_of(c))
            G[key] += n; W[key] += n * (ncalls - seen); N[key] += 1
    return G, W, N, big


def main(argv):
    files = [f for d in project_dirs() for f in glob.glob(os.path.join(d, "*.jsonl"))]
    if not files:
        print("no transcripts found under ~/.claude/projects"); return 1
    per, tot = usage(files)
    per.sort(key=lambda kv: -kv[1]["cache_r"])

    print("SESSIONS (%d transcripts)" % len(per))
    print("  %-9s %6s %10s %11s %13s %10s %8s"
          % ("session", "calls", "fresh in", "cache wr", "cache rd", "out", "ctx/call"))
    for n, s in per:
        print("  %-9s %6d %10d %11d %13d %10d %8.0fk"
              % (n, s["calls"], s["in"], s["cache_w"], s["cache_r"], s["out"],
                 (s["cache_r"] + s["cache_w"] + s["in"]) / s["calls"] / 1000))
    print("  %-9s %6d %10d %11d %13d %10d %8.0fk"
          % ("TOTAL", tot["calls"], tot["in"], tot["cache_w"], tot["cache_r"], tot["out"],
             (tot["cache_r"] + tot["cache_w"] + tot["in"]) / tot["calls"] / 1000))
    cost = {k: tot[k] * v / 1e6 for k, v in PRICE.items()}
    print("  ~$%.0f at Opus list  (cache reads $%.0f / output $%.0f / cache writes $%.0f)"
          % (sum(cost.values()), cost["cache_r"], cost["out"], cost["cache_w"]))

    print()
    print("CONTEXT GROWTH INSIDE A SESSION")
    for p in sorted(files):
        g = growth(p)
        if g:
            print("  %-9s calls %4d   first quarter %5.0fk -> last quarter %5.0fk   "
                  "last quarter = %2.0f%% of the session's input"
                  % (os.path.basename(p)[:8], g[0], g[1] / 1000, g[2] / 1000, 100 * g[3]))

    G, W, N, big = attribution(files)
    twt = sum(W.values()) or 1
    print()
    print("WHAT FILLS THE CONTEXT (weighted by the calls that must re-read it)")
    print("  %-20s %7s %12s %8s" % ("source", "count", "chars", "share"))
    for k, v in W.most_common(8):
        print("  %-20s %7d %12d %7.1f%%" % (k, N[k], G[k], 100 * v / twt))

    if "--top" in argv:
        print()
        print("BIGGEST SINGLE TOOL RESULTS")
        for s, nm, sig in sorted(big, reverse=True)[:12]:
            print("  %8d  %-11s %s" % (s, nm, sig))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
