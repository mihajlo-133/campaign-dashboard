"""
Multi-Client Email Campaign Dashboard

Real-time performance monitor for 6 Instantly and 2 EmailBison workspaces.
Fetches live data, caches for 5 minutes, serves a single-page dashboard.

Usage:
  python gtm/scripts/client_dashboard.py             # port 8060
  python gtm/scripts/client_dashboard.py --port 8061
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants — edit these to change behavior
# ---------------------------------------------------------------------------

PORT = 8060
CACHE_TTL = 300          # seconds (5 minutes)
REQUEST_TIMEOUT = 15     # seconds per API call
AUTO_REFRESH_MS = 300000 # ms — must match CACHE_TTL

BASE_DIR = Path(__file__).parent.parent.parent  # repo root

# KPI targets per client (daily)
# Keys must match CLIENTS dict keys exactly
KPI_TARGETS = {
    "MyPlace":          {"sent": 2000,  "not_contacted": 1000,  "opps_per_day": 4.0,  "reply_rate": 1.5},
    "SwishFunding":     {"sent": 10000, "not_contacted": 10000, "opps_per_day": 9.0,  "reply_rate": 1.3},
    "SmartMatchApp":    {"sent": 2000,  "not_contacted": 2000,  "opps_per_day": 2.0,  "reply_rate": 1.5},
    "HeyReach":         {"sent": 2000,  "not_contacted": 2000,  "opps_per_day": 2.0,  "reply_rate": 1.5},
    "Kayse":            {"sent": 2000,  "not_contacted": 2000,  "opps_per_day": 2.0,  "reply_rate": 1.5},
    "Prosperly":        {"sent": 2000,  "not_contacted": 2000,  "opps_per_day": 2.0,  "reply_rate": 1.5},
    "Enavra":           {"sent": 2000,  "not_contacted": 2000,  "opps_per_day": 2.0,  "reply_rate": 1.5},
    "RankZero":         {"sent": 2000,  "not_contacted": 2000,  "opps_per_day": 2.0,  "reply_rate": 1.5},
    "SwishFunding (EB)":{"sent": 2000,  "not_contacted": 2000,  "opps_per_day": 2.0,  "reply_rate": 1.5},
}

# Alert thresholds (aligned with client_dashboard_spec.md section 7)
REPLY_RATE_WARN   = 1.0   # pct — below this → amber
REPLY_RATE_RED    = 0.5   # pct — below this → red
SENT_PCT_WARN     = 0.8   # fraction of KPI — below this → amber
SENT_PCT_RED      = 0.5   # fraction of KPI — below this → red
BOUNCE_RATE_WARN  = 3.0   # pct — above this → amber
BOUNCE_RATE_RED   = 5.0   # pct — above this → red
OPPS_PCT_WARN     = 0.5   # fraction of 7-day avg → amber if today drops below 50%
# Lead pool capacity thresholds are in days (not_contacted / avg_daily_sent)
POOL_DAYS_RED     = 3     # below 3 days of leads → red
POOL_DAYS_WARN    = 7     # below 7 days of leads → amber

# Factory defaults — used as fallback when no config file or env var is present
FACTORY_THRESHOLDS = {
    "reply_rate_warn": REPLY_RATE_WARN,
    "reply_rate_red":  REPLY_RATE_RED,
    "sent_pct_warn":   SENT_PCT_WARN,
    "sent_pct_red":    SENT_PCT_RED,
    "bounce_rate_warn": BOUNCE_RATE_WARN,
    "bounce_rate_red":  BOUNCE_RATE_RED,
    "opps_pct_warn":   OPPS_PCT_WARN,
    "pool_days_warn":  POOL_DAYS_WARN,
    "pool_days_red":   POOL_DAYS_RED,
}

# ---------------------------------------------------------------------------
# Config layer — load/save/resolve
# ---------------------------------------------------------------------------

_config_lock = threading.Lock()
_config = None   # loaded lazily on first get_config() call


def load_config() -> dict:
    """Load config from disk → DASHBOARD_CONFIG env var → factory defaults.

    Priority (highest first):
      1. dashboard_config.json next to this script
      2. DASHBOARD_CONFIG env var (JSON string)
      3. Factory defaults (KPI_TARGETS + FACTORY_THRESHOLDS)
    """
    global _config

    factory = {
        "version": 1,
        "updated_at": "",
        "global_thresholds": dict(FACTORY_THRESHOLDS),
        "clients": {name: dict(kpi) for name, kpi in KPI_TARGETS.items()},
    }

    config_path = Path(__file__).parent / "dashboard_config.json"
    disk_loaded = False

    # 1. Try disk first
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            is_valid, errors = validate_config(data)
            if is_valid:
                with _config_lock:
                    _config = data
                disk_loaded = True
                if not os.environ.get("DASHBOARD_CONFIG"):
                    print(
                        "WARNING: admin config loaded from disk but DASHBOARD_CONFIG env var is not set. "
                        "Config will be lost on next Render deploy. Use the Export button in /admin to persist."
                    )
                return data
            else:
                print(f"WARNING: dashboard_config.json failed validation ({errors}), trying env var.")
        except Exception as e:
            print(f"WARNING: failed to read dashboard_config.json: {e}, trying env var.")

    # 2. Try DASHBOARD_CONFIG env var
    env_json = os.environ.get("DASHBOARD_CONFIG", "")
    if env_json:
        try:
            data = json.loads(env_json)
            is_valid, errors = validate_config(data)
            if is_valid:
                with _config_lock:
                    _config = data
                return data
            else:
                print(f"WARNING: DASHBOARD_CONFIG env var failed validation ({errors}), using factory defaults.")
        except Exception as e:
            print(f"WARNING: failed to parse DASHBOARD_CONFIG env var: {e}, using factory defaults.")

    # 3. Factory defaults
    with _config_lock:
        _config = factory
    return factory


def save_config(cfg: dict) -> None:
    """Atomically write config to disk, update in-memory config, invalidate cache."""
    global _config, _cache_ts
    config_path = Path(__file__).parent / "dashboard_config.json"
    tmp_path = config_path.with_suffix(".tmp")
    import datetime as _dt
    cfg.setdefault("version", 1)
    cfg["updated_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    data = json.dumps(cfg, indent=2)
    tmp_path.write_text(data, encoding="utf-8")
    tmp_path.rename(config_path)
    with _config_lock:
        _config = cfg
    # Force re-classification on next request
    with _cache_lock:
        _cache_ts.clear()


def get_config() -> dict:
    """Thread-safe getter — lazy-loads config on first call."""
    with _config_lock:
        if _config is not None:
            return _config
    # Not yet loaded — load outside the lock to avoid holding it during I/O
    return load_config()


def get_client_kpi(name: str) -> dict:
    """Return KPI targets for a client. Falls back to KPI_TARGETS factory if not in config."""
    cfg = get_config()
    client_cfg = cfg.get("clients", {}).get(name, {})
    if client_cfg:
        # Strip thresholds key — only return KPI fields
        return {k: v for k, v in client_cfg.items() if k != "thresholds"}
    return KPI_TARGETS.get(name, {})


def get_client_thresholds(name: str) -> dict:
    """Return resolved thresholds for a client: factory → global → per-client overrides."""
    cfg = get_config()
    global_t = cfg.get("global_thresholds", {})
    client_t = cfg.get("clients", {}).get(name, {}).get("thresholds", {})
    return {**FACTORY_THRESHOLDS, **global_t, **client_t}


def validate_config(data: dict) -> tuple:
    """Validate config structure and threshold consistency.

    Returns (is_valid: bool, errors: list[str]).
    """
    errors = []
    if not isinstance(data, dict):
        return False, ["config must be a JSON object"]

    gt = data.get("global_thresholds", {})
    if not isinstance(gt, dict):
        errors.append("global_thresholds must be an object")
    else:
        numeric_fields = [
            "reply_rate_warn", "reply_rate_red",
            "sent_pct_warn", "sent_pct_red",
            "bounce_rate_warn", "bounce_rate_red",
            "opps_pct_warn",
            "pool_days_warn", "pool_days_red",
        ]
        non_numeric = set()
        for f in numeric_fields:
            if f in gt and not isinstance(gt[f], (int, float)):
                errors.append(f"global_thresholds.{f} must be numeric")
                non_numeric.add(f)
        # Consistency checks — only run if both fields are numeric
        if "reply_rate_warn" in gt and "reply_rate_red" in gt \
                and not (non_numeric & {"reply_rate_warn", "reply_rate_red"}):
            if gt["reply_rate_warn"] <= gt["reply_rate_red"]:
                errors.append("reply_rate_warn must be > reply_rate_red")
        if "sent_pct_warn" in gt and "sent_pct_red" in gt \
                and not (non_numeric & {"sent_pct_warn", "sent_pct_red"}):
            if gt["sent_pct_warn"] <= gt["sent_pct_red"]:
                errors.append("sent_pct_warn must be > sent_pct_red")
        if "bounce_rate_warn" in gt and "bounce_rate_red" in gt \
                and not (non_numeric & {"bounce_rate_warn", "bounce_rate_red"}):
            if gt["bounce_rate_warn"] >= gt["bounce_rate_red"]:
                errors.append("bounce_rate_warn must be < bounce_rate_red")
        if "pool_days_warn" in gt and "pool_days_red" in gt \
                and not (non_numeric & {"pool_days_warn", "pool_days_red"}):
            if gt["pool_days_warn"] <= gt["pool_days_red"]:
                errors.append("pool_days_warn must be > pool_days_red")

    clients = data.get("clients", {})
    if not isinstance(clients, dict):
        errors.append("clients must be an object")
    else:
        for cname, ccfg in clients.items():
            if not isinstance(ccfg, dict):
                errors.append(f"clients.{cname} must be an object")
                continue
            kpi_fields = ["sent", "not_contacted", "opps_per_day", "reply_rate"]
            for f in kpi_fields:
                if f in ccfg and not isinstance(ccfg[f], (int, float)):
                    errors.append(f"clients.{cname}.{f} must be numeric")
            cthresh = ccfg.get("thresholds", {})
            if not isinstance(cthresh, dict):
                errors.append(f"clients.{cname}.thresholds must be an object")
            else:
                for f, v in cthresh.items():
                    if not isinstance(v, (int, float)):
                        errors.append(f"clients.{cname}.thresholds.{f} must be numeric")

    return (len(errors) == 0), errors

# ---------------------------------------------------------------------------
# Client registry
# ---------------------------------------------------------------------------

CLIENTS = {
    # Instantly v2
    "MyPlace":       {"platform": "instantly", "env_var": "INSTANTLY_MYPLACE",       "key_path": "tools/accounts/myplace/instantly.md"},
    "SwishFunding":  {"platform": "instantly", "env_var": "INSTANTLY_SWISHFUNDING",  "key_path": "tools/accounts/swishfunding/instantly.md"},
    "SmartMatchApp": {"platform": "instantly", "env_var": "INSTANTLY_SMARTMATCHAPP", "key_path": "tools/accounts/smartmatchapp/instantly.md"},
    "HeyReach":      {"platform": "instantly", "env_var": "INSTANTLY_HEYREACH",      "key_path": "tools/accounts/heyreach-client/instantly.md"},
    "Kayse":         {"platform": "instantly", "env_var": "INSTANTLY_KAYSE",          "key_path": "tools/accounts/kayse/instantly.md"},
    "Prosperly":     {"platform": "instantly", "env_var": "INSTANTLY_PROSPERLY",     "key_path": "tools/accounts/prospeqt/prosperly_instantly.md"},
    "Enavra":        {"platform": "instantly", "env_var": "INSTANTLY_ENAVRA",        "key_path": "tools/accounts/enavra/instantly.md"},

    # EmailBison
    "RankZero":          {"platform": "emailbison", "env_var": "EMAILBISON_RANKZERO",      "key_path": "tools/accounts/rankzero/emailbison.md"},
    "SwishFunding (EB)": {"platform": "emailbison", "env_var": "EMAILBISON_SWISHFUNDING",  "key_path": "tools/accounts/swishfunding/emailbison.md"},
}

# Detect if running on Render (PORT env var set)
IS_RENDER = bool(os.environ.get("PORT"))

# ---------------------------------------------------------------------------
# API key reader
# ---------------------------------------------------------------------------

def read_api_key(key_ref: str) -> str | None:
    """Read API key from env var (Render) or markdown file (local dev)."""
    # Try env var first
    value = os.environ.get(key_ref)
    if value:
        return value.strip()
    # Fall back to file-based reading for local dev
    path = BASE_DIR / key_ref
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        match = re.search(r"```\n(.+?)\n```", content, re.DOTALL)
        return match.group(1).strip() if match else None
    except Exception:
        return None

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_get(url: str, headers: dict, timeout: int = REQUEST_TIMEOUT) -> dict | list | None:
    """GET request, returns parsed JSON or None on any error. Sets _error on None."""
    req = urllib.request.Request(url, headers=headers)
    req.add_header("User-Agent", "ClientDashboard/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"URL error: {e.reason}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON decode error: {e}")


def _http_post(url: str, headers: dict, body: dict, timeout: int = REQUEST_TIMEOUT):
    """Make a POST request and return parsed JSON."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    req.add_header("User-Agent", "ClientDashboard/1.0")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def _count_not_contacted(campaign_id: str, headers: dict) -> int:
    """Count not-yet-contacted leads for a campaign using FILTER_VAL_NOT_CONTACTED.

    Uses POST /api/v2/leads/list with pagination. This matches the Instantly UI
    and is more accurate than leads_count - completed - bounced.
    """
    url = f"{INSTANTLY_BASE}/leads/list"
    count = 0
    cursor = None
    while True:
        body = {
            "filter": "FILTER_VAL_NOT_CONTACTED",
            "campaign": campaign_id,
            "limit": 100,
        }
        if cursor:
            body["starting_after"] = cursor
        resp = _http_post(url, headers, body)
        if not resp or not isinstance(resp, dict):
            break
        items = resp.get("items", [])
        count += len(items)
        next_cursor = resp.get("next_starting_after")
        if not next_cursor or len(items) < 100:
            break
        cursor = next_cursor
        time.sleep(0.1)
    return count


