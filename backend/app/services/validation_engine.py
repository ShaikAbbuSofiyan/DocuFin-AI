import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.validation_history import ValidationRun, ValidationSeverity
from app.schemas.extraction import DocumentType
from app.schemas.validation import (
    ValidationRuleResult,
    ValidationSummary,
)


# Standard currency decimal places by ISO 4217 code
CURRENCY_PRECISION_MAP: Dict[str, int] = {
    # 0 decimal places
    "JPY": 0,
    "KRW": 0,
    "VND": 0,
    "CLP": 0,
    "HUF": 0,
    # 3 decimal places
    "BHD": 3,
    "KWD": 3,
    "OMR": 3,
    "JOD": 3,
    "TND": 3,
    # Standard 2 decimal places default for USD, EUR, GBP, INR, CAD, AUD, etc.
}


def to_decimal(val: Any) -> Optional[Decimal]:
    """
    Safely converts a numeric value or string to high-precision Decimal.
    Returns None if value is None, empty, or cannot be parsed.
    """
    if val is None:
        return None
    try:
        val_str = str(val).strip().replace(",", "")
        return Decimal(val_str)
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_iso_date(date_str: Any) -> Optional[date]:
    """Parses standard ISO YYYY-MM-DD date."""
    if not date_str:
        return None
    try:
        return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


