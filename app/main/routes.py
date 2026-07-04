"""Public-facing pages: home, hotel search, hotel detail."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app import limiter
from app.forms import SearchForm, ReviewForm
from app.models import (
    get_all_hotels, search_hotels, get_hotel_by_id, get_rooms_by_hotel, get_trending_hotels,
    get_most_liked_hotels, get_distinct_amenities, get_reviews_for_hotel, get_hotel_rating_summary,
    get_user_review_for_hotel, user_can_review_hotel, upsert_review,
)

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    form = SearchForm()
    hotels = get_all_hotels()[:6]
    trending = get_trending_hotels(limit=4)
    most_liked = get_most_liked_hotels(limit=6)
    return render_template(
        "index.html", hotels=hotels, form=form, trending=trending, most_liked=most_liked
    )


@main_bp.route("/hotels")
def hotels():
    form = SearchForm(request.args, meta={"csrf": False})
    city = request.args.get("city", "").strip()
    guests = request.args.get("guests", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    star_rating = request.args.get("star_rating", "").strip()
    amenities = [a for a in request.args.getlist("amenities") if a.strip()]
    sort = request.args.get("sort", "").strip()

    results = search_hotels(
        city=city or None,
        guests=guests or None,
        min_price=min_price or None,
        max_price=max_price or None,
        min_star=star_rating or None,
        amenities=amenities or None,
        sort=sort or None,
    )

    filters = {
        "city": city,
        "guests": guests,
        "min_price": min_price,
        "max_price": max_price,
        "star_rating": star_rating,
        "amenities": amenities,
        "sort": sort,
        "any_active": bool(
            city or guests or min_price or max_price or star_rating or amenities or sort
        ),
    }

    return render_template(
        "hotels.html",
        hotels=results,
        form=form,
        city=city,
        filters=filters,
        amenities_options=get_distinct_amenities(),
    )


@main_bp.route("/hotels/<int:hotel_id>")
def hotel_detail(hotel_id):
    hotel = get_hotel_by_id(hotel_id)
    if not hotel:
        abort(404)
    rooms = get_rooms_by_hotel(hotel_id)
    reviews = get_reviews_for_hotel(hotel_id)
    rating_summary = get_hotel_rating_summary(hotel_id)

    review_form = None
    can_review = False
    user_review = None
    if current_user.is_authenticated:
        user_review = get_user_review_for_hotel(current_user.id, hotel_id)
        can_review = user_can_review_hotel(current_user.id, hotel_id)
        if can_review:
            review_form = ReviewForm(obj=user_review) if user_review else ReviewForm()
            if user_review:
                review_form.rating.data = str(user_review["rating"])

    return render_template(
        "hotel_detail.html",
        hotel=hotel,
        rooms=rooms,
        reviews=reviews,
        rating_summary=rating_summary,
        review_form=review_form,
        can_review=can_review,
        user_review=user_review,
    )


@main_bp.route("/hotels/<int:hotel_id>/review", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def submit_review(hotel_id):
    hotel = get_hotel_by_id(hotel_id)
    if not hotel:
        abort(404)

    if not user_can_review_hotel(current_user.id, hotel_id):
        flash("You can review a hotel after a completed stay there.", "error")
        return redirect(url_for("main.hotel_detail", hotel_id=hotel_id))

    form = ReviewForm()
    if form.validate_on_submit():
        upsert_review(current_user.id, hotel_id, int(form.rating.data), form.comment.data or None)
        flash("Thanks — your review has been saved.", "success")
    else:
        flash("Please correct the errors below and try again.", "error")

    return redirect(url_for("main.hotel_detail", hotel_id=hotel_id))


@main_bp.route("/about")
def about():
    return render_template("about.html")


@main_bp.route("/help-center")
def help_center():
    return render_template("help_center.html")


@main_bp.route("/safety-tips")
def safety_tips():
    return render_template("safety_tips.html")


@main_bp.route("/accessibility")
def accessibility():
    return render_template("accessibility.html")


@main_bp.route("/cancellations")
def cancellations():
    return render_template("cancellations.html")


@main_bp.route("/contact-us")
def contact_us():
    return render_template("contact_us.html")


@main_bp.route("/privacy-notice")
def privacy_notice():
    return render_template("privacy_notice.html")


@main_bp.route("/terms-of-service")
def terms_of_service():
    return render_template("terms_of_service.html")
