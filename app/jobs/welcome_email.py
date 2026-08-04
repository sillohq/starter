"""An example job: the work that follows a sign-up but should not delay it.

A job is a class with a ``handle()``. Whatever the constructor takes is what
you dispatch with, and it is what the worker rebuilds the job from — so keep
those arguments to things that survive being written to a queue and read back:
ids, addresses, plain strings and numbers. Not a model instance, not an open
connection, not a request.

Passing the id and loading the row inside ``handle()`` is the habit worth
having. A user serialised at dispatch is a user as they were then; by the time
the job runs the row may have changed, or been deleted.
"""

from __future__ import annotations

import logging

from sillo.work.queue import Job

logger = logging.getLogger("app.jobs")


class SendWelcomeEmail(Job):
    """Greet someone who has just signed up.

    Usage::

        await SendWelcomeEmail.dispatch(user.id)
    """

    def __init__(self, user_id: int, template: str = "welcome") -> None:
        """Init

        Args:
            user_id: Who to write to. Looked up when the job runs.
            template: Which message to send.
        """
        self.user_id = user_id
        self.template = template

    async def handle(self) -> None:
        """Send the message.

        Raising from here marks the job failed and records the traceback, which
        is what you want: a job that swallows its own errors is a job that
        silently does nothing.
        """
        from database.models.user import User

        user = await User.get_or_none(id=self.user_id)
        if user is None:
            # Deleted between dispatch and delivery. Not an error worth
            # retrying — there is nobody to write to.
            logger.info("welcome email skipped: user %s no longer exists", self.user_id)
            return

        # Replace this with your mail client. The job is the shape; sending is
        # your business.
        logger.info("welcome email (%s) to %s <%s>", self.template, user.username, user.email)
