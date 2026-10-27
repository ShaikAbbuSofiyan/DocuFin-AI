import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.test_document_management import register_and_get_token

from app.ai.llm_provider import MockLLMProvider
from app.models.document import Document, DocumentStatus
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.document_page import DocumentPage
from app.models.organization import Organization
from app.models.user import User
from app.schemas.extraction import (
    BankStatementData,
    ClassificationResult,
    DocumentType,
    ExpenseReportData,
    ExtractionMethod,
    InvoiceData,
    normalize_currency,
    normalize_date,
    normalize_numeric,
)
from app.services.classification_service import DocumentClassificationService
from app.services.deterministic_extractor import DeterministicExtractor
from app.services.extraction_service import FinancialExtractionService

# ==============================================================================
# Synthetic Documents with Manually Verified Ground Truth
# ==============================================================================

SYNTHETIC_INVOICE_TEXT = """
ACME CLOUD TECHNOLOGIES INC.
100 Innovation Parkway, Suite 400
San Francisco, CA 94105

TAX INVOICE
Invoice Number: INV-2026-8891
Invoice Date: 2026-10-15
Due Date: 2026-11-14
Currency: USD

Bill To:
Starlight Global Capital Partners
Attn: Accounts Payable
500 Financial Center, Floor 32
New York, NY 10005

Description                          Qty    Rate       Total
Enterprise Dedicated SaaS Node         1    $4,500.00  $4,500.00
High-Throughput API Gateway Pack       2      $250.00    $500.00

Subtotal: $5,000.00
Tax (10%): $500.00
Total Amount: $5,500.00

Payment Terms: Net 30 days. Remit to Acme Cloud Technologies.
"""

SYNTHETIC_INVOICE_DISCREPANCY_TEXT = """
VERTEX LOGISTICS CORP
TAX INVOICE
Invoice Number: INV-9901
Date: 2026-10-20
Due Date: 2026-10-10
Currency: USD

Subtotal: $1,000.00
Tax: $100.00
Total: $1,450.00
"""

SYNTHETIC_INVOICE_MISSING_FIELDS_TEXT = """
INVOICE
Invoice #: INV-4040
From: Solo Freelance Dev
Total: $800.00
"""

SYNTHETIC_BANK_STATEMENT_TEXT = """
FIRST NATIONAL COMMERCIAL BANK
ACCOUNT STATEMENT

Account Summary
Account: Primary Commercial Checking (...9821)
Statement Period: 2026-09-01 to 2026-09-30

Opening Balance: $10,000.00
Closing Balance: $14,250.00

Transaction Detail:
09/05/2026 Payroll Direct Deposit 0.00 5000.00 15000.00
09/18/2026 Office Lease Wire Transfer 750.00 0.00 14250.00
"""

SYNTHETIC_EXPENSE_REPORT_TEXT = """
EXPENSE REPORT & CLAIM
Employee: Sarah Jenkins
Expense Date: 2026-10-22
Merchant: Grand Hyatt Hotel & Suites
Category: Travel & Lodging
Amount: $345.50
Currency: USD
Business Purpose: Q3 Financial Leadership Strategy Meeting
"""


# ==============================================================================
# Unit Tests: Normalization
# ==============================================================================

def test_normalization_utilities():
    # Dates
    assert normalize_date("2026-10-24") == "2026-10-24"
    assert normalize_date("10/24/2026") == "2026-10-24"
    assert normalize_date("October 24, 2026") == "2026-10-24"
    assert normalize_date("invalid-date") is None
    assert normalize_date(None) is None

    # Currencies
    assert normalize_currency("$500.00") == "USD"
    assert normalize_currency("€ 1,200") == "EUR"
    assert normalize_currency("£99.99") == "GBP"
    assert normalize_currency("INR 50,000") == "INR"
    assert normalize_currency("100.00") is None

    # Numerics
    assert normalize_numeric("$1,234.56") == 1234.56
    assert normalize_numeric("5,000.00") == 5000.0
    assert normalize_numeric("(500.00)") == -500.0
    assert normalize_numeric("-250.25") == -250.25
    assert normalize_numeric(None) is None


# ==============================================================================
# Unit Tests: Classification Service
# ==============================================================================

def test_document_classification_service():
    # 1. Invoice
    inv_res = DocumentClassificationService.classify(SYNTHETIC_INVOICE_TEXT)
    assert inv_res.document_type == DocumentType.INVOICE
    assert inv_res.confidence >= 0.75
    assert len(inv_res.signals) > 0

    # 2. Bank Statement
    bank_res = DocumentClassificationService.classify(SYNTHETIC_BANK_STATEMENT_TEXT)
    assert bank_res.document_type == DocumentType.BANK_STATEMENT
    assert bank_res.confidence >= 0.75

    # 3. Expense Report
    exp_res = DocumentClassificationService.classify(SYNTHETIC_EXPENSE_REPORT_TEXT)
    assert exp_res.document_type == DocumentType.EXPENSE_REPORT
    assert exp_res.confidence >= 0.70

    # 4. Unknown
    unknown_res = DocumentClassificationService.classify("Random text with no financial anchors here.")
    assert unknown_res.document_type == DocumentType.UNKNOWN
    assert unknown_res.confidence < 0.50


