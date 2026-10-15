
from flask import jsonify, request, session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from config import app, db
import models  # Load all models for SQLAlchemy and migrations

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

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not all(isinstance(value, str) for value in (username, email, password)):
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

    if len(password) < 8:
        return jsonify({
            "error": "Password must be at least 8 characters long."
        }), 400

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

    return jsonify({
        "message": "Registration successful.",
        "user": user.to_dict()
    }), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

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

    session.clear()
    session["user_id"] = user.id

    return jsonify({
        "message": "Login successful.",
        "user": user.to_dict()
    }), 200


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()

    return jsonify({"message": "Logout successful."}), 200


@app.route("/api/check_session", methods=["GET"])
def check_session():
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify({
            "logged_in": False,
            "user": None
        }), 200

    user = db.session.get(User, user_id)

    if user is None:
        session.clear()
        return jsonify({
            "logged_in": False,
            "user": None
        }), 200

    return jsonify({
        "logged_in": True,
        "user": user.to_dict()
    }), 200



# ---------- User update and delete (Wesley) ----------

@app.route("/api/users/<int:user_id>", methods=["PUT", "PATCH"])
def update_user(user_id):
    current_user_id = session.get("user_id")

    if current_user_id is None:
        return jsonify({"error": "Please log in first."}), 401

    if current_user_id != user_id:
        return jsonify({
            "error": "You can only update your own account."
        }), 403

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

    allowed_fields = {"username", "email", "password"}
    if not data or not set(data).issubset(allowed_fields):
        return jsonify({
            "error": "Provide username, email, or password to update."
        }), 400

    if "username" in data:
        if not isinstance(data["username"], str):
            return jsonify({"error": "Username must be text."}), 400
        username = data["username"].strip()
        if not username or len(username) > 80:
            return jsonify({
                "error": "Username must contain 1 to 80 characters."
            }), 400
        user.username = username

    if "email" in data:
        if not isinstance(data["email"], str):
            return jsonify({"error": "Email must be text."}), 400
        email = data["email"].strip().lower()
        if not email or len(email) > 120:
            return jsonify({
                "error": "Email must contain 1 to 120 characters."
            }), 400
        user.email = email

    if "password" in data:
        password = data["password"]
        if not isinstance(password, str) or len(password) < 8:
            return jsonify({
                "error": "Password must be at least 8 characters long."
            }), 400
        user.set_password(password)

    duplicate = User.query.filter(
        User.id != user.id,
        or_(
            User.username == user.username,
            User.email == user.email
        )
    ).first()

    if duplicate:
        db.session.rollback()
        return jsonify({
            "error": "Username or email is already in use."
        }), 409

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Username or email is already in use."
        }), 409

    return jsonify({
        "message": "User updated successfully.",
        "user": user.to_dict()
    }), 200


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    current_user_id = session.get("user_id")

    if current_user_id is None:
        return jsonify({"error": "Please log in first."}), 401

    if current_user_id != user_id:
        return jsonify({
            "error": "You can only delete your own account."
        }), 403

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found."}), 404

    try:
        db.session.delete(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": (
                "This account has related records and cannot be deleted "
                "until those relationships are handled safely."
            )
        }), 409

    session.clear()
    return jsonify({"message": "User deleted successfully."}), 200


if __name__ == "__main__":
    app.run(port=5555, debug=True)

