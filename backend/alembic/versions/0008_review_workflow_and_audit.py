"""review workflow and audit schema

Revision ID: 0008_review_workflow_and_audit
Revises: 0007_document_chunks_and_chat
Create Date: 2026-11-02 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008_review_workflow_and_audit"
down_revision: Union[str, None] = "0007_document_chunks_and_chat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update audit_logs with organization_id and user_email
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("user_email", sa.String(length=255), nullable=True))
        batch_op.create_index("ix_audit_logs_organization_id", ["organization_id"], unique=False)
        batch_op.create_index("ix_audit_logs_user_email", ["user_email"], unique=False)

    # 2. Create review_tasks table
    op.create_table(
        "review_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("extraction_id", sa.String(length=36), nullable=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="MEDIUM"),
        sa.Column("assigned_to_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reasons", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False, server_default="[]"),
        sa.Column("validation_error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_id"], ["document_extractions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_tasks_document_id", "review_tasks", ["document_id"], unique=False)
    op.create_index("ix_review_tasks_extraction_id", "review_tasks", ["extraction_id"], unique=False)
    op.create_index("ix_review_tasks_organization_id", "review_tasks", ["organization_id"], unique=False)
    op.create_index("ix_review_tasks_status", "review_tasks", ["status"], unique=False)
    op.create_index("ix_review_tasks_priority", "review_tasks", ["priority"], unique=False)
    op.create_index("ix_review_tasks_assigned_to_id", "review_tasks", ["assigned_to_id"], unique=False)

    # 3. Create review_histories table
    op.create_table(
        "review_histories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_task_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("user_role", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=True),
        sa.Column("field_changes", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["review_task_id"], ["review_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_histories_review_task_id", "review_histories", ["review_task_id"], unique=False)
    op.create_index("ix_review_histories_document_id", "review_histories", ["document_id"], unique=False)
    op.create_index("ix_review_histories_organization_id", "review_histories", ["organization_id"], unique=False)
    op.create_index("ix_review_histories_action", "review_histories", ["action"], unique=False)


def downgrade() -> None:
    op.drop_table("review_histories")
    op.drop_table("review_tasks")
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_index("ix_audit_logs_user_email")
        batch_op.drop_index("ix_audit_logs_organization_id")
        batch_op.drop_column("user_email")
        batch_op.drop_column("organization_id")
