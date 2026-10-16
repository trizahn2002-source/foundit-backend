from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from config import db
from models import Claim, Item

claims_bp = Blueprint("claims", __name__)


def current_user_id():
    return session.get("user_id")


def claim_to_json(claim):
    data = claim.to_dict()
    data["claimant"] = claim.user.username if claim.user else None
    return data


@claims_bp.post("/api/items/<int:item_id>/claims")
def create_claim(item_id):
    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item.user_id == user_id:
        return jsonify({"error": "You cannot claim your own item"}), 403
    if item.status != "active":
        return jsonify({"error": "This item is no longer open for claims"}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "A claim must include a message."}), 400

    if Claim.query.filter_by(user_id=user_id, item_id=item_id).first():
        return jsonify({"error": "You have already claimed this item"}), 409

    try:
        claim = Claim(message=message, user_id=user_id, item_id=item_id)
        db.session.add(claim)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "You have already claimed this item"}), 409

    return jsonify(claim_to_json(claim)), 201


@claims_bp.get("/api/items/<int:item_id>/claims")
def list_item_claims(item_id):
    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    query = Claim.query.filter_by(item_id=item_id)
    if item.user_id != user_id:
        query = query.filter_by(user_id=user_id)

    claims = query.order_by(Claim.created_at.desc()).all()
    return jsonify({
        "item_id": item_id,
        "is_owner": item.user_id == user_id,
        "count": len(claims),
        "claims": [claim_to_json(c) for c in claims],
    }), 200


@claims_bp.patch("/api/claims/<int:claim_id>")
def decide_claim(claim_id):
    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    claim = db.session.get(Claim, claim_id)
    if not claim:
        return jsonify({"error": "Claim not found"}), 404
    if claim.item.user_id != user_id:
        return jsonify({"error": "Only the item owner can approve or reject claims"}), 403

    data = request.get_json(silent=True)
    status = data.get("status") if isinstance(data, dict) else None
    if status not in ("approved", "rejected"):
        return jsonify({"error": "status must be 'approved' or 'rejected'"}), 400
    if claim.status != "pending":
        return jsonify({"error": f"Claim is already {claim.status}"}), 400

    claim.status = status

    if status == "approved":
        claim.item.status = "claimed"
        for other in claim.item.claims:
            if other.id != claim.id and other.status == "pending":
                other.status = "rejected"

    db.session.commit()
    return jsonify({
        "claim": claim_to_json(claim),
        "item": claim.item.to_dict(),
    }), 200