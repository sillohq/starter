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
| **Auth** | Session-based over JSON, with JWT written and commented out |
| **Users** | A `User` model with a manager, password hashing and `verify_credentials` |
| **Admin** | Mounted at `/admin/`, with the user model registered |
| **Database** | Record (Tortoise) with SQLite by default, and real migrations |
| **Pages** | One Jinja template and a stylesheet, with `/static` served in development |
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

Or without make, through the project's own console:

```bash
uv run python console.py                    # every command
uv run python console.py db migrate         # create the database, apply migrations
uv run python console.py db make add_posts --apply
uv run python console.py db plan
uv run python console.py db rollback 0001_initial
uv run python console.py user admin ada@example.com ada
uv run python console.py user list
uv run python console.py worker
uv run python console.py scheduler
uv run python console.py serve --reload
```

`uv run` rather than plain `python`, because it always uses this project's
environment. A virtual environment activated somewhere above this directory
shadows it, and bare `python` then finds whatever sillo lives there — usually an
older one, which fails with an ImportError or an AttributeError several frames
deep. `console.py` checks for this and says so, but running it through `uv`
avoids the question.

`console.py` is a thin layer over `sillo.record.commands`,
`sillo.users.commands` and `sillo.work.commands`. The framework provides the
operations and ships no command-line interface of its own; this file decides
what to call them and how to print the result. Add your own commands to it —
it needs nothing beyond argparse.

`make` on its own lists every task:

| Target | What it does |
| --- | --- |
| `make setup` | Everything below, in order, for a fresh clone |
| `make install` | Install Python dependencies |
| `make migrate` | Create the database and apply pending migrations |
| `make migration m="add_posts"` | Write a migration from model changes and apply it |
| `make plan` | Show which migrations would run |
| `make rollback to=0001_initial` | Roll the database back |
| `make admin e=ada@x.com u=ada` | Create an administrator |
| `make users` | List users |
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
  config.py       How this project connects — app and migrations share it
  models/         Your models. `user.py` is provided
  migrations/     Generated migrations — commit these
routes/
  web.py          Server-rendered pages
  auth.py         JSON auth endpoints
  api.py          Everything else under /api
templates/        Jinja templates
static/           CSS, images, anything served as-is
console.py        Management commands — see `python console.py`
scripts/
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
`__init__.py` — the ORM only sees what is imported there, and a model it cannot
see fails later with `default_connection cannot be None` rather than anything
about the missing import.

```bash
make migration m="add_posts"   # write a migration from your model changes, and apply it
make migrate                   # apply anything pending, e.g. after pulling
make plan                      # what would run
make rollback to=0001_initial  # go back
```

Migrations are applied and recorded by sillo Record, tracked in the
`tortoise_migrations` table. Commit the files in `database/migrations/` — they
are part of the project.

There is no migration config file. `database/config.py` describes how the
project connects, once, and both the application and the migration commands read
it — it sits beside the models it registers and the migrations it points at:

```python
def database() -> DatabaseManager:
    manager = DatabaseManager(database_config())
    manager.register_models(*MODEL_MODULES).set_migrations(MIGRATIONS_MODULE)
    return manager
```

Change the connection there and migrations follow, with nothing to keep in step
by hand. It is also how a script of your own opens the database:

```python
from database.config import database

async with database():
    await User.all()
```

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

### Switching to JWT

The wiring is written and commented out in `app/bootstrap.py`. Uncomment the
import and swap the backend:

```python
from sillo.auth.jwt_auth import JWTAuthBackend

backend = JWTAuthBackend(secret_key=config.jwt_secret, identifier="sub")
```

Then add `JWT_SECRET` to `.env` and `jwt_secret` to `app/config.py`, and issue
tokens with `TokenForUser`:

```python
from sillo.auth.jwt_auth import TokenForUser

pair = TokenForUser(user, secret=config.jwt_secret).token_pair()
```

`identifier="sub"` is required, not cosmetic. The backend defaults to reading
the `id` claim, but tokens carry the user id in `sub` — so with the default,
every authenticated request silently fails to load a user, with nothing logged.

Keep the session middleware either way: the admin panel authenticates through
the session regardless of what the rest of the application uses.

## The admin panel

At `/admin/` — note the trailing slash, the routes need it.

```bash
make admin e=ada@example.com u=ada
```

Registration lives in `app/admin.py`, inside `register_admin`. To add a model:

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    verbose_name = "Posts"
    list_display = ["id", "title", "created_at"]
    search_fields = ["title"]
