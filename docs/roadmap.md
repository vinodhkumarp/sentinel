# Sentinel — Roadmap

Each step ends in something demonstrable, and each is useful before the next
exists. The ordering rule: **nothing is built on top of a classifier that has
not been checked against real failures.**

## Step 1 — Classify (now)

- [x] Failure taxonomy, derived from failures RateRadar actually produced
- [x] Fingerprinting: identical problems collapse, different ones do not
- [x] Read-only adapter over RateRadar's run ledger
- [x] `sentinel explain <run_id>`, `sentinel triage`, `sentinel history`
- [ ] Run against the full ledger and check every verdict by hand

That last line is the gate. The taxonomy is a set of claims about what the data
means; until each has been checked against a run whose story is already known,
they are guesses with tests around them.

## Step 2 — Remember

- `sentinel` schema: `incident`, `incident_event`
- Open / recurring / resolved transitions
- New incidents are news; recurring ones are not

This is where noise suppression becomes real rather than theoretical. Until
Sentinel remembers, every run reports the same nine-day-old failure again.

## Step 3 — Narrate

- Ollama, local, optional
- Structured incident in, two to four sentences out
- `--no-llm` always works; tests never require a model

## Step 4 — Deliver

- `sentinel digest` — markdown, what changed since last time
- Slack webhook on **new** incidents only
- Grafana over the `sentinel` schema, rather than building a dashboard

## Step 5 — Generalise

A second adapter, for a pipeline that is not RateRadar — GitHub Actions run
history is the obvious candidate, being structurally different enough to force
real generality rather than a guess at it.

## Explicitly not doing

- Metrics collection. Prometheus exists and is better at it
- Log aggregation. Loki exists and is better at it
- Letting a language model decide severity or whether to alert (ADR-0003)