def _paginate_instantly(url_base: str, headers: dict, limit: int = 100) -> list:
    """Fetch all pages from an Instantly v2 paginated endpoint."""
    results = []
    cursor = None
    while True:
        url = f"{url_base}?limit={limit}"
        if cursor:
            url += f"&starting_after={cursor}"
        data = _http_get(url, headers)
        if isinstance(data, list):
            results.extend(data)
            break  # non-paginated (analytics endpoints return plain list)
        items = data.get("items", []) if isinstance(data, dict) else []
        results.extend(items)
        next_cursor = data.get("next_starting_after") if isinstance(data, dict) else None
        if not next_cursor or len(items) < limit:
            break
        cursor = next_cursor
    return results

# ---------------------------------------------------------------------------
# Instantly data fetcher
# ---------------------------------------------------------------------------

INSTANTLY_BASE = "https://api.instantly.ai/api/v2"


def fetch_instantly_data(client_name: str, api_key: str) -> dict:
    """Fetch campaign analytics for a single Instantly workspace."""
    headers = {"Authorization": f"Bearer {api_key}"}

    today = datetime.now(timezone.utc).date()
    seven_ago = today - timedelta(days=7)

    # 1. Campaigns list (for status/active count)
    campaigns = _paginate_instantly(f"{INSTANTLY_BASE}/campaigns", headers)
    active_campaigns = [c for c in campaigns if c.get("status") == 1]

    # 2. All-time analytics (totals for reply rate, opps)
    analytics = _paginate_instantly(f"{INSTANTLY_BASE}/campaigns/analytics", headers)

    # Aggregate totals
    total_sent      = sum(c.get("emails_sent_count", 0) or 0 for c in analytics)
    total_replies   = sum(c.get("reply_count", 0) or 0 for c in analytics)
    total_opps      = sum(c.get("total_opportunities", 0) or 0 for c in analytics)
    total_leads     = sum(c.get("leads_count", 0) or 0 for c in analytics)
    total_contacted = sum(c.get("contacted_count", 0) or 0 for c in analytics)
    total_bounced   = sum(c.get("bounced_count", 0) or 0 for c in analytics)

    # 3. Daily analytics (last 7 days) for trends and today's numbers
    daily_url = (
        f"{INSTANTLY_BASE}/campaigns/analytics/daily"
        f"?start_date={seven_ago.isoformat()}&end_date={today.isoformat()}&limit=100"
    )
    daily_data = _http_get(daily_url, headers) or []

    # Today's numbers
    today_str = today.isoformat()
    today_daily = next((d for d in daily_data if d.get("date") == today_str), {})
    sent_today     = today_daily.get("sent", 0) or 0
    replies_today  = today_daily.get("replies", 0) or 0
    opps_today     = today_daily.get("opportunities", 0) or 0

    # 7-day averages (excluding today)
    past_days = [d for d in daily_data if d.get("date", "") < today_str]
    if past_days:
        avg_sent_7d   = sum(d.get("sent", 0) or 0 for d in past_days) / len(past_days)
        avg_replies_7d = sum(d.get("replies", 0) or 0 for d in past_days) / len(past_days)
        avg_opps_7d   = sum(d.get("opportunities", 0) or 0 for d in past_days) / len(past_days)
    else:
        avg_sent_7d = avg_replies_7d = avg_opps_7d = 0.0

    # Reply rate (today vs 7-day avg)
    reply_rate_today = (replies_today / sent_today * 100) if sent_today > 0 else 0.0
    reply_rate_7d    = (avg_replies_7d / avg_sent_7d * 100) if avg_sent_7d > 0 else 0.0
    reply_rate_all   = (total_replies / total_sent * 100) if total_sent > 0 else 0.0

    # Count not-yet-contacted leads in two phases:
    # Phase 1 (inline): active campaigns only — fast, avoids timeouts
    # Phase 2 (background): inactive campaigns — merges into cache later
    nc_by_campaign = {}
    for c in active_campaigns:
        cid = c.get("id", "")
        if cid:
            nc_by_campaign[cid] = _count_not_contacted(cid, headers)
    not_contacted = sum(nc_by_campaign.values())

    # Inactive campaigns that still need not-contacted counts
    inactive_campaigns = [c for c in campaigns if c.get("status") != 1 and c.get("id")]
    total_completed = sum(c.get("completed_count", 0) or 0 for c in analytics)

    # Trend direction: compare today vs 7d avg
    opp_trend   = _trend(opps_today, avg_opps_7d)
    reply_trend = _trend(reply_rate_today, reply_rate_7d)
    sent_trend  = _trend(sent_today, avg_sent_7d)

    # Build analytics lookup by campaign_id for efficient per-campaign join
    analytics_by_id = {a.get("campaign_id"): a for a in analytics if a.get("campaign_id")}

    campaigns_list = [
        {
            "name":      c.get("name", "Unknown"),
            "id":        c.get("id", ""),
            "status":    "active" if c.get("status") == 1 else "paused",
            "sent":      analytics_by_id.get(c.get("id"), {}).get("emails_sent_count", 0) or 0,
            "replies":   analytics_by_id.get(c.get("id"), {}).get("reply_count", 0) or 0,
            "leads":     analytics_by_id.get(c.get("id"), {}).get("leads_count", 0) or 0,
            "completed": analytics_by_id.get(c.get("id"), {}).get("completed_count", 0) or 0,
            "bounced":   analytics_by_id.get(c.get("id"), {}).get("bounced_count", 0) or 0,
            "opps":      analytics_by_id.get(c.get("id"), {}).get("total_opportunities", 0) or 0,
            "not_contacted": nc_by_campaign.get(c.get("id", ""), 0),
        }
        for c in campaigns
    ]

    return {
        "platform": "instantly",
        "active_campaigns": len(active_campaigns),
        "total_campaigns": len(campaigns),

        # Today's metrics
        "sent_today":     sent_today,
        "replies_today":  replies_today,
        "opps_today":     opps_today,

        # 7-day averages
        "avg_sent_7d":    round(avg_sent_7d, 1),
        "avg_replies_7d": round(avg_replies_7d, 1),
        "avg_opps_7d":    round(avg_opps_7d, 1),

        # All-time totals
        "total_sent":     total_sent,
        "total_replies":  total_replies,
        "total_opps":     total_opps,
        "total_leads":    total_leads,
        "total_contacted": total_contacted,
        "total_bounced":  total_bounced,

        # Derived
        "not_contacted":    not_contacted,
        "reply_rate_today": round(reply_rate_today, 2),
        "reply_rate_7d":    round(reply_rate_7d, 2),
        "reply_rate_all":   round(reply_rate_all, 2),
        "bounce_rate":      round(total_bounced / total_sent * 100, 2) if total_sent > 0 else 0.0,

        # Trend indicators
        "opp_trend":   opp_trend,
        "reply_trend": reply_trend,
        "sent_trend":  sent_trend,

        # Per-campaign breakdown
        "campaigns": campaigns_list,

        # Daily breakdown (for sparkline — last 7 days)
        "daily": [
            {
                "date":  d.get("date"),
                "sent":  d.get("sent", 0) or 0,
                "opps":  d.get("opportunities", 0) or 0,
                "replies": d.get("replies", 0) or 0,
            }
            for d in sorted(daily_data, key=lambda x: x.get("date", ""))
        ],

        # Pending backfill: inactive campaign IDs needing not-contacted counts
        "_nc_backfill": [c.get("id") for c in inactive_campaigns],
        "_nc_api_key":  api_key,
    }


# ---------------------------------------------------------------------------
# EmailBison data fetcher
# ---------------------------------------------------------------------------

EB_BASE = "https://send.prospeqt.co/api"


def _eb_parse_events_timeseries(series: list) -> dict:
    """Parse campaign-events/stats time-series response into flat totals.

    Response format: [{"label": "Sent", "dates": [["2026-03-23", 5], ...]}, ...]
    Returns: {"sent": N, "replied": N, "interested": N, "bounced": N, "opens": N}
    """
    label_map = {
        "Sent": "sent",
        "Replied": "replied",
        "Interested": "interested",
        "Bounced": "bounced",
        "Total Opens": "opens",
        "Unique Opens": "unique_opens",
        "Unsubscribed": "unsubscribed",
    }
    totals: dict = {}
    for item in series:
        label = item.get("label", "")
        key = label_map.get(label)
        if key:
            totals[key] = sum(v for _, v in item.get("dates", []))
    return totals


def fetch_emailbison_data(client_name: str, api_key: str) -> dict:
    """Fetch campaign analytics for a single EmailBison workspace."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    today = datetime.now(timezone.utc).date()
    seven_ago = today - timedelta(days=7)

    # 1. Campaign list — no pagination, returns flat data array
    raw = _http_get(f"{EB_BASE}/campaigns", headers)
    campaigns_all = raw.get("data", []) if isinstance(raw, dict) else []

    # Status is capitalized ("Active", "Paused", etc.) — compare case-insensitively
    active_campaigns = [c for c in campaigns_all if c.get("status", "").lower() == "active"]
    all_cids = [c["id"] for c in campaigns_all if c.get("id")]

    # 2. Aggregate stats via campaign-events/stats.
    # REQUIRED: must pass at least one campaign_id. Builds ?campaign_ids[]=N&... query.
    # Response is a time-series array — parse with _eb_parse_events_timeseries().
    def _eb_events_stats(start: str, end: str, cids: list) -> dict:
        if not cids:
            return {}
        cid_params = "&".join(f"campaign_ids[]={cid}" for cid in cids)
        url = f"{EB_BASE}/campaign-events/stats?start_date={start}&end_date={end}&{cid_params}"
        resp = _http_get(url, headers) or {}
        series = resp.get("data", []) if isinstance(resp, dict) else []
        return _eb_parse_events_timeseries(series)

    stats_7d    = _eb_events_stats(seven_ago.isoformat(), today.isoformat(), all_cids)
    stats_today = _eb_events_stats(today.isoformat(), today.isoformat(), all_cids)

    sent_today    = stats_today.get("sent", 0) or 0
    replies_today = stats_today.get("replied", 0) or 0
    opps_today    = stats_today.get("interested", 0) or 0
    opens_today   = stats_today.get("opens", 0) or 0

    # 7-day totals excluding today
    sent_7d    = (stats_7d.get("sent", 0) or 0) - sent_today
    replies_7d = (stats_7d.get("replied", 0) or 0) - replies_today
    opps_7d    = (stats_7d.get("interested", 0) or 0) - opps_today
    days_in_range = 6  # 7-day window minus today

    avg_sent_7d  = sent_7d / days_in_range if days_in_range > 0 else 0.0
    avg_opps_7d  = opps_7d / days_in_range if days_in_range > 0 else 0.0
    avg_reply_7d = replies_7d / days_in_range if days_in_range > 0 else 0.0

    # 3. Not-contacted leads — correct filter param is filters[lead_campaign_status]=never_contacted
    nc_data = _http_get(
        f"{EB_BASE}/leads?filters%5Blead_campaign_status%5D=never_contacted&page=1", headers
    ) or {}
    not_contacted_meta = nc_data.get("meta", {}) if isinstance(nc_data, dict) else {}
    not_contacted = not_contacted_meta.get("total", 0) or 0

    # Reply rates
    reply_rate_today = (replies_today / sent_today * 100) if sent_today > 0 else 0.0
    reply_rate_7d    = (avg_reply_7d / avg_sent_7d * 100) if avg_sent_7d > 0 else 0.0

    # Bounce rate from 7d stats
    bounced_7d    = stats_7d.get("bounced", 0) or 0
    total_sent_7d = stats_7d.get("sent", 0) or 0
    bounce_rate   = (bounced_7d / total_sent_7d * 100) if total_sent_7d > 0 else 0.0

    opp_trend   = _trend(opps_today, avg_opps_7d)
    reply_trend = _trend(reply_rate_today, reply_rate_7d)
    sent_trend  = _trend(sent_today, avg_sent_7d)

    # 4. Per-campaign stats — active campaigns + up to 5 most recent non-active
    # Uses POST /api/campaigns/{id}/stats with JSON body (GET returns 405)
    # Response fields: emails_sent, interested, bounced, unique_replies_per_contact
    active_cids = [c for c in campaigns_all if c.get("status", "").lower() == "active"]
    paused_cids = [c for c in campaigns_all if c.get("status", "").lower() != "active"][:5]
    campaigns_to_fetch = active_cids + paused_cids

    def _fetch_eb_campaign_stats(c: dict) -> dict:
        cid = c.get("id", "")
        try:
            s = _http_post(
                f"{EB_BASE}/campaigns/{cid}/stats",
                headers,
                {"start_date": seven_ago.isoformat(), "end_date": today.isoformat()},
            ) or {}
            s_data = s.get("data", s) if isinstance(s, dict) else {}
        except Exception:
            s_data = {}
        return {
            "name":    c.get("name", "Unknown"),
            "id":      cid,
            "status":  c.get("status", "unknown"),
            "sent":    s_data.get("emails_sent", 0) or 0,
            "replies": s_data.get("unique_replies_per_contact", 0) or 0,
            "bounced": s_data.get("bounced", 0) or 0,
            "opps":    s_data.get("interested", 0) or 0,
        }

    # Fetch per-campaign stats in parallel (bounded by campaigns_to_fetch size)
    campaign_results: list = [None] * len(campaigns_to_fetch)
    stat_threads = []
    for idx, c in enumerate(campaigns_to_fetch):
        def _worker(i=idx, camp=c):
            campaign_results[i] = _fetch_eb_campaign_stats(camp)
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        stat_threads.append(t)
    for t in stat_threads:
        t.join(timeout=REQUEST_TIMEOUT)

    campaigns_list = [r for r in campaign_results if r is not None]

    return {
        "platform": "emailbison",
        "active_campaigns": len(active_campaigns),
        "total_campaigns": len(campaigns_all),

        "sent_today":     sent_today,
        "replies_today":  replies_today,
        "opps_today":     opps_today,
        "opens_today":    opens_today,

        "avg_sent_7d":    round(avg_sent_7d, 1),
        "avg_replies_7d": round(avg_reply_7d, 1),
        "avg_opps_7d":    round(avg_opps_7d, 1),

        "not_contacted":    not_contacted,
        "reply_rate_today": round(reply_rate_today, 2),
        "reply_rate_7d":    round(reply_rate_7d, 2),
        "bounce_rate":      round(bounce_rate, 2),
        "opps_7d_total":    opps_7d,

        "opp_trend":   opp_trend,
        "reply_trend": reply_trend,
        "sent_trend":  sent_trend,

        # Per-campaign breakdown (active + top 5 recent paused)
        "campaigns": campaigns_list,

        "daily": [],  # EmailBison doesn't expose per-day breakdown easily
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trend(today_val: float, avg_val: float) -> str:
    """Return 'up', 'down', or 'flat' compared to 7-day average."""
    if avg_val == 0:
        return "flat"
    ratio = today_val / avg_val
    if ratio >= 1.1:
        return "up"
    if ratio <= 0.9:
        return "down"
    return "flat"


def _pool_days_remaining(data: dict, client_name: str) -> float:
    """Calculate lead pool runway in days: not_contacted / daily_send_rate."""
    nc = data.get("not_contacted", 0)
    rate = data.get("sent_today", 0) or data.get("avg_sent_7d", 0)
    if rate <= 0:
        return float("inf")
    return nc / rate


def _classify_client(data: dict, client_name: str) -> str:
    """Classify a client's status: 'green', 'amber', or 'red'."""
    kpi = get_client_kpi(client_name)
    t = get_client_thresholds(client_name)
    sent_kpi = kpi.get("sent", 0)

    # No campaigns running → amber
    if data.get("active_campaigns", 0) == 0 and data.get("total_campaigns", 0) > 0:
        return "amber"

    # Zero sent today when campaigns are active → red
    sent_today = data.get("sent_today", 0)
    if data.get("active_campaigns", 0) > 0 and sent_today == 0:
        return "red"

    # Sent well below KPI → red or amber
    if sent_kpi > 0:
        sent_ratio = sent_today / sent_kpi
        if sent_ratio < t["sent_pct_red"]:
            return "red"
        if sent_ratio < t["sent_pct_warn"]:
            return "amber"

    # Reply rate (only classify if meaningful sample)
    rr = data.get("reply_rate_today", 0)
    if sent_today > 50:
        if rr < t["reply_rate_red"]:
            return "red"
        if rr < t["reply_rate_warn"]:
            return "amber"

    # Bounce rate
    br = data.get("bounce_rate", 0)
    if br > t["bounce_rate_red"]:
        return "red"
    if br > t["bounce_rate_warn"]:
        return "amber"

    # Lead pool runway (days remaining)
    pool_days = _pool_days_remaining(data, client_name)
    if pool_days < t["pool_days_red"]:
        return "red"
    if pool_days < t["pool_days_warn"]:
        return "amber"

    return "green"


