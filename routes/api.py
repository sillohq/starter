"""API routes.

Handlers take the ``HttpContext`` as their one leading argument and return a
response built by one of the functions in ``sillo.responses``. Path parameters
are injected as keyword arguments, and the converter in the path — ``{id:int}``
— determines the type that arrives. Query, header, cookie and form values use
the markers from ``sillo``, which feed both validation and the OpenAPI schema
so the published contract cannot drift from the enforced one.
"""

from __future__ import annotations

from sillo import HttpContext, Router, json

from app.config import config

router = Router(prefix="/api", tags=["starter"])


@router.get("/health", summary="Liveness and readiness probe")
async def health(ctx: HttpContext):
    """Report whether the application and its dependencies are reachable."""
    checks: dict[str, str] = {"app": "ok"}

    # setup_record() stores the manager on the application state. Inside a
    # router, `ctx.app` is the router — `ctx.base_app` is the application
    # that owns the state.
    manager = ctx.base_app.state.get("record")
    checks["database"] = "ok" if manager and await manager.health() else "unavailable"

    healthy = all(status == "ok" for status in checks.values())
    return json(
        {"status": "ok" if healthy else "degraded", "checks": checks, "env": config.app_env},
        status_code=200 if healthy else 503,
    )


@router.get("/", summary="API root")
async def index(ctx: HttpContext):
    """Return a short description of the API."""
    return json(
        {
            "name": "Starter",
            "version": "0.1.0",
            "docs": "/docs",
        }
    )
