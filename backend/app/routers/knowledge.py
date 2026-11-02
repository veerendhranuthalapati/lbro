"""Read-only knowledge endpoints (compliance mapping + attack guides)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.compliance.knowledge.loader import knowledge_versions_snapshot, load_knowledge_bundle
from app.core.rbac import Permission
from app.dependencies import require_permission
from app.knowledge.loader import DECISION_SUPPORT_DISCLAIMER, load_attack_guides, get_guide
from app.models.user import User

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/versions")
async def knowledge_versions(
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_COMPLIANCE))],
) -> dict[str, str]:
    return knowledge_versions_snapshot()


@router.get("/attack-mapping")
async def attack_mapping(
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_COMPLIANCE))],
) -> dict[str, Any]:
    bundle = load_knowledge_bundle()
    return {
        "attack_enterprise_version": bundle.attack_to_technique.attack_enterprise_version,
        "disclaimer": bundle.laws.disclaimer,
        "mappings": {
            k: v.model_dump() for k, v in bundle.attack_to_technique.mappings.items()
        },
    }


@router.get("/attacks")
async def list_attack_guides(
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    q: str | None = Query(None, description="Search title or class id"),
) -> dict[str, Any]:
    bundle = load_attack_guides()
    items = []
    for class_id, guide in bundle.guides.items():
        if q:
            needle = q.lower()
            if needle not in class_id.lower() and needle not in guide.title.lower():
                if needle not in guide.summary_plain.lower():
                    continue
        items.append(
            {
                "class_id": class_id,
                "title": guide.title,
                "summary_plain": guide.summary_plain,
                "content_version": guide.content_version,
            }
        )
    return {
        "content_version": bundle.content_version,
        "disclaimer": DECISION_SUPPORT_DISCLAIMER,
        "items": items,
    }


@router.get("/attacks/{class_id}")
async def get_attack_guide(
    class_id: str,
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    audience: str = Query("analyst", pattern="^(executive|analyst)$"),
) -> dict[str, Any]:
    guide = get_guide(class_id)
    if guide is None:
        raise HTTPException(status_code=404, detail="Unknown attack class")
    data = guide.model_dump(mode="json")
    if audience == "executive":
        data["detail_body"] = guide.summary_plain
    else:
        data["detail_body"] = guide.how_it_works
    bundle = load_attack_guides()
    return {
        "content_version": bundle.content_version,
        "disclaimer": DECISION_SUPPORT_DISCLAIMER,
        "guide": data,
    }
