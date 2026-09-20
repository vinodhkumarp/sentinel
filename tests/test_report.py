"""Rendering. The floor Sentinel must never fall through: a useful answer
without a language model anywhere in the path."""

from __future__ import annotations

from datetime import UTC, datetime

from sentinel.model import FailureClass, Finding, Run, Severity
from sentinel.report import render_run

RUN = Run(
    run_id=42,
    status="completed",
    started_at=datetime(2026, 9, 20, 6, 17, tzinfo=UTC),
    finished_at=datetime(2026, 9, 20, 6, 19, tzinfo=UTC),
    trigger="schedule",
    code_version="abc1234",
    units_total=20,
    units_ok=19,
    units_failed=1,
)


def test_a_clean_run_says_so_plainly() -> None:
    out = render_run(RUN, [])
    assert "nothing to report" in out
    assert "run 42" in out


def test_findings_are_listed_with_their_class_and_title() -> None:
    finding = Finding(
        FailureClass.SILENT_ZERO,
        Severity.HIGH,
        "unit:hsbc",
        "HSBC reported success but returned nothing",
        "silent zero",
        {"typical_items": 30},
    )
    out = render_run(RUN, [finding])
    assert "SILENT_ZERO" in out
    assert "HSBC reported success but returned nothing" in out
    assert "typical_items=30" in out
    assert "1 finding(s), worst HIGH" in out


def test_fingerprints_are_shown_only_when_asked() -> None:
    finding = Finding(FailureClass.CLIENT_ERROR, Severity.HIGH, "unit:x", "t", "sig", {})
    assert "[" not in render_run(RUN, [finding]).split("\n")[-1]
    assert "[" in render_run(RUN, [finding], show_fingerprints=True)


def test_evidence_without_values_does_not_leave_an_empty_line() -> None:
    finding = Finding(
        FailureClass.CLIENT_ERROR, Severity.HIGH, "unit:x", "t", "sig", {"error_kind": None}
    )
    assert not render_run(RUN, [finding]).endswith("\n      ")
