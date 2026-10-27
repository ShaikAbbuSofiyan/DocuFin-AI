import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DocumentType(str, Enum):
    """Supported financial document categories."""
    INVOICE = "INVOICE"
    BANK_STATEMENT = "BANK_STATEMENT"
    EXPENSE_REPORT = "EXPENSE_REPORT"
    UNKNOWN = "UNKNOWN"


class ExtractionMethod(str, Enum):
    """Method utilized to extract or verify structured fields."""
    LLM = "LLM"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    HYBRID = "HYBRID"
    MANUAL = "MANUAL"


class ExtractionStatus(str, Enum):
    """Lifecycle status of the structured extraction."""
    EXTRACTED = "EXTRACTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ==============================================================================
# Normalization Utilities
# ==============================================================================

CURRENCY_SYMBOLS_MAP = {
    "$": "USD",
    "US$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "¥": "JPY",
    "C$": "CAD",
    "A$": "AUD",
    "CHF": "CHF",
}

COMMON_CURRENCY_CODES = {
    "USD", "EUR", "GBP", "INR", "JPY", "CAD", "AUD", "CHF", "CNY", "SGD", "HKD", "NZD"
}


def normalize_currency(val: Any) -> Optional[str]:
    """Normalizes currency text or symbol to standard 3-letter ISO code."""
    if val is None:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None

    # Check direct symbol mapping
    for sym, code in CURRENCY_SYMBOLS_MAP.items():
        if sym in val_str:
            return code

    # Check uppercase 3-letter code
    clean_code = re.sub(r"[^A-Za-z]", "", val_str).upper()
    if clean_code in COMMON_CURRENCY_CODES:
        return clean_code

    if len(clean_code) == 3:
        return clean_code

    return None


def normalize_numeric(val: Any) -> Optional[float]:
    """
    Parses currency strings, formatted commas, and accounting parentheses into standard float.
    Handles '(500.00)' as -500.00, '$1,234.56' as 1234.56.
    """
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        return float(val)

    val_str = str(val).strip()
    if not val_str:
        return None

    is_negative = False
    if val_str.startswith("(") and val_str.endswith(")"):
        is_negative = True
        val_str = val_str[1:-1].strip()
    elif val_str.startswith("-"):
        is_negative = True
        val_str = val_str[1:].strip()

    # Strip currency symbols and letters
    clean = re.sub(r"[^\d.,]", "", val_str)
    if not clean:
        return None

    # Handle European decimal formatting e.g. 1.234,56
    if "," in clean and "." in clean:
        if clean.rfind(",") > clean.rfind("."):
            clean = clean.replace(".", "").replace(",", ".")
        else:
            clean = clean.replace(",", "")
    elif "," in clean:
        # Check if comma represents decimal or thousands
        parts = clean.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            clean = clean.replace(",", ".")
        else:
            clean = clean.replace(",", "")

    try:
        num = float(clean)
        return -num if is_negative else num
    except ValueError:
        return None


