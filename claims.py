import re
from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from config import db
from models import Claim, Item, public_name
from sqlalchemy.orm import joinedload
from pagination import get_page_args, pagination_meta

claims_bp = Blueprint("claims", __name__)


def current_user_id():
    return session.get("user_id")

def validate_contact(method, detail):
    if method not in ("whatsapp", "phone", "email"):
        return "Choose WhatsApp, phone or email."

    if not isinstance(detail, str):
        return "Enter valid contact details."

    detail = detail.strip()

    if not detail or len(detail) > 255:
        return "Contact details are required (maximum 255 characters)."

    if method == "email":
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", detail):
            return "Enter a valid email address."
    else:
        digits = re.sub(r"\D", "", detail)

        if not re.fullmatch(r"\+?[0-9()\-\s]+", detail):
            return "Enter a valid phone number."

        if not 7 <= len(digits) <= 15:
            return "Phone numbers must contain 7 to 15 digits."

    return None



def claim_to_json(claim):
    data = claim.to_dict()
    data["claimant"] = public_name(claim.user) or "Unknown user"

    viewer_id = current_user_id()

    if (
        claim.status == "approved"
        and viewer_id is not None
        and (
            viewer_id == claim.user_id
            or viewer_id == claim.item.user_id
        )
    ):
        data["contact_method"] = claim.contact_method
        data["contact_detail"] = claim.contact_detail

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

    page, per_page = get_page_args(default_per_page=20)
    page_result = (
        query
        .options(joinedload(Claim.user), joinedload(Claim.item))
        .order_by(Claim.created_at.desc(), Claim.id.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify({
        "item_id": item_id,
        "is_owner": item.user_id == user_id,
        "count": page_result.total,
        "claims": [claim_to_json(c) for c in page_result.items],
        "pagination": pagination_meta(page_result),
    }), 200
@claims_bp.get("/api/claims/action-required")
def action_required_claims():
    from sqlalchemy import and_, or_

    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    page, per_page = get_page_args(default_per_page=20)
    page_result = (
        Claim.query
        .join(Item, Claim.item_id == Item.id)
        .options(joinedload(Claim.user), joinedload(Claim.item))
        .filter(
            Item.user_id == user_id,
            or_(
                Claim.status == "pending",
                and_(Claim.status == "approved", Item.status == "claimed"),
            ),
        )
        .order_by(Claim.created_at.desc(), Claim.id.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    relevant_claims = page_result.items

    # Deliberately omit private contact fields from this dashboard endpoint.
    # Contact details remain accessible through the permission-controlled
    # item claims endpoint only for an approved claim.
    claims = []
    for claim in relevant_claims:
        data = claim.to_dict()
        data["claimant"] = public_name(claim.user) or "Unknown user"
        claims.append(data)

    return jsonify({
        "claims": claims,
        "pagination": pagination_meta(page_result),
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
        return jsonify({
            "error": "Only the item owner can approve or reject claims"
        }), 403

    data = request.get_json(silent=True)
    status = data.get("status") if isinstance(data, dict) else None

    if status not in ("approved", "rejected"):
        return jsonify({
            "error": "status must be 'approved' or 'rejected'"
        }), 400

    if claim.status != "pending":
        return jsonify({
            "error": f"Claim is already {claim.status}"
        }), 400

    if status == "approved":
        # Validate contact details before making any changes.
        contact_method = data.get("contact_method")
        contact_detail = data.get("contact_detail")

        validation_error = validate_contact(
            contact_method,
            contact_detail
        )

        if validation_error:
            return jsonify({"error": validation_error}), 400

        # Lock the item row so competing approvals
        # for the same item are processed one at a time.
        item = (
            db.session.query(Item)
            .filter(Item.id == claim.item_id)
            .with_for_update()
            .populate_existing()
            .one()
        )

        # Reload claim state after obtaining the lock.
        # Another request may already have processed it.
        db.session.refresh(claim)

        if claim.status != "pending":
            db.session.rollback()
            return jsonify({
                "error": f"Claim is already {claim.status}"
            }), 409

        # An item must still be active to approve a claim.
        if item.status != "active":
            db.session.rollback()
            return jsonify({
                "error": "This item is no longer available for approval."
            }), 409

        # Never approve a second claimant for the same item.
        existing_approval = Claim.query.filter(
            Claim.item_id == item.id,
            Claim.status == "approved",
            Claim.id != claim.id
        ).first()

        if existing_approval:
            db.session.rollback()
            return jsonify({
                "error": "Another claim has already been approved for this item."
            }), 409

        # Save private contact information.
        claim.contact_method = contact_method
        claim.contact_detail = contact_detail.strip()

        claim.status = "approved"
        item.status = "claimed"

        # Reject other pending claims automatically.
        for other in item.claims:
            if other.id != claim.id and other.status == "pending":
                other.status = "rejected"

    else:
        # Rejection does not require contact information.
        claim.status = "rejected"

    db.session.commit()

    return jsonify({
        "claim": claim_to_json(claim),
        "item": claim.item.to_dict(),
    }), 200
