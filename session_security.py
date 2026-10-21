
import hmac
import secrets

from flask import jsonify, request, session
from config import app


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.get("/api/csrf-token")
def get_csrf_token():
    """Issue a CSRF token associated with this browser session."""

    token = session.get("csrf_token")

    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token

    response = jsonify({"csrf_token": token})
    response.headers["Cache-Control"] = "no-store"
    return response, 200


@app.before_request
def protect_state_changing_requests():
    """Require a valid CSRF token for state-changing requests."""

    if request.method in SAFE_METHODS:
        return

    expected = session.get("csrf_token", "")
    provided = request.headers.get("X-CSRF-Token", "")

    if (
        not expected
        or not provided
        or not hmac.compare_digest(expected, provided)
    ):
        return jsonify({
            "error": (
                "Your security token is missing or invalid. "
                "Please refresh and try again."
            )
        }), 403
