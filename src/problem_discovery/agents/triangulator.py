from __future__ import annotations

from typing import Any

from .base import Agent, AgentResult


class SignalTriangulator(Agent):
    agent_id = "TRIANGULATOR"

    def run(self, context: dict[str, Any]) -> AgentResult:
        f = context.get("agent_f", {})
        g = context.get("agent_g", {})
        h = context.get("agent_h", {})
        i = context.get("agent_i", {})
        j = context.get("agent_j", {})

        strong_agreements = []
        tensions = []
        if f.get("assessment") == "rising" and j.get("assessment") == "positive":
            strong_agreements.append("F + J: Timing signals align for renewed opportunity")
        if h.get("accessibility_score", 0) >= 7 and g.get("entrenchment_score", 0) >= 6:
            tensions.append("High accessibility but medium entrenchment: conversion friction")

        payload = {
            "agent_summary_matrix": {
                "agent_f_trend": f,
                "agent_g_competition": g,
                "agent_h_accessibility": h,
                "agent_i_second_order": i,
                "agent_j_contrarian": j,
            },
            "triangulation_findings": {
                "strong_agreements": strong_agreements,
                "disagreements": [],
                "tensions": tensions,
                "orthogonal_combinations": ["Timing + distribution + budget alignment"],
            },
            "overall_triangulation_score": "strong" if strong_agreements else "mixed",
            "confidence_level": "high" if strong_agreements else "medium",
            "key_insight": "Balance timing with conversion friction",
        }
        return AgentResult(agent_id=self.agent_id, payload=payload)
