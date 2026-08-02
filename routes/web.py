"""Server-rendered pages.

These handlers are registered individually rather than mounted as a router. A
router with no prefix claims ``""`` and would swallow everything registered
after it — including the admin panel, which mounts during startup.

Credentials go through ``User.verify_credentials`` and the session through
``sillo.auth.session_auth``, exactly as the JSON API in routes/auth.py does, so
signing in on a page and signing in over the API are the same operation.
"""

from __future__ import annotations

from sillo.auth.session_auth import login as start_session
from sillo.auth.session_auth import logout as end_session
from sillo.core.http import Request, Response
from sillo.templating import render

from app.config import config
from database.models.user import User


def _current_user(request: Request):
    """The signed-in user, or None.

    ``request.user`` raises when no authentication middleware is installed, so
    this stays defensive: a template asking "is anyone signed in" should not be
    able to take a page down.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return user


def _context(request: Request, **extra):
    """Values every page needs, merged with the page's own."""
    return {"app_name": config.app_name, "user": _current_user(request), **extra}


async def home(request: Request, response: Response):
    """The landing page."""
    return await render("pages/home.html", _context(request), request=request)


async def login_form(request: Request, response: Response):
    """Show the sign-in form."""
    if _current_user(request):
        return response.redirect("/")
    return await render("pages/login.html", _context(request), request=request)


async def login_submit(request: Request, response: Response):
    """Check credentials and open a session.

    ``request.form`` is an async *property*: ``await request.form``, with no
    call parentheses. Writing ``await request.form()`` awaits the coroutine and
    then calls the FormData it returned, which fails as
    "'coroutine' object is not callable".
    """
    form = await request.form
    user = await User.verify_credentials(
        str(form.get("identifier") or ""), str(form.get("password") or "")
    )
    if user is None:
        # One message for every failure, so the form cannot be used to discover
        # which accounts exist.
        return await render(
            "pages/login.html",
            _context(request, error="Those credentials did not match."),
            status_code=401,
            request=request,
        )

    start_session(request, user)
    return response.redirect("/", status_code=303)


async def register_form(request: Request, response: Response):
    """Show the sign-up form."""
    if _current_user(request):
        return response.redirect("/")
    return await render("pages/register.html", _context(request), request=request)


async def register_submit(request: Request, response: Response):
    """Create an account and sign the new user in."""
    form = await request.form
    email = str(form.get("email") or "").strip()
    username = str(form.get("username") or "").strip()
    password = str(form.get("password") or "")

    error = None
    if len(password) < 8:
        error = "Passwords need at least 8 characters."
    elif await User.objects.get_by_email(email) is not None:
        error = "That email is already registered."
    elif await User.objects.get_by_username(username) is not None:
        error = "That username is taken."

    if error:
        return await render(
            "pages/register.html",
            _context(request, error=error),
            status_code=422,
            request=request,
        )

    user = await User.objects.create_user(email=email, username=username, password=password)
    start_session(request, user)
    return response.redirect("/", status_code=303)


async def logout(request: Request, response: Response):
    """End the session."""
    end_session(request)
    return response.redirect("/", status_code=303)
