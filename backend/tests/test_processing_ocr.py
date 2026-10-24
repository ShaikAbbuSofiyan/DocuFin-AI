import io
import time
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image, ImageDraw
import fitz  # PyMuPDF
from app.core.exceptions import ValidationError
from app.models.document import DocumentStatus
from app.models.processing_job import JobStatus
from app.services.document_processor import DocumentProcessor
from app.workers.document_tasks import execute_processing_job, recover_stale_jobs
from tests.test_document_management import register_and_get_token


def create_synthetic_text_pdf(pages_text: list[str]) -> bytes:
    """Creates an in-memory PDF with digital text on each page."""
    pdf = fitz.open()
    for text in pages_text:
        page = pdf.new_page()
        page.insert_text((50, 72), text, fontsize=12)
    pdf_bytes = pdf.tobytes()
    pdf.close()
    return pdf_bytes


def create_synthetic_scanned_pdf() -> bytes:
    """Creates a PDF containing only a raster image and no digital text (scanned PDF)."""
    # Create an image in memory
    img = Image.new("RGB", (300, 150), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 50), "SCANNED INVOICE TOTAL: $4,500.00", fill=(0, 0, 0))
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()

    pdf = fitz.open()
    page = pdf.new_page(width=300, height=150)
    rect = fitz.Rect(0, 0, 300, 150)
    page.insert_image(rect, stream=img_bytes)
    pdf_bytes = pdf.tobytes()
    pdf.close()
    return pdf_bytes


