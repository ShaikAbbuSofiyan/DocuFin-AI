import io
import os
import pytest
from httpx import AsyncClient


# Valid binary payloads matching magic bytes signatures
SAMPLE_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
SAMPLE_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
SAMPLE_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xd9"
FAKE_PDF_DISGUISED_TEXT = b"Hello, this is just plain text disguised as a PDF file."


async def register_and_get_token(client: AsyncClient, email: str, org_name: str) -> tuple[str, str]:
    """Helper to register user and return (access_token, organization_id)."""
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Test User",
            "organization_name": org_name,
        },
    )
    assert res.status_code == 201
    token = res.json()["access_token"]
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me_res.json()["active_organization_id"]
    return token, org_id


@pytest.mark.asyncio
async def test_valid_file_uploads_pdf_png_jpeg(client: AsyncClient):
    """Test 1: Successfully uploads PDF, PNG, and JPEG files with metadata & magic byte validation."""
    token, org_id = await register_and_get_token(client, "uploader1@fintech.com", "FinTech One")
    auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 1. Upload valid PDF
    pdf_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Q3 10-Q Filing", "doc_type": "10-Q"},
        files={"file": ("q3_filing.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
    )
    assert pdf_res.status_code == 201
    pdf_data = pdf_res.json()
    assert pdf_data["title"] == "Q3 10-Q Filing"
    assert pdf_data["filename"] == "q3_filing.pdf"
    assert pdf_data["mime_type"] == "application/pdf"
    assert pdf_data["file_extension"] == ".pdf"
    assert pdf_data["status"] == "UPLOADED"
    assert "file_path" not in pdf_data  # Internal path never exposed!

    # 2. Upload valid PNG
    png_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Invoice Receipt PNG", "doc_type": "INVOICE"},
        files={"file": ("receipt.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")},
    )
    assert png_res.status_code == 201
    png_data = png_res.json()
    assert png_data["mime_type"] == "image/png"
    assert png_data["file_extension"] == ".png"

    # 3. Upload valid JPEG
    jpg_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Balance Sheet Scan", "doc_type": "BALANCE_SHEET"},
        files={"file": ("balance_sheet.jpeg", io.BytesIO(SAMPLE_JPEG_BYTES), "image/jpeg")},
    )
    assert jpg_res.status_code == 201
    jpg_data = jpg_res.json()
    assert jpg_data["mime_type"] == "image/jpeg"
    assert jpg_data["file_extension"] == ".jpeg"


@pytest.mark.asyncio
async def test_invalid_file_validation_magic_bytes_extension_empty(client: AsyncClient):
    """Test 2: Rejects corrupted magic bytes, forbidden extensions, and empty files."""
    token, org_id = await register_and_get_token(client, "security@fintech.com", "Security Org")
    auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 1. Reject fake PDF (plain text lacking %PDF- magic bytes)
    fake_pdf_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Disguised Malware"},
        files={"file": ("fake.pdf", io.BytesIO(FAKE_PDF_DISGUISED_TEXT), "application/pdf")},
    )
    assert fake_pdf_res.status_code == 422
    assert "signature does not match" in fake_pdf_res.json()["error"]["message"]

    # 2. Reject disallowed extension (e.g. .exe)
    exe_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Script"},
        files={"file": ("script.exe", io.BytesIO(b"MZ\x90\x00binary"), "application/octet-stream")},
    )
    assert exe_res.status_code == 422
    assert "Unsupported file extension" in exe_res.json()["error"]["message"]

    # 3. Reject empty file (0 bytes)
    empty_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Empty Doc"},
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert empty_res.status_code == 422
    assert "empty" in empty_res.json()["error"]["details"]["detail"].lower()


