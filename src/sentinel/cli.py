"""Command line. The whole of Sentinel v0.1 is reachable from here."""

from __future__ import annotations

import sys

import typer

from . import db
from .adapters import rateradar
from .classify import classify
from .config import Settings
from .report import render_run

app = typer.Typer(
    add_completion=False,
    help="Triage for data pipeline failures: classify, group, explain.",
)


def _settings() -> Settings:
    return Settings()


@app.command()
def explain(
    run_id: int = typer.Argument(..., help="Run to classify."),
    fingerprints: bool = typer.Option(False, "--fingerprints", help="Show incident ids."),
) -> None:
    """Classify one run and say what is wrong with it."""
    settings = _settings()
    with db.connect_source(settings) as conn:
        run = rateradar.fetch_run(conn, run_id)
        if run is None:
            typer.echo(f"no run {run_id}", err=True)
            raise typer.Exit(code=1)
        units = rateradar.fetch_units(conn, run.run_id)
        histories = rateradar.fetch_histories(
            conn, run.run_id, [u.unit_id for u in units], limit=settings.history_runs
        )

    findings = classify(run, units, histories)
    typer.echo(render_run(run, findings, show_fingerprints=fingerprints))


@app.command()
def triage(
    fingerprints: bool = typer.Option(False, "--fingerprints", help="Show incident ids."),
    strict: bool = typer.Option(
        False, "--strict", help="Exit non-zero if anything HIGH or worse was found."
    ),
) -> None:
    """Classify the most recent finished run."""
    settings = _settings()
    with db.connect_source(settings) as conn:
        run = rateradar.fetch_latest_run(conn)
        if run is None:
            typer.echo("no finished runs yet", err=True)
            raise typer.Exit(code=1)
        units = rateradar.fetch_units(conn, run.run_id)
        histories = rateradar.fetch_histories(
            conn, run.run_id, [u.unit_id for u in units], limit=settings.history_runs
        )

    findings = classify(run, units, histories)
    typer.echo(render_run(run, findings, show_fingerprints=fingerprints))

    # Exit code is opt-in. A scheduled job wants a non-zero on real trouble;
    # a human at a terminal does not want a shell error for a known-broken bank.
    if strict and any(f.severity >= 40 for f in findings):
        sys.exit(1)


@app.command()
def history(
    limit: int = typer.Option(10, help="How many recent runs to list."),
) -> None:
    """One line per recent run: how many findings, and the worst of them."""
    settings = _settings()
    with db.connect_source(settings) as conn:
        latest = rateradar.fetch_latest_run(conn)
        if latest is None:
            typer.echo("no finished runs yet", err=True)
            raise typer.Exit(code=1)
        for run_id in range(latest.run_id, max(latest.run_id - limit, 0), -1):
            run = rateradar.fetch_run(conn, run_id)
            if run is None or run.status == "running":
                continue
            units = rateradar.fetch_units(conn, run_id)
            histories = rateradar.fetch_histories(
                conn, run_id, [u.unit_id for u in units], limit=settings.history_runs
            )
            findings = classify(run, units, histories)
            worst = max((f.severity for f in findings), default=None)
            started = run.started_at.astimezone().strftime("%Y-%m-%d %H:%M")
            typer.echo(
                f"  {run_id:>5}  {started}  {run.status:<10} "
                f"{len(findings):>2} finding(s)  worst={worst.name if worst else '-'}"
            )


if __name__ == "__main__":
    app()
