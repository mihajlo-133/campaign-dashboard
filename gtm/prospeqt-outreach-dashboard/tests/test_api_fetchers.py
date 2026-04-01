"""Tests for fetch_instantly_data and fetch_emailbison_data with monkeypatched HTTP."""

import server


class TestFetchInstantlyData:
    """Test Instantly fetcher with monkeypatched HTTP calls."""

    def _patch_http(self, monkeypatch, campaigns=None, analytics=None, daily=None, steps=None, nc_count=0):
        """Set up monkeypatched HTTP responses for Instantly API."""
        campaigns = campaigns or []
        analytics = analytics or []
        daily = daily or []
        steps = steps or []

        def mock_http_get(url, headers, timeout=15):
            if "/campaigns/analytics/daily" in url:
                return daily
            if "/campaigns/analytics/steps" in url:
                return steps
            if "/campaigns/analytics" in url:
                return analytics
            if "/campaigns" in url:
                return {"items": campaigns, "next_starting_after": None}
            return None

        def mock_http_post(url, headers, body, timeout=15):
            if "/leads/list" in url:
                return {"items": [{}] * nc_count, "next_starting_after": None}
            return None

        monkeypatch.setattr(server, "_http_get", mock_http_get)
        monkeypatch.setattr(server, "_http_post", mock_http_post)
        # Disable step cache so our mock is always hit
        monkeypatch.setattr(server, "STEP_CACHE_TTL", 0)

    def test_basic_parsing(self, monkeypatch):
        campaigns = [
            {"id": "c1", "name": "Camp A", "status": 1},
        ]
        analytics = [
            {
                "campaign_id": "c1",
                "emails_sent_count": 1000,
                "reply_count": 20,
                "total_opportunities": 5,
                "leads_count": 500,
                "contacted_count": 400,
                "bounced_count": 10,
                "completed_count": 380,
            },
        ]
        daily = [
            {"date": "2026-04-01", "sent": 100, "replies": 3, "opportunities": 1},
        ]

        self._patch_http(monkeypatch, campaigns=campaigns, analytics=analytics, daily=daily, nc_count=50)

        result = server.fetch_instantly_data("TestClient", "fake-key")

        assert result["platform"] == "instantly"
        assert result["active_campaigns"] == 1
        assert result["total_campaigns"] == 1
        assert result["sent_today"] == 100
        assert result["replies_today"] == 3
        assert result["opps_today"] == 1
        assert result["total_sent"] == 1000
        assert result["total_replies"] == 20
        assert result["total_opps"] == 5
        assert result["not_contacted"] == 50
        assert result["reply_rate_today"] == 3.0  # 3/100*100
        assert isinstance(result["campaigns"], list)
        assert len(result["campaigns"]) == 1

    def test_empty_responses(self, monkeypatch):
        self._patch_http(monkeypatch)

        result = server.fetch_instantly_data("TestClient", "fake-key")

        assert result["active_campaigns"] == 0
        assert result["total_campaigns"] == 0
        assert result["sent_today"] == 0
        assert result["reply_rate_today"] == 0.0
        assert result["campaigns"] == []

    def test_step_analytics_parsing(self, monkeypatch):
        campaigns = [{"id": "c1", "name": "Camp A", "status": 1}]
        analytics = [{"campaign_id": "c1", "emails_sent_count": 500, "reply_count": 10, "total_opportunities": 2, "leads_count": 200, "contacted_count": 150, "bounced_count": 5, "completed_count": 140}]
        steps = [
            {"step": 0, "sent": 300},
            {"step": 1, "sent": 150},
            {"step": 2, "sent": 50},
            {"step": None, "sent": 999},  # garbage row — should be filtered
        ]

        self._patch_http(monkeypatch, campaigns=campaigns, analytics=analytics, steps=steps)

        result = server.fetch_instantly_data("TestClient", "fake-key")
        assert result["first_touch_sent"] == 300
        assert result["followup_sent"] == 200  # 150 + 50


