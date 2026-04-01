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
from zoneinfo import ZoneInfo

# Campaign analytics use Eastern Time (auto-adjusts for EST/EDT)
EASTERN = ZoneInfo("America/New_York")

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
# Safe numeric coercion — API responses sometimes contain '\\N' or other
# non-numeric strings where numbers are expected (PostgreSQL NULL export
# artifact).  This helper ensures we always get a number back.
# ---------------------------------------------------------------------------

def _safe_num(val, default=0):
    """Coerce a value to a number, returning *default* for None, '\\N', or
    any other non-numeric garbage."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return val
    try:
        return int(val)
    except (ValueError, TypeError):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default


# ---------------------------------------------------------------------------
# Human-readable error messages — raw Python tracebacks confuse AEs.
# ---------------------------------------------------------------------------

_ERROR_MESSAGES = {
    "invalid literal": "Data format error — retrying on next refresh",
    "HTTP 401": "Authentication failed — API key may be invalid",
    "HTTP 403": "Access denied — check API permissions",
    "HTTP 429": "Rate limited — will retry shortly",
    "HTTP 5": "Platform is experiencing issues — will retry",
    "URL error": "Could not reach platform — will retry",
    "JSON decode": "Received unexpected response — will retry",
    "timed out": "Request timed out — will retry",
    "API key not found": "API key not configured",
}


def _friendly_error(raw_error: str) -> str:
    """Map a raw Python exception string to a human-friendly message."""
    lower = raw_error.lower()
    for pattern, message in _ERROR_MESSAGES.items():
        if pattern.lower() in lower:
            return message
    return "Data temporarily unavailable — retrying"


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


def _count_not_contacted_from_analytics(analytics_entry: dict) -> int:
    """Compute not-yet-contacted leads from analytics data.

    not_contacted = leads_count - contacted_count
    This matches Instantly UI and avoids expensive paginated /leads/list calls.
    """
    leads = _safe_num(analytics_entry.get("leads_count"))
    contacted = _safe_num(analytics_entry.get("contacted_count"))
    return max(0, leads - contacted)


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


def _get_step_analytics(client_name: str, headers: dict) -> list:
    """Fetch step analytics with separate 15-min cache."""
    now = time.time()
    with _step_cache_lock:
        ts = _step_cache_ts.get(client_name, 0)
        if (now - ts) < STEP_CACHE_TTL:
            return list(_step_cache_data.get(client_name, []))

    try:
        steps = _http_get(f"{INSTANTLY_BASE}/campaigns/analytics/steps", headers) or []
    except Exception:
        steps = []

    # Filter garbage rows: step is null or string "null"
    clean_steps = [s for s in steps if s.get("step") is not None and str(s.get("step")) != "null"]

    with _step_cache_lock:
        _step_cache_data[client_name] = clean_steps
        _step_cache_ts[client_name] = time.time()

    return clean_steps


def _fetch_campaign_daily(campaign_id: str, date_str: str, headers: dict) -> dict:
    """Fetch daily analytics for a single campaign on a specific date.

    Returns: {sent, first_touch, followups, replies, opps} for that day.
    """
    url = (
        f"{INSTANTLY_BASE}/campaigns/analytics/daily"
        f"?campaign_id={campaign_id}&start_date={date_str}&end_date={date_str}"
        f"&include_opportunities_count=true&limit=10"
    )
    try:
        data = _http_get(url, headers) or []
    except Exception:
        data = []
    row = next((d for d in data if d.get("date") == date_str), {}) if data else {}
    sent = _safe_num(row.get("sent"))
    first_touch = _safe_num(row.get("new_leads_contacted"))
    return {
        "sent": sent,
        "first_touch": first_touch,
        "followups": max(0, sent - first_touch),
        "replies": _safe_num(row.get("replies")),
        "opps": _safe_num(row.get("opportunities")),
    }


def fetch_instantly_data(client_name: str, api_key: str) -> dict:
    """Fetch campaign analytics for a single Instantly workspace."""
    headers = {"Authorization": f"Bearer {api_key}"}

    today = datetime.now(EASTERN).date()
    seven_ago = today - timedelta(days=7)
    today_str = today.isoformat()

    # 1. Campaigns list (for status/active count)
    campaigns = _paginate_instantly(f"{INSTANTLY_BASE}/campaigns", headers)
    active_campaigns = [c for c in campaigns if c.get("status") == 1]
    active_ids = {c.get("id") for c in active_campaigns}

    # 2. All-time analytics per campaign (for lead counts, bounce, pipeline)
    analytics = _paginate_instantly(f"{INSTANTLY_BASE}/campaigns/analytics", headers)
    analytics_by_id = {a.get("campaign_id"): a for a in analytics if a.get("campaign_id")}

    # Active-campaign-only all-time metrics
    active_analytics = [a for a in analytics if a.get("campaign_id") in active_ids]
    active_sent      = sum(_safe_num(c.get("emails_sent_count")) for c in active_analytics)
    active_bounced   = sum(_safe_num(c.get("bounced_count")) for c in active_analytics)
    active_leads     = sum(_safe_num(c.get("leads_count")) for c in active_analytics)
    active_completed = sum(_safe_num(c.get("completed_count")) for c in active_analytics)

    # 3. Per-campaign daily analytics for TODAY (active campaigns only)
    # Fetch in parallel — one API call per active campaign
    daily_by_campaign = {}
    daily_threads = []
    for c in active_campaigns:
        cid = c.get("id", "")
        if not cid:
            continue
        def _worker(camp_id=cid):
            daily_by_campaign[camp_id] = _fetch_campaign_daily(camp_id, today_str, headers)
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        daily_threads.append(t)
    for t in daily_threads:
        t.join(timeout=REQUEST_TIMEOUT)

    # Aggregate today's numbers from per-campaign daily data
    sent_today = sum(d.get("sent", 0) for d in daily_by_campaign.values())
    first_touch_today = sum(d.get("first_touch", 0) for d in daily_by_campaign.values())
    followup_today = sum(d.get("followups", 0) for d in daily_by_campaign.values())
    replies_today = sum(d.get("replies", 0) for d in daily_by_campaign.values())
    opps_today = sum(d.get("opps", 0) for d in daily_by_campaign.values())

    # 4. Workspace-wide daily analytics (last 7 days) for trends
    daily_url = (
        f"{INSTANTLY_BASE}/campaigns/analytics/daily"
        f"?start_date={seven_ago.isoformat()}&end_date={today_str}"
        f"&include_opportunities_count=true&limit=100"
    )
    daily_data = []
    try:
        daily_data = _http_get(daily_url, headers) or []
    except Exception:
        pass

    # 7-day averages (excluding today)
    past_days = [d for d in daily_data if d.get("date", "") < today_str]
    if past_days:
        avg_sent_7d    = sum(_safe_num(d.get("sent")) for d in past_days) / len(past_days)
        avg_replies_7d = sum(_safe_num(d.get("replies")) for d in past_days) / len(past_days)
        avg_opps_7d    = sum(_safe_num(d.get("opportunities")) for d in past_days) / len(past_days)
    else:
        avg_sent_7d = avg_replies_7d = avg_opps_7d = 0.0

    # Rates (today, active campaigns only)
    reply_rate_today = (replies_today / sent_today * 100) if sent_today > 0 else 0.0
    reply_rate_7d    = (avg_replies_7d / avg_sent_7d * 100) if avg_sent_7d > 0 else 0.0
    bounce_rate      = (active_bounced / active_sent * 100) if active_sent > 0 else 0.0

    # 5. Not-yet-contacted leads per campaign (from analytics — no extra API calls)
    nc_by_campaign = {}
    for a in analytics:
        cid = a.get("campaign_id", "")
        if cid:
            nc_by_campaign[cid] = _count_not_contacted_from_analytics(a)
    # Client-level totals: active campaigns only
    not_contacted = sum(nc_by_campaign.get(cid, 0) for cid in active_ids if cid)
    in_progress = sum(
        max(0, _safe_num(a.get("leads_count")) - _safe_num(a.get("completed_count"))
            - _safe_num(a.get("bounced_count")))
        - nc_by_campaign.get(a.get("campaign_id", ""), 0)
        for a in active_analytics
    )

    # Trend direction: compare today vs 7d avg
    opp_trend   = _trend(opps_today, avg_opps_7d)
    reply_trend = _trend(reply_rate_today, reply_rate_7d)
    sent_trend  = _trend(sent_today, avg_sent_7d)

    # (Inactive campaigns no longer need backfill — not_contacted comes from analytics)

    # Build per-campaign list with today's data
    campaigns_list = []
    for c in campaigns:
        cid = c.get("id", "")
        is_active = c.get("status") == 1
        a = analytics_by_id.get(cid, {})
        daily = daily_by_campaign.get(cid, {})
        nc = nc_by_campaign.get(cid, 0)
        leads = _safe_num(a.get("leads_count"))
        completed = _safe_num(a.get("completed_count"))
        bounced = _safe_num(a.get("bounced_count"))
        contacted = _safe_num(a.get("contacted_count"))
        camp_sent_today = daily.get("sent", 0)
        camp_replies_today = daily.get("replies", 0)

        campaigns_list.append({
            "name":           c.get("name", "Unknown"),
            "id":             cid,
            "status":         "active" if is_active else "paused",
            # Today's per-campaign metrics
            "sent_today":     camp_sent_today,
            "first_touch":    daily.get("first_touch", 0),
            "followups":      daily.get("followups", 0),
            "replies_today":  camp_replies_today,
            "opps_today":     daily.get("opps", 0),
            "reply_rate":     round(camp_replies_today / camp_sent_today * 100, 2) if camp_sent_today > 0 else 0.0,
            # Pipeline (current state — from analytics, no extra API calls)
            "not_contacted":  nc,
            "in_progress":    max(0, contacted - completed - bounced),
            # All-time (kept for reference)
            "total_sent":     _safe_num(a.get("emails_sent_count")),
            "total_bounced":  bounced,
        })

    return {
        "platform": "instantly",
        "active_campaigns": len(active_campaigns),
        "total_campaigns": len(campaigns),

        # Today's metrics (aggregated from per-campaign daily data, active only)
        "sent_today":        sent_today,
        "first_touch_today": first_touch_today,
        "followup_today":    followup_today,
        "replies_today":     replies_today,
        "opps_today":        opps_today,

        # Rates (active campaigns only)
        "reply_rate_today": round(reply_rate_today, 2),
        "reply_rate_7d":    round(reply_rate_7d, 2),
        "bounce_rate":      round(bounce_rate, 2),

        # Pipeline (active campaigns only)
        "not_contacted": not_contacted,
        "in_progress":   in_progress,

        # 7-day averages (for trends)
        "avg_sent_7d":    round(avg_sent_7d, 1),
        "avg_replies_7d": round(avg_replies_7d, 1),
        "avg_opps_7d":    round(avg_opps_7d, 1),

        # Trend indicators
        "opp_trend":   opp_trend,
        "reply_trend": reply_trend,
        "sent_trend":  sent_trend,

        # Per-campaign breakdown (with today's data)
        "campaigns": campaigns_list,

        # Daily breakdown (workspace-wide, last 7 days for sparklines)
        "daily": [
            {
                "date":    d.get("date"),
                "sent":    _safe_num(d.get("sent")),
                "opps":    _safe_num(d.get("opportunities")),
                "replies": _safe_num(d.get("replies")),
            }
            for d in sorted(daily_data, key=lambda x: x.get("date", ""))
        ],

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

    today = datetime.now(EASTERN).date()
    seven_ago = today - timedelta(days=7)

    # 1. Campaign list — no pagination, returns flat data array
    raw = _http_get(f"{EB_BASE}/campaigns", headers)
    campaigns_all = raw.get("data", []) if isinstance(raw, dict) else []

    # Status is capitalized ("Active", "Paused", etc.) — compare case-insensitively
    active_campaigns = [c for c in campaigns_all if c.get("status", "").lower() == "active"]
    all_cids = [c["id"] for c in campaigns_all if c.get("id")]
    active_cids_list = [c["id"] for c in active_campaigns if c.get("id")]

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

    # Use active campaign IDs only; fall back to all_cids if no active campaigns
    stats_cids = active_cids_list if active_cids_list else all_cids
    stats_7d    = _eb_events_stats(seven_ago.isoformat(), today.isoformat(), stats_cids)
    stats_today = _eb_events_stats(today.isoformat(), today.isoformat(), stats_cids)

    sent_today    = _safe_num(stats_today.get("sent"))
    replies_today = _safe_num(stats_today.get("replied"))
    opps_today    = _safe_num(stats_today.get("interested"))
    opens_today   = _safe_num(stats_today.get("opens"))

    # 7-day totals excluding today
    sent_7d    = _safe_num(stats_7d.get("sent")) - sent_today
    replies_7d = _safe_num(stats_7d.get("replied")) - replies_today
    opps_7d    = _safe_num(stats_7d.get("interested")) - opps_today
    days_in_range = 6  # 7-day window minus today

    avg_sent_7d  = sent_7d / days_in_range if days_in_range > 0 else 0.0
    avg_opps_7d  = opps_7d / days_in_range if days_in_range > 0 else 0.0
    avg_reply_7d = replies_7d / days_in_range if days_in_range > 0 else 0.0

    # 3. Not-contacted leads — correct filter param is filters[lead_campaign_status]=never_contacted
    nc_data = _http_get(
        f"{EB_BASE}/leads?filters%5Blead_campaign_status%5D=never_contacted&page=1", headers
    ) or {}
    not_contacted_meta = nc_data.get("meta", {}) if isinstance(nc_data, dict) else {}
    not_contacted = _safe_num(not_contacted_meta.get("total"))

    # Reply rates
    reply_rate_today = (replies_today / sent_today * 100) if sent_today > 0 else 0.0
    reply_rate_7d    = (avg_reply_7d / avg_sent_7d * 100) if avg_sent_7d > 0 else 0.0

    # Bounce rate from 7d stats
    bounced_7d    = _safe_num(stats_7d.get("bounced"))
    total_sent_7d = _safe_num(stats_7d.get("sent"))
    bounce_rate   = (bounced_7d / total_sent_7d * 100) if total_sent_7d > 0 else 0.0

    opp_trend   = _trend(opps_today, avg_opps_7d)
    reply_trend = _trend(reply_rate_today, reply_rate_7d)
    sent_trend  = _trend(sent_today, avg_sent_7d)

    # 4. Per-campaign today stats via campaign-events/stats with single campaign_id
    today_str = today.isoformat()
    active_camp_objs = [c for c in campaigns_all if c.get("status", "").lower() == "active"]
    paused_camp_objs = [c for c in campaigns_all if c.get("status", "").lower() != "active"][:5]
    campaigns_to_fetch = active_camp_objs + paused_camp_objs

    def _fetch_eb_campaign_today(c: dict) -> dict:
        cid = c.get("id", "")
        # Today's stats for this campaign
        camp_today = _eb_events_stats(today_str, today_str, [cid]) if cid else {}
        camp_sent = _safe_num(camp_today.get("sent"))
        camp_replies = _safe_num(camp_today.get("replied"))
        camp_opps = _safe_num(camp_today.get("interested"))
        camp_bounced = _safe_num(camp_today.get("bounced"))
        return {
            "name":          c.get("name", "Unknown"),
            "id":            cid,
            "status":        c.get("status", "unknown").lower(),
            "sent_today":    camp_sent,
            "first_touch":   0,  # EmailBison doesn't expose first-touch vs follow-up
            "followups":     0,
            "replies_today": camp_replies,
            "opps_today":    camp_opps,
            "reply_rate":    round(camp_replies / camp_sent * 100, 2) if camp_sent > 0 else 0.0,
            "not_contacted": 0,  # Not available per-campaign in EB
            "in_progress":   0,
            "total_sent":    0,
            "total_bounced": camp_bounced,
        }

    # Fetch per-campaign stats in parallel
    campaign_results: list = [None] * len(campaigns_to_fetch)
    stat_threads = []
    for idx, c in enumerate(campaigns_to_fetch):
        def _worker(i=idx, camp=c):
            campaign_results[i] = _fetch_eb_campaign_today(camp)
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

        # Today's metrics (active campaigns only)
        "sent_today":        sent_today,
        "first_touch_today": 0,  # EmailBison doesn't expose first-touch vs follow-up
        "followup_today":    0,
        "replies_today":     replies_today,
        "opps_today":        opps_today,

        # Rates (active campaigns only)
        "reply_rate_today": round(reply_rate_today, 2),
        "reply_rate_7d":    round(reply_rate_7d, 2),
        "bounce_rate":      round(bounce_rate, 2),

        # Pipeline
        "not_contacted": not_contacted,
        "in_progress":   None,  # Not available in EmailBison

        # 7-day averages (for trends)
        "avg_sent_7d":    round(avg_sent_7d, 1),
        "avg_replies_7d": round(avg_reply_7d, 1),
        "avg_opps_7d":    round(avg_opps_7d, 1),

        # Trend indicators
        "opp_trend":   opp_trend,
        "reply_trend": reply_trend,
        "sent_trend":  sent_trend,

        # Per-campaign breakdown (with today's data)
        "campaigns": campaigns_list,

        "daily": [],
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

_step_cache_lock = threading.Lock()
_step_cache_data = {}   # {client_name: list}
_step_cache_ts   = {}   # {client_name: float}
STEP_CACHE_TTL   = 900  # 15 minutes


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
                # Update per-campaign entry and recalculate campaign-level in_progress
                for camp in data.get("campaigns", []):
                    if camp.get("id") == cid:
                        camp["not_contacted"] = count
                        camp["in_progress"] = max(
                            0,
                            camp.get("leads", 0) - camp.get("completed", 0)
                            - camp.get("bounced", 0) - count
                        )
                        break
                # Recalculate client-level in_progress
                total_nc = sum(c.get("not_contacted", 0) for c in data.get("campaigns", []))
                total_leads_c = sum(c.get("leads", 0) for c in data.get("campaigns", []))
                total_completed_c = sum(c.get("completed", 0) for c in data.get("campaigns", []))
                total_bounced_c = sum(c.get("bounced", 0) for c in data.get("campaigns", []))
                data["in_progress"] = max(0, total_leads_c - total_completed_c - total_bounced_c - total_nc)


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
            _cache_errors[client_name] = _friendly_error(str(exc))
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


_MOCK_MODE = False


def _load_mock_data() -> dict:
    """Load canned data from tests/fixtures/mock_api_data.json."""
    mock_path = Path(__file__).parent / "tests" / "fixtures" / "mock_api_data.json"
    return json.loads(mock_path.read_text(encoding="utf-8"))


def get_all_data() -> dict:
    """Return cached data instantly — never blocks on API fetches."""
    if _MOCK_MODE:
        return _load_mock_data()

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
# HTML templates — loaded from templates/ directory
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _load_template(name: str) -> str:
    return (_TEMPLATE_DIR / name).read_text(encoding="utf-8")


DASHBOARD_HTML = _load_template("dashboard.html").replace("REFRESH_INTERVAL_MS", str(AUTO_REFRESH_MS))
LOGIN_HTML = _load_template("login.html")
ADMIN_HTML = _load_template("admin.html")




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
            # Invalidate cache AND clear stale data so clients see "Loading..."
            with _cache_lock:
                _cache_ts.clear()
                _cache_data.clear()
                _cache_errors.clear()
            # Kick off immediate re-fetch in background threads
            for name in CLIENTS:
                t = threading.Thread(target=_fetch_client, args=(name,), daemon=True)
                t.start()
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
    parser.add_argument("--mock", action="store_true", help="Serve deterministic mock data (for QA screenshots)")
    args = parser.parse_args()

    if args.mock:
        global _MOCK_MODE
        _MOCK_MODE = True
        print("Mock mode enabled — serving canned data from tests/fixtures/mock_api_data.json")

    load_config()

    if not args.no_prefetch and not args.mock:
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
