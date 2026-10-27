import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.document import Document, DocumentStatus
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.organization import Organization
from app.models.validation_history import ValidationRun, ValidationSeverity
from app.schemas.extraction import DocumentType
from app.schemas.validation import ValidationSummary
from app.services.validation_engine import (
    FinancialValidationEngine,
    to_decimal,
)
from tests.test_document_management import register_and_get_token


# ==============================================================================
# Unit Tests: Decimal Arithmetic & Edge Cases
# ==============================================================================

def test_decimal_conversion_and_precision():
    """Verifies that floating point inaccuracies (e.g. 0.1 + 0.2) do not occur."""
    d1 = to_decimal("0.1")
    d2 = to_decimal("0.2")
    assert d1 + d2 == Decimal("0.3")

    # Formatted strings with commas
    assert to_decimal("1,234,567.89") == Decimal("1234567.89")
    assert to_decimal(None) is None
    assert to_decimal("invalid") is None


def test_currency_precision_rules():
    """Verifies standard vs non-standard currency decimal precision rules."""
    engine = FinancialValidationEngine()

    # Standard USD: 2 decimals -> Valid
    usd_data = {"currency": "USD", "total": 125.50}
    res = engine._validate_currency_precision(usd_data)
    assert any(r.is_passed for r in res)

    # USD with 4 decimals -> Warning
    usd_excess = {"currency": "USD", "total": 125.5555}
    res_excess = engine._validate_currency_precision(usd_excess)
    warning = next(r for r in res_excess if r.rule_id == "RULE_CURRENCY_PRECISION")
    assert not warning.is_passed
    assert warning.severity == ValidationSeverity.WARNING
    assert "total" in warning.affected_fields

    # JPY with 0 decimals -> Valid
    jpy_data = {"currency": "JPY", "total": 15000}
    res_jpy = engine._validate_currency_precision(jpy_data)
    assert all(r.is_passed for r in res_jpy)

    # JPY with decimals -> Warning
    jpy_invalid = {"currency": "JPY", "total": 15000.50}
    res_jpy_inv = engine._validate_currency_precision(jpy_invalid)
    assert any(not r.is_passed for r in res_jpy_inv)


# ==============================================================================
# Unit Tests: Mandatory Fields & Date Relationships
# ==============================================================================

def test_mandatory_fields_validation():
    engine = FinancialValidationEngine()

    # 1. Invoice missing invoice_number and vendor
    incomplete_invoice = {"total": 500.0}
    res_inv = engine._validate_mandatory_fields(DocumentType.INVOICE.value, incomplete_invoice)
    err = next(r for r in res_inv if r.rule_id == "RULE_INV_MANDATORY_FIELDS")
    assert not err.is_passed
    assert err.severity == ValidationSeverity.ERROR
    assert "invoice_number" in err.affected_fields
    assert "vendor" in err.affected_fields

    # 2. Complete invoice
    complete_invoice = {
        "invoice_number": "INV-101",
        "vendor": "Acme Inc.",
        "invoice_date": "2026-10-01",
        "total": 500.0,
    }
    res_comp = engine._validate_mandatory_fields(DocumentType.INVOICE.value, complete_invoice)
    assert all(r.is_passed for r in res_comp)

    # 3. Bank statement missing closing balance
    incomplete_bank = {"opening_balance": 1000.0}
    res_bank = engine._validate_mandatory_fields(DocumentType.BANK_STATEMENT.value, incomplete_bank)
    err_bank = next(r for r in res_bank if r.rule_id == "RULE_BANK_MANDATORY_FIELDS")
    assert not err_bank.is_passed
    assert "closing_balance" in err_bank.affected_fields


