"""Authenticated FoundIt profile and account-management routes."""
import hashlib
import os
import hmac
from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import SQLAlchemyError
from config import app, db
from models import User, Item, Claim, GoogleIdentity, LoginOTP, EmailVerification, PasswordResetToken, Tip, PendingEmailChange
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


def update_username_for_user(user, username):
    if not isinstance(username, str) or not (1 <= len(username.strip()) <= 80):
        return fail('Username must contain 1 to 80 characters.', 400)
    username = username.strip()
    if User.query.filter(User.id != user.id, User.username == username).first():
        return fail('Username is already in use.', 409)
    user.username = username
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return fail('Unable to update username.', 409)
    return jsonify({'message': 'Username updated.', 'user': user.to_dict()}), 200


def change_password_for_user(user, data):
    if GoogleIdentity.query.filter_by(user_id=user.id).first() is not None:
        return fail('Password changes are not available for Google-only accounts.', 403)
    old, new = data.get('current_password'), data.get('new_password')
    if not isinstance(old, str) or not isinstance(new, str) or not user.check_password(old):
        return fail('Current password is incorrect.', 403)
    valid, explanation = validate_password(new, user.username, user.email)
    if not valid:
        return fail(explanation, 400)
    if user.check_password(new):
        return fail('Choose a different password.', 400)
    user.set_password(new)
    db.session.commit()
    session.clear()
    return jsonify({'message': 'Password updated. Please sign in again.'}), 200


# Email changes are a two-step operation: the old email stays active until
# a fresh verification code sent to the proposed address is confirmed.
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _deliver_email_change_code(address, code):
    # Dedicated SMTP settings, never put credentials in source control.
    server = os.getenv('EMAIL_CHANGE_SMTP_HOST')
    sender = os.getenv('EMAIL_CHANGE_FROM')
    username = os.getenv('EMAIL_CHANGE_SMTP_USER')
    password = os.getenv('EMAIL_CHANGE_SMTP_PASSWORD')
    if not all((server, sender, username, password)):
        raise RuntimeError('Email-change delivery is not configured')
    port = int(os.getenv('EMAIL_CHANGE_SMTP_PORT', '465'))
    message = EmailMessage()
    message['Subject'] = 'Verify your new FoundIt email'
    message['From'] = sender
    message['To'] = address
    message.set_content(f'Your FoundIt email-change code is: {code}\nIt expires in 10 minutes.\nIf you did not request this, ignore it.')
    with smtplib.SMTP_SSL(server, port, context=ssl.create_default_context(), timeout=15) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)


def _email_change_hash(code):
    return hmac.new(app.config['SECRET_KEY'].encode('utf-8'), code.encode('utf-8'), hashlib.sha256).hexdigest()


@account_settings_bp.post('/api/account/email-change/request')
@rate_limit('request_email_change')
def request_email_change():
    user = current_user()
    if user is None:
        return fail('Please sign in.', 401)
    data = json_body() or {}
    new_email = data.get('new_email')
    if not isinstance(new_email, str):
        return fail('Provide a valid new email.', 400)
    new_email = new_email.strip().lower()
    if not (3 <= len(new_email) <= 120 and new_email.count('@') == 1 and '.' in new_email.split('@')[1]):
        return fail('Provide a valid new email.', 400)
    if new_email == user.email or User.query.filter_by(email=new_email).first():
        return fail('That email cannot be used.', 409)
    identity = GoogleIdentity.query.filter_by(user_id=user.id).first()
    if identity:
        # A Google-only identity remains anchored to its verified Google email.
        return fail('Google accounts cannot change their sign-in email here.', 403)
    if not isinstance(data.get('current_password'), str) or not user.check_password(data['current_password']):
        return fail('Current password is incorrect.', 403)
    if os.getenv('OTP_TEST_MODE', 'true').lower() == 'true':
        if new_email != os.getenv('OTP_TEST_EMAIL', '').strip().lower():
            return fail('Email delivery is restricted during testing.', 403)
    code = f'{secrets.randbelow(1000000):06d}'
    pending = PendingEmailChange.query.filter_by(user_id=user.id).first()
    if pending is None:
        pending = PendingEmailChange(user_id=user.id)
        db.session.add(pending)
    pending.new_email = new_email
    pending.code_hash = _email_change_hash(code)
    pending.expires_at = _utcnow() + timedelta(minutes=10)
    pending.attempts = 0
    try:
        _deliver_email_change_code(new_email, code)
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception('Email-change delivery failed')
        return fail('Could not send a verification code. Please try again.', 503)
    return jsonify({'message': 'A verification code has been sent to the new email.'}), 200


