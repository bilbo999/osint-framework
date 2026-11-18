"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-18 15:56:22.817002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.types import JSONType, NullableJSONType, UTCDateTime

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_outbox",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=32), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("payload", JSONType, nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("processed_at", UTCDateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_graph_outbox")),
    )
    op.create_index(
        op.f("ix_graph_outbox_investigation_id"), "graph_outbox", ["investigation_id"], unique=False
    )
    op.create_index("ix_graph_outbox_pending", "graph_outbox", ["processed_at", "id"], unique=False)
    op.create_table(
        "investigations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "queued",
                "running",
                "completed",
                "completed_with_warnings",
                "failed",
                "closed",
                name="investigationstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.Column("closed_at", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investigations")),
    )
    op.create_index("ix_investigations_status", "investigations", ["status"], unique=False)
    op.create_table(
        "sources",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "dns",
                "rdap",
                "tls",
                "certificate_transparency",
                "http_api",
                "public_web",
                "local_database",
                "local_parser",
                "synthetic",
                name="sourcekind",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("homepage_url", sa.String(length=2048), nullable=True),
        sa.Column("terms_url", sa.String(length=2048), nullable=True),
        sa.Column("requires_api_key", sa.Boolean(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_sources")),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=True),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("details", JSONType, nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            name=op.f("fk_audit_log_investigation_id_investigations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False)
    op.create_index(
        op.f("ix_audit_log_investigation_id"), "audit_log", ["investigation_id"], unique=False
    )
    op.create_table(
        "entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "person",
                "organization",
                "domain",
                "subdomain",
                "ip_address",
                "email",
                "username",
                "phone",
                "url",
                "certificate",
                "autonomous_system",
                name="entitytype",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("attributes", JSONType, nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_entities_confidence_range")
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            name=op.f("fk_entities_investigation_id_investigations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entities")),
    )
    op.create_index(
        "ix_entities_investigation_type", "entities", ["investigation_id", "type"], unique=False
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "dns_response",
                "rdap_response",
                "http_response",
                "api_response",
                "tls_certificate",
                "ct_log_entry",
                "computed",
                "synthetic",
                name="evidencekind",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("collector", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("request_summary", sa.String(length=2048), nullable=True),
        sa.Column("retrieved_at", UTCDateTime(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("metadata", JSONType, nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            name=op.f("fk_evidence_investigation_id_investigations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source"], ["sources.name"], name=op.f("fk_evidence_source_sources")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
    )
    op.create_index(
        op.f("ix_evidence_investigation_id"), "evidence", ["investigation_id"], unique=False
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            name=op.f("fk_reports_investigation_id_investigations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index(
        op.f("ix_reports_investigation_id"), "reports", ["investigation_id"], unique=False
    )
    op.create_table(
        "scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("exposure", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("breakdown", JSONType, nullable=False),
        sa.Column("config_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_scores_confidence_range")
        ),
        sa.CheckConstraint(
            "exposure >= 0 AND exposure <= 100", name=op.f("ck_scores_exposure_range")
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            name=op.f("fk_scores_investigation_id_investigations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scores")),
    )
    op.create_index(
        op.f("ix_scores_investigation_id"), "scores", ["investigation_id"], unique=False
    )
    op.create_table(
        "targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "person",
                "organization",
                "domain",
                "ip_address",
                "email",
                "username",
                "phone",
                "url",
                name="targettype",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("value", sa.String(length=2048), nullable=False),
        sa.Column("seeds", NullableJSONType, nullable=True),
        sa.Column("parent_target_id", sa.Uuid(), nullable=True),
        sa.Column("pivot_depth", sa.Integer(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            name=op.f("fk_targets_investigation_id_investigations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_target_id"],
            ["targets.id"],
            name=op.f("fk_targets_parent_target_id_targets"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_targets")),
    )
    op.create_index(
        op.f("ix_targets_investigation_id"), "targets", ["investigation_id"], unique=False
    )
    op.create_table(
        "collector_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("collector", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "success",
                "timeout",
                "error",
                "rate_limited",
                "circuit_open",
                "skipped",
                name="collectorrunstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("findings_count", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            name=op.f("fk_collector_runs_investigation_id_investigations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["targets.id"],
            name=op.f("fk_collector_runs_target_id_targets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collector_runs")),
    )
    op.create_index(
        op.f("ix_collector_runs_investigation_id"),
        "collector_runs",
        ["investigation_id"],
        unique=False,
    )
    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "domain",
                "subdomain",
                "tld",
                "ip_address",
                "email",
                "username",
                "phone",
                "url",
                "person_name",
                "organization",
                "certificate",
                "mx_record",
                "ns_record",
                "txt_record",
                "spf_policy",
                "dmarc_policy",
                "domain_registration",
                "network_registration",
                "reverse_dns",
                "autonomous_system",
                "geolocation",
                "email_validation",
                "phone_metadata",
                "gravatar_profile",
                "account_presence",
                "breach_exposure",
                "technology",
                name="findingtype",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("raw_value", JSONType, nullable=False),
        sa.Column("normalization_steps", JSONType, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("timestamp", UTCDateTime(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("collector", sa.String(length=64), nullable=False),
        sa.Column(
            "provenance_kind",
            sa.Enum(
                "OBSERVED",
                "DERIVED",
                "INFERRED",
                "CORRELATED",
                name="provenancekind",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("derived_from", JSONType, nullable=False),
        sa.Column("relation_hint", NullableJSONType, nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("metadata", JSONType, nullable=False),
        sa.Column("confidence_factors", NullableJSONType, nullable=True),
        sa.Column(
            "severity",
            sa.Enum(
                "info",
                "low",
                "medium",
                "high",
                "critical",
                name="severity",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_findings_confidence_range")
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.id"],
            name=op.f("fk_findings_evidence_id_evidence"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            name=op.f("fk_findings_investigation_id_investigations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source"], ["sources.name"], name=op.f("fk_findings_source_sources")
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["targets.id"],
            name=op.f("fk_findings_target_id_targets"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_findings")),
    )
    op.create_index(
        "ix_findings_investigation_type", "findings", ["investigation_id", "type"], unique=False
    )
    op.create_index("ix_findings_normalized_value", "findings", ["normalized_value"], unique=False)
    op.create_index("ix_findings_target_id", "findings", ["target_id"], unique=False)
    op.create_table(
        "relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "OWNS",
                "USES",
                "HAS_EMAIL",
                "HAS_PHONE",
                "ASSOCIATED_WITH",
                "RESOLVES_TO",
                "HAS_PTR",
                "HAS_SUBDOMAIN",
                "HAS_CERTIFICATE",
                "MAIL_HANDLED_BY",
                "NAME_SERVED_BY",
                "ANNOUNCED_BY",
                "REGISTERED_BY",
                "HOSTED_ON",
                "POSSIBLY_SAME_AS",
                name="relationtype",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "provenance_kind",
            sa.Enum(
                "OBSERVED",
                "DERIVED",
                "INFERRED",
                "CORRELATED",
                name="provenancekind",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("finding_ids", JSONType, nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_relationships_confidence_range")
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            name=op.f("fk_relationships_investigation_id_investigations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["entities.id"],
            name=op.f("fk_relationships_source_entity_id_entities"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["entities.id"],
            name=op.f("fk_relationships_target_entity_id_entities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_relationships")),
        sa.UniqueConstraint(
            "investigation_id",
            "source_entity_id",
            "target_entity_id",
            "type",
            name=op.f("uq_relationships_edge"),
        ),
    )
    op.create_index(
        op.f("ix_relationships_investigation_id"),
        "relationships",
        ["investigation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_relationships_source_entity_id"),
        "relationships",
        ["source_entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_relationships_target_entity_id"),
        "relationships",
        ["target_entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_relationships_target_entity_id"), table_name="relationships")
    op.drop_index(op.f("ix_relationships_source_entity_id"), table_name="relationships")
    op.drop_index(op.f("ix_relationships_investigation_id"), table_name="relationships")
    op.drop_table("relationships")
    op.drop_index("ix_findings_target_id", table_name="findings")
    op.drop_index("ix_findings_normalized_value", table_name="findings")
    op.drop_index("ix_findings_investigation_type", table_name="findings")
    op.drop_table("findings")
    op.drop_index(op.f("ix_collector_runs_investigation_id"), table_name="collector_runs")
    op.drop_table("collector_runs")
    op.drop_index(op.f("ix_targets_investigation_id"), table_name="targets")
    op.drop_table("targets")
    op.drop_index(op.f("ix_scores_investigation_id"), table_name="scores")
    op.drop_table("scores")
    op.drop_index(op.f("ix_reports_investigation_id"), table_name="reports")
    op.drop_table("reports")
    op.drop_index(op.f("ix_evidence_investigation_id"), table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_entities_investigation_type", table_name="entities")
    op.drop_table("entities")
    op.drop_index(op.f("ix_audit_log_investigation_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_created_at"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("sources")
    op.drop_index("ix_investigations_status", table_name="investigations")
    op.drop_table("investigations")
    op.drop_index("ix_graph_outbox_pending", table_name="graph_outbox")
    op.drop_index(op.f("ix_graph_outbox_investigation_id"), table_name="graph_outbox")
    op.drop_table("graph_outbox")
