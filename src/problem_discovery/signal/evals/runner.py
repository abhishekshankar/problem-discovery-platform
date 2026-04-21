"""Evaluation harness (PRD §13) — Set A/B/C runners."""

from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..extraction.classifier import ProblemSignalClassifier
from ..extraction.llm_extract import extract_problem_from_raw, stub_extraction_for_dev
from ..extraction.verify_quote import quote_is_verified
from ..settings import SignalSettings, get_settings

# PRD §13.3 thresholds (starting)
THRESH_F1 = 0.75
THRESH_SPECIFICITY_MAE = 1.5
THRESH_LAYER_ACC = 0.65
THRESH_WTP_ACC = 0.70

# Week 2 interim gate (PRD §19)
THRESH_F1_WEEK2 = 0.70

THRESH_ARI = 0.60
THRESH_ARI_WEEK4 = 0.55
THRESH_E2E_AGREEMENT = 0.75


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def ensure_eval_set(conn: Any, name: str, version: str, set_type: str, records: list[dict[str, Any]], description: str) -> str:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM eval_sets WHERE name = %s AND version = %s",
            (name, version),
        )
        row = cur.fetchone()
        if row:
            return str(row["id"])
        eid = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO eval_sets (id, name, version, set_type, created_at, record_count, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (eid, name, version, set_type, _utc_now(), len(records), description),
        )
        return eid


def _simulate_pipeline_prediction(
    text: str,
    *,
    clf: ProblemSignalClassifier,
    settings: SignalSettings,
    source_label: str = "eval",
    use_llm: bool,
) -> dict[str, Any]:
    """Mirror production order: classifier → LLM/stub → quote verify."""
    cr = clf.predict(text)
    if not cr.is_problem_signal:
        return {
            "is_problem_signal": False,
            "specificity_score": None,
            "layer": None,
            "wtp_level": None,
            "exact_quote": None,
        }

    raw_payload = json.dumps({"text": text})
    if use_llm and settings.anthropic_api_key and not settings.extraction_use_stub:
        try:
            data = extract_problem_from_raw(source_label=source_label, raw_text=text, settings=settings)
        except Exception:
            data = stub_extraction_for_dev(text)
    else:
        data = stub_extraction_for_dev(text)

    if not data.get("is_problem_signal"):
        return {**data, "is_problem_signal": False}

    eq = data.get("exact_quote")
    if not quote_is_verified(eq, raw_payload):
        return {
            "is_problem_signal": False,
            "specificity_score": data.get("specificity_score"),
            "layer": data.get("layer"),
            "wtp_level": data.get("wtp_level"),
            "exact_quote": eq,
            "quote_failed": True,
        }
    return data


def _binary_f1(y_true: list[bool], y_pred: list[bool]) -> float:
    from sklearn.metrics import f1_score

    if not y_true:
        return 0.0
    return float(f1_score(y_true, y_pred, average="binary", pos_label=True, zero_division=0))


def _mae(a: list[float], b: list[float]) -> float:
    if not a:
        return 0.0
    return float(sum(abs(x - y) for x, y in zip(a, b)) / len(a))


