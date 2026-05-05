"""Tests for _classify_client, _pool_days_remaining, and _trend."""

import server


class TestTrend:
    def test_up_when_today_exceeds_avg_by_10pct(self):
        assert server._trend(110, 100) == "up"
        assert server._trend(200, 100) == "up"

    def test_down_when_today_below_avg_by_10pct(self):
        assert server._trend(89, 100) == "down"
        assert server._trend(50, 100) == "down"

    def test_flat_when_within_10pct(self):
        assert server._trend(100, 100) == "flat"
        assert server._trend(95, 100) == "flat"
        assert server._trend(109, 100) == "flat"

    def test_flat_when_avg_is_zero(self):
        assert server._trend(0, 0) == "flat"
        assert server._trend(100, 0) == "flat"

    def test_zero_today_with_nonzero_avg(self):
        assert server._trend(0, 100) == "down"


class TestPoolDaysRemaining:
    def test_normal_case(self):
        data = {"not_contacted": 1000, "sent_today": 100, "avg_sent_7d": 200}
        result = server._pool_days_remaining(data, "Test")
        assert result == 10.0  # 1000 / 100

    def test_uses_avg_when_sent_today_is_zero(self):
        data = {"not_contacted": 1000, "sent_today": 0, "avg_sent_7d": 200}
        result = server._pool_days_remaining(data, "Test")
        assert result == 5.0  # 1000 / 200

    def test_returns_inf_when_no_sending(self):
        data = {"not_contacted": 1000, "sent_today": 0, "avg_sent_7d": 0}
        result = server._pool_days_remaining(data, "Test")
        assert result == float("inf")

    def test_zero_not_contacted(self):
        data = {"not_contacted": 0, "sent_today": 100, "avg_sent_7d": 200}
        result = server._pool_days_remaining(data, "Test")
        assert result == 0.0


class TestClassifyClient:
    """Test _classify_client using factory defaults (pool_days_red=1, pool_days_warn=3)."""

    def _make_data(self, **overrides):
        """Create a baseline healthy client data dict (10d runway, low bounce)."""
        base = {
            "active_campaigns": 3,
            "total_campaigns": 5,
            "sent_today": 2000,
            "replies_today": 40,
            "opps_today": 4,
            "avg_sent_7d": 1900,
            "reply_rate_today": 2.0,
            "reply_rate_7d": 1.8,
            "bounce_rate": 0.5,
            "not_contacted": 20000,  # 10 days runway at 2000/day
        }
        base.update(overrides)
        return base

    def test_healthy_client_is_green(self):
        data = self._make_data()
        assert server._classify_client(data, "MyPlace") == "green"

    def test_no_active_campaigns_is_amber(self):
        data = self._make_data(active_campaigns=0)
        assert server._classify_client(data, "MyPlace") == "amber"

    # --- Runway is the primary signal ---

    def test_runway_below_one_day_is_red(self):
        # not_contacted=1500, sent=2000 → 0.75 days runway → red
        data = self._make_data(not_contacted=1500)
        assert server._classify_client(data, "MyPlace") == "red"

    def test_runway_between_one_and_three_days_is_amber(self):
        # not_contacted=4000, sent=2000 → 2 days runway → amber
        data = self._make_data(not_contacted=4000)
        assert server._classify_client(data, "MyPlace") == "amber"

    def test_runway_at_three_days_is_green(self):
        # not_contacted=6000, sent=2000 → exactly 3 days → green (boundary, not <3)
        data = self._make_data(not_contacted=6000)
        assert server._classify_client(data, "MyPlace") == "green"

    def test_runway_above_three_days_is_green(self):
        # not_contacted=14000, sent=2000 → 7 days runway → green
        data = self._make_data(not_contacted=14000)
        assert server._classify_client(data, "MyPlace") == "green"

    # --- Regression: zero sent + active campaigns no longer auto-reds when runway is healthy ---

    def test_zero_sent_today_with_healthy_runway_is_green(self):
        # HeyReach/Enavra case: 0 sent today but 7d avg is healthy + plenty of leads → green
        data = self._make_data(sent_today=0, avg_sent_7d=1300, not_contacted=10000)
        # runway = 10000 / 1300 ≈ 7.7 days → green
        assert server._classify_client(data, "MyPlace") == "green"

    def test_low_send_kpi_with_healthy_runway_is_green(self):
        # SmartMatchApp case: only 122 sent today (vs 2000 KPI) but 47d runway → green
        # not_contacted=5841, sent=122 → ~47.9 days → green (no longer red just because KPI low)
        data = self._make_data(sent_today=122, avg_sent_7d=200, not_contacted=5841)
        assert server._classify_client(data, "MyPlace") == "green"

    # --- Bounce rate is still a separate signal ---

    def test_high_bounce_rate_is_red_even_with_healthy_runway(self):
        data = self._make_data(bounce_rate=6.0)
        assert server._classify_client(data, "MyPlace") == "red"

    def test_moderate_bounce_rate_with_healthy_runway_is_amber(self):
        data = self._make_data(bounce_rate=4.0)
        assert server._classify_client(data, "MyPlace") == "amber"

    def test_high_bounce_rate_overrides_amber_runway(self):
        # Even at 2 days runway, 6% bounce is still red, not amber
        data = self._make_data(not_contacted=4000, bounce_rate=6.0)
        assert server._classify_client(data, "MyPlace") == "red"

    # --- Reply rate and KPI ratios no longer drive RAG (regression guards) ---

    def test_low_reply_rate_with_healthy_runway_is_green(self):
        # Reply rate is shown in the card but no longer drives classification
        data = self._make_data(reply_rate_today=0.1)
        assert server._classify_client(data, "MyPlace") == "green"

    def test_below_kpi_send_with_healthy_runway_is_green(self):
        # 50% of KPI used to be red — now it's green if runway is fine
        data = self._make_data(sent_today=900)
        # 20000/900 = 22 days → green
        assert server._classify_client(data, "MyPlace") == "green"


