"""processing jobs and document pages schema

Revision ID: 0004_processing_jobs_and_document_pages
Revises: 0003_document_management_storage
Create Date: 2026-10-24 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_processing_ocr"
down_revision: Union[str, None] = "0003_document_management_storage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create processing_jobs table
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("stage", sa.String(length=50), nullable=False, server_default="QUEUED"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_index(op.f("ix_processing_jobs_document_id"), "processing_jobs", ["document_id"], unique=False)
    op.create_index(op.f("ix_processing_jobs_organization_id"), "processing_jobs", ["organization_id"], unique=False)
    op.create_index(op.f("ix_processing_jobs_status"), "processing_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_processing_jobs_celery_task_id"), "processing_jobs", ["celery_task_id"], unique=False)
    op.create_index(op.f("ix_processing_jobs_idempotency_key"), "processing_jobs", ["idempotency_key"], unique=False)

    # 2. Create document_pages table
    op.create_table(
        "document_pages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False, server_default=""),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_scanned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_images", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ocr_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_index(op.f("ix_document_pages_document_id"), "document_pages", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_pages_page_number"), "document_pages", ["page_number"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_pages_page_number"), table_name="document_pages")
    op.drop_index(op.f("ix_document_pages_document_id"), table_name="document_pages")
    op.drop_table("document_pages")

    op.drop_index(op.f("ix_processing_jobs_idempotency_key"), table_name="processing_jobs")
    op.drop_index(op.f("ix_processing_jobs_celery_task_id"), table_name="processing_jobs")
    op.drop_index(op.f("ix_processing_jobs_status"), table_name="processing_jobs")
    op.drop_index(op.f("ix_processing_jobs_organization_id"), table_name="processing_jobs")
    op.drop_index(op.f("ix_processing_jobs_document_id"), table_name="processing_jobs")
    op.drop_table("processing_jobs")
