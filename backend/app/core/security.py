import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
import jwt
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import logger

# Initialize Argon2 PasswordHasher with OWASP recommended configuration
_password_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash."""
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as exc:
        logger.error(f"Unexpected error during password verification: {exc}")
        return False


def create_access_token(
    subject: str,
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generates a signed JWT access token."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if claims:
        payload.update(claims)

    encoded_jwt = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a signed JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Session has expired. Please log in again.")
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(f"Invalid authentication token: {exc}")


def generate_csrf_token() -> str:
    """Generates a cryptographically secure random token for CSRF protection."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(header_token: Optional[str], cookie_token: Optional[str]) -> bool:
    """Validates double-submit CSRF token using constant-time string comparison."""
    if not header_token or not cookie_token:
        return False
    return hmac.compare_digest(header_token, cookie_token)


# In-memory rate limiting fallback for login attempts
_login_attempts: Dict[str, list[float]] = {}


def check_and_record_login_attempt(
    identifier: str,
    max_attempts: Optional[int] = None,
    lockout_seconds: Optional[int] = None,
) -> Tuple[bool, int]:
    """
    Checks rate limit for an identifier (e.g. IP or email).
    Returns (is_allowed, remaining_lockout_seconds).
    Removes timestamps outside the lockout window.
    """
    settings = get_settings()
    max_att = max_attempts or settings.rate_limit_login_attempts
    lock_sec = lockout_seconds or settings.rate_limit_lockout_seconds
    now = time.time()

    attempts = _login_attempts.setdefault(identifier, [])
    # Filter attempts within lockout window
    valid_attempts = [ts for ts in attempts if now - ts < lock_sec]
    _login_attempts[identifier] = valid_attempts

    if len(valid_attempts) >= max_att:
        oldest_in_window = valid_attempts[0]
        remaining = int(lock_sec - (now - oldest_in_window))
        return False, max(1, remaining)

    # Record current attempt
    valid_attempts.append(now)
    return True, 0


def reset_login_attempts(identifier: str) -> None:
    """Clears failed login attempts upon successful authentication."""
    if identifier in _login_attempts:
        del _login_attempts[identifier]
