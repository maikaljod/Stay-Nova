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


def search_hotels(city=None, guests=None):
    sql = "SELECT * FROM hotels WHERE 1=1"
    params = []
    if city:
        sql += " AND city LIKE %s"
        params.append(f"%{city}%")
    sql += " ORDER BY name"
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