class TestFetchEmailBisonData:
    """Test EmailBison fetcher with monkeypatched HTTP calls."""

    def _patch_http(self, monkeypatch, campaigns=None, stats_7d=None, stats_today=None, nc_total=0):
        campaigns = campaigns or []
        stats_7d = stats_7d or []
        stats_today = stats_today or []

        def mock_http_get(url, headers, timeout=15):
            if "/campaigns?" in url or url.endswith("/campaigns"):
                return {"data": campaigns}
            if "/campaign-events/stats" in url:
                # Distinguish 7d vs today by date params
                if "start_date=" in url:
                    # If start and end are the same date, it's "today" query
                    parts = url.split("start_date=")[1]
                    start = parts.split("&")[0]
                    end_part = url.split("end_date=")[1] if "end_date=" in url else ""
                    end = end_part.split("&")[0]
                    if start == end:
                        return {"data": stats_today}
                    return {"data": stats_7d}
                return {"data": stats_7d}
            if "/leads?" in url:
                return {"data": [], "meta": {"total": nc_total}}
            return None

        def mock_http_post(url, headers, body, timeout=15):
            if "/campaigns/" in url and "/stats" in url:
                return {"data": {"emails_sent": 100, "unique_replies_per_contact": 5, "bounced": 2, "interested": 1}}
            return None

        monkeypatch.setattr(server, "_http_get", mock_http_get)
        monkeypatch.setattr(server, "_http_post", mock_http_post)

    def test_basic_parsing(self, monkeypatch):
        campaigns = [
            {"id": 1, "name": "EB Camp", "status": "Active"},
        ]
        stats_7d = [
            {"label": "Sent", "dates": [["2026-03-26", 100], ["2026-03-27", 110]]},
            {"label": "Replied", "dates": [["2026-03-26", 3], ["2026-03-27", 4]]},
            {"label": "Interested", "dates": [["2026-03-26", 1], ["2026-03-27", 1]]},
            {"label": "Bounced", "dates": [["2026-03-26", 1], ["2026-03-27", 0]]},
        ]
        stats_today = [
            {"label": "Sent", "dates": [["2026-04-01", 50]]},
            {"label": "Replied", "dates": [["2026-04-01", 2]]},
            {"label": "Interested", "dates": [["2026-04-01", 1]]},
        ]

        self._patch_http(monkeypatch, campaigns=campaigns, stats_7d=stats_7d, stats_today=stats_today, nc_total=200)

        result = server.fetch_emailbison_data("TestClient", "fake-key")

        assert result["platform"] == "emailbison"
        assert result["active_campaigns"] == 1
        assert result["sent_today"] == 50
        assert result["replies_today"] == 2
        assert result["opps_today"] == 1
        assert result["not_contacted"] == 200
        assert isinstance(result["campaigns"], list)

    def test_empty_responses(self, monkeypatch):
        self._patch_http(monkeypatch)

        result = server.fetch_emailbison_data("TestClient", "fake-key")

        assert result["active_campaigns"] == 0
        assert result["sent_today"] == 0
        assert result["reply_rate_today"] == 0.0

    def test_none_http_response_handled(self, monkeypatch):
        """When _http_get returns None, fetcher should not crash."""
        def mock_http_get(url, headers, timeout=15):
            return None

        def mock_http_post(url, headers, body, timeout=15):
            return None

        monkeypatch.setattr(server, "_http_get", mock_http_get)
        monkeypatch.setattr(server, "_http_post", mock_http_post)

        result = server.fetch_emailbison_data("TestClient", "fake-key")
        assert result["platform"] == "emailbison"
        assert result["sent_today"] == 0


class TestEbParseEventsTimeseries:
    def test_parses_standard_series(self):
        series = [
            {"label": "Sent", "dates": [["2026-03-26", 100], ["2026-03-27", 200]]},
            {"label": "Replied", "dates": [["2026-03-26", 5], ["2026-03-27", 8]]},
            {"label": "Bounced", "dates": [["2026-03-26", 1], ["2026-03-27", 2]]},
        ]
        result = server._eb_parse_events_timeseries(series)
        assert result["sent"] == 300
        assert result["replied"] == 13
        assert result["bounced"] == 3

    def test_empty_series(self):
        result = server._eb_parse_events_timeseries([])
        assert result == {}

    def test_unknown_labels_ignored(self):
        series = [
            {"label": "UnknownMetric", "dates": [["2026-03-26", 999]]},
            {"label": "Sent", "dates": [["2026-03-26", 50]]},
        ]
        result = server._eb_parse_events_timeseries(series)
        assert "sent" in result
        assert result["sent"] == 50
        assert len(result) == 1
