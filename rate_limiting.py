
import hashlib
import hmac
import math
import secrets

from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import jsonify, request
from sqlalchemy import case
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from config import app, db
from models import RateLimitBucket


# ---------- FoundIt Rate Limit Policies ----------

# Each policy specifies:
# (maximum requests, time window in seconds)

RATE_LIMIT_POLICIES = {
    "register": (5, 3600),
    "login": (10, 900),
    "google_login": (10, 900),
    "edit_profile": (12, 900),
    "change_password": (5, 3600),
    "delete_account": (5, 3600),
    "request_email_change": (3, 3600),
    "confirm_email_change": (5, 900),
    "login_verify_otp": (10, 300),
    "login_resend_otp": (3, 3600),
    "verify_email": (5, 300),
    "resend_verification": (3, 3600),
    "request_password_reset": (3, 3600),
    "validate_reset_token": (30, 900),
    "complete_password_reset": (5, 900),
}


def utc_now():
    """Return naive UTC for our current database columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_identifier(value):
    """
    Hash an IP or account identifier using the secret key.

    Do not store plaintext IP addresses or emails
    in the rate-limit table.
    """
    secret = app.config["SECRET_KEY"].encode("utf-8")

    return hmac.new(
        secret,
        value.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def get_request_identifier(field):
    """
    Read an identifier from the JSON request body.

    Missing identifiers are still protected by
    the per-IP rate limit.
    """
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None

    value = data.get(field)

    if not isinstance(value, str):
        return None

    normalized = value.strip().casefold()

    if not normalized:
        return None

    # Prevent excessive database/hash work for huge input.
    return normalized[:256]


def increment_bucket(action, identifier, limit, window_seconds):
    """
    Atomically increment a rate-limit bucket.

    Uses an INSERT ... ON CONFLICT DO UPDATE statement,
    supported by PostgreSQL and modern SQLite.

    Returns (allowed, retry_after_seconds).
    """
    now = utc_now()
    new_expiry = now + timedelta(seconds=window_seconds)

    table = RateLimitBucket.__table__
    key_hash = hash_identifier(identifier)

    dialect = db.engine.dialect.name

    if dialect == "postgresql":
        statement = pg_insert(table)
    elif dialect == "sqlite":
        statement = sqlite_insert(table)
    else:
        raise RuntimeError(
            "Rate limiting requires PostgreSQL or SQLite."
        )

    statement = statement.values(
        action=action,
        key_hash=key_hash,
        hit_count=1,
        expires_at=new_expiry,
    )

    window_expired = table.c.expires_at <= now

    statement = statement.on_conflict_do_update(
        index_elements=[
            table.c.action,
            table.c.key_hash,
        ],
        set_={
            "hit_count": case(
                (window_expired, 1),
                else_=table.c.hit_count + 1,
            ),
            "expires_at": case(
                (window_expired, new_expiry),
                else_=table.c.expires_at,
            ),
        },
    ).returning(
        table.c.hit_count,
        table.c.expires_at,
    )

    result = db.session.execute(statement).one()
    db.session.commit()

    hit_count, expires_at = result

    if hit_count <= limit:
        return True, 0

    retry_after = max(
        1,
        math.ceil((expires_at - now).total_seconds()),
    )

    return False, retry_after


def check_rate_limit(action, account_identifier=None):
    """
    Check the IP limit and, when available,
    an account-identifier limit.

    Return None if allowed, otherwise a Flask response.

    Rate-limit database failures deny the request
    rather than silently disabling protection.
    """
    if action not in RATE_LIMIT_POLICIES:
        raise ValueError(
            f"Unknown rate-limit policy: {action}"
        )

    limit, window_seconds = RATE_LIMIT_POLICIES[action]

    # Trust Flask's remote_addr only. Do not trust
    # arbitrary X-Forwarded-For request headers.
    ip_address = request.remote_addr or "unknown"

    identifiers = [
        ("ip", ip_address),
    ]

    if account_identifier:
        identifiers.append(
            ("account", account_identifier)
        )

    try:
        for identifier_type, value in identifiers:
            allowed, retry_after = increment_bucket(
                action=f"{action}:{identifier_type}",
                identifier=f"{identifier_type}:{value}",
                limit=limit,
                window_seconds=window_seconds,
            )

            if not allowed:
                response = jsonify({
                    "error": (
                        "Too many requests. "
                        "Please try again later."
                    ),
                    "retry_after": retry_after,
                })

                response.status_code = 429
                response.headers["Retry-After"] = str(
                    retry_after
                )

                return response

    except (SQLAlchemyError, RuntimeError):
        db.session.rollback()

        app.logger.exception(
            "Rate-limit storage unavailable"
        )

        return jsonify({
            "error": (
                "This action is temporarily unavailable. "
                "Please try again shortly."
            )
        }), 503

    return None


def rate_limit(action, identity_field=None):
    """
    Decorator for authentication endpoints.

    Usage:
        @rate_limit("login", "identifier")

    The endpoint executes only when the request
    is within the configured limits.
    """
    def decorator(view_function):
        @wraps(view_function)
        def wrapped(*args, **kwargs):
            identifier = (
                get_request_identifier(identity_field)
                if identity_field
                else None
            )

            blocked_response = check_rate_limit(
                action,
                account_identifier=identifier,
            )

            if blocked_response is not None:
                return blocked_response

            return view_function(*args, **kwargs)

        return wrapped

    return decorator


def cleanup_expired_buckets():
    """
    Remove old counters occasionally to prevent
    indefinite growth of the rate-limit table.

    Entries more than one day beyond expiry
    are no longer needed.
    """
    cutoff = utc_now() - timedelta(days=1)

    try:
        RateLimitBucket.query.filter(
            RateLimitBucket.expires_at < cutoff
        ).delete(synchronize_session=False)

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.warning(
            "Could not clean up expired rate-limit buckets"
        )


@app.after_request
def occasional_rate_limit_cleanup(response):
    """
    Opportunistic cleanup, approximately once
    per 100 requests.

    Cleanup failure does not prevent a completed
    application response from being returned.
    """
    if secrets.randbelow(100) == 0:
        cleanup_expired_buckets()

    return response
