"""Admin panel.

Sillo 1.0 does not ship an admin — it is its own package now, `warder`, which
declares a resource as values rather than as class attributes on a subclass.

The site is built and populated before it is mounted: `add` collects the
declarations, `mount` is what attaches the routes.
"""

from __future__ import annotations

from sillo import SilloApp
from warder import Admin, Auth, Column, Filter, List, Resource

from app.config import config
from database.models.user import User


def register_admin(application: SilloApp) -> Admin:
    """Build the admin site, register models, and mount it.

    Admin logins are checked against :class:`~database.models.user.User`, so
    people sign in with their normal account rather than a separate admin one.
    Mark an account with ``is_staff`` to let it in.

    Returns:
        The mounted admin site.
    """
    admin = Admin(
        title="Starter Admin",
        prefix=config.admin_prefix,
        auth=Auth(users=User),
        # This project installs its own session middleware in app/bootstrap.py.
        # Letting warder add a second one gives the request two sessions on two
        # cookies, and the one that wins is whichever middleware is outermost --
        # so a visitor signs in and the next request reads the other, empty one.
        sessions=False,
    )

    users = Resource(
        User,
        label="User",
        plural="Users",
        search=("email", "username"),
        sort="-id",
        list=List(
            Column("id"),
            Column("email", link=True),
            Column("username"),
            Column("is_active"),
            Column("is_staff"),
            Column("last_login"),
            filters=(
                Filter("bool", "is_active"),
                Filter("bool", "is_staff"),
                Filter("bool", "is_superuser"),
            ),
        ),
    )

    # Register your own models the same way, before the mount call below:
    #
    #     from database.models.post import Post
    #
    #     posts = Resource(
    #         Post,
    #         search=("title",),
    #         list=List(Column("id"), Column("title", link=True), Column("created_at")),
    #     )
    #     admin.add(users, posts)

    admin.add(users)
    admin.mount(application)
    return admin
