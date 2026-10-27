import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.llm_provider import LLMExtractionResult, LLMProvider, get_llm_provider
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.document import Document, DocumentStatus
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.document_page import DocumentPage
from app.models.user import User
from app.schemas.extraction import (
    BankStatementData,
    ClassificationResult,
    DocumentExtractionResponse,
    DocumentExtractionUpdate,
    DocumentType,
    ExpenseReportData,
    ExtractionMethod,
    FieldMetadata,
    InvoiceData,
    ReviewQueueItem,
    normalize_currency,
    normalize_date,
    normalize_numeric,
)
from app.services.classification_service import DocumentClassificationService
from app.services.deterministic_extractor import DeterministicExtractor, find_source_page

logger = logging.getLogger("docufin.services.extraction_service")


class FinancialExtractionService:
    """
    Coordinates financial document intelligence, schema validation, LLM extraction,
    deterministic fallbacks, field confidence computation, and review routing.
    """

    def __init__(self, db: AsyncSession, llm_provider: Optional[LLMProvider] = None):
        self.db = db
        self.settings = get_settings()
        self.llm_provider = llm_provider or get_llm_provider(self.settings)

    async def extract_document(
        self,
        doc_id: str,
        org_id: str,
        preferred_doc_type: Optional[DocumentType] = None,
        force_reextract: bool = False,
    ) -> DocumentExtraction:
        """
        Extracts structured financial entities from the document's OCR text.
        Guarantees bounded validation, field source page preservation, and review routing.
        """
        # 1. Fetch document and OCR pages
        query = (
            select(Document)
            .where(Document.id == doc_id, Document.organization_id == org_id)
            .options(selectinload(Document.pages), selectinload(Document.extractions))
        )
        res = await self.db.execute(query)
        doc = res.scalar_one_or_none()
        if not doc:
            raise NotFoundError("Document", doc_id)

        # Check existing extraction
        if doc.extractions and not force_reextract:
            latest = doc.extractions[0]
            if latest.status != ExtractionStatus.REJECTED.value:
                return latest

        # Check pages from Phase 4 OCR
        pages: List[DocumentPage] = sorted(doc.pages, key=lambda p: p.page_number)
        if not pages:
            raise ValidationError(
                "Document has no extracted OCR pages. Please run document processing first."
            )

        page_texts = [p.text_content for p in pages]
        full_text = "\n\n--- PAGE BREAK ---\n\n".join(page_texts)

        if not full_text.strip():
            raise ValidationError(
                "Document OCR text is empty. Text extraction or OCR produced zero characters."
            )

        # 2. Document Classification
        classification_res: ClassificationResult
        if preferred_doc_type and preferred_doc_type != DocumentType.UNKNOWN:
            classification_res = ClassificationResult(
                document_type=preferred_doc_type,
                confidence=1.0,
                signals=["User/Payload explicitly specified"],
                method="EXPLICIT",
            )
        elif doc.doc_type and doc.doc_type.upper() in DocumentType._value2member_map_:
            classification_res = ClassificationResult(
                document_type=DocumentType(doc.doc_type.upper()),
                confidence=0.95,
                signals=["Preserved from ingestion metadata"],
                method="METADATA",
            )
        else:
            classification_res = await self.llm_provider.classify_document(full_text)

        target_type = classification_res.document_type
        if target_type == DocumentType.UNKNOWN:
            # Fallback to Invoice if signals suggest general invoice
            target_type = DocumentType.INVOICE

        # 3. Structured Extraction Execution via LLM Provider
        llm_result: LLMExtractionResult
        try:
            llm_result = await self.llm_provider.extract_structured(
                text=full_text,
                document_type=target_type,
                page_texts=page_texts,
            )
        except Exception as e:
            logger.error(f"Primary LLM extraction failed: {e}. Executing deterministic fallback.")
            llm_result = LLMExtractionResult(
                data={},
                provider=getattr(self.llm_provider, "provider", "fallback"),
                error=str(e),
                is_fallback=True,
            )

        # 4. Deterministic Extraction (for fallback, corroboration, and source-page resolution)
        deterministic_data: Any
        deterministic_meta: Dict[str, FieldMetadata]
        if target_type == DocumentType.INVOICE:
            deterministic_data, deterministic_meta = DeterministicExtractor.extract_invoice(
                full_text, page_texts
            )
        elif target_type == DocumentType.BANK_STATEMENT:
            deterministic_data, deterministic_meta = DeterministicExtractor.extract_bank_statement(
                full_text, page_texts
            )
        else:
            deterministic_data, deterministic_meta = DeterministicExtractor.extract_expense_report(
                full_text, page_texts
            )

        # 5. Schema Validation, Normalization, & Synthesis
        final_dict, field_meta, review_reasons, validation_errors = self._synthesize_and_validate(
            target_type=target_type,
            llm_result=llm_result,
            deterministic_data=deterministic_data,
            deterministic_meta=deterministic_meta,
            page_texts=page_texts,
        )

        # 6. Overall Confidence & Review Routing
        valid_confidences = [
            fm.confidence for fm in field_meta.values() if fm.value is not None
        ]
        avg_confidence = (
            sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.50
        )
        # Confidence penalty if math discrepancy or validation errors
        if review_reasons or validation_errors:
            avg_confidence = max(0.20, avg_confidence - 0.25)

        needs_review = (
            avg_confidence < self.settings.extraction_confidence_threshold
            or len(review_reasons) > 0
            or len(validation_errors) > 0
        )

        extraction_status = (
            ExtractionStatus.REVIEW_REQUIRED.value if needs_review else ExtractionStatus.EXTRACTED.value
        )

        # Determine overall extraction method
        method = ExtractionMethod.LLM.value
        if llm_result.is_fallback:
            method = ExtractionMethod.DETERMINISTIC_FALLBACK.value
        elif any(fm.extraction_method == ExtractionMethod.DETERMINISTIC_FALLBACK.value for fm in field_meta.values()):
            method = ExtractionMethod.HYBRID.value

        # 7. Persist DocumentExtraction
        token_usage_dict = (
            llm_result.token_usage.model_dump() if llm_result.token_usage else None
        )

        extraction = DocumentExtraction(
            document_id=doc.id,
            organization_id=doc.organization_id,
            document_type=target_type.value,
            classification_confidence=classification_res.confidence,
            schema_version="v1.0",
            extracted_data=final_dict,
            field_metadata={k: v.model_dump() for k, v in field_meta.items()},
            extraction_method=method,
            llm_provider=llm_result.provider,
            llm_model=llm_result.model,
            token_usage=token_usage_dict,
            confidence_score=round(avg_confidence, 2),
            needs_review=needs_review,
            review_reasons=review_reasons,
            is_valid=(len(validation_errors) == 0),
            validation_errors=validation_errors,
            status=extraction_status,
        )

        self.db.add(extraction)

        # Update Document's classification and processing status
        doc.doc_type = target_type.value
        if needs_review:
            doc.status = DocumentStatus.REVIEW_REQUIRED.value
        else:
            doc.status = DocumentStatus.APPROVED.value

        await self.db.commit()
        await self.db.refresh(extraction)

        return extraction

    def _synthesize_and_validate(
        self,
        target_type: DocumentType,
        llm_result: LLMExtractionResult,
        deterministic_data: Any,
        deterministic_meta: Dict[str, FieldMetadata],
        page_texts: List[str],
    ) -> Tuple[Dict[str, Any], Dict[str, FieldMetadata], List[str], List[str]]:
        """
        Merges LLM outputs with deterministic fallbacks, enforces Pydantic validation,
        performs business-independent mathematical reconciliation, and never fabricates missing values.
        """
        review_reasons: List[str] = []
        validation_errors: List[str] = []
        field_meta: Dict[str, FieldMetadata] = {}

        llm_data = llm_result.data or {}
        det_dict = deterministic_data.model_dump()

        if target_type == DocumentType.INVOICE:
            merged: Dict[str, Any] = {}
            for field in [
                "invoice_number", "vendor", "invoice_date", "due_date",
                "currency", "subtotal", "tax", "total", "line_items",
            ]:
                llm_val = llm_data.get(field)
                det_val = det_dict.get(field)

                # Prioritize LLM value if valid, fallback to deterministic
                val = llm_val if llm_val is not None else det_val
                merged[field] = val

                raw = str(val) if val is not None else None
                source_pg = find_source_page(raw, page_texts) if val is not None else None

                method = ExtractionMethod.LLM.value if llm_val is not None else ExtractionMethod.DETERMINISTIC_FALLBACK.value
                conf = 0.85 if llm_val is not None else 0.80
                if llm_val is not None and det_val is not None and str(llm_val).lower() == str(det_val).lower():
                    # Corroborated by both LLM and regex
                    conf = 0.95
                    method = ExtractionMethod.HYBRID.value

                field_meta[field] = FieldMetadata(
                    value=val,
                    raw_value=raw,
                    source_page=source_pg,
                    extraction_method=method,
                    confidence=conf if val is not None else 0.0,
                )

            # Pydantic validation
            try:
                validated_model = InvoiceData.model_validate(merged)
                final_data = validated_model.model_dump()
            except Exception as e:
                validation_errors.append(f"Invoice schema validation error: {e}")
                final_data = merged

            # Business Check: Math reconciliation (subtotal + tax = total)
            sub = final_data.get("subtotal")
            tax = final_data.get("tax")
            tot = final_data.get("total")
            if sub is not None and tax is not None and tot is not None:
                expected = round(sub + tax, 2)
                actual = round(tot, 2)
                if abs(expected - actual) > 0.05:
                    review_reasons.append(
                        f"Mathematical discrepancy: Subtotal ({sub:.2f}) + Tax ({tax:.2f}) = {expected:.2f}, but Total is {actual:.2f}."
                    )
            elif tot is None:
                review_reasons.append("Critical field 'total' is missing or unextracted.")

            # Date sanity check
            inv_d = final_data.get("invoice_date")
            due_d = final_data.get("due_date")
            if inv_d and due_d and due_d < inv_d:
                review_reasons.append(
                    f"Temporal anomaly: Due date ({due_d}) precedes Invoice date ({inv_d})."
                )

        elif target_type == DocumentType.BANK_STATEMENT:
            merged = {}
            for field in [
                "statement_period", "opening_balance", "closing_balance",
                "transactions", "transaction_dates", "descriptions",
                "debits", "credits", "running_balances",
            ]:
                llm_val = llm_data.get(field)
                det_val = det_dict.get(field)
                val = llm_val if llm_val is not None else det_val
                merged[field] = val

                raw = str(val) if val is not None else None
                source_pg = find_source_page(raw, page_texts) if val is not None else None
                field_meta[field] = FieldMetadata(
                    value=val,
                    raw_value=raw,
                    source_page=source_pg,
                    extraction_method=ExtractionMethod.LLM.value if llm_val is not None else ExtractionMethod.DETERMINISTIC_FALLBACK.value,
                    confidence=0.88 if val is not None else 0.0,
                )

            try:
                validated_model = BankStatementData.model_validate(merged)
                final_data = validated_model.model_dump()
            except Exception as e:
                validation_errors.append(f"Bank statement schema validation error: {e}")
                final_data = merged

            # Mathematical check on opening balance, transactions and closing balance
            op_bal = final_data.get("opening_balance")
            cl_bal = final_data.get("closing_balance")
            txs = final_data.get("transactions") or []
            if op_bal is not None and cl_bal is not None and txs:
                tot_debit = sum(t.get("debit", 0.0) or 0.0 for t in txs)
                tot_credit = sum(t.get("credit", 0.0) or 0.0 for t in txs)
                calculated = round(op_bal - tot_debit + tot_credit, 2)
                if abs(calculated - round(cl_bal, 2)) > 0.10:
                    review_reasons.append(
                        f"Ledger discrepancy: Opening balance ({op_bal:.2f}) - Debits ({tot_debit:.2f}) + Credits ({tot_credit:.2f}) = {calculated:.2f}, differs from Closing balance ({cl_bal:.2f})."
                    )

        else:  # EXPENSE_REPORT
            merged = {}
            for field in ["expense_date", "merchant", "category", "amount", "currency", "description", "expenses"]:
                llm_val = llm_data.get(field)
                det_val = det_dict.get(field)
                val = llm_val if llm_val is not None else det_val
                merged[field] = val

                raw = str(val) if val is not None else None
                source_pg = find_source_page(raw, page_texts) if val is not None else None
                field_meta[field] = FieldMetadata(
                    value=val,
                    raw_value=raw,
                    source_page=source_pg,
                    extraction_method=ExtractionMethod.LLM.value if llm_val is not None else ExtractionMethod.DETERMINISTIC_FALLBACK.value,
                    confidence=0.88 if val is not None else 0.0,
                )

            try:
                validated_model = ExpenseReportData.model_validate(merged)
                final_data = validated_model.model_dump()
            except Exception as e:
                validation_errors.append(f"Expense report schema validation error: {e}")
                final_data = merged

            if final_data.get("amount") is None:
                review_reasons.append("Expense report amount is missing.")

        return final_data, field_meta, review_reasons, validation_errors

    async def get_extraction(self, doc_id: str, org_id: str) -> Optional[DocumentExtraction]:
        """Fetches the latest structured extraction for a document."""
        query = (
            select(DocumentExtraction)
            .where(
                DocumentExtraction.document_id == doc_id,
                DocumentExtraction.organization_id == org_id,
            )
            .order_by(desc(DocumentExtraction.created_at))
            .limit(1)
        )
        res = await self.db.execute(query)
        return res.scalar_one_or_none()

    async def update_extraction(
        self,
        doc_id: str,
        org_id: str,
        payload: DocumentExtractionUpdate,
        analyst_user: User,
    ) -> DocumentExtraction:
        """
        Saves analyst corrections and human-in-the-loop approvals.
        Marks fields with MANUAL extraction method and sets review timestamps.
        """
        extraction = await self.get_extraction(doc_id, org_id)
        if not extraction:
            raise NotFoundError("DocumentExtraction for document", doc_id)

        # Merge edited fields
        current_data = dict(extraction.extracted_data)
        current_data.update(payload.extracted_data)
        extraction.extracted_data = current_data

        # Update field metadata for modified fields to mark as MANUAL
        current_meta = dict(extraction.field_metadata)
        for k, v in payload.extracted_data.items():
            if k in current_meta:
                meta_item = dict(current_meta[k])
                meta_item["value"] = v
                meta_item["extraction_method"] = ExtractionMethod.MANUAL.value
                meta_item["confidence"] = 1.0  # Analyst confirmed
                current_meta[k] = meta_item
        extraction.field_metadata = current_meta

        # Status update
        if payload.status:
            extraction.status = payload.status
            if payload.status == ExtractionStatus.APPROVED.value:
                extraction.needs_review = False
                extraction.confidence_score = 1.0
                # Update parent document status
                doc_query = select(Document).where(Document.id == doc_id)
                doc_res = await self.db.execute(doc_query)
                doc = doc_res.scalar_one_or_none()
                if doc:
                    doc.status = DocumentStatus.APPROVED.value
            elif payload.status == ExtractionStatus.REJECTED.value:
                extraction.needs_review = False
                doc_query = select(Document).where(Document.id == doc_id)
                doc_res = await self.db.execute(doc_query)
                doc = doc_res.scalar_one_or_none()
                if doc:
                    doc.status = DocumentStatus.REJECTED.value

        if payload.analyst_notes:
            extraction.analyst_notes = payload.analyst_notes

        extraction.reviewed_by_id = analyst_user.id
        extraction.reviewed_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(extraction)
        return extraction

    async def get_review_queue(
        self,
        org_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReviewQueueItem], int]:
        """
        Queries documents requiring analyst verification, ordered by lowest confidence first.
        """
        offset = (page - 1) * page_size
        query = (
            select(DocumentExtraction, Document)
            .join(Document, DocumentExtraction.document_id == Document.id)
            .where(
                DocumentExtraction.organization_id == org_id,
                DocumentExtraction.needs_review.is_(True),
            )
            .order_by(DocumentExtraction.confidence_score.asc())
            .offset(offset)
            .limit(page_size)
        )

        count_query = (
            select(func.count(DocumentExtraction.id))
            .where(
                DocumentExtraction.organization_id == org_id,
                DocumentExtraction.needs_review.is_(True),
            )
        )

        res = await self.db.execute(query)
        rows = res.all()

        count_res = await self.db.execute(count_query)
        total = count_res.scalar_one() or 0

        items: List[ReviewQueueItem] = []
        for ext, doc in rows:
            data = ext.extracted_data or {}
            total_amt = data.get("total") or data.get("amount") or data.get("closing_balance")
            curr = data.get("currency")
            items.append(
                ReviewQueueItem(
                    extraction_id=ext.id,
                    document_id=doc.id,
                    document_title=doc.title,
                    document_type=ext.document_type,
                    filename=doc.filename,
                    status=ext.status,
                    confidence_score=ext.confidence_score,
                    review_reasons=ext.review_reasons or [],
                    created_at=ext.created_at,
                    total_amount=total_amt,
                    currency=curr,
                )
            )

        return items, total
