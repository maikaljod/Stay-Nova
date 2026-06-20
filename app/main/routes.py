"""Public-facing pages: home, hotel search, hotel detail."""
from flask import Blueprint, render_template, request

from app.forms import SearchForm
from app.models import get_all_hotels, search_hotels, get_hotel_by_id, get_rooms_by_hotel

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    form = SearchForm()
    hotels = get_all_hotels()[:6]
    return render_template("index.html", hotels=hotels, form=form)


@main_bp.route("/hotels")
def hotels():
    form = SearchForm(request.args, meta={"csrf": False})
    city = request.args.get("city", "").strip()
    guests = request.args.get("guests", "").strip()
    results = search_hotels(city=city or None, guests=guests or None)
    return render_template("hotels.html", hotels=results, form=form, city=city)


@main_bp.route("/hotels/<int:hotel_id>")
def hotel_detail(hotel_id):
    hotel = get_hotel_by_id(hotel_id)
    if not hotel:
        from flask import abort
        abort(404)
    rooms = get_rooms_by_hotel(hotel_id)
    return render_template("hotel_detail.html", hotel=hotel, rooms=rooms)


@main_bp.route("/about")
def about():
    return render_template("about.html")
