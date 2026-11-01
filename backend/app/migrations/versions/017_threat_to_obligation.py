"""Threat-to-obligation data map and exposure assessment tables."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017_threat_to_obligation"
down_revision: Union[str, None] = "016_ml_classification_retry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "compliance_inference_mode",
            sa.String(20),
            nullable=False,
            server_default="hybrid",
        ),
    )

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("environment", sa.String(50), nullable=True),
        sa.Column("owner", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(50), nullable=False, server_default="internal"),
        sa.Column("criticality", sa.String(50), nullable=True),
        sa.Column("data_categories", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("encrypted_at_rest", sa.Boolean(), nullable=True),
        sa.Column("identifiers", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("project_id", "name", name="uq_assets_project_name"),
    )
    op.create_index("ix_assets_project_id", "assets", ["project_id"])

    op.create_table(
        "asset_residency",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("jurisdiction_code", sa.String(20), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("count_basis", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("as_of", sa.Date(), nullable=True),
        sa.Column("data_category", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "asset_id",
            "jurisdiction_code",
            "data_category",
            name="uq_asset_residency_jurisdiction_category",
        ),
    )
    op.create_index("ix_asset_residency_asset_id", "asset_residency", ["asset_id"])
    op.create_index("ix_asset_residency_jurisdiction_code", "asset_residency", ["jurisdiction_code"])

    op.create_table(
        "incident_exposure_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("engine_version", sa.String(32), nullable=False),
        sa.Column("knowledge_versions", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("inputs_hash", sa.String(64), nullable=False),
        sa.Column("overall_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="provisional"),
        sa.Column("results", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("trace", postgresql.JSON(), nullable=False, server_default="[]"),
    )
    op.create_index(
        "ix_incident_exposure_assessments_incident_id",
        "incident_exposure_assessments",
        ["incident_id"],
    )

    op.create_table(
        "incident_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("link_source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("match_confidence", sa.String(20), nullable=False, server_default="high"),
        sa.Column("exposure_fraction", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "confirmed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="confirmed"),
        sa.UniqueConstraint("incident_id", "asset_id", name="uq_incident_asset"),
    )
    op.create_index("ix_incident_assets_incident_id", "incident_assets", ["incident_id"])
    op.create_index("ix_incident_assets_asset_id", "incident_assets", ["asset_id"])

    op.add_column(
        "compliance_records",
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
    )
    op.add_column("compliance_records", sa.Column("rule_id", sa.String(100), nullable=True))
    op.add_column("compliance_records", sa.Column("rule_version", sa.String(32), nullable=True))
    op.add_column(
        "compliance_records",
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incident_exposure_assessments.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "compliance_records",
        sa.Column("clock_start_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "compliance_records",
        sa.Column("analyst_decision", sa.String(20), nullable=True),
    )
    op.add_column("compliance_records", sa.Column("decision_reason", sa.Text(), nullable=True))
    op.add_column(
        "compliance_records",
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_compliance_records_assessment_id",
        "compliance_records",
        ["assessment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_compliance_records_assessment_id", table_name="compliance_records")
    op.drop_column("compliance_records", "provisional")
    op.drop_column("compliance_records", "decision_reason")
    op.drop_column("compliance_records", "analyst_decision")
    op.drop_column("compliance_records", "clock_start_at")
    op.drop_column("compliance_records", "assessment_id")
    op.drop_column("compliance_records", "rule_version")
    op.drop_column("compliance_records", "rule_id")
    op.drop_column("compliance_records", "source")

    op.drop_index("ix_incident_assets_asset_id", table_name="incident_assets")
    op.drop_index("ix_incident_assets_incident_id", table_name="incident_assets")
    op.drop_table("incident_assets")

    op.drop_index(
        "ix_incident_exposure_assessments_incident_id",
        table_name="incident_exposure_assessments",
    )
    op.drop_table("incident_exposure_assessments")

    op.drop_index("ix_asset_residency_jurisdiction_code", table_name="asset_residency")
    op.drop_index("ix_asset_residency_asset_id", table_name="asset_residency")
    op.drop_table("asset_residency")

    op.drop_index("ix_assets_project_id", table_name="assets")
    op.drop_table("assets")

    op.drop_column("projects", "compliance_inference_mode")
