"""Authentication blueprint: register, login, logout, password change,
email verification, password reset, and two-factor authentication."""
from datetime import datetime, timedelta

from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from app import limiter
from app.forms import (
    RegistrationForm, LoginForm, ChangePasswordForm, ResendVerificationForm,
    ForgotPasswordForm, ResetPasswordForm,
    TwoFactorSetupForm, TwoFactorVerifyForm, TwoFactorDisableForm,
)
from app.models import (
    get_user_by_email, get_user_by_id, create_user, record_login_success, record_login_failure,
    update_password, mark_email_verified, set_reset_token, get_user_by_reset_token,
    clear_reset_token, reset_password, set_totp_secret, enable_totp, disable_totp,
)
from app.email_utils import send_email
from app.tokens import generate_token, verify_token, EMAIL_VERIFY_SALT, PASSWORD_RESET_SALT
from app.twofactor import generate_secret, build_qr_data_uri, verify_code

PENDING_2FA_SESSION_KEY = "pending_2fa_user_id"
PENDING_2FA_REMEMBER_KEY = "pending_2fa_remember"
PENDING_2FA_SECRET_SESSION_KEY = "pending_totp_secret"

auth_bp = Blueprint("auth", __name__)


def _absolute_url(endpoint, **values):
    base = current_app.config["APP_BASE_URL"].rstrip("/")
    return base + url_for(endpoint, **values)


