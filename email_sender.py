
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