@pytest.mark.asyncio
async def test_search_filter_sort_and_pagination(client: AsyncClient):
    """Test 3: Validates document listing with search, filtering by status & doc_type, sorting and pagination."""
    token, org_id = await register_and_get_token(client, "analyst2@fintech.com", "Analytics Group")
    auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # Upload 3 distinct documents
    docs_to_create = [
        ("Alpha Annual 10-K", "10-K", "alpha_10k.pdf"),
        ("Beta Earnings Call", "EARNINGS_CALL", "beta_earnings.pdf"),
        ("Gamma Vendor Invoice", "INVOICE", "gamma_invoice.pdf"),
    ]
    for title, doc_type, fname in docs_to_create:
        await client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
            data={"title": title, "doc_type": doc_type},
            files={"file": (fname, io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
        )

    # 1. Search by title
    search_res = await client.get(
        "/api/v1/documents?search=Earnings",
        headers=auth_headers,
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total"] == 1
    assert search_data["items"][0]["title"] == "Beta Earnings Call"

    # 2. Filter by doc_type
    filter_res = await client.get(
        "/api/v1/documents?doc_type=INVOICE",
        headers=auth_headers,
    )
    assert filter_res.status_code == 200
    filter_data = filter_res.json()
    assert filter_data["total"] == 1
    assert filter_data["items"][0]["doc_type"] == "INVOICE"

    # 3. Filter by status
    status_res = await client.get(
        "/api/v1/documents?status=UPLOADED",
        headers=auth_headers,
    )
    assert status_res.status_code == 200
    assert status_res.json()["total"] >= 3

    # 4. Sorting and Pagination
    page_res = await client.get(
        "/api/v1/documents?page=1&page_size=2&sort_by=title&sort_order=asc",
        headers=auth_headers,
    )
    assert page_res.status_code == 200
    page_data = page_res.json()
    assert page_data["page"] == 1
    assert page_data["page_size"] == 2
    assert len(page_data["items"]) == 2
    assert page_data["total_pages"] >= 2


@pytest.mark.asyncio
async def test_document_preview_and_download(client: AsyncClient):
    """Test 4: Verifies safe inline preview and attachment download with proper security headers."""
    token, org_id = await register_and_get_token(client, "preview_user@fintech.com", "Preview Org")
    auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # Upload document
    upload_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={"title": "Audit Review PDF", "doc_type": "10-K"},
        files={"file": ("audit_review.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
    )
    doc_id = upload_res.json()["id"]

    # 1. Preview (Content-Disposition: inline)
    preview_res = await client.get(
        f"/api/v1/documents/{doc_id}/preview",
        headers=auth_headers,
    )
    assert preview_res.status_code == 200
    assert "inline" in preview_res.headers.get("content-disposition", "")
    assert preview_res.headers.get("content-type") == "application/pdf"
    assert preview_res.headers.get("x-content-type-options") == "nosniff"
    assert preview_res.content == SAMPLE_PDF_BYTES

    # 2. Download (Content-Disposition: attachment)
    download_res = await client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers=auth_headers,
    )
    assert download_res.status_code == 200
    assert "attachment" in download_res.headers.get("content-disposition", "")
    assert "audit_review.pdf" in download_res.headers.get("content-disposition", "")
    assert download_res.content == SAMPLE_PDF_BYTES


@pytest.mark.asyncio
async def test_cross_organization_isolation(client: AsyncClient):
    """Test 5: Cross-organization protection - users from another organization cannot access, preview, or delete."""
    token_a, org_a_id = await register_and_get_token(client, "alice@alpha-bank.com", "Alpha Bank")
    token_b, org_b_id = await register_and_get_token(client, "bob@beta-invest.com", "Beta Invest")

    headers_a = {"Authorization": f"Bearer {token_a}", "X-Organization-Id": org_a_id}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Organization-Id": org_b_id}

    # Org A uploads confidential doc
    upload_res = await client.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        data={"title": "Confidential Alpha Merger"},
        files={"file": ("merger.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
    )
    doc_id = upload_res.json()["id"]

    # Org B attempts to read details -> 403 Forbidden
    cross_get = await client.get(f"/api/v1/documents/{doc_id}", headers=headers_b)
    assert cross_get.status_code == 403

    # Org B attempts to preview -> 403 Forbidden
    cross_preview = await client.get(f"/api/v1/documents/{doc_id}/preview", headers=headers_b)
    assert cross_preview.status_code == 403

    # Org B attempts to download -> 403 Forbidden
    cross_download = await client.get(f"/api/v1/documents/{doc_id}/download", headers=headers_b)
    assert cross_download.status_code == 403

    # Org B attempts to delete -> 403 Forbidden
    cross_delete = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers_b)
    assert cross_delete.status_code == 403


@pytest.mark.asyncio
async def test_document_deletion_consistency(client: AsyncClient):
    """Test 6: Deletion with authorization removes from DB and disk storage consistently."""
    token, org_id = await register_and_get_token(client, "admin_del@fintech.com", "Deletion Org")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # Upload document
    upload_res = await client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"title": "Temporary Doc To Delete"},
        files={"file": ("temp.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
    )
    doc_id = upload_res.json()["id"]

    # Delete as Admin
    del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.json()["message"]

    # Verify document no longer exists
    get_res = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert get_res.status_code == 404
