# ADR-0002: Classification is a pure function

**Status:** accepted

## Context

The classifier needs a run, its units, and each unit's history. The path of
least resistance is to let it fetch what it needs — pass a connection in, query
inside, return findings.

## Decision

`classify.py` imports only the standard library and `model.py`. It receives data
structures and returns findings. All I/O happens in the adapter, above it.

## Why

**Testability is the whole argument.** The taxonomy is a set of claims about what
the data means — that success-with-zero-items is alarming only if the unit has
produced before, that three consecutive 5xx is different from one. Each claim
needs a test, and each test needs to construct an awkward situation: a brand with
four good runs then a zero, a brand that has never produced anything. Fabricating
those as data structures is trivial. Fabricating them as database state is a
fixture harness nobody maintains.

Two consequences follow for free. The module can be lifted into a Lambda later,
where classification runs always-on in AWS while narration happens wherever the
model lives — the split ADR-0003 implies. And when a verdict is wrong there is
exactly one file to read, with no question of whether the bug is in the query.

## Cost

The adapter must fetch everything the classifier *might* need, including history
for units that turn out to be fine. At twenty units and ten runs that is two
hundred rows, which is nothing. At ten thousand units it would matter, and the
answer then is to narrow what the adapter fetches — not to move queries into the
classifier.
