"""
Database bootstrap script for StayNova.

Creates the database and tables (from sql/schema.sql) and inserts sample
hotels, rooms, and an admin account so the app is usable immediately.

Usage:
    python scripts/init_db.py            # create schema + seed sample data
    python scripts/init_db.py --no-seed  # create schema only
"""
import os
import sys
import argparse

import pymysql

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "root")
MYSQL_DB = os.environ.get("MYSQL_DB", "staynova")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@staynova.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql", "schema.sql")


def run_schema(conn):
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql_script = f.read()

    statements = [s.strip() for s in sql_script.split(";") if s.strip()]
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    conn.commit()
    print("Schema applied.")


def seed_data(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM hotels")
        if cur.fetchone()["c"] > 0:
            print("Sample data already present, skipping seed.")
            return

        hotels = [
            ("The Grand Meridian", "New York", "5th Avenue, Manhattan", 5,
             "A landmark luxury hotel in the heart of Manhattan with skyline views.",
             "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80",
             "Free WiFi, Spa, Gym, Rooftop Bar, Pool"),
            ("Ocean Breeze Resort", "Miami", "Collins Avenue, South Beach", 4,
             "Beachfront resort with private access to South Beach.",
             "https://images.unsplash.com/photo-1571003123894-1f0594d2b5d9?auto=format&fit=crop&w=1200&q=80",
             "Free WiFi, Beach Access, Pool, Bar, Parking"),
            ("Alpine Lodge", "Denver", "Mountain View Road", 4,
             "Cozy mountain lodge minutes from world-class ski slopes.",
             "https://images.unsplash.com/photo-1548704806-074ca7d67f78?auto=format&fit=crop&w=1200&q=80",
             "Free WiFi, Fireplace, Ski Storage, Restaurant"),
            ("Urban Nest Boutique Hotel", "Chicago", "Michigan Avenue", 3,
             "Modern boutique hotel steps from the Magnificent Mile.",
             "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?auto=format&fit=crop&w=1200&q=80",
             "Free WiFi, Gym, Business Center, Bar"),
        ]

        room_templates = [
            ("Standard Room", "Comfortable room with all essential amenities.", 89.00, 2, 10,
             "https://images.unsplash.com/photo-1566665797739-1674de7a421a?auto=format&fit=crop&w=900&q=80"),
            ("Deluxe Room", "Spacious room with premium furnishing and city view.", 149.00, 3, 8,
             "https://images.unsplash.com/photo-1611892440504-42a792e24d32?auto=format&fit=crop&w=900&q=80"),
            ("Executive Suite", "Suite with separate living area and luxury amenities.", 249.00, 4, 4,
             "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=900&q=80"),
        ]

        for hotel in hotels:
            cur.execute(
                """INSERT INTO hotels (name, city, address, star_rating, description, image_url, amenities)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                hotel,
            )
            hotel_id = cur.lastrowid
            for room in room_templates:
                cur.execute(
                    """INSERT INTO rooms (hotel_id, room_type, description, price_per_night, capacity, total_rooms, image_url)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (hotel_id, *room),
                )

        cur.execute("SELECT COUNT(*) AS c FROM users WHERE email = %s", (ADMIN_EMAIL,))
        if cur.fetchone()["c"] == 0:
            cur.execute(
                """INSERT INTO users (first_name, last_name, email, password_hash, role, is_active)
                   VALUES (%s, %s, %s, %s, %s, 1)""",
                ("Site", "Admin", ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD), "admin"),
            )
            print(f"Admin account created -> email: {ADMIN_EMAIL}  password: {ADMIN_PASSWORD}")
            print("IMPORTANT: change this password after first login.")

    conn.commit()
    print("Sample data inserted.")


def main():
    parser = argparse.ArgumentParser(description="Initialize the StayNova database.")
    parser.add_argument("--no-seed", action="store_true", help="Skip inserting sample data.")
    args = parser.parse_args()

    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    try:
        run_schema(conn)
        conn.select_db(MYSQL_DB)
        if not args.no_seed:
            seed_data(conn)
    finally:
        conn.close()

    print("Database ready.")


if __name__ == "__main__":
    main()
