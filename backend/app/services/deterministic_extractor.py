import re
from typing import Any, Dict, List, Optional, Tuple
from app.schemas.extraction import (
    BankStatementData,
    BankTransaction,
    ExpenseItem,
    ExpenseReportData,
    ExtractionMethod,
    FieldMetadata,
    InvoiceData,
    InvoiceLineItem,
    StatementPeriod,
    normalize_currency,
    normalize_date,
    normalize_numeric,
)


def find_source_page(raw_needle: Optional[str], page_texts: Optional[List[str]]) -> Optional[int]:
    """Determines the 1-indexed document page where the extracted text appears."""
    if not raw_needle or not page_texts:
        return 1
    needle_clean = raw_needle.strip().lower()
    if not needle_clean:
        return 1

    for idx, page_text in enumerate(page_texts, start=1):
        if needle_clean in page_text.lower():
            return idx
    return 1


class DeterministicExtractor:
    """
    Deterministic rule-based and regex extraction engine for financial documents.
    Serves as offline fallback and cross-validation mechanism for LLM outputs.
    Guarantees that missing fields are kept as null (never fabricated).
    """

    # --------------------------------------------------------------------------
    # Invoice Extraction
    # --------------------------------------------------------------------------

    INVOICE_NUM_PATTERNS = [
        r"(?i)\binvoice\s*(?:number|no|#)[\s.:#-]*([A-Za-z0-9-_/]+)",
        r"(?i)\binv[\s.:#-]*([A-Za-z0-9-_/]+)",
        r"(?i)\bbill\s*#[\s.:#-]*([A-Za-z0-9-_/]+)",
    ]

    VENDOR_PATTERNS = [
        r"(?i)\b(?:from|vendor|billed\s+by|supplier|remit\s+to)[\s:]*([^\n\r]+)",
        r"(?i)^([A-Za-z0-9&.,\s-]{3,40}(?:Inc|LLC|Corp|Ltd|Co|Solutions|Technologies|Services))",
    ]

    INVOICE_DATE_PATTERNS = [
        r"(?i)\binvoice\s+date[\s.:-]*([A-Za-z0-9,./ -]{6,25})",
        r"(?i)\bdate\s+of\s+issue[\s.:-]*([A-Za-z0-9,./ -]{6,25})",
        r"(?i)\bdate[\s.:-]*([A-Za-z0-9,./ -]{6,25})",
    ]

    DUE_DATE_PATTERNS = [
        r"(?i)\bdue\s+date[\s.:-]*([A-Za-z0-9,./ -]{6,25})",
        r"(?i)\bpayment\s+due[\s.:-]*([A-Za-z0-9,./ -]{6,25})",
        r"(?i)\bpay\s+by[\s.:-]*([A-Za-z0-9,./ -]{6,25})",
    ]

    SUBTOTAL_PATTERNS = [
        r"(?i)\bsubtotal[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bsub-total[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bnet\s+amount[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
    ]

    TAX_PATTERNS = [
        r"(?i)\btax(?:\s*\(\d+%\))?[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bvat(?:\s*\(\d+%\))?[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bgst(?:\s*\(\d+%\))?[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bsales\s+tax[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
    ]

    TOTAL_PATTERNS = [
        r"(?i)\btotal\s+amount[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bamount\s+due[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bbalance\s+due[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\btotal[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bgrand\s+total[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
    ]

    @classmethod
    def extract_invoice(
        cls, text: str, page_texts: Optional[List[str]] = None
    ) -> Tuple[InvoiceData, Dict[str, FieldMetadata]]:
        field_meta: Dict[str, FieldMetadata] = {}

        # 1. Invoice Number
        inv_num, raw_inv = cls._match_first_pattern(text, cls.INVOICE_NUM_PATTERNS)
        field_meta["invoice_number"] = FieldMetadata(
            value=inv_num,
            raw_value=raw_inv,
            source_page=find_source_page(raw_inv, page_texts) if inv_num else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.92 if inv_num else 0.0,
        )

        # 2. Vendor
        vendor, raw_vendor = cls._extract_vendor(text)
        field_meta["vendor"] = FieldMetadata(
            value=vendor,
            raw_value=raw_vendor,
            source_page=find_source_page(raw_vendor, page_texts) if vendor else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.85 if vendor else 0.0,
        )

        # 3. Currency
        curr = normalize_currency(text)
        field_meta["currency"] = FieldMetadata(
            value=curr,
            raw_value=curr,
            source_page=1,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.95 if curr else 0.0,
        )

        # 4. Dates
        inv_date_str, raw_inv_date = cls._match_first_pattern(text, cls.INVOICE_DATE_PATTERNS)
        clean_inv_date = normalize_date(inv_date_str)
        field_meta["invoice_date"] = FieldMetadata(
            value=clean_inv_date,
            raw_value=raw_inv_date,
            source_page=find_source_page(raw_inv_date, page_texts) if clean_inv_date else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.90 if clean_inv_date else 0.0,
        )

        due_date_str, raw_due_date = cls._match_first_pattern(text, cls.DUE_DATE_PATTERNS)
        clean_due_date = normalize_date(due_date_str)
        field_meta["due_date"] = FieldMetadata(
            value=clean_due_date,
            raw_value=raw_due_date,
            source_page=find_source_page(raw_due_date, page_texts) if clean_due_date else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.90 if clean_due_date else 0.0,
        )

        # 5. Amounts
        subtotal_str, raw_sub = cls._match_first_pattern(text, cls.SUBTOTAL_PATTERNS)
        subtotal = normalize_numeric(subtotal_str)
        field_meta["subtotal"] = FieldMetadata(
            value=subtotal,
            raw_value=raw_sub,
            source_page=find_source_page(raw_sub, page_texts) if subtotal is not None else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.88 if subtotal is not None else 0.0,
        )

        tax_str, raw_tax = cls._match_first_pattern(text, cls.TAX_PATTERNS)
        tax = normalize_numeric(tax_str)
        field_meta["tax"] = FieldMetadata(
            value=tax,
            raw_value=raw_tax,
            source_page=find_source_page(raw_tax, page_texts) if tax is not None else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.88 if tax is not None else 0.0,
        )

        total_str, raw_total = cls._match_first_pattern(text, cls.TOTAL_PATTERNS)
        total = normalize_numeric(total_str)
        field_meta["total"] = FieldMetadata(
            value=total,
            raw_value=raw_total,
            source_page=find_source_page(raw_total, page_texts) if total is not None else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.94 if total is not None else 0.0,
        )

        # 6. Line Items
        line_items = cls._extract_invoice_line_items(text)
        field_meta["line_items"] = FieldMetadata(
            value=[li.model_dump() for li in line_items],
            raw_value=f"{len(line_items)} line items found",
            source_page=1,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.80 if line_items else 0.0,
        )

        invoice_data = InvoiceData(
            invoice_number=inv_num,
            vendor=vendor,
            invoice_date=clean_inv_date,
            due_date=clean_due_date,
            currency=curr,
            subtotal=subtotal,
            tax=tax,
            total=total,
            line_items=line_items,
        )

        return invoice_data, field_meta

    # --------------------------------------------------------------------------
    # Bank Statement Extraction
    # --------------------------------------------------------------------------

    STATEMENT_PERIOD_PATTERNS = [
        r"(?i)\bstatement\s+period[\s.:-]*([A-Za-z0-9,./ -]+(?:to|through|-)[A-Za-z0-9,./ -]+)",
        r"(?i)\bperiod[\s.:-]*([A-Za-z0-9,./ -]+(?:to|through|-)[A-Za-z0-9,./ -]+)",
        r"(?i)\bfor\s+the\s+period[\s.:-]*([A-Za-z0-9,./ -]+(?:to|through|-)[A-Za-z0-9,./ -]+)",
    ]

    OPENING_BALANCE_PATTERNS = [
        r"(?i)\bopening\s+balance[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bstarting\s+balance[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bbeginning\s+balance[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bprevious\s+balance[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
    ]

    CLOSING_BALANCE_PATTERNS = [
        r"(?i)\bclosing\s+balance[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bending\s+balance[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bnew\s+balance[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bstatement\s+balance[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
    ]

    @classmethod
    def extract_bank_statement(
        cls, text: str, page_texts: Optional[List[str]] = None
    ) -> Tuple[BankStatementData, Dict[str, FieldMetadata]]:
        field_meta: Dict[str, FieldMetadata] = {}

        # 1. Statement Period
        period_str, raw_period = cls._match_first_pattern(text, cls.STATEMENT_PERIOD_PATTERNS)
        period_obj = None
        if period_str:
            parts = re.split(r"(?i)\s+(?:to|through|-)\s+", period_str.strip())
            start_d = normalize_date(parts[0]) if len(parts) > 0 else None
            end_d = normalize_date(parts[1]) if len(parts) > 1 else None
            period_obj = StatementPeriod(
                start_date=start_d, end_date=end_d, raw_period=period_str.strip()
            )

        field_meta["statement_period"] = FieldMetadata(
            value=period_obj.model_dump() if period_obj else None,
            raw_value=raw_period,
            source_page=find_source_page(raw_period, page_texts) if period_obj else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.88 if period_obj else 0.0,
        )

        # 2. Opening Balance
        open_str, raw_open = cls._match_first_pattern(text, cls.OPENING_BALANCE_PATTERNS)
        open_bal = normalize_numeric(open_str)
        field_meta["opening_balance"] = FieldMetadata(
            value=open_bal,
            raw_value=raw_open,
            source_page=find_source_page(raw_open, page_texts) if open_bal is not None else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.92 if open_bal is not None else 0.0,
        )

        # 3. Closing Balance
        close_str, raw_close = cls._match_first_pattern(text, cls.CLOSING_BALANCE_PATTERNS)
        close_bal = normalize_numeric(close_str)
        field_meta["closing_balance"] = FieldMetadata(
            value=close_bal,
            raw_value=raw_close,
            source_page=find_source_page(raw_close, page_texts) if close_bal is not None else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.92 if close_bal is not None else 0.0,
        )

        # 4. Transactions
        transactions = cls._extract_bank_transactions(text)
        field_meta["transactions"] = FieldMetadata(
            value=[t.model_dump() for t in transactions],
            raw_value=f"{len(transactions)} transactions parsed",
            source_page=1,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.85 if transactions else 0.0,
        )

        # Summary field projections
        dates = [t.transaction_date or "" for t in transactions]
        descs = [t.description or "" for t in transactions]
        debits = [t.debit or 0.0 for t in transactions]
        credits = [t.credit or 0.0 for t in transactions]
        balances = [t.running_balance or 0.0 for t in transactions]

        field_meta["transaction_dates"] = FieldMetadata(
            value=dates, source_page=1, confidence=0.85 if dates else 0.0
        )
        field_meta["descriptions"] = FieldMetadata(
            value=descs, source_page=1, confidence=0.85 if descs else 0.0
        )
        field_meta["debits"] = FieldMetadata(
            value=debits, source_page=1, confidence=0.85 if debits else 0.0
        )
        field_meta["credits"] = FieldMetadata(
            value=credits, source_page=1, confidence=0.85 if credits else 0.0
        )
        field_meta["running_balances"] = FieldMetadata(
            value=balances, source_page=1, confidence=0.85 if balances else 0.0
        )

        data = BankStatementData(
            statement_period=period_obj,
            opening_balance=open_bal,
            closing_balance=close_bal,
            transactions=transactions,
            transaction_dates=dates,
            descriptions=descs,
            debits=debits,
            credits=credits,
            running_balances=balances,
        )

        return data, field_meta

    # --------------------------------------------------------------------------
    # Expense Report Extraction
    # --------------------------------------------------------------------------

    MERCHANT_PATTERNS = [
        r"(?i)\bmerchant[\s.:-]*([^\n\r]+)",
        r"(?i)\bpayee[\s.:-]*([^\n\r]+)",
        r"(?i)\bstore[\s.:-]*([^\n\r]+)",
        r"(?i)\bvendor[\s.:-]*([^\n\r]+)",
        r"(?i)^([A-Za-z0-9&.,\s-]{3,35}(?:Coffee|Cafe|Hotel|Airlines|Restaurant|Uber|Lyft|Suites|Express))",
    ]

    EXPENSE_DATE_PATTERNS = [
        r"(?i)\bexpense\s+date[\s.:-]*([A-Za-z0-9,./ -]{6,25})",
        r"(?i)\bdate[\s.:-]*([A-Za-z0-9,./ -]{6,25})",
        r"(?i)\btransaction\s+date[\s.:-]*([A-Za-z0-9,./ -]{6,25})",
    ]

    CATEGORY_PATTERNS = [
        r"(?i)\bcategory[\s.:-]*([A-Za-z\t &/-]{3,30})",
        r"(?i)\bexpense\s+type[\s.:-]*([A-Za-z\t &/-]{3,30})",
    ]

    EXPENSE_AMOUNT_PATTERNS = [
        r"(?i)\b(?:expense\s+)?amount[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\btotal\s+amount[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\btotal[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
        r"(?i)\bgrand\s+total[\s.:-]*([\$€£₹]?[0-9,.]+(?:\.\d{2})?)",
    ]

    EXPENSE_DESC_PATTERNS = [
        r"(?i)\bdescription[\s.:-]*([^\n\r]+)",
        r"(?i)\bbusiness\s+purpose[\s.:-]*([^\n\r]+)",
        r"(?i)\bpurpose[\s.:-]*([^\n\r]+)",
    ]

    @classmethod
    def extract_expense_report(
        cls, text: str, page_texts: Optional[List[str]] = None
    ) -> Tuple[ExpenseReportData, Dict[str, FieldMetadata]]:
        field_meta: Dict[str, FieldMetadata] = {}

        # 1. Date
        d_str, raw_d = cls._match_first_pattern(text, cls.EXPENSE_DATE_PATTERNS)
        clean_date = normalize_date(d_str)
        field_meta["expense_date"] = FieldMetadata(
            value=clean_date,
            raw_value=raw_d,
            source_page=find_source_page(raw_d, page_texts) if clean_date else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.90 if clean_date else 0.0,
        )

        # 2. Merchant
        merchant, raw_merchant = cls._match_first_pattern(text, cls.MERCHANT_PATTERNS)
        if merchant:
            merchant = merchant.strip().strip(",")
        field_meta["merchant"] = FieldMetadata(
            value=merchant,
            raw_value=raw_merchant,
            source_page=find_source_page(raw_merchant, page_texts) if merchant else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.88 if merchant else 0.0,
        )

        # 3. Category
        category, raw_cat = cls._match_first_pattern(text, cls.CATEGORY_PATTERNS)
        if category:
            category = category.strip().title()
        else:
            # Infer standard category from merchant/text
            category = cls._infer_expense_category(text)

        field_meta["category"] = FieldMetadata(
            value=category,
            raw_value=raw_cat,
            source_page=find_source_page(raw_cat, page_texts) if category else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.80 if category else 0.0,
        )

        # 4. Amount
        amt_str, raw_amt = cls._match_first_pattern(text, cls.EXPENSE_AMOUNT_PATTERNS)
        amount = normalize_numeric(amt_str)
        field_meta["amount"] = FieldMetadata(
            value=amount,
            raw_value=raw_amt,
            source_page=find_source_page(raw_amt, page_texts) if amount is not None else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.92 if amount is not None else 0.0,
        )

        # 5. Currency
        curr = normalize_currency(text)
        field_meta["currency"] = FieldMetadata(
            value=curr,
            raw_value=curr,
            source_page=1,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.95 if curr else 0.0,
        )

        # 6. Description
        desc, raw_desc = cls._match_first_pattern(text, cls.EXPENSE_DESC_PATTERNS)
        if desc:
            desc = desc.strip()
        field_meta["description"] = FieldMetadata(
            value=desc,
            raw_value=raw_desc,
            source_page=find_source_page(raw_desc, page_texts) if desc else None,
            extraction_method=ExtractionMethod.DETERMINISTIC_FALLBACK.value,
            confidence=0.80 if desc else 0.0,
        )

        # Single expense item list
        expense_item = ExpenseItem(
            expense_date=clean_date,
            merchant=merchant,
            category=category,
            amount=amount,
            currency=curr,
            description=desc,
        )

        data = ExpenseReportData(
            expense_date=clean_date,
            merchant=merchant,
            category=category,
            amount=amount,
            currency=curr,
            description=desc,
            expenses=[expense_item] if amount is not None else [],
        )

        return data, field_meta

    # --------------------------------------------------------------------------
    # Helper Extractors
    # --------------------------------------------------------------------------

    @classmethod
    def _match_first_pattern(
        cls, text: str, patterns: List[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                val = match.group(1).strip()
                return val, match.group(0).strip()
        return None, None

    @classmethod
    def _extract_vendor(cls, text: str) -> Tuple[Optional[str], Optional[str]]:
        # Heuristic 1: Check first 3 lines for company entity suffix (Inc, LLC, Corp, Ltd, etc.)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:3]:
            if any(k in line.lower() for k in ["invoice", "tax invoice", "statement", "receipt", "page", "bill to"]):
                continue
            if re.search(r"(?i)\b(?:Inc|LLC|Corp|Ltd|Co|Solutions|Technologies|Services|Group)\b", line):
                return line.strip(",."), line

        # Heuristic 2: Check explicit patterns
        for pattern in cls.VENDOR_PATTERNS:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                v = match.group(1).strip().strip(",.")
                if len(v) > 2 and not any(k in v.lower() for k in ["invoice", "date", "bill to", "tax"]):
                    return v, match.group(0).strip()

        # Heuristic 3: First clean non-header line that looks like an organization name
        for line in lines[:5]:
            if any(k in line.lower() for k in ["invoice", "tax invoice", "statement", "receipt", "page", "bill to"]):
                continue
            if len(line) >= 3 and len(line) <= 50 and not re.match(r"^\d", line):
                return line.strip(",."), line

        return None, None

    @classmethod
    def _extract_invoice_line_items(cls, text: str) -> List[InvoiceLineItem]:
        items: List[InvoiceLineItem] = []
        # Match lines like: "Software Subscription   1   $1,200.00   $1,200.00"
        line_item_regex = re.compile(
            r"^(?P<desc>[A-Za-z0-9\s.,&/-]{4,50})\s+(?P<qty>\d+(?:\.\d+)?)\s+[\$€£₹]?(?P<unit>[0-9,.]+(?:\.\d{2})?)\s+[\$€£₹]?(?P<tot>[0-9,.]+(?:\.\d{2})?)$",
            re.MULTILINE,
        )
        for m in line_item_regex.finditer(text):
            desc = m.group("desc").strip()
            # Ignore headers
            if any(h in desc.lower() for h in ["description", "item", "qty", "rate", "subtotal"]):
                continue
            qty = normalize_numeric(m.group("qty"))
            unit = normalize_numeric(m.group("unit"))
            tot = normalize_numeric(m.group("tot"))
            items.append(
                InvoiceLineItem(description=desc, quantity=qty, unit_price=unit, total_price=tot)
            )

        return items

    @classmethod
    def _extract_bank_transactions(cls, text: str) -> List[BankTransaction]:
        transactions: List[BankTransaction] = []
        # Pattern: Date  Description  Debit/Withdrawal  Credit/Deposit  Balance
        # e.g.: "10/12/2026 Payroll Direct Deposit 0.00 4500.00 9500.00"
        tx_regex = re.compile(
            r"^(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(?P<desc>[A-Za-z0-9\s.,&#/-]{3,40}?)\s+(?:[\$€£₹]?(?P<debit>[0-9,.]+(?:\.\d{2})?)\s+)?(?:[\$€£₹]?(?P<credit>[0-9,.]+(?:\.\d{2})?)\s+)?(?:[\$€£₹]?(?P<balance>[0-9,.]+(?:\.\d{2})?))$",
            re.MULTILINE,
        )

        for m in tx_regex.finditer(text):
            d_str = normalize_date(m.group("date"))
            desc = m.group("desc").strip()
            debit = normalize_numeric(m.group("debit"))
            credit = normalize_numeric(m.group("credit"))
            bal = normalize_numeric(m.group("balance"))

            transactions.append(
                BankTransaction(
                    transaction_date=d_str,
                    description=desc,
                    debit=debit,
                    credit=credit,
                    running_balance=bal,
                )
            )

        return transactions

    @classmethod
    def _infer_expense_category(cls, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["hotel", "inn", "suites", "flight", "airline", "uber", "taxi", "rental"]):
            return "Travel & Lodging"
        if any(w in text_lower for w in ["cafe", "coffee", "restaurant", "dining", "starbucks", "meal", "grill"]):
            return "Meals & Entertainment"
        if any(w in text_lower for w in ["software", "aws", "cloud", "github", "subscription", "saas", "license"]):
            return "Software & Subscriptions"
        if any(w in text_lower for w in ["office", "staples", "paper", "supplies", "desk"]):
            return "Office Supplies"
        return "General Business"
