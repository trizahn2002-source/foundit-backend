"""Google Identity Services ID-token verification for FoundIt."""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, session
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.exc import IntegrityError

from config import app, db
from models import GoogleIdentity, User
from rate_limiting import rate_limit

google_auth_bp = Blueprint("google_auth", __name__)


def error(message, status):
    return jsonify({"error": message}), status


def auth_stamp(user):
    return hmac.new(app.config["SECRET_KEY"].encode("utf-8"),
                    user.password_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def available_google_username(email):
    # Generate a unique opaque username; never claim another user's username.
    for _ in range(8):
        candidate = "google_" + secrets.token_hex(12)
        if User.query.filter_by(username=candidate).first() is None:
            return candidate
    raise RuntimeError("Unable to allocate a username")


@google_auth_bp.post("/api/auth/google")
@rate_limit("google_login", "credential")
def google_sign_in():
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        return error("Google Sign-In is not configured.", 503)

    data = request.get_json(silent=True)
    credential = data.get("credential") if isinstance(data, dict) else None
    if not isinstance(credential, str) or not 100 <= len(credential) <= 8192:
        return error("A valid Google credential is required.", 400)

    try:
        claims = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
    except (ValueError, Exception) as exc:
        # Don't expose token details, Google identity or internals.
        app.logger.info("Google token verification failed: %s", type(exc).__name__)
        return error("Google sign-in could not be verified. Please try again.", 401)

    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        return error("Invalid Google token issuer.", 401)
    sub = claims.get("sub")
    email = claims.get("email")
    if not isinstance(sub, str) or not sub or len(sub) > 255:
        return error("Google account information is incomplete.", 401)
    if not isinstance(email, str) or not email or len(email) > 120 or claims.get("email_verified") is not True:
        return error("Google account must have a verified email.", 403)
    email = email.strip().lower()

    google_first_name = claims.get("given_name")
    if not isinstance(google_first_name, str):
        google_first_name = ""
    google_first_name = google_first_name.strip()[:80]

    identity = GoogleIdentity.query.filter_by(google_sub=sub).first()
    if identity is not None:
        user = identity.user
        if user is None or user.email_verified_at is None:
            return error("This account cannot sign in. Please contact support.", 403)
        # Backfill the first name for Google users created before this update.
        # Do not overwrite a name they might customize in Account Settings.
        if google_first_name and not user.display_name:
            user.display_name = google_first_name
            db.session.commit()
    else:
        # NEVER auto-link by matching email: establish account ownership
        # via a separate explicitly verified linking flow later.
        if User.query.filter_by(email=email).first():
            return error("An account already uses this email. Please sign in with your password; Google linking is not available yet.", 409)
        user = User(
            username=available_google_username(email),
            email=email,
            display_name=google_first_name or None,
        )
        user.set_password(secrets.token_urlsafe(48))  # Unusable unknown password.
        user.email_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.add(user)
            db.session.flush()
            db.session.add(GoogleIdentity(user_id=user.id, google_sub=sub))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return error("Account creation conflicted with an existing account. Please retry or use password sign-in.", 409)

    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["auth_stamp"] = auth_stamp(user)
    return jsonify({"message": "Google sign-in successful.", "user": user.to_dict()}), 200
