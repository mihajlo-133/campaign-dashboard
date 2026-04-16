#!/usr/bin/env python3
"""RankZero weekly client-facing report — email-ready HTML with inline SVG charts.

Pulls MTD / WTD / Week-before totals plus daily time series for Sent, Replied,
and Interested (opps) from EmailBison. Renders 3 sections with 3 dual-axis line
charts. Weekdays only on X axis.

Stdlib-only. Output: outputs/rankzero/reports/weekly_YYYYMMDD.html

Run:
  python3 gtm/scripts/rankzero_weekly_report.py
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = "https://send.prospeqt.co/api"
ENV_PATH = Path(__file__).resolve().parents[2] / "tools/prospeqt-automation/.env"
OUT_DIR = Path(__file__).resolve().parents[2] / "outputs/rankzero/reports"
TIMEOUT = 30
SLEEP = 0.1


def load_api_key(var: str = "EMAILBISON_RANKZERO") -> str:
    """Resolve API key. Priority: env var → .env file.

    Env var wins so this runs in Claude Routines / CI without a local .env.
    """
    val = os.environ.get(var)
    if val:
        return val.strip()
    if ENV_PATH.exists():
        text = ENV_PATH.read_text(encoding="utf-8")
        m = re.search(rf"^{re.escape(var)}\s*=\s*(.+)$", text, re.MULTILINE)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    sys.exit(f"[ERROR] {var} not found in env or {ENV_PATH}")


def _telegram_api(token: str, method: str, body: bytes, content_type: str) -> dict:
    """POST to the Telegram Bot API and return the parsed JSON response."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Telegram HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    if not resp.get("ok"):
        raise RuntimeError(f"Telegram returned not-ok: {resp}")
    return resp


def _send_telegram_text(token: str, chat_id: str, text: str) -> None:
    body = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    _telegram_api(token, "sendMessage", body, "application/json")


