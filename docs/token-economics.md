# What our sessions cost, and why

_Measured 2026-09-05 from the seven Claude Code transcripts in
`~/.claude/projects/…von-neumann-factory/*.jsonl`. Every assistant message carries a
`usage` record, so none of this is estimated. Re-run it any time:_

```
python tools/token_report.py          # totals, growth, attribution
python tools/token_report.py --top    # the biggest single tool results
```

## The one equation

> **Cost = (context size) × (turns).**

Every model call re-sends the entire conversation. So a chunk of context is not paid
for once — it is paid for by every call that comes after it. A 500-token paragraph
written at turn 100 of 700 is billed 600 more times. Nothing else in this project's
spend comes close to that effect.

## The numbers (first seven sessions)

| | |
|---|---|
| model calls | **2,732** |
| input tokens read (cached) | **806,118,506** |
| cache writes | 19,072,326 |
| output | 5,026,016 |
| **average context per call** | **302k tokens** |

At Opus list prices ≈ **$1,944**, split **62% cache reads / 19% output / 18% cache
writes**. The dollar figure is a scale indicator, not a bill.

## Context only ever grows inside a session

| session | calls | ctx, first quarter | ctx, last quarter | share of that session's input spend |
|---|---|---|---|---|
| ad86a355 | 769 | 165k | **527k** | last quarter = 33% |
| 77e176e7 | 522 | 125k | **501k** | last quarter = 38% |
| 7968b076 | 297 | 148k | **466k** | last quarter = 37% |
| a5dd2fa2 | 313 | 116k | **415k** | last quarter = 40% |
| 40ddfdb9 | 650 | 150k | **316k** | last quarter = 33% |

**Every session spent about a third of its whole input budget on its last quarter of
turns** — the same work per turn at three to four times the price, purely because
everything earlier had to be re-read. This is the single cheapest thing to fix, and it
costs nothing but the discipline to stop.

## What fills the context

Weighted by how many later calls must re-read it:

| source | share | detail |
|---|---|---|
| **assistant prose** | **41.0%** | 2.18M chars over 2,732 messages. Long explanations are the largest line item in the project. |
| **Bash tool results** | **34.4%** | 934 results, avg 1,617 chars; worst singles ~30k — ad-hoc `python -c` dumps, `for` loops over islands, whole-file `cat`s. |
| attachments | 16.6% | prompt snapshots (629KB), edited-file re-injections (170KB), token reminders (124KB over 1,320 injections) |
| Read tool | 2.7% | 29 reads, 170KB — `conventions.md` alone was 21KB in one shot |

## What we changed on 2026-09-05

1. **`tools/brief.py`** — measured state in ~14 lines (game up?, newest save, delivered
   counts + rates, goals, active task), so a session no longer reads history to find
   out where it is.
2. **`docs/PROGRESS.md` split** — 1,138 lines → 169 current + `docs/history/` archive.
   Nothing deleted; verified line-by-line against `git show HEAD:docs/PROGRESS.md`.
3. **`CLAUDE.md`** — the read-first list became a start-a-session procedure, and
   `architecture.md` / `conventions.md` are now explicitly grep-references.
4. **`tools/token_report.py`** — this analysis, re-runnable, so the numbers stay honest.

## Standing rules

* **Batch experiments.** One restart discriminates between several hypotheses, never
  one. Sequential single-hypothesis builds is what burns a budget.
* **Stop at ~200k context.** Commit, update PROGRESS.md, hand off, clear.
* **Tools print verdicts, not data.** `PASS 118/118 islands, 0 rotation rewrites` beats
  a table. Anything piped through `head` afterwards was already paid for in full.
* **Prefer local deterministic code** over a model call — and over a subagent, which
  starts cold and re-derives context this project has already paid for.
* **Shorter answers.** The largest single line item is the assistant's own prose.