def test_date_sequence_and_format_rules():
    engine = FinancialValidationEngine()

    # 1. Due date before invoice date -> ERROR
    inv_inverted_dates = {
        "invoice_date": "2026-10-25",
        "due_date": "2026-10-10",
    }
    res_dates = engine._validate_dates(DocumentType.INVOICE.value, inv_inverted_dates)
    err = next(r for r in res_dates if r.rule_id == "RULE_DATE_SEQUENCE")
    assert not err.is_passed
    assert err.severity == ValidationSeverity.ERROR

    # 2. Valid sequence -> PASS
    inv_valid_dates = {
        "invoice_date": "2026-10-10",
        "due_date": "2026-10-25",
    }
    res_valid = engine._validate_dates(DocumentType.INVOICE.value, inv_valid_dates)
    assert any(r.rule_id == "RULE_DATE_SEQUENCE" and r.is_passed for r in res_valid)

    # 3. Bank statement inverted period -> ERROR
    bank_inverted_period = {
        "statement_period": {
            "start_date": "2026-10-31",
            "end_date": "2026-10-01",
        }
    }
    res_period = engine._validate_dates(DocumentType.BANK_STATEMENT.value, bank_inverted_period)
    err_period = next(r for r in res_period if r.rule_id == "RULE_STATEMENT_PERIOD")
    assert not err_period.is_passed
    assert err_period.severity == ValidationSeverity.ERROR


# ==============================================================================
# Unit Tests: Invoice Reconciliation & Tolerances
# ==============================================================================

def test_invoice_subtotal_tax_total_reconciliation():
    engine = FinancialValidationEngine(rounding_tolerance=0.05)

    # Exact match: 1000 + 100 == 1100 -> PASS
    clean_inv = {"subtotal": 1000.00, "tax": 100.00, "total": 1100.00}
    res_clean = engine._validate_invoice_reconciliation(clean_inv)
    assert any(r.rule_id == "RULE_INV_TOTAL_RECONCILIATION" and r.is_passed for r in res_clean)

    # Within tolerance: 1000 + 100 == 1100.03 (diff = 0.03 <= 0.05) -> PASS
    tol_inv = {"subtotal": 1000.00, "tax": 100.00, "total": 1100.03}
    res_tol = engine._validate_invoice_reconciliation(tol_inv)
    assert any(r.rule_id == "RULE_INV_TOTAL_RECONCILIATION" and r.is_passed for r in res_tol)

    # Discrepancy beyond tolerance: 1000 + 100 != 1150.00 -> ERROR
    mismatch_inv = {"subtotal": 1000.00, "tax": 100.00, "total": 1150.00}
    res_mismatch = engine._validate_invoice_reconciliation(mismatch_inv)
    err = next(r for r in res_mismatch if r.rule_id == "RULE_INV_TOTAL_RECONCILIATION")
    assert not err.is_passed
    assert err.severity == ValidationSeverity.ERROR
    assert "subtotal" in err.affected_fields
    assert "total" in err.affected_fields


def test_invoice_negative_values():
    engine = FinancialValidationEngine()
    data = {"total": -50.00, "subtotal": -50.00}
    res = engine._validate_invoice_negative_values(data)
    assert len(res) == 1
    assert res[0].severity == ValidationSeverity.WARNING
    assert "credit note" in res[0].explanation.lower()


# ==============================================================================
# Unit Tests: Bank Statement Transactions & Ledger Reconciliations
# ==============================================================================

