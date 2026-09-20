# Sentinel

Failure triage for data pipelines. Sentinel reads a pipeline's operational
record and answers three questions a `SELECT` cannot: **what kind of failure is
this, is it the same one as yesterday, and does a human need to care?**

That middle question is the project. Listing failures is trivial. Staying quiet
about the bank that has been returning 500s for nine days, while still catching
the genuinely new thing underneath it, is not.

Its first subject is [RateRadar](../rateradar), a collector that has been
running unattended against twenty Australian banks. Every failure class below
was observed there before it was named — this is a record of real failures, not
an imagined catalogue.

## What it does

```
run ledger  ─→  classify  ─→  fingerprint  ─→  incidents  ─→  narrate  ─→  deliver
(read-only)     (pure fn)     (grouping)       (step 2)      (step 3)     (step 4+)
```

**Classification is deterministic.** No model decides whether something is
wrong, how severe it is, or whether to alert. A language model's only job, when
one is available at all, is turning a finished structured incident into readable
prose. See [ADR-0003](docs/adr/0003-rules-classify-the-model-writes.md).

## Try it

```bash
make setup
cp .env.example .env          # point SENTINEL_SOURCE_DATABASE_URL at the ledger
sentinel explain 42           # classify one run
sentinel triage               # classify the most recent finished run
sentinel history --limit 20   # one line per recent run
```

`make check` runs everything CI runs: ruff, mypy, pytest.

## The taxonomy

| Class | Means |
|---|---|
| `SILENT_ZERO` | Reported success, produced nothing — having produced before |
| `NEVER_PRODUCED` | Enabled, never produced anything. A coverage gap, not an incident |
| `TRANSIENT_UPSTREAM` | Upstream 5xx / timeout / dropped connection, recently |
| `PERSISTENT_UPSTREAM` | ...and has kept doing it for several runs |
| `CLIENT_ERROR` | 4xx. Upstream is fine; we are asking wrongly |
| `VERSION_NEGOTIATION` | Could not agree a protocol version |
| `PARTIAL_DEGRADATION` | Some items failed, not all |
| `SCHEMA_DRIFT` | Payloads arrived and would not parse |
| `COVERAGE_LOSS` | Produced far fewer items than it usually does |
| `VERSION_DRIFT` | Negotiated a different protocol version than last time |
| `CIRCUIT_OPEN` | Skipped; its circuit breaker is open |
| `RUN_FAILED` | The run itself died — infrastructure, not upstream |
| `TOTAL_OUTAGE` | Every unit failed. Almost always ours, not theirs |

The distinctions are the point. `SILENT_ZERO` and `NEVER_PRODUCED` look
identical in the ledger — success, zero items — and only one is worth waking up
for. A 4xx outranks a 5xx because it is ours to fix and will not heal itself.

## Where things are

| Path | What |
|---|---|
| [`src/sentinel/model.py`](src/sentinel/model.py) | The vocabulary: runs, units, findings |
| [`src/sentinel/classify.py`](src/sentinel/classify.py) | The taxonomy, applied. Pure, no I/O |
| [`src/sentinel/fingerprint.py`](src/sentinel/fingerprint.py) | Grouping and noise suppression |
| [`src/sentinel/adapters/`](src/sentinel/adapters/) | Everything that knows about a specific pipeline |
| [`docs/architecture.md`](docs/architecture.md) | How it fits together, and why |
| [`docs/adr/`](docs/adr/) | The decisions, and what they cost |
| [`docs/roadmap.md`](docs/roadmap.md) | What is built and what is next |
