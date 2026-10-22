"""document management and secure storage schema

Revision ID: 0003_document_management_storage
Revises: 0002_auth_and_organizations
Create Date: 2026-10-22 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_document_management_storage"
down_revision: Union[str, None] = "0002_auth_and_organizations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add storage and security columns to documents table
    op.add_column(
        "documents",
        sa.Column("storage_key", sa.String(length=512), nullable=False, server_default=""),
    )
    op.add_column(
        "documents",
        sa.Column("file_extension", sa.String(length=20), nullable=False, server_default=".pdf"),
    )
    op.add_column(
        "documents",
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "documents",
        sa.Column("uploader_id", sa.String(length=36), nullable=True),
    )

    # 2. Add foreign key to users for uploader
    op.create_foreign_key(
        "fk_documents_uploader_id",
        "documents",
        "users",
        ["uploader_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. Create indices for fast filtering and searching
    op.create_index(op.f("ix_documents_storage_key"), "documents", ["storage_key"], unique=False)
    op.create_index(op.f("ix_documents_checksum_sha256"), "documents", ["checksum_sha256"], unique=False)
    op.create_index(op.f("ix_documents_uploader_id"), "documents", ["uploader_id"], unique=False)
    op.create_index(op.f("ix_documents_doc_type"), "documents", ["doc_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_doc_type"), table_name="documents")
    op.drop_index(op.f("ix_documents_uploader_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_checksum_sha256"), table_name="documents")
    op.drop_index(op.f("ix_documents_storage_key"), table_name="documents")

    op.drop_constraint("fk_documents_uploader_id", "documents", type_="foreignkey")
    op.drop_column("documents", "uploader_id")
    op.drop_column("documents", "checksum_sha256")
    op.drop_column("documents", "file_extension")
    op.drop_column("documents", "storage_key")
