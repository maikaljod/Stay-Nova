"""Booking flow + user dashboard."""
from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, Response
from flask_login import login_required, current_user

from app.forms import BookingForm
from app.models import (
    get_room_by_id, is_room_available, create_booking, get_bookings_by_user,
    get_booking_by_id, cancel_booking,
)

booking_bp = Blueprint("booking", __name__)


@booking_bp.route("/book/<int:room_id>", methods=["GET", "POST"])
@login_required
def book_room(room_id):
    room = get_room_by_id(room_id)
    if not room:
        abort(404)

    form = BookingForm(room_id=room_id)
    if request.method == "GET":
        form.check_in.data = date.today() + timedelta(days=1)
        form.check_out.data = date.today() + timedelta(days=2)
        form.guests.data = 2

    if form.validate_on_submit():
        check_in, check_out = form.check_in.data, form.check_out.data

        if check_in < date.today():
            flash("Check-in date cannot be in the past.", "error")
            return render_template("booking.html", room=room, form=form)

        if form.guests.data > room["capacity"]:
            flash(f"This room type fits up to {room['capacity']} guests.", "error")
            return render_template("booking.html", room=room, form=form)

        if not is_room_available(room_id, check_in, check_out, room["total_rooms"]):
            flash("Sorry, this room is not available for the selected dates.", "error")
            return render_template("booking.html", room=room, form=form)

        nights = (check_out - check_in).days
        total_price = Decimal(room["price_per_night"]) * nights

        booking_id = create_booking(
            current_user.id, room_id, check_in, check_out, form.guests.data, total_price
        )
        flash("Booking confirmed! Have a great stay.", "success")
        return redirect(url_for("booking.confirmation", booking_id=booking_id))

    return render_template("booking.html", room=room, form=form)


@booking_bp.route("/booking/<int:booking_id>/confirmation")
@login_required
def confirmation(booking_id):
    booking = get_booking_by_id(booking_id)
    if not booking or booking["user_id"] != current_user.id:
        abort(404)
    return render_template("booking_confirmation.html", booking=booking)


@booking_bp.route("/dashboard")
@login_required
def dashboard():
    bookings = get_bookings_by_user(current_user.id)
    today = date.today()

    # Current: still-active confirmed stays (upcoming or in progress).
    # Past: anything cancelled/completed, or a confirmed stay whose
    # check-out date has already gone by.
    current_bookings = [
        b for b in bookings if b["status"] == "confirmed" and b["check_out"] >= today
    ]
    past_bookings = [b for b in bookings if b not in current_bookings]

    return render_template(
        "dashboard.html",
        bookings=bookings,
        current_bookings=current_bookings,
        past_bookings=past_bookings,
        today=today,
    )


@booking_bp.route("/booking/<int:booking_id>/confirmation/download")
@login_required
def download_confirmation(booking_id):
    booking = get_booking_by_id(booking_id)
    if not booking or booking["user_id"] != current_user.id:
        abort(404)
    html = render_template("booking_confirmation_download.html", booking=booking)
    response = Response(html, mimetype="text/html")
    response.headers["Content-Disposition"] = f'attachment; filename="staynova-confirmation-{booking_id}.html"'
    return response


@booking_bp.route("/booking/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel(booking_id):
    booking = get_booking_by_id(booking_id)
    if not booking or booking["user_id"] != current_user.id:
        abort(404)
    if booking["status"] != "confirmed":
        flash("This booking can no longer be cancelled.", "error")
    else:
        cancel_booking(booking_id)
        flash("Booking cancelled.", "info")
    return redirect(url_for("booking.dashboard"))
