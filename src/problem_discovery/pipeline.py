from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents.orchestrator import Orchestrator
from .agents.hunter_social import AgentA
from .agents.hunter_social_devvit import AgentADevvit
from .agents.review_raider import AgentB
from .agents.review_raider_g2 import AgentBG2
from .agents.job_board import AgentC
from .agents.job_board_hasdata import AgentCHasData
from .agents.budget_allocator import AgentL
from .agents.pattern_recognizer import AgentD
from .agents.skeptic_lite import AgentELite
from .agents.trend_archaeologist import AgentF
from .agents.solution_scout import AgentG
from .agents.gtm_pathfinder import AgentH
from .agents.consequence_mapper import AgentI
from .agents.contrarian_scanner import AgentJ
from .agents.triangulator import SignalTriangulator
from .agents.skeptic_full import AgentEFull
from .memory.storage import Storage
from .config import SourceConfig
from .g2_client import G2Client
from .hasdata_client import HasDataClient
from .scoring import calculate_final_score


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Pipeline:
    def __init__(self, db_path: Path, seed: int = 42) -> None:
        self.seed = seed
        self.storage = Storage(db_path)
        self.sources = SourceConfig()

    def _load_json(self, path: Path | None, fallback: dict[str, Any]) -> dict[str, Any]:
        if path is None:
            return fallback
        if not path.exists():
            return fallback
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def run(
        self,
        niche: str,
        phase: str,
        founder_profile_path: Path | None = None,
        use_devvit: bool = False,
        devvit_signal_path: Path | None = None,
    ) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        founder_profile = self._load_json(
            founder_profile_path,
            {
                "technical_depth": "high",
                "sales_capability": "low",
                "domain_expertise": [niche],
                "network_industries": [],
                "capital_available": "bootstrap",
                "risk_tolerance": "medium",
                "timeline_to_revenue": "6_months",
            },
        )
        context: dict[str, Any] = {
            "niche": niche,
            "sub_verticals": [],
            "constraints": {"exclude_enterprise": True, "exclude_regulated": False, "geographic_focus": "US"},
            "founder_profile": founder_profile,
            "max_signals": 24,
            "seed": self.seed,
            "devvit_signal_path": str(devvit_signal_path) if devvit_signal_path else None,
            "g2_product_ids": self.sources.g2_product_ids,
            "indeed_location": self.sources.indeed_location,
            "indeed_country": self.sources.indeed_country,
            "indeed_domain": self.sources.indeed_domain,
            "indeed_sort": self.sources.indeed_sort,
        }

        orchestrator = Orchestrator()
        orchestration = orchestrator.run(context).payload
        context.update(orchestration)

        if phase in {"1", "all", "2", "3", "4", "5"}:
            per_agent = max(6, context["max_signals"] // 3)
            context["max_signals"] = per_agent

            if use_devvit and devvit_signal_path is not None:
                agent_a = AgentADevvit(self.seed, devvit_signal_path)
            else:
                agent_a = AgentA(self.seed)

            if self.sources.g2_api_key and self.sources.g2_product_ids:
                g2_client = G2Client(
                    api_key=self.sources.g2_api_key,
                    base_url=self.sources.g2_base_url,
                    auth_scheme=self.sources.g2_auth_scheme,
                    mode=self.sources.g2_mode,
                )
                agent_b = AgentBG2(g2_client, self.seed)
            else:
                agent_b = AgentB(self.seed)

            if self.sources.hasdata_api_key:
                hasdata_client = HasDataClient(
                    api_key=self.sources.hasdata_api_key,
                    base_url=self.sources.hasdata_base_url,
                )
                agent_c = AgentCHasData(
                    hasdata_client,
                    self.seed,
                    location=self.sources.indeed_location,
                    country=self.sources.indeed_country,
                    domain=self.sources.indeed_domain,
                    sort=self.sources.indeed_sort,
                )
            else:
                agent_c = AgentC(self.seed)
            res_a = agent_a.run(context).payload
            res_b = agent_b.run(context).payload
            res_c = agent_c.run(context).payload

            signals = res_a["signals"] + res_b["signals"] + res_c["signals"]
            context["signals"] = signals

            for signal in signals:
                self.storage.insert_signal(signal["signal_id"], run_id, signal["source_agent"], signal)

            agent_l = AgentL(self.seed)
            budget = agent_l.run({"signals": signals}).payload
            context.update(budget)

        if phase in {"2", "all", "3", "4", "5"}:
            agent_d = AgentD(self.seed)
            clusters = agent_d.run({"signals": context["signals"]}).payload["clusters"]
            agent_e = AgentELite()
            filtered = agent_e.run({"clusters": clusters, "founder_profile": founder_profile}).payload
            context["clusters"] = filtered["clusters"]
            context["lite_rejects"] = filtered["rejects"]

        if phase in {"3", "all", "4", "5"}:
            enriched_clusters = []
            for cluster in context.get("clusters", []):
                agent_f = AgentF(self.seed)
                agent_g = AgentG(self.seed)
                agent_h = AgentH(self.seed)
                agent_i = AgentI(self.seed)
                agent_j = AgentJ(self.seed)
                tri = SignalTriangulator()

                out_f = agent_f.run({"cluster": cluster}).payload
                out_g = agent_g.run({"cluster": cluster}).payload
                out_h = agent_h.run({"cluster": cluster}).payload
                out_i = agent_i.run({"cluster": cluster}).payload
                out_j = agent_j.run({"cluster": cluster}).payload
                out_tri = tri.run({
                    "agent_f": out_f,
                    "agent_g": out_g,
                    "agent_h": out_h,
                    "agent_i": out_i,
                    "agent_j": out_j,
                }).payload

                cluster_payload = {
                    "cluster_id": cluster["cluster_id"],
                    "cluster_name": cluster["cluster_name"],
                    "description": cluster["description"],
                    "created_at": cluster["created_at"],
                    "phase": 3,
                    "signals": {
                        "total_count": len(cluster["signals"]),
                        "by_agent": {},
                        "by_platform": {},
                    },
                    "stakeholders": {
                        "has_problem": "Operations",
                        "pays_for_solution": "Operations",
                        "end_user": "Operations",
                    },
                    "budget_analysis": context.get("budget_analysis", {}),
                    "agent_assessments": {
                        "F": out_f,
                        "G": out_g,
                        "H": out_h,
                        "I": out_i,
                        "J": out_j,
                    },
                    "triangulation": out_tri,
                    "skeptic_review": {},
                    "scores": {},
                }
                enriched_clusters.append(cluster_payload)
            context["clusters"] = enriched_clusters

        if phase in {"4", "all", "5"}:
            agent_e_full = AgentEFull(self.seed)
            for cluster in context.get("clusters", [])[:10]:
                skeptic = agent_e_full.run({"cluster": cluster}).payload
                cluster["skeptic_review"] = skeptic

        if phase in {"5", "all"}:
            ranked = []
            for cluster in context.get("clusters", []):
                agent_outputs = {
                    "F": cluster["agent_assessments"].get("F", {}),
                    "G": cluster["agent_assessments"].get("G", {}),
                    "H": cluster["agent_assessments"].get("H", {}),
                    "I": cluster["agent_assessments"].get("I", {}),
                    "J": cluster["agent_assessments"].get("J", {}),
                    "E": cluster.get("skeptic_review", {}),
                    "triangulation_score": 8 if cluster.get("triangulation", {}).get("overall_triangulation_score") == "strong" else 6,
                    "wtp_score": 7,
                }
                final_score = calculate_final_score(cluster, agent_outputs, founder_profile)
                cluster["scores"] = {
                    "base_score": final_score,
                    "founder_fit_multiplier": 1.0,
                    "skeptic_penalty": 1.0,
                    "final_score": final_score,
                }
                ranked.append(cluster)

            ranked.sort(key=lambda c: c["scores"]["final_score"], reverse=True)
            context["ranked_clusters"] = ranked

        summary = {
            "signals_collected": len(context.get("signals", [])),
            "clusters_formed": len(context.get("clusters", [])),
            "clusters_after_filter": len(context.get("clusters", [])),
            "clusters_deep_analyzed": len(context.get("clusters", [])),
            "final_ranked_count": len(context.get("ranked_clusters", [])),
        }

        self.storage.insert_run(run_id, niche, utc_now(), summary)
        for cluster in context.get("ranked_clusters", []):
            self.storage.insert_cluster(cluster["cluster_id"], run_id, cluster)

        return {
            "run_id": run_id,
            "niche": niche,
            "founder_profile": founder_profile,
            "run_timestamp": utc_now(),
            "summary": summary,
            "top_opportunities": context.get("ranked_clusters", [])[:10],
            "memory_updates": {
                "patterns_logged": 0,
                "failures_logged": 0,
                "exploration_logged": 0,
            },
        }

    def close(self) -> None:
        self.storage.close()
