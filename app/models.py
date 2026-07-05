"""Data-access helpers and the Flask-Login user wrapper.

Every query below uses parameterized placeholders. No user input is ever
interpolated directly into a SQL string.
"""
import hashlib
from datetime import datetime, timedelta

from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.db import query, execute

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


def hash_password(plain_password):
    """Hash a plain-text password using the app-configured method.

    Centralizing this (instead of calling generate_password_hash directly
    at each call site) means the hashing method is a single, explicit,
    documented config value (PASSWORD_HASH_METHOD) rather than an implicit
    Werkzeug default that could silently change between versions.
    """
    method = current_app.config.get("PASSWORD_HASH_METHOD", "scrypt")
    return generate_password_hash(plain_password, method=method)


def hash_token(raw_token):
    """Hash a raw, single-use token (e.g. password reset) before storing it.

    Tokens are already itsdangerous-signed and expiring; hashing before
    storage means a database leak alone can't be used to reset a password,
    the same defense-in-depth principle as hashing user passwords.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class User(UserMixin):
    """Adapter around a users row so Flask-Login can work with it."""

    def __init__(self, row):
        self.id = row["id"]
        self.first_name = row["first_name"]
        self.last_name = row["last_name"]
        self.email = row["email"]
        self.phone = row.get("phone")
        self.password_hash = row["password_hash"]
        self.role = row["role"]
        self.is_active_flag = bool(row.get("is_active", 1))
        self.failed_logins = row.get("failed_logins", 0)
        self.locked_until = row.get("locked_until")
        self.email_verified = bool(row.get("email_verified", 0))
        self.totp_secret = row.get("totp_secret")
        self.totp_enabled_flag = bool(row.get("totp_enabled", 0))

    # Flask-Login expects get_id() to return a string
    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        return self.is_active_flag

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_email_verified(self):
        return self.email_verified

    @property
    def has_2fa_enabled(self):
        return self.totp_enabled_flag

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def check_password(self, plain_password):
        return check_password_hash(self.password_hash, plain_password)

    def is_locked(self):
        return bool(self.locked_until and self.locked_until > datetime.utcnow())


# ---------------------------------------------------------------------------
# User queries
# ---------------------------------------------------------------------------

def get_user_by_id(user_id):
    row = query("SELECT * FROM users WHERE id = %s", (user_id,), fetch="one")
    return User(row) if row else None


def get_user_by_email(email):
    row = query("SELECT * FROM users WHERE email = %s", (email.lower().strip(),), fetch="one")
    return User(row) if row else None


def create_user(first_name, last_name, email, phone, password):
    password_hash = hash_password(password)
    return execute(
        """INSERT INTO users (first_name, last_name, email, phone, password_hash, role)
           VALUES (%s, %s, %s, %s, %s, 'user')""",
        (first_name.strip(), last_name.strip(), email.lower().strip(), phone, password_hash),
    )


def record_login_success(user_id):
    execute(
        "UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = %s",
        (user_id,),
    )


def record_login_failure(user):
    failed = user.failed_logins + 1
    if failed >= MAX_FAILED_LOGINS:
        locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
        execute(
            "UPDATE users SET failed_logins = %s, locked_until = %s WHERE id = %s",
            (failed, locked_until, user.id),
        )
    else:
        execute("UPDATE users SET failed_logins = %s WHERE id = %s", (failed, user.id))


def update_password(user_id, new_password):
    execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (hash_password(new_password), user_id),
    )


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

def mark_email_verified(user_id):
    execute("UPDATE users SET email_verified = 1 WHERE id = %s", (user_id,))


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

def set_reset_token(user_id, raw_token, expires_at):
    execute(
        "UPDATE users SET reset_token_hash = %s, reset_token_expires = %s WHERE id = %s",
        (hash_token(raw_token), expires_at, user_id),
    )


def get_user_by_reset_token(raw_token):
    """Look up a user by a raw reset token, honoring the stored expiry.

    Returns None if no user has this (hashed) token pending, or if it has
    expired server-side (independent of the itsdangerous signature's own
    expiry check, which the caller performs separately).
    """
    row = query(
        "SELECT * FROM users WHERE reset_token_hash = %s AND reset_token_expires > %s",
        (hash_token(raw_token), datetime.utcnow()),
        fetch="one",
    )
    return User(row) if row else None


def clear_reset_token(user_id):
    execute(
        "UPDATE users SET reset_token_hash = NULL, reset_token_expires = NULL WHERE id = %s",
        (user_id,),
    )


def reset_password(user_id, new_password):
    """Set a new password and invalidate the reset token in one place."""
    execute(
        "UPDATE users SET password_hash = %s, reset_token_hash = NULL, "
        "reset_token_expires = NULL, failed_logins = 0, locked_until = NULL WHERE id = %s",
        (hash_password(new_password), user_id),
    )


# ---------------------------------------------------------------------------
# Two-factor authentication (TOTP)
# ---------------------------------------------------------------------------

def set_totp_secret(user_id, secret):
    """Stage a TOTP secret without enabling 2FA yet (until confirmed)."""
    execute("UPDATE users SET totp_secret = %s WHERE id = %s", (secret, user_id))


def enable_totp(user_id):
    execute("UPDATE users SET totp_enabled = 1 WHERE id = %s", (user_id,))


def disable_totp(user_id):
    execute(
        "UPDATE users SET totp_enabled = 0, totp_secret = NULL WHERE id = %s",
        (user_id,),
    )


# ---------------------------------------------------------------------------
# Hotel / room queries
# ---------------------------------------------------------------------------

def get_all_hotels():
    return query("SELECT * FROM hotels ORDER BY name")


def get_trending_hotels(limit=4):
    """Hotels for the homepage "trending destinations" strip, each with its
    cheapest available room price (None if the hotel has no rooms yet)."""
    return query(
        """SELECT hotels.id, hotels.name, hotels.city, hotels.image_url, hotels.star_rating,
                  MIN(rooms.price_per_night) AS from_price
           FROM hotels
           LEFT JOIN rooms ON rooms.hotel_id = hotels.id
           GROUP BY hotels.id, hotels.name, hotels.city, hotels.image_url, hotels.star_rating
           ORDER BY hotels.star_rating DESC, hotels.name ASC
           LIMIT %s""",
        (limit,),
    )


def get_most_liked_hotels(limit=6, min_reviews=1):
    """Hotels guests rate highest, for the homepage "Most liked by guests"
    section. Ranked by review volume first, then average rating, so a hotel
    with a handful of glowing reviews doesn't outrank one loved by many.
    Only hotels with at least `min_reviews` review(s) are eligible.

    Review aggregates are computed in a subquery before joining to hotels/
    rooms, so a hotel with multiple rooms doesn't inflate its review count
    or skew its average via the join fan-out."""
    return query(
        """SELECT hotels.id, hotels.name, hotels.city, hotels.image_url, hotels.star_rating,
                  review_stats.review_count, review_stats.average_rating,
                  room_prices.from_price
           FROM hotels
           JOIN (
               SELECT hotel_id, COUNT(*) AS review_count, AVG(rating) AS average_rating
               FROM reviews
               GROUP BY hotel_id
               HAVING COUNT(*) >= %s
           ) AS review_stats ON review_stats.hotel_id = hotels.id
           LEFT JOIN (
               SELECT hotel_id, MIN(price_per_night) AS from_price
               FROM rooms
               GROUP BY hotel_id
           ) AS room_prices ON room_prices.hotel_id = hotels.id
           ORDER BY review_stats.review_count DESC, review_stats.average_rating DESC
           LIMIT %s""",
        (min_reviews, limit),
    )


def get_distinct_amenities():
    """Flatten every hotel's comma-separated amenities string into a sorted,
    de-duplicated list, for populating the hotels-page filter checkboxes."""
    rows = query("SELECT DISTINCT amenities FROM hotels WHERE amenities IS NOT NULL AND amenities <> ''")
    seen = set()
    for row in rows:
        for item in (row["amenities"] or "").split(","):
            name = item.strip()
            if name:
                seen.add(name)
    return sorted(seen)


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_HOTEL_SORT_OPTIONS = {
    "price_asc": "(room_prices.from_price IS NULL) ASC, room_prices.from_price ASC",
    "price_desc": "(room_prices.from_price IS NULL) ASC, room_prices.from_price DESC",
    "rating_desc": "average_rating DESC, review_count DESC",
}


def search_hotels(city=None, guests=None, min_price=None, max_price=None, min_star=None, amenities=None, sort=None):
    """Hotel search with optional filters. Price/rating come from LEFT JOIN
    subqueries (a hotel's cheapest room, and its review average) so hotels
    with no rooms or no reviews yet still show up rather than being dropped."""
    sql = """
        SELECT hotels.*, room_prices.from_price,
               COALESCE(review_stats.average_rating, 0) AS average_rating,
               COALESCE(review_stats.review_count, 0) AS review_count
        FROM hotels
        LEFT JOIN (
            SELECT hotel_id, MIN(price_per_night) AS from_price
            FROM rooms
            GROUP BY hotel_id
        ) AS room_prices ON room_prices.hotel_id = hotels.id
        LEFT JOIN (
            SELECT hotel_id, COUNT(*) AS review_count, AVG(rating) AS average_rating
            FROM reviews
            GROUP BY hotel_id
        ) AS review_stats ON review_stats.hotel_id = hotels.id
        WHERE 1=1
    """
    params = []

    if city:
        sql += " AND hotels.city LIKE %s"
        params.append(f"%{city}%")

    min_star_val = _safe_int(min_star)
    if min_star_val:
        sql += " AND hotels.star_rating >= %s"
        params.append(min_star_val)

    min_price_val = _safe_float(min_price)
    if min_price_val is not None:
        sql += " AND room_prices.from_price >= %s"
        params.append(min_price_val)

    max_price_val = _safe_float(max_price)
    if max_price_val is not None:
        sql += " AND room_prices.from_price <= %s"
        params.append(max_price_val)

    for amenity in (amenities or []):
        amenity = (amenity or "").strip()
        if amenity:
            sql += " AND hotels.amenities LIKE %s"
            params.append(f"%{amenity}%")

    order_by = _HOTEL_SORT_OPTIONS.get(sort, "hotels.name ASC")
    sql += f" ORDER BY {order_by}"

    hotels = query(sql, params)

    if guests:
        # keep only hotels that have at least one room fitting the party size
        filtered = []
        for hotel in hotels:
            rooms = get_rooms_by_hotel(hotel["id"])
            if any(r["capacity"] >= int(guests) for r in rooms):
                filtered.append(hotel)
        return filtered
    return hotels


def get_hotel_by_id(hotel_id):
    return query("SELECT * FROM hotels WHERE id = %s", (hotel_id,), fetch="one")


def create_hotel(name, city, address, description, star_rating, image_url, amenities):
    return execute(
        """INSERT INTO hotels (name, city, address, description, star_rating, image_url, amenities)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (name, city, address, description, star_rating, image_url, amenities),
    )