class TestSafeNum:
    """Test _safe_num handles API garbage like '\\N' PostgreSQL NULL markers."""

    def test_normal_int(self):
        assert server._safe_num(42) == 42

    def test_normal_float(self):
        assert server._safe_num(3.14) == 3.14

    def test_none_returns_default(self):
        assert server._safe_num(None) == 0

    def test_backslash_n_returns_default(self):
        assert server._safe_num("\\N") == 0

    def test_empty_string_returns_default(self):
        assert server._safe_num("") == 0

    def test_string_number(self):
        assert server._safe_num("123") == 123

    def test_string_float(self):
        assert server._safe_num("3.14") == 3.14

    def test_garbage_string_returns_default(self):
        assert server._safe_num("not_a_number") == 0

    def test_custom_default(self):
        assert server._safe_num(None, default=-1) == -1

    def test_zero_is_preserved(self):
        assert server._safe_num(0) == 0


class TestFriendlyError:
    """Test _friendly_error maps raw exceptions to human messages."""

    def test_invalid_literal(self):
        msg = server._friendly_error("invalid literal for int() with base 10: '\\\\N'")
        assert "Data format error" in msg

    def test_http_401(self):
        msg = server._friendly_error("HTTP 401: Unauthorized")
        assert "Authentication" in msg or "API key" in msg

    def test_http_429(self):
        msg = server._friendly_error("HTTP 429: Too Many Requests")
        assert "Rate limited" in msg

    def test_timeout(self):
        msg = server._friendly_error("Connection timed out")
        assert "timed out" in msg.lower() or "retry" in msg.lower()

    def test_unknown_error_gets_generic_message(self):
        msg = server._friendly_error("some weird error nobody expected")
        assert "temporarily unavailable" in msg.lower()

    def test_api_key_not_found(self):
        msg = server._friendly_error("API key not found")
        assert "API key" in msg
