"""Shared pytest fixtures for prospeqt-outreach-dashboard tests."""

import json
import sys
from pathlib import Path

import pytest

# Ensure server module is importable
_PROJECT_DIR = Path(__file__).parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_api_data():
    """Full mock API data matching /api/data response shape."""
    return json.loads((FIXTURES_DIR / "mock_api_data.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_client_data(mock_api_data):
    """A single client's data dict (MyPlace — healthy/green)."""
    return mock_api_data["MyPlace"]


@pytest.fixture
def mock_config():
    """A valid dashboard config dict for testing config validation."""
    return {
        "version": 1,
        "updated_at": "2026-04-01T00:00:00Z",
        "global_thresholds": {
            "reply_rate_warn": 1.0,
            "reply_rate_red": 0.5,
            "sent_pct_warn": 0.8,
            "sent_pct_red": 0.5,
            "bounce_rate_warn": 3.0,
            "bounce_rate_red": 5.0,
            "opps_pct_warn": 0.5,
            "pool_days_warn": 3,
            "pool_days_red": 1,
        },
        "clients": {
            "TestClient": {
                "sent": 2000,
                "not_contacted": 1000,
                "opps_per_day": 4.0,
                "reply_rate": 1.5,
            }
        },
    }
