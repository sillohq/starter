"""Application assembly.

``create_app`` is the single place where the application is put together:
middleware, then infrastructure, then routes. Keeping it a function rather than
module-level code means tests can build an isolated instance, and the import in
``app/main.py`` stays trivial.
"""

from __future__ import annotations

from sillo import silloApp
from sillo.security import (
    CORSMiddleware,
    CorsConfig,
)
from sillo.session import SessionConfig, SessionMiddleware
from sillo.record import DatabaseConfig, setup_record
from sillo.auth import AuthenticationMiddleware
from sillo.auth.session_auth import SessionAuthBackend
from sillo.work import setup_work
from sillo.admin import setup_admin

from app.config import config
from app.config import cors_origins
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
    # Background work is wired but switched off. Uncomment this line, and the
    # `worker` and `scheduler` entries in the Makefile, when you have a job or
    # a scheduled task worth running. See app/jobs/ and app/tasks/.
    # _register_work(application)
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
    ``application.state["record"]`` for health checks.
    """
    setup_record(
        application,
        # Off by default — see config.db_generate_schemas for why.
        DatabaseConfig(
            url=config.database_url,
            pool_size=config.db_pool_size,
            echo=config.db_echo,
            generate_schemas=config.db_generate_schemas,
        ),
        # Only these modules are scanned for models, and models are keyed by
        # class name — so do not add "sillo.users" here. Its built-in `User`
        # would displace the project's own and stop its columns being created.
        model_modules=[
            "database.models",
            # The admin panel stores its activity log and roles in these models.
            "sillo.admin.models",
        ],
    )


def _register_work(application: silloApp) -> None:
    """Start the queue connection and scheduler alongside the application.

    Not called by default — see create_app(). Left here complete rather than
    deleted so switching queues on is uncommenting one line, not going and
    reading how it was meant to be wired.
    """
    setup_work(application, queue_name="default")

    # Importing the module registers its scheduled tasks against the manager.
    from app.tasks import register_tasks

    register_tasks(application)


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

    application.get("/", handler=web.home, name="home")
    application.get("/login", handler=web.login_form, name="login")
    application.post("/login", handler=web.login_submit, name="login.submit")
    application.get("/register", handler=web.register_form, name="register")
    application.post("/register", handler=web.register_submit, name="register.submit")
    application.post("/logout", handler=web.logout, name="logout")


def _register_admin(application: silloApp) -> None:
    """Mount the admin panel and register its models."""
    from app.admin import register_admin

    register_admin(application)
