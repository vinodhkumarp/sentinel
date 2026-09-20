# ADR-0003: Rules classify; the model only writes

**Status:** accepted

## Context

Sentinel is an "AI triage" tool. The tempting shape is to hand the raw ledger
rows and error text to a language model and ask what went wrong. That is the
version that demonstrates best in a single screenshot.

## Decision

Deterministic code decides everything that matters: what class of failure this
is, how severe it is, whether two findings are the same incident, and whether
anyone is told. A language model receives a *finished* structured incident and
writes two to four sentences about it.

The model is an enhancement and never a dependency. `--no-llm` produces the full
structured verdict. Tests never require a model to be installed.

## Why

**A diagnosis you cannot unit-test is not a diagnosis.** "Three consecutive 5xx
from the same endpoint is PERSISTENT_UPSTREAM at HIGH severity" is a claim that
can be checked, versioned, and argued about. "The model said it looked serious"
is not, and when it is wrong there is nothing to fix.

**Small local models are weak at exactly this.** The chosen runtime is Ollama on
a laptop. An 8B model writes a decent paragraph and reasons poorly about whether
an absent value is alarming. Asking it to do the part it is bad at, and not the
part it is good at, would be the wrong way round.

**Non-determinism in the alerting path is a bug.** Whether you are woken at 3am
should not vary between runs on identical input.

**It degrades honestly.** With no model available, Sentinel is a good rules-based
monitor. The reverse design degrades to nothing.

## Cost

Sentinel can only recognise failure classes someone has named. A genuinely novel
failure lands in a generic bucket, where an end-to-end model might have said
something insightful. The mitigation is that the taxonomy is cheap to extend and
each addition arrives with a test.

It is also a less impressive demo. A tool that reasons from raw logs looks more
like magic than one that applies a documented taxonomy. That trade is accepted:
the second one is right more often, and can explain why.