def run_extractor_eval(
    jsonl_path: Path | None = None,
    *,
    target_version: str = "extractor",
    eval_name: str = "extractor_v1",
    eval_version: str = "1",
    week2_gate: bool = False,
    settings: SignalSettings | None = None,
) -> dict[str, Any]:
    """Set A — F1, specificity MAE, layer acc, wtp acc; persist eval_runs."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required for eval runs")

    root = Path(__file__).resolve().parents[2]
    path = jsonl_path or (root / "evals" / "extractor_v1.jsonl")
    records = load_jsonl(path)

    clf = ProblemSignalClassifier(settings=s)
    use_llm = bool(s.anthropic_api_key) and not s.extraction_use_stub

    y_true_bin: list[bool] = []
    y_pred_bin: list[bool] = []
    spec_true: list[float] = []
    spec_pred: list[float] = []
    layer_true: list[str] = []
    layer_pred: list[str] = []
    wtp_true: list[str] = []
    wtp_pred: list[str] = []

    for row in records:
        text = str(row.get("text", ""))
        gold_prob = bool(row.get("is_problem_signal"))
        y_true_bin.append(gold_prob)

        pred = _simulate_pipeline_prediction(text, clf=clf, settings=s, use_llm=use_llm)
        y_pred_bin.append(bool(pred.get("is_problem_signal")))

        if gold_prob and pred.get("is_problem_signal"):
            gs = row.get("specificity_score")
            if gs is not None and pred.get("specificity_score") is not None:
                spec_true.append(float(gs))
                spec_pred.append(float(pred["specificity_score"]))
            gl = row.get("layer")
            pl = pred.get("layer")
            if gl and pl:
                layer_true.append(str(gl))
                layer_pred.append(str(pl))
            gw = row.get("wtp_level")
            pw = pred.get("wtp_level")
            if gw and pw:
                wtp_true.append(str(gw))
                wtp_pred.append(str(pw))

    f1 = _binary_f1(y_true_bin, y_pred_bin)
    spec_mae = _mae(spec_true, spec_pred) if spec_true else None
    layer_acc = (
        sum(1 for a, b in zip(layer_true, layer_pred) if a == b) / len(layer_true) if layer_true else None
    )
    wtp_acc = sum(1 for a, b in zip(wtp_true, wtp_pred) if a == b) / len(wtp_true) if wtp_true else None

    f1_threshold = THRESH_F1_WEEK2 if week2_gate else THRESH_F1
    passed = (
        f1 >= f1_threshold
        and (spec_mae is None or spec_mae <= THRESH_SPECIFICITY_MAE)
        and (layer_acc is None or layer_acc >= THRESH_LAYER_ACC)
        and (wtp_acc is None or wtp_acc >= THRESH_WTP_ACC)
    )
    # If no LLM, only gate on F1 from classifier+stub path (will usually fail — intentional)
    if not use_llm:
        passed = f1 >= f1_threshold

    scores = {
        "is_problem_signal_f1": round(f1, 4),
        "specificity_mae": round(spec_mae, 4) if spec_mae is not None else None,
        "layer_accuracy": round(layer_acc, 4) if layer_acc is not None else None,
        "wtp_accuracy": round(wtp_acc, 4) if wtp_acc is not None else None,
        "records": len(records),
        "use_llm": use_llm,
        "thresholds": {
            "f1": f1_threshold,
            "specificity_mae_max": THRESH_SPECIFICITY_MAE,
            "layer_acc_min": THRESH_LAYER_ACC,
            "wtp_acc_min": THRESH_WTP_ACC,
        },
    }

    run_id = str(uuid.uuid4())
    with connection(autocommit=True) as conn:
        eval_set_id = ensure_eval_set(
            conn,
            eval_name,
            eval_version,
            "extractor",
            records,
            "PRD Set A — extractor / pipeline binary + field metrics",
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eval_runs (id, eval_set_id, target_version, run_at, scores_json, passed, promoted_to_production)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (run_id, eval_set_id, target_version, _utc_now(), json.dumps(scores), passed, False),
            )

    return {"eval_run_id": run_id, "eval_set_id": eval_set_id, "scores": scores, "passed": passed}


def run_extractor_eval_stub(jsonl_path: Path | None = None) -> dict[str, Any]:
    """Backward-compatible stub: registers null scores (baseline before harness)."""
    s = get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required for eval runs")

    root = Path(__file__).resolve().parents[2]
    path = jsonl_path or (root / "evals" / "extractor_v0.jsonl")
    if not path.exists():
        path = root / "evals" / "extractor_v1.jsonl"
    records = load_jsonl(path) if path.exists() else []

    run_id = str(uuid.uuid4())
    scores = {
        "note": "stub_run_before_extractor",
        "records_loaded": len(records),
        "f1": None,
        "specificity_mae": None,
    }

    with connection(autocommit=True) as conn:
        eval_set_id = ensure_eval_set(conn, "extractor_v0", "0", "extractor", records, "PRD Set A placeholder")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eval_runs (id, eval_set_id, target_version, run_at, scores_json, passed, promoted_to_production)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (run_id, eval_set_id, "extractor_stub", _utc_now(), json.dumps(scores), False, False),
            )

    return {"eval_run_id": run_id, "eval_set_id": eval_set_id, "scores": scores}


def _adjusted_rand_index(labels_true: list[int], labels_pred: list[int]) -> float:
    from sklearn.metrics import adjusted_rand_score

    if len(labels_true) < 2:
        return 0.0
    return float(adjusted_rand_score(labels_true, labels_pred))


def run_clusterer_eval(
    jsonl_path: Path | None = None,
    *,
    target_version: str = "clusterer",
    settings: SignalSettings | None = None,
    week4_gate: bool = False,
) -> dict[str, Any]:
    """Set B (static) — ARI using `predicted_cluster_id` from JSONL (dev / fixture rows)."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    root = Path(__file__).resolve().parents[2]
    path = jsonl_path or (root / "evals" / "clusterer_v1.jsonl")
    records = load_jsonl(path)

    # Each row: problem_id, gold_cluster_id (int or str), optional embedding text for prediction
    labels_true: list[int] = []
    labels_pred: list[int] = []
    cluster_map: dict[str, int] = {}
    next_id = 0
    pred_counter: dict[str, int] = defaultdict(int)

    for row in records:
        gid = str(row.get("gold_cluster_id", row.get("cluster_id", "")))
        if gid not in cluster_map:
            cluster_map[gid] = next_id
            next_id += 1
        labels_true.append(cluster_map[gid])
        # Trivial pred: use model_cluster_id if present else gold (dev)
        pid = str(row.get("predicted_cluster_id", row.get("gold_cluster_id")))
        if pid not in pred_counter:
            pred_counter[pid] = len(pred_counter)
        labels_pred.append(pred_counter[pid])

    ari = _adjusted_rand_index(labels_true, labels_pred)
    thresh = THRESH_ARI_WEEK4 if week4_gate else THRESH_ARI
    passed = ari >= thresh

    scores = {
        "ari": round(ari, 4),
        "records": len(records),
        "threshold_ari": thresh,
    }
    run_id = str(uuid.uuid4())
    with connection(autocommit=True) as conn:
        eid = ensure_eval_set(
            conn,
            "clusterer_v1",
            "1",
            "clusterer",
            records,
            "PRD Set B — gold cluster groupings",
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eval_runs (id, eval_set_id, target_version, run_at, scores_json, passed, promoted_to_production)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (run_id, eid, target_version, _utc_now(), json.dumps(scores), passed, False),
            )
    return {"eval_run_id": run_id, "eval_set_id": eid, "scores": scores, "passed": passed}


