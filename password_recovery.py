
import hashlib
import os
import secrets

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import app, db
from models import User, PasswordResetToken
from email_sender import send_password_reset_email
from password_security import validate_password
from rate_limiting import rate_limit


# ---------- Password Recovery ----------

password_recovery_bp = Blueprint(
    "password_recovery",
    __name__
)

RESET_EXPIRY_MINUTES = 15

GENERIC_RESET_MESSAGE = (
    "If an account exists for this email, "
    "we'll send a password reset link."
)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_reset_token(token):
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def normalized_datetime(value):
    if value.tzinfo is not None:
        return value.astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    return value


def email_allowed_for_delivery(email):
    """
    Respect the same Resend testing restriction
    used by the registration flow.
    """
    test_mode = os.getenv(
        "OTP_TEST_MODE", "true"
    ).lower() == "true"

    if not test_mode:
        return True

    allowed = os.getenv(
        "OTP_TEST_EMAIL", ""
    ).strip().lower()

    return bool(allowed) and email == allowed


@password_recovery_bp.route(
    "/api/forgot-password",
    methods=["POST"]
)
@rate_limit("request_password_reset", "email")
def forgot_password():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Request body must be valid JSON."
        }), 400

    email = data.get("email")

    if (
        not isinstance(email, str)
        or not email.strip()
        or len(email.strip()) > 120
    ):
        return jsonify({
            "error": "Enter a valid email address."
        }), 400

    email = email.strip().lower()

    user = User.query.filter_by(email=email).first()

    # Never disclose whether the account exists.
    # Also do not attempt unsupported email delivery
    # while Resend is restricted to its test inbox.
    if user is None or not email_allowed_for_delivery(email):
        return jsonify({
            "message": GENERIC_RESET_MESSAGE
        }), 200

    token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(token)

    frontend_url = os.environ.get(
        "FRONTEND_URL",
        "http://localhost:5173"
    ).rstrip("/")

    # Put the token in the URL fragment rather than
    # the query string, so ordinary page requests
    # and referrer headers do not transmit it.
    reset_link = (
        f"{frontend_url}/reset-password"
        f"#{urlencode({'token': token})}"
    )

    try:
        # A new request invalidates earlier reset links.
        PasswordResetToken.query.filter_by(
            user_id=user.id
        ).delete(synchronize_session=False)

        record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=utc_now() + timedelta(
                minutes=RESET_EXPIRY_MINUTES
            )
        )

        db.session.add(record)
        db.session.flush()

        # Send before committing, so a delivery
        # failure can roll back the new reset record.
        send_password_reset_email(
            user.email,
            reset_link
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception(
            "Could not prepare password-reset email "
            "for user ID %s",
            user.id
        )

        # The response remains identical so callers
        # cannot use delivery errors to find accounts.
        return jsonify({
            "message": GENERIC_RESET_MESSAGE
        }), 200

    return jsonify({
        "message": GENERIC_RESET_MESSAGE
    }), 200



@password_recovery_bp.route(
    "/api/validate-reset-token",
    methods=["POST"]
)
@rate_limit("validate_reset_token", "token")
def validate_reset_token():
    """Check a reset link without consuming the token."""

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "valid": False,
            "message": "Invalid reset link."
        }), 400

    token = data.get("token")

    if (
        not isinstance(token, str)
        or not token
        or len(token) > 256
    ):
        return jsonify({
            "valid": False,
            "message": "Invalid reset link."
        }), 400

    record = PasswordResetToken.query.filter_by(
        token_hash=hash_reset_token(token)
    ).first()

    if record is None:
        return jsonify({
            "valid": False,
            "message": (
                "This password-reset link is no longer valid. "
                "It may have already been used."
            )
        }), 400

    if utc_now() >= normalized_datetime(record.expires_at):
        return jsonify({
            "valid": False,
            "message": (
                "This password-reset link has expired. "
                "Please request a new one."
            )
        }), 400

    return jsonify({
        "valid": True
    }), 200

@password_recovery_bp.route(
    "/api/reset-password",
    methods=["POST"]
)
@rate_limit("complete_password_reset", "token")
def reset_password():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Request body must be valid JSON."
        }), 400

    token = data.get("token")
    password = data.get("password")
    confirm_password = data.get("confirm_password")

    if (
        not isinstance(token, str)
        or not token
        or len(token) > 256
    ):
        return jsonify({
            "error": "Invalid or expired reset link."
        }), 400

    if (
        not isinstance(password, str)
        or not isinstance(confirm_password, str)
    ):
        return jsonify({
            "error": "Enter and confirm your new password."
        }), 400

    if password != confirm_password:
        return jsonify({
            "error": "Passwords do not match."
        }), 400

    valid, message = validate_password(password)

    if not valid:
        return jsonify({"error": message}), 400

    try:
        # Row locking prevents two simultaneous requests
        # from successfully consuming the same token.
        record = (
            db.session.query(PasswordResetToken)
            .filter_by(token_hash=hash_reset_token(token))
            .with_for_update()
            .first()
        )

        if record is None:
            return jsonify({
                "error": "Invalid or expired reset link."
            }), 400

        if utc_now() >= normalized_datetime(
            record.expires_at
        ):
            db.session.delete(record)
            db.session.commit()

            return jsonify({
                "error": "This reset link has expired."
            }), 400

        user = db.session.get(User, record.user_id)

        if user is None:
            db.session.rollback()
            return jsonify({
                "error": "Invalid or expired reset link."
            }), 400

        user.set_password(password)

        # Invalidate every outstanding recovery link
        # for this account, including this one.
        PasswordResetToken.query.filter_by(
            user_id=user.id
        ).delete(synchronize_session=False)

        db.session.commit()

    except (SQLAlchemyError, IntegrityError):
        db.session.rollback()
        app.logger.exception(
            "Password reset database operation failed"
        )

        return jsonify({
            "error": (
                "Unable to reset the password right now. "
                "Please try again."
            )
        }), 503

    return jsonify({
        "message": (
            "Password reset successful. "
            "You can now sign in with your new password."
        )
    }), 200
