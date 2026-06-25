"""TOTP (time-based one-time password) helpers for two-factor authentication.

Uses pyotp for secret generation / code verification (RFC 6238) and qrcode
to render an inline QR code (as a base64 PNG data URI, so no image files
need to be written to disk) for scanning with an authenticator app such as
Google Authenticator or Authy.
"""
import base64
import io

import pyotp
import qrcode


def generate_secret():
    return pyotp.random_base32()


def build_qr_data_uri(secret, account_email, issuer_name):
    uri = pyotp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=issuer_name)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_code(secret, code):
    """Check a 6-digit code, allowing +/-1 time-step for clock drift."""
    if not secret:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)
