import os
import base64
from email.message import EmailMessage
import logging
import threading
logger = logging.getLogger(__name__)

import requests
import resend
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

load_dotenv()

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def _send_email(recipient, subject, body):
    """Send transactional email through the configured provider."""

    provider = os.getenv("EMAIL_PROVIDER", "resend").lower()

    if provider == "resend":
        resend.api_key = os.environ["RESEND_API_KEY"]

        return resend.Emails.send({
            "from": os.getenv(
                "MAIL_FROM",
                "FoundIt <onboarding@resend.dev>"
            ),
            "to": [recipient],
            "subject": subject,
            "text": body,
        })

    if provider == "gmail":
        credentials = Credentials(
            token=None,
            refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GMAIL_CLIENT_ID"],
            client_secret=os.environ["GMAIL_CLIENT_SECRET"],
            scopes=[GMAIL_SCOPE],
        )

        credentials.refresh(Request())

        message = EmailMessage()
        message["From"] = os.environ["GMAIL_SENDER_EMAIL"]
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        encoded = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("ascii")

        response = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={
                "Authorization": f"Bearer {credentials.token}"
            },
            json={"raw": encoded},
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    raise ValueError(f"Unsupported email provider: {provider}")


def send_verification_email(recipient, code):
    """Send a FoundIt email verification code."""

    return _send_email(
        recipient,
        "Your FoundIt verification code",
        (
            "Welcome to FoundIt!\n\n"
            f"Your verification code is: {code}\n\n"
            "This code expires in 5 minutes.\n\n"
            "If you didn't request this, you can ignore it.\n\n"
            "The FoundIt Team"
        ),
    )


def send_password_reset_email(recipient, reset_link):
    """Send a secure FoundIt password-reset link."""

    return _send_email(
        recipient,
        "Reset your FoundIt password",
        (
            "Hello,\n\n"
            "We received a request to reset your "
            "FoundIt password.\n\n"
            "Use the secure link below:\n\n"
            f"{reset_link}\n\n"
            "This link expires in 15 minutes "
            "and can only be used once.\n\n"
            "If you did not request this, "
            "you can safely ignore this email.\n\n"
            "The FoundIt Team"
        ),
    )


def send_login_otp_email(recipient, code):
    """Deliver a temporary code for password-based login."""

    return _send_email(
        recipient,
        "Your FoundIt sign-in code",
        (
            f"Your FoundIt sign-in code is: {code}\n\n"
            "This code expires in 5 minutes. "
            "If you did not attempt to sign in, "
            "please change your password.\n\n"
            "The FoundIt Team"
        ),
    )

def _notification_allowed(recipient):
    """Same Resend testing restriction used by the other email flows."""

    test_mode = os.getenv("OTP_TEST_MODE", "true").lower() == "true"

    if not test_mode:
        return True

    allowed = os.getenv("OTP_TEST_EMAIL", "").strip().lower()

    return bool(allowed) and (recipient or "").strip().lower() == allowed


def send_in_background(send_function, recipient, *args):
    """
    Send a notification without slowing down or breaking the request.

    Pass plain values only (no database objects), because this runs in
    another thread. Failures are logged and never raised.
    """

    if not recipient or not _notification_allowed(recipient):
        logger.info(
            "Skipped %s: recipient not allowed or missing",
            send_function.__name__,
        )
        return

    def run():
        try:
            send_function(recipient, *args)
        except Exception:
            logger.exception("Could not send %s", send_function.__name__)

    threading.Thread(target=run, daemon=True).start()


def send_claim_received_email(recipient, item_title, item_link):
    """Tell the item owner that someone submitted a claim."""

    return _send_email(
        recipient,
        "Someone claimed your item on FoundIt",
        (
            "Hello,\n\n"
            f'A new claim was submitted for your item "{item_title}".\n\n'
            "Log in and open the item to review it:\n\n"
            f"{item_link}\n\n"
            "Only you can approve or reject it.\n\n"
            "The FoundIt Team"
        ),
    )


def send_claim_approved_email(recipient, item_title, item_link):
    """Tell a claimant that their claim was approved."""

    return _send_email(
        recipient,
        "Your FoundIt claim was approved",
        (
            "Good news!\n\n"
            f'Your claim for "{item_title}" was approved.\n\n'
            "Log in and open the item to see how to contact the finder:\n\n"
            f"{item_link}\n\n"
            "The FoundIt Team"
        ),
    )


def send_claim_rejected_email(recipient, item_title, item_link):
    """Tell a claimant that their claim was not approved."""

    return _send_email(
        recipient,
        "Update on your FoundIt claim",
        (
            "Hello,\n\n"
            f'Your claim for "{item_title}" was not approved.\n\n'
            "You can view the item here:\n\n"
            f"{item_link}\n\n"
            "The FoundIt Team"
        ),
    )