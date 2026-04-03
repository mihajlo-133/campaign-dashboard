"""Regression tests for backfill race condition fix and thread pool bounding.

BUG-03: Stale backfill results overwriting fresher cache data.
BUG-04: Unbounded threading.Thread() spawning for backfill work.
"""

import inspect
import threading
import server
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def clean_cache_state():
    """Reset shared cache state before and after each test to prevent pollution."""
    clients_to_clean = ["TestClient", "TestClient2", "_test_temp"]
    with server._cache_lock:
        for c in clients_to_clean:
            server._cache_data.pop(c, None)
            server._cache_ts.pop(c, None)
            server._cache_errors.pop(c, None)
            server._cache_generation.pop(c, None)
    yield
    with server._cache_lock:
        for c in clients_to_clean:
            server._cache_data.pop(c, None)
            server._cache_ts.pop(c, None)
            server._cache_errors.pop(c, None)
            server._cache_generation.pop(c, None)


class TestGenerationCounter:
    def test_backfill_discards_stale_write(self):
        """When generation has advanced, backfill results are discarded."""
        # Setup: put client in cache with generation=2
        with server._cache_lock:
            server._cache_data["TestClient"] = {
                "campaigns": [
                    {
                        "id": "c1",
                        "not_contacted": 100,
                        "status": "active",
                        "total_leads": 500,
                        "total_completed": 200,
                        "total_bounced": 50,
                    }
                ],
                "not_contacted": 100,
                "in_progress": 150,
            }
            server._cache_generation["TestClient"] = 2

        # Call backfill with stale generation=1 — should be discarded
        with patch.object(server, "_count_not_contacted_via_api", return_value=999):
            server._backfill_nc("TestClient", ["c1"], "fake-key", generation=1)

        # Verify: not_contacted was NOT updated (still 100, not 999)
        assert server._cache_data["TestClient"]["not_contacted"] == 100

    def test_backfill_writes_when_generation_matches(self):
        """When generation matches, backfill results are applied to cache."""
        with server._cache_lock:
            server._cache_data["TestClient2"] = {
                "campaigns": [
                    {
                        "id": "c1",
                        "not_contacted": 100,
                        "status": "active",
                        "total_leads": 500,
                        "total_completed": 200,
                        "total_bounced": 50,
                    }
                ],
                "not_contacted": 100,
                "in_progress": 150,
                "sent_today": 10,
                "avg_sent_7d": 10,
                "opps_per_day": 1.0,
                "reply_rate": 1.0,
            }
            server._cache_generation["TestClient2"] = 5

        # Call backfill with matching generation=5 — should succeed
        with patch.object(server, "_count_not_contacted_via_api", return_value=50):
            server._backfill_nc("TestClient2", ["c1"], "fake-key", generation=5)

        # Verify: not_contacted was updated
        assert server._cache_data["TestClient2"]["campaigns"][0]["not_contacted"] == 50

    def test_backfill_function_accepts_generation_parameter(self):
        """_backfill_nc signature includes generation parameter."""
        sig = inspect.signature(server._backfill_nc)
        assert "generation" in sig.parameters, "_backfill_nc must accept a 'generation' parameter"

    def test_cache_generation_dict_exists(self):
        """_cache_generation global dict exists on server module."""
        assert hasattr(server, "_cache_generation"), "server must have _cache_generation dict"
        assert isinstance(server._cache_generation, dict)


class TestThreadPoolBounding:
    def test_backfill_pool_exists_with_max_workers_10(self):
        """_backfill_pool ThreadPoolExecutor with max_workers=10 exists."""
        assert hasattr(server, "_backfill_pool"), "server must have _backfill_pool"
        assert server._backfill_pool._max_workers == 10

    def test_no_raw_thread_in_fetch_client_backfill(self):
        """_fetch_client uses pool.submit, not threading.Thread for backfill."""
        source = inspect.getsource(server._fetch_client)
        assert "threading.Thread" not in source, (
            "_fetch_client must not use threading.Thread for backfill; use _backfill_pool.submit"
        )
        assert "_backfill_pool.submit" in source, (
            "_fetch_client must use _backfill_pool.submit for backfill"
        )

    def test_no_raw_thread_in_background_refresh_loop(self):
        """_background_refresh_loop uses pool.submit, not threading.Thread."""
        source = inspect.getsource(server._background_refresh_loop)
        assert "threading.Thread" not in source, (
            "_background_refresh_loop must not use threading.Thread; use _backfill_pool.submit"
        )
        assert "_backfill_pool.submit" in source, (
            "_background_refresh_loop must use _backfill_pool.submit"
        )

    def test_no_raw_thread_in_do_post_refresh(self):
        """do_POST /api/refresh uses pool.submit, not threading.Thread."""
        source = inspect.getsource(server.Handler.do_POST)
        assert "threading.Thread" not in source, (
            "do_POST must not use threading.Thread for refresh; use _backfill_pool.submit"
        )
        assert "_backfill_pool.submit" in source, (
            "do_POST must use _backfill_pool.submit for refresh"
        )
