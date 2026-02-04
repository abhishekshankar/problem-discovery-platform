from __future__ import annotations

from typing import Any


def founder_fit_multiplier(cluster: dict[str, Any], founder_profile: dict[str, Any]) -> float:
    multiplier = 1.0
    requires_technical = cluster.get("requires_technical", "medium")
    requires_sales = cluster.get("requires_sales", "smb")
    requires_capital = cluster.get("requires_capital", "low")
    domain = cluster.get("domain", "")

    if requires_technical == "high" and founder_profile.get("technical_depth") == "low":
        multiplier *= 0.5
    if requires_sales == "enterprise" and founder_profile.get("sales_capability") == "low":
        multiplier *= 0.5
    if domain and domain in founder_profile.get("domain_expertise", []):
        multiplier *= 1.3
    if requires_capital == "high" and founder_profile.get("capital_available") == "bootstrap":
        multiplier *= 0.7

    return min(max(multiplier, 0.3), 1.5)


def calculate_skeptic_penalty(skeptic_output: dict[str, Any]) -> float:
    verdict = skeptic_output.get("survival_verdict", "PROCEED")
    if verdict == "REJECT":
        return 0.5
    if verdict == "PROCEED_WITH_CAUTION":
        return 0.85
    return 1.0


def calculate_final_score(cluster: dict[str, Any], agent_outputs: dict[str, Any], founder_profile: dict[str, Any]) -> float:
    wtp_score = agent_outputs.get("wtp_score", 6)
    triangulation_score = agent_outputs.get("triangulation_score", 6)
    trend_score = agent_outputs.get("F", {}).get("trend_score", 5)
    competition_score = 10 - agent_outputs.get("G", {}).get("competitor_count", 5)
    accessibility_score = agent_outputs.get("H", {}).get("accessibility_score", 5)
    entrenchment_score = 10 - agent_outputs.get("G", {}).get("entrenchment_score", 5)
    network_score = agent_outputs.get("H", {}).get("network_effect_score", 5)
    contrarian_score = agent_outputs.get("J", {}).get("contrarian_score", 5)
    second_order_score = agent_outputs.get("I", {}).get("opportunity_score", 5)

    base_score = (
        wtp_score * 0.20
        + triangulation_score * 0.15
        + trend_score * 0.15
        + competition_score * 0.15
        + accessibility_score * 0.10
        + entrenchment_score * 0.10
        + network_score * 0.05
        + contrarian_score * 0.05
        + second_order_score * 0.05
    )

    multiplier = founder_fit_multiplier(cluster, founder_profile)
    skeptic_penalty = calculate_skeptic_penalty(agent_outputs.get("E", {}))
    return round(base_score * multiplier * skeptic_penalty, 2)