# ---------------------------------------------------------------------------
# Data cache with TTL
# ---------------------------------------------------------------------------

_cache_lock   = threading.Lock()
_cache_data   = {}   # {client_name: {...data...}}
_cache_ts     = {}   # {client_name: float timestamp}
_cache_errors = {}   # {client_name: str error message}


def _should_refresh(client_name: str) -> bool:
    ts = _cache_ts.get(client_name, 0)
    return (time.time() - ts) > CACHE_TTL


def _backfill_nc(client_name: str, campaign_ids: list, api_key: str) -> None:
    """Background: count not-contacted leads for inactive campaigns and merge into cache."""
    headers = {"Authorization": f"Bearer {api_key}"}
    for cid in campaign_ids:
        count = _count_not_contacted(cid, headers)
        if count > 0:
            with _cache_lock:
                data = _cache_data.get(client_name)
                if not data:
                    return
                # Update top-level not_contacted total
                data["not_contacted"] = data.get("not_contacted", 0) + count
                # Update per-campaign entry
                for camp in data.get("campaigns", []):
                    if camp.get("id") == cid:
                        camp["not_contacted"] = count
                        break


def _fetch_client(client_name: str) -> None:
    """Fetch data for one client and update cache."""
    cfg = CLIENTS[client_name]
    key_ref = cfg["env_var"] if IS_RENDER else cfg["key_path"]
    key = read_api_key(key_ref)

    with _cache_lock:
        if not key:
            _cache_errors[client_name] = "API key not found"
            _cache_ts[client_name] = time.time()
            return

    try:
        if cfg["platform"] == "instantly":
            result = fetch_instantly_data(client_name, key)
        elif cfg["platform"] == "emailbison":
            result = fetch_emailbison_data(client_name, key)
        else:
            raise ValueError(f"Unknown platform: {cfg['platform']}")

        result["status"] = _classify_client(result, client_name)
        result["kpi"]    = get_client_kpi(client_name)
        result["thresholds"] = get_client_thresholds(client_name)
        result["fetched_at"] = datetime.now(timezone.utc).isoformat()

        # Extract backfill info before caching
        nc_backfill = result.pop("_nc_backfill", [])
        nc_api_key  = result.pop("_nc_api_key", None)

        with _cache_lock:
            _cache_data[client_name]   = result
            _cache_ts[client_name]     = time.time()
            _cache_errors.pop(client_name, None)

        # Phase 2: backfill not-contacted counts for inactive campaigns
        if nc_backfill and nc_api_key:
            t = threading.Thread(
                target=_backfill_nc,
                args=(client_name, nc_backfill, nc_api_key),
                daemon=True,
            )
            t.start()

    except Exception as exc:
        with _cache_lock:
            _cache_errors[client_name] = str(exc)
            _cache_ts[client_name]     = time.time()


_bg_refresh_running = False


def _background_refresh_loop():
    """Continuously refresh all clients on a timer. Runs in a daemon thread."""
    while True:
        threads = []
        for name in CLIENTS:
            if _should_refresh(name):
                t = threading.Thread(target=_fetch_client, args=(name,), daemon=True)
                t.start()
                threads.append(t)
        for t in threads:
            t.join(timeout=REQUEST_TIMEOUT + 5)
        time.sleep(60)  # check every 60s, but CACHE_TTL controls actual refresh


def start_background_refresh():
    """Start the background refresh loop (idempotent)."""
    global _bg_refresh_running
    if _bg_refresh_running:
        return
    _bg_refresh_running = True
    t = threading.Thread(target=_background_refresh_loop, daemon=True)
    t.start()


