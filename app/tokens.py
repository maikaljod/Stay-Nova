"""Signed, expiring tokens for email verification and password reset.

Tokens are itsdangerous-signed (tamper-proof, tied to SECRET_KEY) and carry
their own expiry, so they never need to be stored server-side to be
verified. For password reset we additionally persist a *hash* of the token
in the database (see app/models.py) so a reset link is single-use and can be
revoked — the signature alone would otherwise stay valid for its full
lifetime even after being used once.
"""
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app

EMAIL_VERIFY_SALT = "email-verify"
PASSWORD_RESET_SALT = "password-reset"


def _serializer(salt):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def generate_token(payload, salt):
    return _serializer(salt).dumps(payload)


def verify_token(token, salt, max_age):
    """Return the original payload, or None if invalid/expired."""
    try:
        return _serializer(salt).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
