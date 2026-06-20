"""Thin pymysql data-access layer.

We use raw pymysql (per the project requirements) rather than an ORM.
All queries use parameterized placeholders (%s) — never string-format
user input into SQL — to prevent SQL injection.
"""
import pymysql
import pymysql.cursors
from flask import current_app, g


def get_db():
    """Return a request-scoped pymysql connection, opening one if needed."""
    if "db" not in g:
        cfg = current_app.config
        g.db = pymysql.connect(
            host=cfg["MYSQL_HOST"],
            port=cfg["MYSQL_PORT"],
            user=cfg["MYSQL_USER"],
            password=cfg["MYSQL_PASSWORD"],
            db=cfg["MYSQL_DB"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def query(sql, params=None, fetch="all"):
    """Run a SELECT and return rows.

    fetch: 'all' | 'one'
    """
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        if fetch == "one":
            return cur.fetchone()
        return cur.fetchall()


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE, commit, and return the cursor's lastrowid."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
    conn.commit()
    return cur.lastrowid


def execute_many(sql, seq_of_params):
    conn = get_db()
    with conn.cursor() as cur:
        cur.executemany(sql, seq_of_params)
    conn.commit()
