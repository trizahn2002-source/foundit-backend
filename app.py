import hashlib
import hmac
import os
import session_security
from rate_limiting import rate_limit
from flask import jsonify, request, session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from password_security import validate_password
from password_recovery import password_recovery_bp
from google_auth import google_auth_bp
from account_settings import account_settings_bp
from login_otp import deliver_login_code, validate_login_code

from config import app, db
import models  # Load all models for SQLAlchemy and migrations

from email_verification import (
    create_email_otp,
    verify_email_otp,
)

User = models.User

# Invalidate old sessions when an account password changes.

def authentication_stamp(user):
    secret = app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(
        secret,
        user.password_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@app.before_request
def validate_existing_session():
    user_id = session.get("user_id")

    if user_id is None:
        return

    user = db.session.get(User, user_id)

    if (
        user is None
        or not hmac.compare_digest(
            str(session.get("auth_stamp", "")),
            authentication_stamp(user),
        )
    ):
        session.clear()


from matches import matches_bp
from dashboard import dashboard_bp
from claims import claims_bp
from tips import tips_bp

app.register_blueprint(matches_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tips_bp)
app.register_blueprint(claims_bp)
app.register_blueprint(password_recovery_bp)
app.register_blueprint(google_auth_bp)
app.register_blueprint(account_settings_bp)

import item_routes


@app.route("/api")
def index():
    return jsonify({"message": "FoundIt API is running"}), 200


# ---------- Authentication (Wesley) ----------

def otp_testing_enabled():
    return os.getenv("OTP_TEST_MODE", "true").lower() == "true"


def email_allowed_for_testing(email):
    if not otp_testing_enabled():
        return True

    allowed_email = os.getenv(
        "OTP_TEST_EMAIL", ""
    ).strip().lower()

    return bool(allowed_email) and email == allowed_email


def get_json_data():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


@app.route("/api/register", methods=["POST"])
@rate_limit("register", "email")
def register():
    data = get_json_data()

    if data is None:
        return jsonify({
            "error": "Request body must be valid JSON."
        }), 400

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not all(
        isinstance(value, str)
        for value in (username, email, password)
    ):
        return jsonify({
            "error": "Username, email and password are required."
        }), 400

    username = username.strip()
    email = email.strip().lower()

    if not username or not email or not password:
        return jsonify({
            "error": "Username, email and password cannot be empty."
        }), 400

    if len(username) > 80 or len(email) > 120:
        return jsonify({
            "error": "Username or email is too long."
        }), 400

    if "@" not in email or email.startswith("@"):
        return jsonify({
            "error": "Enter a valid email address."
        }), 400

    password_valid, password_message = validate_password(
        password,
        username,
        email
    )
    
    if not password_valid:
        return jsonify({
            "error": password_message
        }), 400

    if not email_allowed_for_testing(email):
        return jsonify({
            "error": (
                "Registration is currently restricted "
                "to the authorized test email."
            )
        }), 403

    existing_user = User.query.filter(
        or_(
            User.username == username,
            User.email == email
        )
    ).first()

    if existing_user:
        return jsonify({
            "error": "Username or email is already registered."
        }), 409

    user = User(username=username, email=email)
    user.set_password(password)

    try:
        db.session.add(user)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Username or email is already registered."
        }), 409

    success, message = create_email_otp(user)

    if not success:
        # Preserve the newly created account so the user can
        # request another OTP instead of losing registration.
        return jsonify({
            "error": message,
            "verification_required": True,
            "email": user.email,
        }), 503

    return jsonify({
        "message": message,
        "verification_required": True,
        "email": user.email,
    }), 201


@app.route("/api/verify-email", methods=["POST"])
@rate_limit("verify_email", "email")
def verify_email():
    data = get_json_data()

    if data is None:
        return jsonify({
            "error": "Request body must be valid JSON."
        }), 400

    email = data.get("email")
    code = data.get("code")

    if not isinstance(email, str):
        return jsonify({
            "error": "A valid email address is required."
        }), 400

    email = email.strip().lower()

    user = User.query.filter_by(email=email).first()

    if user is None:
        return jsonify({
            "error": "Invalid or expired verification code."
        }), 400

    success, message = verify_email_otp(user, code)

    if not success:
        return jsonify({"error": message}), 400

    return jsonify({
        "message": message,
        "email_verified": True,
    }), 200


@app.route(
    "/api/resend-verification",
    methods=["POST"]
)
@rate_limit("resend_verification", "email")
def resend_verification():
    data = get_json_data()

    if data is None:
        return jsonify({
            "error": "Request body must be valid JSON."
        }), 400

    email = data.get("email")
    password = data.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({
            "error": "Email and password are required."
        }), 400

    email = email.strip().lower()

    if not email_allowed_for_testing(email):
        return jsonify({
            "error": "Email delivery is restricted during testing."
        }), 403

    user = User.query.filter_by(email=email).first()

    if user is None or not user.check_password(password):
        return jsonify({
            "error": "Unable to process verification request."
        }), 400

    if user.email_verified_at is not None:
        return jsonify({
            "message": "Email is already verified."
        }), 200

    success, message = create_email_otp(user)

    if not success:
        return jsonify({"error": message}), 429 if (
            "Please wait" in message
        ) else 503

    return jsonify({"message": message}), 200