def normalize_date(val: Any) -> Optional[str]:
    """
    Parses various date representations into standard ISO format (YYYY-MM-DD).
    Returns None if date cannot be validated. Never fabricates dates.
    """
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")

    val_str = str(val).strip()
    if not val_str:
        return None

    # Common date formats
    date_formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%b. %d, %Y",
        "%Y.%m.%d",
    ]

    for fmt in date_formats:
        try:
            parsed = datetime.strptime(val_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Regex extraction for embedded date like "Dated 2026-10-24"
    match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", val_str)
    if match:
        y, m, d = match.groups()
        try:
            parsed = datetime(int(y), int(m), int(d))
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


# ==============================================================================
# Field-Level Metadata & Confidence Models
# ==============================================================================

class FieldMetadata(BaseModel):
    """Audit metadata recorded for each extracted financial field."""
    value: Any = None
    raw_value: Optional[str] = None
    source_page: Optional[int] = Field(None, description="1-indexed source document page")
    extraction_method: str = Field(ExtractionMethod.LLM.value, description="Method used to extract field")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Heuristic confidence score (not calibrated)")


# ==============================================================================
# Versioned Financial Document Schemas (v1.0)
# ==============================================================================

class InvoiceLineItem(BaseModel):
    """Line item itemized on a corporate invoice."""
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None

    @field_validator("quantity", "unit_price", "total_price", mode="before")
    @classmethod
    def parse_numeric(cls, v: Any) -> Optional[float]:
        return normalize_numeric(v)


class InvoiceData(BaseModel):
    """
    Versioned Pydantic schema (v1.0) for accounts payable invoices.
    Supported fields:
    - invoice_number, vendor, invoice_date, due_date, currency, subtotal, tax, total, line_items.
    """
    schema_version: str = "v1.0"
    invoice_number: Optional[str] = None
    vendor: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    currency: Optional[str] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    line_items: List[InvoiceLineItem] = Field(default_factory=list)

    @field_validator("invoice_date", "due_date", mode="before")
    @classmethod
    def clean_dates(cls, v: Any) -> Optional[str]:
        return normalize_date(v)

    @field_validator("currency", mode="before")
    @classmethod
    def clean_currency(cls, v: Any) -> Optional[str]:
        return normalize_currency(v)

    @field_validator("subtotal", "tax", "total", mode="before")
    @classmethod
    def clean_amounts(cls, v: Any) -> Optional[float]:
        return normalize_numeric(v)

    @model_validator(mode="after")
    def validate_math_consistency(self) -> "InvoiceData":
        """Checks subtotal + tax = total within a rounding tolerance."""
        if self.subtotal is not None and self.tax is not None and self.total is not None:
            calc_total = round(self.subtotal + self.tax, 2)
            actual_total = round(self.total, 2)
            if abs(calc_total - actual_total) > 0.05:
                # Discrepancy detected, will be flagged during review routing
                pass
        return self


class BankTransaction(BaseModel):
    """Single ledger entry on a commercial bank statement."""
    transaction_date: Optional[str] = None
    description: Optional[str] = None
    debit: Optional[float] = None
    credit: Optional[float] = None
    running_balance: Optional[float] = None

    @field_validator("transaction_date", mode="before")
    @classmethod
    def clean_date(cls, v: Any) -> Optional[str]:
        return normalize_date(v)

    @field_validator("debit", "credit", "running_balance", mode="before")
    @classmethod
    def clean_numbers(cls, v: Any) -> Optional[float]:
        return normalize_numeric(v)


class StatementPeriod(BaseModel):
    """Date span for a bank statement cycle."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    raw_period: Optional[str] = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def clean_period_dates(cls, v: Any) -> Optional[str]:
        return normalize_date(v)


class BankStatementData(BaseModel):
    """
    Versioned Pydantic schema (v1.0) for commercial bank statements.
    Supported fields:
    - statement_period, opening_balance, closing_balance, transaction_dates, descriptions, debits, credits, running_balances.
    """
    schema_version: str = "v1.0"
    statement_period: Optional[Union[StatementPeriod, str]] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    transactions: List[BankTransaction] = Field(default_factory=list)

    # Aggregated convenience projections
    transaction_dates: List[str] = Field(default_factory=list)
    descriptions: List[str] = Field(default_factory=list)
    debits: List[float] = Field(default_factory=list)
    credits: List[float] = Field(default_factory=list)
    running_balances: List[float] = Field(default_factory=list)

    @field_validator("opening_balance", "closing_balance", mode="before")
    @classmethod
    def clean_balances(cls, v: Any) -> Optional[float]:
        return normalize_numeric(v)

    @model_validator(mode="after")
    def populate_projections(self) -> "BankStatementData":
        """Ensures transaction_dates, descriptions, debits, credits, running_balances are in sync."""
        if self.transactions:
            if not self.transaction_dates:
                self.transaction_dates = [t.transaction_date or "" for t in self.transactions]
            if not self.descriptions:
                self.descriptions = [t.description or "" for t in self.transactions]
            if not self.debits:
                self.debits = [t.debit or 0.0 for t in self.transactions]
            if not self.credits:
                self.credits = [t.credit or 0.0 for t in self.transactions]
            if not self.running_balances:
                self.running_balances = [t.running_balance or 0.0 for t in self.transactions]
        return self


class ExpenseItem(BaseModel):
    """Single line expense entry."""
    expense_date: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    description: Optional[str] = None

    @field_validator("expense_date", mode="before")
    @classmethod
    def clean_date(cls, v: Any) -> Optional[str]:
        return normalize_date(v)

    @field_validator("currency", mode="before")
    @classmethod
    def clean_curr(cls, v: Any) -> Optional[str]:
        return normalize_currency(v)

    @field_validator("amount", mode="before")
    @classmethod
    def clean_amount(cls, v: Any) -> Optional[float]:
        return normalize_numeric(v)


class ExpenseReportData(BaseModel):
    """
    Versioned Pydantic schema (v1.0) for employee expense claims and receipts.
    Supported fields:
    - expense_date, merchant, category, amount, currency, description, and expenses list.
    """
    schema_version: str = "v1.0"
    expense_date: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    expenses: List[ExpenseItem] = Field(default_factory=list)

    @field_validator("expense_date", mode="before")
    @classmethod
    def clean_date(cls, v: Any) -> Optional[str]:
        return normalize_date(v)

    @field_validator("currency", mode="before")
    @classmethod
    def clean_curr(cls, v: Any) -> Optional[str]:
        return normalize_currency(v)

    @field_validator("amount", mode="before")
    @classmethod
    def clean_amount(cls, v: Any) -> Optional[float]:
        return normalize_numeric(v)


# ==============================================================================
# Request & Response API Payloads
# ==============================================================================

class TriggerExtractionRequest(BaseModel):
    """Payload to trigger financial structured extraction."""
    force_reextract: bool = False
    document_type: Optional[DocumentType] = None
    preferred_provider: Optional[str] = None


class ClassificationResult(BaseModel):
    """Document classification output."""
    document_type: DocumentType
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    signals: List[str] = Field(default_factory=list)
    method: str = "HEURISTIC"


class DocumentExtractionResponse(BaseModel):
    """Structured extraction response with field-level metadata and audit trace."""
    id: str
    document_id: str
    organization_id: str
    document_type: str
    classification_confidence: float
    schema_version: str
    extracted_data: Dict[str, Any]
    field_metadata: Dict[str, FieldMetadata]
    extraction_method: str
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None
    confidence_score: float
    needs_review: bool
    review_reasons: List[str]
    is_valid: bool
    validation_errors: List[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentExtractionUpdate(BaseModel):
    """Editable fields payload submitted by financial analysts."""
    extracted_data: Dict[str, Any]
    status: Optional[str] = None  # APPROVED, REJECTED, REVIEW_REQUIRED
    analyst_notes: Optional[str] = None


class ReviewQueueItem(BaseModel):
    """Document queued for manual human-in-the-loop audit review."""
    extraction_id: str
    document_id: str
    document_title: str
    document_type: str
    filename: str
    status: str
    confidence_score: float
    review_reasons: List[str]
    created_at: datetime
    total_amount: Optional[float] = None
    currency: Optional[str] = None