def get_all_data() -> dict:
    """Return cached data instantly — never blocks on API fetches."""
    # Ensure background refresh is running
    start_background_refresh()

    result = {}
    with _cache_lock:
        for name in CLIENTS:
            if name in _cache_data:
                entry = dict(_cache_data[name])
                entry["error"] = None
            elif name in _cache_errors:
                entry = {"error": _cache_errors[name], "status": "error"}
            else:
                entry = {"error": "Loading...", "status": "loading"}
            entry["platform"] = CLIENTS[name]["platform"]
            # Always apply current thresholds so config changes take effect
            # immediately without waiting for the next background fetch cycle.
            entry["thresholds"] = get_client_thresholds(name)
            result[name] = entry
    return result


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Prospeqt &mdash; Campaign Dashboard</title>
<link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAMAAACdt4HsAAAAHlBMVEVMaXEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABKvP01AAAACXRSTlMA46EiQoTCEGeetEsFAAAACXBIWXMAAAsTAAALEwEAmpwYAAABWElEQVR42u2Xyw7EIAhFS1Us///Dk3bqGywyq0l6t+oJeIngtk3lcXebXW4nIjisx2MAumRE+Pv4KUMeDqlRcIvRU6+lPA4gRqANwiMJUl3FZZ0kCGrrRMShts6Qh0NSSbCUsW4pjwNoQYOlHmlR3VVI5qGTIgtRkQJ46W6Qu8cwVE0UwrvATQLcxjrJpj5yOZYN2RaXN6KXMkxxxX3Pq1VQ342M0Xd4CXzWfA0oEbvA3HAq1Ay+cmoB5ZgTi93HpuZ7gPbRyb4OAN2jU66TATw/OnXNswDC+fmmUlgAvIAX8AL+AdD272VA36NWAUPzWwMw/XsFELnurQcIo5caII1eBQBTgDi8VENjFeIIkMYkz484SsDYBtNooAOw/fseDRSAfvrIQQQVAPx0VH8CAD99lDxwDkDDL1CRvBJg/UFOrdMD0P4FfrJOAQBz9F/ATx/48zmYLn8A5oQ0r5uSKKoAAAAASUVORK5CYII=">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root,html[data-theme="dark"]{
  --bg:#0c0c0e;--bg-el:#161618;--bg-hov:#1f1f22;--bg-sel:#1a1e35;
  --bd:#2a2a2e;--bd-s:#3a3a3e;
  --tx1:#f0f0f0;--tx2:#909090;--tx3:#7a7a7e;
  --blue:#2756f7;--blue-h:#1679fa;--blue-bg:rgba(39,86,247,.15);
  --green:#34C759;--amber:#f59e0b;--red:#C33939;
  --sh:0 0.6px 0.6px -1.25px rgba(0,0,0,.3),0 2.3px 2.3px -2.5px rgba(0,0,0,.25),0 10px 10px -3.75px rgba(0,0,0,.15);
  --sh-md:0 4px 12px rgba(0,0,0,.3);
  --sh-lg:0 10px 25px -5px rgba(0,0,0,.35);
}
html[data-theme="light"]{
  --bg:#f5f5f7;--bg-el:#ffffff;--bg-hov:#f0f0f2;--bg-sel:#e8eeff;
  --bd:#e0e0e4;--bd-s:#d0d0d4;
  --tx1:#1a1a1a;--tx2:#6b6b6b;--tx3:#8a8a8e;
  --blue:#2756f7;--blue-h:#1679fa;--blue-bg:rgba(39,86,247,.1);
  --green:#1a8a3e;--amber:#b87a00;--red:#c33939;
  --sh:0 0.6px 0.6px -1.25px rgba(0,0,0,.06),0 2.3px 2.3px -2.5px rgba(0,0,0,.05),0 10px 10px -3.75px rgba(0,0,0,.03);
  --sh-md:0 4px 12px rgba(0,0,0,.08);
  --sh-lg:0 10px 25px -5px rgba(0,0,0,.1);
}
html[data-theme="light"] .cell-val.g{color:#1a8a3e}
html[data-theme="light"] .cell-val.a{color:#b87a00}
html[data-theme="light"] .cell-val.r{color:#c33939}
html[data-theme="light"] .exp-kpi-val.g{color:#1a8a3e}
html[data-theme="light"] .exp-kpi-val.a{color:#b87a00}
html[data-theme="light"] .exp-kpi-val.r{color:#c33939}
html[data-theme="light"] .pill-g{background:rgba(26,138,62,.08);color:#1a8a3e;border-color:rgba(26,138,62,.2)}
html[data-theme="light"] .pill-a{background:rgba(184,122,0,.08);color:#b87a00;border-color:rgba(184,122,0,.2)}
html[data-theme="light"] .pill-r{background:rgba(195,57,57,.08);color:#c33939;border-color:rgba(195,57,57,.2)}
html[data-theme="light"] .chip.c-red{color:#c33939}
html[data-theme="light"] .chip.c-amber{color:#b87a00}
html[data-theme="light"] .chip.c-green{color:#1a8a3e}
html[data-theme="light"] .camp-group-hdr:hover{background:rgba(0,0,0,.03)}
html[data-theme="light"] .skel{background:linear-gradient(90deg,#e8e8ec 25%,#f0f0f4 50%,#e8e8ec 75%);background-size:200% 100%}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:14px}
body{background:var(--bg);color:var(--tx1);font-family:'Inter',sans-serif;line-height:1.5;font-variant-numeric:tabular-nums;min-height:100vh}
@media(prefers-reduced-motion:reduce){*{animation-duration:.01ms!important;transition-duration:.01ms!important}}
.shell{max-width:1280px;margin:0 auto;padding:0 24px 32px}
/* Top bar */
.topbar{display:flex;align-items:center;justify-content:space-between;height:64px;border-bottom:1px solid var(--bd);margin-bottom:0;gap:16px;padding:0 4px}
.logo{display:flex;align-items:center;gap:10px;font-size:17px;font-weight:700;color:var(--tx1);letter-spacing:-.03em;font-family:'Space Grotesk',sans-serif}
.logo-icon{width:28px;height:28px;border-radius:6px;background:linear-gradient(180deg,#FFEAA9 0%,#FFD348 35%,#FF9B1C 65%,#FF4A00 100%);display:flex;align-items:center;justify-content:center}
.logo-icon svg{width:16px;height:16px}
.topbar-mid{font-size:12px;color:var(--tx3);font-family:'Space Mono',monospace}
.btn{display:inline-flex;align-items:center;gap:6px;min-height:44px;padding:0 18px;border-radius:12px;border:none;background:linear-gradient(180deg,#1679fa -23%,#0a61d1 100%);color:#fff;font-size:13px;font-weight:600;cursor:pointer;transition:opacity .15s,transform .1s;font-family:'Inter',sans-serif;box-shadow:0 2px 8px rgba(22,121,250,.25)}
.btn:hover{opacity:.92;transform:translateY(-1px)}
/* Theme toggle */
.theme-btn{width:36px;height:36px;border-radius:8px;border:1px solid var(--bd);background:var(--bg-el);color:var(--tx2);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:16px;transition:background .15s,border-color .15s;flex-shrink:0}
.theme-btn:hover{background:var(--bg-hov);border-color:var(--bd-s)}
.btn.loading .icon-ref{display:none}
.btn .spin{display:none;width:12px;height:12px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite}
.btn.loading .spin{display:block}
@keyframes spin{to{transform:rotate(360deg)}}
/* Progress bar */
.cd-bar{height:2px;background:transparent;overflow:hidden;position:relative}
.cd-fill{height:100%;background:var(--blue);opacity:.4;width:100%;transform-origin:left;transition:none}
.cd-fill.run{animation:countdown linear forwards}
@keyframes countdown{from{width:100%}to{width:0%}}
/* Summary chips */
.chips-wrap{padding:20px 0 16px}
.chips{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.chip{display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 14px;border-radius:8px;border:1px solid var(--bd);background:var(--bg-el);font-size:12px;color:var(--tx2);box-shadow:var(--sh);font-family:'Inter',sans-serif}
.chip strong{color:var(--tx1);font-weight:600}
.chip.c-red{border-color:rgba(195,57,57,.2);background:rgba(195,57,57,.04);color:#C33939}
.chip.c-amber{border-color:rgba(245,158,11,.25);background:rgba(245,158,11,.04);color:#d97706}
.chip.c-green{border-color:rgba(52,199,89,.2);background:rgba(52,199,89,.04);color:#29753c}
.chip.c-blue{border-color:var(--blue-bg);background:var(--blue-bg);color:var(--blue)}
.dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.dot-red{background:var(--red)}.dot-amber{background:var(--amber)}.dot-green{background:var(--green)}.dot-muted{background:var(--tx3)}
/* Table */
.tbl-wrap{border:1px solid var(--bd);border-radius:12px;overflow:hidden;box-shadow:var(--sh);background:var(--bg-el)}
.tbl-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;min-width:760px;border-spacing:0}
thead tr{background:var(--bg)}
thead th{padding:12px 16px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);text-align:left;white-space:nowrap;cursor:pointer;user-select:none;transition:color .15s;border-bottom:1px solid var(--bd);font-family:'Space Mono',monospace}
thead th.num{text-align:right}
thead th:hover{color:var(--tx1)}
thead th.sort-asc::after{content:' \2191';color:var(--blue)}
thead th.sort-desc::after{content:' \2193';color:var(--blue)}
tbody tr{height:52px;cursor:pointer;transition:background .12s}
tbody tr:hover{background:var(--bg-hov)}
tbody tr.selected{background:var(--bg-sel);box-shadow:inset 3px 0 0 var(--blue)}
tbody tr.err-row{cursor:default;box-shadow:inset 3px 0 0 var(--red)}
tbody tr.err-row:hover{background:transparent}
td{padding:0 16px;font-size:13px;color:var(--tx1);white-space:nowrap;border-bottom:1px solid var(--bd)}
tbody tr:last-child td{border-bottom:none}
td.num{text-align:right;font-family:'Space Mono',monospace;font-size:13px}
.client-name{font-weight:600;font-size:13px;letter-spacing:-.01em;font-family:'Space Grotesk',sans-serif}
.client-plat{display:flex;align-items:center;gap:4px;font-size:11px;color:var(--tx3);letter-spacing:.02em;text-transform:uppercase;margin-top:1px;font-family:'Space Mono',monospace}
.plat-logo{width:14px;height:14px;border-radius:3px;object-fit:contain;flex-shrink:0}
.cell-val{font-family:'Space Mono',monospace}
.cell-val.g{color:#29753c}.cell-val.a{color:#d97706}.cell-val.r{color:#C33939}.cell-val.m{color:var(--tx3)}
.trend{font-size:10px;margin-left:3px}
.trend-u{color:#29753c}.trend-d{color:#C33939}.trend-f{color:var(--tx3)}
.pill{display:inline-flex;align-items:center;height:24px;padding:0 10px;border-radius:6px;font-size:11px;font-weight:600;letter-spacing:.02em}
.pill-g{background:rgba(52,199,89,.08);color:#29753c;border:1px solid rgba(52,199,89,.2)}
.pill-a{background:rgba(245,158,11,.08);color:#d97706;border:1px solid rgba(245,158,11,.2)}
.pill-r{background:rgba(195,57,57,.08);color:#C33939;border:1px solid rgba(195,57,57,.2)}
.pill-m{background:var(--bg-el);color:var(--tx3);border:1px solid var(--bd)}
/* Skeleton — dark-theme compatible */
.skel{background:linear-gradient(90deg,var(--bg-hov) 25%,var(--bd) 50%,var(--bg-hov) 75%);background-size:200% 100%;animation:shimmer 1.5s infinite;border-radius:4px;display:inline-block}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
/* Tooltip */
[data-tip]{position:relative}
[data-tip]::after{content:attr(data-tip);position:absolute;bottom:calc(100% + 6px);left:50%;transform:translateX(-50%);background:#000;color:#fff;font-size:11px;padding:6px 12px;border-radius:8px;border:none;box-shadow:var(--sh-md);white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .12s;z-index:100;letter-spacing:normal;text-transform:none;font-family:'Inter',sans-serif}
[data-tip]:hover::after,[data-tip]:focus-visible::after{opacity:1}
/* Focus indicators */
:focus-visible{outline:2px solid var(--blue);outline-offset:2px;border-radius:4px}
:focus:not(:focus-visible){outline:none}
tbody tr:focus-visible{background:var(--bg-sel);box-shadow:inset 3px 0 0 var(--blue)}
/* Expandable row */
.row-chevron{display:inline-block;font-size:11px;color:var(--tx3);transition:transform .2s ease;margin-left:4px}
tbody tr.expanded .row-chevron{transform:rotate(90deg)}
tr.expand-row{display:none}
tr.expand-row.visible{display:table-row}
.expand-row td{padding:0!important;border:none!important;height:0;line-height:0}
.expand-panel{max-height:0;overflow:hidden;transition:max-height .22s ease;background:var(--bg-el);border-left:3px solid var(--blue)}
.expand-panel.open{max-height:2000px}
.expand-inner{padding:24px 28px 28px}
/* KPI cards row */
.exp-kpis{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}
.exp-kpi{background:var(--bg-el);border:1px solid var(--bd);border-radius:12px;padding:16px 20px;flex:1;min-width:140px;box-shadow:var(--sh)}
.exp-kpi-label{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);font-weight:600;margin-bottom:6px;font-family:'Space Mono',monospace}
.exp-kpi-val{font-size:24px;font-weight:700;font-family:'Space Grotesk',sans-serif;letter-spacing:-.03em;line-height:1.1;color:var(--tx1)}
.exp-kpi-val.g{color:#29753c}.exp-kpi-val.a{color:#d97706}.exp-kpi-val.r{color:#C33939}
.exp-kpi-sub{font-size:11px;color:var(--tx3);margin-top:6px}
.exp-kpi-bar{height:3px;background:var(--bd);border-radius:2px;overflow:hidden;margin-top:10px}
.exp-kpi-bar-fill{height:100%;border-radius:2px;transition:width .4s}
.exp-kpi-bar-fill.g{background:var(--green)}.exp-kpi-bar-fill.a{background:var(--amber)}.exp-kpi-bar-fill.r{background:var(--red)}
/* Campaign sub-table — matches client-level table styling */
.exp-section-label{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);font-weight:600;margin-bottom:12px;font-family:'Space Mono',monospace}
.camp-table{width:100%;border-collapse:collapse;font-size:13px;background:var(--bg-el);border-radius:12px;overflow:hidden;border:1px solid var(--bd);box-shadow:var(--sh)}
.camp-table th{padding:12px 16px;font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);font-weight:600;text-align:left;border-bottom:1px solid var(--bd);font-family:'Space Mono',monospace;background:var(--bg)}
.camp-table th.num{text-align:right}
.camp-table td{padding:0 16px;color:var(--tx1);border-bottom:1px solid var(--bd);vertical-align:middle;height:52px;font-size:13px;white-space:nowrap}
.camp-table td.num{text-align:right;font-family:'Space Mono',monospace;font-size:13px}
.camp-table tr:last-child td{border-bottom:none}
.camp-table tr:hover td{background:var(--bg-hov)}
.camp-name{font-weight:600;white-space:nowrap;font-size:13px;letter-spacing:-.01em;font-family:'Space Grotesk',sans-serif}
.camp-status-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;flex-shrink:0;vertical-align:middle}
.camp-status-active{background:#22c55e}.camp-status-paused{background:#94a3b8}
/* Campaign group headers */
.camp-group-hdr{cursor:pointer;user-select:none;transition:background .12s}
.camp-group-hdr:hover{background:rgba(255,255,255,.04)}
.camp-group-hdr td{padding:0 16px!important;height:48px;font-size:13px;font-weight:600;color:var(--tx2);border-bottom:1px solid var(--bd);font-family:'Space Grotesk',sans-serif}
.camp-group-hdr .camp-chev{display:inline-block;font-size:9px;color:var(--tx3);margin-right:8px;transition:transform .2s}
.camp-group-hdr.open .camp-chev{transform:rotate(90deg)}
.camp-group-hdr .camp-group-count{font-weight:400;color:var(--tx3);font-size:11px;margin-left:4px}
.camp-group-row{display:none}
.camp-group-row.visible{display:table-row}
/* Alerts in expanded */
.d-alert{padding:10px 14px;border-radius:8px;font-size:12px;line-height:1.6;margin-bottom:8px}
.d-alert.r{background:rgba(195,57,57,.05);border:1px solid rgba(195,57,57,.15);color:#C33939}
.d-alert.a{background:rgba(245,158,11,.05);border:1px solid rgba(245,158,11,.15);color:#d97706}
/* Mobile card stack — replaces table below 640px */
.card-stack{display:none}
.card-stack .m-card{background:var(--bg-el);border:1px solid var(--bd);border-radius:12px;padding:16px;margin-bottom:12px;cursor:pointer;transition:background .12s;box-shadow:var(--sh)}
.card-stack .m-card:active{background:var(--bg-hov)}
.card-stack .m-card.selected{background:var(--bg-sel);border-color:var(--blue)}
.card-stack .m-card-hdr{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px}
.card-stack .m-card-name{font-weight:600;font-size:15px;font-family:'Space Grotesk',sans-serif;letter-spacing:-.01em}
.card-stack .m-card-plat{display:flex;align-items:center;gap:5px;font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);font-family:'Space Mono',monospace;margin-bottom:10px}
.card-stack .plat-logo{width:13px;height:13px;border-radius:3px}
.card-stack .m-card-metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;border-top:1px solid var(--bd);padding-top:10px}
.card-stack .m-metric-label{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);font-family:'Space Mono',monospace;margin-bottom:2px}
.card-stack .m-metric-val{font-size:16px;font-weight:600;font-family:'Space Mono',monospace}
/* Error card variant */
.card-stack .m-card.err{background:rgba(195,57,57,.04);border-color:rgba(195,57,57,.2);border-left:3px solid var(--red);cursor:default}
.card-stack .m-card.err .m-card-err{font-size:12px;color:var(--tx2);border-top:1px solid rgba(195,57,57,.12);padding-top:10px;margin-top:6px}
.card-stack .m-card.err .m-card-err-msg{color:var(--red);font-weight:500;margin-bottom:2px}
/* Mobile expand detail in card */
.card-stack .m-card-detail{display:none;border-top:1px solid var(--bd);margin-top:12px;padding-top:12px}
.card-stack .m-card.expanded .m-card-detail{display:block}
.card-stack .m-card-detail .exp-kpis{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.card-stack .m-card-detail .exp-kpi{min-width:auto}
/* Campaign table → fully flattened on mobile (no grid-on-tr, pure block) */
.card-stack .m-card-detail .camp-table,
.card-stack .m-card-detail .camp-table thead,
.card-stack .m-card-detail .camp-table tbody,
.card-stack .m-card-detail .camp-table tr,
.card-stack .m-card-detail .camp-table th,
.card-stack .m-card-detail .camp-table td{display:block;width:100%;border:none;padding:0;height:auto;background:transparent;box-shadow:none}
.card-stack .m-card-detail .camp-table thead{display:none}
.card-stack .m-card-detail .camp-table{font-size:12px;min-width:0;overflow:visible}
/* Each campaign row becomes a mini-card */
.card-stack .m-card-detail .camp-table tbody tr:not(.camp-group-hdr):not(.camp-group-row){padding:12px;margin-bottom:8px;border:1px solid var(--bd);border-radius:8px;background:var(--bg-hov)}
.card-stack .m-card-detail .camp-table tbody tr:not(.camp-group-hdr):not(.camp-group-row) td{white-space:normal;text-align:left;font-size:12px;padding:2px 0}
.card-stack .m-card-detail .camp-table tbody tr:not(.camp-group-hdr):not(.camp-group-row) td[data-label]::before{content:attr(data-label) ": ";font-size:10px;color:var(--tx3);font-family:'Space Mono',monospace;font-weight:400}
.card-stack .m-card-detail .camp-table tbody tr:not(.camp-group-hdr):not(.camp-group-row) td:first-child{font-size:13px;font-weight:600;padding-bottom:6px;border-bottom:1px solid var(--bd);margin-bottom:6px}
.card-stack .m-card-detail .camp-table tbody tr:not(.camp-group-hdr):not(.camp-group-row) td:first-child::before{display:none}
.card-stack .m-card-detail .camp-table tbody tr:not(.camp-group-hdr):not(.camp-group-row) td.num{text-align:left}
.card-stack .m-card-detail .camp-name{white-space:normal;word-break:break-word;font-size:12px}
/* Campaign group rows (paused/other) — hidden by default, mini-card when visible */
.card-stack .m-card-detail .camp-group-row{display:none!important}
.card-stack .m-card-detail .camp-group-row.visible{display:block!important;padding:12px;margin-bottom:8px;border:1px solid var(--bd);border-radius:8px;background:var(--bg-hov)}
.card-stack .m-card-detail .camp-group-row.visible td{white-space:normal;text-align:left;font-size:12px;padding:2px 0}
.card-stack .m-card-detail .camp-group-row.visible td[data-label]::before{content:attr(data-label) ": ";font-size:10px;color:var(--tx3);font-family:'Space Mono',monospace;font-weight:400}
.card-stack .m-card-detail .camp-group-row.visible td:first-child{font-size:13px;font-weight:600;padding-bottom:6px;border-bottom:1px solid var(--bd);margin-bottom:6px}
.card-stack .m-card-detail .camp-group-row.visible td:first-child::before{display:none}
.card-stack .m-card-detail .camp-group-row.visible td.num{text-align:left}
/* Campaign group headers */
.card-stack .m-card-detail .camp-group-hdr{padding:10px 0!important;border-bottom:1px solid var(--bd);margin-top:4px}
.card-stack .m-card-detail .camp-group-hdr td{padding:0!important;height:auto}
.card-stack .m-card-detail .camp-group-hdr.open .camp-chev{transform:rotate(90deg)}
@media(max-width:768px){.shell{padding:0 16px 24px}.exp-kpis{flex-direction:column}}
@media(max-width:640px){
  .tbl-wrap{display:none}
  .card-stack{display:block}
  .chips{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;padding-bottom:4px;scrollbar-width:none}
  .chips::-webkit-scrollbar{display:none}
  .chips-wrap{position:relative}
  .chips-wrap::after{content:'';position:absolute;right:0;top:0;bottom:0;width:24px;background:linear-gradient(to right,transparent,var(--bg));pointer-events:none}
  .topbar{height:auto;padding:12px 4px;flex-wrap:wrap;gap:8px}
  .topbar-mid{font-size:11px;order:3;width:100%;text-align:center}
}
</style>
</head>
<body>
<div class="shell">
<div class="topbar">
  <div class="logo"><span class="logo-icon"><svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C8 7 4 10 4 14a8 8 0 0016 0c0-4-4-7-8-12z" fill="#fff"/></svg></span>Prospeqt</div>
  <span class="topbar-mid" id="ts">--</span>
  <div style="display:flex;align-items:center;gap:8px">
  <button class="theme-btn" onclick="toggleTheme()" id="theme-btn" title="Toggle light/dark mode">&#9790;</button>
  <button class="btn" onclick="forceRefresh()" id="refresh-btn">
    <span class="icon-ref">&#x21BB; Refresh</span>
    <span class="spin"></span>
  </button>
  </div>
</div>
<div class="cd-bar"><div class="cd-fill" id="cd-fill"></div></div>
<div class="chips-wrap">
  <div class="chips" id="chips">
    <span class="chip skel" style="width:110px;height:30px"></span>
    <span class="chip skel" style="width:90px;height:30px"></span>
    <span class="chip skel" style="width:90px;height:30px"></span>
  </div>
</div>
<div class="tbl-wrap">
  <div class="tbl-scroll">
    <table id="main-table">
      <thead>
        <tr>
          <th data-col="name">Client</th>
          <th class="col-sm-hide" data-col="platform">Platform</th>
          <th class="num" data-col="sent_today" data-tip="Emails sent today across all active campaigns">Sent Today</th>
          <th class="num col-sm-hide" data-col="not_contacted" data-tip="Leads that haven&#39;t completed the sequence yet (in progress + not contacted)">Remaining</th>
          <th class="num col-sm-hide" data-col="reply_rate_today" data-tip="% of emails sent today that received a reply">Reply Rate</th>
          <th class="num col-sm-hide" data-col="opps_today" data-tip="Positive replies indicating genuine interest">Opps</th>
          <th class="num col-sm-hide" data-col="bounce_rate" data-tip="% of all-time sent emails that bounced">Bounce</th>
          <th data-col="status" data-tip="Overall health based on KPI thresholds">Status</th>
          <th style="width:32px"></th>
        </tr>
      </thead>
      <tbody id="tbl-body">
        <tr><td colspan="8"><span class="skel" style="width:55%;height:14px;display:block;margin:14px 16px"></span></td></tr>
        <tr><td colspan="8"><span class="skel" style="width:75%;height:14px;display:block;margin:14px 16px"></span></td></tr>
        <tr><td colspan="8"><span class="skel" style="width:45%;height:14px;display:block;margin:14px 16px"></span></td></tr>
      </tbody>
    </table>
  </div>
</div>
<div class="card-stack" id="card-stack"></div>
</div>
<script>
var REFRESH_MS = REFRESH_INTERVAL_MS;
var _rt = null;
var _allData = {};
var _sortCol = 'status', _sortDir = 1;
var _expanded = null;
var PLAT_LOGOS={instantly:'https://instantly.ai/blog/content/images/2024/05/cleaned_rounded.png',emailbison:'https://media.licdn.com/dms/image/v2/D4E0BAQGpOS_Byh2OIw/company-logo_200_200/company-logo_200_200/0/1732486612419?e=2147483647&v=beta&t=6FgrEcbuxBgMDPbTksuPOVFkhApor1pUxpM3EJLAiOs'};
function platLabel(p){var label=p==='instantly'?'Instantly':'EmailBison';var src=PLAT_LOGOS[p];if(!src)return label;return '<img class="plat-logo" src="'+src+'" alt="'+label+'"> '+label}
function platIcon(p){var src=PLAT_LOGOS[p];var label=p==='instantly'?'Instantly':'EmailBison';if(!src)return '';return '<img class="plat-logo" src="'+src+'" alt="'+label+'">'}
function fmt(n){return n==null?'--':Number(n).toLocaleString('en-US')}
function fmtPct(n,d){return n==null?'--':Number(n).toFixed(d!=null?d:2)+'%'}
function fmtDec(n,d){return n==null?'--':Number(n).toFixed(d!=null?d:1)}
function clientStatus(d){return d.status==='loading'?'loading':d.error?'error':(d.status||'error')}
function statusOrder(s){return s==='red'?0:s==='amber'?1:s==='green'?2:3}
function sentCls(v,k){if(!k)return 'm';var r=v/k;return r>=0.9?'g':r>=0.7?'a':'r'}
function rrCls(r,t){var warn=t&&t.reply_rate_warn!=null?t.reply_rate_warn:1.0;var red=t&&t.reply_rate_red!=null?t.reply_rate_red:0.5;return r>=warn?'g':r>=red?'a':'r'}
function ncCls(nc,s,a,t){var rate=s>0?s:(a||0);var d=rate>0?nc/rate:Infinity;var warn=t&&t.pool_days_warn!=null?t.pool_days_warn:7;var red=t&&t.pool_days_red!=null?t.pool_days_red:3;return d>=warn?'g':d>=red?'a':'r'}
function bounceCls(b,t){var warn=t&&t.bounce_rate_warn!=null?t.bounce_rate_warn:3;var red=t&&t.bounce_rate_red!=null?t.bounce_rate_red:5;return b>red?'r':b>warn?'a':'m'}
function oppsCls(tv,a,t){var warn=t&&t.opps_pct_warn!=null?t.opps_pct_warn:0.5;return tv>=(a||0)*warn?'g':'a'}
function trend(t){
  if(t==='up')  return '<span class="trend trend-u">\u25b2</span>';
  if(t==='down')return '<span class="trend trend-d">\u25bc</span>';
  return '<span class="trend trend-f">\u2013</span>';
}
function pill(s){
  if(s==='green')return '<span class="pill pill-g">On Track</span>';
  if(s==='amber')return '<span class="pill pill-a">Watch</span>';
  if(s==='red')  return '<span class="pill pill-r">Action</span>';
  if(s==='loading')return '<span class="pill pill-m"><span class="skel" style="width:40px;height:10px"></span></span>';
  return '<span class="pill pill-r">Error</span>';
}
function sortedKeys(data){
  var keys=Object.keys(data);
  keys.sort(function(a,b){
    var da=data[a],db=data[b],va,vb;
    if(_sortCol==='status'){va=statusOrder(clientStatus(da));vb=statusOrder(clientStatus(db));return _sortDir*(va-vb)}
    if(_sortCol==='name'||_sortCol==='platform'){va=a.toLowerCase();vb=b.toLowerCase();return _sortDir*(va<vb?-1:va>vb?1:0)}
    va=da[_sortCol]||0;vb=db[_sortCol]||0;return _sortDir*(va-vb);
  });
  return keys;
}
function renderTable(data){
  var keys=sortedKeys(data);
  var rows='';
  keys.forEach(function(name){
    var d=data[name],s=clientStatus(d),kpi=d.kpi||{},t=d.thresholds||{};
    var isExp=_expanded===name;
    if(d.error){
      rows+='<tr class="err-row" data-name="'+name+'">';
      rows+='<td><div class="client-name" style="color:var(--tx3)">'+name+'</div><div class="client-plat">'+(d.platform==='instantly'?'Instantly':'EmailBison')+'</div></td>';
      rows+='<td class="col-sm-hide"><span style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--tx3);display:inline-flex;align-items:center;gap:4px">'+platLabel(d.platform)+'</span></td>';
      rows+='<td class="num"><span style="color:var(--tx3);font-size:12px">'+d.error+'</span></td>';
      rows+='<td class="num col-sm-hide"></td>';
      rows+='<td class="num col-sm-hide"></td>';
      rows+='<td class="num col-sm-hide"></td>';
      rows+='<td class="num col-sm-hide"></td>';
      rows+='<td>'+pill('error')+'</td><td></td></tr>';
      return;
    }
    var sc=sentCls(d.sent_today||0,kpi.sent),rc=rrCls(d.reply_rate_today||0,t);
    var nc=ncCls(d.not_contacted||0,d.sent_today||0,d.avg_sent_7d||0,t);
    var bc=bounceCls(d.bounce_rate||0,t),oc=oppsCls(d.opps_today||0,d.avg_opps_7d||0,t);
    var selCls=isExp?' selected':'';
    var expCls=isExp?' expanded':'';
    rows+='<tr data-name="'+name+'" tabindex="0" class="'+selCls+expCls+'" onclick="toggleRow(this,\''+name+'\')" onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();toggleRow(this,\''+name+'\')}">';
    rows+='<td><div class="client-name">'+name+'</div><div class="client-plat">'+(d.platform==='instantly'?'Instantly':'EmailBison')+'</div></td>';
    rows+='<td class="col-sm-hide"><span style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--tx3);display:inline-flex;align-items:center;gap:4px">'+platLabel(d.platform)+'</span></td>';
    rows+='<td class="num"><span class="cell-val '+sc+'">'+fmt(d.sent_today)+'</span>'+trend(d.sent_trend)+'</td>';
    rows+='<td class="num col-sm-hide"><span class="cell-val '+nc+'">'+fmt(d.not_contacted)+'</span></td>';
    var rrDisp=(d.sent_today||0)===0?'--':fmtPct(d.reply_rate_today);
    rows+='<td class="num col-sm-hide"><span class="cell-val '+((d.sent_today||0)===0?'m':rc)+'">'+rrDisp+'</span>'+((d.sent_today||0)>0?trend(d.reply_trend):'')+'</td>';
    rows+='<td class="num col-sm-hide"><span class="cell-val '+oc+'">'+fmt(d.opps_today)+'</span>'+trend(d.opp_trend)+'</td>';
    rows+='<td class="num col-sm-hide"><span class="cell-val '+bc+'">'+fmtPct(d.bounce_rate)+'</span></td>';
    rows+='<td>'+pill(s)+'</td>';
    rows+='<td style="text-align:center"><span class="row-chevron">&#9658;</span></td>';
    rows+='</tr>';
    // Expand row (always rendered, toggled via CSS)
    rows+='<tr class="expand-row" data-expand-for="'+name+'"><td colspan="9">';
    rows+='<div class="expand-panel'+(isExp?' open':'')+'"><div class="expand-inner" id="exp-inner-'+name.replace(/[^a-zA-Z0-9]/g,'_')+'">';
    if(isExp){rows+=buildExpandContent(name,d);}
    rows+='</div></div></td></tr>';
  });
  document.getElementById('tbl-body').innerHTML=rows;
}
function renderChips(data){
  var counts={green:0,amber:0,red:0,error:0},totalSent=0,totalOpps=0,rrSum=0,rrN=0;
  Object.keys(data).forEach(function(k){
    var d=data[k],s=clientStatus(d);
    if(counts[s]!=null)counts[s]++;
    if(!d.error){totalSent+=(d.sent_today||0);totalOpps+=(d.opps_today||0);if(d.reply_rate_today!=null){rrSum+=d.reply_rate_today;rrN++;}}
  });
  var avgRR=rrN>0?(rrSum/rrN):0;
  var h='';
  h+='<span class="chip c-blue"><strong>'+fmt(totalSent)+'</strong>&nbsp;sent today</span>';
  h+='<span class="chip c-blue"><strong>'+fmt(totalOpps)+'</strong>&nbsp;opps</span>';
  h+='<span class="chip">Avg reply&nbsp;<strong>'+fmtPct(avgRR)+'</strong></span>';
  if(counts.red)   h+='<span class="chip c-red"><span class="dot dot-red"></span><strong>'+counts.red+'</strong>&nbsp;action needed</span>';
  if(counts.amber) h+='<span class="chip c-amber"><span class="dot dot-amber"></span><strong>'+counts.amber+'</strong>&nbsp;watch</span>';
  if(counts.green) h+='<span class="chip c-green"><span class="dot dot-green"></span><strong>'+counts.green+'</strong>&nbsp;on track</span>';
  if(counts.error) h+='<span class="chip"><span class="dot dot-muted"></span><strong>'+counts.error+'</strong>&nbsp;errors</span>';
  document.getElementById('chips').innerHTML=h;
}
var _campGroupId=0;
function buildCampaignRow(c){
  var isActive=c.status==='active';
  var dotCls=isActive?'camp-status-active':'camp-status-paused';
  var rr=c.sent>0?fmtPct(c.replies/c.sent*100):'--';
  var nc=c.not_contacted!=null?fmt(c.not_contacted):'--';
  var h='<tr>';
  h+='<td data-label="Campaign"><span class="camp-name" title="'+c.name+'">'+c.name+'</span></td>';
  h+='<td data-label="Status" style="white-space:nowrap"><span class="camp-status-dot '+dotCls+'"></span>'+(isActive?'Active':'Paused')+'</td>';
  h+='<td data-label="Sent" class="num">'+fmt(c.sent)+'</td>';
  h+='<td data-label="Remaining" class="num" style="color:'+(c.not_contacted>0?'#d97706':'var(--tx3)')+'">'+nc+'</td>';
  h+='<td data-label="Replies" class="num" style="color:'+(c.replies>0?'#29753c':'var(--tx3)')+'">'+fmt(c.replies)+'</td>';
  h+='<td data-label="Bounced" class="num" style="color:'+(c.bounced>0?'#C33939':'var(--tx3)')+'">'+fmt(c.bounced)+'</td>';
  h+='<td data-label="Opps" class="num" style="color:'+(c.opps>0?'#29753c':'var(--tx3)')+'">'+fmt(c.opps)+'</td>';
  h+='<td data-label="Reply Rate" class="num">'+rr+'</td>';
  h+='</tr>';
  return h;
}
function buildCampaignTable(campaigns){
  if(!campaigns||campaigns.length===0)return '<p style="font-size:12px;color:var(--tx3);padding:8px 0">No campaign data available.</p>';
  var bySent=function(a,b){return (b.sent||0)-(a.sent||0)};
  var active=campaigns.filter(function(c){return c.status==='active'}).sort(bySent);
  var paused=campaigns.filter(function(c){return c.status==='paused'||c.status==='stopped'}).sort(bySent);
  var other=campaigns.filter(function(c){return c.status!=='active'&&c.status!=='paused'&&c.status!=='stopped'}).sort(bySent);
  var h='<table class="camp-table">';
  h+='<thead><tr><th>Campaign</th><th>Status</th><th class="num">Sent</th><th class="num">Remaining</th><th class="num">Replies</th><th class="num">Bounced</th><th class="num">Opps</th><th class="num">Reply Rate</th></tr></thead>';
  h+='<tbody>';
  // Active campaigns: always visible
  if(active.length===0){h+='<tr><td colspan="8" style="font-size:12px;color:var(--tx3);padding:12px">No active campaigns</td></tr>';}
  active.forEach(function(c){h+=buildCampaignRow(c)});
  // Paused: collapsed group
  if(paused.length){
    var gid='cg'+(_campGroupId++);
    h+='<tr class="camp-group-hdr" onclick="toggleCampGroup(this,\''+gid+'\',event)">';
    h+='<td colspan="8"><span class="camp-chev">&#9658;</span>Paused<span class="camp-group-count">('+paused.length+')</span></td></tr>';
    paused.forEach(function(c){h+='<tr class="camp-group-row" data-group="'+gid+'">'+buildCampaignRow(c).replace(/^<tr>/,'').replace(/<\/tr>$/,'')+'</tr>'});
  }
  // Other (completed, unknown, etc.): collapsed group
  if(other.length){
    var gid2='cg'+(_campGroupId++);
    h+='<tr class="camp-group-hdr" onclick="toggleCampGroup(this,\''+gid2+'\',event)">';
    h+='<td colspan="8"><span class="camp-chev">&#9658;</span>Other<span class="camp-group-count">('+other.length+')</span></td></tr>';
    other.forEach(function(c){h+='<tr class="camp-group-row" data-group="'+gid2+'">'+buildCampaignRow(c).replace(/^<tr>/,'').replace(/<\/tr>$/,'')+'</tr>'});
  }
  h+='</tbody></table>';
  return h;
}
function toggleCampGroup(hdr,gid,evt){
  if(evt){evt.stopPropagation();}
  var isOpen=hdr.classList.toggle('open');
  var rows=hdr.closest('table').querySelectorAll('tr[data-group="'+gid+'"]');
  rows.forEach(function(r){isOpen?r.classList.add('visible'):r.classList.remove('visible')});
}
function buildAlerts(name,d){
  var alerts=[],t=d.thresholds||{};
  var poolDaysRed=t.pool_days_red!=null?t.pool_days_red:3;
  var poolDaysWarn=t.pool_days_warn!=null?t.pool_days_warn:7;
  var rrRed=t.reply_rate_red!=null?t.reply_rate_red:0.5;
  var rrWarn=t.reply_rate_warn!=null?t.reply_rate_warn:1.0;
  var brRed=t.bounce_rate_red!=null?t.bounce_rate_red:5;
  var brWarn=t.bounce_rate_warn!=null?t.bounce_rate_warn:3;
  var nc=d.not_contacted||0,sentToday=d.sent_today||0,avg7d=d.avg_sent_7d||0;
  var rate=sentToday>0?sentToday:avg7d,poolD=rate>0?nc/rate:Infinity;
  if(poolD<poolDaysRed) alerts.push({cls:'r',msg:'Lead pool critical ('+fmtDec(poolD,1)+'d) \u2014 upload leads immediately'});
  else if(poolD<poolDaysWarn) alerts.push({cls:'a',msg:'Lead pool low ('+fmtDec(poolD,1)+'d) \u2014 plan lead upload soon'});
  var rr=d.reply_rate_today||0;
  if(sentToday>50&&rr<rrRed) alerts.push({cls:'r',msg:'Reply rate very low ('+fmtPct(rr)+') \u2014 check deliverability or copy'});
  else if(sentToday>50&&rr<rrWarn) alerts.push({cls:'a',msg:'Reply rate below target ('+fmtPct(rr)+') \u2014 review copy or segments'});
  if((d.active_campaigns||0)===0&&(d.total_campaigns||0)>0) alerts.push({cls:'r',msg:'No active campaigns \u2014 check campaign status'});
  if((d.active_campaigns||0)>0&&sentToday===0) alerts.push({cls:'r',msg:'Campaigns active but nothing sent \u2014 check sending accounts'});
  var br=d.bounce_rate||0;
  if(br>brRed) alerts.push({cls:'r',msg:'Bounce rate '+fmtPct(br)+' \u2014 data quality issue'});
  else if(br>brWarn) alerts.push({cls:'a',msg:'Bounce rate elevated ('+fmtPct(br)+') \u2014 monitor closely'});
  return alerts;
}
function buildExpandContent(name,d){
  var kpi=d.kpi||{},t=d.thresholds||{},h='';
  if(d.error){return '<div class="d-alert r">'+d.error+'</div>';}
  // Row 1: KPI metric cards
  h+='<div class="exp-kpis">';
  var sc=sentCls(d.sent_today||0,kpi.sent),sentPct=kpi.sent>0?Math.min(100,Math.round(((d.sent_today||0)/kpi.sent)*100)):null;
  h+='<div class="exp-kpi"><div class="exp-kpi-label">Sent Today</div><div class="exp-kpi-val '+sc+'">'+fmt(d.sent_today)+'</div>';
  h+='<div class="exp-kpi-sub">KPI: '+fmt(kpi.sent||0)+(sentPct!=null?' &middot; '+sentPct+'%':'')+'</div>';
  if(sentPct!=null)h+='<div class="exp-kpi-bar"><div class="exp-kpi-bar-fill '+sc+'" style="width:'+sentPct+'%"></div></div>';
  h+='</div>';
  var ncR=ncCls(d.not_contacted||0,d.sent_today||0,d.avg_sent_7d||0,t);
  var rate2=(d.sent_today>0?d.sent_today:(d.avg_sent_7d||0)),poolD2=rate2>0?(d.not_contacted||0)/rate2:null;
  var poolLabel=poolD2!=null?(poolD2>99?'>99d':fmtDec(poolD2,1)+'d remaining'):'-- remaining';
  h+='<div class="exp-kpi"><div class="exp-kpi-label">Lead Pool</div><div class="exp-kpi-val '+ncR+'">'+fmt(d.not_contacted)+'</div>';
  h+='<div class="exp-kpi-sub">'+poolLabel+' at current pace</div></div>';
  var rc=rrCls(d.reply_rate_today||0,t),rrPct=kpi.reply_rate>0?Math.min(200,Math.round(((d.reply_rate_today||0)/kpi.reply_rate)*100)):null;
  h+='<div class="exp-kpi"><div class="exp-kpi-label">Reply Rate</div><div class="exp-kpi-val '+rc+'">'+fmtPct(d.reply_rate_today)+'</div>';
  h+='<div class="exp-kpi-sub">Target: '+fmtPct(kpi.reply_rate||0)+(rrPct!=null?' &middot; '+rrPct+'%':'')+'</div>';
  if(rrPct!=null)h+='<div class="exp-kpi-bar"><div class="exp-kpi-bar-fill '+rc+'" style="width:'+Math.min(100,rrPct)+'%"></div></div>';
  h+='</div>';
  var oc=oppsCls(d.opps_today||0,d.avg_opps_7d||0,t);
  h+='<div class="exp-kpi"><div class="exp-kpi-label">Opportunities</div><div class="exp-kpi-val '+oc+'">'+fmt(d.opps_today)+'</div>';
  h+='<div class="exp-kpi-sub">Target: '+fmtDec(kpi.opps_per_day||0,1)+'/day &middot; 7d avg: '+fmtDec(d.avg_opps_7d,1)+'</div></div>';
  var bc=bounceCls(d.bounce_rate||0,t);
  var brWarnDisp=t.bounce_rate_warn!=null?t.bounce_rate_warn:3;
  var brRedDisp=t.bounce_rate_red!=null?t.bounce_rate_red:5;
  h+='<div class="exp-kpi"><div class="exp-kpi-label">Bounce Rate</div><div class="exp-kpi-val '+bc+'">'+fmtPct(d.bounce_rate)+'</div>';
  h+='<div class="exp-kpi-sub">Warn &gt;'+brWarnDisp+'% &middot; Red &gt;'+brRedDisp+'%</div></div>';
  h+='</div>';
  // Row 2: Campaigns sub-table
  if(d.campaigns&&d.campaigns.length>0){
    h+='<div style="margin-bottom:20px"><div class="exp-section-label">Campaigns &mdash; '+(d.active_campaigns||0)+' active / '+(d.total_campaigns||0)+' total</div>';
    h+=buildCampaignTable(d.campaigns);
    h+='</div>';
  }
  // Alerts
  var alerts=buildAlerts(name,d);
  if(alerts.length){
    h+='<div style="margin-top:16px">';
    alerts.forEach(function(a){h+='<div class="d-alert '+a.cls+'">'+a.msg+'</div>';});
    h+='</div>';
  }
  return h;
}
function toggleRow(tr,name){
  if(_expanded===name){
    // Collapse
    _expanded=null;
    tr.classList.remove('selected','expanded');
    var expRow=tr.nextElementSibling;
    if(expRow&&expRow.classList.contains('expand-row')){
      expRow.querySelector('.expand-panel').classList.remove('open');
      expRow.classList.remove('visible');
    }
  } else {
    // Collapse any previously expanded row
    if(_expanded){
      var prevTr=document.querySelector('tbody tr[data-name="'+_expanded+'"]');
      if(prevTr){
        prevTr.classList.remove('selected','expanded');
        var prevExp=prevTr.nextElementSibling;
        if(prevExp&&prevExp.classList.contains('expand-row')){
          prevExp.querySelector('.expand-panel').classList.remove('open');
          prevExp.classList.remove('visible');
        }
      }
    }
    _expanded=name;
    tr.classList.add('selected','expanded');
    var expRow2=tr.nextElementSibling;
    if(expRow2&&expRow2.classList.contains('expand-row')){
      var inner=expRow2.querySelector('.expand-inner');
      var panel=expRow2.querySelector('.expand-panel');
      // Lazily build content
      if(!inner.innerHTML.trim()){
        inner.innerHTML=buildExpandContent(name,_allData[name]);
      }
      expRow2.classList.add('visible');
      panel.classList.add('open');
    }
  }
}
document.querySelectorAll('thead th[data-col]').forEach(function(th){
  th.addEventListener('click',function(){
    var col=th.getAttribute('data-col');
    if(_sortCol===col){_sortDir*=-1}else{_sortCol=col;_sortDir=1}
    document.querySelectorAll('thead th').forEach(function(h){h.classList.remove('sort-asc','sort-desc')});
    th.classList.add(_sortDir===1?'sort-asc':'sort-desc');
    renderTable(_allData);
  });
});
document.querySelector('thead th[data-col="status"]').classList.add('sort-asc');
function startCd(secs){
  var fill=document.getElementById('cd-fill');
  fill.classList.remove('run');fill.style.animationDuration=secs+'s';
  void fill.offsetWidth;fill.classList.add('run');
}
function renderCards(data){
  var keys=sortedKeys(data);
  var h='';
  keys.forEach(function(name){
    var d=data[name],s=clientStatus(d),kpi=d.kpi||{},t=d.thresholds||{};
    var isExp=_expanded===name;
    if(d.error){
      h+='<div class="m-card err" data-name="'+name+'">';
      h+='<div class="m-card-hdr"><span class="m-card-name" style="color:var(--tx3)">'+name+'</span>'+pill('error')+'</div>';
      h+='<div class="m-card-plat">'+(d.platform==='instantly'?'Instantly':'EmailBison')+'</div>';
      h+='<div class="m-card-err"><div class="m-card-err-msg">'+d.error+'</div></div>';
      h+='</div>';
      return;
    }
    var sc=sentCls(d.sent_today||0,kpi.sent),rc=rrCls(d.reply_rate_today||0,t);
    var nc=ncCls(d.not_contacted||0,d.sent_today||0,d.avg_sent_7d||0,t);
    var bc=bounceCls(d.bounce_rate||0,t);
    var rrMobile=(d.sent_today||0)===0?'--':fmtPct(d.reply_rate_today);
    var rrMobileCls=(d.sent_today||0)===0?'m':rc;
    h+='<div class="m-card'+(isExp?' selected expanded':'')+'" data-name="'+name+'" onclick="toggleCard(this,\''+name+'\')">';
    h+='<div class="m-card-hdr"><span class="m-card-name">'+name+'</span>'+pill(s)+'</div>';
    h+='<div class="m-card-plat">'+(d.platform==='instantly'?'Instantly':'EmailBison')+'</div>';
    h+='<div class="m-card-metrics">';
    h+='<div><div class="m-metric-label">Sent Today</div><div class="m-metric-val cell-val '+sc+'">'+fmt(d.sent_today)+' '+trend(d.sent_trend)+'</div></div>';
    h+='<div><div class="m-metric-label">Reply Rate</div><div class="m-metric-val cell-val '+rrMobileCls+'">'+rrMobile+'</div></div>';
    h+='<div><div class="m-metric-label">Leads Left</div><div class="m-metric-val cell-val '+nc+'">'+fmt(d.not_contacted)+'</div></div>';
    h+='<div><div class="m-metric-label">Bounce</div><div class="m-metric-val cell-val '+bc+'">'+fmtPct(d.bounce_rate)+'</div></div>';
    h+='</div>';
    // Inline expand detail
    h+='<div class="m-card-detail">';
    if(isExp){h+=buildExpandContent(name,d);}
    h+='</div>';
    h+='</div>';
  });
  document.getElementById('card-stack').innerHTML=h;
}
function toggleCard(card,name){
  if(_expanded===name){
    _expanded=null;
    card.classList.remove('selected','expanded');
    card.querySelector('.m-card-detail').innerHTML='';
  } else {
    // Collapse previous
    if(_expanded){
      var prev=document.querySelector('.card-stack .m-card[data-name="'+_expanded+'"]');
      if(prev){prev.classList.remove('selected','expanded');prev.querySelector('.m-card-detail').innerHTML='';}
    }
    _expanded=name;
    card.classList.add('selected','expanded');
    card.querySelector('.m-card-detail').innerHTML=buildExpandContent(name,_allData[name]);
  }
}
function render(data){
  _allData=data;
  renderChips(data);renderTable(data);renderCards(data);
  document.getElementById('ts').textContent='Updated '+new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}
function hasLoading(data){
  return Object.keys(data).some(function(k){return data[k].status==='loading'||data[k].error==='Loading...'});
}
function fetchAndRender(){
  fetch('/api/data').then(function(r){return r.json()}).then(function(data){
    render(data);
    // Poll every 3s while data is still loading, then normal interval
    var interval=hasLoading(data)?3000:REFRESH_MS;
    startCd(Math.floor(interval/1000));
    if(_rt)clearTimeout(_rt);_rt=setTimeout(fetchAndRender,interval);
  }).catch(function(e){
    document.getElementById('ts').textContent='Error: '+e.message;
    if(_rt)clearTimeout(_rt);_rt=setTimeout(fetchAndRender,30000);
  });
}
function forceRefresh(){
  if(_rt)clearTimeout(_rt);
  var btn=document.getElementById('refresh-btn');btn.classList.add('loading');
  fetch('/api/refresh',{method:'POST'}).catch(function(){}).finally(function(){
    // Poll quickly until fresh data arrives
    var polls=0;
    function pollFresh(){
      fetch('/api/data').then(function(r){return r.json()}).then(function(data){
        render(data);polls++;
        if(hasLoading(data)&&polls<20){setTimeout(pollFresh,2000)}
        else{startCd(Math.floor(REFRESH_MS/1000));_rt=setTimeout(fetchAndRender,REFRESH_MS);btn.classList.remove('loading')}
      }).catch(function(){btn.classList.remove('loading')});
    }
    pollFresh();
  });
}
// Theme toggle — persists to localStorage
function toggleTheme(){
  var html=document.documentElement;
  var current=html.getAttribute('data-theme')||'dark';
  var next=current==='dark'?'light':'dark';
  html.setAttribute('data-theme',next);
  localStorage.setItem('theme',next);
  document.getElementById('theme-btn').innerHTML=next==='dark'?'&#9790;':'&#9728;';
}
(function initTheme(){
  var saved=localStorage.getItem('theme');
  if(saved){
    document.documentElement.setAttribute('data-theme',saved);
    if(saved==='light')document.getElementById('theme-btn').innerHTML='&#9728;';
  }
})();
fetchAndRender();
</script>
</body>
</html>
"""

# Inject JS constant at serve time
DASHBOARD_HTML = DASHBOARD_HTML.replace("REFRESH_INTERVAL_MS", str(AUTO_REFRESH_MS))


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Ping log — ring buffer of recent keep-alive pings
# ---------------------------------------------------------------------------

_ping_log: list = []       # [{ts, source, status}]
_ping_log_lock = threading.Lock()
_PING_LOG_MAX = 200
_server_start_ts = datetime.now(timezone.utc).isoformat()

# HMAC auth token bound to this server instance (invalidated on restart)
_hmac_start_ts = str(int(time.time()))


def _record_ping(source: str = "unknown"):
    with _ping_log_lock:
        _ping_log.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": source,
        })
        if len(_ping_log) > _PING_LOG_MAX:
            _ping_log[:] = _ping_log[-_PING_LOG_MAX:]


# ---------------------------------------------------------------------------
# Admin auth — HMAC cookie
# ---------------------------------------------------------------------------

def _make_token(password: str) -> str:
    key = (password + _hmac_start_ts).encode()
    return hmac.new(key, b"admin", hashlib.sha256).hexdigest()


def _parse_cookie(cookie_header: str) -> dict:
    result = {}
    for part in cookie_header.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            result[k.strip()] = v.strip()
    return result


def _check_admin_auth(handler) -> bool:
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        return False
    cookie = _parse_cookie(handler.headers.get("Cookie", "")).get("admin_token", "")
    return hmac.compare_digest(cookie, _make_token(password))


# ---------------------------------------------------------------------------
# Admin HTML templates
# ---------------------------------------------------------------------------

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Admin Login</title>
<style>
:root{--bg:#0c0c0e;--bg-el:#161618;--bd:#2a2a2e;--tx1:#f0f0f0;--tx2:#909090;--blue:#2756f7;--red:#C33939;--sh:0 4px 12px rgba(0,0,0,.3)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx1);font-family:'Inter',system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:var(--bg-el);border:1px solid var(--bd);border-radius:12px;padding:32px;width:100%;max-width:360px;box-shadow:var(--sh)}
h1{font-size:18px;font-weight:600;margin-bottom:24px}
label{display:block;font-size:12px;color:var(--tx2);margin-bottom:6px}
input[type=password]{width:100%;background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:10px 14px;color:var(--tx1);font-size:14px;outline:none}
input[type=password]:focus{border-color:var(--blue)}
button{margin-top:16px;width:100%;padding:12px;border-radius:8px;border:none;background:var(--blue);color:#fff;font-size:14px;font-weight:600;cursor:pointer}
button:hover{opacity:.9}
.err{color:var(--red);font-size:12px;margin-top:12px}
</style>
</head>
<body>
<div class="card">
  <h1>Admin Login</h1>
  <form method="POST" action="/admin/login">
    <label>Password</label>
    <input type="password" name="password" autofocus>
    <button type="submit">Sign In</button>
    ERROR_MSG
  </form>
</div>
</body>
</html>"""

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard Admin</title>
<style>
:root{--bg:#0c0c0e;--bg-el:#161618;--bg-hov:#1f1f22;--bd:#2a2a2e;--bd-s:#3a3a3e;--tx1:#f0f0f0;--tx2:#909090;--tx3:#7a7a7e;--blue:#2756f7;--blue-bg:rgba(39,86,247,.15);--green:#34C759;--amber:#f59e0b;--red:#C33939;--sh:0 4px 12px rgba(0,0,0,.3)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx1);font-family:'Inter',system-ui,sans-serif;font-size:14px;line-height:1.5;padding:24px}
.shell{max-width:1100px;margin:0 auto}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}
h1{font-size:18px;font-weight:600}
.logout{font-size:12px;color:var(--tx2);text-decoration:none}
.logout:hover{color:var(--tx1)}
.section{background:var(--bg-el);border:1px solid var(--bd);border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:var(--sh)}
.section-title{font-size:13px;font-weight:600;color:var(--tx2);text-transform:uppercase;letter-spacing:.06em;margin-bottom:16px}
table{width:100%;border-collapse:collapse}
th{font-size:11px;font-weight:600;color:var(--tx3);text-transform:uppercase;letter-spacing:.05em;padding:8px 12px;text-align:left;border-bottom:1px solid var(--bd)}
th.num{text-align:right}
td{padding:8px 12px;border-bottom:1px solid var(--bd);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:nth-child(even) td{background:rgba(255,255,255,.015)}
.td-label{color:var(--tx2);font-size:13px}
input[type=number]{background:var(--bg);border:1px solid var(--bd);border-radius:6px;color:var(--tx1);font-size:13px;padding:5px 8px;width:90px;outline:none;text-align:right}
input[type=number]:focus{border-color:var(--blue)}
input[type=number].overridden{border-left:3px solid var(--blue)}
.client-name{font-weight:500}
.plat-badge{font-size:10px;color:var(--tx3);background:var(--bg);border:1px solid var(--bd);border-radius:4px;padding:2px 6px;margin-left:6px}
.chevron{cursor:pointer;color:var(--tx3);font-size:11px;user-select:none;padding:2px 6px;border-radius:4px}
.chevron:hover{background:var(--bg-hov);color:var(--tx1)}
.override-row{display:none}
.override-row.open{display:table-row-group}
.override-inner{padding:12px 12px 12px 24px;background:var(--bg)}
.override-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px}
.override-field{display:flex;align-items:center;justify-content:space-between;gap:8px}
.override-label{font-size:12px;color:var(--tx2)}
.reset-link{font-size:11px;color:var(--blue);cursor:pointer;white-space:nowrap}
.reset-link:hover{text-decoration:underline}
.export-area{margin-top:12px}
textarea{width:100%;background:var(--bg);border:1px solid var(--bd);border-radius:8px;color:var(--tx1);font-size:12px;font-family:monospace;padding:12px;resize:vertical;min-height:120px;outline:none}
.instructions{font-size:12px;color:var(--tx2);margin-bottom:8px}
.save-bar{display:flex;align-items:center;gap:12px;margin-top:20px}
.save-btn{padding:10px 24px;border-radius:8px;border:none;background:var(--blue);color:#fff;font-size:14px;font-weight:600;cursor:pointer}
.save-btn:disabled{opacity:.4;cursor:not-allowed}
.save-btn:not(:disabled):hover{opacity:.9}
.toast{display:none;padding:8px 16px;border-radius:8px;font-size:13px}
.toast.ok{background:rgba(52,199,89,.15);color:var(--green);border:1px solid rgba(52,199,89,.25)}
.toast.err{background:rgba(195,57,57,.12);color:var(--red);border:1px solid rgba(195,57,57,.2)}
</style>
</head>
<body>
<div class="shell">
<div class="topbar"><h1>Dashboard Admin</h1><a class="logout" href="/admin/logout">Sign out</a></div>

<div class="section">
<div class="section-title">Global Thresholds</div>
<table id="gt-table">
<thead><tr><th>Metric</th><th class="num">Warn</th><th class="num">Red</th></tr></thead>
<tbody>
<tr><td class="td-label">Reply Rate (%)</td><td><input type="number" step="0.1" data-gt="reply_rate_warn"></td><td><input type="number" step="0.1" data-gt="reply_rate_red"></td></tr>
<tr><td class="td-label">Sent Volume (fraction of KPI)</td><td><input type="number" step="0.05" data-gt="sent_pct_warn"></td><td><input type="number" step="0.05" data-gt="sent_pct_red"></td></tr>
<tr><td class="td-label">Bounce Rate (%)</td><td><input type="number" step="0.5" data-gt="bounce_rate_warn"></td><td><input type="number" step="0.5" data-gt="bounce_rate_red"></td></tr>
<tr><td class="td-label">Lead Pool (days)</td><td><input type="number" step="1" data-gt="pool_days_warn"></td><td><input type="number" step="1" data-gt="pool_days_red"></td></tr>
<tr><td class="td-label">Opps vs 7d Avg (fraction)</td><td><input type="number" step="0.05" data-gt="opps_pct_warn"></td><td class="td-label" style="color:var(--tx3);font-size:12px">n/a</td></tr>
</tbody></table>
</div>
<div class="section">
<div class="section-title">Client KPI Targets</div>
<table id="kpi-table">
<thead><tr><th>Client</th><th class="num">Sent/Day</th><th class="num">Pool Target</th><th class="num">Opps/Day</th><th class="num">Reply Rate %</th><th></th></tr></thead>
<tbody id="kpi-tbody"></tbody>
</table>
</div>
<div class="section">
<div class="section-title">Export Config</div>
<p class="instructions">Click Export to generate the current config. Paste into <code>DASHBOARD_CONFIG</code> in Render env vars to persist across deploys.</p>
<button onclick="exportConfig()" style="padding:8px 16px;border-radius:6px;border:1px solid var(--bd);background:var(--bg-hov);color:var(--tx1);font-size:13px;cursor:pointer">Export Config</button>
<div class="export-area" id="export-area" style="display:none"><textarea id="export-txt" readonly onclick="this.select()"></textarea></div>
</div>
<div class="save-bar">
<button class="save-btn" id="save-btn" disabled onclick="saveConfig()">Save Changes</button>
<div class="toast" id="toast"></div>
</div>
</div>

<script>
var _cfg = null, _origJson = '';
var THRESH_KEYS = ['reply_rate_warn','reply_rate_red','sent_pct_warn','sent_pct_red','bounce_rate_warn','bounce_rate_red','pool_days_warn','pool_days_red','opps_pct_warn'];
var THRESH_LABELS = {reply_rate_warn:'Reply Rate Warn',reply_rate_red:'Reply Rate Red',sent_pct_warn:'Sent Pct Warn',sent_pct_red:'Sent Pct Red',bounce_rate_warn:'Bounce Warn',bounce_rate_red:'Bounce Red',pool_days_warn:'Pool Days Warn',pool_days_red:'Pool Days Red',opps_pct_warn:'Opps Pct Warn'};

fetch('/admin/api/config').then(function(r){return r.json();}).then(function(cfg){
  _cfg = cfg; _origJson = JSON.stringify(cfg);
  var gt = cfg.global_thresholds || {};
  document.querySelectorAll('[data-gt]').forEach(function(inp){
    var k = inp.getAttribute('data-gt');
    if(gt[k] !== undefined) inp.value = gt[k];
  });
  buildKpiRows(cfg);
  document.querySelectorAll('input').forEach(function(i){i.addEventListener('input', checkDirty);});
});
function buildKpiRows(cfg){
  var clients = cfg.clients || {}, gt = cfg.global_thresholds || {};
  var tb = document.getElementById('kpi-tbody'), html = '';
  Object.keys(clients).forEach(function(name){
    var c = clients[name], ct = c.thresholds || {};
    var rowId = 'row-' + name.replace(/[^a-z0-9]/gi,'_');
    html += '<tr>';
    html += '<td><span class="client-name">'+name+'</span><span class="chevron" onclick="toggleOverrides(\''+rowId+'\')" id="chev-'+rowId+'">&#9654; overrides</span></td>';
    html += '<td><input type="number" data-client="'+name+'" data-kpi="sent" value="'+(c.sent||'')+'"></td>';
    html += '<td><input type="number" data-client="'+name+'" data-kpi="not_contacted" value="'+(c.not_contacted||'')+'"></td>';
    html += '<td><input type="number" step="0.1" data-client="'+name+'" data-kpi="opps_per_day" value="'+(c.opps_per_day||'')+'"></td>';
    html += '<td><input type="number" step="0.1" data-client="'+name+'" data-kpi="reply_rate" value="'+(c.reply_rate||'')+'"></td>';
    html += '<td></td></tr>';
    html += '<tbody class="override-row" id="'+rowId+'">';
    html += '<tr><td colspan="6"><div class="override-inner"><div class="override-grid">';
    THRESH_KEYS.forEach(function(k){
      var val = ct[k] !== undefined ? ct[k] : '';
      var gval = gt[k] !== undefined ? gt[k] : '';
      var ovr = ct[k] !== undefined;
      html += '<div class="override-field">';
      html += '<span class="override-label">'+THRESH_LABELS[k]+'</span>';
      html += '<input type="number" step="0.1" data-client="'+name+'" data-thresh="'+k+'" value="'+val+'" placeholder="'+gval+'" class="'+(ovr?'overridden':'')+'" style="width:80px">';
      html += '<span class="reset-link" onclick="resetOverride(\''+name+'\',\''+k+'\')">Reset</span>';
      html += '</div>';
    });
    html += '</div></div></td></tr></tbody>';
  });
  document.getElementById('kpi-tbody').innerHTML = html;
}

function toggleOverrides(rowId){
  var el = document.getElementById(rowId);
  var chev = document.getElementById('chev-'+rowId);
  el.classList.toggle('open');
  chev.innerHTML = el.classList.contains('open') ? '&#9660; overrides' : '&#9654; overrides';
}
function resetOverride(clientName, key){
  var inp = document.querySelector('[data-client="'+clientName+'"][data-thresh="'+key+'"]');
  if(inp){inp.value='';inp.classList.remove('overridden');checkDirty();}
}
function collectConfig(){
  var cfg = JSON.parse(JSON.stringify(_cfg));
  var gt = cfg.global_thresholds || {};
  document.querySelectorAll('[data-gt]').forEach(function(inp){
    var k = inp.getAttribute('data-gt'), v = parseFloat(inp.value);
    if(!isNaN(v)) gt[k] = v;
  });
  cfg.global_thresholds = gt;
  Object.keys(cfg.clients || {}).forEach(function(name){
    var c = cfg.clients[name];
    ['sent','not_contacted'].forEach(function(k){
      var inp = document.querySelector('[data-client="'+name+'"][data-kpi="'+k+'"]');
      if(inp && inp.value !== '') c[k] = parseInt(inp.value);
    });
    ['opps_per_day','reply_rate'].forEach(function(k){
      var inp = document.querySelector('[data-client="'+name+'"][data-kpi="'+k+'"]');
      if(inp && inp.value !== '') c[k] = parseFloat(inp.value);
    });
    var overrides = {};
    THRESH_KEYS.forEach(function(k){
      var inp = document.querySelector('[data-client="'+name+'"][data-thresh="'+k+'"]');
      if(inp && inp.value !== '') overrides[k] = parseFloat(inp.value);
    });
    if(Object.keys(overrides).length) c.thresholds = overrides;
    else delete c.thresholds;
  });
  return cfg;
}

function checkDirty(){
  var cur = JSON.stringify(collectConfig());
  document.getElementById('save-btn').disabled = (cur === _origJson);
}
function showToast(msg, type){
  var t = document.getElementById('toast');
  t.className = 'toast ' + type; t.textContent = msg; t.style.display = 'inline-block';
  setTimeout(function(){t.style.display='none';}, 3000);
}

function saveConfig(){
  var btn = document.getElementById('save-btn');
  btn.textContent = 'Saving...'; btn.disabled = true;
  var cfg = collectConfig();
  fetch('/admin/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(cfg)})
    .then(function(r){
      if(r.ok){ _cfg = cfg; _origJson = JSON.stringify(cfg); btn.textContent = 'Saved \u2713'; showToast('Saved successfully','ok'); setTimeout(function(){btn.textContent='Save Changes';checkDirty();},2000); }
      else{ return r.json().then(function(e){throw new Error((e.errors||[e.error||'Save failed']).join(', '));}); }
    })
    .catch(function(e){ btn.textContent = 'Save Changes'; btn.disabled = false; showToast(e.message,'err'); });
}

function exportConfig(){
  var cfg = collectConfig();
  document.getElementById('export-txt').value = JSON.stringify(cfg, null, 2);
  document.getElementById('export-area').style.display = 'block';
}
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        _record_ping("head")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/data":
            self._serve_json(get_all_data())
        elif self.path == "/api/ping":
            _record_ping(self.headers.get("X-Ping-Source", "get"))
            self._serve_json({"status": "ok", "ts": datetime.now(timezone.utc).isoformat()})
        elif self.path == "/api/ping-log":
            with _ping_log_lock:
                log_copy = list(_ping_log)
            self._serve_json({
                "server_start": _server_start_ts,
                "total_pings": len(log_copy),
                "last_ping": log_copy[-1] if log_copy else None,
                "pings": log_copy,
            })
        elif self.path in ("/admin", "/admin/"):
            if not os.environ.get("ADMIN_PASSWORD"):
                self.send_response(404)
                self.end_headers()
                return
            if not _check_admin_auth(self):
                self._redirect("/admin/login")
                return
            self._serve_html(ADMIN_HTML)
        elif self.path in ("/admin/login", "/admin/login?error=1"):
            error = "error=1" in self.path
            html = LOGIN_HTML.replace("ERROR_MSG", '<p class="err">Incorrect password.</p>' if error else "")
            self._serve_html(html)
        elif self.path == "/admin/logout":
            self.send_response(302)
            self.send_header("Set-Cookie", "admin_token=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict")
            self.send_header("Location", "/admin/login")
            self.end_headers()
        elif self.path == "/admin/api/config":
            if not _check_admin_auth(self):
                self.send_response(401)
                self.end_headers()
                return
            self._serve_json(get_config())
        else:
            self._serve_html(DASHBOARD_HTML)

    def do_POST(self):
        if self.path == "/api/refresh":
            # Invalidate all cache entries so next GET fetches fresh
            with _cache_lock:
                _cache_ts.clear()
            self.send_response(204)
            self.end_headers()
        elif self.path == "/admin/login":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            params = urllib.parse.parse_qs(body)
            password = params.get("password", [""])[0]
            expected = os.environ.get("ADMIN_PASSWORD", "")
            if expected and hmac.compare_digest(password, expected):
                token = _make_token(expected)
                self.send_response(302)
                self.send_header("Set-Cookie", f"admin_token={token}; Max-Age=28800; Path=/; HttpOnly; SameSite=Strict")
                self.send_header("Location", "/admin")
                self.end_headers()
            else:
                self._redirect("/admin/login?error=1")
        elif self.path == "/admin/api/config":
            if not _check_admin_auth(self):
                self.send_response(401)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                self._serve_json({"error": "Invalid JSON"}, status=400)
                return
            is_valid, errors = validate_config(body)
            if not is_valid:
                self._serve_json({"errors": errors}, status=400)
                return
            save_config(body)
            self._serve_json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_json(self, data: dict, status: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress per-request logs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Multi-client campaign dashboard")
    env_port = int(os.environ.get("PORT", PORT))
    parser.add_argument("--port", type=int, default=env_port, help=f"Port (default: {PORT})")
    parser.add_argument("--no-prefetch", action="store_true", help="Skip prefetch on startup")
    args = parser.parse_args()

    load_config()

    if not args.no_prefetch:
        print("Pre-fetching data for all clients...")
        threads = []
        for name in CLIENTS:
            t = threading.Thread(target=_fetch_client, args=(name,), daemon=True)
            t.start()
            threads.append((name, t))
        for name, t in threads:
            t.join(timeout=REQUEST_TIMEOUT + 5)
            status = "OK" if name in _cache_data else f"ERR: {_cache_errors.get(name, '?')}"
            print(f"  {name}: {status}")

    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    server = HTTPServer((host, args.port), Handler)
    print(f"\nClient Dashboard running at http://localhost:{args.port}")
    print(f"  {len(CLIENTS)} clients: {', '.join(CLIENTS.keys())}")
    print(f"  Cache TTL: {CACHE_TTL}s | Auto-refresh: {AUTO_REFRESH_MS//1000}s")
    print("  Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
