from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FounderProfile:
    technical_depth: str = "medium"
    sales_capability: str = "medium"
    domain_expertise: list[str] = field(default_factory=list)
    network_industries: list[str] = field(default_factory=list)
    capital_available: str = "bootstrap"
    risk_tolerance: str = "medium"
    timeline_to_revenue: str = "6_months"


@dataclass
class Constraints:
    exclude_enterprise: bool = True
    exclude_regulated: bool = False
    geographic_focus: str = "US"


@dataclass
class InputPayload:
    niche: str
    sub_verticals: list[str]
    founder_profile: FounderProfile
    constraints: Constraints


@dataclass
class RawSignal:
    signal_id: str
    source_agent: str
    source_platform: str
    source_url: str
    timestamp_found: str
    content: dict[str, Any]
    extracted_data: dict[str, Any]
    metadata: dict[str, Any]


@dataclass
class ProblemCluster:
    cluster_id: str
    cluster_name: str
    description: str
    created_at: str
    phase: int
    signals: dict[str, Any]
    stakeholders: dict[str, Any]
    budget_analysis: dict[str, Any]
    agent_assessments: dict[str, Any]
    triangulation: dict[str, Any]
    skeptic_review: dict[str, Any]
    scores: dict[str, Any]


@dataclass
class RunSummary:
    signals_collected: int
    clusters_formed: int
    clusters_after_filter: int
    clusters_deep_analyzed: int
    final_ranked_count: int


@dataclass
class FinalOpportunity:
    rank: int
    cluster_id: str
    cluster_name: str
    final_score: float
    one_line_summary: str
    evidence_strength: str
    key_evidence: list[str]
    key_risks: list[str]
    recommended_next_steps: list[str]
    full_dossier: dict[str, Any]


@dataclass
class FinalOutput:
    run_id: str
    niche: str
    founder_profile: dict[str, Any]
    run_timestamp: str
    summary: RunSummary
    top_opportunities: list[FinalOpportunity]
    memory_updates: dict[str, Any]

