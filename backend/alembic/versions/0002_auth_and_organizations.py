"""authentication, roles, and organization isolation schema

Revision ID: 0002_auth_and_organizations
Revises: 0001_initial_schema
Create Date: 2026-10-20 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_auth_and_organizations"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_name"), "organizations", ["name"], unique=False)
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)

    # 2. Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 3. Create organization_memberships table
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="Analyst"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_user_organization_membership"),
    )
    op.create_index(op.f("ix_organization_memberships_user_id"), "organization_memberships", ["user_id"], unique=False)
    op.create_index(op.f("ix_organization_memberships_organization_id"), "organization_memberships", ["organization_id"], unique=False)
    op.create_index(op.f("ix_organization_memberships_role"), "organization_memberships", ["role"], unique=False)

    # 4. Add organization_id column to documents table for tenant isolation
    op.add_column("documents", sa.Column("organization_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_documents_organization_id",
        "documents",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_documents_organization_id"), "documents", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_organization_id"), table_name="documents")
    op.drop_constraint("fk_documents_organization_id", "documents", type_="foreignkey")
    op.drop_column("documents", "organization_id")

    op.drop_index(op.f("ix_organization_memberships_role"), table_name="organization_memberships")
    op.drop_index(op.f("ix_organization_memberships_organization_id"), table_name="organization_memberships")
    op.drop_index(op.f("ix_organization_memberships_user_id"), table_name="organization_memberships")
    op.drop_table("organization_memberships")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_table("organizations")
