"""Record models for Starter.

Every model must be imported here. The ORM is pointed at this package and
discovers models from the names it exports — a model that lives in a sibling
file but is never imported here does not exist as far as the database is
concerned, and its first query fails with a confusing
"default_connection cannot be None".

The block below is maintained by ``sillo-start generate model``. Edit it by
hand if you like; the tool rewrites only what is between the markers, so
anything you add outside them is left alone.
"""

from __future__ import annotations

# >>> sillo-start: models >>>
from database.models.user import User

#: The explicit registry the ORM reads, in preference to scanning this module.
__models__ = [User]

__all__ = ["User"]
# <<< sillo-start: models <<<
