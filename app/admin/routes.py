"""Admin blueprint: dashboard + basic hotel/room/booking management.

All routes are protected by @admin_required (role check) on top of
@login_required, so only accounts with role='admin' can reach them.
"""
import pymysql
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.security import admin_required
from app.forms import HotelForm, RoomForm
from app.models import (
    get_admin_stats, get_all_hotels, create_hotel, delete_hotel, get_hotel_by_id,
    get_rooms_by_hotel, create_room, delete_room, get_all_bookings,
    get_all_users_with_booking_counts, update_user_profile, delete_user, count_admins,
)

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    stats = get_admin_stats()
    recent_bookings = get_all_bookings()[:5]
    return render_template("admin/dashboard.html", stats=stats, recent_bookings=recent_bookings)


@admin_bp.route("/hotels", methods=["GET", "POST"])
@login_required
@admin_required
def hotels():
    form = HotelForm()
    if form.validate_on_submit():
        create_hotel(
            form.name.data, form.city.data, form.address.data, form.description.data,
            form.star_rating.data, form.image_url.data or None, form.amenities.data or None,
        )
        flash("Hotel added.", "success")
        return redirect(url_for("admin.hotels"))
    return render_template("admin/hotels.html", form=form, hotels=get_all_hotels())


@admin_bp.route("/hotels/<int:hotel_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_hotel_route(hotel_id):
    delete_hotel(hotel_id)
    flash("Hotel removed.", "info")
    return redirect(url_for("admin.hotels"))


@admin_bp.route("/hotels/<int:hotel_id>/rooms", methods=["GET", "POST"])
@login_required
@admin_required
def rooms(hotel_id):
    hotel = get_hotel_by_id(hotel_id)
    if not hotel:
        from flask import abort
        abort(404)

    form = RoomForm()
    if form.validate_on_submit():
        create_room(
            hotel_id, form.room_type.data, form.description.data, form.price_per_night.data,
            form.capacity.data, form.total_rooms.data, form.image_url.data or None,
        )
        flash("Room added.", "success")
        return redirect(url_for("admin.rooms", hotel_id=hotel_id))

    return render_template(
        "admin/rooms.html", form=form, hotel=hotel, rooms=get_rooms_by_hotel(hotel_id)
    )


@admin_bp.route("/rooms/<int:room_id>/delete/<int:hotel_id>", methods=["POST"])
@login_required
@admin_required
def delete_room_route(room_id, hotel_id):
    delete_room(room_id)
    flash("Room removed.", "info")
    return redirect(url_for("admin.rooms", hotel_id=hotel_id))


@admin_bp.route("/bookings")
@login_required
@admin_required
def bookings():
    return render_template("admin/bookings.html", bookings=get_all_bookings())


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    return render_template("admin/users.html", users=get_all_users_with_booking_counts())


@admin_bp.route("/users/<int:user_id>/update", methods=["POST"])
@login_required
@admin_required
def update_user_route(user_id):
    full_name = (request.form.get("full_name") or "").strip()
    first_name, _, last_name = full_name.partition(" ")
    email = (request.form.get("email") or "").strip()
    role = request.form.get("role")

    if role not in ("user", "admin"):
        flash("Invalid role.", "danger")
        return redirect(url_for("admin.users"))
    if not first_name or not email:
        flash("Name and email are required.", "danger")
        return redirect(url_for("admin.users"))
    if user_id == current_user.id and role != "admin":
        flash("You can't remove your own admin role.", "danger")
        return redirect(url_for("admin.users"))

    try:
        update_user_profile(user_id, first_name, last_name, email, role)
    except pymysql.err.IntegrityError:
        flash("That email is already in use by another account.", "danger")
        return redirect(url_for("admin.users"))

    flash("User updated.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user_route(user_id):
    if user_id == current_user.id:
        flash("You can't delete your own account.", "danger")
        return redirect(url_for("admin.users"))
    return_users = get_all_users_with_booking_counts()
    target = next((u for u in return_users if u["id"] == user_id), None)
    if target and target["role"] == "admin" and count_admins() <= 1:
        flash("Can't delete the last remaining admin.", "danger")
        return redirect(url_for("admin.users"))

    delete_user(user_id)
    flash("User removed.", "info")
    return redirect(url_for("admin.users"))
