"""Connections. Deliberately thin: Sentinel reads, it does not own a schema yet."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import Settings

Conn = psycopg.Connection[dict[str, Any]]


@contextmanager
def connect_source(settings: Settings) -> Iterator[Conn]:
    """Open a read-only connection to the pipeline being watched.

    read_only is set on the session rather than trusted to convention: Sentinel
    reading a production pipeline should be incapable of altering it, not merely
    disinclined. A read-only role is still the right credential on top of this.
    """
    with psycopg.connect(str(settings.source_database_url), row_factory=dict_row) as conn:
        conn.read_only = True
        yield conn
