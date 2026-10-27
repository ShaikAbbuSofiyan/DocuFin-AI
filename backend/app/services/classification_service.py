import re
from typing import Dict, List, Tuple
from app.schemas.extraction import ClassificationResult, DocumentType


class DocumentClassificationService:
    """
    Deterministic rule-based & keyword classifier for financial filings and records.
    Evaluates lexical density, domain markers, and structural anchors.
    """

    # Primary high-confidence anchors
    INVOICE_ANCHORS = [
        r"\btax\s+invoice\b",
        r"\binvoice\s*#?:?\s*[a-z0-9_-]+",
        r"\bbill\s+to\b",
        r"\bremit\s+to\b",
        r"\bpayment\s+terms\b",
        r"\bdue\s+date\b",
        r"\bsubtotal\b",
        r"\bunit\s+price\b",
        r"\bpo\s*#?:?\s*[a-z0-9_-]+",
    ]

    BANK_STATEMENT_ANCHORS = [
        r"\bbank\s+statement\b",
        r"\baccount\s+statement\b",
        r"\baccount\s+summary\b",
        r"\bopening\s+balance\b",
        r"\bclosing\s+balance\b",
        r"\bstarting\s+balance\b",
        r"\bending\s+balance\b",
        r"\bdeposits\s+and\s+(?:other\s+)?credits\b",
        r"\bwithdrawals\s+and\s+(?:other\s+)?debits\b",
        r"\bchecking\s+account\b",
        r"\bsavings\s+account\b",
        r"\bstatement\s+period\b",
    ]

    EXPENSE_REPORT_ANCHORS = [
        r"\bexpense\s+report\b",
        r"\bexpense\s+claim\b",
        r"\breimbursement\s+(?:form|request|claim)\b",
        r"\bemployee\s+expense\b",
        r"\bbusiness\s+purpose\b",
        r"\bmerchant\b",
        r"\bexpense\s+date\b",
        r"\breceipt\b",
        r"\bper\s+diem\b",
        r"\bcardholder\b",
    ]

    # Secondary supporting keywords
    INVOICE_KEYWORDS = ["invoice", "vendor", "client", "billing", "subtotal", "tax", "total", "item", "qty", "rate"]
    BANK_KEYWORDS = ["bank", "account", "transaction", "balance", "debit", "credit", "ledger", "deposit", "withdrawal", "statement"]
    EXPENSE_KEYWORDS = ["expense", "merchant", "receipt", "category", "claim", "reimbursement", "travel", "mileage", "meal"]

    @classmethod
    def classify(cls, text: str) -> ClassificationResult:
        """
        Classifies financial document text into INVOICE, BANK_STATEMENT, EXPENSE_REPORT, or UNKNOWN.
        Returns document type, confidence score (0.0 - 1.0), and matched signals.
        """
        if not text or not text.strip():
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                signals=["Empty text content"],
                method="HEURISTIC",
            )

        text_lower = text.lower()

        invoice_score, invoice_signals = cls._score_category(
            text_lower, cls.INVOICE_ANCHORS, cls.INVOICE_KEYWORDS, "Invoice"
        )
        bank_score, bank_signals = cls._score_category(
            text_lower, cls.BANK_STATEMENT_ANCHORS, cls.BANK_KEYWORDS, "BankStatement"
        )
        expense_score, expense_signals = cls._score_category(
            text_lower, cls.EXPENSE_REPORT_ANCHORS, cls.EXPENSE_KEYWORDS, "ExpenseReport"
        )

        scores = [
            (DocumentType.INVOICE, invoice_score, invoice_signals),
            (DocumentType.BANK_STATEMENT, bank_score, bank_signals),
            (DocumentType.EXPENSE_REPORT, expense_score, expense_signals),
        ]

        # Sort descending by score
        scores.sort(key=lambda x: x[1], reverse=True)
        top_type, top_score, top_signals = scores[0]

        # Minimum threshold for confident classification
        if top_score < 3.0:
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=round(min(top_score / 10.0, 0.45), 2),
                signals=top_signals or ["Insufficient domain signals"],
                method="HEURISTIC",
            )

        # Calculate heuristic confidence: score scaled, capped at 0.98
        second_score = scores[1][1]
        margin = top_score - second_score
        base_conf = 0.70 + min(margin * 0.05, 0.25)
        confidence = round(min(base_conf, 0.98), 2)

        return ClassificationResult(
            document_type=top_type,
            confidence=confidence,
            signals=top_signals,
            method="HEURISTIC",
        )

    @classmethod
    def _score_category(
        cls, text: str, anchors: List[str], keywords: List[str], label: str
    ) -> Tuple[float, List[str]]:
        score = 0.0
        signals = []

        # High-weight anchor regex matches (3.0 points each)
        for pattern in anchors:
            matches = re.findall(pattern, text)
            if matches:
                weight = 3.0 * min(len(matches), 3)
                score += weight
                clean_name = pattern.replace(r"\b", "").replace(r"\s+", " ")
                signals.append(f"Anchor '{clean_name}' (matched {len(matches)}x)")

        # Secondary keyword matches (0.5 points each)
        for kw in keywords:
            count = len(re.findall(rf"\b{kw}\b", text))
            if count > 0:
                score += min(count * 0.5, 2.0)
                if len(signals) < 6:
                    signals.append(f"Keyword '{kw}' ({count}x)")

        return score, signals
