"""Authentication routes.

Credential checking goes through ``User.verify_credentials``, which looks the
user up by email or username, rejects inactive accounts, verifies the hash and
stamps ``last_login`` — so these handlers stay about HTTP and never touch a
password hash directly.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from sillo import Router
from sillo.core.http import Request, Response
from sillo.auth.session_auth import login as start_session
from sillo.auth.session_auth import logout as end_session

from app.config import config
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
async def register(request: Request, response: Response, payload) -> Response:
    """Register a new user.

    The uniqueness check is deliberately explicit: letting the database
    constraint raise would surface as a 500 rather than a 409.
    """
    if await User.objects.get_by_email(payload.email) is not None:
        return response.json({"detail": "That email is already registered."}, status_code=409)
    if await User.objects.get_by_username(payload.username) is not None:
        return response.json({"detail": "That username is taken."}, status_code=409)

    user = await User.objects.create_user(
        email=payload.email,
        username=payload.username,
        password=payload.password,
    )
    return response.json(_serialize(user), status_code=201)


@router.post("/login", request_model=LoginRequest, summary="Sign in")
async def login(request: Request, response: Response, payload) -> Response:
    """Exchange credentials for a session."""
    user = await User.verify_credentials(payload.identifier, payload.password)
    if user is None:
        # One message for every failure mode, so the response cannot be used
        # to discover which accounts exist.
        return response.json({"detail": "Invalid credentials."}, status_code=401)

    start_session(request, user)
    return response.json({"user": _serialize(user)})


@router.post("/logout", summary="Sign out")
async def logout(request: Request, response: Response) -> Response:
    """End the current session."""
    end_session(request)
    return response.json({"detail": "Signed out."})


@router.get("/me", summary="The signed-in user")
async def me(request: Request, response: Response) -> Response:
    """Return the authenticated user, or 401 when there is none.

    ``request.user`` is populated by the authentication middleware registered
    in ``app.bootstrap``.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return response.json({"detail": "Not authenticated."}, status_code=401)
    return response.json(_serialize(user))
