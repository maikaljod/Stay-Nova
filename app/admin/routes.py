"""Admin blueprint: dashboard + basic hotel/room/booking management.

All routes are protected by @admin_required (role check) on top of
@login_required, so only accounts with role='admin' can reach them.
"""
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required

from app.security import admin_required
from app.forms import HotelForm, RoomForm
from app.models import (
    get_admin_stats, get_all_hotels, create_hotel, delete_hotel, get_hotel_by_id,
    get_rooms_by_hotel, create_room, delete_room, get_all_bookings,
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
