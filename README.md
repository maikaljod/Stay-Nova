# StayNova

StayNova is a secure hotel booking web application built with Flask, MySQL
(via PyMySQL), and server-rendered HTML/CSS/JS (Jinja2 templates).

## Features

- User registration & login with hashed passwords, account lockout after
  repeated failed attempts, and rate-limited login endpoint
- CSRF protection on every form (Flask-WTF)
- Secure session cookies (HttpOnly, SameSite) and security response headers
- Hotel search/browse, hotel detail pages, room booking with availability
  checks and date validation
- User dashboard with booking history and cancellation
- Admin panel to manage hotels, rooms, and view all bookings
- Modern, responsive UI (no external CSS framework, single stylesheet)

## Project structure

```
app/                Flask application package
  auth/              login, register, logout, password change
  main/              home page, hotel search/detail
  booking/           booking flow, dashboard
  admin/             admin dashboard + hotel/room management
  __init__.py        application factory
  db.py              PyMySQL connection helper (parameterized queries)
  models.py          data-access functions + Flask-Login User wrapper
  forms.py           WTForms definitions with validation
  security.py        admin_required decorator
instance/            local-only overrides (not committed)
scripts/init_db.py   creates the database/tables and seeds sample data
sql/schema.sql       MySQL schema (users, hotels, rooms, bookings)
static/              css/js assets
templates/           Jinja2 templates
test/test.py         smoke tests
config.py            environment-driven configuration
run.py               application entry point
```

## Setup

1. **Create a virtual environment and install dependencies**

   ```bash
   python -m venv venv
   venv\Scripts\activate        # Windows
   pip install -r requirements.txt
   ```

2. **Configure environment variables**

   Copy `.env.example` to `.env` and adjust if needed. Defaults already match
   MySQL Workbench's local credentials (`root` / `root`):

   ```
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=root
   MYSQL_DB=staynova
   ```

   Set a real `SECRET_KEY` for anything beyond local testing.

3. **Create the database and seed sample data**

   Make sure MySQL (e.g. via MySQL Workbench / MySQL Server) is running, then:

   ```bash
   python scripts/init_db.py
   ```

   This creates the `staynova` database, all tables, four sample hotels with
   rooms, and an admin account (`admin@staynova.com` / `Admin@12345` by
   default — printed to the console, change it after first login).

4. **Run the app**

   ```bash
   python run.py
   ```

   Visit http://127.0.0.1:5000

## Security notes

- Passwords are hashed with Werkzeug's `generate_password_hash` (never
  stored in plain text).
- All SQL queries use parameterized placeholders — no string interpolation
  of user input.
- CSRF tokens are required on every state-changing form.
- Login is rate-limited (10/minute per IP) and accounts lock for 15 minutes
  after 5 consecutive failed attempts.
- Session cookies are HttpOnly/SameSite=Lax; set `SESSION_COOKIE_SECURE=true`
  once the app is served over HTTPS.
- Generic error messages are used on login/registration so the app doesn't
  reveal whether a given email is registered.

## Tests

```bash
pytest test/test.py
```
