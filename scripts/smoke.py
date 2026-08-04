"""Boot the application and exercise every route.

Run by CI, and useful by hand after a dependency bump. A project can import
cleanly, render every template and still fail on the first real request —
middleware ordering, a missing static mount, an auth backend reading the wrong
claim. Those only surface when something actually calls the app, which is what
this does.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.main import app  # noqa: E402
from database.config import database  # noqa: E402
from database.models.user import User  # noqa: E402


class Lifespan:
    """Drive the ASGI lifespan so startup hooks — the database — actually run."""

    def __init__(self, application):
        self.app = application
        self.receive_queue: asyncio.Queue = asyncio.Queue()
        self.send_queue: asyncio.Queue = asyncio.Queue()

    async def __aenter__(self):
        self.task = asyncio.create_task(
            self.app({"type": "lifespan"}, self.receive_queue.get, self.send_queue.put)
        )
        await self.receive_queue.put({"type": "lifespan.startup"})
        message = await self.send_queue.get()
        if message["type"] != "lifespan.startup.complete":
            raise RuntimeError(f"startup failed: {message}")
        return self

    async def __aexit__(self, *_):
        await self.receive_queue.put({"type": "lifespan.shutdown"})
        try:
            await asyncio.wait_for(self.send_queue.get(), 5)
            await asyncio.wait_for(self.task, 5)
        except Exception:
            self.task.cancel()


async def make_staff_account(email: str, username: str, password: str) -> None:
    """Create an administrator before the application starts.

    The ORM connection the app opens on startup lives in the startup task, so a
    script cannot borrow it from out here. Opening our own first, and closing it
    again, is simpler than reaching into the application's.
    """
    from sillo.users.commands import create_admin

    async with database():
        await create_admin(email, username, password, model=User)


async def _logged_in() -> bool:
    """Whether the admin recorded a login. Opens its own connection, like the
    account creation above, because the application's belongs to its own task."""
    from sillo.admin import AdminActivity

    async with database():
        return await AdminActivity.filter(action="login").exists()


class _CaptureJobLogs(logging.Handler):
    """Collect what app.jobs logs, so a check can see a job actually ran."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


async def _job_ran(handler: _CaptureJobLogs, seconds: float = 4.0) -> bool:
    """Wait briefly for the queued job to be handled."""
    for _ in range(int(seconds * 20)):
        if any("welcome email" in message for message in handler.messages):
            return True
        await asyncio.sleep(0.05)
    return False


async def main() -> int:
    """Return 0 when every check passed, 1 otherwise."""
    failures: list[str] = []

    def check(label: str, actual, expected) -> None:
        ok = actual == expected
        print(f"  {'ok  ' if ok else 'FAIL'}  {label:34s} {actual}")
        if not ok:
            failures.append(f"{label}: expected {expected}, got {actual}")

    jobs_log = _CaptureJobLogs()
    job_logger = logging.getLogger("app.jobs")
    job_logger.setLevel(logging.INFO)
    job_logger.addHandler(jobs_log)

    staff = f"staff{uuid.uuid4().hex[:8]}"
    await make_staff_account(f"{staff}@example.com", staff, "Hunter2!pass")

    async with Lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://smoke", follow_redirects=False
        ) as client:
            check("GET /", (await client.get("/")).status_code, 200)
            check(
                "GET /static/css/app.css",
                (await client.get("/static/css/app.css")).status_code,
                200,
            )
            check("GET /docs", (await client.get("/docs")).status_code, 200)
            check("GET /api/health", (await client.get("/api/health")).status_code, 200)
            check("GET /admin/login/", (await client.get("/admin/login/")).status_code, 200)

            page = await client.get("/")
            check("welcome page renders", "Sillo starter" in page.text, True)

            # The JSON auth API, which is what the starter ships enabled.
            suffix = uuid.uuid4().hex[:8]
            created = await client.post(
                "/api/auth/register",
                json={
                    "email": f"{suffix}@example.com",
                    "username": suffix,
                    "password": "Hunter2!pass",
                },
            )
            check("POST /api/auth/register", created.status_code, 201)
            # Registering queues a welcome email. The worker runs inside this
            # process, so the job should be delivered within a moment — and a
            # job that is queued but never runs is the failure worth catching.
            check("welcome email job ran", await _job_ran(jobs_log), True)
            signed_in = await client.post(
                "/api/auth/login",
                json={"identifier": f"{suffix}@example.com", "password": "Hunter2!pass"},
            )
            check("POST /api/auth/login", signed_in.status_code, 200)
            wrong = await client.post(
                "/api/auth/login",
                json={"identifier": f"{suffix}@example.com", "password": "nope"},
            )
            check("POST /api/auth/login, bad password", wrong.status_code, 401)

            # Signing in to the admin with an ordinary account, which is the
            # point of there being one user model. Reaching the login page
            # proves nothing: the form renders whether or not the credentials
            # behind it are ever accepted.
            signed_in = await client.post(
                "/admin/login/",
                data={"email": f"{staff}@example.com", "password": "Hunter2!pass"},
            )
            check("POST /admin/login/", signed_in.status_code, 302)
            dashboard = await client.get("/admin/", cookies=signed_in.cookies)
            check("GET /admin/ signed in", dashboard.status_code, 200)

            # The audit log is registered by default, so it has a table and the
            # admin lists it. Reaching the page is the part that breaks when the
            # model is registered with the admin but not with the ORM.
            log = await client.get("/admin/adminactivity/", cookies=signed_in.cookies)
            check("GET /admin/adminactivity/", log.status_code, 200)
            check("the sign-in was recorded", await _logged_in(), True)

    if failures:
        print("\n" + "\n".join(f"  {failure}" for failure in failures), file=sys.stderr)
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
