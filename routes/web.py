"""Server-rendered pages.

One page. Handlers are registered individually in ``app/bootstrap.py`` rather
than mounted as a router: a ``Router`` with no prefix claims ``""`` and
everything beneath it, including the admin panel that mounts during startup.
"""

from __future__ import annotations

from sillo.core.http import Request, Response
from sillo.templating import render

from app.config import config


async def welcome(request: Request, response: Response):
    """The landing page."""
    return await render("welcome.html", {"app_name": config.app_name}, request=request)
