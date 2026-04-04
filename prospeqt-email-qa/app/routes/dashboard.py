import math
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.cache import get_cache
from app.services.poller import trigger_qa_all, trigger_qa_workspace

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# ---------------------------------------------------------------------------
# Utility functions (used by routes and templates)
# ---------------------------------------------------------------------------

LEAD_STATUS_LABELS = {1: "Active", 2: "Paused", 3: "Completed", -1: "Bounced"}


def health_class(broken: int, total: int) -> str:
    """Return CSS modifier class for traffic light dot. Per D-08/D-09."""
    if total == 0:
        return "gray"
    pct = broken / total
    if pct < 0.02:
        return "green"
    elif pct <= 0.10:
        return "yellow"
    return "red"


def health_pct(broken: int, total: int) -> str:
    """Return percentage string like '3.2%' or '0%'. Guards zero division."""
    if total == 0:
        return "0%"
    return f"{broken / total * 100:.1f}%"


def freshness_class(ts: datetime | None) -> str:
    """Return CSS class for freshness indicator. Per D-18."""
    if ts is None:
        return "gray"
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    if age < 300:
        return "green"
    elif age < 900:
        return "amber"
    return "gray"


def freshness_text(ts: datetime | None) -> str:
    """Return human-readable freshness string."""
    if ts is None:
        return "Never scanned"
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    if age < 60:
        return "Just now"
    elif age < 3600:
        mins = int(age // 60)
        return f"{mins} min ago"
    hours = int(age // 3600)
    return f"{hours}h ago"


def total_leads_for_workspace(ws) -> int:
    """Sum total_leads across all campaigns in a workspace."""
    return sum(c.total_leads for c in ws.campaigns)


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Overview page: all workspaces with health status. Per VIEW-01, D-04/D-05/D-06."""
    data = await get_cache().get_all()
    ws_display = []
    for ws in data.workspaces:
        ws_total = total_leads_for_workspace(ws)
        ws_display.append({
            "name": ws.workspace_name,
            "broken": ws.total_broken,
            "total": ws_total,
            "health": health_class(ws.total_broken, ws_total),
            "pct": health_pct(ws.total_broken, ws_total),
            "campaign_count": len(ws.campaigns),
            "freshness_cls": freshness_class(ws.last_checked),
            "freshness_txt": freshness_text(ws.last_checked),
            "error": ws.error,
        })
    return templates.TemplateResponse(request, "dashboard.html", {
        "workspaces": ws_display,
        "ws_count": len(ws_display),
    })


@router.get("/ws/{ws_name}", response_class=HTMLResponse)
async def workspace_detail(request: Request, ws_name: str):
    """Workspace detail page: campaign table. Per VIEW-02, VIEW-05, VIEW-06, D-03."""
    result = await get_cache().get_workspace(ws_name)
    if result is None:
        # Workspace not yet scanned — render empty state with scan button
        return templates.TemplateResponse(request, "workspace.html", {
            "ws_name": ws_name,
            "campaigns": [],
            "ws_broken": 0,
            "ws_total": 0,
            "ws_health": "gray",
            "ws_pct": "0%",
            "not_scanned": True,
        })
    ws_total = total_leads_for_workspace(result)
    campaigns_display = []
    for c in result.campaigns:
        affected_vars = list(c.issues_by_variable.keys())
        if len(affected_vars) > 2:
            var_text = ", ".join(affected_vars[:2]) + f" +{len(affected_vars) - 2} more"
        elif affected_vars:
            var_text = ", ".join(affected_vars)
        else:
            var_text = ""
        campaigns_display.append({
            "id": c.campaign_id,
            "name": c.campaign_name,
            "status": "active" if c.total_leads > 0 else "draft",
            "broken": c.broken_count,
            "total": c.total_leads,
            "health": health_class(c.broken_count, c.total_leads),
            "pct": health_pct(c.broken_count, c.total_leads),
            "var_text": var_text,
            "freshness_cls": freshness_class(c.last_checked),
            "freshness_txt": freshness_text(c.last_checked),
        })
    return templates.TemplateResponse(request, "workspace.html", {
        "ws_name": ws_name,
        "campaigns": campaigns_display,
        "ws_broken": result.total_broken,
        "ws_total": ws_total,
        "ws_health": health_class(result.total_broken, ws_total),
        "ws_pct": health_pct(result.total_broken, ws_total),
        "not_scanned": False,
    })


@router.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Scan API routes (HTMX endpoints, return partial HTML)
# ---------------------------------------------------------------------------


@router.post("/api/scan/all", response_class=HTMLResponse)
async def scan_all(request: Request):
    """Trigger QA across all workspaces and return refreshed workspace grid. Per OPS-01, D-16."""
    await trigger_qa_all()
    # Return current cached state — scan runs async in background
    data = await get_cache().get_all()
    ws_display = []
    for ws in data.workspaces:
        ws_total = total_leads_for_workspace(ws)
        ws_display.append({
            "name": ws.workspace_name,
            "broken": ws.total_broken,
            "total": ws_total,
            "health": health_class(ws.total_broken, ws_total),
            "pct": health_pct(ws.total_broken, ws_total),
            "campaign_count": len(ws.campaigns),
            "freshness_cls": freshness_class(ws.last_checked),
            "freshness_txt": freshness_text(ws.last_checked),
            "error": ws.error,
        })
    return templates.TemplateResponse(request, "dashboard.html", {
        "workspaces": ws_display,
        "ws_count": len(ws_display),
        "partial": True,
    })


@router.post("/api/scan/ws/{ws_name}", response_class=HTMLResponse)
async def scan_workspace(request: Request, ws_name: str):
    """Trigger QA for one workspace and return refreshed campaign table. Per OPS-02, D-16."""
    await trigger_qa_workspace(ws_name)
    result = await get_cache().get_workspace(ws_name)
    campaigns_display = []
    if result:
        for c in result.campaigns:
            affected_vars = list(c.issues_by_variable.keys())
            if len(affected_vars) > 2:
                var_text = ", ".join(affected_vars[:2]) + f" +{len(affected_vars) - 2} more"
            elif affected_vars:
                var_text = ", ".join(affected_vars)
            else:
                var_text = ""
            campaigns_display.append({
                "id": c.campaign_id,
                "name": c.campaign_name,
                "status": "active" if c.total_leads > 0 else "draft",
                "broken": c.broken_count,
                "total": c.total_leads,
                "health": health_class(c.broken_count, c.total_leads),
                "pct": health_pct(c.broken_count, c.total_leads),
                "var_text": var_text,
                "freshness_cls": freshness_class(c.last_checked),
                "freshness_txt": freshness_text(c.last_checked),
            })
    return templates.TemplateResponse(request, "workspace.html", {
        "ws_name": ws_name,
        "campaigns": campaigns_display,
        "partial": True,
    })
