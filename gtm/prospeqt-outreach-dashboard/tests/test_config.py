"""Tests for validate_config, get_client_thresholds, and get_client_kpi."""

import server


class TestValidateConfig:
    def test_valid_config_passes(self, mock_config):
        is_valid, errors = server.validate_config(mock_config)
        assert is_valid is True
        assert errors == []

    def test_non_dict_is_invalid(self):
        is_valid, errors = server.validate_config("not a dict")
        assert is_valid is False
        assert "config must be a JSON object" in errors

    def test_non_numeric_threshold_fails(self):
        cfg = {
            "global_thresholds": {"reply_rate_warn": "bad"},
            "clients": {},
        }
        is_valid, errors = server.validate_config(cfg)
        assert is_valid is False
        assert any("reply_rate_warn" in e and "numeric" in e for e in errors)

    def test_warn_must_exceed_red_for_reply_rate(self):
        cfg = {
            "global_thresholds": {
                "reply_rate_warn": 0.3,  # warn < red = invalid
                "reply_rate_red": 0.5,
            },
            "clients": {},
        }
        is_valid, errors = server.validate_config(cfg)
        assert is_valid is False
        assert any("reply_rate_warn must be > reply_rate_red" in e for e in errors)

    def test_bounce_warn_must_be_less_than_red(self):
        cfg = {
            "global_thresholds": {
                "bounce_rate_warn": 5.0,  # warn >= red = invalid
                "bounce_rate_red": 5.0,
            },
            "clients": {},
        }
        is_valid, errors = server.validate_config(cfg)
        assert is_valid is False
        assert any("bounce_rate_warn must be < bounce_rate_red" in e for e in errors)

    def test_pool_days_warn_must_exceed_red(self):
        cfg = {
            "global_thresholds": {
                "pool_days_warn": 2,
                "pool_days_red": 3,
            },
            "clients": {},
        }
        is_valid, errors = server.validate_config(cfg)
        assert is_valid is False
        assert any("pool_days_warn must be > pool_days_red" in e for e in errors)

    def test_client_non_numeric_kpi_fails(self):
        cfg = {
            "global_thresholds": {},
            "clients": {
                "BadClient": {"sent": "not_a_number"},
            },
        }
        is_valid, errors = server.validate_config(cfg)
        assert is_valid is False
        assert any("BadClient" in e and "sent" in e for e in errors)

    def test_client_threshold_non_numeric_fails(self):
        cfg = {
            "global_thresholds": {},
            "clients": {
                "BadClient": {"thresholds": {"reply_rate_warn": "bad"}},
            },
        }
        is_valid, errors = server.validate_config(cfg)
        assert is_valid is False
        assert any("BadClient" in e and "reply_rate_warn" in e for e in errors)

    def test_empty_config_is_valid(self):
        """Minimal empty config with no thresholds/clients is valid."""
        is_valid, errors = server.validate_config({})
        assert is_valid is True

    def test_clients_not_dict_fails(self):
        cfg = {"global_thresholds": {}, "clients": "not_dict"}
        is_valid, errors = server.validate_config(cfg)
        assert is_valid is False
        assert any("clients must be an object" in e for e in errors)


class TestGetClientThresholds:
    def test_factory_defaults_returned_for_unknown_client(self):
        thresholds = server.get_client_thresholds("NonExistentClient")
        assert thresholds["reply_rate_warn"] == server.FACTORY_THRESHOLDS["reply_rate_warn"]
        assert thresholds["pool_days_red"] == server.FACTORY_THRESHOLDS["pool_days_red"]

    def test_all_factory_keys_present(self):
        thresholds = server.get_client_thresholds("MyPlace")
        for key in server.FACTORY_THRESHOLDS:
            assert key in thresholds


class TestGetClientKpi:
    def test_known_client_returns_kpi(self):
        kpi = server.get_client_kpi("MyPlace")
        assert "sent" in kpi
        assert "opps_per_day" in kpi

    def test_unknown_client_returns_empty(self):
        kpi = server.get_client_kpi("NonExistentClient")
        assert kpi == {}
