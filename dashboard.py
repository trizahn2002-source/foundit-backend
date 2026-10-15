from flask import Blueprint, jsonify, session
from models import Item, Claim, User
from config import db

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/api/users/<int:user_id>/items")
def get_my_items(user_id):
    logged_in_user_id = session.get("user_id")

    if logged_in_user_id is None:
        return jsonify({"error": "Login required"}), 401
    
    if logged_in_user_id != user_id:
        return jsonify({"error": "You are not allowed to view another user's items"}), 403


    items = (
        Item.query
        .filter_by(user_id=user_id)
        .order_by(Item.created_at.desc())
        .all()
    )

    return jsonify({
        "user_id": user_id,
        "count": len(items),
        "items": [item.to_dict() for item in items],
    }), 200


@dashboard_bp.get("/api/users/<int:user_id>/claims")
def get_my_claims(user_id):
    logged_in_user_id = session.get("user_id")

    if logged_in_user_id is None:
        return jsonify({"error": "Login required"}), 401

    if logged_in_user_id != user_id:
        return jsonify({"error": "You are not allowed to view another user's claims"}), 403

    claims = (
        Claim.query
        .filter_by(user_id=user_id)
        .order_by(Claim.created_at.desc())
        .all()
    )

    return jsonify({
        "user_id": user_id,
        "count": len(claims),
        "claims": [claim.to_dict() for claim in claims],
    }), 200