def test_bank_statement_debit_credit_representation():
    engine = FinancialValidationEngine()

    # 1. Invalid: both debit and credit non-zero on the same row -> ERROR
    both_populated = {
        "transactions": [
            {"description": "Transfer", "debit": 100.0, "credit": 50.0}
        ]
    }
    res_both = engine._validate_transaction_debit_credit(both_populated)
    err = next(r for r in res_both if r.rule_id == "RULE_TXN_DEBIT_CREDIT_MUTUAL")
    assert not err.is_passed
    assert err.severity == ValidationSeverity.ERROR

    # 2. Invalid: negative debit or credit -> ERROR
    negative_val = {
        "transactions": [
            {"description": "Fee", "debit": -25.0, "credit": 0.0}
        ]
    }
    res_neg = engine._validate_transaction_debit_credit(negative_val)
    err_neg = next(r for r in res_neg if r.rule_id == "RULE_TXN_NON_NEGATIVE")
    assert not err_neg.is_passed
    assert err_neg.severity == ValidationSeverity.ERROR

    # 3. Valid transactions -> PASS
    valid_txns = {
        "transactions": [
            {"description": "Client Payment", "debit": 0.0, "credit": 5000.0},
            {"description": "SaaS Subscription", "debit": 200.0, "credit": 0.0},
        ]
    }
    res_valid = engine._validate_transaction_debit_credit(valid_txns)
    assert all(r.is_passed for r in res_valid)


def test_bank_statement_ledger_reconciliation():
    engine = FinancialValidationEngine(rounding_tolerance=0.05)

    # Opening 10,000 + Credits 5,000 - Debits 2,000 == Closing 13,000 -> PASS
    balanced_stmt = {
        "opening_balance": 10000.00,
        "closing_balance": 13000.00,
        "transactions": [
            {"credit": 5000.00, "debit": 0.0, "running_balance": 15000.00},
            {"credit": 0.0, "debit": 2000.00, "running_balance": 13000.00},
        ],
    }
    res_bal = engine._validate_bank_balances(balanced_stmt)
    assert any(r.rule_id == "RULE_BANK_LEDGER_RECONCILIATION" and r.is_passed for r in res_bal)
    assert any(r.rule_id == "RULE_BANK_RUNNING_BALANCES" and r.is_passed for r in res_bal)

    # Ledger mismatch: Opening 10,000 + Credits 5,000 - Debits 2,000 != Closing 15,000 -> ERROR
    unbalanced_stmt = {
        "opening_balance": 10000.00,
        "closing_balance": 15000.00,
        "transactions": [
            {"credit": 5000.00, "debit": 0.0, "running_balance": 15000.00},
            {"credit": 0.0, "debit": 2000.00, "running_balance": 13000.00},
        ],
    }
    res_unbal = engine._validate_bank_balances(unbalanced_stmt)
    err = next(r for r in res_unbal if r.rule_id == "RULE_BANK_LEDGER_RECONCILIATION")
    assert not err.is_passed
    assert err.severity == ValidationSeverity.ERROR
    assert "Discrepancy" in err.explanation


# ==============================================================================
# Integration Tests: Duplicate Invoice Detection & Workflow
# ==============================================================================

