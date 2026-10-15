from flask import Blueprint, jsonify
from models import Item, Claim, User
from config import db

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/api/users/<int:user_id>/items")
def get_my_items(user_id):
    user = db.session.get(User, user_id)

    if user is None:
        return jsonify({"error": "User not found"}), 404
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
    user = db.session.get(User, user_id)

    if user is None:
        return jsonify({"error": "User not found"}), 404
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