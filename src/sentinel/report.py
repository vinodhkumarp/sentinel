"""Rendering findings for a human. No model involved -- see ADR-0003.

This is the floor: whatever else Sentinel gains later, it must always be able
to say what it found without a language model being available.
"""

from __future__ import annotations

from .fingerprint import fingerprint
from .model import Finding, Run, Severity

_MARKERS = {
    Severity.CRITICAL: "!!",
    Severity.HIGH: "! ",
    Severity.MEDIUM: "~ ",
    Severity.LOW: "- ",
    Severity.INFO: "  ",
}


def _evidence(finding: Finding) -> str:
    if not finding.evidence:
        return ""
    pairs = ", ".join(f"{k}={v}" for k, v in finding.evidence.items() if v is not None)
    return f"      {pairs}" if pairs else ""


def render_run(run: Run, findings: list[Finding], *, show_fingerprints: bool = False) -> str:
    """A plain-text verdict on one run."""
    started = run.started_at.astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lines = [
        f"run {run.run_id}  {run.status}  {started}  "
        f"trigger={run.trigger}  units={run.units_ok}/{run.units_total} ok",
    ]
    if run.code_version:
        lines.append(f"code {run.code_version}")
    lines.append("")

    if not findings:
        lines.append("  nothing to report.")
        return "\n".join(lines)

    worst = max(f.severity for f in findings)
    lines.append(f"  {len(findings)} finding(s), worst {worst.name}")
    lines.append("")

    for finding in findings:
        marker = _MARKERS[finding.severity]
        suffix = f"  [{fingerprint(finding)}]" if show_fingerprints else ""
        lines.append(f"  {marker} {finding.failure_class.value:<20} {finding.title}{suffix}")
        detail = _evidence(finding)
        if detail:
            lines.append(detail)

    return "\n".join(lines)
