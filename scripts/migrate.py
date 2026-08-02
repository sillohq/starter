"""Migrations, through sillo.

Wraps :class:`sillo.record.MigrationHelper` so the project never drives the
underlying ORM's tooling directly. The settings come from ``app.database``,
which is the same configuration the application runs on.

    python scripts/migrate.py init          set up and apply the first migration
    python scripts/migrate.py make [name]   write a migration from model changes
    python scripts/migrate.py up            apply everything pending
    python scripts/migrate.py down <target> roll back to a migration
    python scripts/migrate.py plan          show what would run
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sillo.record import MigrationHelper  # noqa: E402

from app.database import MIGRATIONS_MODULE, TORTOISE_ORM  # noqa: E402

USAGE = __doc__


def helper() -> MigrationHelper:
    """A helper bound to this project's configuration."""
    return MigrationHelper(TORTOISE_ORM, app="models")


async def main(argv: list[str]) -> int:
    """Dispatch one command. Returns the process exit code."""
    command = argv[0] if argv else "up"
    args = argv[1:]
    migrations = helper()

    if command == "init":
        # The helper's own init needs the config as a dotted path, because the
        # commands that create a migration package are only reachable that way.
        await MigrationHelper("app.database.TORTOISE_ORM", app="models").init()
        await MigrationHelper("app.database.TORTOISE_ORM", app="models").make("initial")
        await migrations.upgrade()
        print(f"Database ready — migrations in {MIGRATIONS_MODULE.replace('.', '/')}/")
    elif command == "make":
        await MigrationHelper("app.database.TORTOISE_ORM", app="models").make(
            args[0] if args else None
        )
    elif command in {"up", "upgrade"}:
        await migrations.upgrade()
        print("Database is up to date.")
    elif command in {"down", "downgrade"}:
        if not args:
            print("A target is required, e.g. 0001_initial.", file=sys.stderr)
            return 2
        await migrations.downgrade(args[0])
    elif command == "plan":
        for line in await migrations.plan():
            print(line)
    else:
        print(USAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
