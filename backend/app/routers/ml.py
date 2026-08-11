"""ML classification and model registry router."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.project_access import resolve_project_scope
from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.ml.classifier import classifier
from app.ml.model_registry import (
    get_active_model_info,
    get_evaluation_metrics,
    has_verified_evaluation,
    list_models,
    model_artifact_exists,
)
from app.models.incident import Incident
from app.models.user import User
from app.schemas.incident import NetworkFeaturesInput

router = APIRouter(prefix="/ml", tags=["ml"])


def _apply_project_scope(q, scope_ids: Optional[list[uuid.UUID]]):
    if scope_ids is None:
        return q
    if not scope_ids:
        return q.where(false())
    return q.where(Incident.project_id.in_(scope_ids))


class ModelInfo(BaseModel):
    model_id: str
    version: str
    trained_at: str
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    is_active: bool
    feature_count: int
    class_count: int
    model_loaded: bool = False


class MLStats(BaseModel):
    active_model: Optional[ModelInfo]
    registry: List[ModelInfo]
    predictions_today: int
    avg_confidence: float
    low_confidence_count: int
    attack_distribution: Dict[str, int]
    top_features: List[Dict[str, Any]]
    has_evaluation_data: bool = False
    runtime_mode: str = "heuristic"
    evaluation: Optional[Dict[str, Any]] = None


@router.post("/classify")
async def classify_flow(
    features: NetworkFeaturesInput,
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ML))],
):
    """Classify a network flow and return attack category with confidence."""
    result = await asyncio.to_thread(classifier.predict, features.model_dump())
    return result


@router.get("/model-info")
async def model_info(
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ML))],
):
    return get_active_model_info()


@router.get("/models")
async def list_model_versions(
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_ML))],
):
    return {"models": list_models()}


@router.get("/stats", response_model=MLStats)
async def ml_stats(
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ML))],
    db: AsyncSession = Depends(get_db),
    project_id: Optional[uuid.UUID] = Query(None),
):
    """Aggregated ML statistics: model info, prediction counts, attack distribution."""
    scope_ids = await resolve_project_scope(db, current_user, project_id)
    today = datetime.now(timezone.utc).date()

    def _pf(q):
        return _apply_project_scope(q, scope_ids)

    today_result = await db.execute(
        _pf(select(func.count()))
        .where(Incident.confidence_score.isnot(None))
        .where(func.date(Incident.created_at) == today)
    )
    predictions_today: int = today_result.scalar_one() or 0

    avg_result = await db.execute(
        _pf(select(func.avg(Incident.confidence_score)))
        .where(Incident.confidence_score.isnot(None))
    )
    avg_confidence: float = float(avg_result.scalar_one() or 0.0)

    low_conf_result = await db.execute(
        _pf(select(func.count()))
        .where(Incident.needs_analyst_review == True)  # noqa: E712
    )
    low_confidence_count: int = low_conf_result.scalar_one() or 0

    dist_result = await db.execute(
        _pf(select(Incident.attack_category, func.count().label("cnt")))
        .where(Incident.attack_category.isnot(None))
        .group_by(Incident.attack_category)
        .order_by(func.count().desc())
    )
    attack_distribution: Dict[str, int] = {row.attack_category: row.cnt for row in dist_result}

    # Model info — evaluation metrics only when artifact + registry metrics verified
    active_info = await asyncio.to_thread(get_active_model_info)
    all_models = await asyncio.to_thread(list_models)
    model_loaded = classifier._model is not None if hasattr(classifier, "_model") else False
    if not model_loaded:
        classifier._load()
        model_loaded = classifier._model is not None
    has_eval = await asyncio.to_thread(has_verified_evaluation)
    evaluation = await asyncio.to_thread(get_evaluation_metrics)

    def to_model_info(m: dict, is_active: bool = False) -> ModelInfo:
        metrics = m.get("metrics", {})
        include_eval = has_eval and is_active
        return ModelInfo(
            model_id=m.get("model_id", m.get("version", "heuristic")),
            version=m.get("version", "0.0.0"),
            trained_at=m.get("registered_at") or m.get("trained_at") or datetime.now(timezone.utc).isoformat(),
            accuracy=float(metrics["accuracy"]) if include_eval and metrics.get("accuracy") is not None else None,
            f1_score=float(metrics.get("f1") or metrics.get("f1_macro") or 0) if include_eval and (metrics.get("f1") or metrics.get("f1_macro")) else None,
            is_active=is_active,
            feature_count=m.get("feature_count", 78),
            class_count=m.get("class_count", 15),
            model_loaded=model_loaded and is_active,
        )

    active_version = active_info.get("version") if active_info else None
    active_model = to_model_info(active_info, is_active=True) if active_info and active_info.get("version") else None
    registry = [to_model_info(m, is_active=(m.get("version") == active_version)) for m in (all_models if isinstance(all_models, list) else [])]

    # Top features from classifier (if model loaded)
    top_features: List[Dict[str, Any]] = []
    if hasattr(classifier, "_model") and classifier._model is not None:
        try:
            importances = classifier._model.feature_importances_
            from app.ml.features import CICIDS2017_FEATURES as FEATURE_NAMES
            pairs = sorted(
                zip(FEATURE_NAMES, importances),
                key=lambda x: x[1],
                reverse=True,
            )[:10]
            top_features = [{"name": n, "importance": float(v)} for n, v in pairs]
        except Exception:
            pass

    return MLStats(
        active_model=active_model,
        registry=registry,
        predictions_today=predictions_today,
        avg_confidence=avg_confidence,
        low_confidence_count=low_confidence_count,
        attack_distribution=attack_distribution,
        top_features=top_features,
        has_evaluation_data=has_eval,
        runtime_mode="model" if model_loaded else "heuristic",
        evaluation=evaluation,
    )


# MITRE ATT&CK mapping for known attack categories
_MITRE_MAP: dict[str, str] = {
    "DoS Hulk":               "T1499",
    "DDoS":                   "T1498",
    "PortScan":                "T1046",
    "FTP-Patator":             "T1110",
    "SSH-Patator":             "T1110",
    "DoS slowloris":           "T1499",
    "DoS Slowhttptest":        "T1499",
    "DoS GoldenEye":           "T1499",
    "Bot":                     "T1587",
    "Web Attack - Brute Force":"T1110",
    "Web Attack - XSS":        "T1059",
    "Web Attack - Sql Injection": "T1190",
    "Infiltration":            "T1566",
    "Heartbleed":              "T1212",
}


@router.get("/flows")
async def ml_flows(
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ML))],
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    project_id: Optional[uuid.UUID] = Query(None),
):
    """
    Live ML flow classifications derived from recent incidents that have ML predictions.
    Each incident with network features becomes a CICIDSFlow entry consumed by ThreatIntelPage.
    """
    import hashlib

    scope_ids = await resolve_project_scope(db, current_user, project_id)
    result = await db.execute(
        _apply_project_scope(
            select(Incident)
            .where(Incident.confidence_score.isnot(None))
            .where(Incident.attack_category.isnot(None))
            .order_by(Incident.detected_at.desc())
            .limit(limit),
            scope_ids,
        )
    )
    incidents = result.scalars().all()

    flows = []
    for inc in incidents:
        nf = inc.network_features or {}
        # Derive a stable flow_id from incident id
        flow_id = hashlib.md5(str(inc.id).encode()).hexdigest()[:12]
        # Extract or default network feature values
        total_fwd = int(nf.get("total_fwd_packets", 0) or 0)
        total_bwd = int(nf.get("total_bwd_packets", 0) or 0)
        fwd_bytes = int(nf.get("total_fwd_bytes", 0) or 0)
        bwd_bytes = int(nf.get("total_bwd_bytes", 0) or 0)
        duration  = float(nf.get("flow_duration", 0) or 0)
        bps       = float(nf.get("flow_bytes_per_sec", 0) or 0)
        pps       = float(nf.get("flow_packets_per_sec", 0) or 0)
        fwd_iat   = float(nf.get("fwd_iat_mean", 0) or 0)
        bwd_iat   = float(nf.get("bwd_iat_mean", 0) or 0)

        attack_type = inc.attack_category or "BENIGN"
        mitre = _MITRE_MAP.get(attack_type)

        flows.append({
            "flow_id":              flow_id,
            "timestamp":            inc.detected_at.isoformat(),
            "src_ip":               inc.source_ip or "0.0.0.0",
            "dst_ip":               inc.destination_ip or "0.0.0.0",
            "src_port":             inc.source_port or 0,
            "dst_port":             inc.destination_port or 0,
            "protocol":             (inc.protocol or "TCP").upper(),
            "attack_type":          attack_type,
            "flow_duration":        duration,
            "total_fwd_packets":    total_fwd,
            "total_bwd_packets":    total_bwd,
            "total_fwd_bytes":      fwd_bytes,
            "total_bwd_bytes":      bwd_bytes,
            "flow_bytes_per_sec":   bps,
            "flow_packets_per_sec": pps,
            "fwd_iat_mean":         fwd_iat,
            "bwd_iat_mean":         bwd_iat,
            "confidence_score":     float(inc.confidence_score or 0.0),
            "is_false_positive":    False,
            "mitre_technique":      mitre,
            "label":                attack_type,
        })
    return flows


@router.get("/metrics")
async def ml_metrics(
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ML))],
    db: AsyncSession = Depends(get_db),
    project_id: Optional[uuid.UUID] = Query(None),
):
    """
    ML performance metrics for ThreatIntelPage.
    Evaluation metrics (accuracy, precision, recall, F1, MCC) come ONLY from
    registry.json when the model artifact is present. No synthetic fallbacks.
    """
    scope_ids = await resolve_project_scope(db, current_user, project_id)

    if not hasattr(classifier, "_loaded") or not classifier._loaded:
        classifier._load()
    model_loaded = classifier._model is not None
    has_eval = has_verified_evaluation()
    evaluation = get_evaluation_metrics()

    feature_importance: list[dict] = []
    if model_loaded:
        try:
            from app.ml.features import CICIDS2017_FEATURES as FEATURE_NAMES
            importances = classifier._model.feature_importances_
            pairs = sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True)[:10]
            feature_importance = [{"feature": n, "importance": float(v)} for n, v in pairs]
        except Exception:
            pass

    dist_result = await db.execute(
        _apply_project_scope(
            select(Incident.attack_category, func.count().label("cnt"))
            .where(Incident.attack_category.isnot(None))
            .group_by(Incident.attack_category),
            scope_ids,
        )
    )
    attack_dist = {row.attack_category: row.cnt for row in dist_result}

    conf_result = await db.execute(
        _apply_project_scope(
            select(
                Incident.attack_category,
                func.avg(Incident.confidence_score).label("avg_conf"),
                func.count().label("cnt"),
            )
            .where(Incident.attack_category.isnot(None))
            .where(Incident.confidence_score.isnot(None))
            .group_by(Incident.attack_category),
            scope_ids,
        )
    )
    per_class = [
        {
            "subject": row.attack_category,
            "A": round(float(row.avg_conf or 0) * 100, 1),
            "fullMark": 100,
            "count": row.cnt,
        }
        for row in conf_result
    ]

    fp_analysis: list[dict] = []
    if has_eval and evaluation and evaluation.get("confusion_matrix"):
        cm = evaluation["confusion_matrix"]
        labels = evaluation.get("labels") or []
        for i, label in enumerate(labels):
            if i < len(cm):
                row = cm[i]
                tp = row[i] if i < len(row) else 0
                fp = sum(row) - tp
                col_sum = sum(cm[j][i] for j in range(len(cm)) if j < len(cm[j]))
                fn = col_sum - tp
                fp_analysis.append({"attack": label, "tp": tp, "fp": fp, "fn": fn})

    tactic_map = {
        "DoS Hulk": "Impact", "DDoS": "Impact", "DoS slowloris": "Impact",
        "DoS GoldenEye": "Impact", "DoS Slowhttptest": "Impact",
        "PortScan": "Discovery",
        "FTP-Patator": "Credential Access", "SSH-Patator": "Credential Access",
        "Bot": "Command & Control",
        "Web Attack - Brute Force": "Initial Access",
        "Web Attack - XSS": "Execution",
        "Web Attack - Sql Injection": "Initial Access",
        "Infiltration": "Lateral Movement",
        "Heartbleed": "Credential Access",
    }
    tactic_colors = {
        "Impact": "#e54e1b", "Discovery": "#3a7a50", "Credential Access": "#d97706",
        "Command & Control": "#7c3aed", "Initial Access": "#e54e1b",
        "Execution": "#d97706", "Lateral Movement": "#e54e1b", "Other": "#6b6560",
    }
    tactic_counts: dict[str, int] = {}
    for attack, cnt in attack_dist.items():
        tactic = tactic_map.get(attack, "Other")
        tactic_counts[tactic] = tactic_counts.get(tactic, 0) + cnt

    tactic_distribution = [
        {"tactic": tactic, "count": count, "color": tactic_colors.get(tactic, "#6b6560")}
        for tactic, count in sorted(tactic_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "has_evaluation_data": has_eval,
        "model_loaded": model_loaded,
        "runtime_mode": "model" if model_loaded else "heuristic",
        "evaluation": evaluation,
        "feature_importance": feature_importance,
        "per_class_confidence": per_class,
        "false_positive_analysis": fp_analysis,
        "tactic_distribution": tactic_distribution,
    }
