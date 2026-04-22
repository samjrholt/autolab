"""LLM-backed agent integrations.

Today this exposes the Claude-native Planner / PolicyProvider / Campaign
Designer.  Provider abstraction (LiteLLM etc.) is v2.
"""

from __future__ import annotations

from autolab.agents.claude import (
    CLAUDE_MODEL_DEFAULT,
    CampaignDesigner,
    ClaudePlanner,
    ClaudePolicyProvider,
    ClaudeResponse,
    ClaudeTransport,
    DesignResult,
    campaign_from_draft,
    objective_from,
    workflow_template_from_draft,
)

__all__ = [
    "CLAUDE_MODEL_DEFAULT",
    "CampaignDesigner",
    "ClaudePlanner",
    "ClaudePolicyProvider",
    "ClaudeResponse",
    "ClaudeTransport",
    "DesignResult",
    "campaign_from_draft",
    "objective_from",
    "workflow_template_from_draft",
]
