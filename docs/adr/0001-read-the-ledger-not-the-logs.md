# ADR-0001: Read the run ledger, not the logs

**Status:** accepted

## Context

Sentinel needs to know what a pipeline did. There are two sources: the
structured ledger the pipeline writes about itself (`collection_run`,
`collection_run_brand`, `quarantine`), and the log lines it emits while running.

The obvious move is logs. Every monitoring product starts there, log platforms
are a mature market, and RateRadar already emits structured JSON specifically so
a log platform could filter on fields.

## Decision

Read the ledger. Treat logs as optional colour, not as input.

## Why

The ledger is a deliberate record; logs are a side effect. RateRadar's ledger
exists because ADR-0005 over there required that every outcome be recorded — so
`products_failed`, `products_quarantined` and `error_kind` are *designed* fields
with meanings someone chose. Log lines are whatever the code happened to print.

Parsing logs back into facts the ledger already holds is an expensive way to
lose fidelity. `status = 'partial'` with `products_failed = 4` is unambiguous;
recovering that from log text is a regex that breaks when someone rewords a
message.

It also sets the standard for what Sentinel can support. "Point it at a pipeline
that keeps an honest record of its runs" is a real requirement that rewards good
practice, and a more useful position than "point it at anything and hope".

## Cost

Sentinel cannot watch a pipeline that keeps no structured record, which rules out
a great many real pipelines. It also cannot see anything that happened *between*
ledger writes — a slow memory leak, a retry storm inside one unit — because the
ledger records outcomes, not behaviour.

If that becomes limiting, logs join as a *second* input for enrichment, not as a
replacement. The classifier's verdicts should never depend on a log line.
