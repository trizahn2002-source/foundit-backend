
import hashlib
import hmac
import secrets

from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import SQLAlchemyError

from config import app, db
from models import EmailVerification
from email_sender import send_verification_email


OTP_EXPIRY_MINUTES = 5
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


def utc_now():
    """UTC without timezone information, matching our current DB columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_otp(user_id, code):
    """Create a server-keyed digest of the verification code."""

    secret = app.config["SECRET_KEY"].encode("utf-8")
    message = f"email-verification:{user_id}:{code}".encode("utf-8")

    return hmac.new(
        secret,
        message,
        hashlib.sha256
    ).hexdigest()


def create_email_otp(user):
    """
    Generate and email a verification code.

    Returns (success, message).
    Never returns the OTP to the API caller.
    """

    if user.email_verified_at is not None:
        return False, "This email is already verified."

    now = utc_now()

    existing = (
        EmailVerification.query
        .filter_by(user_id=user.id)
        .order_by(EmailVerification.created_at.desc())
        .first()
    )

    if existing:
        created_at = existing.created_at

        if created_at.tzinfo is not None:
            created_at = created_at.astimezone(
                timezone.utc
            ).replace(tzinfo=None)

        elapsed = (now - created_at).total_seconds()

        if elapsed < RESEND_COOLDOWN_SECONDS:
            return (
                False,
                "Please wait before requesting another code."
            )

    code = f"{secrets.randbelow(1_000_000):06d}"

    try:
        # Invalidate previous verification codes.
        EmailVerification.query.filter_by(
            user_id=user.id
        ).delete(synchronize_session=False)

        verification = EmailVerification(
            user_id=user.id,
            code_hash=hash_otp(user.id, code),
            expires_at=now + timedelta(
                minutes=OTP_EXPIRY_MINUTES
            ),
            attempts=0,
        )

        db.session.add(verification)
        db.session.flush()

        # Send before committing the new OTP record.
        # If delivery raises an exception, rollback keeps
        # the previous database state intact.
        send_verification_email(user.email, code)

        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception(
            "Email verification delivery failed for user ID %s",
            user.id
        )

        return (
            False,
            "We couldn't send your verification email. "
            "Please try again shortly."
        )

    return (
        True,
        "We've sent a verification code to your email."
    )


def verify_email_otp(user, submitted_code):
    """
    Verify a code and mark the user's email as verified.

    Returns (success, message).
    """

    if user.email_verified_at is not None:
        return True, "Email is already verified."

    if (
        not isinstance(submitted_code, str)
        or len(submitted_code) != 6
        or not submitted_code.isascii()
        or not submitted_code.isdigit()
    ):
        return False, "Enter a valid six-digit code."

    verification = (
        EmailVerification.query
        .filter_by(user_id=user.id)
        .order_by(EmailVerification.created_at.desc())
        .first()
    )

    if verification is None:
        return (
            False,
            "No verification code found. Request a new one."
        )

    now = utc_now()

    expires_at = verification.expires_at

    if expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    if now >= expires_at:
        db.session.delete(verification)
        db.session.commit()

        return (
            False,
            "This code has expired. Request a new one."
        )

    if verification.attempts >= MAX_ATTEMPTS:
        db.session.delete(verification)
        db.session.commit()

        return (
            False,
            "Too many attempts. Request a new code."
        )

    submitted_hash = hash_otp(
        user.id,
        submitted_code
    )

    if not hmac.compare_digest(
        verification.code_hash,
        submitted_hash
    ):
        verification.attempts += 1

        if verification.attempts >= MAX_ATTEMPTS:
            db.session.delete(verification)

        db.session.commit()

        return False, "Incorrect verification code."

    # Success: verify email and consume the OTP.
    user.email_verified_at = now

    EmailVerification.query.filter_by(
        user_id=user.id
    ).delete(synchronize_session=False)

    db.session.commit()

    return True, "Email verified successfully."
