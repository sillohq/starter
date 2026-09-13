"""Authentication routes.

Credential checking goes through ``User.verify_credentials``, which looks the
user up by email or username, rejects inactive accounts, verifies the hash and
stamps ``last_login`` — so these handlers stay about HTTP and never touch a
password hash directly.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from sillo import HttpContext, Router, created, json
from sillo.auth import useAuth
from sillo.auth.session_auth import login as start_session
from sillo.auth.session_auth import logout as end_session

from database.models.user import User

router = Router(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    """Payload for creating an account."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Payload for signing in. The identifier may be an email or a username."""

    identifier: str
    password: str


def _serialize(user: User) -> dict:
    """Shape a user for a response body, without the password hash."""
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "is_active": user.is_active,
    }


@router.post("/register", request_model=RegisterRequest, summary="Create an account")
async def register(ctx: HttpContext, payload):
    """Register a new user.

    ``payload`` is the validated ``RegisterRequest``: sillo injects the body
    into the first plain parameter after the context.

    The uniqueness check is deliberately explicit: letting the database
    constraint raise would surface as a 500 rather than a 409.
    """
    if await User.objects.get_by_email(payload.email) is not None:
        return json({"detail": "That email is already registered."}, status_code=409)
    if await User.objects.get_by_username(payload.username) is not None:
        return json({"detail": "That username is taken."}, status_code=409)

    user = await User.objects.create_user(
        email=payload.email,
        username=payload.username,
        password=payload.password,
    )
    return created(_serialize(user))


@router.post("/login", request_model=LoginRequest, summary="Sign in")
async def login(ctx: HttpContext, payload):
    """Exchange credentials for a session."""
    user = await User.verify_credentials(payload.identifier, payload.password)
    if user is None:
        # One message for every failure mode, so the response cannot be used
        # to discover which accounts exist.
        return json({"detail": "Invalid credentials."}, status_code=401)

    start_session(ctx, user)
    return json({"user": _serialize(user)})


@router.post("/logout", summary="Sign out")
async def logout(ctx: HttpContext):
    """End the current session."""
    end_session(ctx)
    return json({"detail": "Signed out."})


@router.get("/me", auth=useAuth(), summary="The signed-in user")
async def me(ctx: HttpContext):
    """Return the authenticated user.

    ``auth=useAuth()`` is the gate: unauthenticated requests are answered with
    a 401 before this handler runs, and the route's securityScheme is written
    into the OpenAPI spec — the gate and the document cannot drift apart.
    """
    return json(_serialize(ctx.user))