class FinancialValidationEngine:
    """
    Deterministic financial validation engine independent of LLMs.
    Performs high-precision Decimal business rule checks, ledger reconciliation,
    currency precision verification, and duplicate invoice detection.
    """

    def __init__(
        self,
        rounding_tolerance: Optional[float] = None,
        default_currency_precision: Optional[int] = None,
        strict_mode: bool = False,
    ):
        self.rounding_tolerance = Decimal(
            str(rounding_tolerance if rounding_tolerance is not None else settings.validation_rounding_tolerance)
        )
        self.default_currency_precision = (
            default_currency_precision or settings.validation_default_currency_precision
        )
        self.strict_mode = strict_mode

    async def validate_document_extraction(
        self,
        db: AsyncSession,
        document_id: str,
        organization_id: str,
        document_type: str,
        extracted_data: Dict[str, Any],
        extraction_id: Optional[str] = None,
        triggered_by: str = "EXTRACTION",
    ) -> Tuple[ValidationSummary, ValidationRun]:
        """
        Executes the complete rule suite for the extracted document data,
        records an immutable ValidationRun history snapshot in the database,
        and returns both the summary and persisted record.
        """
        results: List[ValidationRuleResult] = []

        # 1. Mandatory Fields Validation
        results.extend(self._validate_mandatory_fields(document_type, extracted_data))

        # 2. Date Formats & Temporal Relationships
        results.extend(self._validate_dates(document_type, extracted_data))

        # 3. Currency Precision & Formatting
        results.extend(self._validate_currency_precision(extracted_data))

        # 4. Document-Type Specific Rules
        doc_type_upper = (document_type or "UNKNOWN").upper()

        if doc_type_upper == DocumentType.INVOICE.value:
            # Invoice Math Reconciliations
            results.extend(self._validate_invoice_reconciliation(extracted_data))
            # Negative Values Check
            results.extend(self._validate_invoice_negative_values(extracted_data))
            # Duplicate Invoice Detection
            dup_result = await self._check_duplicate_invoice(
                db=db,
                document_id=document_id,
                organization_id=organization_id,
                extracted_data=extracted_data,
            )
            if dup_result:
                results.append(dup_result)

        elif doc_type_upper == DocumentType.BANK_STATEMENT.value:
            # Bank Statement Debit/Credit Checks
            results.extend(self._validate_transaction_debit_credit(extracted_data))
            # Running Balance & Closing Ledger Reconciliation
            results.extend(self._validate_bank_balances(extracted_data))

        elif doc_type_upper == DocumentType.EXPENSE_REPORT.value:
            # Expense Report Validations
            results.extend(self._validate_expense_report(extracted_data))

        # Compile Summary
        error_count = sum(1 for r in results if not r.is_passed and r.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for r in results if not r.is_passed and r.severity == ValidationSeverity.WARNING)
        info_count = sum(1 for r in results if not r.is_passed and r.severity == ValidationSeverity.INFO)
        is_valid = error_count == 0

        summary = ValidationSummary(
            is_valid=is_valid,
            has_warnings=warning_count > 0,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            results=results,
        )

        # Persist Validation History Record
        history_record = ValidationRun(
            document_id=document_id,
            extraction_id=extraction_id,
            organization_id=organization_id,
            triggered_by=triggered_by,
            is_valid=is_valid,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            results=[r.model_dump() for r in results],
        )
        db.add(history_record)
        await db.commit()
        await db.refresh(history_record)

        return summary, history_record

    # --------------------------------------------------------------------------
    # 1. Mandatory Fields Rules
    # --------------------------------------------------------------------------
    def _validate_mandatory_fields(
        self, document_type: str, data: Dict[str, Any]
    ) -> List[ValidationRuleResult]:
        results: List[ValidationRuleResult] = []
        doc_type_upper = (document_type or "UNKNOWN").upper()

        if doc_type_upper == DocumentType.INVOICE.value:
            required = {
                "invoice_number": "Invoice identifier",
                "vendor": "Vendor / issuer name",
                "invoice_date": "Invoice issue date",
                "total": "Total invoice payable amount",
            }
            missing = [k for k in required if data.get(k) is None or str(data.get(k)).strip() == ""]
            if missing:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_INV_MANDATORY_FIELDS",
                        rule_name="Invoice Mandatory Fields",
                        severity=ValidationSeverity.ERROR,
                        is_passed=False,
                        explanation=(
                            f"Mandatory invoice fields missing: "
                            f"{', '.join([required[k] for k in missing])}. Manual verification required."
                        ),
                        affected_fields=missing,
                    )
                )
            else:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_INV_MANDATORY_FIELDS",
                        rule_name="Invoice Mandatory Fields",
                        severity=ValidationSeverity.INFO,
                        is_passed=True,
                        explanation="All mandatory invoice fields are populated.",
                        affected_fields=list(required.keys()),
                    )
                )

        elif doc_type_upper == DocumentType.BANK_STATEMENT.value:
            required = {
                "opening_balance": "Opening balance",
                "closing_balance": "Closing balance",
            }
            missing = [k for k in required if data.get(k) is None]
            if missing:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_BANK_MANDATORY_FIELDS",
                        rule_name="Bank Statement Mandatory Balances",
                        severity=ValidationSeverity.ERROR,
                        is_passed=False,
                        explanation=f"Mandatory balance fields missing: {', '.join(missing)}.",
                        affected_fields=missing,
                    )
                )
            else:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_BANK_MANDATORY_FIELDS",
                        rule_name="Bank Statement Mandatory Balances",
                        severity=ValidationSeverity.INFO,
                        is_passed=True,
                        explanation="Opening and closing balances are present.",
                        affected_fields=list(required.keys()),
                    )
                )

        elif doc_type_upper == DocumentType.EXPENSE_REPORT.value:
            required = {
                "amount": "Expense total amount",
                "currency": "Expense currency",
                "expense_date": "Expense date",
                "merchant": "Merchant / Payee",
            }
            missing = [k for k in required if data.get(k) is None or str(data.get(k)).strip() == ""]
            if missing:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_EXP_MANDATORY_FIELDS",
                        rule_name="Expense Report Mandatory Fields",
                        severity=ValidationSeverity.ERROR,
                        is_passed=False,
                        explanation=f"Mandatory expense fields missing: {', '.join(missing)}.",
                        affected_fields=missing,
                    )
                )
            else:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_EXP_MANDATORY_FIELDS",
                        rule_name="Expense Report Mandatory Fields",
                        severity=ValidationSeverity.INFO,
                        is_passed=True,
                        explanation="All mandatory expense report fields are populated.",
                        affected_fields=list(required.keys()),
                    )
                )

        return results

    # --------------------------------------------------------------------------
    # 2. Date Formats & Relationships
    # --------------------------------------------------------------------------
    def _validate_dates(
        self, document_type: str, data: Dict[str, Any]
    ) -> List[ValidationRuleResult]:
        results: List[ValidationRuleResult] = []
        today = date.today()

        # Check all date fields for valid format
        date_fields = ["invoice_date", "due_date", "expense_date"]
        for field in date_fields:
            raw_val = data.get(field)
            if raw_val is not None:
                parsed = parse_iso_date(raw_val)
                if parsed is None:
                    results.append(
                        ValidationRuleResult(
                            rule_id="RULE_DATE_FORMAT",
                            rule_name="Date Format Standard",
                            severity=ValidationSeverity.ERROR,
                            is_passed=False,
                            explanation=f"Field '{field}' with value '{raw_val}' does not conform to ISO YYYY-MM-DD.",
                            affected_fields=[field],
                        )
                    )
                else:
                    # Check reasonableness: year >= 1990 and not far future (> 90 days ahead)
                    if parsed.year < 1990:
                        results.append(
                            ValidationRuleResult(
                                rule_id="RULE_DATE_RANGE",
                                rule_name="Historical Date Boundary",
                                severity=ValidationSeverity.WARNING,
                                is_passed=False,
                                explanation=f"Field '{field}' ({raw_val}) is dated before 1990. Please verify.",
                                affected_fields=[field],
                            )
                        )
                    elif parsed > today + timedelta(days=90):
                        results.append(
                            ValidationRuleResult(
                                rule_id="RULE_DATE_FUTURE",
                                rule_name="Future Date Verification",
                                severity=ValidationSeverity.WARNING,
                                is_passed=False,
                                explanation=f"Field '{field}' ({raw_val}) is more than 90 days in the future. Please verify.",
                                affected_fields=[field],
                            )
                        )

        # Invoice Date Relationship: due_date >= invoice_date
        inv_date_str = data.get("invoice_date")
        due_date_str = data.get("due_date")
        if inv_date_str and due_date_str:
            d_inv = parse_iso_date(inv_date_str)
            d_due = parse_iso_date(due_date_str)
            if d_inv and d_due:
                if d_due < d_inv:
                    results.append(
                        ValidationRuleResult(
                            rule_id="RULE_DATE_SEQUENCE",
                            rule_name="Invoice Due Date Sequence",
                            severity=ValidationSeverity.ERROR,
                            is_passed=False,
                            explanation=(
                                f"Invoice due date ({due_date_str}) precedes the issue date ({inv_date_str}). "
                                "Verification required."
                            ),
                            affected_fields=["invoice_date", "due_date"],
                        )
                    )
                else:
                    results.append(
                        ValidationRuleResult(
                            rule_id="RULE_DATE_SEQUENCE",
                            rule_name="Invoice Due Date Sequence",
                            severity=ValidationSeverity.INFO,
                            is_passed=True,
                            explanation="Due date is on or after the invoice issue date.",
                            affected_fields=["invoice_date", "due_date"],
                        )
                    )

        # Bank Statement Period Relationship: start_date <= end_date
        period = data.get("statement_period")
        if isinstance(period, dict):
            s_date_str = period.get("start_date")
            e_date_str = period.get("end_date")
            if s_date_str and e_date_str:
                d_start = parse_iso_date(s_date_str)
                d_end = parse_iso_date(e_date_str)
                if d_start and d_end and d_end < d_start:
                    results.append(
                        ValidationRuleResult(
                            rule_id="RULE_STATEMENT_PERIOD",
                            rule_name="Statement Period Sequence",
                            severity=ValidationSeverity.ERROR,
                            is_passed=False,
                            explanation=f"Statement period end date ({e_date_str}) precedes start date ({s_date_str}).",
                            affected_fields=["statement_period"],
                        )
                    )

        return results

    # --------------------------------------------------------------------------
    # 3. Currency Precision & Formatting Rules
    # --------------------------------------------------------------------------
    def _validate_currency_precision(self, data: Dict[str, Any]) -> List[ValidationRuleResult]:
        results: List[ValidationRuleResult] = []
        curr = data.get("currency")
        expected_decimals = CURRENCY_PRECISION_MAP.get(str(curr).upper(), self.default_currency_precision) if curr else self.default_currency_precision

        amount_fields = ["total", "subtotal", "tax", "amount", "opening_balance", "closing_balance"]
        excess_fields = []

        for field in amount_fields:
            val = data.get(field)
            if val is not None:
                dec = to_decimal(val)
                if dec is not None:
                    # Check fractional decimal places
                    exponent = abs(dec.as_tuple().exponent) if dec.as_tuple().exponent < 0 else 0
                    if exponent > expected_decimals:
                        excess_fields.append((field, str(val), exponent))

        if excess_fields:
            details = ", ".join([f"{f}={v} ({exp} decimals)" for f, v, exp in excess_fields])
            results.append(
                ValidationRuleResult(
                    rule_id="RULE_CURRENCY_PRECISION",
                    rule_name="Currency Decimal Precision",
                    severity=ValidationSeverity.WARNING,
                    is_passed=False,
                    explanation=(
                        f"Fields exceed expected currency precision ({expected_decimals} decimal places for {curr or 'default'}): "
                        f"{details}. Values may require standard rounding."
                    ),
                    affected_fields=[f for f, _, _ in excess_fields],
                )
            )
        else:
            results.append(
                ValidationRuleResult(
                    rule_id="RULE_CURRENCY_PRECISION",
                    rule_name="Currency Decimal Precision",
                    severity=ValidationSeverity.INFO,
                    is_passed=True,
                    explanation=f"All monetary values conform to standard currency precision ({expected_decimals} decimals).",
                    affected_fields=[f for f in amount_fields if data.get(f) is not None],
                )
            )

        return results

    # --------------------------------------------------------------------------
    # 4. Invoice Reconciliation (Decimal Arithmetic)
    # --------------------------------------------------------------------------
    def _validate_invoice_reconciliation(self, data: Dict[str, Any]) -> List[ValidationRuleResult]:
        results: List[ValidationRuleResult] = []

        d_total = to_decimal(data.get("total"))
        d_subtotal = to_decimal(data.get("subtotal"))
        d_tax = to_decimal(data.get("tax")) or Decimal("0.00")

        # 4a. Subtotal + Tax == Total
        if d_total is not None and d_subtotal is not None:
            expected_total = d_subtotal + d_tax
            diff = abs(d_total - expected_total)

            if diff > self.rounding_tolerance:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_INV_TOTAL_RECONCILIATION",
                        rule_name="Invoice Total Reconciliation",
                        severity=ValidationSeverity.ERROR,
                        is_passed=False,
                        explanation=(
                            f"Total ({d_total}) differs from Subtotal ({d_subtotal}) + Tax ({d_tax}) = "
                            f"{expected_total} by {diff} (tolerance: {self.rounding_tolerance}). Verification required."
                        ),
                        affected_fields=["total", "subtotal", "tax"],
                    )
                )
            else:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_INV_TOTAL_RECONCILIATION",
                        rule_name="Invoice Total Reconciliation",
                        severity=ValidationSeverity.INFO,
                        is_passed=True,
                        explanation=(
                            f"Total ({d_total}) reconciles with subtotal ({d_subtotal}) + tax ({d_tax}) "
                            f"within configured tolerance ({self.rounding_tolerance})."
                        ),
                        affected_fields=["total", "subtotal", "tax"],
                    )
                )

        # 4b. Itemized Line Items Sum vs Subtotal
        line_items = data.get("line_items") or []
        if line_items and isinstance(line_items, list):
            items_sum = Decimal("0.00")
            has_line_amounts = False

            for item in line_items:
                if isinstance(item, dict):
                    amt = to_decimal(item.get("amount"))
                    if amt is None and item.get("quantity") is not None and item.get("unit_price") is not None:
                        q = to_decimal(item.get("quantity"))
                        p = to_decimal(item.get("unit_price"))
                        if q is not None and p is not None:
                            amt = (q * p).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                    if amt is not None:
                        items_sum += amt
                        has_line_amounts = True

            target_subtotal = d_subtotal if d_subtotal is not None else d_total

            if has_line_amounts and target_subtotal is not None:
                item_diff = abs(items_sum - target_subtotal)
                if item_diff > self.rounding_tolerance:
                    results.append(
                        ValidationRuleResult(
                            rule_id="RULE_INV_LINE_ITEMS_RECONCILIATION",
                            rule_name="Line Items Sum vs Subtotal",
                            severity=ValidationSeverity.WARNING,
                            is_passed=False,
                            explanation=(
                                f"Sum of {len(line_items)} line items ({items_sum}) differs from target "
                                f"subtotal/total ({target_subtotal}) by {item_diff}. Please verify line pricing."
                            ),
                            affected_fields=["line_items", "subtotal"],
                        )
                    )
                else:
                    results.append(
                        ValidationRuleResult(
                            rule_id="RULE_INV_LINE_ITEMS_RECONCILIATION",
                            rule_name="Line Items Sum vs Subtotal",
                            severity=ValidationSeverity.INFO,
                            is_passed=True,
                            explanation=f"Sum of {len(line_items)} line items ({items_sum}) matches subtotal.",
                            affected_fields=["line_items", "subtotal"],
                        )
                    )

        return results

    def _validate_invoice_negative_values(self, data: Dict[str, Any]) -> List[ValidationRuleResult]:
        results: List[ValidationRuleResult] = []
        d_total = to_decimal(data.get("total"))
        d_subtotal = to_decimal(data.get("subtotal"))

        if (d_total is not None and d_total < Decimal("0.00")) or (d_subtotal is not None and d_subtotal < Decimal("0.00")):
            results.append(
                ValidationRuleResult(
                    rule_id="RULE_INV_NEGATIVE_AMOUNT",
                    rule_name="Negative Value Notice",
                    severity=ValidationSeverity.WARNING,
                    is_passed=False,
                    explanation="Negative invoice total or subtotal detected. Verify if document is a credit note or adjustment.",
                    affected_fields=["total", "subtotal"],
                )
            )

        return results

    # --------------------------------------------------------------------------
    # 5. Duplicate Invoice Detection
    # --------------------------------------------------------------------------
    async def _check_duplicate_invoice(
        self,
        db: AsyncSession,
        document_id: str,
        organization_id: str,
        extracted_data: Dict[str, Any],
    ) -> Optional[ValidationRuleResult]:
        inv_num = extracted_data.get("invoice_number")
        vendor = extracted_data.get("vendor")

        if not inv_num or not vendor:
            return None

        clean_inv = str(inv_num).strip()
        clean_vendor = str(vendor).strip()

        # Query existing extractions in this organization for identical invoice number and vendor
        query = (
            select(DocumentExtraction)
            .where(
                DocumentExtraction.organization_id == organization_id,
                DocumentExtraction.document_id != document_id,
                DocumentExtraction.document_type == DocumentType.INVOICE.value,
            )
            .limit(100)
        )
        res = await db.execute(query)
        existing_extractions = res.scalars().all()

        for ext in existing_extractions:
            ext_data = ext.extracted_data or {}
            ext_inv = str(ext_data.get("invoice_number", "")).strip()
            ext_vendor = str(ext_data.get("vendor", "")).strip()

            if ext_inv.lower() == clean_inv.lower() and ext_vendor.lower() == clean_vendor.lower():
                return ValidationRuleResult(
                    rule_id="RULE_DUP_INVOICE_IDENTIFIER",
                    rule_name="Duplicate Invoice Identifier Check",
                    severity=ValidationSeverity.ERROR,
                    is_passed=False,
                    explanation=(
                        f"Duplicate invoice identifier detected: An invoice with number '{clean_inv}' from vendor '{clean_vendor}' "
                        f"already exists in document (ID: {ext.document_id[:8]}...). "
                        "Verification required."
                    ),
                    affected_fields=["invoice_number", "vendor"],
                )

        return ValidationRuleResult(
            rule_id="RULE_DUP_INVOICE_IDENTIFIER",
            rule_name="Duplicate Invoice Identifier Check",
            severity=ValidationSeverity.INFO,
            is_passed=True,
            explanation=f"Invoice identifier '{clean_inv}' is unique within organization vendor history.",
            affected_fields=["invoice_number", "vendor"],
        )

    # --------------------------------------------------------------------------
    # 6. Bank Statement Transaction Checks & Running Balances
    # --------------------------------------------------------------------------
    def _validate_transaction_debit_credit(self, data: Dict[str, Any]) -> List[ValidationRuleResult]:
        results: List[ValidationRuleResult] = []
        txns = data.get("transactions") or []

        if not txns or not isinstance(txns, list):
            return results

        invalid_representation_count = 0
        negative_entry_count = 0
        missing_both_count = 0

        for i, t in enumerate(txns):
            if isinstance(t, dict):
                deb = to_decimal(t.get("debit"))
                crd = to_decimal(t.get("credit"))

                # Non-negative check
                if (deb is not None and deb < Decimal("0.00")) or (crd is not None and crd < Decimal("0.00")):
                    negative_entry_count += 1

                # Mutually exclusive: cannot both be non-zero
                if deb is not None and crd is not None and deb > Decimal("0.00") and crd > Decimal("0.00"):
                    invalid_representation_count += 1

                # At least one must be specified
                if (deb is None or deb == Decimal("0.00")) and (crd is None or crd == Decimal("0.00")):
                    missing_both_count += 1

        if invalid_representation_count > 0:
            results.append(
                ValidationRuleResult(
                    rule_id="RULE_TXN_DEBIT_CREDIT_MUTUAL",
                    rule_name="Debit/Credit Mutual Exclusivity",
                    severity=ValidationSeverity.ERROR,
                    is_passed=False,
                    explanation=(
                        f"{invalid_representation_count} transaction(s) have both non-zero debit and credit amounts. "
                        "Entries must represent either an inflow or an outflow."
                    ),
                    affected_fields=["transactions"],
                )
            )

        if negative_entry_count > 0:
            results.append(
                ValidationRuleResult(
                    rule_id="RULE_TXN_NON_NEGATIVE",
                    rule_name="Debit/Credit Non-Negative Sign",
                    severity=ValidationSeverity.ERROR,
                    is_passed=False,
                    explanation=(
                        f"{negative_entry_count} transaction(s) contain negative debit or credit amounts. "
                        "Debits and credits should be expressed as unsigned positive quantities."
                    ),
                    affected_fields=["transactions"],
                )
            )

        if missing_both_count > 0:
            results.append(
                ValidationRuleResult(
                    rule_id="RULE_TXN_AMOUNT_SPECIFIED",
                    rule_name="Transaction Amount Presence",
                    severity=ValidationSeverity.WARNING,
                    is_passed=False,
                    explanation=f"{missing_both_count} transaction(s) have neither debit nor credit populated.",
                    affected_fields=["transactions"],
                )
            )

        if invalid_representation_count == 0 and negative_entry_count == 0:
            results.append(
                ValidationRuleResult(
                    rule_id="RULE_TXN_DEBIT_CREDIT_MUTUAL",
                    rule_name="Debit/Credit Mutual Exclusivity",
                    severity=ValidationSeverity.INFO,
                    is_passed=True,
                    explanation="All transactions exhibit valid debit/credit representation.",
                    affected_fields=["transactions"],
                )
            )

        return results

    def _validate_bank_balances(self, data: Dict[str, Any]) -> List[ValidationRuleResult]:
        results: List[ValidationRuleResult] = []

        d_open = to_decimal(data.get("opening_balance"))
        d_close = to_decimal(data.get("closing_balance"))
        txns = data.get("transactions") or []

        total_credits = Decimal("0.00")
        total_debits = Decimal("0.00")

        # Track running balance reconciliation
        running_balance_mismatches = 0
        current_running = d_open

        for i, t in enumerate(txns):
            if isinstance(t, dict):
                deb = to_decimal(t.get("debit")) or Decimal("0.00")
                crd = to_decimal(t.get("credit")) or Decimal("0.00")
                total_credits += crd
                total_debits += deb

                stated_running = to_decimal(t.get("running_balance"))
                if current_running is not None:
                    expected_running = current_running + crd - deb
                    if stated_running is not None:
                        if abs(stated_running - expected_running) > self.rounding_tolerance:
                            running_balance_mismatches += 1
                        current_running = stated_running
                    else:
                        current_running = expected_running

        # Overall Statement Ledger Reconciliation:
        # Opening + Total Credits - Total Debits == Closing
        if d_open is not None and d_close is not None:
            expected_closing = d_open + total_credits - total_debits
            closing_diff = abs(d_close - expected_closing)

            if closing_diff > self.rounding_tolerance:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_BANK_LEDGER_RECONCILIATION",
                        rule_name="Bank Ledger Closing Reconciliation",
                        severity=ValidationSeverity.ERROR,
                        is_passed=False,
                        explanation=(
                            f"Closing balance ({d_close}) does not reconcile with Opening ({d_open}) + "
                            f"Credits ({total_credits}) - Debits ({total_debits}) = {expected_closing}. "
                            f"Discrepancy: {closing_diff} (tolerance: {self.rounding_tolerance})."
                        ),
                        affected_fields=["opening_balance", "closing_balance", "transactions"],
                    )
                )
            else:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_BANK_LEDGER_RECONCILIATION",
                        rule_name="Bank Ledger Closing Reconciliation",
                        severity=ValidationSeverity.INFO,
                        is_passed=True,
                        explanation=(
                            f"Opening ({d_open}) + Credits ({total_credits}) - Debits ({total_debits}) "
                            f"reconciles exactly with Closing ({d_close})."
                        ),
                        affected_fields=["opening_balance", "closing_balance", "transactions"],
                    )
                )

        if running_balance_mismatches > 0:
            results.append(
                ValidationRuleResult(
                    rule_id="RULE_BANK_RUNNING_BALANCES",
                    rule_name="Transaction Running Balance Step Verification",
                    severity=ValidationSeverity.WARNING,
                    is_passed=False,
                    explanation=(
                        f"{running_balance_mismatches} transaction row(s) exhibit running balance step discrepancies. "
                        "Verify whether transaction ordering or unrecorded adjustments exist."
                    ),
                    affected_fields=["running_balances", "transactions"],
                )
            )
        elif txns and any(isinstance(t, dict) and t.get("running_balance") is not None for t in txns):
            results.append(
                ValidationRuleResult(
                    rule_id="RULE_BANK_RUNNING_BALANCES",
                    rule_name="Transaction Running Balance Step Verification",
                    severity=ValidationSeverity.INFO,
                    is_passed=True,
                    explanation="All transaction running balances reconcile consecutively.",
                    affected_fields=["running_balances", "transactions"],
                )
            )

        return results

    # --------------------------------------------------------------------------
    # 7. Expense Report Checks
    # --------------------------------------------------------------------------
    def _validate_expense_report(self, data: Dict[str, Any]) -> List[ValidationRuleResult]:
        results: List[ValidationRuleResult] = []
        d_amount = to_decimal(data.get("amount"))

        if d_amount is not None and d_amount < Decimal("0.00"):
            results.append(
                ValidationRuleResult(
                    rule_id="RULE_EXP_NEGATIVE_AMOUNT",
                    rule_name="Negative Expense Claim",
                    severity=ValidationSeverity.WARNING,
                    is_passed=False,
                    explanation="Expense amount is negative. Confirm if this constitutes a refund or credit reimbursement.",
                    affected_fields=["amount"],
                )
            )

        expenses = data.get("expenses") or []
        if expenses and isinstance(expenses, list) and d_amount is not None:
            sub_sum = Decimal("0.00")
            for exp in expenses:
                if isinstance(exp, dict):
                    amt = to_decimal(exp.get("amount"))
                    if amt is not None:
                        sub_sum += amt

            diff = abs(sub_sum - d_amount)
            if diff > self.rounding_tolerance:
                results.append(
                    ValidationRuleResult(
                        rule_id="RULE_EXP_SUM_RECONCILIATION",
                        rule_name="Itemized Expense Sum Reconciliation",
                        severity=ValidationSeverity.WARNING,
                        is_passed=False,
                        explanation=f"Sum of itemized expense receipts ({sub_sum}) differs from overall total ({d_amount}) by {diff}.",
                        affected_fields=["amount", "expenses"],
                    )
                )

        return results
