"""Smoke tests for dashboard and health routes."""
import pytest
from httpx import ASGITransport, AsyncClient


async def test_health_check(mock_env):
    from app.main import create_app
    from app.services import workspace as ws_module

    ws_module.load_from_env()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_dashboard_returns_html(mock_env):
    from app.main import create_app
    from app.services import workspace as ws_module

    ws_module.load_from_env()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


async def test_nonexistent_route_returns_404(mock_env):
    from app.main import create_app
    from app.services import workspace as ws_module

    ws_module.load_from_env()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/nonexistent")
    assert response.status_code == 404
