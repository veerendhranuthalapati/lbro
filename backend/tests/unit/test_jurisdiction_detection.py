"""
LBRO — Unit tests for IncidentService jurisdiction detection
"""
from unittest.mock import AsyncMock

from app.models.incident import Jurisdiction
from app.schemas.incident import IncidentCreate
from app.services.incident_service import IncidentService


def make_service() -> IncidentService:
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return IncidentService(db)


def make_payload(**kwargs) -> IncidentCreate:
    defaults = {
        "title": "Test incident",
        "severity": "MEDIUM",
        "source_system": "test",
        "contains_pii": False,
        "contains_phi": False,
    }
    defaults.update(kwargs)
    return IncidentCreate(**defaults)


class TestJurisdictionDetection:
    def test_pii_triggers_gdpr_and_dpdpa(self):
        svc = make_service()
        payload = make_payload(contains_pii=True)
        result = svc._detect_jurisdictions(payload)
        assert Jurisdiction.GDPR in result
        assert Jurisdiction.DPDPA in result

    def test_phi_triggers_hipaa(self):
        svc = make_service()
        payload = make_payload(contains_phi=True)
        result = svc._detect_jurisdictions(payload)
        assert Jurisdiction.HIPAA in result

    def test_pii_and_phi_triggers_all_three(self):
        svc = make_service()
        payload = make_payload(contains_pii=True, contains_phi=True)
        result = svc._detect_jurisdictions(payload)
        assert Jurisdiction.GDPR in result
        assert Jurisdiction.DPDPA in result
        assert Jurisdiction.HIPAA in result

    def test_no_flags_no_jurisdiction_when_no_records(self):
        svc = make_service()
        payload = make_payload()
        result = svc._detect_jurisdictions(payload)
        assert result == []

    def test_records_count_triggers_gdpr_by_default(self):
        svc = make_service()
        payload = make_payload(affected_records_count=100)
        result = svc._detect_jurisdictions(payload)
        assert Jurisdiction.GDPR in result

    def test_zero_records_no_default_gdpr(self):
        svc = make_service()
        payload = make_payload(affected_records_count=0)
        result = svc._detect_jurisdictions(payload)
        assert result == []
