from flask import Blueprint, jsonify, request, session

from config import db
from models import Claim, Item, Tip
from mpesa import check_stk_status, send_stk_push

tips_bp = Blueprint("tips", __name__, url_prefix="/api")


@tips_bp.post("/items/<int:item_id>/tips")
def create_tip(item_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Please log in to send a tip."}), 401

    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found."}), 404
    if item.user_id == user_id:
        return jsonify({"error": "You can't tip yourself."}), 400

    # Only the owner whose claim was approved can tip the finder
    claim = Claim.query.filter_by(item_id=item_id, user_id=user_id, status="approved").first()
    if not claim:
        return jsonify({"error": "You can tip once your claim is approved."}), 403

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request body."}), 400
    phone = data.get("phone")
    try:
        amount = int(data.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0
    if amount < 1 or amount > 100000:
        return jsonify({"error": "Enter an amount of at least KSh 1."}), 400
    if not isinstance(phone, str) or not phone.strip():
        return jsonify({"error": "Enter your M-Pesa phone number."}), 400

    try:
        mpesa = send_stk_push(phone, amount, reference=f"FoundIt{item_id}")
    except Exception:
        return jsonify({"error": "Could not reach M-Pesa. Try again."}), 502

    if mpesa.get("ResponseCode") != "0":
        message = mpesa.get("errorMessage") or mpesa.get("ResponseDescription") or "M-Pesa request failed."
        return jsonify({"error": message}), 400

    tip = Tip(
        amount=amount,
        phone=phone,
        item_id=item_id,
        tipper_id=user_id,
        finder_id=item.user_id,
        checkout_request_id=mpesa.get("CheckoutRequestID"),
    )
    db.session.add(tip)
    db.session.commit()
    return jsonify({"message": "Check your phone and enter your M-Pesa PIN.", "tip": tip.to_dict()}), 201


@tips_bp.get("/tips/<int:tip_id>/status")
def tip_status(tip_id):
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"error": "Please log in."}), 401
    tip = db.session.get(Tip, tip_id)
    if not tip or user_id not in (tip.tipper_id, tip.finder_id):
        return jsonify({"error": "Tip not found."}), 404

    if tip.status == "pending" and tip.checkout_request_id:
        try:
            result = check_stk_status(tip.checkout_request_id)
            code = str(result.get("ResultCode", ""))
            if code == "0":
                tip.status = "paid"
                db.session.commit()
            elif code and code != "4999":  # 4999 = still processing, keep waiting
                tip.status = "failed"
                db.session.commit()
        except Exception:
            pass  # still processing, try again later

    return jsonify(tip.to_dict()), 200