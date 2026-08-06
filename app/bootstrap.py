"""Application assembly.

``create_app`` is the single place where the application is put together:
middleware, then infrastructure, then routes. Keeping it a function rather than
module-level code means tests can build an isolated instance, and the import in
``app/main.py`` stays trivial.
"""

from __future__ import annotations

from sillo import silloApp
from sillo.auth import AuthenticationMiddleware
from sillo.auth.session_auth import SessionAuthBackend

# For JWT instead of sessions — see the backend swap in _register_middleware.
# from sillo.auth.jwt_auth import JWTAuthBackend
from sillo.record import setup_record
from sillo.security import (
    CorsConfig,
    CORSMiddleware,
)
from sillo.session import SessionConfig, SessionMiddleware
from sillo.work import setup_work

from app.config import config, cors_origins
from database.models.user import User


def create_app() -> silloApp:
    """Build and return the configured application."""
    application = silloApp(
        debug=config.debug,
        title=config.app_name,
        version="0.1.0",
    )

    # Order matters, and not in the obvious direction. ``application.use()``
    # puts the newest registration *outermost*, so whatever registers last runs
    # first at request time.
    #
    # ``AdminSite.mount()`` attaches its own auth middleware through
    # ``app.use()``, and that middleware reads ``request.session``. So the admin
    # has to be registered *before* the middleware block, which is what leaves
    # the session middleware outside — and therefore ahead — of it. Register it
    # after, and every admin page 500s with "No Session Middleware Installed"
    # while the session middleware is demonstrably installed.
    _register_admin(application)
    _register_templating()
    _register_middleware(application)
    _register_database(application)
    # Background work is wired but switched off. Uncomment this line when you
    # have a job or a scheduled task worth running. See app/jobs/ and
    # app/tasks/, and run the worker with `make worker`.
    #
    # Pass in_process=True to run the worker inside this process instead, and
    # not run `make worker` at all — see _run_worker_in_process for what that
    # costs.
    # _register_work(application)
    # _register_work(application, in_process=True)
    _register_static(application)
    _register_routes(application)

    return application


def _register_templating() -> None:
    """Configure the Jinja environment before any page is rendered.

    ``sillo.templating.render`` raises NotImplementedError until the engine has
    been set up, so this is not optional for a project that serves HTML.
    """
    from app.templating import setup

    setup(auto_reload=config.app_env == "local")


def _register_static(application: silloApp) -> None:
    """Serve ./static at /static.

    Fine for development and small deployments. Put nginx or Caddy in front in
    production and this never sees traffic — a web server serves files better
    than an ASGI worker that could be answering requests instead::

        location /static/ { alias /srv/starter/static/; expires 30d; }
    """
    from sillo.core.routing import Group
    from sillo.static import StaticFiles

    from app.templating import BASE_DIR

    application.add_route(
        Group(path="/static", app=StaticFiles(directory=str(BASE_DIR / "static")))
    )


def _register_middleware(application: silloApp) -> None:
    """Attach middleware.

    ``application.use()`` builds the chain inside-out: the middleware
    registered *last* is the outermost, and therefore runs *first* on the way
    in. The registrations below are ordered accordingly — innermost concern
    first, outermost last — so at request time the chain runs

        CORS → sessions → CSRF → rate limit → authentication → handler.

    Authentication reads the session, so the session middleware has to be
    registered after it, not before.
    """
    application.use(
        AuthenticationMiddleware(
            user_model=User,
            backend=SessionAuthBackend(),
            # To authenticate with bearer tokens instead, uncomment the import
            # above and swap the backend for:
            #
            #     backend=JWTAuthBackend(
            #         secret_key=config.jwt_secret,
            #         identifier="sub",
            #     ),
            #
            # identifier="sub" is required, not cosmetic. The backend reads
            # payload.get(identifier) and defaults to "id", but sillo writes the
            # user id into the "sub" claim — so with the default, identity is
            # always "" and every authenticated request silently fails to load a
            # user, with nothing logged.
            #
            # Issue tokens with TokenForUser:
            #
            #     from sillo.auth.jwt_auth import TokenForUser
            #     pair = TokenForUser(user, secret=config.jwt_secret).token_pair()
            #
            # Add JWT_SECRET to .env, and jwt_secret to app/config.py. Keep the
            # session middleware either way: the admin panel authenticates
            # through the session regardless of what the rest of the app uses.
        )
    )
    # Registered after authentication so it ends up *outside* it and therefore
    # runs first: SessionAuthBackend reads request.session, and the admin
    # panel's SessionAuth backend does too. The admin needs this even when the
    # app authenticates with JWT, which is why the guard is uses_sessions
    # rather than session.enabled.
    application.use(
        SessionMiddleware(
            config=SessionConfig(
                session_cookie_name=config.session_cookie_name,
                session_expiration_time=config.session_lifetime,
                # Secure cookies require HTTPS, which local development is not.
                session_cookie_secure=config.app_env != "local",
            ),
            secret_key=config.secret_key,
        )
    )
    application.use(
        CORSMiddleware(
            config=CorsConfig(
                allow_origins=cors_origins(),
                allow_credentials=True,
            )
        )
    )