```

### One user model

There is no separate administrator account. Sign-in is checked against the
project's own `User`, so people use their normal account, and adding a field to
`User` adds it everywhere.

That works because both the admin's default user model and yours extend
`sillo.users.UserBaseModel` — the same `set_password`, `check_password` and
`verify_credentials`. Passing your model is all it takes:

```python
AdminSite(title="…", prefix=config.admin_prefix, user_model=User)
```

`database/config.py` registers this project's models and the admin's activity
log, so a fresh database holds one table for people — `users` — plus
`admin_activity`, which records who changed what and when.

What it does **not** register is `sillo.admin.default_user`, the admin's
fallback user model. That would add a second set of accounts beside `users` to
keep in step, or to forget about.

`User` also declares `password = PasswordField()`. `UserBaseModel` types that
column as a plain `CharField`, which stores exactly what it is handed, so
`user.password = "hunter2"` followed by `save()` writes the plaintext without
complaint. `PasswordField` hashes on the way to the database, and is what
`sillo.admin`'s own user model uses — declaring it is what makes this model the
same kind of thing.

To drop the audit log, remove `"sillo.admin.models"` from `MODEL_MODULES` and
run `make migration m="drop activity log"`. The admin works either way — without
the table it records nothing, and the entry disappears from the sidebar rather
than leading to an error.

An account needs `is_staff` to get in, and `make admin` sets it. The flag is
load-bearing rather than decorative: every registered user holds a session, so
without it the sign-up form would be the way into the admin. Clearing `is_staff`
or `is_active` takes effect on the account's next request.

The admin authenticates through the session, which is why the session middleware
is registered where it is in `bootstrap.py` — and why it stays on even if you
move the rest of the app to JWT.

## Pages and templates

One page, at `/`, rendered from `templates/welcome.html`. Replace it with
whatever your application actually is.

`app/templating.py` configures Jinja, and `create_app` sets it up before any
page renders — without that, `render` raises `NotImplementedError`.

```python
from sillo.templating import render


async def welcome(request, response):
    return await render("welcome.html", {"app_name": config.app_name}, request=request)
```

Pages are registered **individually** in `bootstrap.py`, not mounted as a
router:

```python
application.get("/", handler=web.welcome, name="welcome")
```

A `Router` with no prefix claims `""` and everything under it, including the
admin panel that mounts during startup.

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

### The worker in the same process

To skip the separate process entirely — useful in development, and reasonable
for a small single-instance deployment — pass `in_process=True` instead:

```python
_register_work(application, in_process=True)
```

The application then runs its own worker, on the same queue it dispatches into,
and `make worker` is not needed. Two things make that work, and both are easy to
get wrong by hand: the worker is built from the application's *connection*
rather than from a URL, so jobs go in and come out of the same queue; and it
runs as a background task, because `worker.run()` does not return until the
worker stops.

What it costs: the worker shares an event loop with request handling, so a job
that blocks blocks responses. With more than one application process each gets
its own worker, and the in-memory queue is neither shared between them nor kept
across a restart. At that point run `make worker` separately and point
`QUEUE_URL` at Redis.

Jobs go in `app/jobs/` and must be imported in that package's `__init__.py` so
the worker can resolve a queued payload back to the class that handles it.
Scheduled tasks go in `app/tasks/`.

The default queue is in-memory, which means jobs are lost on restart and are not
shared between processes. Set `QUEUE_URL=redis://localhost:6379` before relying
on it for anything — `console.py worker` reads it and picks the connection.

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

3. **Models must be imported in `database/models/__init__.py`.** The ORM only
   sees what is imported there. A model it cannot see fails on first query with
   "default_connection cannot be None".

4. **`request.user` raises without auth middleware.** It does not return `None`.

5. **`await request.form`, not `await request.form()`.** It is a property.

6. **Admin routes need the trailing slash.** `/admin/login/`, not `/admin/login`.

7. **Do not add `sillo.users` to `model_modules`.** Models are keyed by class
   name, so the framework's built-in `User` would displace this project's own
   and its extra columns would never be created — with no error.

8. **Do not add `sillo.admin.default_user` to `MODEL_MODULES`.** Its
   `AdminUser` would sit beside your `User` as a second set of accounts, and
   its `AdminRole` beside that. This project has one user model.
   `sillo.admin.models` is a different thing — the activity log — and is
   registered on purpose.

9. **The admin's login form field is `email`, not `username`.** It accepts
   either value, but the form field is named `email`.

10. **Run the console through `uv run`, not bare `python`.** An activated
    virtual environment from a parent directory shadows this project's, and the
    sillo it finds there is usually older than this project needs.

11. **Schema generation is off on purpose.** See
    [Database and migrations](#database-and-migrations).

## Licence

BSD-3-Clause. Use it for anything.
