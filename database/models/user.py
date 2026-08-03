"""The application's user model. There is only one.

Everyone is a row in ``users`` — the person who signs up through the API, and
the person who signs in to the admin. What separates them is ``is_staff``, not
a second table.

``sillo.users.UserBaseModel`` supplies the fields and behaviour authentication
depends on — email, username, hashed password, the active/staff/superuser
flags, and ``set_password``/``check_password``. ``sillo.admin``'s own user model
extends exactly the same base, which is why passing this one to ``AdminSite``
replaces it outright rather than adapting to it.

Three constraints are worth knowing before you edit this file:

* Only the modules listed in ``MODEL_MODULES`` (see ``database/config.py``) are
  registered with the ORM, and models are keyed by class name. Do not add
  ``sillo.users`` to that list — its built-in ``User`` would displace this one
  and your extra columns would silently stop being created. Do not add
  ``sillo.admin.default_user`` either; that is the second table this file
  exists to avoid.
* ``password`` is redeclared below, on purpose. The base class types it as a
  plain CharField.
* Tortoise does not call Django's ``contribute_to_class`` hook, so the manager
  is bound to this model explicitly at the bottom of the file.
"""

from __future__ import annotations

from sillo.record.fields import PasswordField
from sillo.users import UserBaseModel, UserManager
from tortoise import fields


class User(UserBaseModel):
    """A person who can sign in to Starter, including to the admin."""

    #: Query helpers: ``User.objects.create_user(...)``, ``get_by_email(...)``.
    objects = UserManager()

    #: Declared, not inherited. ``UserBaseModel`` types this as a plain
    #: CharField, which stores exactly what it is handed — so
    #: ``user.password = "hunter2"`` followed by ``save()`` writes the
    #: plaintext, silently. ``PasswordField`` hashes on the way to the
    #: database, and is what ``sillo.admin``'s own user model uses.
    password = PasswordField()

    # Add your own profile fields here. The authentication fields are
    # inherited and should not be redeclared. Note that `display_name`,
    # `identity` and `is_authenticated` are read-only properties on the base
    # class — declaring a field with one of those names shadows the property
    # and fails on assignment.
    full_name = fields.CharField(max_length=150, null=True)

    class Meta:
        table = "users"

    def __str__(self) -> str:
        return self.email


# Bind the manager to this model. Without this the manager has no model and
# falls back to sillo's built-in User, which this project does not register —
# producing a confusing "default_connection cannot be None" at the first query.
User.objects.contribute_to_class(User, "objects")
