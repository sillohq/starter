"""Server-rendered pages.

One page. Handlers are registered individually in ``app/bootstrap.py`` rather
than mounted as a router: a ``Router`` with no prefix claims ``""`` and
everything beneath it.
"""

from __future__ import annotations

from sillo import HttpContext

from app.config import config
from app.templating import render


async def welcome(ctx: HttpContext):
    """The landing page."""
    return render("welcome.html", {"app_name": config.app_name})
