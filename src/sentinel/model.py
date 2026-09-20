"""The vocabulary Sentinel reasons in.

Deliberately one step removed from RateRadar's own words: a *unit* is whatever
a run does work on -- a bank brand here, a table or a partition elsewhere --
and an *item* is whatever a unit produces. Nothing below imports a driver or
touches a network, so the classifier can be tested without a database and later
lifted into a Lambda without modification (ADR-0002).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any


class Severity(IntEnum):
    INFO = 10
    LOW = 20
    MEDIUM = 30
    HIGH = 40
    CRITICAL = 50


class FailureClass(StrEnum):
    """What kind of thing went wrong.

    Every member here was observed in RateRadar before it was named -- the
    taxonomy is a record of real failures, not an imagined catalogue.
    """

    # A unit reported success and produced nothing. The dangerous one: it looks
    # healthy on every dashboard that counts errors.
    SILENT_ZERO = "SILENT_ZERO"
    # Enabled, never produced anything, ever. A coverage gap, not an incident.
    NEVER_PRODUCED = "NEVER_PRODUCED"
    # Upstream returned 5xx / timed out / dropped the connection, recently.
    TRANSIENT_UPSTREAM = "TRANSIENT_UPSTREAM"
    # ... and has kept doing it for several consecutive runs.
    PERSISTENT_UPSTREAM = "PERSISTENT_UPSTREAM"
    # 4xx. Upstream is fine; we are asking wrongly.
    CLIENT_ERROR = "CLIENT_ERROR"
    # Could not agree a protocol version with upstream.
    VERSION_NEGOTIATION = "VERSION_NEGOTIATION"
    # Some items failed, not all.
    PARTIAL_DEGRADATION = "PARTIAL_DEGRADATION"
    # Payloads arrived but would not parse -- upstream changed shape.
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    # Produced far fewer items than it usually does.
    COVERAGE_LOSS = "COVERAGE_LOSS"
    # Negotiated a different protocol version than last time.
    VERSION_DRIFT = "VERSION_DRIFT"
    # Skipped because its circuit breaker is open.
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    # The run itself died -- infrastructure, not upstream.
    RUN_FAILED = "RUN_FAILED"
    # Every unit failed. Almost always ours, not theirs.
    TOTAL_OUTAGE = "TOTAL_OUTAGE"
    # Nothing has completed recently enough.
    STALE = "STALE"


@dataclass(frozen=True)
class Run:
    """One execution of the pipeline."""

    run_id: int
    status: str  # running | completed | failed
    started_at: datetime
    finished_at: datetime | None
    trigger: str
    code_version: str | None
    units_total: int
    units_ok: int
    units_failed: int


@dataclass(frozen=True)
class UnitRun:
    """What one unit did inside one run."""

    run_id: int
    unit_id: str
    unit_name: str
    status: str  # ok | partial | failed | skipped_circuit_open
    items_seen: int
    items_failed: int
    items_quarantined: int
    items_new: int
    requests: int
    duration_ms: int | None
    error_kind: str | None
    error_detail: str | None
    protocol_version: int | None


@dataclass(frozen=True)
class UnitHistory:
    """What this unit did before, newest first, excluding the run being judged.

    History is what separates "this is broken" from "this is how it always is".
    Without it, a unit that has legitimately never produced anything looks
    identical to one that stopped yesterday.
    """

    unit_id: str
    recent_statuses: tuple[str, ...] = ()
    recent_items_seen: tuple[int, ...] = ()
    previous_protocol_version: int | None = None

    @property
    def consecutive_failures(self) -> int:
        count = 0
        for status in self.recent_statuses:
            if status != "failed":
                break
            count += 1
        return count

    @property
    def typical_items(self) -> int | None:
        """Median of recent non-zero observations.

        Median rather than mean: one bad run should not drag the baseline down
        and mask the next one. Zeroes are excluded because a unit that was
        already broken must not lower the bar for noticing that it still is.
        """
        seen = sorted(n for n in self.recent_items_seen if n > 0)
        if not seen:
            return None
        return seen[len(seen) // 2]


@dataclass(frozen=True)
class Finding:
    """One classified problem, before any grouping or prose."""

    failure_class: FailureClass
    severity: Severity
    scope: str  # "unit:<id>" | "run" | "pipeline"
    title: str
    signature: str  # normalised; what makes two findings "the same problem"
    evidence: dict[str, Any] = field(default_factory=dict)

    def sort_key(self) -> tuple[int, str, str]:
        return (-int(self.severity), self.scope, self.failure_class.value)
