"""Smoke tests. DB-dependent tests auto-skip if MySQL isn't reachable."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
import pytest

from app import create_app
from config import Config


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


def _db_available():
    try:
        conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            db=Config.MYSQL_DB,
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()
needs_db = pytest.mark.skipif(not DB_AVAILABLE, reason="MySQL not reachable / staynova DB not initialized")


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.test_client() as client:
        yield client


def test_login_page_loads(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert b"Log in" in response.data or b"Log In" in response.data


def test_register_page_loads(client):
    response = client.get("/auth/register")
    assert response.status_code == 200


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code in (301, 302)
    assert "/auth/login" in response.headers.get("Location", "")


def test_admin_requires_login(client):
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code in (301, 302)


@needs_db
def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"StayNova" in response.data


def test_404_page(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404


@needs_db
def test_hotels_listing_loads(client):
    response = client.get("/hotels")
    assert response.status_code == 200
