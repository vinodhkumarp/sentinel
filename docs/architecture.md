# Sentinel — Architecture

## The problem

A pipeline that records its failures honestly produces a table of failures. That
table is not an answer. After a week of twice-daily runs, RateRadar's ledger
holds the same three banks failing the same way, one bank that has quietly
returned nothing since it was enabled, and — somewhere in there — the one new
thing that actually matters.

Sentinel's job is to find that one thing and say it in a sentence.

## Shape

```
  source pipeline (read-only)
        │
        ▼
  adapters/rateradar.py ── the only module that knows RateRadar's tables
        │
        ▼  Run, UnitRun, UnitHistory        ← model.py: neutral vocabulary
        │
  classify.py ── pure functions, no I/O, no model
        │
        ▼  Finding
        │
  fingerprint.py ── identical problems collapse into one incident
        │
        ▼
  [step 2] incident store ── open / recurring / resolved
        │
        ▼
  [step 3] narrate ── Ollama, optional, prose only
        │
        ▼
  report.py / [step 4] digest, Slack, Grafana
```

## The three load-bearing decisions

**Classification is pure.** `classify.py` imports nothing but the standard
library and `model.py`. It takes data structures and returns findings. This buys
three things at once: the taxonomy is unit-testable against failures that really
happened; the module can be lifted into a Lambda later without modification; and
there is exactly one place to look when a verdict is wrong.

**The model never decides anything.** Severity, grouping and whether to alert are
all computed. A language model, when present, receives a finished incident and
writes prose about it. It cannot invent a diagnosis — only a clumsy sentence.
This is also what makes the project testable at all: prose is checked for shape,
diagnosis is checked for correctness, and they are checked separately.

**History is a first-class input.** Most of the taxonomy's interesting
distinctions are impossible without it. Success with zero items is either a
catastrophe or business as usual depending entirely on whether that unit has
ever produced anything. One 500 is weather; five in a row is a broken bank. The
baseline for "far fewer items than usual" is a median of recent non-zero runs —
median so that one bad run cannot drag the bar down and mask the next one.

## Vocabulary

`model.py` speaks of *runs*, *units* and *items* rather than runs, brands and
products. A unit is whatever a run does work on; an item is whatever a unit
produces. The translation happens in the adapter and nowhere else, so supporting
a second pipeline means writing a sibling module — not touching the classifier.

This is one step of abstraction, taken deliberately and not two. There is no
plugin system, no registry, no configuration language. Those are earned by a
second real adapter, not predicted before one exists.

## What Sentinel is not

Not a metrics system and not a log aggregator — Prometheus and Loki exist and are
better at both. Sentinel reads the *structured record a pipeline keeps about
itself*, which is a smaller and more opinionated input than either, and the
reason it can say something specific rather than draw a chart.
