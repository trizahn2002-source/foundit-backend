from flask import Blueprint, request, jsonify, session

from config import db
from models import Claim, Item, User

claims_bp = Blueprint("claims", __name__, url_prefix="/api")


def current_user():
    user_id = session.get("user_id") or request.headers.get("X-User-Id", type=int)
    return db.get_or_404(User, user_id)


@claims_bp.route("/items/<int:item_id>/claims", methods=["POST"])
def create_claim(item_id):
    user = current_user()
    item = db.get_or_404(Item, item_id)
    data = request.get_json() or {}

    try:
        claim = Claim(message=data.get("message"), user_id=user.id, item_id=item.id)
        db.session.add(claim)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

    return jsonify(claim.to_dict()), 201


@claims_bp.route("/items/<int:item_id>/claims", methods=["GET"])
def get_item_claims(item_id):
    claims = Claim.query.filter_by(item_id=item_id).all()
    return jsonify([c.to_dict() for c in claims])


@claims_bp.route("/claims/mine", methods=["GET"])
def get_my_claims():
    user = current_user()
    claims = Claim.query.filter_by(user_id=user.id).all()
    return jsonify([c.to_dict() for c in claims])


@claims_bp.route("/claims/<int:claim_id>", methods=["GET"])
def get_claim(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    return jsonify(claim.to_dict())


@claims_bp.route("/claims/<int:claim_id>", methods=["PATCH"])
def update_claim_status(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    data = request.get_json() or {}

    try:
        claim.status = data.get("status")
        if claim.status == "approved":
            claim.item.status = "claimed"
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

    return jsonify(claim.to_dict())


@claims_bp.route("/claims/<int:claim_id>", methods=["DELETE"])
def delete_claim(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    db.session.delete(claim)
    db.session.commit()
    return jsonify({"message": "Claim withdrawn."})