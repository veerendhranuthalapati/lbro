"""ML classification and model registry router."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.ml.classifier import classifier
from app.ml.model_registry import get_active_model_info, list_models
from app.models.incident import Incident
from app.models.user import User
from app.schemas.incident import NetworkFeaturesInput

router = APIRouter(prefix="/ml", tags=["ml"])


class ModelInfo(BaseModel):
    model_id: str
    version: str
    trained_at: str
    accuracy: float
    f1_score: float
    is_active: bool
    feature_count: int
    class_count: int


class MLStats(BaseModel):
    active_model: Optional[ModelInfo]
    registry: List[ModelInfo]
    predictions_today: int
    avg_confidence: float
    low_confidence_count: int
    attack_distribution: Dict[str, int]
    top_features: List[Dict[str, Any]]


@router.post("/classify")
async def classify_flow(
    features: NetworkFeaturesInput,
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ML))],
):
    """Classify a network flow and return attack category with confidence."""
    result = classifier.predict(features.model_dump())
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
):
    """Aggregated ML statistics: model info, prediction counts, attack distribution."""
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)

    # Incidents with ML predictions today
    today_result = await db.execute(
        select(func.count())
        .where(Incident.confidence_score.isnot(None))
        .where(func.date(Incident.created_at) == today)
    )
    predictions_today: int = today_result.scalar_one() or 0

    # Average confidence across all classified incidents
    avg_result = await db.execute(
        select(func.avg(Incident.confidence_score))
        .where(Incident.confidence_score.isnot(None))
    )
    avg_confidence: float = float(avg_result.scalar_one() or 0.0)

    # Low confidence count (needs analyst review)
    low_conf_result = await db.execute(
        select(func.count())
        .where(Incident.needs_analyst_review == True)  # noqa: E712
    )
    low_confidence_count: int = low_conf_result.scalar_one() or 0

    # Attack distribution
    dist_result = await db.execute(
        select(Incident.attack_category, func.count().label("cnt"))
        .where(Incident.attack_category.isnot(None))
        .group_by(Incident.attack_category)
        .order_by(func.count().desc())
    )
    attack_distribution: Dict[str, int] = {row.attack_category: row.cnt for row in dist_result}

    # Model info
    active_info = get_active_model_info()
    all_models = list_models()

    def to_model_info(m: dict, is_active: bool = False) -> ModelInfo:
        metrics = m.get("metrics", {})
        return ModelInfo(
            model_id=m.get("model_id", m.get("version", "heuristic")),
            version=m.get("version", "0.0.0"),
            trained_at=m.get("registered_at") or m.get("trained_at") or datetime.now(timezone.utc).isoformat(),
            accuracy=float(metrics.get("accuracy", m.get("accuracy", 0.0))),
            f1_score=float(metrics.get("f1", m.get("f1_score", 0.0))),
            is_active=is_active,
            feature_count=m.get("feature_count", 78),
            class_count=m.get("class_count", 15),
        )

    active_version = active_info.get("version") if active_info else None
    active_model = to_model_info(active_info, is_active=True) if active_info and active_info.get("version") else None
    registry = [to_model_info(m, is_active=(m.get("version") == active_version)) for m in (all_models if isinstance(all_models, list) else [])]

    # Top features from classifier (if model loaded)
    top_features: List[Dict[str, Any]] = []
    if hasattr(classifier, "model") and classifier.model is not None:
        try:
            importances = classifier.model.feature_importances_
            from app.ml.features import FEATURE_NAMES
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
    )
