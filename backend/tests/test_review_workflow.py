import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.organization import Organization
from app.models.review_task import ReviewTask, ReviewTaskPriority, ReviewTaskStatus
from app.models.user import User
from app.services.state_machine import validate_document_transition, validate_review_task_transition
from app.core.exceptions import ValidationError


async def register_and_get_user(
    client: AsyncClient,
    email: str,
    org_name: str,
    role: str = OrganizationRole.REVIEWER.value,
) -> tuple[str, str, str]:
    """Helper: Registers a user, retrieves JWT token, user_id, and org_id."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassword123!",
            "full_name": f"User {email.split('@')[0]}",
            "organization_name": org_name,
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]

    me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200, me_resp.text
    org_id = me_resp.json()["active_organization_id"]
    return token, user_id, org_id


# ==============================================================================
# 1. State Machine Unit Tests: Valid & Invalid Document State Transitions
# ==============================================================================

def test_document_state_machine_valid_transitions():
    """Verifies that allowed document lifecycle transitions succeed."""
    # UPLOADED -> QUEUED -> PROCESSING -> REVIEW_REQUIRED -> APPROVED
    validate_document_transition(DocumentStatus.UPLOADED.value, DocumentStatus.QUEUED.value)
    validate_document_transition(DocumentStatus.QUEUED.value, DocumentStatus.PROCESSING.value)
    validate_document_transition(DocumentStatus.PROCESSING.value, DocumentStatus.REVIEW_REQUIRED.value)
    validate_document_transition(DocumentStatus.REVIEW_REQUIRED.value, DocumentStatus.APPROVED.value)
    validate_document_transition(DocumentStatus.REVIEW_REQUIRED.value, DocumentStatus.REJECTED.value)
    validate_document_transition(DocumentStatus.APPROVED.value, DocumentStatus.REVIEW_REQUIRED.value)
    validate_document_transition(DocumentStatus.REJECTED.value, DocumentStatus.REVIEW_REQUIRED.value)


def test_document_state_machine_invalid_transitions():
    """Verifies that illegal transitions raise ValidationError."""
    with pytest.raises(ValidationError, match="Invalid document state transition"):
        validate_document_transition(DocumentStatus.UPLOADED.value, DocumentStatus.APPROVED.value)

    with pytest.raises(ValidationError, match="Invalid document state transition"):
        validate_document_transition(DocumentStatus.PROCESSING.value, DocumentStatus.REJECTED.value)

    with pytest.raises(ValidationError, match="Invalid document state transition"):
        validate_document_transition(DocumentStatus.APPROVED.value, DocumentStatus.QUEUED.value)


def test_review_task_state_machine_transitions():
    """Verifies review task lifecycle transitions and rejection of illegal states."""
    validate_review_task_transition(ReviewTaskStatus.PENDING.value, ReviewTaskStatus.IN_REVIEW.value)
    validate_review_task_transition(ReviewTaskStatus.IN_REVIEW.value, ReviewTaskStatus.APPROVED.value)

    with pytest.raises(ValidationError, match="Invalid review task state transition"):
        validate_review_task_transition(ReviewTaskStatus.CANCELLED.value, ReviewTaskStatus.APPROVED.value)


# ==============================================================================
# 2. Integration Tests: Review Queue, Field Corrections, & Concurrency Locking
# ==============================================================================

@pytest.mark.asyncio
async def test_review_queue_and_assignment(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    1. Create reviewer user and document requiring review.
    2. Query review queue -> Verify task presence.
    3. Assign task to reviewer -> Status transitions to IN_REVIEW.
    """
    email = f"reviewer_{uuid.uuid4().hex[:6]}@example.com"
    token, user_id, org_id = await register_and_get_user(client, email, "Apex Review Capital")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # Create document and extraction needing review
    doc = Document(
        organization_id=org_id,
        title="Vendor_Invoice_9921.pdf",
        filename="Vendor_Invoice_9921.pdf",
        storage_key="test/doc9921.pdf",
        file_path="storage/test/doc9921.pdf",
        file_size_bytes=1024,
        status=DocumentStatus.REVIEW_REQUIRED.value,
        doc_type="INVOICE",
    )
    db_session.add(doc)
    await db_session.flush()

    ext = DocumentExtraction(
        document_id=doc.id,
        organization_id=org_id,
        document_type="INVOICE",
        extracted_data={"invoice_number": "INV-9921", "total_amount": 1500.0, "subtotal": 1200.0, "tax_amount": 200.0},
        field_metadata={
            "invoice_number": {"value": "INV-9921", "confidence": 0.95, "source_page": 1, "extraction_method": "LLM"},
            "total_amount": {"value": 1500.0, "confidence": 0.60, "source_page": 1, "extraction_method": "LLM"},
        },
        needs_review=True,
        review_reasons=["Subtotal (1200.0) + Tax (200.0) != Total (1500.0)"],
        confidence_score=0.77,
        status=ExtractionStatus.REVIEW_REQUIRED.value,
    )
    db_session.add(ext)
    await db_session.commit()

    # Create review task via API
    create_resp = await client.post(
        "/api/v1/reviews",
        json={"document_id": doc.id, "priority": "HIGH", "review_reasons": ["Tax mismatch"]},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    task_id = create_resp.json()["id"]

    # List queue
    queue_resp = await client.get("/api/v1/reviews/queue", headers=headers)
    assert queue_resp.status_code == 200, queue_resp.text
    items = queue_resp.json()["items"]
    assert any(it["id"] == task_id for it in items)

    # Assign task to reviewer
    assign_resp = await client.post(
        f"/api/v1/reviews/{task_id}/assign",
        json={"assigned_to_id": user_id},
        headers=headers,
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assert assign_resp.json()["status"] == ReviewTaskStatus.IN_REVIEW.value
    assert assign_resp.json()["assigned_to_id"] == user_id


@pytest.mark.asyncio
async def test_field_correction_history_and_optimistic_locking(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    1. Correct a field -> Before and after values recorded in ReviewHistory.
    2. Attempt update with stale version -> Fails with HTTP 409 Conflict.
    3. Update with correct version -> Succeeds and increments version.
    """
    email = f"lead_reviewer_{uuid.uuid4().hex[:6]}@example.com"
    token, user_id, org_id = await register_and_get_user(client, email, "Audit Partners LLP")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    doc = Document(
        organization_id=org_id,
        title="Q3_Statement.pdf",
        filename="Q3_Statement.pdf",
        storage_key="test/q3.pdf",
        file_path="storage/test/q3.pdf",
        file_size_bytes=1024,
        status=DocumentStatus.REVIEW_REQUIRED.value,
        doc_type="INVOICE",
    )
    db_session.add(doc)
    await db_session.flush()

    ext = DocumentExtraction(
        document_id=doc.id,
        organization_id=org_id,
        document_type="INVOICE",
        extracted_data={"invoice_number": "INV-101", "total_amount": 1000.0, "subtotal": 900.0, "tax_amount": 100.0},
        field_metadata={
            "total_amount": {"value": 1000.0, "confidence": 0.70, "extraction_method": "LLM"},
        },
        needs_review=True,
        status=ExtractionStatus.REVIEW_REQUIRED.value,
    )
    db_session.add(ext)
    await db_session.commit()

    task = ReviewTask(
        document_id=doc.id,
        extraction_id=ext.id,
        organization_id=org_id,
        status=ReviewTaskStatus.PENDING.value,
        priority=ReviewTaskPriority.MEDIUM.value,
        version=1,
    )
    db_session.add(task)
    await db_session.commit()

    # 1. Correct field with version=1
    corr_payload = {
        "field_updates": {"total_amount": 1250.0},
        "notes": "Corrected total per physical receipt signature",
        "expected_version": 1,
    }
    corr_resp = await client.post(f"/api/v1/reviews/{task.id}/correct", json=corr_payload, headers=headers)
    assert corr_resp.status_code == 200, corr_resp.text
    updated_data = corr_resp.json()
    assert updated_data["version"] == 2
    assert updated_data["extracted_data"]["total_amount"] == 1250.0

    # Verify review history tracked the before & after values
    hist_resp = await client.get(f"/api/v1/reviews/{task.id}/history", headers=headers)
    assert hist_resp.status_code == 200, hist_resp.text
    histories = hist_resp.json()
    assert len(histories) >= 1
    corr_history = next(h for h in histories if h["action"] == "FIELD_CORRECTION")
    assert corr_history["field_changes"]["total_amount"]["old_value"] == 1000.0
    assert corr_history["field_changes"]["total_amount"]["new_value"] == 1250.0

    # 2. Concurrent update attempt: another reviewer sends update with old version 1 -> HTTP 409
    stale_payload = {
        "field_updates": {"total_amount": 1300.0},
        "notes": "Concurrent update with stale version",
        "expected_version": 1,
    }
    conflict_resp = await client.post(f"/api/v1/reviews/{task.id}/correct", json=stale_payload, headers=headers)
    assert conflict_resp.status_code == 409, conflict_resp.text
    assert "Concurrent modification" in conflict_resp.json()["error"]["message"]

    # 3. Valid update with expected_version=2 -> Succeeds and reaches version 3
    valid_payload = {
        "field_updates": {"tax_amount": 150.0},
        "notes": "Tax adjusted",
        "expected_version": 2,
    }
    valid_resp = await client.post(f"/api/v1/reviews/{task.id}/correct", json=valid_payload, headers=headers)
    assert valid_resp.status_code == 200, valid_resp.text
    assert valid_resp.json()["version"] == 3


# ==============================================================================
# 3. Dual-Control / Segregation of Duties Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_dual_control_self_approval_prevention(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Dual control policy:
    1. Uploader attempting to approve their own document is blocked with HTTP 403.
    2. A distinct second reviewer can successfully approve the document.
    """
    # Create Uploader
    uploader_email = f"uploader_{uuid.uuid4().hex[:6]}@example.com"
    uploader_token, uploader_id, org_id = await register_and_get_user(client, uploader_email, "Dual Control Fund")
    uploader_headers = {"Authorization": f"Bearer {uploader_token}", "X-Organization-Id": org_id}

    # Create Second Reviewer in same organization
    reviewer2 = User(
        email=f"reviewer2_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="hashed_pw_test",
        full_name="Second Reviewer",
        is_active=True,
    )
    db_session.add(reviewer2)
    await db_session.flush()

    mem2 = OrganizationMembership(
        user_id=reviewer2.id,
        organization_id=org_id,
        role=OrganizationRole.REVIEWER.value,
        is_active=True,
    )
    db_session.add(mem2)

    # Document uploaded by uploader_id
    doc = Document(
        organization_id=org_id,
        uploader_id=uploader_id,
        title="Dual_Control_Invoice.pdf",
        filename="Dual_Control_Invoice.pdf",
        storage_key="test/dc.pdf",
        file_path="storage/test/dc.pdf",
        file_size_bytes=2048,
        status=DocumentStatus.REVIEW_REQUIRED.value,
        doc_type="INVOICE",
    )
    db_session.add(doc)
    await db_session.flush()

    ext = DocumentExtraction(
        document_id=doc.id,
        organization_id=org_id,
        document_type="INVOICE",
        extracted_data={"total_amount": 5000.0},
        needs_review=True,
        status=ExtractionStatus.REVIEW_REQUIRED.value,
    )
    db_session.add(ext)
    await db_session.flush()

    task = ReviewTask(
        document_id=doc.id,
        extraction_id=ext.id,
        organization_id=org_id,
        status=ReviewTaskStatus.PENDING.value,
        priority=ReviewTaskPriority.HIGH.value,
        version=1,
    )
    db_session.add(task)
    await db_session.commit()

    # 1. Uploader attempts self-approval -> 403 Forbidden
    self_appr_resp = await client.post(
        f"/api/v1/reviews/{task.id}/approve",
        json={"notes": "I approve my own upload", "expected_version": 1},
        headers=uploader_headers,
    )
    assert self_appr_resp.status_code == 403, self_appr_resp.text
    assert "Self-approval policy violation" in self_appr_resp.json()["error"]["message"]

    # 2. Log in as Reviewer 2
    # In test, generate token for reviewer2 or promote membership
    from app.core.security import create_access_token
    token2 = create_access_token(subject=reviewer2.id)
    reviewer2_headers = {"Authorization": f"Bearer {token2}", "X-Organization-Id": org_id}

    appr2_resp = await client.post(
        f"/api/v1/reviews/{task.id}/approve",
        json={"notes": "Verified against purchase order. Signed off.", "expected_version": 1},
        headers=reviewer2_headers,
    )
    assert appr2_resp.status_code == 200, appr2_resp.text
    assert appr2_resp.json()["status"] == ReviewTaskStatus.APPROVED.value

    # Verify document status updated to APPROVED
    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.APPROVED.value


# ==============================================================================
# 4. Rejection Workflow & Reason Enforcement Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_rejection_workflow_and_mandatory_reason(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    1. Attempt rejection without reason -> Fails with validation error.
    2. Rejection with valid reason -> Transitions task and document to REJECTED.
    """
    email = f"reject_reviewer_{uuid.uuid4().hex[:6]}@example.com"
    token, user_id, org_id = await register_and_get_user(client, email, "Risk Audit Corp")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    doc = Document(
        organization_id=org_id,
        title="Fraudulent_Receipt.pdf",
        filename="Fraudulent_Receipt.pdf",
        storage_key="test/fraud.pdf",
        file_path="storage/test/fraud.pdf",
        file_size_bytes=512,
        status=DocumentStatus.REVIEW_REQUIRED.value,
        doc_type="EXPENSE_REPORT",
    )
    db_session.add(doc)
    await db_session.flush()

    task = ReviewTask(
        document_id=doc.id,
        organization_id=org_id,
        status=ReviewTaskStatus.PENDING.value,
        priority=ReviewTaskPriority.CRITICAL.value,
        version=1,
    )
    db_session.add(task)
    await db_session.commit()

    # 1. Reject without reason -> 422 Unprocessable Entity
    empty_resp = await client.post(
        f"/api/v1/reviews/{task.id}/reject",
        json={"rejection_reason": "", "expected_version": 1},
        headers=headers,
    )
    assert empty_resp.status_code in [400, 422], empty_resp.text

    # 2. Reject with reason -> 200 OK
    reject_reason = "Unverifiable merchant address and missing itemized tax breakdown."
    rej_resp = await client.post(
        f"/api/v1/reviews/{task.id}/reject",
        json={"rejection_reason": reject_reason, "expected_version": 1},
        headers=headers,
    )
    assert rej_resp.status_code == 200, rej_resp.text
    assert rej_resp.json()["status"] == ReviewTaskStatus.REJECTED.value
    assert rej_resp.json()["rejection_reason"] == reject_reason

    # Verify document is marked REJECTED
    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.REJECTED.value


# ==============================================================================
# 5. Multi-Tenant Isolation & Searchable Audit Log Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_review_and_audit_organization_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    1. User A in Org A cannot view or modify review task belonging to Org B.
    2. Audit logs are strictly isolated: Org A cannot query audit logs of Org B.
    3. Audit logs are searchable and paginated.
    """
    # Org A
    user_a = f"usera_rev_{uuid.uuid4().hex[:6]}@example.com"
    token_a, _, org_a_id = await register_and_get_user(client, user_a, "Organization Alpha")
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Organization-Id": org_a_id}

    # Org B
    user_b = f"userb_rev_{uuid.uuid4().hex[:6]}@example.com"
    token_b, _, org_b_id = await register_and_get_user(client, user_b, "Organization Beta")
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Organization-Id": org_b_id}

    # Create task in Org B
    doc_b = Document(
        organization_id=org_b_id,
        title="Beta_Confidential.pdf",
        filename="Beta_Confidential.pdf",
        storage_key="test/beta.pdf",
        file_path="storage/test/beta.pdf",
        file_size_bytes=1000,
        status=DocumentStatus.REVIEW_REQUIRED.value,
        doc_type="INVOICE",
    )
    db_session.add(doc_b)
    await db_session.flush()

    task_b = ReviewTask(
        document_id=doc_b.id,
        organization_id=org_b_id,
        status=ReviewTaskStatus.PENDING.value,
        priority=ReviewTaskPriority.HIGH.value,
        version=1,
    )
    db_session.add(task_b)
    await db_session.commit()

    # User A in Org A tries to access Org B's review task -> 404 Not Found (isolated)
    cross_resp = await client.get(f"/api/v1/reviews/{task_b.id}", headers=headers_a)
    assert cross_resp.status_code == 404, cross_resp.text

    # User A tries to approve Org B's task -> 404 Not Found
    cross_appr = await client.post(
        f"/api/v1/reviews/{task_b.id}/approve",
        json={"notes": "Hacked", "expected_version": 1},
        headers=headers_a,
    )
    assert cross_appr.status_code == 404, cross_appr.text

    # Searchable Audit Log Test for Org B
    # Trigger an audit event in Org B by assigning task
    await client.post(
        f"/api/v1/reviews/{task_b.id}/assign",
        json={"assigned_to_id": None},
        headers=headers_b,
    )

    audit_resp = await client.get(
        "/api/v1/audit/logs?search=REVIEW_TASK_ASSIGNED",
        headers=headers_b,
    )
    assert audit_resp.status_code == 200, audit_resp.text
    b_logs = audit_resp.json()
    assert b_logs["total"] >= 1
    assert all(it["organization_id"] == org_b_id for it in b_logs["items"])

    # Org A queries audit logs -> Org B's events must NOT be present
    audit_a_resp = await client.get("/api/v1/audit/logs", headers=headers_a)
    assert audit_a_resp.status_code == 200, audit_a_resp.text
    a_logs = audit_a_resp.json()
    assert all(it["organization_id"] == org_a_id for it in a_logs["items"])