def run_clusterer_eval_live(
    jsonl_path: Path | None = None,
    *,
    target_version: str = "clusterer_live_kmeans",
    settings: SignalSettings | None = None,
    week4_gate: bool = False,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Set B (live) — embed `text` with the production embedding model, KMeans with K = unique gold labels, ARI vs gold.
    Does not write to the DB. Requires `sentence-transformers` + `scikit-learn`.
    """
    from sklearn.cluster import KMeans

    from ..extraction.embed import embed_texts

    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    root = Path(__file__).resolve().parents[2]
    path = jsonl_path or (root / "evals" / "clusterer_v1.jsonl")
    records = load_jsonl(path)
    if len(records) < 2:
        raise ValueError("clusterer live eval needs at least 2 JSONL rows")

    texts = [str(r.get("text", "")) for r in records]
    cluster_map: dict[str, int] = {}
    next_id = 0
    labels_true: list[int] = []
    for row in records:
        gid = str(row.get("gold_cluster_id", row.get("cluster_id", "")))
        if gid not in cluster_map:
            cluster_map[gid] = next_id
            next_id += 1
        labels_true.append(cluster_map[gid])

    n_clusters = len(cluster_map)
    if n_clusters < 1:
        raise ValueError("no gold_cluster_id values in JSONL")

    emb = embed_texts(texts, settings=s)
    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels_pred = [int(x) for x in km.fit_predict(emb)]

    ari = _adjusted_rand_index(labels_true, labels_pred)
    thresh = THRESH_ARI_WEEK4 if week4_gate else THRESH_ARI
    passed = ari >= thresh

    scores = {
        "ari": round(ari, 4),
        "records": len(records),
        "threshold_ari": thresh,
        "n_gold_clusters": n_clusters,
        "method": "kmeans_on_embeddings",
    }
    run_id = str(uuid.uuid4())
    with connection(autocommit=True) as conn:
        eid = ensure_eval_set(
            conn,
            "clusterer_live",
            "1",
            "clusterer",
            records,
            "PRD Set B — KMeans predictions on eval embeddings",
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eval_runs (id, eval_set_id, target_version, run_at, scores_json, passed, promoted_to_production)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (run_id, eid, target_version, _utc_now(), json.dumps(scores), passed, False),
            )
    return {"eval_run_id": run_id, "eval_set_id": eid, "scores": scores, "passed": passed}


def run_end_to_end_eval(
    jsonl_path: Path | None = None,
    *,
    target_version: str = "ranker_brief",
    settings: SignalSettings | None = None,
) -> dict[str, Any]:
    """Set C (static) — compares `decision` to `predicted_decision` columns in JSONL (fixture / hand-filled)."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    root = Path(__file__).resolve().parents[2]
    path = jsonl_path or (root / "evals" / "end_to_end_v1.jsonl")
    records = load_jsonl(path)

    agree = 0
    total = 0
    for row in records:
        gold = str(row.get("decision", row.get("action", ""))).lower()
        pred = str(row.get("predicted_decision", row.get("replay_decision", ""))).lower()
        if not gold:
            continue
        total += 1
        if pred == gold:
            agree += 1

    agreement = agree / total if total else 0.0
    passed = agreement >= THRESH_E2E_AGREEMENT
    scores = {"decision_agreement": round(agreement, 4), "n": total, "threshold": THRESH_E2E_AGREEMENT}

    run_id = str(uuid.uuid4())
    with connection(autocommit=True) as conn:
        eid = ensure_eval_set(conn, "end_to_end_v1", "1", "end_to_end", records, "PRD Set C")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eval_runs (id, eval_set_id, target_version, run_at, scores_json, passed, promoted_to_production)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (run_id, eid, target_version, _utc_now(), json.dumps(scores), passed, False),
            )
    return {"eval_run_id": run_id, "eval_set_id": eid, "scores": scores, "passed": passed}


