"""Grouping. The tests are all about what must collapse and what must not."""

from __future__ import annotations

from sentinel.fingerprint import fingerprint, normalise_error
from sentinel.model import FailureClass, Finding, Severity


def finding(**kwargs: object) -> Finding:
    defaults: dict[str, object] = {
        "failure_class": FailureClass.PERSISTENT_UPSTREAM,
        "severity": Severity.HIGH,
        "scope": "unit:brand-1",
        "title": "whatever",
        "signature": "500 from upstream",
        "evidence": {},
    }
    defaults.update(kwargs)
    return Finding(**defaults)  # type: ignore[arg-type]


def test_identical_problems_share_a_fingerprint() -> None:
    assert fingerprint(finding()) == fingerprint(finding(title="a different title"))


def test_the_title_and_evidence_do_not_affect_grouping() -> None:
    a = fingerprint(finding(evidence={"consecutive_failures": 3}))
    b = fingerprint(finding(evidence={"consecutive_failures": 9}))
    assert a == b


def test_different_units_are_different_incidents() -> None:
    assert fingerprint(finding()) != fingerprint(finding(scope="unit:brand-2"))


def test_different_classes_are_different_incidents() -> None:
    assert fingerprint(finding()) != fingerprint(finding(failure_class=FailureClass.CLIENT_ERROR))


def test_ids_inside_an_error_are_normalised_away() -> None:
    a = finding(signature="detail for 3f2504e0-4f89-11d3-9a0c-0305e82c3301 failed")
    b = finding(signature="detail for 550e8400-e29b-41d4-a716-446655440000 failed")
    assert fingerprint(a) == fingerprint(b)


def test_timestamps_inside_an_error_are_normalised_away() -> None:
    a = finding(signature="timed out at 2026-09-19T06:17:02Z")
    b = finding(signature="timed out at 2026-09-20T18:17:44Z")
    assert fingerprint(a) == fingerprint(b)


def test_an_http_status_survives_normalisation() -> None:
    # 500 and 503 are genuinely different problems; a blanket digit rule would
    # have merged them, which is why the substitution starts at four digits.
    assert normalise_error("http 500 from upstream") != normalise_error("http 503 from upstream")
    assert "500" in normalise_error("http 500 from upstream")


def test_long_identifiers_are_normalised_but_short_numbers_are_not() -> None:
    assert normalise_error("product 9f8e7d6c5b4a failed") == "product <hex> failed"
    assert normalise_error("attempt 3 of 5") == "attempt 3 of 5"


def test_whitespace_and_case_do_not_split_an_incident() -> None:
    assert normalise_error("  500   FROM\nUpstream ") == normalise_error("500 from upstream")


def test_a_missing_error_normalises_to_empty_rather_than_none() -> None:
    assert normalise_error(None) == ""