# ==============================================================================
# Field-Level Accuracy Verification on Synthetic Documents
# ==============================================================================

def test_invoice_field_level_accuracy():
    """Measures field-level extraction precision against synthetic ground truth."""
    data, meta = DeterministicExtractor.extract_invoice(SYNTHETIC_INVOICE_TEXT, [SYNTHETIC_INVOICE_TEXT])

    # Ground truth mapping
    ground_truth = {
        "invoice_number": "INV-2026-8891",
        "vendor": "ACME CLOUD TECHNOLOGIES INC.",
        "invoice_date": "2026-10-15",
        "due_date": "2026-11-14",
        "currency": "USD",
        "subtotal": 5000.00,
        "tax": 500.00,
        "total": 5500.00,
    }

    correct_fields = 0
    total_fields = len(ground_truth)

    for field, expected in ground_truth.items():
        actual = getattr(data, field)
        if actual == expected:
            correct_fields += 1

    accuracy = correct_fields / total_fields
    print(f"\n[BENCHMARK] Invoice Field-Level Accuracy: {accuracy * 100:.2f}% ({correct_fields}/{total_fields})")
    assert accuracy >= 0.875  # Minimum 7/8 exact field matches
    assert data.total == 5500.00
    assert data.invoice_number == "INV-2026-8891"
    assert len(data.line_items) == 2


def test_bank_statement_field_level_accuracy():
    """Measures bank statement field extraction accuracy against ground truth."""
    data, meta = DeterministicExtractor.extract_bank_statement(SYNTHETIC_BANK_STATEMENT_TEXT, [SYNTHETIC_BANK_STATEMENT_TEXT])

    assert data.opening_balance == 10000.00
    assert data.closing_balance == 14250.00
    assert len(data.transactions) == 2
    assert data.transactions[0].credit == 5000.00
    assert data.transactions[1].debit == 750.00
    assert len(data.transaction_dates) == 2
    assert len(data.running_balances) == 2


def test_expense_report_field_level_accuracy():
    """Measures expense report field extraction accuracy against ground truth."""
    data, meta = DeterministicExtractor.extract_expense_report(SYNTHETIC_EXPENSE_REPORT_TEXT, [SYNTHETIC_EXPENSE_REPORT_TEXT])

    assert data.amount == 345.50
    assert data.currency == "USD"
    assert data.expense_date == "2026-10-22"
    assert "Grand Hyatt" in (data.merchant or "")
    assert data.category == "Travel & Lodging"


def test_missing_values_never_fabricated():
    """Verifies that missing fields in document text are strictly returned as None."""
    data, meta = DeterministicExtractor.extract_invoice(SYNTHETIC_INVOICE_MISSING_FIELDS_TEXT)

    assert data.invoice_number == "INV-4040"
    assert data.total == 800.00
    # Must NOT fabricate dates or tax
    assert data.invoice_date is None
    assert data.due_date is None
    assert data.tax is None
    assert data.subtotal is None
    assert len(data.line_items) == 0


