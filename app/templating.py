"""Server-rendered HTML.

Sillo 1.0 does not ship a templating layer — it left core along with the admin
panel, because not every application renders HTML and the ones that do disagree
about how. So the project owns its own Jinja environment, which is all the
framework was doing anyway.

The environment is built once here and handlers only ever call ``render``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sillo import html
from sillo.responses import BaseResponse

BASE_DIR = Path(__file__).resolve().parent.parent

_environment: Environment | None = None


def setup(*, auto_reload: bool = True) -> Environment:
    """Configure the Jinja environment for this project.

    Args:
        auto_reload: Re-read a template when its file changes. Convenient in
            development, wasted stat calls in production — pass
            ``config.app_env == "local"``.
    """
    global _environment
    _environment = Environment(
        loader=FileSystemLoader(str(BASE_DIR / "templates")),
        # On by default and worth leaving on: it is what stops a value in a
        # context dict being read as markup.
        autoescape=select_autoescape(("html", "xml")),
        auto_reload=auto_reload,
    )
    return _environment


def render(template: str, context: dict[str, Any] | None = None) -> BaseResponse:
    """Render *template* and return it as an HTML response.

    Raises:
        RuntimeError: If ``setup()`` has not run. Failing loudly beats
            rendering nothing and returning a blank page.
    """
    if _environment is None:
        raise RuntimeError(
            "The template environment is not configured. "
            "Call app.templating.setup() during application assembly."
        )
    return html(_environment.get_template(template).render(context or {}))
