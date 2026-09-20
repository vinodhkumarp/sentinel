"""The taxonomy, applied.

Pure functions: same inputs, same findings, no I/O, no model. This is the part
that decides whether something is wrong and how badly -- and it is deliberately
the part with no intelligence in it, because a diagnosis you cannot unit-test
is not a diagnosis (ADR-0003).
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import FailureClass, Finding, Run, Severity, UnitHistory, UnitRun

# Upstream's fault, and usually temporary.
_UPSTREAM_KINDS = frozenset({"timeout", "transport", "http_5xx"})


@dataclass(frozen=True)
class Thresholds:
    """Every number the classifier can argue about, in one place.

    Defaults are drawn from RateRadar running twice a day: three consecutive
    failures is a day and a half, which is long enough that it is no longer a
    blip and short enough to still be worth an alert.
    """

    persistent_after_failures: int = 3
    coverage_loss_ratio: float = 0.5  # produced less than half its usual
    coverage_loss_severe_ratio: float = 0.2
    stale_after_hours: float = 30.0
    min_history_for_baseline: int = 3


def classify_unit(
    unit: UnitRun,
    history: UnitHistory | None = None,
    thresholds: Thresholds | None = None,
) -> list[Finding]:
    """Everything wrong with one unit's contribution to one run."""
    t = thresholds or Thresholds()
    h = history or UnitHistory(unit_id=unit.unit_id)
    scope = f"unit:{unit.unit_id}"
    findings: list[Finding] = []

    if unit.status == "skipped_circuit_open":
        findings.append(
            Finding(
                FailureClass.CIRCUIT_OPEN,
                Severity.MEDIUM,
                scope,
                f"{unit.unit_name} skipped: circuit breaker open",
                "circuit open",
                {"consecutive_failures": h.consecutive_failures},
            )
        )
        return findings  # nothing else to say about a unit that never ran

    if unit.status == "failed":
        findings.append(_classify_failure(unit, h, t, scope))
    elif unit.status == "partial":
        findings.append(
            Finding(
                FailureClass.PARTIAL_DEGRADATION,
                Severity.MEDIUM,
                scope,
                f"{unit.unit_name}: {unit.items_failed} of {unit.items_seen} items failed",
                unit.error_detail or unit.error_kind or "partial",
                {
                    "items_seen": unit.items_seen,
                    "items_failed": unit.items_failed,
                    "error_kind": unit.error_kind,
                },
            )
        )

    # Reported success and produced nothing. Whether that is alarming depends
    # entirely on whether it ever produced anything before.
    if unit.status == "ok" and unit.items_seen == 0:
        ever_produced = any(n > 0 for n in h.recent_items_seen)
        if ever_produced:
            findings.append(
                Finding(
                    FailureClass.SILENT_ZERO,
                    Severity.HIGH,
                    scope,
                    f"{unit.unit_name} reported success but returned nothing",
                    "silent zero after previously producing items",
                    {"typical_items": h.typical_items, "requests": unit.requests},
                )
            )
        else:
            findings.append(
                Finding(
                    FailureClass.NEVER_PRODUCED,
                    Severity.LOW,
                    scope,
                    f"{unit.unit_name} is enabled but has never returned anything",
                    "never produced any items",
                    {"runs_observed": len(h.recent_items_seen) + 1},
                )
            )

    if unit.items_quarantined > 0:
        findings.append(
            Finding(
                FailureClass.SCHEMA_DRIFT,
                Severity.HIGH,
                scope,
                f"{unit.unit_name}: {unit.items_quarantined} payloads would not parse",
                "payloads failed validation",
                {"items_quarantined": unit.items_quarantined},
            )
        )

    coverage = _classify_coverage(unit, h, t, scope)
    if coverage:
        findings.append(coverage)

    if (
        unit.protocol_version is not None
        and h.previous_protocol_version is not None
        and unit.protocol_version != h.previous_protocol_version
    ):
        findings.append(
            Finding(
                FailureClass.VERSION_DRIFT,
                Severity.LOW,
                scope,
                f"{unit.unit_name} negotiated v{unit.protocol_version}, "
                f"was v{h.previous_protocol_version}",
                "protocol version changed",
                {"from": h.previous_protocol_version, "to": unit.protocol_version},
            )
        )

    return findings