@pytest.mark.asyncio
async def test_duplicate_invoice_detection_and_resolution(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Tests:
    1. First invoice succeeds without duplicates.
    2. Second document with identical vendor and invoice_number in same org is flagged as duplicate.
    3. Re-validating after editing invoice number clears the error.
    4. Validation history logs are recorded.
    """
    # 1. Setup user and organization
    user_email = f"audit_analyst_{uuid.uuid4().hex[:6]}@example.com"
    token, org_id = await register_and_get_token(client, user_email, "Audit Corp Inc.")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Document 1 (Existing Invoice)
    doc1 = Document(
        organization_id=org_id,
        title="invoice_acme_001.pdf",
        filename="invoice_acme_001.pdf",
        storage_key="test/doc1.pdf",
        file_path="storage/test/doc1.pdf",
        file_size_bytes=1024,
        checksum_sha256="abc1",
        mime_type="application/pdf",
        status=DocumentStatus.APPROVED.value,
        doc_type=DocumentType.INVOICE.value,
    )
    db_session.add(doc1)
    await db_session.flush()

    ext1 = DocumentExtraction(
        document_id=doc1.id,
        organization_id=org_id,
        document_type=DocumentType.INVOICE.value,
        extracted_data={
            "invoice_number": "INV-2026-DUPLICATE-TEST",
            "vendor": "Acme Global Solutions",
            "invoice_date": "2026-10-10",
            "total": 1200.00,
        },
        field_metadata={},
        is_valid=True,
        status=ExtractionStatus.APPROVED.value,
    )
    db_session.add(ext1)
    await db_session.commit()

    # 3. Create Document 2 with the SAME vendor and invoice_number
    doc2 = Document(
        organization_id=org_id,
        title="invoice_acme_duplicate.pdf",
        filename="invoice_acme_duplicate.pdf",
        storage_key="test/doc2.pdf",
        file_path="storage/test/doc2.pdf",
        file_size_bytes=1024,
        checksum_sha256="abc2",
        mime_type="application/pdf",
        status=DocumentStatus.REVIEW_REQUIRED.value,
        doc_type=DocumentType.INVOICE.value,
    )
    db_session.add(doc2)
    await db_session.flush()

    ext2 = DocumentExtraction(
        document_id=doc2.id,
        organization_id=org_id,
        document_type=DocumentType.INVOICE.value,
        extracted_data={
            "invoice_number": "INV-2026-DUPLICATE-TEST",  # Duplicate!
            "vendor": "Acme Global Solutions",
            "invoice_date": "2026-10-15",
            "subtotal": 1000.00,
            "tax": 100.00,
            "total": 1100.00,
        },
        field_metadata={},
        is_valid=True,
        status=ExtractionStatus.EXTRACTED.value,
    )
    db_session.add(ext2)
    await db_session.commit()

    # 4. Trigger on-demand validation via API
    val_resp = await client.post(f"/api/v1/documents/{doc2.id}/validate", headers=headers)
    assert val_resp.status_code == 200
    val_data = val_resp.json()

    # Should fail due to duplicate detection rule
    assert not val_data["is_valid"]
    assert val_data["error_count"] >= 1
    dup_rule = next(r for r in val_data["results"] if r["rule_id"] == "RULE_DUP_INVOICE_IDENTIFIER")
    assert not dup_rule["is_passed"]
    assert dup_rule["severity"] == "ERROR"
    assert "Duplicate invoice identifier detected" in dup_rule["explanation"]

    # 5. Check validation-latest endpoint
    latest_resp = await client.get(f"/api/v1/documents/{doc2.id}/validation-latest", headers=headers)
    assert latest_resp.status_code == 200
    latest_data = latest_resp.json()
    assert latest_data["document_id"] == doc2.id
    assert not latest_data["is_valid"]

    # 6. Check validation-history endpoint
    hist_resp = await client.get(f"/api/v1/documents/{doc2.id}/validation-history", headers=headers)
    assert hist_resp.status_code == 200
    history_entries = hist_resp.json()
    assert len(history_entries) >= 1
    assert history_entries[0]["triggered_by"] == "API_REVALIDATE"

    # 7. Authorized Correction: Analyst updates invoice_number to unique identifier
    patch_resp = await client.patch(
        f"/api/v1/documents/{doc2.id}/extraction",
        json={
            "extracted_data": {
                "invoice_number": "INV-2026-UNIQUE-RESOLVED",
                "vendor": "Acme Global Solutions",
                "invoice_date": "2026-10-15",
                "subtotal": 1000.00,
                "tax": 100.00,
                "total": 1100.00,
            },
            "analyst_notes": "Corrected typo in invoice identifier from OCR misread.",
        },
        headers=headers,
    )
    assert patch_resp.status_code == 200
    patch_data = patch_resp.json()
    # Now it should be valid!
    assert patch_data["is_valid"] is True

    # 8. Check that validation history recorded the MANUAL_CORRECTION run
    hist_after = await client.get(f"/api/v1/documents/{doc2.id}/validation-history", headers=headers)
    assert hist_after.status_code == 200
    new_history = hist_after.json()
    assert len(new_history) >= 2
    assert new_history[0]["triggered_by"] == "MANUAL_CORRECTION"
    assert new_history[0]["is_valid"] is True