def _register_database(application: silloApp) -> None:
    """Wire the Record ORM into the application lifecycle.

    ``setup_record`` registers the startup and shutdown hooks and the
    per-request context middleware, and stores the manager on
    ``application.state["record"]`` — for health checks, and for the ``sillo``
    command, which reads it to offer the migration and account commands.

    The migrations package is set here rather than only where migrations run.
    Serving an application does not need it, but the manager on ``app.state``
    is the one ``sillo db:make`` reaches, and a manager that does not know
    where migrations live cannot write one.
    """
    from database.config import MIGRATIONS_MODULE, MODEL_MODULES, database_config

    manager = setup_record(application, database_config(), model_modules=MODEL_MODULES)
    manager.set_migrations(MIGRATIONS_MODULE)


def _register_work(application: silloApp, *, in_process: bool = False) -> None:
    """Start the queue connection and scheduler alongside the application.

    Not called by default — see create_app(). Left here complete rather than
    deleted so switching queues on is uncommenting one line, not going and
    reading how it was meant to be wired.

    Args:
        in_process: Also run a worker inside this process, so `sillo
            worker` is not needed. See :func:`_run_worker_in_process`.
    """
    from sillo.work.queue import Job

    work = setup_work(application, queue_name="default")

    # Every job class dispatches into this connection. Without it the first
    # dispatch raises "No queue connection configured for <Job>", naming the
    # job rather than the wiring.
    Job.on_connection(work["connection"])

    # Importing the package registers the job classes, so a queued payload can
    # be resolved back to the class that handles it.
    import app.jobs  # noqa: F401

    # Importing the module registers its scheduled tasks against the manager.
    from app.tasks import register_tasks

    register_tasks(application)

    if in_process:
        _run_worker_in_process(application, work["connection"])


def _run_worker_in_process(application: silloApp, connection) -> None:
    """Run the queue worker inside the application process.

    One process instead of two: convenient in development, and reasonable for a
    small single-instance deployment. Two things make it work.

    The worker is built on the *same* connection the application dispatches
    into. Build it from a URL instead and you get a second, separate queue —
    jobs go in one and the worker drains the other, and nothing appears to
    happen.

    It runs as a background task, because ``worker.run()`` does not return until
    the worker is stopped, and a startup hook that never returns is an
    application that never finishes starting.

    Know what you are trading away. The worker shares an event loop with request
    handling, so a job that blocks blocks responses; with more than one
    application process each gets its own worker, and an in-memory queue is not
    shared between them or kept across a restart. At that point run
    ``sillo queue:work`` separately and set ``QUEUE_URL`` to Redis.
    """
    import asyncio

    from sillo.work.commands import build_worker

    worker = build_worker(connection=connection, queues=["default"], concurrency=4)
    state: dict = {}

    async def start() -> None:
        state["task"] = asyncio.create_task(worker.run())

    async def stop() -> None:
        worker.stop()
        task = state.get("task")
        if task is not None:
            task.cancel()

    application.on_startup(start)
    application.on_shutdown(stop)


def _register_routes(application: silloApp) -> None:
    """Attach the application's routes.

    Order is significant. A router claims its whole prefix subtree, so the most
    specific prefix has to be mounted first — mounting "/api" before
    "/api/auth" would leave every auth route unreachable.

    Web pages are registered individually rather than mounted, because a
    prefix-less router would claim "/" and everything beneath it.
    """
    from routes.auth import router as auth_router  # /api/auth

    application.mount_router(auth_router)
    from routes.api import router as api_router  # /api

    application.mount_router(api_router)

    # Pages last, and one handler at a time. A prefix-less Router would mount at
    # "" and claim everything, including the admin panel that startup adds.
    from routes import web

    application.get("/", handler=web.welcome, name="welcome")


def _register_admin(application: silloApp) -> None:
    """Mount the admin panel and register its models."""
    from app.admin import register_admin

    register_admin(application)