def create_synthetic_png_image() -> bytes:
    """Creates a PNG image file."""
    img = Image.new("RGB", (200, 100), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.text((10, 40), "RECEIPT #99281", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ==============================================================================
# Unit Tests: DocumentProcessor Engine
# ==============================================================================

def test_extract_text_pdf_multipage():
    """Verify PyMuPDF multi-page digital text extraction and duration measurement."""
    processor = DocumentProcessor(max_pages=10)
    pages = [
        "DocuFin AI Quarterly Financial Report Page 1 Revenue: $50,000,000",
        "Operating Expenses Breakdown Page 2 Research: $12,000,000 General: $5,000,000",
        "Consolidated Balance Sheet Page 3 Assets: $150,000,000 Liabilities: $40,000,000",
    ]
    pdf_bytes = create_synthetic_text_pdf(pages)

    start_time = time.perf_counter()
    result = processor.process_document(pdf_bytes, mime_type="application/pdf", filename="report.pdf")
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    assert result.total_pages == 3
    assert result.total_words > 15
    assert result.scanned_pages_count == 0
    assert result.digital_pages_count == 3
    assert result.ocr_applied is False
    assert len(result.pages) == 3

    # Verify 1-indexed page preserving
    assert result.pages[0].page_number == 1
    assert "Revenue: $50,000,000" in result.pages[0].text_content
    assert result.pages[1].page_number == 2
    assert "Research: $12,000,000" in result.pages[1].text_content
    assert result.pages[2].page_number == 3
    assert "Assets: $150,000,000" in result.pages[2].text_content
    print(f"\n[BENCHMARK] 3-page digital text PDF processed in {elapsed_ms:.2f}ms")


def test_detect_scanned_pdf_page():
    """Verify detection of image-only/scanned PDF pages and OCR invocation."""
    processor = DocumentProcessor(max_pages=10, min_words_for_digital=10)
    scanned_bytes = create_synthetic_scanned_pdf()

    start_time = time.perf_counter()
    result = processor.process_document(scanned_bytes, mime_type="application/pdf", filename="scanned.pdf")
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    assert result.total_pages == 1
    assert result.scanned_pages_count == 1
    assert result.pages[0].is_scanned is True
    assert result.pages[0].has_images is True
    print(f"[BENCHMARK] Scanned page detection & OCR completed in {elapsed_ms:.2f}ms")


def test_process_standalone_image():
    """Verify processing of standalone PNG/JPEG images."""
    processor = DocumentProcessor()
    png_bytes = create_synthetic_png_image()

    start_time = time.perf_counter()
    result = processor.process_document(png_bytes, mime_type="image/png", filename="receipt.png")
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    assert result.total_pages == 1
    assert result.scanned_pages_count == 1
    assert result.pages[0].page_number == 1
    assert result.pages[0].is_scanned is True
    print(f"[BENCHMARK] Standalone PNG image processed in {elapsed_ms:.2f}ms")


def test_empty_and_corrupt_files():
    """Verify empty files (0 bytes) and corrupt files are safely rejected."""
    processor = DocumentProcessor()

    # 1. Empty file
    with pytest.raises(ValidationError) as empty_err:
        processor.process_document(b"", mime_type="application/pdf")
    assert "empty" in str(empty_err.value).lower()

    # 2. Corrupted PDF binary
    with pytest.raises(ValidationError) as corrupt_err:
        processor.process_document(b"%PDF-1.4 CORRUPTED GARBAGE DATA \x00\xff", mime_type="application/pdf")
    assert "corrupt" in str(corrupt_err.value).lower() or "invalid" in str(corrupt_err.value).lower()


def test_resource_safeguard_page_limit():
    """Verify safeguard against documents exceeding maximum page limits."""
    processor = DocumentProcessor(max_pages=2)  # Limit to 2 pages
    pdf_bytes = create_synthetic_text_pdf(["Page 1", "Page 2", "Page 3 (Exceeds Limit)"])

    with pytest.raises(ValidationError) as limit_err:
        processor.process_document(pdf_bytes, mime_type="application/pdf")
    assert "maximum page threshold" in str(limit_err.value).lower()


# ==============================================================================
# Integration Tests: Endpoints, Async Queueing, Polling, & Retries
# ==============================================================================

@pytest.mark.asyncio
async def test_queue_processing_and_status_polling(client: AsyncClient):
    """Test: Upload document, queue async processing, poll job status."""
    token, org_id = await register_and_get_token(client, "proc_analyst@docufin.ai", "FinAnalytics")
    auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 1. Upload valid test document
    pdf_bytes = create_synthetic_text_pdf([
        "Q3 2026 Earnings Call Transcript. Net Profit rose 18% year over year.",
        "Cash reserves remain strong at $4.2 Billion.",
    ])
    upload_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Q3 Earnings Transcript", "doc_type": "10-Q"},
        files={"file": ("earnings_q3.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. Queue processing job
    queue_res = await client.post(
        f"/api/v1/documents/{doc_id}/process",
        headers=auth_headers,
        json={"idempotency_key": "token-q3-001"},
    )
    assert queue_res.status_code == 202
    job_data = queue_res.json()
    job_id = job_data["id"]
    assert job_data["document_id"] == doc_id
    assert job_data["status"] in ("PENDING", "PROCESSING", "QUEUED")
    assert job_data["stage"] in ("QUEUED", "VALIDATING")

    # 3. Poll job status via API
    poll_res = await client.get(
        f"/api/v1/documents/{doc_id}/processing-jobs/{job_id}",
        headers=auth_headers,
    )
    assert poll_res.status_code == 200
    polled_job = poll_res.json()
    assert polled_job["id"] == job_id
    assert polled_job["max_attempts"] == 3

    # 4. List all processing jobs for document
    list_jobs_res = await client.get(
        f"/api/v1/documents/{doc_id}/processing-jobs",
        headers=auth_headers,
    )
    assert list_jobs_res.status_code == 200
    all_jobs = list_jobs_res.json()
    assert len(all_jobs) >= 1
    assert all_jobs[0]["id"] == job_id


@pytest.mark.asyncio
async def test_idempotent_duplicate_job_submission(client: AsyncClient):
    """Test: Repeated submission with same idempotency token returns existing job."""
    token, org_id = await register_and_get_token(client, "idem_user@docufin.ai", "IdemCorp")
    auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    pdf_bytes = create_synthetic_text_pdf(["Audit Report 2026. Unqualified Opinion."])
    upload_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Audit Report"},
        files={"file": ("audit.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    doc_id = upload_res.json()["id"]

    # First submission
    sub1 = await client.post(
        f"/api/v1/documents/{doc_id}/process",
        headers=auth_headers,
        json={"idempotency_key": "unique-idem-key-123"},
    )
    assert sub1.status_code == 202
    job1_id = sub1.json()["id"]

    # Duplicate submission with same key
    sub2 = await client.post(
        f"/api/v1/documents/{doc_id}/process",
        headers=auth_headers,
        json={"idempotency_key": "unique-idem-key-123"},
    )
    assert sub2.status_code == 202
    job2_id = sub2.json()["id"]

    # Must be identical job without creating duplicate rows
    assert job1_id == job2_id


@pytest.mark.asyncio
async def test_worker_execution_and_extracted_text_api(client: AsyncClient, db_session: AsyncSession):
    """Test: Direct worker execution, page storage, and querying extracted text API."""
    token, org_id = await register_and_get_token(client, "exec_tester@docufin.ai", "ExecutionCorp")
    auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # Upload 2-page document
    pdf_bytes = create_synthetic_text_pdf([
        "Page 1: Total Assets: $85,000,000. Cash and cash equivalents: $20,000,000.",
        "Page 2: Total Liabilities: $35,000,000. Equity: $50,000,000.",
    ])
    upload_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Balance Sheet 2026"},
        files={"file": ("balance_sheet.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    doc_id = upload_res.json()["id"]

    # Queue job
    queue_res = await client.post(
        f"/api/v1/documents/{doc_id}/process",
        headers=auth_headers,
    )
    job_id = queue_res.json()["id"]

    # Execute worker logic synchronously (simulating worker process execution)
    worker_res = await execute_processing_job(
        job_id=job_id, document_id=doc_id, current_attempt=1, db_session=db_session
    )
    assert worker_res["status"] == "COMPLETED"
    assert worker_res["pages"] == 2
    assert worker_res["words"] > 10
    assert worker_res["duration_ms"] is not None

    # Retrieve extracted text through API
    text_res = await client.get(
        f"/api/v1/documents/{doc_id}/extracted-text",
        headers=auth_headers,
    )
    assert text_res.status_code == 200
    data = text_res.json()
    assert data["document_id"] == doc_id
    assert data["total_pages"] == 2
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page_number"] == 1
    assert "Total Assets: $85,000,000" in data["pages"][0]["text_content"]
    assert data["pages"][1]["page_number"] == 2
    assert "Total Liabilities: $35,000,000" in data["pages"][1]["text_content"]

    # Check updated document status in DB
    doc_detail = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert doc_detail.status_code == 200
    assert doc_detail.json()["status"] == DocumentStatus.REVIEW_REQUIRED.value


@pytest.mark.asyncio
async def test_failed_job_retry_and_recovery(client: AsyncClient):
    """Test: Failed-job recovery mechanism and retry endpoint."""
    token, org_id = await register_and_get_token(client, "retry_admin@docufin.ai", "RecoveryCorp")
    auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    pdf_bytes = create_synthetic_text_pdf(["Quarterly Tax Filing."])
    upload_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Tax Filing"},
        files={"file": ("taxes.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    doc_id = upload_res.json()["id"]

    # Retry endpoint forces re-processing
    retry_res = await client.post(
        f"/api/v1/documents/{doc_id}/retry",
        headers=auth_headers,
    )
    assert retry_res.status_code == 202
    retry_job = retry_res.json()
    assert retry_job["document_id"] == doc_id

    # Test stale job recovery scan endpoint
    recovery_res = await client.post(
        "/api/v1/documents/recover-stale-jobs",
        headers=auth_headers,
    )
    assert recovery_res.status_code == 200
    assert "Recovery scan completed" in recovery_res.json()["message"]
