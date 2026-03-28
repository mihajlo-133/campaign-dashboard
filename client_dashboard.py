"""
Multi-Client Email Campaign Dashboard

Real-time performance monitor for 6 Instantly and 2 EmailBison workspaces.
Fetches live data, caches for 5 minutes, serves a single-page dashboard.

Usage:
  python gtm/scripts/client_dashboard.py             # port 8060
  python gtm/scripts/client_dashboard.py --port 8061
"""

import argparse
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

    # Count not-yet-contacted leads using the leads/list API with
    # FILTER_VAL_NOT_CONTACTED — accurate per-campaign counts.
    nc_by_campaign = {}
    for c in campaigns:
        cid = c.get("id", "")
        if cid:
            nc_by_campaign[cid] = _count_not_contacted(cid, headers)
    not_contacted = sum(nc_by_campaign.values())
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
    }


# ---------------------------------------------------------------------------
# EmailBison data fetcher
# ---------------------------------------------------------------------------

EB_BASE = "https://dedi.emailbison.com/api"


def fetch_emailbison_data(client_name: str, api_key: str) -> dict:
    """Fetch campaign analytics for a single EmailBison workspace."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    today = datetime.now(timezone.utc).date()
    seven_ago = today - timedelta(days=7)

    # 1. Campaign list
    campaigns_all = []
    page = 1
    while True:
        data = _http_get(f"{EB_BASE}/campaigns?page={page}", headers)
        items = data.get("data", []) if isinstance(data, dict) else []
        campaigns_all.extend(items)
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        if page >= meta.get("last_page", 1):
            break
        page += 1

    active_campaigns = [c for c in campaigns_all if c.get("status") == "active"]

    # 2. Aggregate stats via campaign-events endpoint
    stats_url = (
        f"{EB_BASE}/campaign-events/stats"
        f"?start_date={seven_ago.isoformat()}&end_date={today.isoformat()}"
    )
    stats = _http_get(stats_url, headers) or {}
    stats_data = stats.get("data", stats) if isinstance(stats, dict) else {}

    # Today's campaign-events stats
    today_url = (
        f"{EB_BASE}/campaign-events/stats"
        f"?start_date={today.isoformat()}&end_date={today.isoformat()}"
    )
    today_stats_raw = _http_get(today_url, headers) or {}
    today_stats = today_stats_raw.get("data", today_stats_raw) if isinstance(today_stats_raw, dict) else {}

    sent_today   = today_stats.get("sent", 0) or 0
    replies_today = today_stats.get("replies", 0) or 0
    opps_today   = today_stats.get("opportunities", 0) or 0
    opens_today  = today_stats.get("opens", 0) or 0

    # 7-day totals (divide by 7 for avg, subtract today)
    sent_7d     = (stats_data.get("sent", 0) or 0) - sent_today
    replies_7d  = (stats_data.get("replies", 0) or 0) - replies_today
    opps_7d     = (stats_data.get("opportunities", 0) or 0) - opps_today
    days_in_range = 6  # 7 days minus today

    avg_sent_7d  = sent_7d / days_in_range if days_in_range > 0 else 0.0
    avg_opps_7d  = opps_7d / days_in_range if days_in_range > 0 else 0.0
    avg_reply_7d = replies_7d / days_in_range if days_in_range > 0 else 0.0

    # 3. Not-contacted leads
    nc_data = _http_get(f"{EB_BASE}/leads?status=not_contacted&page=1", headers) or {}
    not_contacted_meta = nc_data.get("meta", {}) if isinstance(nc_data, dict) else {}
    # total leads with not_contacted status
    not_contacted = not_contacted_meta.get("total", 0) or 0

    # Reply rates
    reply_rate_today = (replies_today / sent_today * 100) if sent_today > 0 else 0.0
    reply_rate_7d    = (avg_reply_7d / avg_sent_7d * 100) if avg_sent_7d > 0 else 0.0

    # Bounced / total sent from 7d stats
    bounced_7d = stats_data.get("bounced", 0) or 0
    total_sent_7d = stats_data.get("sent", 0) or 0
    bounce_rate = (bounced_7d / total_sent_7d * 100) if total_sent_7d > 0 else 0.0

    opp_trend   = _trend(opps_today, avg_opps_7d)
    reply_trend = _trend(reply_rate_today, reply_rate_7d)
    sent_trend  = _trend(sent_today, avg_sent_7d)

    # 4. Per-campaign stats — active campaigns + up to 5 most recent paused
    active_cids = [c for c in campaigns_all if c.get("status") == "active"]
    paused_cids = [c for c in campaigns_all if c.get("status") != "active"][:5]
    campaigns_to_fetch = active_cids + paused_cids

    def _fetch_eb_campaign_stats(c: dict) -> dict:
        cid = c.get("id", "")
        try:
            s = _http_get(
                f"{EB_BASE}/campaigns/{cid}/stats"
                f"?start_date={seven_ago.isoformat()}&end_date={today.isoformat()}",
                headers,
            ) or {}
            s_data = s.get("data", s) if isinstance(s, dict) else {}
        except Exception:
            s_data = {}
        return {
            "name":    c.get("name", "Unknown"),
            "id":      cid,
            "status":  c.get("status", "unknown"),
            "sent":    s_data.get("sent", 0) or 0,
            "replies": s_data.get("replies", 0) or 0,
            "bounced": s_data.get("bounced", 0) or 0,
            "opps":    s_data.get("opportunities", 0) or 0,
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
    kpi = KPI_TARGETS.get(client_name, {})
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
        if sent_ratio < SENT_PCT_RED:
            return "red"
        if sent_ratio < SENT_PCT_WARN:
            return "amber"

    # Reply rate (only classify if meaningful sample)
    rr = data.get("reply_rate_today", 0)
    if sent_today > 50:
        if rr < REPLY_RATE_RED:
            return "red"
        if rr < REPLY_RATE_WARN:
            return "amber"

    # Bounce rate
    br = data.get("bounce_rate", 0)
    if br > BOUNCE_RATE_RED:
        return "red"
    if br > BOUNCE_RATE_WARN:
        return "amber"

    # Lead pool runway (days remaining)
    pool_days = _pool_days_remaining(data, client_name)
    if pool_days < POOL_DAYS_RED:
        return "red"
    if pool_days < POOL_DAYS_WARN:
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
        result["kpi"]    = KPI_TARGETS.get(client_name, {})
        result["fetched_at"] = datetime.now(timezone.utc).isoformat()

        with _cache_lock:
            _cache_data[client_name]   = result
            _cache_ts[client_name]     = time.time()
            _cache_errors.pop(client_name, None)

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
:root{
  --bg:#f4f4f4;--bg-el:#ffffff;--bg-hov:#f9f9f9;--bg-sel:#f0f4ff;
  --bd:#e1e2e3;--bd-s:#d0d1d2;
  --tx1:#000000;--tx2:#4d4d4d;--tx3:#909090;
  --blue:#2756f7;--blue-h:#1679fa;--blue-bg:#e8eeff;
  --green:#34C759;--amber:#f59e0b;--red:#C33939;
  --sh:0 0.6px 0.6px -1.25px rgba(0,0,0,.09),0 2.3px 2.3px -2.5px rgba(0,0,0,.08),0 10px 10px -3.75px rgba(0,0,0,.03);
  --sh-md:0 4px 12px rgba(0,0,0,.06);
  --sh-lg:0 10px 25px -5px rgba(0,0,0,.08);
}
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
.btn{display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 18px;border-radius:12px;border:none;background:linear-gradient(180deg,#1679fa -23%,#0a61d1 100%);color:#fff;font-size:13px;font-weight:600;cursor:pointer;transition:opacity .15s,transform .1s;font-family:'Inter',sans-serif;box-shadow:0 2px 8px rgba(22,121,250,.25)}
.btn:hover{opacity:.92;transform:translateY(-1px)}
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
thead tr{background:#fafafa}
thead th{padding:12px 16px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);text-align:left;white-space:nowrap;cursor:pointer;user-select:none;transition:color .15s;border-bottom:1px solid var(--bd);font-family:'Space Mono',monospace}
thead th.num{text-align:right}
thead th:hover{color:var(--tx1)}
thead th.sort-asc::after{content:' \2191';color:var(--blue)}
thead th.sort-desc::after{content:' \2193';color:var(--blue)}
tbody tr{height:52px;cursor:pointer;transition:background .12s}
tbody tr:hover{background:var(--bg-hov)}
tbody tr.selected{background:var(--bg-sel);box-shadow:inset 3px 0 0 var(--blue)}
tbody tr.err-row{cursor:default}
tbody tr.err-row:hover{background:transparent}
td{padding:0 16px;font-size:13px;color:var(--tx1);white-space:nowrap;border-bottom:1px solid var(--bd)}
tbody tr:last-child td{border-bottom:none}
td.num{text-align:right;font-family:'Space Mono',monospace;font-size:13px}
.client-name{font-weight:600;font-size:13px;letter-spacing:-.01em;font-family:'Space Grotesk',sans-serif}
.client-plat{font-size:11px;color:var(--tx3);letter-spacing:.02em;text-transform:uppercase;margin-top:1px;font-family:'Space Mono',monospace}
.cell-val{font-family:'Space Mono',monospace}
.cell-val.g{color:#29753c}.cell-val.a{color:#d97706}.cell-val.r{color:#C33939}.cell-val.m{color:var(--tx3)}
.trend{font-size:10px;margin-left:3px}
.trend-u{color:#29753c}.trend-d{color:#C33939}.trend-f{color:var(--tx3)}
.pill{display:inline-flex;align-items:center;height:24px;padding:0 10px;border-radius:6px;font-size:11px;font-weight:600;letter-spacing:.02em}
.pill-g{background:rgba(52,199,89,.08);color:#29753c;border:1px solid rgba(52,199,89,.2)}
.pill-a{background:rgba(245,158,11,.08);color:#d97706;border:1px solid rgba(245,158,11,.2)}
.pill-r{background:rgba(195,57,57,.08);color:#C33939;border:1px solid rgba(195,57,57,.2)}
.pill-m{background:var(--bg-el);color:var(--tx3);border:1px solid var(--bd)}
/* Skeleton */
.skel{background:linear-gradient(90deg,#f1f5f9 25%,#e2e8f0 50%,#f1f5f9 75%);background-size:200% 100%;animation:shimmer 1.5s infinite;border-radius:4px;display:inline-block}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
/* Tooltip */
[data-tip]{position:relative}
[data-tip]::after{content:attr(data-tip);position:absolute;bottom:calc(100% + 6px);left:50%;transform:translateX(-50%);background:#000;color:#fff;font-size:11px;padding:6px 12px;border-radius:8px;border:none;box-shadow:var(--sh-md);white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .12s;z-index:100;letter-spacing:normal;text-transform:none;font-family:'Inter',sans-serif}
[data-tip]:hover::after{opacity:1}
/* Expandable row */
.row-chevron{display:inline-block;font-size:11px;color:var(--tx3);transition:transform .2s ease;margin-left:4px}
tbody tr.expanded .row-chevron{transform:rotate(90deg)}
tr.expand-row{display:none}
tr.expand-row.visible{display:table-row}
.expand-row td{padding:0!important;border:none!important;height:0;line-height:0}
.expand-panel{max-height:0;overflow:hidden;transition:max-height .22s ease;background:#fafafa;border-left:3px solid var(--blue)}
.expand-panel.open{max-height:2000px}
.expand-inner{padding:24px 28px 28px}
/* KPI cards row */
.exp-kpis{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}
.exp-kpi{background:#fff;border:1px solid var(--bd);border-radius:12px;padding:16px 20px;flex:1;min-width:140px;box-shadow:var(--sh)}
.exp-kpi-label{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);font-weight:600;margin-bottom:6px;font-family:'Space Mono',monospace}
.exp-kpi-val{font-size:24px;font-weight:700;font-family:'Space Grotesk',sans-serif;letter-spacing:-.03em;line-height:1.1;color:var(--tx1)}
.exp-kpi-val.g{color:#29753c}.exp-kpi-val.a{color:#d97706}.exp-kpi-val.r{color:#C33939}
.exp-kpi-sub{font-size:11px;color:var(--tx3);margin-top:6px}
.exp-kpi-bar{height:3px;background:var(--bd);border-radius:2px;overflow:hidden;margin-top:10px}
.exp-kpi-bar-fill{height:100%;border-radius:2px;transition:width .4s}
.exp-kpi-bar-fill.g{background:var(--green)}.exp-kpi-bar-fill.a{background:var(--amber)}.exp-kpi-bar-fill.r{background:var(--red)}
/* Campaign sub-table */
.exp-section-label{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);font-weight:600;margin-bottom:12px;font-family:'Space Mono',monospace}
.camp-table{width:100%;border-collapse:collapse;font-size:12px;background:#fff;border-radius:8px;overflow:hidden;border:1px solid var(--bd)}
.camp-table th{padding:8px 12px;font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--tx3);font-weight:600;text-align:left;border-bottom:1px solid var(--bd);font-family:'Space Mono',monospace}
.camp-table th.num{text-align:right}
.camp-table td{padding:10px 12px;color:var(--tx1);border-bottom:1px solid var(--bd);vertical-align:middle;height:38px}
.camp-table td.num{text-align:right;font-family:'Space Mono',monospace}
.camp-table tr:last-child td{border-bottom:none}
.camp-table tr:hover td{background:rgba(0,0,0,.015)}
.camp-name{font-weight:500;white-space:nowrap}
.camp-status-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;flex-shrink:0;vertical-align:middle}
.camp-status-active{background:#22c55e}.camp-status-paused{background:#94a3b8}
/* Campaign group headers */
.camp-group-hdr{cursor:pointer;user-select:none;transition:background .12s}
.camp-group-hdr:hover{background:rgba(0,0,0,.03)}
.camp-group-hdr td{padding:10px 12px!important;font-size:12px;font-weight:600;color:var(--tx2);border-bottom:1px solid var(--bd);font-family:'Space Grotesk',sans-serif}
.camp-group-hdr .camp-chev{display:inline-block;font-size:9px;color:var(--tx3);margin-right:8px;transition:transform .2s}
.camp-group-hdr.open .camp-chev{transform:rotate(90deg)}
.camp-group-hdr .camp-group-count{font-weight:400;color:var(--tx3);font-size:11px;margin-left:4px}
.camp-group-row{display:none}
.camp-group-row.visible{display:table-row}
/* Alerts in expanded */
.d-alert{padding:10px 14px;border-radius:8px;font-size:12px;line-height:1.6;margin-bottom:8px}
.d-alert.r{background:rgba(195,57,57,.05);border:1px solid rgba(195,57,57,.15);color:#C33939}
.d-alert.a{background:rgba(245,158,11,.05);border:1px solid rgba(245,158,11,.15);color:#d97706}
@media(max-width:768px){.shell{padding:0 16px 24px}.exp-kpis{flex-direction:column}}
@media(max-width:480px){.chips{display:none}}
</style>
</head>
<body>
<div class="shell">
<div class="topbar">
  <div class="logo"><span class="logo-icon"><svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C8 7 4 10 4 14a8 8 0 0016 0c0-4-4-7-8-12z" fill="#fff"/></svg></span>Prospeqt</div>
  <span class="topbar-mid" id="ts">--</span>
  <button class="btn" onclick="forceRefresh()" id="refresh-btn">
    <span class="icon-ref">&#x21BB; Refresh</span>
    <span class="spin"></span>
  </button>
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
          <th data-col="platform">Platform</th>
          <th class="num" data-col="sent_today" data-tip="Emails sent today across all active campaigns">Sent Today</th>
          <th class="num" data-col="not_contacted" data-tip="Leads that haven&#39;t completed the sequence yet (in progress + not contacted)">Remaining</th>
          <th class="num" data-col="reply_rate_today" data-tip="% of emails sent today that received a reply">Reply Rate</th>
          <th class="num" data-col="opps_today" data-tip="Positive replies indicating genuine interest">Opps</th>
          <th class="num" data-col="bounce_rate" data-tip="% of all-time sent emails that bounced">Bounce</th>
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
</div>
<script>
var REFRESH_MS = REFRESH_INTERVAL_MS;
var _rt = null;
var _allData = {};
var _sortCol = 'status', _sortDir = 1;
var _expanded = null;
var KPI = {
  'MyPlace':           {sent:2000, not_contacted:1000,  opps_per_day:4.0, reply_rate:1.5},
  'SwishFunding':      {sent:10000,not_contacted:10000, opps_per_day:9.0, reply_rate:1.3},
  'SmartMatchApp':     {sent:2000, not_contacted:2000,  opps_per_day:2.0, reply_rate:1.5},
  'HeyReach':          {sent:2000, not_contacted:2000,  opps_per_day:2.0, reply_rate:1.5},
  'Kayse':             {sent:2000, not_contacted:2000,  opps_per_day:2.0, reply_rate:1.5},
  'Prosperly':         {sent:2000, not_contacted:2000,  opps_per_day:2.0, reply_rate:1.5},
  'RankZero':          {sent:2000, not_contacted:2000,  opps_per_day:2.0, reply_rate:1.5},
  'SwishFunding (EB)': {sent:2000, not_contacted:2000,  opps_per_day:2.0, reply_rate:1.5}
};
function fmt(n){return n==null?'--':Number(n).toLocaleString('en-US')}
function fmtPct(n,d){return n==null?'--':Number(n).toFixed(d!=null?d:2)+'%'}
function fmtDec(n,d){return n==null?'--':Number(n).toFixed(d!=null?d:1)}
function clientStatus(d){return d.status==='loading'?'loading':d.error?'error':(d.status||'error')}
function statusOrder(s){return s==='red'?0:s==='amber'?1:s==='green'?2:3}
function sentCls(v,k){if(!k)return 'm';var r=v/k;return r>=0.9?'g':r>=0.7?'a':'r'}
function rrCls(r){return r>=1.0?'g':r>=0.5?'a':'r'}
function ncCls(nc,s,a){var rate=s>0?s:(a||0);var d=rate>0?nc/rate:Infinity;return d>=7?'g':d>=3?'a':'r'}
function bounceCls(b){return b>5?'r':b>3?'a':'m'}
function oppsCls(t,a){return t>=(a||0)*0.9?'g':'a'}
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
  return '<span class="pill pill-m">Error</span>';
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
    var d=data[name],s=clientStatus(d),kpi=KPI[name]||{};
    var isExp=_expanded===name;
    if(d.error){
      rows+='<tr class="err-row" data-name="'+name+'">';
      rows+='<td><div class="client-name" style="color:var(--tx3)">'+name+'</div><div class="client-plat">'+(d.platform||'')+'</div></td>';
      rows+='<td><span style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--tx3)">'+(d.platform==='instantly'?'Instantly':'EmailBison')+'</span></td>';
      rows+='<td class="num" colspan="5"><span style="color:var(--tx3);font-size:12px">'+d.error+'</span></td>';
      rows+='<td>'+pill('error')+'</td><td></td></tr>';
      return;
    }
    var sc=sentCls(d.sent_today||0,kpi.sent),rc=rrCls(d.reply_rate_today||0);
    var nc=ncCls(d.not_contacted||0,d.sent_today||0,d.avg_sent_7d||0);
    var bc=bounceCls(d.bounce_rate||0),oc=oppsCls(d.opps_today||0,d.avg_opps_7d||0);
    var selCls=isExp?' selected':'';
    var expCls=isExp?' expanded':'';
    rows+='<tr data-name="'+name+'" class="'+selCls+expCls+'" onclick="toggleRow(this,\''+name+'\')">';
    rows+='<td><div class="client-name">'+name+'</div><div class="client-plat">'+(d.platform||'')+'</div></td>';
    rows+='<td><span style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--tx3)">'+(d.platform==='instantly'?'Instantly':'EmailBison')+'</span></td>';
    rows+='<td class="num"><span class="cell-val '+sc+'">'+fmt(d.sent_today)+'</span>'+trend(d.sent_trend)+'</td>';
    rows+='<td class="num"><span class="cell-val '+nc+'">'+fmt(d.not_contacted)+'</span></td>';
    rows+='<td class="num"><span class="cell-val '+rc+'">'+fmtPct(d.reply_rate_today)+'</span>'+trend(d.reply_trend)+'</td>';
    rows+='<td class="num"><span class="cell-val '+oc+'">'+fmt(d.opps_today)+'</span>'+trend(d.opp_trend)+'</td>';
    rows+='<td class="num"><span class="cell-val '+bc+'">'+fmtPct(d.bounce_rate)+'</span></td>';
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
  h+='<td><span class="camp-name" title="'+c.name+'">'+c.name+'</span></td>';
  h+='<td style="white-space:nowrap"><span class="camp-status-dot '+dotCls+'"></span>'+(isActive?'Active':'Paused')+'</td>';
  h+='<td class="num">'+fmt(c.sent)+'</td>';
  h+='<td class="num" style="color:'+(c.not_contacted>0?'#d97706':'var(--tx3)')+'">'+nc+'</td>';
  h+='<td class="num" style="color:'+(c.replies>0?'#29753c':'var(--tx3)')+'">'+fmt(c.replies)+'</td>';
  h+='<td class="num" style="color:'+(c.bounced>0?'#C33939':'var(--tx3)')+'">'+fmt(c.bounced)+'</td>';
  h+='<td class="num" style="color:'+(c.opps>0?'#29753c':'var(--tx3)')+'">'+fmt(c.opps)+'</td>';
  h+='<td class="num">'+rr+'</td>';
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
    h+='<tr class="camp-group-hdr" onclick="toggleCampGroup(this,\''+gid+'\')">';
    h+='<td colspan="8"><span class="camp-chev">&#9658;</span>Paused<span class="camp-group-count">('+paused.length+')</span></td></tr>';
    paused.forEach(function(c){h+='<tr class="camp-group-row" data-group="'+gid+'">'+buildCampaignRow(c).replace(/^<tr>/,'').replace(/<\/tr>$/,'')+'</tr>'});
  }
  // Other (completed, unknown, etc.): collapsed group
  if(other.length){
    var gid2='cg'+(_campGroupId++);
    h+='<tr class="camp-group-hdr" onclick="toggleCampGroup(this,\''+gid2+'\')">';
    h+='<td colspan="8"><span class="camp-chev">&#9658;</span>Other<span class="camp-group-count">('+other.length+')</span></td></tr>';
    other.forEach(function(c){h+='<tr class="camp-group-row" data-group="'+gid2+'">'+buildCampaignRow(c).replace(/^<tr>/,'').replace(/<\/tr>$/,'')+'</tr>'});
  }
  h+='</tbody></table>';
  return h;
}
function toggleCampGroup(hdr,gid){
  var isOpen=hdr.classList.toggle('open');
  var rows=hdr.closest('table').querySelectorAll('tr[data-group="'+gid+'"]');
  rows.forEach(function(r){isOpen?r.classList.add('visible'):r.classList.remove('visible')});
}
function buildAlerts(name,d){
  var alerts=[],kpi=KPI[name]||{};
  var nc=d.not_contacted||0,sentToday=d.sent_today||0,avg7d=d.avg_sent_7d||0;
  var rate=sentToday>0?sentToday:avg7d,poolD=rate>0?nc/rate:Infinity;
  if(poolD<3) alerts.push({cls:'r',msg:'Lead pool critical ('+fmtDec(poolD,1)+'d) \u2014 upload leads immediately'});
  else if(poolD<7) alerts.push({cls:'a',msg:'Lead pool low ('+fmtDec(poolD,1)+'d) \u2014 plan lead upload soon'});
  var rr=d.reply_rate_today||0;
  if(sentToday>50&&rr<0.5) alerts.push({cls:'r',msg:'Reply rate very low ('+fmtPct(rr)+') \u2014 check deliverability or copy'});
  else if(sentToday>50&&rr<1.0) alerts.push({cls:'a',msg:'Reply rate below target ('+fmtPct(rr)+') \u2014 review copy or segments'});
  if((d.active_campaigns||0)===0&&(d.total_campaigns||0)>0) alerts.push({cls:'r',msg:'No active campaigns \u2014 check campaign status'});
  if((d.active_campaigns||0)>0&&sentToday===0) alerts.push({cls:'r',msg:'Campaigns active but nothing sent \u2014 check sending accounts'});
  var br=d.bounce_rate||0;
  if(br>5) alerts.push({cls:'r',msg:'Bounce rate '+fmtPct(br)+' \u2014 data quality issue'});
  else if(br>3) alerts.push({cls:'a',msg:'Bounce rate elevated ('+fmtPct(br)+') \u2014 monitor closely'});
  return alerts;
}
function buildExpandContent(name,d){
  var kpi=KPI[name]||{},h='';
  if(d.error){return '<div class="d-alert r">'+d.error+'</div>';}
  // Row 1: KPI metric cards
  h+='<div class="exp-kpis">';
  var sc=sentCls(d.sent_today||0,kpi.sent),sentPct=kpi.sent>0?Math.min(100,Math.round(((d.sent_today||0)/kpi.sent)*100)):null;
  h+='<div class="exp-kpi"><div class="exp-kpi-label">Sent Today</div><div class="exp-kpi-val '+sc+'">'+fmt(d.sent_today)+'</div>';
  h+='<div class="exp-kpi-sub">KPI: '+fmt(kpi.sent||0)+(sentPct!=null?' &middot; '+sentPct+'%':'')+'</div>';
  if(sentPct!=null)h+='<div class="exp-kpi-bar"><div class="exp-kpi-bar-fill '+sc+'" style="width:'+sentPct+'%"></div></div>';
  h+='</div>';
  var ncR=ncCls(d.not_contacted||0,d.sent_today||0,d.avg_sent_7d||0);
  var rate2=(d.sent_today>0?d.sent_today:(d.avg_sent_7d||0)),poolD2=rate2>0?(d.not_contacted||0)/rate2:null;
  var poolLabel=poolD2!=null?(poolD2>99?'>99d':fmtDec(poolD2,1)+'d remaining'):'-- remaining';
  h+='<div class="exp-kpi"><div class="exp-kpi-label">Lead Pool</div><div class="exp-kpi-val '+ncR+'">'+fmt(d.not_contacted)+'</div>';
  h+='<div class="exp-kpi-sub">'+poolLabel+' at current pace</div></div>';
  var rc=rrCls(d.reply_rate_today||0),rrPct=kpi.reply_rate>0?Math.min(200,Math.round(((d.reply_rate_today||0)/kpi.reply_rate)*100)):null;
  h+='<div class="exp-kpi"><div class="exp-kpi-label">Reply Rate</div><div class="exp-kpi-val '+rc+'">'+fmtPct(d.reply_rate_today)+'</div>';
  h+='<div class="exp-kpi-sub">Target: '+fmtPct(kpi.reply_rate||0)+(rrPct!=null?' &middot; '+rrPct+'%':'')+'</div>';
  if(rrPct!=null)h+='<div class="exp-kpi-bar"><div class="exp-kpi-bar-fill '+rc+'" style="width:'+Math.min(100,rrPct)+'%"></div></div>';
  h+='</div>';
  var oc=oppsCls(d.opps_today||0,d.avg_opps_7d||0);
  h+='<div class="exp-kpi"><div class="exp-kpi-label">Opportunities</div><div class="exp-kpi-val '+oc+'">'+fmt(d.opps_today)+'</div>';
  h+='<div class="exp-kpi-sub">Target: '+fmtDec(kpi.opps_per_day||0,1)+'/day &middot; 7d avg: '+fmtDec(d.avg_opps_7d,1)+'</div></div>';
  var bc=bounceCls(d.bounce_rate||0);
  h+='<div class="exp-kpi"><div class="exp-kpi-label">Bounce Rate</div><div class="exp-kpi-val '+bc+'">'+fmtPct(d.bounce_rate)+'</div>';
  h+='<div class="exp-kpi-sub">Warn &gt;3% &middot; Red &gt;5%</div></div>';
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
function render(data){
  _allData=data;
  renderChips(data);renderTable(data);
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

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/data":
            self._serve_json(get_all_data())
        else:
            self._serve_html(DASHBOARD_HTML)

    def do_POST(self):
        if self.path == "/api/refresh":
            # Invalidate all cache entries so next GET fetches fresh
            with _cache_lock:
                _cache_ts.clear()
            self.send_response(204)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_json(self, data: dict):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(200)
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
