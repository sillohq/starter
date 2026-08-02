"""Create an administrator account.

Run with `make admin`, or `python scripts/create_admin.py`. Pass the details as
arguments for non-interactive use:

    python scripts/create_admin.py admin@example.com admin

The password is read from ADMIN_PASSWORD when set, and prompted for otherwise,
so it never has to appear in shell history or a CI log. It must satisfy the
framework's policy: at least 8 characters, with an uppercase letter, a digit
and a special character.
"""

from __future__ import annotations

import asyncio
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tortoise import Tortoise  # noqa: E402

from app.database import TORTOISE_ORM  # noqa: E402
from database.models.user import User  # noqa: E402


async def main() -> int:
    """Create the account, or report why it could not be created."""
    email = sys.argv[1] if len(sys.argv) > 1 else input("Email: ").strip()
    username = sys.argv[2] if len(sys.argv) > 2 else input("Username: ").strip()
    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Password: ")

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        if await User.objects.get_by_email(email) is not None:
            print(f"{email} already has an account.", file=sys.stderr)
            return 1

        try:
            user = await User.objects.create_superuser(
                email=email, username=username, password=password
            )
        except ValueError as exc:
            # The framework enforces the password policy — uppercase, digit and
            # special character, not only length. Report its wording rather
            # than a local guess that would contradict it.
            print(str(exc), file=sys.stderr)
            return 1

        print(f"Created {user.email} — sign in at /admin/")
        return 0
    finally:
        # Without this the event loop stays alive on an open connection and the
        # script hangs at interpreter shutdown.
        await Tortoise.close_connections()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