def _classify_failure(unit: UnitRun, h: UnitHistory, t: Thresholds, scope: str) -> Finding:
    signature = unit.error_detail or unit.error_kind or "failed"
    kind = unit.error_kind
    # +1: this run's failure is not yet in history.
    consecutive = h.consecutive_failures + 1
    evidence = {
        "error_kind": kind,
        "consecutive_failures": consecutive,
        "items_seen": unit.items_seen,
    }

    if kind == "http_4xx":
        # Upstream is answering correctly; we are asking wrongly. Ours to fix,
        # and it will not resolve itself, so it outranks a 5xx.
        return Finding(
            FailureClass.CLIENT_ERROR,
            Severity.HIGH,
            scope,
            f"{unit.unit_name} rejected our request ({kind})",
            signature,
            evidence,
        )

    if kind == "version":
        return Finding(
            FailureClass.VERSION_NEGOTIATION,
            Severity.HIGH,
            scope,
            f"{unit.unit_name}: could not agree a protocol version",
            signature,
            evidence,
        )

    if kind in _UPSTREAM_KINDS and consecutive >= t.persistent_after_failures:
        return Finding(
            FailureClass.PERSISTENT_UPSTREAM,
            Severity.HIGH,
            scope,
            f"{unit.unit_name} has failed {consecutive} runs in a row ({kind})",
            signature,
            evidence,
        )

    if kind in _UPSTREAM_KINDS:
        return Finding(
            FailureClass.TRANSIENT_UPSTREAM,
            Severity.LOW,
            scope,
            f"{unit.unit_name} failed ({kind})",
            signature,
            evidence,
        )

    return Finding(
        FailureClass.PERSISTENT_UPSTREAM
        if consecutive >= t.persistent_after_failures
        else FailureClass.TRANSIENT_UPSTREAM,
        Severity.MEDIUM,
        scope,
        f"{unit.unit_name} failed ({kind or 'unknown'})",
        signature,
        evidence,
    )


def _classify_coverage(unit: UnitRun, h: UnitHistory, t: Thresholds, scope: str) -> Finding | None:
    """Produced meaningfully less than usual, while claiming to be fine.

    Only judged for units that succeeded: a partial or failed run already has a
    finding, and reporting the shortfall again would be the same news twice.
    Zero is left to SILENT_ZERO, which can say something more specific.
    """
    if unit.status != "ok" or unit.items_seen == 0:
        return None
    if len(h.recent_items_seen) < t.min_history_for_baseline:
        return None
    baseline = h.typical_items
    if not baseline:
        return None

    ratio = unit.items_seen / baseline
    if ratio >= t.coverage_loss_ratio:
        return None

    return Finding(
        FailureClass.COVERAGE_LOSS,
        Severity.HIGH if ratio < t.coverage_loss_severe_ratio else Severity.MEDIUM,
        scope,
        f"{unit.unit_name} returned {unit.items_seen} items, usually {baseline}",
        "item count fell well below its baseline",
        {"items_seen": unit.items_seen, "baseline": baseline, "ratio": round(ratio, 3)},
    )


def classify_run(run: Run, units: list[UnitRun]) -> list[Finding]:
    """Problems that belong to the run as a whole rather than any one unit."""
    findings: list[Finding] = []

    if run.status == "failed":
        findings.append(
            Finding(
                FailureClass.RUN_FAILED,
                Severity.CRITICAL,
                "run",
                f"Run {run.run_id} did not complete",
                "run failed",
                {"trigger": run.trigger, "code_version": run.code_version},
            )
        )

    # Every unit failing is almost never every upstream failing at once. It is
    # nearly always us: credentials, egress, a bad deploy.
    if units and all(u.status == "failed" for u in units):
        findings.append(
            Finding(
                FailureClass.TOTAL_OUTAGE,
                Severity.CRITICAL,
                "run",
                f"All {len(units)} units failed in run {run.run_id}",
                "every unit failed in one run",
                {"units_total": len(units), "code_version": run.code_version},
            )
        )

    return findings


def classify(
    run: Run,
    units: list[UnitRun],
    histories: dict[str, UnitHistory] | None = None,
    thresholds: Thresholds | None = None,
) -> list[Finding]:
    """Everything wrong with one run, most severe first."""
    histories = histories or {}
    findings = classify_run(run, units)
    for unit in units:
        findings.extend(classify_unit(unit, histories.get(unit.unit_id), thresholds))
    return sorted(findings, key=lambda f: f.sort_key())
