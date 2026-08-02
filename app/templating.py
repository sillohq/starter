"""Server-rendered HTML.

The engine is configured once here and set up during application assembly, so
handlers only ever call ``render``. Without ``setup_environment`` the render
helper raises ``NotImplementedError`` rather than falling back to something —
so this module existing is what makes any HTML page work.
"""

from __future__ import annotations

from pathlib import Path

from sillo.templating import TemplateConfig, TemplateEngine

BASE_DIR = Path(__file__).resolve().parent.parent

engine = TemplateEngine()


def setup(*, auto_reload: bool = True) -> TemplateEngine:
    """Configure the Jinja environment for this project.

    Args:
        auto_reload: Re-read a template when its file changes. Convenient in
            development, wasted stat calls in production — pass
            ``config.app_env == "local"``.
    """
    engine.setup_environment(
        TemplateConfig(
            template_dir=str(BASE_DIR / "templates"),
            auto_reload=auto_reload,
        )
    )
    return engine
