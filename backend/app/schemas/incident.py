"""Incident schemas."""
from __future__ import annotations

import ipaddress
import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Allowed protocol values (case-insensitive input, stored lowercase)
_ALLOWED_PROTOCOLS = {"tcp", "udp", "icmp", "http", "https", "dns", "ftp", "ssh", "smtp", "other"}


def _validate_ip(value: str | None) -> str | None:
    """Return the IP unchanged if valid IPv4/IPv6, else raise ValueError."""
    if value is None:
        return value
    value = value.strip()
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise ValueError(f"'{value}' is not a valid IPv4 or IPv6 address")
    return value


class NetworkFeaturesInput(BaseModel):
    """Raw network flow features for ML classification (CICIDS2017 feature set)."""
    destination_port: Optional[int] = None
    flow_duration: Optional[float] = None
    total_fwd_packets: Optional[int] = None
    total_bwd_packets: Optional[int] = None
    total_length_fwd_packets: Optional[float] = None
    total_length_bwd_packets: Optional[float] = None
    fwd_packet_length_max: Optional[float] = None
    fwd_packet_length_min: Optional[float] = None
    fwd_packet_length_mean: Optional[float] = None
    fwd_packet_length_std: Optional[float] = None
    bwd_packet_length_max: Optional[float] = None
    bwd_packet_length_min: Optional[float] = None
    bwd_packet_length_mean: Optional[float] = None
    bwd_packet_length_std: Optional[float] = None
    flow_bytes_per_sec: Optional[float] = None
    flow_packets_per_sec: Optional[float] = None
    flow_iat_mean: Optional[float] = None
    flow_iat_std: Optional[float] = None
    flow_iat_max: Optional[float] = None
    flow_iat_min: Optional[float] = None
    fwd_iat_total: Optional[float] = None
    fwd_iat_mean: Optional[float] = None
    fwd_iat_std: Optional[float] = None
    fwd_iat_max: Optional[float] = None
    fwd_iat_min: Optional[float] = None
    bwd_iat_total: Optional[float] = None
    bwd_iat_mean: Optional[float] = None
    bwd_iat_std: Optional[float] = None
    bwd_iat_max: Optional[float] = None
    bwd_iat_min: Optional[float] = None
    fwd_psh_flags: Optional[int] = None
    bwd_psh_flags: Optional[int] = None
    fwd_urg_flags: Optional[int] = None
    bwd_urg_flags: Optional[int] = None
    fwd_header_length: Optional[float] = None
    bwd_header_length: Optional[float] = None
    fwd_packets_per_sec: Optional[float] = None
    bwd_packets_per_sec: Optional[float] = None
    min_packet_length: Optional[float] = None
    max_packet_length: Optional[float] = None
    packet_length_mean: Optional[float] = None
    packet_length_std: Optional[float] = None
    packet_length_variance: Optional[float] = None
    fin_flag_count: Optional[int] = None
    syn_flag_count: Optional[int] = None
    rst_flag_count: Optional[int] = None
    psh_flag_count: Optional[int] = None
    ack_flag_count: Optional[int] = None
    urg_flag_count: Optional[int] = None
    cwe_flag_count: Optional[int] = None
    ece_flag_count: Optional[int] = None
    down_up_ratio: Optional[float] = None
    average_packet_size: Optional[float] = None
    avg_fwd_segment_size: Optional[float] = None
    avg_bwd_segment_size: Optional[float] = None
    fwd_avg_bytes_per_bulk: Optional[float] = None
    fwd_avg_packets_per_bulk: Optional[float] = None
    fwd_avg_bulk_rate: Optional[float] = None
    bwd_avg_bytes_per_bulk: Optional[float] = None
    bwd_avg_packets_per_bulk: Optional[float] = None
    bwd_avg_bulk_rate: Optional[float] = None
    subflow_fwd_packets: Optional[int] = None
    subflow_fwd_bytes: Optional[float] = None
    subflow_bwd_packets: Optional[int] = None
    subflow_bwd_bytes: Optional[float] = None
    init_win_bytes_forward: Optional[float] = None
    init_win_bytes_backward: Optional[float] = None
    act_data_pkt_fwd: Optional[float] = None
    min_seg_size_forward: Optional[float] = None
    active_mean: Optional[float] = None
    active_std: Optional[float] = None
    active_max: Optional[float] = None
    active_min: Optional[float] = None
    idle_mean: Optional[float] = None
    idle_std: Optional[float] = None
    idle_max: Optional[float] = None
    idle_min: Optional[float] = None


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    severity: Optional[Literal["critical", "high", "medium", "low", "info"]] = "medium"
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    source_port: Optional[int] = Field(None, ge=0, le=65535)
    destination_port: Optional[int] = Field(None, ge=0, le=65535)
    protocol: Optional[str] = None
    network_features: Optional[NetworkFeaturesInput] = None
    affected_jurisdictions: Optional[List[str]] = Field(None, max_length=20)
    personal_data_involved: bool = False
    health_data_involved: bool = False
    # Optional: assign to a specific project at creation time
    project_id: Optional[uuid.UUID] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Title must be at least 3 non-whitespace characters")
        return v

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v if v else None

    @field_validator("source_ip")
    @classmethod
    def validate_source_ip(cls, v: str | None) -> str | None:
        return _validate_ip(v)

    @field_validator("destination_ip")
    @classmethod
    def validate_destination_ip(cls, v: str | None) -> str | None:
        return _validate_ip(v)

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in _ALLOWED_PROTOCOLS:
            raise ValueError(
                f"Protocol must be one of: {', '.join(sorted(_ALLOWED_PROTOCOLS))}"
            )
        return v

    @field_validator("affected_jurisdictions")
    @classmethod
    def validate_jurisdictions(cls, v: List[str] | None) -> List[str] | None:
        if v is None:
            return v
        cleaned = [j.strip().upper() for j in v if j.strip()]
        # Deduplicate while preserving order
        seen: set[str] = set()
        result = [j for j in cleaned if not (j in seen or seen.add(j))]  # type: ignore[func-returns-value]
        return result or None

class IncidentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    status: Optional[Literal["new", "triaging", "contained", "eradicating", "recovering", "closed", "reopened"]] = None
    severity: Optional[Literal["critical", "high", "medium", "low", "info"]] = None
    assigned_to: Optional[uuid.UUID] = None
    affected_jurisdictions: Optional[List[str]] = None
    personal_data_involved: Optional[bool] = None
    health_data_involved: Optional[bool] = None
    containment_actions: Optional[List[str]] = Field(None, max_length=50)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Title must be at least 3 non-whitespace characters")
        return v

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v if v else None


class IncidentActionResponse(BaseModel):
    id: uuid.UUID
    action_type: str
    description: str
    automated: bool
    result: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentResponse(BaseModel):
    id: uuid.UUID
    external_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: str
    severity: str
    attack_category: Optional[str] = None
    confidence_score: Optional[float] = None
    ml_model_version: Optional[str] = None
    needs_analyst_review: bool
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    source_port: Optional[int] = None
    destination_port: Optional[int] = None
    protocol: Optional[str] = None
    affected_jurisdictions: Optional[List[str]] = None
    personal_data_involved: bool
    health_data_involved: bool
    assigned_to: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None
    detected_at: datetime
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    actions: List[IncidentActionResponse] = []

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    items: List[IncidentResponse]
    total: int
    page: int
    page_size: int


class StatusChangeRequest(BaseModel):
    status: str = Field(min_length=1, max_length=50)
    notes: Optional[str] = Field(None, max_length=1000)


class ReopenRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000)
