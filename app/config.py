"""Application configuration.

Settings are declared once here as a typed :class:`sillo.config.Config` and
loaded from ``.env`` at import. Read values from the ``config`` object rather
than calling ``os.getenv`` around the codebase — a typo in an environment
variable name then fails at startup with a clear message instead of silently
becoming ``None`` at request time.
"""

from __future__ import annotations

from typing import Literal

from sillo.config import Config


class AppConfig(Config):
    """Typed settings for Starter."""

    # -- application ---------------------------------------------------
    app_name: str = "Starter"
    app_env: Literal["local", "testing", "staging", "production"] = "local"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    secret_key: str = "change-me"

    # -- database ------------------------------------------------------
    database_url: str = "sqlite://storage/starter.db"
    db_pool_size: int = 5
    db_echo: bool = False
    # Off, because migrations own the schema. Generating it on startup would
    # create tables outside the migration history, and would have every
    # process race to run DDL — "database is locked" on SQLite when the app,
    # worker and scheduler boot together. Set DB_GENERATE_SCHEMAS=true for a
    # throwaway database with no migrations.
    db_generate_schemas: bool = False

    # -- authentication ------------------------------------------------

    # -- session ---------------------------------------------------------
    # Guarded on uses_sessions (session.enabled or admin.enabled), not on the
    # auth strategy: the session middleware is registered whenever sessions are
    # on — including alongside JWT auth, and for the admin panel, which needs
    # them regardless — and it reads both of these at startup.
    session_cookie_name: str = "session_id"
    session_lifetime: int = 86400

    # -- admin ---------------------------------------------------------
    admin_enabled: bool = True
    admin_prefix: str = "/admin"

    # -- security ------------------------------------------------------
    cors_allow_origins: str = "http://localhost:5173"

    # -- logging -------------------------------------------------------
    log_level: Literal["debug", "info", "warning", "error"] = "info"


#: Loaded once at import and shared across the application.
#:
#: The env file is passed to the constructor rather than declared on an inner
#: ``class Config``. Both are supported by the framework, but the inner-class
#: form is the one Pydantic v2 has deprecated, and it would emit a warning
#: every time this module is imported.
config = AppConfig(_env_file=".env")


def cors_origins() -> list[str]:
    """Split the comma-separated origin list into the form the middleware wants."""
    return [origin.strip() for origin in config.cors_allow_origins.split(",") if origin.strip()]
