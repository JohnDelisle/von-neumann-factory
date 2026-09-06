#!/usr/bin/env python3
"""
say.py -- one verbosity rule for every read tool in this project.

    A tool's DEFAULT output fits in ~15 lines and ends in a verdict.
    Everything else moves behind `--full`.

## Why

Measured on 2026-09-05 (`docs/token-economics.md`): tool results were 34% of the
context weight of our sessions, and context is re-read by every later model call, so
a table printed once is paid for hundreds of times. A number that gets piped through
`head` afterwards was already paid for in full. Printing the verdict instead of the
evidence is the cheapest change available, and it is also the more honest one -- it
forces the tool to decide, rather than leaving a human to squint at rows.

Detail is never deleted, only deferred: `--full` restores every line.

    import say
    say.detail("one row of evidence")          # only under --full
    say.verdict(ok, "118/118 islands accepted")
    path = say.args()[0]                       # argv with the flags removed
"""
import sys

FLAGS = ("--full", "-v", "--verbose")
FULL = any(f in sys.argv for f in FLAGS)


def args(argv=None):
    """Positional arguments, flags removed."""
    return [a for a in (argv if argv is not None else sys.argv[1:]) if a not in FLAGS]


def detail(msg=""):
    """Evidence. Printed only when someone asked for it."""
    if FULL:
        print(msg)


def some(rows, fmt=str, cap=5, label="more"):
    """Print up to `cap` rows by default, all of them under --full, and always say
    how many were held back -- a hidden row that nobody is told about is a lie."""
    rows = list(rows)
    shown = rows if FULL else rows[:cap]
    for r in shown:
        print("      " + fmt(r))
    if len(rows) > len(shown):
        print("      (%d %s behind --full)" % (len(rows) - len(shown), label))


def verdict(ok, msg):
    """The last line a tool prints. Returns ok so it can be used inline."""
    print(("PASS  " if ok else "FAIL  ") + msg)
    return ok
