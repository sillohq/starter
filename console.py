"""Management commands for this project.

    python console.py                      list the commands
    python console.py db migrate           create the database and apply migrations
    python console.py db make add_posts    write a migration from model changes
    python console.py db plan              show what would run
    python console.py db rollback 0001_initial
    python console.py user admin ada@example.com ada
    python console.py user list
    python console.py worker               run the queue worker
    python console.py scheduler            run scheduled tasks
    python console.py serve                run the application

Everything here is a thin call into ``sillo.record.commands``,
``sillo.users.commands`` and ``sillo.work.commands``. The framework provides the
operations; this file only decides what to call them and how to print the
result, which is exactly the part that belongs to a project rather than to a
framework.

Add your own by writing a function and registering it in build_parser(). No
dependency beyond sillo is needed — argparse ships with Python.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import config  # noqa: E402
from app.database import MIGRATIONS_MODULE, database  # noqa: E402

# -- database ----------------------------------------------------------


async def db_migrate(args) -> int:
    """Create the database and apply every pending migration."""
    from sillo.record.commands import init, make, migrate

    package = Path(MIGRATIONS_MODULE.replace(".", "/"))
    if not any(package.glob("0*.py")):
        # Nothing written yet: set the package up and record the starting
        # schema, so a later model change is an alteration of a known table
        # rather than a table the migration engine has never seen.
        await init(database())
        await make(database(), "initial")

    await migrate(database(), fake=args.fake)
    print("Database is up to date." if not args.fake else "Migrations recorded.")
    return 0


async def db_make(args) -> int:
    """Write a migration from the current model changes."""
    from sillo.record.commands import make, migrate

    await make(database(), args.name)
    if args.apply:
        await migrate(database())
        print("Written and applied.")
    else:
        print("Written. Review it, then: python console.py db migrate")
    return 0


async def db_plan(args) -> int:
    """Show which migrations would run."""
    from sillo.record.commands import plan

    lines = await plan(database())
    print("\n".join(lines) if lines else "Nothing pending.")
    return 0


async def db_rollback(args) -> int:
    """Roll the database back to a migration."""
    from sillo.record.commands import rollback

    await rollback(database(), args.target)
    print(f"Rolled back to {args.target}.")
    return 0


# -- users -------------------------------------------------------------


async def user_create(args) -> int:
    """Create a user, or an administrator with --admin."""
    from sillo.users.commands import create_admin, create_user

    from database.models.user import User

    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    create = create_admin if args.admin else create_user
    try:
        user = await create(args.email, args.username, password, model=User)
    except ValueError as error:
        # The framework reports which rule failed — duplicate address, or which
        # part of the password policy. Its wording beats a local guess.
        print(error, file=sys.stderr)
        return 1

    print(f"Created {user.email}" + (" — sign in at /admin/" if args.admin else ""))
    return 0


async def user_list(args) -> int:
    """List users, newest first."""
    from sillo.users.commands import list_users

    from database.models.user import User

    users = await list_users(model=User, limit=args.limit, staff_only=args.staff)
    if not users:
        print("No users yet.")
        return 0
    for user in users:
        flags = "".join(["A" if user.is_staff else "-", "-" if user.is_active else "X"])
        print(f"  {user.id:>4}  {flags}  {user.email:<32} {user.username}")
    print("\n  A = admin access, X = deactivated")
    return 0


async def user_password(args) -> int:
    """Change a user's password."""
    from sillo.users.commands import set_password

    from database.models.user import User

    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("New password: ")
    try:
        await set_password(args.identifier, password, model=User)
    except (LookupError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print("Password changed.")
    return 0


# -- processes ---------------------------------------------------------


async def worker(args) -> int:
    """Run the queue worker until stopped."""
    from sillo.work.commands import run_worker

    # Importing the package registers the job classes, so a queued payload can
    # be resolved back to the class that handles it.
    import app.jobs  # noqa: F401

    await run_worker(
        url=os.getenv("QUEUE_URL") or None,
        queues=args.queues.split(",") if args.queues else None,
        concurrency=args.concurrency,
    )
    return 0


async def scheduler(args) -> int:
    """Run scheduled tasks until stopped."""
    from sillo.work.commands import run_scheduler

    from app.tasks import register_tasks

    await run_scheduler(register_tasks)
    return 0


async def _with_database(coroutine):
    """Open the database for the duration of *coroutine*.

    The command functions in ``sillo.users.commands`` operate on models and
    assume the ORM is already initialised — that is the application's job, and
    here it is this file's. Migrations are the exception: they open and close
    their own connections, so they are not wrapped.

    Returns:
        Whatever *coroutine* returned.
    """
    async with database():
        return await coroutine


def serve(args) -> int:
    """Run the application. Synchronous — uvicorn owns the loop."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host or config.host,
        port=args.port or config.port,
        reload=args.reload,
    )
    return 0


# -- wiring ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the command tree."""
    parser = argparse.ArgumentParser(
        prog="python console.py",
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="group", metavar="<command>")

    # Named `schema`, not `database`: the module-level `database` is this
    # project's manager factory, and shadowing it here would be a trap.
    schema = commands.add_parser("db", help="Migrations and schema.").add_subparsers(
        dest="action", metavar="<action>"
    )

    migrate_cmd = schema.add_parser("migrate", help="Create the database and apply migrations.")
    migrate_cmd.add_argument("--fake", action="store_true", help="Record without running the SQL.")
    migrate_cmd.set_defaults(run=db_migrate)

    make_cmd = schema.add_parser("make", help="Write a migration from model changes.")
    make_cmd.add_argument("name", nargs="?", help="Name for the migration.")
    make_cmd.add_argument("--apply", action="store_true", help="Apply it straight away.")
    make_cmd.set_defaults(run=db_make)

    plan_cmd = schema.add_parser("plan", help="Show which migrations would run.")
    plan_cmd.set_defaults(run=db_plan)

    rollback_cmd = schema.add_parser("rollback", help="Roll back to a migration.")
    rollback_cmd.add_argument("target", help="Migration to stop at, or 'zero'.")
    rollback_cmd.set_defaults(run=db_rollback)

    users = commands.add_parser("user", help="Accounts.").add_subparsers(
        dest="action", metavar="<action>"
    )

    for name, is_admin in (("create", False), ("admin", True)):
        create_cmd = users.add_parser(
            name, help="Create an administrator." if is_admin else "Create a user."
        )
        create_cmd.add_argument("email")
        create_cmd.add_argument("username")
        create_cmd.set_defaults(run=user_create, admin=is_admin, needs_database=True)

    list_cmd = users.add_parser("list", help="List users.")
    list_cmd.add_argument("--limit", type=int, default=50)
    list_cmd.add_argument("--staff", action="store_true", help="Only administrators.")
    list_cmd.set_defaults(run=user_list, needs_database=True)

    password_cmd = users.add_parser("password", help="Change a password.")
    password_cmd.add_argument("identifier", help="Email address or username.")
    password_cmd.set_defaults(run=user_password, needs_database=True)

    worker_cmd = commands.add_parser("worker", help="Run the queue worker.")
    worker_cmd.add_argument("--queues", help="Comma-separated, highest priority first.")
    worker_cmd.add_argument("--concurrency", type=int, default=4)
    worker_cmd.set_defaults(run=worker, needs_database=True)

    scheduler_cmd = commands.add_parser("scheduler", help="Run scheduled tasks.")
    scheduler_cmd.set_defaults(run=scheduler, needs_database=True)

    serve_cmd = commands.add_parser("serve", help="Run the application.")
    serve_cmd.add_argument("--host")
    serve_cmd.add_argument("--port", type=int)
    serve_cmd.add_argument("--reload", action="store_true")
    serve_cmd.set_defaults(run=serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse *argv* and run the command it names."""
    # "Database connected" / "connections closed" around every command is noise
    # here; the application still logs them at startup.
    logging.getLogger("sillo.record").setLevel(logging.WARNING)

    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "run", None):
        parser.print_help()
        return 0

    if asyncio.iscoroutinefunction(args.run):
        if getattr(args, "needs_database", False):
            return asyncio.run(_with_database(args.run(args)))
        return asyncio.run(args.run(args))
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
