"""Authenticated FoundIt profile and account-management routes."""
import hashlib
import hmac
from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import SQLAlchemyError
from config import app, db
from models import User, Item, Claim, GoogleIdentity, LoginOTP, EmailVerification, PasswordResetToken
from password_security import validate_password
from rate_limiting import rate_limit

account_settings_bp = Blueprint('account_settings', __name__)


def current_user():
    user_id = session.get('user_id')
    return db.session.get(User, user_id) if user_id is not None else None


def fail(message, status):
    return jsonify({'error': message}), status


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


@account_settings_bp.get('/api/account')
def account_details():
    user = current_user()
    if not user:
        return fail('Please sign in.', 401)
    return jsonify({'user': user.to_dict(), 'google_only': GoogleIdentity.query.filter_by(user_id=user.id).first() is not None}), 200


@account_settings_bp.patch('/api/account/display-name')
@rate_limit('edit_profile')
def edit_display_name():
    user = current_user()
    if user is None:
        return fail('Please sign in.', 401)
    data = json_body()
    name = data.get('display_name') if data else None
    if not isinstance(name, str) or not (1 <= len(name.strip()) <= 80) or any(ord(ch) < 32 for ch in name):
        return fail('Enter a display name between 1 and 80 characters.', 400)
    user.display_name = name.strip()
    db.session.commit()
    return jsonify({'message': 'Display name updated.', 'user': user.to_dict()}), 200


@account_settings_bp.post('/api/account/change-password')
@rate_limit('change_password')
def change_password():
    user = current_user()
    if not user:
        return fail('Please sign in.', 401)
    if GoogleIdentity.query.filter_by(user_id=user.id).first() is not None:
        return fail('Password changes are not available for Google-only accounts.', 403)
    data = json_body() or {}
    old, new = data.get('current_password'), data.get('new_password')
    if not isinstance(old, str) or not isinstance(new, str) or not user.check_password(old):
        return fail('Current password is incorrect.', 403)
    valid, explanation = validate_password(new, user.username, user.email)
    if not valid:
        return fail(explanation, 400)
    if user.check_password(new):
        return fail('Choose a new password that is different from your current one.', 400)
    user.set_password(new)
    db.session.commit()
    session.clear()  # Existing cookies invalidated via auth_stamp on subsequent requests.
    return jsonify({'message': 'Password updated. Please sign in again.'}), 200


@account_settings_bp.post('/api/account/delete')
@rate_limit('delete_account')
def delete_account():
    user = current_user()
    if not user:
        return fail('Please sign in.', 401)
    data = json_body() or {}
    if data.get('confirmation') != 'DELETE':
        return fail('Type DELETE to confirm account deletion.', 400)

    google_identity = GoogleIdentity.query.filter_by(user_id=user.id).first()
    if google_identity:
        credential = data.get('google_credential')
        if not isinstance(credential, str):
            return fail('Confirm your Google account to delete it.', 403)
        import os
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
        try:
            claims = id_token.verify_oauth2_token(credential, google_requests.Request(), os.getenv('GOOGLE_CLIENT_ID', ''))
        except Exception:
            return fail('Google account verification failed.', 403)
        if not hmac.compare_digest(str(claims.get('sub', '')), str(google_identity.google_sub)):
            return fail('This Google account does not match your FoundIt account.', 403)
    else:
        password = data.get('password')
        if not isinstance(password, str) or not user.check_password(password):
            return fail('Current password is incorrect.', 403)

    try:
        # Remove claims on the user's items, then their own claims, then the items.
        # Keep unrelated users' reports and claims intact.
        item_ids = [item_id for (item_id,) in db.session.query(Item.id).filter_by(user_id=user.id).all()]
        if item_ids:
            Claim.query.filter(Claim.item_id.in_(item_ids)).delete(synchronize_session=False)
        Claim.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        Item.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        # Explicit dependent cleanup avoids foreign-key restrictions even if cascades differ.
        GoogleIdentity.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        LoginOTP.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        EmailVerification.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        PasswordResetToken.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        db.session.delete(user)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception('Account deletion failed')
        return fail('Could not delete your account. Please try again.', 503)
    session.clear()
    return jsonify({'message': 'Your account has been deleted.'}), 200
