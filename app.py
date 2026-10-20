
import os

from flask import jsonify, request, session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from config import app, db
import models  # Load all models for SQLAlchemy and migrations

from email_verification import (
    create_email_otp,
    verify_email_otp,
)

User = models.User

from matches import matches_bp
from dashboard import dashboard_bp
from claims import claims_bp

app.register_blueprint(matches_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(claims_bp)

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

    if len(password) < 8:
        return jsonify({
            "error": "Password must be at least 8 characters long."
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

    session.clear()
    session["user_id"] = user.id

    return jsonify({
        "message": "Login successful.",
        "user": user.to_dict(),
    }), 200


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


if __name__ == "__main__":
    app.run(port=5555, debug=True)