def run_end_to_end_eval_replay_from_db(
    jsonl_path: Path | None = None,
    *,
    target_version: str = "ranker_brief_replay",
    settings: SignalSettings | None = None,
) -> dict[str, Any]:
    """
    Set C (replay) — for each row with `cluster_id`, compute current `ranker_surface_eligibility`.
    Gold positive = decision `accept`; prediction positive = surface_eligible.
    This is a proxy: uses live cluster state, not a frozen feature snapshot (see PRD §13 / §10).
    """
    from ..ranker.service import ranker_surface_eligibility

    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    root = Path(__file__).resolve().parents[2]
    path = jsonl_path or (root / "evals" / "end_to_end_v1.jsonl")
    records = load_jsonl(path)

    agree = 0
    total = 0
    details: list[dict[str, Any]] = []
    for row in records:
        cid = row.get("cluster_id")
        gold = str(row.get("decision", row.get("action", ""))).lower().strip()
        if not cid or not gold:
            continue
        elig = ranker_surface_eligibility(str(cid), settings=s, refresh_stats=False)
        pred_pos = bool(elig.get("surface_eligible"))
        gold_pos = gold == "accept"
        total += 1
        match = pred_pos == gold_pos
        if match:
            agree += 1
        details.append(
            {
                "cluster_id": str(cid),
                "gold_decision": gold,
                "surface_eligible": pred_pos,
                "agree": match,
            }
        )

    agreement = agree / total if total else 0.0
    passed = agreement >= THRESH_E2E_AGREEMENT
    scores = {
        "decision_agreement": round(agreement, 4),
        "n": total,
        "threshold": THRESH_E2E_AGREEMENT,
        "mode": "ranker_surface_eligibility_replay",
        "note": "Gold accept ↔ eligible; other decisions ↔ ineligible. Uses current DB state.",
    }

    run_id = str(uuid.uuid4())
    with connection(autocommit=True) as conn:
        eid = ensure_eval_set(conn, "end_to_end_replay", "1", "end_to_end", records, "PRD Set C — ranker replay")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eval_runs (id, eval_set_id, target_version, run_at, scores_json, passed, promoted_to_production)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (run_id, eid, target_version, _utc_now(), json.dumps(scores), passed, False),
            )
    return {
        "eval_run_id": run_id,
        "eval_set_id": eid,
        "scores": scores,
        "passed": passed,
        "details_sample": details[:20],
    }


if __name__ == "__main__":
    import sys

    p = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    print(run_extractor_eval_stub(p))
