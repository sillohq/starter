"""Database wiring.

One definition of how this project connects, built from
:class:`sillo.record.DatabaseConfig` and used by both the running application
and the migration commands. Nothing here writes a Tortoise configuration by
hand — ``DatabaseManager.tortoise_config()`` derives it from the same settings
the application runs on, so the two cannot drift apart.
"""

from __future__ import annotations

from sillo.record import DatabaseConfig, DatabaseManager

from app.config import config

#: Modules scanned for models. A model that is not imported in this package's
#: ``__init__`` is invisible to the ORM, and the first query fails with
#: "default_connection cannot be None" rather than anything about the import.
MODEL_MODULES = ["database.models", "sillo.admin.models"]

#: Where migrations live, as a dotted path.
MIGRATIONS_MODULE = "database.migrations"


def database_config() -> DatabaseConfig:
    """The connection settings for this project."""
    return DatabaseConfig(
        url=config.database_url,
        pool_size=config.db_pool_size,
        echo=config.db_echo,
        # Migrations own the schema. Generating it on startup would create
        # tables outside the migration history, and have every process race to
        # run DDL — "database is locked" when the app and a worker boot together.
        generate_schemas=config.db_generate_schemas,
    )


def _manager() -> DatabaseManager:
    """A manager carrying this project's config and model modules."""
    manager = DatabaseManager(database_config())
    manager.register_models(*MODEL_MODULES)
    return manager


#: The configuration the migration engine reads. Derived, never hand-written.
TORTOISE_ORM = _manager().tortoise_config(MIGRATIONS_MODULE)
