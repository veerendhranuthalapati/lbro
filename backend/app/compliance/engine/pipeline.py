"""
Pure exposure inference pipeline — no database I/O.

Maps attack class → MITRE techniques → data categories → asset residency → legal rules.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.compliance.engine.types import (
    AssetInput,
    ClassificationInput,
    EngineConfigInput,
    EngineWarning,
    ExposureAssessmentResult,
    IncidentContextInput,
    InferredObligation,
    JurisdictionExposure,
    TraceStep,
)
from app.compliance.knowledge.loader import load_knowledge_bundle
from app.compliance.knowledge.schemas import KnowledgeBundle, LegalRule


def run_exposure_assessment(
    classification: ClassificationInput,
    incident: IncidentContextInput,
    assets: tuple[AssetInput, ...],
    config: EngineConfigInput,
    *,
    bundle: KnowledgeBundle | None = None,
) -> ExposureAssessmentResult:
    """Evaluate obligations from ML output, assets, and knowledge base rules."""
    kb = bundle or load_knowledge_bundle()
    disclaimer = kb.laws.disclaimer
    trace: list[TraceStep] = []
    warnings: list[EngineWarning] = []
    provisional_reasons: list[str] = []

    if config.inference_mode == "manual":
        return _manual_only_result(incident, config, kb, disclaimer)

    attack = classification.attack_category or "BENIGN"
    mapping = kb.attack_to_technique.mappings.get(attack)
    if mapping is None:
        warnings.append(
            EngineWarning(
                code="unmapped_attack_class",
                message=f"No technique mapping for attack class {attack!r}",
                context={"attack_category": attack},
            )
        )
        techniques: list[dict[str, Any]] = []
    else:
        if mapping.unmapped_reason and not mapping.techniques:
            trace.append(
                TraceStep(
                    step="attack_class",
                    detail={"attack_category": attack, "unmapped_reason": mapping.unmapped_reason},
                )
            )
            techniques = []
        else:
            techniques = [
                {
                    "technique_id": t.technique_id,
                    "name": t.name,
                    "likelihood": t.likelihood,
                    "rationale": t.rationale,
                    "confirms_exfiltration": t.confirms_exfiltration,
                }
                for t in mapping.techniques
            ]
            trace.append(TraceStep(step="attack_class", detail={"attack_category": attack, "techniques": techniques}))

    impact_types: set[str] = set()
    candidate_categories: set[str] = set()
    confirms_exfil = False
    for t in mapping.techniques if mapping else []:
        tid = t.technique_id.split(".")[0]
        impact = kb.technique_to_data.techniques.get(tid)
        if not impact:
            continue
        impact_types.update(impact.impact_types)
        candidate_categories.update(impact.data_categories_at_risk)
        if t.confirms_exfiltration:
            confirms_exfil = True
        trace.append(
            TraceStep(
                step="technique_impact",
                detail={"technique_id": tid, "impact_types": list(impact.impact_types), "categories": impact.data_categories_at_risk},
            )
        )

    availability_only = impact_types <= {"availability"} and bool(impact_types)
    no_breach = availability_only
    no_breach_explanation = (
        "Impact is availability-only; breach-notification rules requiring confidentiality/integrity are not triggered by this assessment."
        if no_breach
        else None
    )

    confirmed_assets = [a for a in assets if a.link_status == "confirmed"]
    if not confirmed_assets:
        warnings.append(
            EngineWarning(
                code="no_assets_linked",
                message="No confirmed assets linked; jurisdiction counts and inferred rules use manual jurisdictions only.",
            )
        )

    exposed_categories: set[str] = set()
    jurisdiction_rows: dict[str, list[int]] = {}

    for asset in confirmed_assets:
        if confirms_exfil:
            asset_exposed = set(asset.data_categories)
            note = "confirms_exfiltration on technique mapping expands to full asset category set"
        else:
            asset_exposed = candidate_categories.intersection(set(asset.data_categories))
            for tid in [t.technique_id.split(".")[0] for t in (mapping.techniques if mapping else [])]:
                imp = kb.technique_to_data.techniques.get(tid)
                if imp and imp.exposure_assumption == "credentials_only":
                    asset_exposed.add("authentication_credentials")
                    note = "credentials_only exposure assumption adds authentication_credentials"
                    break
            else:
                note = "intersection of candidate categories with asset inventory"
        exposed_categories.update(asset_exposed)
        trace.append(
            TraceStep(
                step="asset_exposure",
                detail={"asset_id": asset.asset_id, "categories": sorted(asset_exposed), "reason": note},
            )
        )
        for res in asset.residency:
            if res.record_count is None:
                warnings.append(
                    EngineWarning(
                        code="unknown_record_count",
                        message=f"Unknown record count for asset {asset.name} in {res.jurisdiction_code}",
                        context={"asset_id": asset.asset_id, "jurisdiction": res.jurisdiction_code},
                    )
                )
                continue
            scaled = int(res.record_count * asset.exposure_fraction)
            jurisdiction_rows.setdefault(res.jurisdiction_code, []).append(scaled)
            trace.append(
                TraceStep(
                    step="residency_count",
                    detail={
                        "asset_id": asset.asset_id,
                        "jurisdiction": res.jurisdiction_code,
                        "count": scaled,
                        "basis": res.count_basis,
                    },
                )
            )

    jurisdiction_exposure: list[JurisdictionExposure] = []
    for code, counts in jurisdiction_rows.items():
        if not counts:
            continue
        jurisdiction_exposure.append(
            JurisdictionExposure(
                jurisdiction_code=code,
                lower_bound=max(counts),
                upper_bound=sum(counts),
                point_estimate=None,
                basis="upper_bound is sum across assets; lower_bound is max single asset (deduplication unknown)",
                deduplication_unknown=True,
            )
        )

    supported_jurisdictions: set[str] = set()
    for rule in kb.laws.rules:
        supported_jurisdictions.update(rule.jurisdiction_codes)

    for je in jurisdiction_exposure:
        if je.jurisdiction_code not in supported_jurisdictions and not _jurisdiction_covered_by_rule_pack(je.jurisdiction_code, kb):
            warnings.append(
                EngineWarning(
                    code="unsupported_jurisdiction",
                    message=f"No rule pack for jurisdiction {je.jurisdiction_code}",
                    context={"jurisdiction": je.jurisdiction_code, "upper_bound": je.upper_bound},
                )
            )

    clock_start, clock_source = _select_clock_start(incident)
    if clock_source == "detected_at_fallback":
        warnings.append(
            EngineWarning(
                code="clock_start_detection",
                message="Confirmation time missing; using detection time for deadlines",
            )
        )

    personal_data = incident.personal_data_involved or any(
        kb.data_categories.categories[c].is_personal_data for c in exposed_categories if c in kb.data_categories.categories
    )

    obligations: list[InferredObligation] = []
    for rule in kb.laws.rules:
        if not _rule_applies(rule, impact_types, exposed_categories, personal_data, incident, jurisdiction_exposure, availability_only):
            continue
        for ob in rule.obligations:
            deadline_at = _compute_deadline(ob.deadline.amount, ob.deadline.unit, clock_start)
            trace.append(
                TraceStep(
                    step="rule_obligation",
                    detail={
                        "rule_id": rule.rule_id,
                        "obligation_id": ob.obligation_id,
                        "deadline_at": deadline_at.isoformat() if deadline_at else None,
                    },
                )
            )
            obligations.append(
                InferredObligation(
                    rule_id=rule.rule_id,
                    rule_version=rule.rule_version,
                    obligation_id=ob.obligation_id,
                    law=rule.law,
                    description=ob.description,
                    recipient_type=ob.recipient_type,
                    recipient=ob.recipient,
                    deadline_at=deadline_at,
                    clock_start_at=clock_start,
                    clock_start_source=clock_source,
                    provisional=False,
                    requires_assessment=ob.is_conditional_on_risk_assessment,
                    origin="inferred",
                    verification_status=rule.verification_status,
                    legal_review_status=rule.legal_review_status,
                )
            )
            if rule.verification_status == "unverified":
                warnings.append(EngineWarning(code="unverified_rule", message=f"Rule {rule.rule_id} is unverified", context={"rule_id": rule.rule_id}))
            if rule.legal_review_status == "unreviewed":
                warnings.append(
                    EngineWarning(
                        code="rule_unreviewed_by_counsel",
                        message=f"Rule {rule.rule_id} not reviewed by counsel",
                        context={"rule_id": rule.rule_id},
                    )
                )

    if no_breach and not obligations:
        trace.append(TraceStep(step="no_breach_notification_trigger", detail={"explanation": no_breach_explanation}))

    _apply_ml_gating(classification, config, provisional_reasons)
    for ob in obligations:
        if provisional_reasons:
            ob.provisional = True

    overall_confidence = _overall_confidence(classification, assets, jurisdiction_exposure)
    status = "provisional" if provisional_reasons else "confirmed"

    if config.inference_mode in ("hybrid", "inferred") and incident.manual_jurisdictions:
        trace.append(
            TraceStep(
                step="manual_jurisdictions",
                detail={"jurisdictions": list(incident.manual_jurisdictions), "mode": config.inference_mode},
            )
        )

    payload = {
        "classification": classification.__dict__,
        "incident": {**incident.__dict__, "detected_at": incident.detected_at.isoformat(), "confirmed_at": incident.confirmed_at.isoformat() if incident.confirmed_at else None},
        "assets": [a.__dict__ for a in assets],
        "config": config.__dict__,
    }
    inputs_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    return ExposureAssessmentResult(
        status=status,
        overall_confidence=overall_confidence,
        provisional_reasons=provisional_reasons,
        techniques=techniques,
        exposed_categories=sorted(exposed_categories),
        jurisdiction_exposure=jurisdiction_exposure,
        obligations=obligations,
        warnings=warnings,
        trace=trace,
        no_breach_notification_trigger=no_breach and not obligations,
        no_breach_explanation=no_breach_explanation,
        inputs_hash=inputs_hash,
        disclaimer=disclaimer,
    )


def _manual_only_result(
    incident: IncidentContextInput,
    config: EngineConfigInput,
    kb: KnowledgeBundle,
    disclaimer: str,
) -> ExposureAssessmentResult:
    return ExposureAssessmentResult(
        status="confirmed",
        overall_confidence=1.0,
        provisional_reasons=[],
        techniques=[],
        exposed_categories=[],
        jurisdiction_exposure=[],
        obligations=[],
        warnings=[
            EngineWarning(code="inference_disabled", message="Project compliance_inference_mode is manual"),
        ],
        trace=[TraceStep(step="mode", detail={"inference_mode": "manual"})],
        no_breach_notification_trigger=False,
        no_breach_explanation=None,
        inputs_hash="manual",
        disclaimer=disclaimer,
    )


def _jurisdiction_covered_by_rule_pack(code: str, kb: KnowledgeBundle) -> bool:
    for rule in kb.laws.rules:
        if code in rule.jurisdiction_codes:
            return True
    return False


def _select_clock_start(incident: IncidentContextInput) -> tuple[datetime, str]:
    if incident.confirmed_at:
        return incident.confirmed_at.astimezone(timezone.utc), "confirmed_at"
    return incident.detected_at.astimezone(timezone.utc), "detected_at_fallback"


def _compute_deadline(amount: int | None, unit: str, start: datetime) -> datetime | None:
    if amount is None or unit in ("without_delay", "without_unreasonable_delay", "undue_delay"):
        return None
    if unit == "hours":
        return start + timedelta(hours=amount)
    if unit == "days":
        return start + timedelta(days=amount)
    return None


def _rule_applies(
    rule: LegalRule,
    impact_types: set[str],
    exposed_categories: set[str],
    personal_data: bool,
    incident: IncidentContextInput,
    jurisdictions: list[JurisdictionExposure],
    availability_only: bool,
) -> bool:
    cond = rule.applies_when
    if cond.excludes_availability_only and availability_only:
        return False
    if cond.requires_cyber_incident_reporting:
        return any(j.jurisdiction_code == "IN" for j in jurisdictions) or "IN" in incident.manual_jurisdictions
    if cond.requires_personal_data and not personal_data:
        return False
    if cond.requires_impact_types:
        if not impact_types.intersection(set(cond.requires_impact_types)):
            return False
    if cond.requires_categories_any:
        if not exposed_categories.intersection(set(cond.requires_categories_any)):
            if not (cond.requires_categories_any == ["health_data"] and incident.health_data_involved):
                return False
    active_jurisdictions = {j.jurisdiction_code for j in jurisdictions} | set(incident.manual_jurisdictions)
    if not active_jurisdictions.intersection(set(rule.jurisdiction_codes)):
        return False
    if cond.min_record_count_point is not None:
        relevant = [j for j in jurisdictions if j.jurisdiction_code in rule.jurisdiction_codes]
        if not relevant:
            return False
        upper = max((j.upper_bound or 0) for j in relevant)
        if upper < cond.min_record_count_point:
            return False
    return True


def _apply_ml_gating(
    classification: ClassificationInput,
    config: EngineConfigInput,
    provisional_reasons: list[str],
) -> None:
    if classification.source != "model":
        provisional_reasons.append(f"classification source={classification.source}")
    if classification.ood_flag:
        provisional_reasons.append("ood_flag")
    if classification.needs_review:
        provisional_reasons.append("needs_review")
    if classification.confidence < config.ml_review_threshold:
        provisional_reasons.append(f"confidence below threshold ({classification.confidence:.2f})")


def _overall_confidence(
    classification: ClassificationInput,
    assets: tuple[AssetInput, ...],
    jurisdictions: list[JurisdictionExposure],
) -> float:
    bands = [classification.confidence]
    for a in assets:
        if a.link_status == "confirmed":
            bands.append({"high": 0.95, "medium": 0.7, "low": 0.4}[a.match_confidence])
    if any(j.lower_bound is None for j in jurisdictions):
        bands.append(0.3)
    return min(bands) if bands else 0.0
