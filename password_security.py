
import re


MIN_PASSWORD_LENGTH = 8


def get_password_requirements(password):
    """
    Return the five password requirements.

    This function is shared by registration,
    password changes and password resets.
    """
    if not isinstance(password, str):
        password = ""

    return {
        "min_length": len(password) >= MIN_PASSWORD_LENGTH,
        "uppercase": bool(re.search(r"[A-Z]", password)),
        "lowercase": bool(re.search(r"[a-z]", password)),
        "number": bool(re.search(r"[0-9]", password)),
        "symbol": bool(re.search(r"[^A-Za-z0-9\s]", password)),
    }


def validate_password(password, username="", email=""):
    """
    Enforce FoundIt's agreed password checklist.

    Returns (valid, message).
    """
    if not isinstance(password, str):
        return False, "Password is required."

    requirements = get_password_requirements(password)

    messages = {
        "min_length": "At least 8 characters",
        "uppercase": "At least one uppercase letter",
        "lowercase": "At least one lowercase letter",
        "number": "At least one number",
        "symbol": "At least one special character",
    }

    missing = [
        messages[key]
        for key, satisfied in requirements.items()
        if not satisfied
    ]

    if missing:
        return (
            False,
            "Password must meet these requirements: "
            + "; ".join(missing) + "."
        )

    return True, "Password meets all requirements."
