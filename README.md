# StayNova

StayNova is a secure hotel booking web application built with Flask, MySQL
(via PyMySQL), and server-rendered HTML/CSS/JS (Jinja2 templates).

## Features

- User registration & login with hashed passwords, account lockout after
  repeated failed attempts, and rate-limited login endpoint
- Email verification on signup (signed, expiring token; resend flow)
- Self-service password reset via emailed, single-use, expiring link
- Optional two-factor authentication (TOTP, compatible with Google
  Authenticator / Authy / 1Password) with QR-code enrollment
- Rate limiting on all sensitive account endpoints (login, register,
  password reset, resend verification, 2FA)
- CSRF protection on every form (Flask-WTF)
- Secure session cookies (HttpOnly, SameSite) and security response headers
- Hotel search/browse, hotel detail pages, room booking with availability
  checks and date validation
- Reviews & ratings: guests who completed a stay can rate (1-5) and review
  a hotel; hotel pages show the average rating and every review
- Booking history split into current (upcoming/active) and past bookings,
  with cancellation for upcoming stays and a downloadable confirmation
  for any booking
- Admin panel to manage hotels, rooms, and view all bookings
- Modern, responsive UI (no external CSS framework, single stylesheet)

## Responsive breakpoints

| Device        | Screen width  |
| ------------- | ------------: |
| Mobile        |   up to 430px |
| Tablet        |    431-1023px |
| Laptop        |   1024-1439px |
| Desktop       |   1440-1919px |
| Large desktop |       1920px+ |

Base styles in `static/css/style.css` are written desktop-first (targeting
Laptop and up); `@media (max-width: ...)` rules scale the layout down for
Tablet and Mobile, and `@media (min-width: 1440px)` / `(min-width: 1920px)`
rules widen the container and grids back up for Desktop and Large desktop.
See the comment block at the top of `style.css` for the exact scale.

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
  email_utils.py     outgoing email helper (dev outbox fallback)
  tokens.py          signed, expiring tokens (verify email / reset password)
  twofactor.py       TOTP secret generation, QR code, code verification
instance/            local-only overrides (not committed); outbox/ holds
                     dev-mode emails when MAIL_SERVER isn't configured
scripts/init_db.py   creates the database/tables and seeds sample data
sql/schema.sql       MySQL schema (users, hotels, rooms, bookings, reviews)
sql/migrations/      incremental ALTER TABLE scripts for existing databases
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

   If you already had a StayNova database from before a given feature was
   added, apply the matching script(s) in `sql/migrations/` once instead
   (e.g. `mysql -u root -p staynova < sql/migrations/0002_reviews.sql`).

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
  after 5 consecutive failed attempts. Registration, password reset, resend
  verification, and 2FA code checks are rate-limited too.
- Session cookies are HttpOnly/SameSite=Lax; set `SESSION_COOKIE_SECURE=true`
  once the app is served over HTTPS.
- Generic error messages are used on login/registration/forgot-password so
  the app doesn't reveal whether a given email is registered.
- Email verification, password-reset links, and 2FA:
  - New accounts must verify their email (signed `itsdangerous` token, 24h
    expiry) before they can log in. Accounts that existed before this
    feature was added are grandfathered in via the migration script.
  - Password reset links are signed + expiring (1h) *and* single-use — a
    hash of the token is stored server-side and cleared the moment it's
    used, so a link can't be replayed even before it expires.
  - Two-factor authentication is TOTP-based (RFC 6238) and optional
    per-account; the shared secret is never shown again after setup, and
    disabling it requires re-entering the current password.
  - In development, no real mail server is required — verification and
    reset emails are written to `instance/outbox/` instead of being sent
    (see `.env.example` for `MAIL_SERVER` and friends to send real email).
- Password hashing uses an explicit, configurable method (`PASSWORD_HASH_METHOD`
  in `.env`, default `scrypt`) via a single `hash_password()` helper in
  `app/models.py`, rather than relying on whatever Werkzeug happens to
  default to.
- Redirects: any `next=` query parameter (used after login/2FA to send you
  back where you came from) is validated with `_is_safe_redirect_target()`
  before being used. A naive `startswith("/")` check would still let
  `//evil.com` through, since browsers treat that as a protocol-relative
  external URL — it's parsed and rejected unless it has no scheme/host.
- Session management: the Flask session is cleared right before a user
  becomes fully authenticated (normal login and after 2FA), so no stale
  data (like an abandoned 2FA-setup secret) carries into the new session.
  `session.permanent` follows the "remember me" checkbox, and logout clears
  the session outright.
- Form handling: CSRF token failures (expired/duplicate form submissions)
  are caught by a dedicated error handler that redirects back with a
  friendly message instead of showing a raw 400 error page. Forms also
  flash a single top-level notice when server-side validation fails, in
  addition to the existing per-field error messages.
- Reviews are gated server-side: only a user with a confirmed, already
  completed stay at a hotel can post one (checked again on submit, not
  just before showing the form), and it's one review per user per hotel
  (a resubmission updates the existing review rather than creating a
  duplicate).

## Tests

```bash
pytest test/test.py
```
