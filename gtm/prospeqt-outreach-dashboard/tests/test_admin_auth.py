"""Regression tests for admin authentication functions.

Tests _make_token and _check_admin_auth in server.py.
These functions implement HMAC-SHA256 cookie-based session auth for the admin panel.
"""

import os
import importlib

import pytest

import server


class MockHandler:
    """Minimal mock of BaseHTTPRequestHandler for testing _check_admin_auth."""

    def __init__(self, cookie_header: str = ""):
        self.headers = {"Cookie": cookie_header}


# ---------------------------------------------------------------------------
# _make_token tests
# ---------------------------------------------------------------------------


def test_make_token_returns_hex_string():
    """_make_token returns a 64-character hex string (SHA-256 digest)."""
    result = server._make_token("testpass")
    assert isinstance(result, str)
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_make_token_deterministic():
    """_make_token returns the same token for the same password on every call."""
    result1 = server._make_token("somepassword")
    result2 = server._make_token("somepassword")
    assert result1 == result2


def test_make_token_different_passwords():
    """_make_token returns different tokens for different passwords."""
    token_a = server._make_token("password1")
    token_b = server._make_token("password2")
    assert token_a != token_b


# ---------------------------------------------------------------------------
# _check_admin_auth tests
# ---------------------------------------------------------------------------


def test_check_admin_auth_valid_cookie(monkeypatch):
    """_check_admin_auth returns True when request has cookie with valid token."""
    password = "supersecretadmin"
    monkeypatch.setenv("ADMIN_PASSWORD", password)
    token = server._make_token(password)
    handler = MockHandler(cookie_header=f"admin_token={token}")
    assert server._check_admin_auth(handler) is True


def test_check_admin_auth_no_cookie(monkeypatch):
    """_check_admin_auth returns False when request has no Cookie header."""
    monkeypatch.setenv("ADMIN_PASSWORD", "somepass")
    handler = MockHandler(cookie_header="")
    assert server._check_admin_auth(handler) is False


def test_check_admin_auth_wrong_token(monkeypatch):
    """_check_admin_auth returns False when cookie contains a wrong token."""
    monkeypatch.setenv("ADMIN_PASSWORD", "correctpassword")
    handler = MockHandler(cookie_header="admin_token=badtoken")
    assert server._check_admin_auth(handler) is False


def test_check_admin_auth_no_password_env(monkeypatch):
    """_check_admin_auth returns False when ADMIN_PASSWORD env var is not set."""
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    # Use a technically valid token structure, but no password in env
    token = server._make_token("somepass")
    handler = MockHandler(cookie_header=f"admin_token={token}")
    assert server._check_admin_auth(handler) is False


def test_check_admin_auth_multiple_cookies(monkeypatch):
    """_check_admin_auth parses the correct cookie when multiple cookies are present."""
    password = "multipass"
    monkeypatch.setenv("ADMIN_PASSWORD", password)
    token = server._make_token(password)
    # Simulate a real multi-cookie header
    cookie_header = f"session=abc123; admin_token={token}; theme=dark"
    handler = MockHandler(cookie_header=cookie_header)
    assert server._check_admin_auth(handler) is True