def delete_hotel(hotel_id):
    execute("DELETE FROM hotels WHERE id = %s", (hotel_id,))


def get_rooms_by_hotel(hotel_id):
    return query("SELECT * FROM rooms WHERE hotel_id = %s ORDER BY price_per_night", (hotel_id,))


def get_room_by_id(room_id):
    return query(
        """SELECT rooms.*, hotels.name AS hotel_name, hotels.city AS hotel_city
           FROM rooms JOIN hotels ON hotels.id = rooms.hotel_id
           WHERE rooms.id = %s""",
        (room_id,),
        fetch="one",
    )


def create_room(hotel_id, room_type, description, price_per_night, capacity, total_rooms, image_url):
    return execute(
        """INSERT INTO rooms (hotel_id, room_type, description, price_per_night, capacity, total_rooms, image_url)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (hotel_id, room_type, description, price_per_night, capacity, total_rooms, image_url),
    )


def delete_room(room_id):
    execute("DELETE FROM rooms WHERE id = %s", (room_id,))


# ---------------------------------------------------------------------------
# Booking queries
# ---------------------------------------------------------------------------

def count_overlapping_bookings(room_id, check_in, check_out):
    row = query(
        """SELECT COUNT(*) AS c FROM bookings
           WHERE room_id = %s AND status = 'confirmed'
             AND NOT (check_out <= %s OR check_in >= %s)""",
        (room_id, check_in, check_out),
        fetch="one",
    )
    return row["c"]


def is_room_available(room_id, check_in, check_out, total_rooms):
    booked = count_overlapping_bookings(room_id, check_in, check_out)
    return booked < total_rooms


def create_booking(user_id, room_id, check_in, check_out, guests, total_price):
    return execute(
        """INSERT INTO bookings (user_id, room_id, check_in, check_out, guests, total_price, status)
           VALUES (%s, %s, %s, %s, %s, %s, 'confirmed')""",
        (user_id, room_id, check_in, check_out, guests, total_price),
    )


def get_bookings_by_user(user_id):
    return query(
        """SELECT bookings.*, rooms.room_type, rooms.image_url, hotels.name AS hotel_name, hotels.city
           FROM bookings
           JOIN rooms ON rooms.id = bookings.room_id
           JOIN hotels ON hotels.id = rooms.hotel_id
           WHERE bookings.user_id = %s
           ORDER BY bookings.created_at DESC""",
        (user_id,),
    )


def get_booking_by_id(booking_id):
    return query(
        """SELECT bookings.*, rooms.room_type, rooms.price_per_night, rooms.total_rooms,
                  hotels.name AS hotel_name
           FROM bookings
           JOIN rooms ON rooms.id = bookings.room_id
           JOIN hotels ON hotels.id = rooms.hotel_id
           WHERE bookings.id = %s""",
        (booking_id,),
        fetch="one",
    )


def cancel_booking(booking_id):
    execute("UPDATE bookings SET status = 'cancelled' WHERE id = %s", (booking_id,))


def get_all_bookings():
    return query(
        """SELECT bookings.*, users.email AS user_email, users.first_name, users.last_name,
                  rooms.room_type, hotels.name AS hotel_name
           FROM bookings
           JOIN users ON users.id = bookings.user_id
           JOIN rooms ON rooms.id = bookings.room_id
           JOIN hotels ON hotels.id = rooms.hotel_id
           ORDER BY bookings.created_at DESC"""
    )


def get_all_users_with_booking_counts():
    """Every user plus how many bookings they've made, for the admin
    "Manage users" table. LEFT JOIN so users with zero bookings still
    show up (with a count of 0) instead of being dropped."""
    return query(
        """SELECT users.id, users.first_name, users.last_name, users.email, users.role,
                  COUNT(bookings.id) AS booking_count
           FROM users
           LEFT JOIN bookings ON bookings.user_id = users.id
           GROUP BY users.id, users.first_name, users.last_name, users.email, users.role
           ORDER BY users.id ASC"""
    )


def count_admins():
    row = query("SELECT COUNT(*) AS c FROM users WHERE role = 'admin'", fetch="one")
    return row["c"]


def update_user_profile(user_id, first_name, last_name, email, role):
    execute(
        """UPDATE users SET first_name = %s, last_name = %s, email = %s, role = %s
           WHERE id = %s""",
        (first_name.strip(), last_name.strip(), email.lower().strip(), role, user_id),
    )


def delete_user(user_id):
    execute("DELETE FROM users WHERE id = %s", (user_id,))


def get_admin_stats():
    hotels = query("SELECT COUNT(*) AS c FROM hotels", fetch="one")["c"]
    rooms = query("SELECT COUNT(*) AS c FROM rooms", fetch="one")["c"]
    users = query("SELECT COUNT(*) AS c FROM users", fetch="one")["c"]
    bookings = query("SELECT COUNT(*) AS c FROM bookings WHERE status = 'confirmed'", fetch="one")["c"]
    revenue_row = query(
        "SELECT COALESCE(SUM(total_price), 0) AS total FROM bookings WHERE status IN ('confirmed', 'completed')",
        fetch="one",
    )
    return {
        "hotels": hotels,
        "rooms": rooms,
        "users": users,
        "bookings": bookings,
        "revenue": revenue_row["total"],
    }


# ---------------------------------------------------------------------------
# Reviews & ratings
# ---------------------------------------------------------------------------

def get_reviews_for_hotel(hotel_id):
    return query(
        """SELECT reviews.*, users.first_name, users.last_name
           FROM reviews
           JOIN users ON users.id = reviews.user_id
           WHERE reviews.hotel_id = %s
           ORDER BY reviews.created_at DESC""",
        (hotel_id,),
    )


def get_hotel_rating_summary(hotel_id):
    row = query(
        """SELECT COUNT(*) AS review_count, AVG(rating) AS average_rating
           FROM reviews WHERE hotel_id = %s""",
        (hotel_id,),
        fetch="one",
    )
    return {
        "review_count": row["review_count"] or 0,
        "average_rating": float(row["average_rating"]) if row["average_rating"] is not None else None,
    }


def get_user_review_for_hotel(user_id, hotel_id):
    return query(
        "SELECT * FROM reviews WHERE user_id = %s AND hotel_id = %s",
        (user_id, hotel_id),
        fetch="one",
    )


def user_can_review_hotel(user_id, hotel_id):
    """True if the user has a confirmed, already-completed stay at this hotel."""
    row = query(
        """SELECT COUNT(*) AS c
           FROM bookings
           JOIN rooms ON rooms.id = bookings.room_id
           WHERE bookings.user_id = %s AND rooms.hotel_id = %s
             AND bookings.status = 'confirmed' AND bookings.check_out < CURDATE()""",
        (user_id, hotel_id),
        fetch="one",
    )
    return row["c"] > 0


def upsert_review(user_id, hotel_id, rating, comment, booking_id=None):
    """Create the user's review for this hotel, or update it if one already
    exists (one review per user per hotel — see the unique key in schema.sql)."""
    execute(
        """INSERT INTO reviews (user_id, hotel_id, booking_id, rating, comment)
           VALUES (%s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE rating = VALUES(rating), comment = VALUES(comment),
                                   booking_id = COALESCE(VALUES(booking_id), booking_id)""",
        (user_id, hotel_id, booking_id, rating, comment),
    )


def delete_review(review_id, user_id):
    """Delete a review, scoped to its owner so users can't delete others'."""
    execute("DELETE FROM reviews WHERE id = %s AND user_id = %s", (review_id, user_id))
