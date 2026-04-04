"""Pydantic v2 models for QA result data shapes.

These models represent the output of the QA engine at three levels:
- CampaignQAResult: per-campaign broken variable summary (D-08)
- WorkspaceQAResult: aggregated result for one Instantly workspace
- GlobalQAResult: top-level result across all configured workspaces
"""
from datetime import datetime

from pydantic import BaseModel


class CampaignQAResult(BaseModel):
    """QA result for a single campaign. Shape per D-08."""

    campaign_id: str
    campaign_name: str
    total_leads: int
    broken_count: int  # Distinct count of leads with at least one broken variable
    issues_by_variable: dict[str, int] = {}  # {varName: broken_lead_count}
    last_checked: datetime | None = None


class WorkspaceQAResult(BaseModel):
    """Aggregated QA result for one Instantly workspace."""

    workspace_name: str
    campaigns: list[CampaignQAResult] = []
    total_broken: int = 0
    error: str | None = None
    last_checked: datetime | None = None


class GlobalQAResult(BaseModel):
    """Top-level QA result across all configured workspaces."""

    workspaces: list[WorkspaceQAResult] = []
    errors: dict[str, str] = {}  # {workspace_name: error_message}
    total_broken: int = 0
    total_campaigns_checked: int = 0
    last_refresh: datetime | None = None
