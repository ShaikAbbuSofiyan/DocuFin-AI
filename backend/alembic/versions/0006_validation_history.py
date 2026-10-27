"""validation history schema

Revision ID: 0006_validation_history
Revises: 0005_document_extractions
Create Date: 2026-10-27 21:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_validation_history"
down_revision: Union[str, None] = "0005_document_extractions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extraction_id", sa.String(length=36), sa.ForeignKey("document_extractions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by", sa.String(length=50), nullable=False, server_default="EXTRACTION"),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("info_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_index(op.f("ix_validation_runs_document_id"), "validation_runs", ["document_id"], unique=False)
    op.create_index(op.f("ix_validation_runs_extraction_id"), "validation_runs", ["extraction_id"], unique=False)
    op.create_index(op.f("ix_validation_runs_organization_id"), "validation_runs", ["organization_id"], unique=False)
    op.create_index(op.f("ix_validation_runs_is_valid"), "validation_runs", ["is_valid"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_validation_runs_is_valid"), table_name="validation_runs")
    op.drop_index(op.f("ix_validation_runs_organization_id"), table_name="validation_runs")
    op.drop_index(op.f("ix_validation_runs_extraction_id"), table_name="validation_runs")
    op.drop_index(op.f("ix_validation_runs_document_id"), table_name="validation_runs")
    op.drop_table("validation_runs")
