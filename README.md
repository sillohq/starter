# Sillo Starter

A working Sillo application: session authentication with a real user model, an
admin panel, the Record ORM with migrations, server-rendered pages, a JSON API,
and a queue worker waiting to be switched on.

It is not a scaffold that produces code you then have to make work. Its CI boots
the application and exercises every route on every push, so what you clone is
known to run.

```bash
git clone https://github.com/sillohq/starter.git myapp
cd myapp
make setup
make dev
```

Then open <http://localhost:8000>.

---

## Contents

- [What you get](#what-you-get)
- [Requirements](#requirements)
- [Getting started](#getting-started)
- [Project layout](#project-layout)
- [Configuration](#configuration)
- [Database and migrations](#database-and-migrations)
- [Authentication](#authentication)
- [The admin panel](#the-admin-panel)
- [Pages and templates](#pages-and-templates)
- [The JSON API](#the-json-api)
- [Background work](#background-work)
- [Testing](#testing)
- [Deploying](#deploying)
- [Things that will bite you](#things-that-will-bite-you)

---

## What you get

| | |
| --- | --- |
| **Auth** | Session-based, with registration, sign-in and sign-out on both pages and the API |
| **Users** | A `User` model with a manager, password hashing and `verify_credentials` |
| **Admin** | Mounted at `/admin/`, with the user model registered |
| **Database** | Record (Tortoise) with SQLite by default, and real migrations |
| **Pages** | Jinja templates, a base layout, and `/static` served in development |
| **API** | JSON routes under `/api`, with OpenAPI at `/docs` |
| **Queue** | A worker and scheduler, wired but commented out |
| **Tooling** | `make` targets, ruff, pytest, and CI on three Python versions |

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

SQLite needs nothing else. Postgres or MySQL need a running server and one
extra driver; see [Configuration](#configuration).

## Getting started

```bash
make setup      # install dependencies, create .env, create the database
make admin      # create an administrator account
make dev        # run with reload on http://localhost:8000
```

`make` on its own lists every task:

| Target | What it does |
| --- | --- |
| `make setup` | Everything below, in order, for a fresh clone |
| `make install` | Install Python dependencies |
| `make migrate` | Create the database and apply pending migrations |
| `make migration m="add_posts"` | Write a migration from model changes and apply it |
| `make rollback to=0001_initial` | Roll the database back |
| `make history` | Show which migrations have been applied |
| `make admin` | Create an administrator |
| `make dev` | Run with reload |
| `make serve` | Run as production would, with workers |
| `make worker` / `make scheduler` | Background processes, once enabled |
| `make test` | Run the test suite |
| `make lint` / `make format` | Check or apply formatting and lint rules |
| `make check` | Everything CI runs |

## Project layout

```
app/
  main.py         ASGI entrypoint — `uvicorn app.main:app`
  bootstrap.py    Application assembly. Start reading here
  config.py       Typed settings, loaded from the environment
  admin.py        Admin panel registration
  templating.py   Jinja setup
  jobs/           Queue jobs
  tasks/          Scheduled tasks
database/
  config.py       Tortoise config, read by the migration engine
  models/         Your models. `user.py` is provided
  migrations/     Generated migrations — commit these
routes/
  web.py          Server-rendered pages
  auth.py         JSON auth endpoints
  api.py          Everything else under /api
templates/        Jinja templates
static/           CSS, images, anything served as-is
scripts/
  worker.py       Queue worker
  scheduler.py    Scheduled task runner
  create_admin.py Administrator bootstrap
  smoke.py        Boots the app and hits every route
tests/
```

`app/bootstrap.py` is the one file worth reading first. Everything the
application is made of is assembled there, in order, with the reasoning written
down beside each step.

## Configuration

All configuration is environment variables. Nothing is read from a file at
runtime — `app/config.py` declares the settings and their types, and `.env` is
loaded at import.

```bash
APP_NAME=Starter
APP_ENV=local                 # local | testing | staging | production
DEBUG=true
HOST=127.0.0.1
PORT=8000
SECRET_KEY=...                # signs sessions. Change it
DATABASE_URL=sqlite://storage/starter.db
```

Read values through `config`, not `os.getenv`:

```python
from app.config import config

config.database_url
```

A typo in a variable name then fails at startup with a clear message, instead of
becoming `None` at request time.

### Another database

```bash
# Postgres
DATABASE_URL=postgres://user:password@localhost:5432/starter
uv add asyncpg

# MySQL
DATABASE_URL=mysql://user:password@localhost:3306/starter
uv add aiomysql
```

Nothing else changes. The driver is read from the URL.

## Database and migrations

Models live in `database/models/` and must be imported in that package's
`__init__.py` — Tortoise only sees what is imported there, and a model it cannot
see fails later with `default_connection cannot be None` rather than anything
about the missing import.

```bash
make migration m="add_posts"   # write a migration from your model changes, and apply it
make migrate                   # apply anything pending, e.g. after pulling
make history                   # what has been applied
make rollback to=0001_initial  # go back
```

Migrations are Tortoise's own, tracked in the `tortoise_migrations` table.
Commit the files in `database/migrations/` — they are part of the project.

The application does **not** create tables on startup. `db_generate_schemas` is
off, because generating schemas on boot creates tables outside the migration
history, and has every process race to run DDL — an app, a worker and a
scheduler sharing one SQLite file will deadlock on it. Set
`DB_GENERATE_SCHEMAS=true` only for a throwaway database with no migrations.

## Authentication

Sessions, not tokens. A cookie holds the session id; the user is loaded on each
request by `AuthenticationMiddleware`.

Both the pages and the API go through `User.verify_credentials`, which looks the
user up by email or username, rejects inactive accounts, verifies the hash and
stamps `last_login`. Handlers stay about HTTP and never touch a password hash.

```python
from database.models.user import User
from sillo.auth.session_auth import login, logout

user = await User.verify_credentials(identifier, password)
if user:
    login(request, user)
```

In a handler, `request.user` is the signed-in user. It **raises** when no
authentication middleware is installed, so guard it if the route might run
without one:

```python
user = getattr(request, "user", None)
if user is None or not user.is_authenticated:
    ...
```

Passwords must be at least 8 characters and contain an uppercase letter, a digit
and a special character. The framework enforces this and reports precisely which
rule failed.

### Wanting JWT instead

`sillo.auth.jwt_auth` provides `JWTAuthBackend` and `TokenForUser`. Swap the
backend in `app/bootstrap.py`. One thing to know: pass `identifier="sub"`.

```python
JWTAuthBackend(secret_key=config.secret_key, identifier="sub")
```

The backend defaults to reading the `id` claim, but tokens carry the user id in
`sub`. With the default, every authenticated request silently fails to load a
user, with nothing logged.

## The admin panel

At `/admin/` — note the trailing slash, the routes need it.

```bash
make admin
```

Registration lives in `app/admin.py`, inside `register_admin`. To add a model:

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    verbose_name = "Posts"
    list_display = ["id", "title", "created_at"]
    search_fields = ["title"]
```

Sign-in is checked against the project's own `User`, so people use their normal
account. An account needs `is_staff` to get in — `make admin` sets it.

The admin authenticates through the session, which is why the session middleware
is registered where it is in `bootstrap.py` — and why it stays on even if you
move the rest of the app to JWT.

## Pages and templates

Templates are Jinja, under `templates/`. `app/templating.py` configures the
engine, and `create_app` sets it up before any page renders — without that,
`render` raises `NotImplementedError`.

```python
from sillo.templating import render

async def home(request, response):
    return await render("pages/home.html", {"title": "Home"}, request=request)
```

Pages are registered **individually** in `bootstrap.py`, not mounted as a
router:

```python
application.get("/", handler=web.home, name="home")
```

A `Router` with no prefix claims `""` and everything under it, including the
admin panel that mounts during startup. Registering handlers one at a time
avoids that.

Form bodies are read with `await request.form` — an async *property*, with no
call parentheses. `await request.form()` awaits the coroutine and then calls the
result, which fails as `'coroutine' object is not callable`.

## The JSON API

Routers under `/api`, documented at `/docs`.

```python
from sillo import Router

router = Router(prefix="/api/posts", tags=["posts"])

@router.get("/", summary="List posts")
async def index(request, response):
    return response.json([...])
```

Mount it in `_register_routes`. **Order matters**: a router claims its whole
prefix subtree, so mount the most specific prefix first. Mounting `/api` before
`/api/auth` leaves every auth route unreachable.

## Background work

The worker and scheduler are written and ready, and switched off. In
`app/bootstrap.py`:

```python
# _register_work(application)
```

Uncomment it, then:

```bash
make worker
make scheduler
```

Jobs go in `app/jobs/` and must be imported in that package's `__init__.py` so
the worker can resolve a queued payload back to the class that handles it.
Scheduled tasks go in `app/tasks/`.

The default queue is in-memory, which means jobs are lost on restart and are not
shared between processes. Switch to Redis in `scripts/worker.py` before relying
on it for anything.

## Testing

```bash
make test
```

`tests/conftest.py` provides an app fixture against a temporary database.

There is also a smoke test that boots the application and calls every route:

```bash
uv run python scripts/smoke.py
```

It is worth running after any dependency bump. A project can import cleanly,
render every template and still fail on the first real request — middleware
ordering, a missing static mount, an auth backend reading the wrong claim. Those
only surface when something actually calls the app.

CI runs the suite, the linter and the smoke test on Python 3.11, 3.12 and 3.13,
on every push and once a week.

## Deploying

```bash
make serve
```

which is:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Set before you do:

```bash
APP_ENV=production
DEBUG=false
SECRET_KEY=<a real secret>
DATABASE_URL=postgres://...
```

Then apply migrations — `make migrate` — as part of the deploy, before traffic
reaches the new code.

**`--workers` and SQLite do not mix.** Several processes writing one SQLite file
contend for locks. Use Postgres or MySQL in production, or stay on one worker.

**Serve static files with a web server**, not with Python:

```nginx
location /static/ {
    alias /srv/myapp/static/;
    expires 30d;
}
location / {
    proxy_pass http://127.0.0.1:8000;
}
```

The `/static` mount in `bootstrap.py` is for development and small deployments.
With a proxy in front it never sees traffic.

## Things that will bite you

Collected from actually running this, not from reading the source.

1. **Middleware order is inside-out.** `application.use()` puts the newest
   registration *outermost*, so the last one registered runs *first*. Session
   middleware is registered after authentication so it ends up outside it, and
   therefore runs before it — because the auth backend reads the session.

2. **A prefix-less router swallows everything.** Mounting one claims `""` and
   every path beneath it, including routes registered later during startup.
   Register root-level pages individually.

3. **Models must be imported in `database/models/__init__.py`.** Tortoise only
   sees what is imported there. A model it cannot see fails on first query with
   "default_connection cannot be None".

4. **`request.user` raises without auth middleware.** It does not return `None`.

5. **`await request.form`, not `await request.form()`.** It is a property.

6. **Admin routes need the trailing slash.** `/admin/login/`, not `/admin/login`.

7. **Do not add `sillo.users` to `model_modules`.** Models are keyed by class
   name, so the framework's built-in `User` would displace this project's own
   and its extra columns would never be created — with no error.

8. **Schema generation is off on purpose.** See
   [Database and migrations](#database-and-migrations).

## Licence

BSD-3-Clause. Use it for anything.
