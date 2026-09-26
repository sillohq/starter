"""Shared test fixtures.

The application is built per-test through ``create_app`` so no state leaks
between tests. ``TestClient`` is used as a context manager because entering it
runs the ASGI lifespan — which is what opens the database connection and starts
the scheduler.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point every test at its own throwaway SQLite file.

    The environment variable is set before ``app.config`` is imported by the
    application factory, so the test database is picked up rather than the
    development one.
    """
    monkeypatch.setenv("DATABASE_URL", f"sqlite://{tmp_path / 'test.db'}")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DEBUG", "true")
    for name in list(sys.modules):
        if (
            name == "app"
            or name.startswith("app.")
            or (name == "database" or name.startswith("database."))
            or (name == "routes" or name.startswith("routes."))
        ):
            sys.modules.pop(name)
    yield


@pytest.fixture
def app():
    """Build a fresh application instance."""
    from app.bootstrap import create_app

    return create_app()


@pytest.fixture
def client(app):
    """A test client with the application lifespan running."""
    from sillo.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