def _send_telegram_document(token: str, chat_id: str, html_body: str, filename: str) -> None:
    """Upload the HTML report as a document via multipart/form-data. Stdlib-only."""
    boundary = f"----RankZeroReport{int(time.time())}"
    ct = f"multipart/form-data; boundary={boundary}"
    html_bytes = html_body.encode("utf-8")
    parts: list[bytes] = []
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode("utf-8"))
    parts.append(
        (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
            f'Content-Type: text/html; charset=utf-8\r\n\r\n'
        ).encode("utf-8")
    )
    parts.append(html_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    _telegram_api(token, "sendDocument", b"".join(parts), ct)


def send_telegram(html_body: str, totals: dict, today: date) -> None:
    """Send the weekly report to Telegram: text summary + HTML as document.

    Required env vars:
      TELEGRAM_BOT_TOKEN  — bot token from @BotFather
      TELEGRAM_CHAT_ID    — target chat ID (personal chat or channel)
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        sys.exit("[ERROR] TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

    # Plain-text summary (no emoji — bot config note says they render as ??)
    m, w, p = totals["mtd"], totals["wtd"], totals["prior"]
    m_rate = f"{(m['replied'] / m['sent'] * 100):.2f}%" if m["sent"] else "—"
    text = (
        f"Rank Zero - Weekly Outreach Report\n"
        f"{today.strftime('%b %d, %Y')}\n\n"
        f"MONTH TO DATE\n"
        f"  Sent:    {m['sent']:,}\n"
        f"  Replies: {m['replied']:,} ({m_rate} reply rate)\n"
        f"  Opps:    {m['opps']:,}\n\n"
        f"WEEK TO DATE\n"
        f"  Sent:    {w['sent']:,}\n"
        f"  Replies: {w['replied']:,}\n"
        f"  Opps:    {w['opps']:,}\n\n"
        f"WEEK BEFORE\n"
        f"  Sent:    {p['sent']:,}\n"
        f"  Replies: {p['replied']:,}\n"
        f"  Opps:    {p['opps']:,}\n\n"
        f"Full report with charts attached as HTML."
    )
    _send_telegram_text(token, chat_id, text)

    filename = f"rankzero_weekly_{today.strftime('%Y%m%d')}.html"
    _send_telegram_document(token, chat_id, html_body, filename)
    print(f"[OK] Sent report to Telegram chat {chat_id}")


def _http(method: str, url: str, headers: dict, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"[HTTP {e.code}] {method} {url}", file=sys.stderr)
        return None
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"[ERR] {method} {url}: {e}", file=sys.stderr)
        return None


def _i(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0


def q(params: dict) -> str:
    return urllib.parse.urlencode(params)


def fmt_range(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{start.strftime('%b')} {start.day} – {end.day}"
    return f"{start.strftime('%b')} {start.day} – {end.strftime('%b')} {end.day}"


def ratio(contacted: int, opps: int) -> str:
    if opps <= 0:
        return "—"
    return f"{round(contacted / opps):,}:1"


def fetch_daily_series(headers: dict, start: date, end: date) -> dict[str, dict[str, int]]:
    """Returns {label: {date_iso: value}} for Sent / Replied / Interested."""
    url = f"{BASE}/workspaces/v1.1/line-area-chart-stats?{q({'start_date': start.isoformat(), 'end_date': end.isoformat()})}"
    resp = _http("GET", url, headers) or {}
    rows = resp.get("data", []) if isinstance(resp, dict) else []
    wanted = {"Sent", "Replied", "Interested"}
    out: dict[str, dict[str, int]] = {w: {} for w in wanted}
    for item in rows:
        label = item.get("label")
        if label not in wanted:
            continue
        for pair in item.get("dates", []) or []:
            if isinstance(pair, list) and len(pair) >= 2:
                out[label][pair[0]] = _i(pair[1])
    return out


def weekdays_between(start: date, end: date) -> list[date]:
    """Inclusive list of weekdays (Mon–Fri) between start and end."""
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def window_totals(series: dict[str, dict[str, int]], start: date, end: date) -> dict[str, int]:
    s, e = start.isoformat(), end.isoformat()
    def tot(label: str) -> int:
        return sum(v for d, v in series.get(label, {}).items() if s <= d <= e)
    return {"sent": tot("Sent"), "replied": tot("Replied"), "opps": tot("Interested")}


# ---------- SVG chart rendering ----------

CHART_W = 520
CHART_H = 220
PAD_L = 48
PAD_R = 48
PAD_T = 30
PAD_B = 36


import math


def _nice_bounds(n: float, target_ticks: int = 5) -> tuple[float, float, list[float]]:
    """Return (max_val, step, ticks) where ticks are regular intervals from 0 to max_val.

    Picks a "nice" step from {1, 2, 2.5, 5} × 10^k. Rounds max_val up to a
    multiple of step so ticks are clean.
    """
    if n <= 0:
        return 10.0, 2.0, [0, 2, 4, 6, 8, 10]
    raw_step = n / target_ticks
    mag = 10 ** math.floor(math.log10(raw_step))
    norm = raw_step / mag
    step = 10 * mag  # fallback
    for mult in (1, 2, 2.5, 5, 10):
        if norm <= mult:
            step = mult * mag
            break
    max_val = math.ceil(n / step) * step
    ticks = []
    v = 0.0
    while v <= max_val + step * 0.001:
        ticks.append(v)
        v += step
    return max_val, step, ticks


def _format_tick(n: float) -> str:
    n_int = int(round(n))
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n_int//1000}k"
    if n >= 1_000:
        # e.g. 2500 -> "2.5k", 2000 -> "2k"
        v = n / 1_000
        return (f"{v:.1f}k" if v != int(v) else f"{int(v)}k")
    # smaller than 1k: keep whole or one decimal for .5 steps
    if n == int(n):
        return str(int(n))
    return f"{n:.1f}"


def _smooth_path(points: list[tuple[float, float]], tension: float = 0.18) -> str:
    """Catmull-Rom-style smooth path. tension=0 is straight, ~0.3 is pronounced."""
    n = len(points)
    if n == 0:
        return ""
    if n == 1:
        return f"M{points[0][0]:.2f},{points[0][1]:.2f}"
    if n == 2:
        return f"M{points[0][0]:.2f},{points[0][1]:.2f} L{points[1][0]:.2f},{points[1][1]:.2f}"
    parts = [f"M{points[0][0]:.2f},{points[0][1]:.2f}"]
    for i in range(n - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[i + 2] if i + 2 < n else points[i + 1]
        cp1x = p1[0] + (p2[0] - p0[0]) * tension
        cp1y = p1[1] + (p2[1] - p0[1]) * tension
        cp2x = p2[0] - (p3[0] - p1[0]) * tension
        cp2y = p2[1] - (p3[1] - p1[1]) * tension
        parts.append(
            f"C{cp1x:.2f},{cp1y:.2f} {cp2x:.2f},{cp2y:.2f} {p2[0]:.2f},{p2[1]:.2f}"
        )
    return " ".join(parts)


def build_svg_chart(
    days: list[date],
    sent: list[int],
    replied: list[int],
    opps: list[int],
    max_sent: float,
    max_right: float,
    left_ticks: list[float],
    right_ticks: list[float],
) -> str:
    """Return SVG with dual-Y-axis smooth line chart. Weekdays only.

    Max values + tick lists are passed in so all charts share identical scales.
    """
    n = len(days)
    if n == 0:
        return '<div style="padding:24px;color:#9ca3af;font-size:13px;">No data</div>'

    inner_w = CHART_W - PAD_L - PAD_R
    inner_h = CHART_H - PAD_T - PAD_B

    def x(i: int) -> float:
        if n == 1:
            return PAD_L + inner_w / 2
        return PAD_L + (i / (n - 1)) * inner_w

    def y_left(v: float) -> float:
        return PAD_T + inner_h - (v / max_sent) * inner_h

    def y_right(v: float) -> float:
        return PAD_T + inner_h - (v / max_right) * inner_h

    def pts(values: list[int], y_fn) -> list[tuple[float, float]]:
        return [(x(i), y_fn(v)) for i, v in enumerate(values)]

    # X labels: show every day if <=10, else ~6 evenly spaced
    x_labels = []
    for i, d in enumerate(days):
        if n <= 10 or i % max(1, n // 6) == 0 or i == n - 1:
            x_labels.append((i, d))

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHART_W} {CHART_H}" '
        f'width="100%" height="{CHART_H}" style="display:block;max-width:{CHART_W}px;">'
    )

    # Horizontal grid lines (one per left tick → evenly spaced)
    for t in left_ticks:
        ly = y_left(t)
        svg.append(
            f'<line x1="{PAD_L}" y1="{ly:.2f}" x2="{PAD_L + inner_w}" y2="{ly:.2f}" '
            f'stroke="#eceef2" stroke-width="1"/>'
        )

    # Left Y labels (Sent scale)
    for t in left_ticks:
        ly = y_left(t)
        svg.append(
            f'<text x="{PAD_L - 8}" y="{ly + 3:.2f}" text-anchor="end" '
            f'font-family="Helvetica,Arial,sans-serif" font-size="10" fill="#6b7280">'
            f'{_format_tick(t)}</text>'
        )

    # Right Y labels (Replies / Opps scale)
    for t in right_ticks:
        ry = y_right(t)
        svg.append(
            f'<text x="{PAD_L + inner_w + 8}" y="{ry + 3:.2f}" text-anchor="start" '
            f'font-family="Helvetica,Arial,sans-serif" font-size="10" fill="#6b7280">'
            f'{_format_tick(t)}</text>'
        )

    # X labels
    for i, d in x_labels:
        svg.append(
            f'<text x="{x(i):.2f}" y="{PAD_T + inner_h + 16:.2f}" text-anchor="middle" '
            f'font-family="Helvetica,Arial,sans-serif" font-size="10" fill="#6b7280">'
            f'{d.strftime("%b %d")}</text>'
        )

    # Axis frame
    svg.append(
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T + inner_h}" '
        f'stroke="#d1d5db" stroke-width="1"/>'
    )
    svg.append(
        f'<line x1="{PAD_L + inner_w}" y1="{PAD_T}" x2="{PAD_L + inner_w}" y2="{PAD_T + inner_h}" '
        f'stroke="#d1d5db" stroke-width="1"/>'
    )
    svg.append(
        f'<line x1="{PAD_L}" y1="{PAD_T + inner_h}" x2="{PAD_L + inner_w}" y2="{PAD_T + inner_h}" '
        f'stroke="#d1d5db" stroke-width="1"/>'
    )

    # Smooth data lines (bezier tension 0.18 — slight curve)
    TENSION = 0.18
    svg.append(
        f'<path d="{_smooth_path(pts(sent, y_left), TENSION)}" fill="none" '
        f'stroke="#2563eb" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    svg.append(
        f'<path d="{_smooth_path(pts(replied, y_right), TENSION)}" fill="none" '
        f'stroke="#0d9488" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    svg.append(
        f'<path d="{_smooth_path(pts(opps, y_right), TENSION)}" fill="none" '
        f'stroke="#d97706" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # Data points for sparse series (<=10 points, show dots)
    if n <= 10:
        for i, v in enumerate(sent):
            svg.append(f'<circle cx="{x(i):.2f}" cy="{y_left(v):.2f}" r="3" fill="#2563eb"/>')
        for i, v in enumerate(replied):
            svg.append(f'<circle cx="{x(i):.2f}" cy="{y_right(v):.2f}" r="3" fill="#0d9488"/>')
        for i, v in enumerate(opps):
            svg.append(f'<circle cx="{x(i):.2f}" cy="{y_right(v):.2f}" r="3" fill="#d97706"/>')

    # Legend
    svg.append(
        f'<text x="{PAD_L}" y="{PAD_T - 10}" text-anchor="start" '
        f'font-family="Helvetica,Arial,sans-serif" font-size="10" font-weight="600" fill="#2563eb">'
        f'Sent (left)</text>'
    )
    svg.append(
        f'<text x="{PAD_L + inner_w}" y="{PAD_T - 10}" text-anchor="end" '
        f'font-family="Helvetica,Arial,sans-serif" font-size="10" font-weight="600" fill="#6b7280">'
        f'<tspan fill="#0d9488">Replied</tspan>  •  <tspan fill="#d97706">Opps</tspan>  (right)</text>'
    )

    svg.append("</svg>")
    return "".join(svg)


# ---------- HTML rendering ----------

def section_html(title: str, range_label: str, totals: dict[str, int], svg: str) -> str:
    sent = totals["sent"]
    replied = totals["replied"]
    opps = totals["opps"]
    contacted_unique = sent  # EmailBison "Sent" is the closest daily sent proxy
    reply_pct = f"{(replied / sent * 100):.2f}%" if sent else "—"
    opp_pct = f"{(opps / sent * 100):.3f}%" if sent else "—"
    return f"""
    <tr>
      <td style="padding:28px 32px 8px 32px;">
        <div style="font-size:11px;letter-spacing:0.08em;text-transform:uppercase;color:#6b7280;font-weight:600;">{html.escape(title)}</div>
        <div style="font-size:13px;color:#6b7280;margin-top:4px;">{html.escape(range_label)}</div>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;">
          <tr>
            <td width="33%" valign="top" style="padding:12px 12px 12px 0;">
              <div style="font-size:11px;color:#6b7280;font-weight:500;">Emails sent</div>
              <div style="font-size:22px;font-weight:700;color:#0f172a;margin-top:2px;letter-spacing:-0.02em;">{sent:,}</div>
            </td>
            <td width="33%" valign="top" style="padding:12px;">
              <div style="font-size:11px;color:#6b7280;font-weight:500;">Replies</div>
              <div style="font-size:22px;font-weight:700;color:#0f172a;margin-top:2px;letter-spacing:-0.02em;">{replied:,}</div>
              <div style="font-size:11px;color:#9ca3af;margin-top:2px;">{reply_pct} reply rate</div>
            </td>
            <td width="33%" valign="top" style="padding:12px 0 12px 12px;">
              <div style="font-size:11px;color:#6b7280;font-weight:500;">Opportunities</div>
              <div style="font-size:22px;font-weight:700;color:#0f172a;margin-top:2px;letter-spacing:-0.02em;">{opps:,}</div>
              <div style="font-size:11px;color:#9ca3af;margin-top:2px;">{opp_pct} of sent</div>
            </td>
          </tr>
        </table>

        <div style="margin-top:12px;background:#ffffff;border:1px solid #eceef2;border-radius:8px;padding:12px 8px;">
          {svg}
        </div>
      </td>
    </tr>
    <tr><td style="padding:0 32px;"><div style="border-top:1px solid #eceef2;"></div></td></tr>
    """


def build_html(today: date, windows: dict) -> str:
    mtd_section = section_html(
        "Month to date",
        fmt_range(windows["mtd"]["start"], windows["mtd"]["end"]),
        windows["mtd"]["totals"],
        windows["mtd"]["svg"],
    )
    wtd_section = section_html(
        "Week to date",
        fmt_range(windows["wtd"]["start"], windows["wtd"]["end"]),
        windows["wtd"]["totals"],
        windows["wtd"]["svg"],
    )
    prior_section = section_html(
        "Week before",
        fmt_range(windows["prior"]["start"], windows["prior"]["end"]),
        windows["prior"]["totals"],
        windows["prior"]["svg"],
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rank Zero — Outreach Performance — {today.strftime('%b %d, %Y')}</title>
</head>
<body style="margin:0;padding:0;background:#f5f6f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#1a1d24;">

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f5f6f8;padding:24px 0;">
  <tr>
    <td align="center">

      <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.04);">

        <tr>
          <td style="padding:32px 32px 20px 32px;border-bottom:1px solid #eceef2;">
            <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#6b7280;font-weight:600;">Weekly Outreach Report</div>
            <div style="font-size:24px;font-weight:700;color:#0f172a;margin-top:8px;line-height:1.2;">Rank Zero · {today.strftime('%b %d, %Y')}</div>
            <div style="font-size:14px;color:#6b7280;margin-top:6px;">Performance across three windows: month to date, week to date, and the prior week. Daily series shown in weekdays only.</div>
          </td>
        </tr>

        {mtd_section}
        {wtd_section}
        {prior_section}

        <tr>
          <td style="padding:20px 32px 28px 32px;background:#fafbfc;">
            <div style="font-size:12px;color:#9ca3af;">Prepared by Prospeqt · <a href="mailto:mihajlo@prospeqt.co" style="color:#6b7280;text-decoration:none;">mihajlo@prospeqt.co</a></div>
          </td>
        </tr>

      </table>

    </td>
  </tr>
</table>

</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank Zero weekly report generator")
    parser.add_argument("--send", action="store_true",
                        help="Send to Telegram (requires TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars)")
    parser.add_argument("--no-write", action="store_true",
                        help="Skip writing HTML to disk (useful in cloud routines)")
    args = parser.parse_args()

    api_key = load_api_key("EMAILBISON_RANKZERO")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    today = date.today()
    mtd_start, mtd_end = today - timedelta(days=30), today
    wtd_start, wtd_end = today - timedelta(days=7), today
    prior_start, prior_end = today - timedelta(days=14), today - timedelta(days=7)

    # One fetch covers everything since MTD ⊇ WTD ⊇ prior-week.
    all_daily = fetch_daily_series(headers, mtd_start, mtd_end)

    # Extract daily series per window first (without rendering charts yet).
    def extract(start: date, end: date):
        days = weekdays_between(start, end)
        sent = [all_daily["Sent"].get(d.isoformat(), 0) for d in days]
        replied = [all_daily["Replied"].get(d.isoformat(), 0) for d in days]
        opps = [all_daily["Interested"].get(d.isoformat(), 0) for d in days]
        return {
            "start": start, "end": end, "days": days,
            "sent": sent, "replied": replied, "opps": opps,
            "totals": {"sent": sum(sent), "replied": sum(replied), "opps": sum(opps)},
        }

    raw = {
        "mtd": extract(mtd_start, mtd_end),
        "wtd": extract(wtd_start, wtd_end),
        "prior": extract(prior_start, prior_end),
    }

    # Global Y-axis bounds across all three windows so charts share scales.
    all_sent_vals = [v for w in raw.values() for v in w["sent"]]
    all_right_vals = [v for w in raw.values() for v in (w["replied"] + w["opps"])]
    max_sent, _, left_ticks = _nice_bounds(max(all_sent_vals) if all_sent_vals else 1, target_ticks=5)
    max_right, _, right_ticks = _nice_bounds(max(all_right_vals) if all_right_vals else 1, target_ticks=5)

    windows = {}
    for key, w in raw.items():
        svg = build_svg_chart(
            w["days"], w["sent"], w["replied"], w["opps"],
            max_sent, max_right, left_ticks, right_ticks,
        )
        windows[key] = {
            "start": w["start"], "end": w["end"],
            "totals": w["totals"], "svg": svg,
        }

    html_out = build_html(today, windows)

    if not args.no_write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"weekly_{today.strftime('%Y%m%d')}.html"
        out_path.write_text(html_out, encoding="utf-8")
        print(f"[OK] Wrote {out_path}")

    print(f"     MTD:   sent={windows['mtd']['totals']['sent']:,}  replied={windows['mtd']['totals']['replied']:,}  opps={windows['mtd']['totals']['opps']:,}")
    print(f"     WTD:   sent={windows['wtd']['totals']['sent']:,}  replied={windows['wtd']['totals']['replied']:,}  opps={windows['wtd']['totals']['opps']:,}")
    print(f"     Prior: sent={windows['prior']['totals']['sent']:,}  replied={windows['prior']['totals']['replied']:,}  opps={windows['prior']['totals']['opps']:,}")

    if args.send:
        totals = {
            "mtd": windows["mtd"]["totals"],
            "wtd": windows["wtd"]["totals"],
            "prior": windows["prior"]["totals"],
        }
        send_telegram(html_out, totals, today)


if __name__ == "__main__":
    main()
