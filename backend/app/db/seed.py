import uuid
from sqlalchemy import select
from app.core.logging import logger
from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.organization import Organization
from app.models.user import User


async def seed_demo_accounts() -> None:
    """
    Ensures default enterprise organization and demo accounts
    (Admin, Analyst, Reviewer) exist with Password123!.
    """
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # 1. Ensure default organization exists
            org_slug = "acme-capital"
            query_org = select(Organization).where(Organization.slug == org_slug)
            res_org = await db.execute(query_org)
            org = res_org.scalar_one_or_none()

            if not org:
                org = Organization(
                    id=str(uuid.uuid4()),
                    name="Acme Capital LP",
                    slug=org_slug,
                    is_active=True,
                )
                db.add(org)
                await db.flush()
                logger.info(f"Seeded default organization: {org.name} ({org.id})")

            # 2. Demo accounts to provision
            demo_users = [
                {
                    "email": "admin@docufin.ai",
                    "full_name": "Sarah Connor (Admin)",
                    "role": OrganizationRole.ADMIN.value,
                    "is_superuser": True,
                },
                {
                    "email": "analyst@docufin.ai",
                    "full_name": "Alex Vance (Lead Analyst)",
                    "role": OrganizationRole.ANALYST.value,
                    "is_superuser": False,
                },
                {
                    "email": "reviewer@docufin.ai",
                    "full_name": "Elena Rostova (Compliance Reviewer)",
                    "role": OrganizationRole.REVIEWER.value,
                    "is_superuser": False,
                },
            ]

            default_hashed_pwd = hash_password("Password123!")

            for item in demo_users:
                user_query = select(User).where(User.email == item["email"])
                user_res = await db.execute(user_query)
                user = user_res.scalar_one_or_none()

                if not user:
                    user = User(
                        id=str(uuid.uuid4()),
                        email=item["email"],
                        full_name=item["full_name"],
                        hashed_password=default_hashed_pwd,
                        is_active=True,
                        is_superuser=item["is_superuser"],
                    )
                    db.add(user)
                    await db.flush()
                    logger.info(f"Seeded demo user: {user.email}")

                # Ensure membership in default organization
                mem_query = select(OrganizationMembership).where(
                    OrganizationMembership.user_id == user.id,
                    OrganizationMembership.organization_id == org.id,
                )
                mem_res = await db.execute(mem_query)
                membership = mem_res.scalar_one_or_none()

                if not membership:
                    membership = OrganizationMembership(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        organization_id=org.id,
                        role=item["role"],
                        is_active=True,
                    )
                    db.add(membership)
                    logger.info(f"Assigned {user.email} to {org.name} as {item['role']}")

            await db.commit()
            logger.info("Demo accounts verification and seeding complete.")
        except Exception as exc:
            await db.rollback()
            logger.warning(f"Demo accounts seeding skipped or encountered issue: {exc}")
