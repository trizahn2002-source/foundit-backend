"""Second step authentication for password-based logins; """
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import SQLAlchemyError
from config import app, db
from models import LoginOTP
from email_sender import send_login_otp_email

OTP_MINUTES = 5
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60

def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def digest(user_id, code):
    key = app.config["SECRET_KEY"].encode("utf-8")
    msg = f"login-otp:{user_id}:{code}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def normalize(dt):
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt

def deliver_login_code(user, *, resend=False):
    """Generate/store/send OTP; do not disclose its value or open a login session."""
    if os.getenv("OTP_TEST_MODE", "true").lower() == "true":
        allowed = os.getenv("OTP_TEST_EMAIL", "").strip().lower()
        if user.email.lower() != allowed:
            return False, "Email delivery is restricted to the authorized test inbox."
    previous = LoginOTP.query.filter_by(user_id=user.id).first()
    if resend and previous and previous.created_at:
        if (now_utc() - normalize(previous.created_at)).total_seconds() < RESEND_COOLDOWN_SECONDS:
            return False, "Please wait before requesting another code."
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        # Preserve old code if email delivery fails.
        send_login_otp_email(user.email, code)
        LoginOTP.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        db.session.add(LoginOTP(
            user_id=user.id, code_hash=digest(user.id, code),
            expires_at=now_utc() + timedelta(minutes=OTP_MINUTES), attempts=0,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Login OTP delivery failed for user %s", user.id)
        return False, "Could not send your login code. Please try again shortly."
    return True, "A six-digit sign-in code has been sent to your email."

def validate_login_code(user, code):
    if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
        return False, "Enter a valid six-digit code."
    record = LoginOTP.query.filter_by(user_id=user.id).first()
    if record is None:
        return False, "No active sign-in code. Please sign in again."
    if now_utc() >= normalize(record.expires_at):
        db.session.delete(record)
        db.session.commit()
        return False, "Your sign-in code has expired. Please sign in again."
    if record.attempts >= MAX_ATTEMPTS:
        db.session.delete(record)
        db.session.commit()
        return False, "Too many incorrect attempts. Please sign in again."
    if not hmac.compare_digest(record.code_hash, digest(user.id, code)):
        record.attempts += 1
        if record.attempts >= MAX_ATTEMPTS:
            db.session.delete(record)
        db.session.commit()
        return False, "Incorrect sign-in code."
    db.session.delete(record)
    db.session.commit()
    return True, "Code verified."
