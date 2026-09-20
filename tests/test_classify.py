"""The taxonomy, checked against failures that actually happened.

Every case below is a real RateRadar incident, which is the point of building
the collector first: these are not hypotheticals about what a pipeline might do.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sentinel.classify import Thresholds, classify, classify_unit
from sentinel.model import FailureClass, Run, Severity, UnitHistory, UnitRun

NOW = datetime(2026, 9, 20, 6, 17, tzinfo=UTC)


def unit(**kwargs: object) -> UnitRun:
    defaults: dict[str, object] = {
        "run_id": 1,
        "unit_id": "brand-1",
        "unit_name": "Test Bank",
        "status": "ok",
        "items_seen": 32,
        "items_failed": 0,
        "items_quarantined": 0,
        "items_new": 0,
        "requests": 40,
        "duration_ms": 1200,
        "error_kind": None,
        "error_detail": None,
        "protocol_version": 5,
    }
    defaults.update(kwargs)
    return UnitRun(**defaults)  # type: ignore[arg-type]


def classes(findings: list[object]) -> set[FailureClass]:
    return {f.failure_class for f in findings}  # type: ignore[attr-defined]


def only(findings: list[object], cls: FailureClass) -> object:
    matches = [f for f in findings if f.failure_class is cls]  # type: ignore[attr-defined]
    assert len(matches) == 1, f"expected exactly one {cls}, got {classes(findings)}"
    return matches[0]


# --- the HSBC case: success with nothing behind it --------------------------


def test_silent_zero_when_a_unit_that_used_to_produce_returns_nothing() -> None:
    history = UnitHistory("brand-1", recent_statuses=("ok",) * 3, recent_items_seen=(30, 31, 30))
    findings = classify_unit(unit(items_seen=0), history)
    finding = only(findings, FailureClass.SILENT_ZERO)
    assert finding.severity is Severity.HIGH  # type: ignore[attr-defined]
    assert finding.evidence["typical_items"] == 30  # type: ignore[attr-defined]


def test_a_unit_that_never_produced_is_a_coverage_gap_not_an_incident() -> None:
    history = UnitHistory("brand-1", recent_statuses=("ok",) * 5, recent_items_seen=(0, 0, 0, 0, 0))
    findings = classify_unit(unit(items_seen=0), history)
    finding = only(findings, FailureClass.NEVER_PRODUCED)
    # The distinction that matters: same observable, different problem, and
    # only one of them is worth waking up for.
    assert finding.severity is Severity.LOW  # type: ignore[attr-defined]


# --- the BOQ / ME / Virgin case: 500s that do not go away -------------------


def test_one_upstream_failure_is_transient() -> None:
    findings = classify_unit(
        unit(
            status="failed", items_seen=0, error_kind="http_5xx", error_detail="500 from /products"
        ),
        UnitHistory("brand-1", recent_statuses=("ok", "ok")),
    )
    assert only(findings, FailureClass.TRANSIENT_UPSTREAM).severity is Severity.LOW  # type: ignore[attr-defined]


def test_the_same_failure_three_runs_running_is_persistent() -> None:
    findings = classify_unit(
        unit(
            status="failed", items_seen=0, error_kind="http_5xx", error_detail="500 from /products"
        ),
        UnitHistory("brand-1", recent_statuses=("failed", "failed", "ok")),
    )
    finding = only(findings, FailureClass.PERSISTENT_UPSTREAM)
    assert finding.severity is Severity.HIGH  # type: ignore[attr-defined]
    assert finding.evidence["consecutive_failures"] == 3  # type: ignore[attr-defined]


def test_the_persistence_threshold_is_configurable() -> None:
    history = UnitHistory("brand-1", recent_statuses=("failed",))
    args = dict(status="failed", items_seen=0, error_kind="timeout", error_detail="timed out")
    assert FailureClass.TRANSIENT_UPSTREAM in classes(classify_unit(unit(**args), history))
    lenient = Thresholds(persistent_after_failures=2)
    assert FailureClass.PERSISTENT_UPSTREAM in classes(
        classify_unit(unit(**args), history, lenient)
    )


def test_a_4xx_outranks_a_5xx_because_it_is_ours_to_fix() -> None:
    findings = classify_unit(
        unit(status="failed", items_seen=0, error_kind="http_4xx", error_detail="400 bad request"),
        UnitHistory("brand-1"),
    )
    assert only(findings, FailureClass.CLIENT_ERROR).severity is Severity.HIGH  # type: ignore[attr-defined]


# --- coverage --------------------------------------------------------------


def test_coverage_loss_when_output_falls_below_half_the_baseline() -> None:
    history = UnitHistory(
        "brand-1", recent_statuses=("ok",) * 4, recent_items_seen=(30, 32, 31, 30)
    )
    finding = only(classify_unit(unit(items_seen=8), history), FailureClass.COVERAGE_LOSS)
    assert finding.evidence["baseline"] == 31  # type: ignore[attr-defined]


def test_no_coverage_verdict_without_enough_history_to_have_a_baseline() -> None:
    history = UnitHistory("brand-1", recent_statuses=("ok",), recent_items_seen=(30,))
    assert FailureClass.COVERAGE_LOSS not in classes(classify_unit(unit(items_seen=2), history))


def test_a_zero_is_reported_as_silent_zero_rather_than_twice() -> None:
    history = UnitHistory(
        "brand-1", recent_statuses=("ok",) * 4, recent_items_seen=(30, 32, 31, 30)
    )
    found = classes(classify_unit(unit(items_seen=0), history))
    assert FailureClass.SILENT_ZERO in found
    assert FailureClass.COVERAGE_LOSS not in found


def test_a_failed_unit_is_not_also_accused_of_losing_coverage() -> None:
    history = UnitHistory(
        "brand-1", recent_statuses=("ok",) * 4, recent_items_seen=(30, 32, 31, 30)
    )
    found = classes(
        classify_unit(unit(status="failed", items_seen=0, error_kind="timeout"), history)
    )
    assert FailureClass.COVERAGE_LOSS not in found


def test_the_baseline_ignores_zeroes_so_a_broken_unit_does_not_lower_the_bar() -> None:
    history = UnitHistory("brand-1", recent_items_seen=(0, 0, 30, 32, 31))
    assert history.typical_items == 31


# --- other classes ----------------------------------------------------------


def test_quarantined_payloads_are_schema_drift() -> None:
    findings = classify_unit(unit(status="partial", items_quarantined=3), UnitHistory("brand-1"))
    assert only(findings, FailureClass.SCHEMA_DRIFT).severity is Severity.HIGH  # type: ignore[attr-defined]
    assert FailureClass.PARTIAL_DEGRADATION in classes(findings)


def test_a_changed_protocol_version_is_noted_quietly() -> None:
    history = UnitHistory("brand-1", previous_protocol_version=3)
    finding = only(classify_unit(unit(protocol_version=5), history), FailureClass.VERSION_DRIFT)
    assert finding.evidence == {"from": 3, "to": 5}  # type: ignore[attr-defined]
    assert finding.severity is Severity.LOW  # type: ignore[attr-defined]


def test_a_skipped_unit_produces_one_finding_and_no_speculation() -> None:
    findings = classify_unit(
        unit(status="skipped_circuit_open", items_seen=0), UnitHistory("brand-1")
    )
    assert classes(findings) == {FailureClass.CIRCUIT_OPEN}


# --- run level --------------------------------------------------------------


def run(**kwargs: object) -> Run:
    defaults: dict[str, object] = {
        "run_id": 42,
        "status": "completed",
        "started_at": NOW,
        "finished_at": NOW,
        "trigger": "schedule",
        "code_version": "abc1234",
        "units_total": 20,
        "units_ok": 20,
        "units_failed": 0,
    }
    defaults.update(kwargs)
    return Run(**defaults)  # type: ignore[arg-type]


def test_everything_failing_at_once_is_reported_as_ours() -> None:
    units = [
        unit(unit_id=f"b{i}", status="failed", items_seen=0, error_kind="transport")
        for i in range(3)
    ]
    findings = classify(run(units_ok=0, units_failed=3), units)
    outage = only(findings, FailureClass.TOTAL_OUTAGE)
    assert outage.severity is Severity.CRITICAL  # type: ignore[attr-defined]
    # and it sorts above the individual unit failures
    assert findings[0].failure_class is FailureClass.TOTAL_OUTAGE  # type: ignore[attr-defined]


def test_a_failed_run_is_critical_and_scoped_to_the_run() -> None:
    finding = only(classify(run(status="failed"), []), FailureClass.RUN_FAILED)
    assert finding.scope == "run"  # type: ignore[attr-defined]


def test_a_clean_run_produces_nothing_at_all() -> None:
    units = [unit(unit_id=f"b{i}") for i in range(3)]
    histories = {
        f"b{i}": UnitHistory(f"b{i}", recent_statuses=("ok",) * 3, recent_items_seen=(32, 32, 32))
        for i in range(3)
    }
    assert classify(run(), units, histories) == []
