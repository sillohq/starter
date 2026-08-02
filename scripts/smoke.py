"""Boot the application and exercise every route.

Run by CI, and useful by hand after a dependency bump. A project can import
cleanly, render every template and still fail on the first real request —
middleware ordering, a missing static mount, an auth backend reading the wrong
claim. Those only surface when something actually calls the app, which is what
this does.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.main import app  # noqa: E402


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


async def main() -> int:
    """Return 0 when every check passed, 1 otherwise."""
    failures: list[str] = []

    def check(label: str, actual, expected) -> None:
        ok = actual == expected
        print(f"  {'ok  ' if ok else 'FAIL'}  {label:34s} {actual}")
        if not ok:
            failures.append(f"{label}: expected {expected}, got {actual}")

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

    if failures:
        print("\n" + "\n".join(f"  {failure}" for failure in failures), file=sys.stderr)
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
