"""Authentication blueprint: register, login, logout, password change."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app import limiter
from app.forms import RegistrationForm, LoginForm, ChangePasswordForm
from app.models import (
    get_user_by_email, create_user, record_login_success, record_login_failure,
    update_password,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
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
        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


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
