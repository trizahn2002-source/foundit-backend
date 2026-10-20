
import os
import resend
from dotenv import load_dotenv

load_dotenv()


def send_verification_email(recipient, code):
    """Send a FoundIt email verification code."""

    resend.api_key = os.environ["RESEND_API_KEY"]

    result = resend.Emails.send({
        "from": os.getenv(
            "MAIL_FROM",
            "FoundIt <onboarding@resend.dev>"
        ),
        "to": [recipient],
        "subject": "Your FoundIt verification code",
        "text": (
            "Welcome to FoundIt!\n\n"
            f"Your verification code is: {code}\n\n"
            "This code expires in 5 minutes.\n\n"
            "If you didn't request this, you can ignore it.\n\n"
            "The FoundIt Team"
        ),
    })

    return result


def send_password_reset_email(recipient, reset_link):
    """Send a secure FoundIt password-reset link."""

    resend.api_key = os.environ["RESEND_API_KEY"]

    return resend.Emails.send({
        "from": os.getenv(
            "MAIL_FROM",
            "FoundIt <onboarding@resend.dev>"
        ),
        "to": [recipient],
        "subject": "Reset your FoundIt password",
        "text": (
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
    })
