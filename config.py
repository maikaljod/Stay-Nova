"""Configuration settings for the StayNova Flask application.

All secrets are read from environment variables (see .env.example).
Never commit a real .env file or hardcode secrets here.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool_env(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    """Base configuration shared by all environments."""

    # --- Core / secrets -------------------------------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key-change-me")
    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = _bool_env("FLASK_DEBUG", False)

    # --- MySQL / pymysql --------------------------------------------------
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "root")
    MYSQL_DB = os.environ.get("MYSQL_DB", "staynova")

    # --- Session / cookie security ---------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # --- CSRF (Flask-WTF) ---------------------------------------------------
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # --- Misc -----------------------------------------------------------
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB request body cap
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # --- Outgoing email ---------------------------------------------------
    # If MAIL_SERVER is unset (the default), emails are written to
    # instance/outbox/ instead of actually being sent, so the app works
    # out of the box without a real mail server configured.
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = _bool_env("MAIL_USE_TLS", True)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@staynova.com")

    # Used to build absolute links inside emails (verify/reset).
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000")

    # --- Account security: email verification / password reset / 2FA -----
    EMAIL_VERIFICATION_MAX_AGE = int(os.environ.get("EMAIL_VERIFICATION_MAX_AGE", 60 * 60 * 24))  # 24h
    PASSWORD_RESET_MAX_AGE = int(os.environ.get("PASSWORD_RESET_MAX_AGE", 60 * 60))  # 1h
    TOTP_ISSUER_NAME = os.environ.get("TOTP_ISSUER_NAME", "StayNova")

    # --- Password hashing --------------------------------------------------
    # "scrypt" (Werkzeug's current default) is memory-hard and a strong
    # choice; "pbkdf2:sha256" is a widely-compatible alternative. Made
    # explicit/configurable rather than left implicit, so it's a documented,
    # deliberate choice instead of "whatever this Werkzeug version defaults to".
    PASSWORD_HASH_METHOD = os.environ.get("PASSWORD_HASH_METHOD", "scrypt")


class DevelopmentConfig(Config):
    ENV = "development"
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    ENV = "production"
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env_name = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env_name, DevelopmentConfig)
