"""Read-only compliance knowledge endpoints."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.compliance.knowledge.loader import knowledge_versions_snapshot, load_knowledge_bundle
from app.core.rbac import Permission
from app.dependencies import require_permission
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
