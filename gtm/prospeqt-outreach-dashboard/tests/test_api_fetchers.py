"""Tests for fetch_instantly_data and fetch_emailbison_data with monkeypatched HTTP."""

import server
from datetime import datetime
from zoneinfo import ZoneInfo

TODAY_STR = datetime.now(ZoneInfo("America/New_York")).date().isoformat()


class TestFetchInstantlyData:
    """Test Instantly fetcher with monkeypatched HTTP calls."""

    def _patch_http(self, monkeypatch, campaigns=None, analytics=None, daily=None, campaign_daily=None, nc_count=0):
        """Set up monkeypatched HTTP responses for Instantly API."""
        campaigns = campaigns or []
        analytics = analytics or []
        daily = daily or []
        campaign_daily = campaign_daily or {}

        def mock_http_get(url, headers, timeout=15):
            if "/campaigns/analytics/daily" in url:
                # Per-campaign daily: ?campaign_id=X in query string
                for camp_id, data in campaign_daily.items():
                    if f"campaign_id={camp_id}" in url:
                        return data
                return daily
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
                "new_leads_contacted_count": 400,
                "bounced_count": 10,
                "completed_count": 380,
            },
        ]
        daily = [
            {"date": TODAY_STR, "sent": 100, "replies": 3, "opportunities": 1},
        ]
        # Per-campaign daily data (sent_today is aggregated from these)
        campaign_daily = {
            "c1": [{"date": TODAY_STR, "sent": 100, "new_leads_contacted": 60, "replies": 3, "opportunities": 1}],
        }

        self._patch_http(monkeypatch, campaigns=campaigns, analytics=analytics, daily=daily, campaign_daily=campaign_daily)

        result = server.fetch_instantly_data("TestClient", "fake-key")

        assert result["platform"] == "instantly"
        assert result["active_campaigns"] == 1
        assert result["total_campaigns"] == 1
        assert result["sent_today"] == 100
        assert result["replies_today"] == 3
        assert result["opps_today"] == 1
        # not_contacted = leads_count(500) - new_leads_contacted_count(400) = 100
        assert result["not_contacted"] == 100
        assert result["reply_rate_today"] == 3.0  # 3/100*100
        assert isinstance(result["campaigns"], list)
        assert len(result["campaigns"]) == 1

        # New fields present
        assert "first_touch_today" in result
        assert "followup_today" in result
        assert "reply_rate_7d" in result
        assert "bounce_rate" in result
        assert "in_progress" in result

        # Removed fields absent
        assert "total_sent" not in result
        assert "total_replies" not in result
        assert "total_opps" not in result
        assert "first_touch_sent" not in result
        assert "followup_sent" not in result
        assert "reply_rate_all" not in result
        assert "active_sent" not in result
        assert "active_replies" not in result
        assert "active_bounced" not in result
        assert "active_opps" not in result

    def test_empty_responses(self, monkeypatch):
        self._patch_http(monkeypatch)

        result = server.fetch_instantly_data("TestClient", "fake-key")

        assert result["active_campaigns"] == 0
        assert result["total_campaigns"] == 0
        assert result["sent_today"] == 0
        assert result["reply_rate_today"] == 0.0
        assert result["campaigns"] == []

    def test_active_campaign_filtering(self, monkeypatch):
        """Bounce rate uses only active campaigns; paused campaigns excluded."""
        campaigns = [
            {"id": "active1", "name": "Active Camp", "status": 1},
            {"id": "paused1", "name": "Paused Camp", "status": 3},
        ]
        analytics = [
            {
                "campaign_id": "active1",
                "emails_sent_count": 1000,
                "reply_count": 20,
                "total_opportunities": 5,
                "leads_count": 400,
                "new_leads_contacted_count": 300,
                "bounced_count": 10,
                "completed_count": 280,
            },
            {
                "campaign_id": "paused1",
                "emails_sent_count": 5000,
                "reply_count": 10,
                "total_opportunities": 2,
                "leads_count": 2000,
                "new_leads_contacted_count": 1800,
                "bounced_count": 500,  # big number — should NOT inflate active bounce_rate
                "completed_count": 1700,
            },
        ]

        self._patch_http(monkeypatch, campaigns=campaigns, analytics=analytics)

        result = server.fetch_instantly_data("TestClient", "fake-key")

        # active_campaigns count should reflect only active (status=1)
        assert result["active_campaigns"] == 1

        # bounce_rate uses active only — 10/1000 = 1.0%
        assert result["bounce_rate"] == 1.0

        # in_progress = contacted - completed - bounced (active only)
        # active contacted=300, completed=280, bounced=10
        assert result["in_progress"] == 10  # 300 - 280 - 10
        # not_contacted = leads - new_leads_contacted (active only) = 400 - 300 = 100
        assert result["not_contacted"] == 100

        # Removed active_* top-level fields
        assert "active_sent" not in result
        assert "active_replies" not in result
        assert "active_bounced" not in result
        assert "active_opps" not in result
        assert "reply_rate_all" not in result

    def test_per_campaign_daily_data(self, monkeypatch):
        """Per-campaign sent_today, first_touch, followups are populated."""
        campaigns = [
            {"id": "c1", "name": "Camp A", "status": 1},
            {"id": "c2", "name": "Camp B", "status": 1},
        ]
        analytics = [
            {"campaign_id": "c1", "emails_sent_count": 500, "reply_count": 10, "total_opportunities": 2, "leads_count": 200, "new_leads_contacted_count": 150, "bounced_count": 5, "completed_count": 140},
            {"campaign_id": "c2", "emails_sent_count": 300, "reply_count": 6, "total_opportunities": 1, "leads_count": 120, "new_leads_contacted_count": 90, "bounced_count": 3, "completed_count": 85},
        ]
        # Aggregate daily (used for sent_today totals)
        daily = [
            {"date": TODAY_STR, "sent": 80, "replies": 4, "opportunities": 1},
        ]
        # Per-campaign daily breakdowns (first_touch = step 0, followups = steps 1+)
        campaign_daily = {
            "c1": [{"date": TODAY_STR, "step": 0, "sent": 30}, {"date": TODAY_STR, "step": 1, "sent": 20}],
            "c2": [{"date": TODAY_STR, "step": 0, "sent": 20}, {"date": TODAY_STR, "step": 1, "sent": 10}],
        }

        self._patch_http(monkeypatch, campaigns=campaigns, analytics=analytics, daily=daily, campaign_daily=campaign_daily)

        result = server.fetch_instantly_data("TestClient", "fake-key")

        # Campaigns list should exist
        assert isinstance(result["campaigns"], list)
        assert len(result["campaigns"]) == 2

        # Each campaign should have the new fields
        for camp in result["campaigns"]:
            assert "sent_today" in camp
            assert "first_touch" in camp
            assert "followups" in camp
            assert "replies_today" in camp
            assert "opps_today" in camp
            assert "reply_rate" in camp
            assert "not_contacted" in camp
            assert "in_progress" in camp
            assert "total_sent" in camp
            assert "total_bounced" in camp

            # Old fields removed from campaigns
            assert "sent" not in camp
            assert "replies" not in camp
            assert "leads" not in camp
            assert "completed" not in camp
            assert "bounced" not in camp
            assert "opps" not in camp

        # first_touch_today and followup_today aggregated at client level
        assert "first_touch_today" in result
        assert "followup_today" in result


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
            {"label": "Sent", "dates": [[TODAY_STR, 50]]},
            {"label": "Replied", "dates": [[TODAY_STR, 2]]},
            {"label": "Interested", "dates": [[TODAY_STR, 1]]},
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

        # EmailBison has first_touch_today and followup_today as 0
        assert result["first_touch_today"] == 0
        assert result["followup_today"] == 0

        # New fields present
        assert "reply_rate_today" in result
        assert "reply_rate_7d" in result
        assert "bounce_rate" in result
        assert "in_progress" in result

        # Removed fields absent
        assert "first_touch_sent" not in result
        assert "followup_sent" not in result
        assert "reply_rate_all" not in result
        assert "active_sent" not in result
        assert "opps_7d_total" not in result

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

    def test_campaign_fields_new_structure(self, monkeypatch):
        """EmailBison campaign entries use new field names."""
        campaigns = [
            {"id": 1, "name": "EB Camp A", "status": "Active"},
            {"id": 2, "name": "EB Camp B", "status": "Active"},
        ]
        stats_today = [
            {"label": "Sent", "dates": [[TODAY_STR, 80]]},
            {"label": "Replied", "dates": [[TODAY_STR, 3]]},
            {"label": "Interested", "dates": [[TODAY_STR, 1]]},
        ]

        self._patch_http(monkeypatch, campaigns=campaigns, stats_today=stats_today, nc_total=500)

        result = server.fetch_emailbison_data("TestClient", "fake-key")

        assert isinstance(result["campaigns"], list)
        for camp in result["campaigns"]:
            assert "sent_today" in camp
            assert "replies_today" in camp
            assert "opps_today" in camp
            assert "reply_rate" in camp
            assert "total_sent" in camp
            assert "total_bounced" in camp
            assert "first_touch" in camp
            assert "followups" in camp

            # Old fields removed
            assert "sent" not in camp
            assert "replies" not in camp
            assert "bounced" not in camp
            assert "opps" not in camp


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