@account_settings_bp.post('/api/account/email-change/confirm')
@rate_limit('confirm_email_change')
def confirm_email_change():
    user = current_user()
    if user is None:
        return fail('Please sign in.', 401)
    data = json_body() or {}
    code = data.get('code')
    pending = PendingEmailChange.query.filter_by(user_id=user.id).first()
    if pending is None or pending.expires_at <= _utcnow():
        return fail('Email-change code is invalid or expired.', 400)
    if pending.attempts >= 5:
        return fail('Too many incorrect attempts. Request a new code.', 429)
    pending.attempts += 1
    if not isinstance(code, str) or not hmac.compare_digest(pending.code_hash, _email_change_hash(code)):
        db.session.commit()
        return fail('Email-change code is invalid or expired.', 400)
    if User.query.filter(User.id != user.id, User.email == pending.new_email).first():
        return fail('That email is already registered.', 409)
    user.email = pending.new_email
    db.session.delete(pending)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return fail('That email is already registered.', 409)
    # Prevent stale sessions after changing the primary sign-in identifier.
    session.clear()
    return jsonify({'message': 'Email changed. Please sign in again.'}), 200


@account_settings_bp.post('/api/account/change-password')
@rate_limit('change_password')
def change_password():
    user = current_user()
    if not user:
        return fail('Please sign in.', 401)
    return change_password_for_user(user, json_body() or {})


def delete_account_for_user(user, data):
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
        issued_at = claims.get('iat')
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if not isinstance(issued_at, (int, float)) or not (0 <= now_ts - int(issued_at) <= 300):
            return fail('Please authenticate with Google again.', 403)
        if not hmac.compare_digest(str(claims.get('sub', '')), str(google_identity.google_sub)):
            return fail('This Google account does not match your FoundIt account.', 403)
    else:
        password = data.get('password')
        if not isinstance(password, str) or not user.check_password(password):
            return fail('Current password is incorrect.', 403)

    try:
        # Keep the payment ledger, but detach deleted identities/items and wipe
        # the personal phone number on transactions involving this account.
        db.session.query(Tip).filter(
            (Tip.tipper_id == user.id) | (Tip.finder_id == user.id)
        ).update({Tip.phone: None}, synchronize_session=False)
        db.session.query(Tip).filter(Tip.tipper_id == user.id).update(
            {Tip.tipper_id: None}, synchronize_session=False)
        db.session.query(Tip).filter(Tip.finder_id == user.id).update(
            {Tip.finder_id: None}, synchronize_session=False)
        # Remove claims on the user's items, then their own claims, then the items.
        # Keep unrelated users' reports and claims intact.
        item_ids = [item_id for (item_id,) in db.session.query(Item.id).filter_by(user_id=user.id).all()]
        if item_ids:
            db.session.query(Tip).filter(Tip.item_id.in_(item_ids)).update(
                {Tip.item_id: None}, synchronize_session=False)
            Claim.query.filter(Claim.item_id.in_(item_ids)).delete(synchronize_session=False)
        Claim.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        Item.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        # Explicit dependent cleanup avoids foreign-key restrictions even if cascades differ.
        GoogleIdentity.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        LoginOTP.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        EmailVerification.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        PasswordResetToken.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        PendingEmailChange.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        db.session.delete(user)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception('Account deletion failed')
        return fail('Could not delete your account. Please try again.', 503)
    session.clear()
    return jsonify({'message': 'Your account has been deleted.'}), 200


@account_settings_bp.post('/api/account/delete')
@rate_limit('delete_account')
def delete_account():
    user = current_user()
    if not user:
        return fail('Please sign in.', 401)
    return delete_account_for_user(user, json_body() or {})