def _send_verification_email(user):
    token = generate_token(user.email, salt=EMAIL_VERIFY_SALT)
    link = _absolute_url("auth.verify_email", token=token)
    send_email(
        user.email,
        "Verify your StayNova email address",
        f"Hi {user.first_name},\n\n"
        f"Please confirm your email address by visiting the link below "
        f"(valid for 24 hours):\n\n{link}\n\n"
        f"If you didn't create a StayNova account, you can ignore this email.",
    )


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        existing = get_user_by_email(form.email.data)
        if existing:
            # Generic message: don't reveal that the email is already registered
            flash("Could not create account with the details provided. Please try again.", "error")
            return render_template("auth/register.html", form=form)

        create_user(
            form.first_name.data,
            form.last_name.data,
            form.email.data,
            form.phone.data or None,
            form.password.data,
        )
        new_user = get_user_by_email(form.email.data)
        _send_verification_email(new_user)
        flash(
            "Account created! We've sent a verification link to your email — "
            "please confirm it before logging in.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    email = verify_token(token, salt=EMAIL_VERIFY_SALT, max_age=current_app.config["EMAIL_VERIFICATION_MAX_AGE"])
    if not email:
        flash("That verification link is invalid or has expired. Request a new one below.", "error")
        return redirect(url_for("auth.resend_verification"))

    user = get_user_by_email(email)
    if not user:
        flash("That verification link is invalid or has expired. Request a new one below.", "error")
        return redirect(url_for("auth.resend_verification"))

    if not user.is_email_verified:
        mark_email_verified(user.id)
        flash("Your email has been verified. You can now log in.", "success")
    else:
        flash("Your email was already verified. You can log in.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def resend_verification():
    form = ResendVerificationForm()
    if form.validate_on_submit():
        user = get_user_by_email(form.email.data)
        if user and not user.is_email_verified:
            _send_verification_email(user)
        # Same message whether or not the account exists / is already verified,
        # so this endpoint can't be used to enumerate registered emails.
        flash(
            "If that email is registered and not yet verified, we've sent a new verification link.",
            "info",
        )
        return redirect(url_for("auth.login"))
    return render_template("auth/resend_verification.html", form=form)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = get_user_by_email(form.email.data)
        if user:
            raw_token = generate_token(user.email, salt=PASSWORD_RESET_SALT)
            max_age = current_app.config["PASSWORD_RESET_MAX_AGE"]
            expires_at = datetime.utcnow() + timedelta(seconds=max_age)
            set_reset_token(user.id, raw_token, expires_at)
            link = _absolute_url("auth.reset_password_request", token=raw_token)
            send_email(
                user.email,
                "Reset your StayNova password",
                f"Hi {user.first_name},\n\n"
                f"We received a request to reset your password. This link is valid "
                f"for {max_age // 60} minutes:\n\n{link}\n\n"
                f"If you didn't request this, you can safely ignore this email — "
                f"your password won't change.",
            )
        # Same message whether or not the account exists, to avoid email enumeration.
        flash("If an account exists for that email, we've sent password reset instructions.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def reset_password_request(token):
    max_age = current_app.config["PASSWORD_RESET_MAX_AGE"]
    email = verify_token(token, salt=PASSWORD_RESET_SALT, max_age=max_age)
    user = get_user_by_reset_token(token) if email else None

    if not email or not user or user.email != email:
        flash("That reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        reset_password(user.id, form.new_password.data)
        flash("Your password has been reset. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = get_user_by_email(form.email.data)

        if user and user.is_locked():
            flash("Too many failed attempts. Please try again in a few minutes.", "error")
            return render_template("auth/login.html", form=form)

        if user and user.check_password(form.password.data) and user.is_active:
            if not user.is_email_verified:
                flash(
                    "Please verify your email before logging in. "
                    "Didn't get the link? Use \"Resend verification email\" below.",
                    "error",
                )
                return render_template("auth/login.html", form=form)

            if user.has_2fa_enabled:
                # Don't fully log in yet — stash the pending user and hand off
                # to the 2FA verification step.
                session[PENDING_2FA_SESSION_KEY] = user.id
                session[PENDING_2FA_REMEMBER_KEY] = (form.remember_me.data == "1")
                next_page = request.args.get("next")
                return redirect(url_for("auth.two_factor_verify", next=next_page))

            record_login_success(user.id)
            login_user(user, remember=(form.remember_me.data == "1"))
            flash(f"Welcome back, {user.first_name}!", "success")
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("admin.dashboard" if user.is_admin else "main.index"))

        if user:
            record_login_failure(user)

        # Same generic message whether the email exists or not
        flash("Invalid email or password.", "error")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "error")
        else:
            update_password(current_user.id, form.new_password.data)
            flash("Password updated successfully.", "success")
            return redirect(url_for("booking.dashboard"))
    return render_template("auth/change_password.html", form=form)


@auth_bp.route("/2fa/verify", methods=["GET", "POST"])
@limiter.limit("10 per 5 minutes")
def two_factor_verify():
    user_id = session.get(PENDING_2FA_SESSION_KEY)
    if not user_id:
        return redirect(url_for("auth.login"))

    user = get_user_by_id(user_id)
    if not user or not user.has_2fa_enabled:
        session.pop(PENDING_2FA_SESSION_KEY, None)
        session.pop(PENDING_2FA_REMEMBER_KEY, None)
        return redirect(url_for("auth.login"))

    form = TwoFactorVerifyForm()
    if form.validate_on_submit():
        if verify_code(user.totp_secret, form.code.data):
            remember = session.pop(PENDING_2FA_REMEMBER_KEY, False)
            session.pop(PENDING_2FA_SESSION_KEY, None)
            record_login_success(user.id)
            login_user(user, remember=remember)
            flash(f"Welcome back, {user.first_name}!", "success")
            next_page = request.args.get("next") or request.form.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("admin.dashboard" if user.is_admin else "main.index"))
        flash("Invalid authentication code. Please try again.", "error")

    return render_template("auth/two_factor_verify.html", form=form, next=request.args.get("next", ""))


@auth_bp.route("/2fa/cancel", methods=["POST"])
def two_factor_cancel():
    session.pop(PENDING_2FA_SESSION_KEY, None)
    session.pop(PENDING_2FA_REMEMBER_KEY, None)
    return redirect(url_for("auth.login"))


@auth_bp.route("/account/2fa", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per 5 minutes", methods=["POST"])
def two_factor_setup():
    if current_user.has_2fa_enabled:
        disable_form = TwoFactorDisableForm()
        if disable_form.validate_on_submit():
            if not current_user.check_password(disable_form.current_password.data):
                flash("Current password is incorrect.", "error")
            else:
                disable_totp(current_user.id)
                flash("Two-factor authentication has been disabled.", "info")
                return redirect(url_for("auth.two_factor_setup"))
        return render_template("auth/two_factor_setup.html", enabled=True, disable_form=disable_form)

    secret = session.get(PENDING_2FA_SECRET_SESSION_KEY)
    if not secret:
        secret = generate_secret()
        session[PENDING_2FA_SECRET_SESSION_KEY] = secret

    setup_form = TwoFactorSetupForm()
    if setup_form.validate_on_submit():
        if verify_code(secret, setup_form.code.data):
            set_totp_secret(current_user.id, secret)
            enable_totp(current_user.id)
            session.pop(PENDING_2FA_SECRET_SESSION_KEY, None)
            flash("Two-factor authentication is now enabled on your account.", "success")
            return redirect(url_for("auth.two_factor_setup"))
        flash("That code didn't match. Please try again.", "error")

    qr_data_uri = build_qr_data_uri(secret, current_user.email, current_app.config["TOTP_ISSUER_NAME"])
    return render_template(
        "auth/two_factor_setup.html",
        enabled=False,
        setup_form=setup_form,
        qr_data_uri=qr_data_uri,
        secret=secret,
    )
