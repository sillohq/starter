"""Background jobs.

Import each job class here. The worker resolves a queued payload back to its
class by importing the module the payload names, so a job in a module nobody
imports would still be found — but keeping them reachable from one place is how
you find them later, and it is what lets payloads queued by an older release,
which recorded only a class name, still resolve.

Dispatch from anywhere::

    from app.jobs import SendWelcomeEmail

    await SendWelcomeEmail.dispatch(user.id)

Nothing runs until a worker is going. Either uncomment
``_register_work(application, in_process=True)`` in ``app/bootstrap.py`` to run
one inside the application, or run ``make worker`` beside it.
"""

from __future__ import annotations

from app.jobs.welcome_email import SendWelcomeEmail

__all__ = ["SendWelcomeEmail"]
