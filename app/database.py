"""Database wiring.

One definition of how this project connects, built from
:class:`sillo.record.DatabaseConfig` and shared by the running application, the
migration commands and anything else that opens the database. Nothing here
describes the connection twice, so the application and its migrations cannot
drift apart.
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


def database() -> DatabaseManager:
    """A manager for this project's database.

    What ``console.py`` hands to the migration commands, and what a script that
    needs the ORM opens::

        async with database() as db:
            await User.all()

    The application does not call this — ``setup_record`` in ``app/bootstrap.py``
    builds its own manager from the same :func:`database_config`, and ties it to
    the application's startup and shutdown.
    """
    manager = DatabaseManager(database_config())
    manager.register_models(*MODEL_MODULES).set_migrations(MIGRATIONS_MODULE)
    return manager