# ==============================================================================
# Robustness & Error Handling Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_malformed_llm_response_recovery(db_session: AsyncSession):
    """Verifies that malformed or broken JSON from LLM is safely handled via fallback."""
    org = Organization(id=str(uuid.uuid4()), name="Test Org 1", slug=f"test-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()

    # Create test document with OCR page
    doc = Document(
        title="Malformed LLM Test Document",
        filename="test_malformed.pdf",
        storage_key=f"{org.id}/malformed.pdf",
        file_path="storage/malformed.pdf",
        file_size_bytes=1024,
        organization_id=org.id,
        status=DocumentStatus.UPLOADED.value,
        doc_type="INVOICE",
    )
    db_session.add(doc)
    await db_session.flush()

    page = DocumentPage(
        document_id=doc.id,
        page_number=1,
        text_content=SYNTHETIC_INVOICE_TEXT,
        word_count=50,
        char_count=350,
    )
    db_session.add(page)
    await db_session.commit()

    # Provider that outputs malformed JSON
    mock_provider = MockLLMProvider(force_malformed=True)
    service = FinancialExtractionService(db_session, llm_provider=mock_provider)

    extraction = await service.extract_document(doc_id=doc.id, org_id=org.id)
    assert extraction is not None
    assert extraction.document_type == "INVOICE"
    # Fallback recovered the data
    assert extraction.extracted_data.get("invoice_number") == "INV-2026-8891"
    assert extraction.extracted_data.get("total") == 5500.00


@pytest.mark.asyncio
async def test_provider_timeout_graceful_recovery(db_session: AsyncSession):
    """Verifies that provider timeout triggers deterministic fallback and sets review required."""
    org = Organization(id=str(uuid.uuid4()), name="Test Org 2", slug=f"test-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()

    doc = Document(
        title="Timeout Test Document",
        filename="test_timeout.pdf",
        storage_key=f"{org.id}/timeout.pdf",
        file_path="storage/timeout.pdf",
        file_size_bytes=1024,
        organization_id=org.id,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.flush()

    page = DocumentPage(
        document_id=doc.id,
        page_number=1,
        text_content=SYNTHETIC_INVOICE_TEXT,
        word_count=50,
        char_count=350,
    )
    db_session.add(page)
    await db_session.commit()

    # Provider that simulates timeout
    mock_provider = MockLLMProvider(force_timeout=True)
    service = FinancialExtractionService(db_session, llm_provider=mock_provider)

    extraction = await service.extract_document(doc_id=doc.id, org_id=org.id)
    assert extraction is not None
    assert extraction.extraction_method == ExtractionMethod.DETERMINISTIC_FALLBACK.value
    assert extraction.extracted_data.get("total") == 5500.00


@pytest.mark.asyncio
async def test_review_routing_on_math_discrepancy(db_session: AsyncSession):
    """Verifies that mathematical discrepancies route document to review queue."""
    org = Organization(id=str(uuid.uuid4()), name="Test Org 3", slug=f"test-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()

    doc = Document(
        title="Math Discrepancy Doc",
        filename="test_math.pdf",
        storage_key=f"{org.id}/math.pdf",
        file_path="storage/math.pdf",
        file_size_bytes=1024,
        organization_id=org.id,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.flush()

    page = DocumentPage(
        document_id=doc.id,
        page_number=1,
        text_content=SYNTHETIC_INVOICE_DISCREPANCY_TEXT,
        word_count=40,
        char_count=200,
    )
    db_session.add(page)
    await db_session.commit()

    service = FinancialExtractionService(db_session)
    extraction = await service.extract_document(doc_id=doc.id, org_id=org.id)

    assert extraction.needs_review is True
    assert extraction.status == ExtractionStatus.REVIEW_REQUIRED.value
    assert any("Mathematical discrepancy" in r for r in extraction.review_reasons)
    assert any("Temporal anomaly" in r for r in extraction.review_reasons)


# ==============================================================================
# End-to-End API Route Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_extraction_api_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Tests the full API flow: Extract -> Inspect -> Patch Analyst Review -> Review Queue."""
    token, org_id = await register_and_get_token(client, "analyst@fintech.com", "Extraction FinTech")
    auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 1. Create document with page in database
    doc = Document(
        title="API Extraction Verification Filing",
        filename="filing_api.pdf",
        storage_key=f"{org_id}/filing_api.pdf",
        file_path="storage/filing_api.pdf",
        file_size_bytes=2048,
        organization_id=org_id,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.flush()

    page = DocumentPage(
        document_id=doc.id,
        page_number=1,
        text_content=SYNTHETIC_INVOICE_TEXT,
        word_count=50,
        char_count=350,
    )
    db_session.add(page)
    await db_session.commit()

    # 2. Trigger Extraction via POST /api/v1/documents/{doc_id}/extract
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/extract",
        headers=auth_headers,
        json={"force_reextract": True},
    )
    assert resp.status_code == 200
    ext_data = resp.json()
    assert ext_data["document_id"] == doc.id
    assert ext_data["document_type"] == "INVOICE"
    assert ext_data["extracted_data"]["invoice_number"] == "INV-2026-8891"
    assert ext_data["extracted_data"]["total"] == 5500.00
    assert "field_metadata" in ext_data

    # 3. Inspect Extraction via GET /api/v1/documents/{doc_id}/extraction
    get_resp = await client.get(
        f"/api/v1/documents/{doc.id}/extraction",
        headers=auth_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == ext_data["id"]

    # 4. Analyst Correction via PATCH /api/v1/documents/{doc_id}/extraction
    patch_resp = await client.patch(
        f"/api/v1/documents/{doc.id}/extraction",
        headers=auth_headers,
        json={
            "extracted_data": {"invoice_number": "INV-2026-8891-CORRECTED", "total": 5500.00},
            "status": "APPROVED",
            "analyst_notes": "Verified against purchase order PO-440.",
        },
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["extracted_data"]["invoice_number"] == "INV-2026-8891-CORRECTED"
    assert patched["status"] == "APPROVED"
    assert patched["field_metadata"]["invoice_number"]["extraction_method"] == "MANUAL"

    # 5. Review Queue via GET /api/v1/documents/review-queue
    rq_resp = await client.get(
        "/api/v1/documents/review-queue",
        headers=auth_headers,
    )
    assert rq_resp.status_code == 200
    assert isinstance(rq_resp.json(), list)
