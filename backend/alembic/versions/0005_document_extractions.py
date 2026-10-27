"""document extractions schema

Revision ID: 0005_document_extractions
Revises: 0004_processing_ocr
Create Date: 2026-10-27 20:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_document_extractions"
down_revision: Union[str, None] = "0004_processing_ocr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_extractions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False, server_default="UNKNOWN"),
        sa.Column("classification_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("schema_version", sa.String(length=20), nullable=False, server_default="v1.0"),
        sa.Column("extracted_data", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("field_metadata", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("extraction_method", sa.String(length=50), nullable=False, server_default="LLM"),
        sa.Column("llm_provider", sa.String(length=50), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_reasons", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="EXTRACTED"),
        sa.Column("reviewed_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analyst_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_index(op.f("ix_document_extractions_document_id"), "document_extractions", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_extractions_organization_id"), "document_extractions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_document_extractions_document_type"), "document_extractions", ["document_type"], unique=False)
    op.create_index(op.f("ix_document_extractions_confidence_score"), "document_extractions", ["confidence_score"], unique=False)
    op.create_index(op.f("ix_document_extractions_needs_review"), "document_extractions", ["needs_review"], unique=False)
    op.create_index(op.f("ix_document_extractions_status"), "document_extractions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_extractions_status"), table_name="document_extractions")
    op.drop_index(op.f("ix_document_extractions_needs_review"), table_name="document_extractions")
    op.drop_index(op.f("ix_document_extractions_confidence_score"), table_name="document_extractions")
    op.drop_index(op.f("ix_document_extractions_document_type"), table_name="document_extractions")
    op.drop_index(op.f("ix_document_extractions_organization_id"), table_name="document_extractions")
    op.drop_index(op.f("ix_document_extractions_document_id"), table_name="document_extractions")
    op.drop_table("document_extractions")