@app.route("/api/login", methods=["POST"])
@rate_limit("login", "identifier")
def login():
    data = get_json_data()

    if data is None:
        return jsonify({
            "error": "Request body must be valid JSON."
        }), 400

    identifier = data.get("identifier")

    if identifier is None:
        identifier = data.get("email") or data.get("username")

    password = data.get("password")

    if not isinstance(identifier, str) or not isinstance(password, str):
        return jsonify({
            "error": "Username or email and password are required."
        }), 400

    identifier = identifier.strip()

    user = User.query.filter(
        or_(
            User.username == identifier,
            User.email == identifier.lower()
        )
    ).first()

    if user is None or not user.check_password(password):
        return jsonify({
            "error": "Invalid username/email or password."
        }), 401

    if user.email_verified_at is None:
        return jsonify({
            "error": "Please verify your email before signing in.",
            "verification_required": True,
            "email": user.email,
        }), 403

    # Password alone never grants an authenticated session.
    # Clear any previous login and create only a short-lived pending challenge.
    session.clear()
    success, message = deliver_login_code(user)
    if not success:
        return jsonify({"error": message}), 503
    session["pending_2fa_user_id"] = user.id
    session["pending_2fa_until"] = int(__import__("time").time()) + 300
    return jsonify({"two_factor_required": True, "message": message}), 200


@app.post("/api/login/verify-otp")
@rate_limit("login_verify_otp", "code")
def complete_login_otp():
    import time
    from models import LoginOTP
    pending_id = session.get("pending_2fa_user_id")
    deadline = session.get("pending_2fa_until", 0)
    if not pending_id or time.time() >= deadline:
        session.clear()
        return jsonify({"error": "Your sign-in challenge has expired. Please log in again."}), 401
    user = db.session.get(User, pending_id)
    if user is None or user.email_verified_at is None:
        session.clear()
        return jsonify({"error": "Please sign in again."}), 401
    payload = get_json_data() or {}
    success, message = validate_login_code(user, payload.get("code"))
    if not success:
        return jsonify({"error": message}), 400
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["auth_stamp"] = authentication_stamp(user)
    return jsonify({"message": "Login successful.", "user": user.to_dict()}), 200


@app.post("/api/login/resend-otp")
@rate_limit("login_resend_otp", "email")
def resend_login_otp():
    import time
    pending_id = session.get("pending_2fa_user_id")
    if not pending_id or time.time() >= session.get("pending_2fa_until", 0):
        session.clear()
        return jsonify({"error": "Sign-in expired. Please log in again."}), 401
    user = db.session.get(User, pending_id)
    if user is None or user.email_verified_at is None:
        session.clear()
        return jsonify({"error": "Please log in again."}), 401
    success, message = deliver_login_code(user, resend=True)
    if not success:
        return jsonify({"error": message}), 429 if "wait" in message.lower() else 503
    session["pending_2fa_until"] = int(time.time()) + 300
    return jsonify({"message": message}), 200


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()

    return jsonify({
        "message": "Logout successful."
    }), 200


@app.route("/api/check_session", methods=["GET"])
def check_session():
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify({
            "logged_in": False,
            "user": None,
        }), 200

    user = db.session.get(User, user_id)

    if user is None or user.email_verified_at is None:
        session.clear()
        return jsonify({
            "logged_in": False,
            "user": None,
        }), 200

    return jsonify({
        "logged_in": True,
        "user": user.to_dict(),
    }), 200



# ---------- User update and delete (Wesley; shared security rules) ----------
from account_settings import (
    current_user, fail, update_username_for_user,
    change_password_for_user, delete_account_for_user,
)


@app.route("/api/users/<int:user_id>", methods=["PUT", "PATCH"])
@rate_limit("edit_profile")
def update_user(user_id):
    user = current_user()
    if user is None:
        return fail("Please log in first.", 401)
    if user.id != user_id:
        return fail("You can only update your own account.", 403)
    data = get_json_data()
    if not data:
        return fail("Provide a username, password or verified email-change request.", 400)
    if "email" in data:
        return fail("Use the verified email-change flow: /api/account/email-change/request.", 400)
    if "password" in data:
        if set(data) - {"password", "current_password"}:
            return fail("Update password separately from other fields.", 400)
        return change_password_for_user(user, {
            "current_password": data.get("current_password"),
            "new_password": data.get("password"),
        })
    if set(data) != {"username"}:
        return fail("Only username updates are supported here.", 400)
    return update_username_for_user(user, data["username"])


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@rate_limit("delete_account")
def delete_user(user_id):
    user = current_user()
    if user is None:
        return fail("Please log in first.", 401)
    if user.id != user_id:
        return fail("You can only delete your own account.", 403)
    return delete_account_for_user(user, get_json_data() or {})


if __name__ == "__main__":
    app.run(port=5555, debug=True)
