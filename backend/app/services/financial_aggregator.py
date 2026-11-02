import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.schemas.extraction import DocumentType


class CitationItem(BaseModel):
    """Verifiable source reference linking an answer back to its original document and page."""
    document_id: str
    document_title: str
    page_number: int
    excerpt: str
    relevance_score: float = 1.0


class AggregatorResult(BaseModel):
    """Result of deterministic financial aggregation over validated database records."""
    matched: bool
    answer: str = ""
    citations: List[CitationItem] = Field(default_factory=list)
    is_numerical_aggregation: bool = False
    intent: Optional[str] = None


class DeterministicFinancialAggregator:
    """
    Executes exact, deterministic financial calculations and queries directly over
    validated database records, guaranteeing that LLMs never hallucinate numerical figures.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_query(
        self,
        query: str,
        organization_id: str,
        scoped_doc_ids: Optional[List[str]] = None,
    ) -> AggregatorResult:
        """
        Determines whether the query asks a quantitative question answerable directly
        from validated structured records, and if so, computes the exact result.
        """
        q_lower = query.lower().strip()

        # 1. Total amount across invoices
        if self._is_total_amount_query(q_lower):
            return await self._aggregate_invoice_totals(organization_id, scoped_doc_ids)

        # 2. Overdue invoices
        if self._is_overdue_query(q_lower):
            return await self._query_overdue_invoices(organization_id, scoped_doc_ids)

        # 3. Closing / Opening balance query
        if self._is_balance_query(q_lower):
            return await self._query_bank_balances(organization_id, scoped_doc_ids)

        # 4. Transactions exceeding a numerical threshold
        threshold_match = self._match_transaction_threshold(q_lower)
        if threshold_match:
            thresh_val, thresh_curr = threshold_match
            return await self._query_high_value_transactions(
                organization_id, thresh_val, thresh_curr, scoped_doc_ids
            )

        # 5. Fields / documents needing manual verification
        if self._is_manual_verification_query(q_lower):
            return await self._query_manual_verification_items(organization_id, scoped_doc_ids)

        return AggregatorResult(matched=False)

    # --------------------------------------------------------------------------
    # Intent Matchers
    # --------------------------------------------------------------------------
    def _is_total_amount_query(self, q: str) -> bool:
        patterns = [
            r"total\s+(amount|sum|cost|spend|value)",
            r"sum\s+of\s+(all\s+)?(the\s+)?invoices",
            r"what\s+is\s+the\s+total",
            r"how\s+much\s+(in\s+total|altogether|are\s+these\s+invoices)",
            r"aggregate\s+(amount|total|sum)",
        ]
        return any(re.search(p, q) for p in patterns)

    def _is_overdue_query(self, q: str) -> bool:
        patterns = [
            r"overdue",
            r"past\s+due",
            r"late\s+invoices",
            r"unpaid\s+and\s+due",
            r"which\s+invoices\s+are\s+(overdue|late)",
        ]
        return any(re.search(p, q) for p in patterns)

    def _is_balance_query(self, q: str) -> bool:
        patterns = [
            r"closing\s+balance",
            r"opening\s+balance",
            r"ending\s+balance",
            r"what\s+is\s+the\s+(closing|opening|current|final)\s+balance",
            r"account\s+balance",
        ]
        return any(re.search(p, q) for p in patterns)

    def _match_transaction_threshold(self, q: str) -> Optional[Tuple[Decimal, Optional[str]]]:
        # Match e.g. "exceed ₹50,000", "greater than 50000", "over $10,000", "above 2500"
        m = re.search(
            r"(?:exceed(?:ing)?|greater\s+than|more\s+than|above|over)\s+([₹\$€£]?)[\s]*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)",
            q,
        )
        if m:
            curr_sym = m.group(1) or None
            curr_code = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}.get(curr_sym)
            raw_num = m.group(2).replace(",", "")
            try:
                val = Decimal(raw_num)
                return val, curr_code
            except Exception:
                pass
        return None

    def _is_manual_verification_query(self, q: str) -> bool:
        patterns = [
            r"manual\s+verification",
            r"need\s+(manual\s+)?verification",
            r"review\s+required",
            r"flagged(\s+for\s+review)?",
            r"which\s+(fields|documents)\s+need\s+(review|verification)",
            r"pending\s+review",
        ]
        return any(re.search(p, q) for p in patterns)

    # --------------------------------------------------------------------------
    # Deterministic Computation Handlers
    # --------------------------------------------------------------------------
    async def _aggregate_invoice_totals(
        self,
        org_id: str,
        scoped_doc_ids: Optional[List[str]],
    ) -> AggregatorResult:
        query = (
            select(DocumentExtraction, Document)
            .join(Document, DocumentExtraction.document_id == Document.id)
            .where(
                DocumentExtraction.organization_id == org_id,
                DocumentExtraction.document_type == DocumentType.INVOICE.value,
            )
        )
        if scoped_doc_ids:
            query = query.where(DocumentExtraction.document_id.in_(scoped_doc_ids))

        res = await self.db.execute(query)
        rows = res.all()

        if not rows:
            return AggregatorResult(
                matched=True,
                answer="No validated invoices were found matching the requested scope.",
                citations=[],
                is_numerical_aggregation=True,
                intent="TOTAL_AMOUNT",
            )

        total_sum = Decimal("0.00")
        currencies = set()
        citations = []
        breakdown = []

        for ext, doc in rows:
            data = ext.extracted_data or {}
            inv_total = data.get("total")
            inv_num = data.get("invoice_number") or doc.title or doc.filename
            curr = data.get("currency") or "USD"
            vendor = data.get("vendor") or "Unknown Vendor"
            currencies.add(curr)

            if inv_total is not None:
                dec_val = Decimal(str(inv_total))
                total_sum += dec_val
                breakdown.append(f"- **{inv_num}** ({vendor}): {curr} {dec_val:,.2f}")

                # Find source page
                field_meta = ext.field_metadata or {}
                pg = field_meta.get("total", {}).get("source_page") or 1

                citations.append(
                    CitationItem(
                        document_id=doc.id,
                        document_title=doc.title or doc.filename,
                        page_number=pg,
                        excerpt=f"Invoice {inv_num} ({vendor}) Total: {curr} {dec_val:,.2f}",
                        relevance_score=1.0,
                    )
                )

        curr_label = list(currencies)[0] if len(currencies) == 1 else "mixed currencies"
        ans = (
            f"### Deterministic Total Calculation\n\n"
            f"The exact total amount calculated across **{len(rows)} invoice(s)** is **{curr_label} {total_sum:,.2f}**.\n\n"
            f"**Itemized Breakdown:**\n" + "\n".join(breakdown)
        )

        return AggregatorResult(
            matched=True,
            answer=ans,
            citations=citations,
            is_numerical_aggregation=True,
            intent="TOTAL_AMOUNT",
        )

    async def _query_overdue_invoices(
        self,
        org_id: str,
        scoped_doc_ids: Optional[List[str]],
    ) -> AggregatorResult:
        query = (
            select(DocumentExtraction, Document)
            .join(Document, DocumentExtraction.document_id == Document.id)
            .where(
                DocumentExtraction.organization_id == org_id,
                DocumentExtraction.document_type == DocumentType.INVOICE.value,
            )
        )
        if scoped_doc_ids:
            query = query.where(DocumentExtraction.document_id.in_(scoped_doc_ids))

        res = await self.db.execute(query)
        rows = res.all()

        today = date.today()
        overdue_items = []
        citations = []

        for ext, doc in rows:
            data = ext.extracted_data or {}
            due_date_str = data.get("due_date")
            if due_date_str:
                try:
                    d_due = datetime.strptime(str(due_date_str).strip(), "%Y-%m-%d").date()
                    if d_due < today:
                        inv_num = data.get("invoice_number") or doc.title
                        vendor = data.get("vendor") or "Unknown"
                        tot = data.get("total")
                        curr = data.get("currency") or "USD"
                        days_late = (today - d_due).days

                        overdue_items.append(
                            f"- **{inv_num}** ({vendor}): Due **{d_due.isoformat()}** ({days_late} days overdue) — {curr} {tot:,.2f}"
                        )

                        field_meta = ext.field_metadata or {}
                        pg = field_meta.get("due_date", {}).get("source_page") or 1
                        citations.append(
                            CitationItem(
                                document_id=doc.id,
                                document_title=doc.title or doc.filename,
                                page_number=pg,
                                excerpt=f"Invoice {inv_num} Due Date: {due_date_str}, Amount: {curr} {tot}",
                                relevance_score=1.0,
                            )
                        )
                except ValueError:
                    pass

        if not overdue_items:
            return AggregatorResult(
                matched=True,
                answer=f"As of today ({today.isoformat()}), **none of the verified invoices are overdue**.",
                citations=[],
                is_numerical_aggregation=True,
                intent="OVERDUE_INVOICES",
            )

        ans = (
            f"### Overdue Invoices Report (As of {today.isoformat()})\n\n"
            f"Identified **{len(overdue_items)} overdue invoice(s)**:\n\n"
            + "\n".join(overdue_items)
        )
        return AggregatorResult(
            matched=True,
            answer=ans,
            citations=citations,
            is_numerical_aggregation=True,
            intent="OVERDUE_INVOICES",
        )

    async def _query_bank_balances(
        self,
        org_id: str,
        scoped_doc_ids: Optional[List[str]],
    ) -> AggregatorResult:
        query = (
            select(DocumentExtraction, Document)
            .join(Document, DocumentExtraction.document_id == Document.id)
            .where(
                DocumentExtraction.organization_id == org_id,
                DocumentExtraction.document_type == DocumentType.BANK_STATEMENT.value,
            )
        )
        if scoped_doc_ids:
            query = query.where(DocumentExtraction.document_id.in_(scoped_doc_ids))

        res = await self.db.execute(query)
        rows = res.all()

        if not rows:
            return AggregatorResult(
                matched=True,
                answer="No validated bank statements were found in the specified document scope.",
                citations=[],
                is_numerical_aggregation=True,
                intent="BANK_BALANCES",
            )

        reports = []
        citations = []
        for ext, doc in rows:
            data = ext.extracted_data or {}
            open_bal = data.get("opening_balance")
            close_bal = data.get("closing_balance")
            period = data.get("statement_period")
            period_str = ""
            if isinstance(period, dict):
                period_str = f" ({period.get('start_date')} to {period.get('end_date')})"

            reports.append(
                f"- **{doc.title or doc.filename}**{period_str}:\n"
                f"  - **Opening Balance**: {open_bal:,.2f}\n"
                f"  - **Closing Balance**: **{close_bal:,.2f}**"
            )

            field_meta = ext.field_metadata or {}
            pg = field_meta.get("closing_balance", {}).get("source_page") or 1
            citations.append(
                CitationItem(
                    document_id=doc.id,
                    document_title=doc.title or doc.filename,
                    page_number=pg,
                    excerpt=f"Statement{period_str} Opening: {open_bal}, Closing: {close_bal}",
                    relevance_score=1.0,
                )
            )

        ans = (
            "### Verified Bank Statement Balances\n\n"
            + "\n".join(reports)
        )
        return AggregatorResult(
            matched=True,
            answer=ans,
            citations=citations,
            is_numerical_aggregation=True,
            intent="BANK_BALANCES",
        )

    async def _query_high_value_transactions(
        self,
        org_id: str,
        threshold: Decimal,
        currency_code: Optional[str],
        scoped_doc_ids: Optional[List[str]],
    ) -> AggregatorResult:
        query = (
            select(DocumentExtraction, Document)
            .join(Document, DocumentExtraction.document_id == Document.id)
            .where(
                DocumentExtraction.organization_id == org_id,
                DocumentExtraction.document_type == DocumentType.BANK_STATEMENT.value,
            )
        )
        if scoped_doc_ids:
            query = query.where(DocumentExtraction.document_id.in_(scoped_doc_ids))

        res = await self.db.execute(query)
        rows = res.all()

        matching_txns = []
        citations = []

        for ext, doc in rows:
            data = ext.extracted_data or {}
            txns = data.get("transactions") or []
            for t in txns:
                if isinstance(t, dict):
                    deb = t.get("debit")
                    crd = t.get("credit")
                    amt = Decimal(str(deb if deb else (crd if crd else 0)))
                    if amt >= threshold:
                        t_type = "Debit" if deb else "Credit"
                        desc = t.get("description", "Transaction")
                        dt = t.get("transaction_date", "N/A")
                        curr_label = currency_code or "amount"

                        matching_txns.append(
                            f"- [{dt}] **{desc}**: {t_type} of **{curr_label} {amt:,.2f}** ({doc.title or doc.filename})"
                        )
                        citations.append(
                            CitationItem(
                                document_id=doc.id,
                                document_title=doc.title or doc.filename,
                                page_number=1,
                                excerpt=f"[{dt}] {desc}: {t_type} {amt:,.2f}",
                                relevance_score=1.0,
                            )
                        )

        if not matching_txns:
            return AggregatorResult(
                matched=True,
                answer=f"No transactions exceeding **{threshold:,.2f}** were found in the statement records.",
                citations=[],
                is_numerical_aggregation=True,
                intent="TRANSACTION_THRESHOLD",
            )

        ans = (
            f"### High-Value Transactions Exceeding {threshold:,.2f}\n\n"
            f"Found **{len(matching_txns)} transaction(s)** meeting criteria:\n\n"
            + "\n".join(matching_txns)
        )
        return AggregatorResult(
            matched=True,
            answer=ans,
            citations=citations,
            is_numerical_aggregation=True,
            intent="TRANSACTION_THRESHOLD",
        )

    async def _query_manual_verification_items(
        self,
        org_id: str,
        scoped_doc_ids: Optional[List[str]],
    ) -> AggregatorResult:
        query = (
            select(DocumentExtraction, Document)
            .join(Document, DocumentExtraction.document_id == Document.id)
            .where(
                DocumentExtraction.organization_id == org_id,
                DocumentExtraction.needs_review == True,
            )
        )
        if scoped_doc_ids:
            query = query.where(DocumentExtraction.document_id.in_(scoped_doc_ids))

        res = await self.db.execute(query)
        rows = res.all()

        if not rows:
            return AggregatorResult(
                matched=True,
                answer="All verified document extractions are approved; **no fields currently require manual verification**.",
                citations=[],
                is_numerical_aggregation=True,
                intent="MANUAL_VERIFICATION",
            )

        items = []
        citations = []
        for ext, doc in rows:
            reasons = ext.review_reasons or ["Flagged for analyst review"]
            reasons_fmt = "; ".join(reasons)
            items.append(
                f"- **{doc.title or doc.filename}** ({ext.document_type}):\n"
                f"  - *Review Reasons*: {reasons_fmt}\n"
                f"  - *Confidence*: {MathRound(ext.confidence_score * 100)}%"
            )
            citations.append(
                CitationItem(
                    document_id=doc.id,
                    document_title=doc.title or doc.filename,
                    page_number=1,
                    excerpt=f"Needs Review reasons: {reasons_fmt}",
                    relevance_score=1.0,
                )
            )

        ans = (
            f"### Records Requiring Manual Verification ({len(rows)})\n\n"
            + "\n".join(items)
        )
        return AggregatorResult(
            matched=True,
            answer=ans,
            citations=citations,
            is_numerical_aggregation=True,
            intent="MANUAL_VERIFICATION",
        )


def MathRound(val: float) -> int:
    return int(round(val))
