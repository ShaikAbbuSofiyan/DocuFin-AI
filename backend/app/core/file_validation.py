import hashlib
import os
import re
from typing import Tuple
from app.core.config import get_settings
from app.core.exceptions import ValidationError

# Magic byte signatures for authorized file types
MAGIC_SIGNATURES = {
    ".pdf": [b"%PDF-"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
}

MIME_MAPPING = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes raw client-supplied filename to prevent path traversal or filesystem exploits.
    Strips directory separators and normalizes characters.
    """
    if not filename:
        return "unnamed_document"
    # Extract only the base name (strip directory traversal attempts)
    clean_name = os.path.basename(filename).strip()
    # Replace dangerous or control characters with underscore, preserve dots and dashes
    clean_name = re.sub(r"[^\w.\- ]", "_", clean_name)
    clean_name = re.sub(r"\s+", " ", clean_name).strip()
    return clean_name or "unnamed_document"


def validate_file_content(
    filename: str,
    content_type: str,
    content: bytes,
) -> Tuple[str, str, str, str]:
    """
    Validates file metadata, size, MIME type, and magic bytes header.

    Returns:
        (sanitized_filename, extension, detected_mime_type, sha256_checksum)

    Raises:
        ValidationError: If validation fails on size, extension, MIME type, or magic bytes.
    """
    settings = get_settings()

    # 1. Size validation
    file_size = len(content)
    if file_size == 0:
        raise ValidationError("File validation failed", {"detail": "Uploaded file is empty (0 bytes)."})

    if file_size > settings.max_upload_size_bytes:
        raise ValidationError(
            f"File exceeds maximum upload size of {settings.max_upload_size_mb}MB.",
            {"max_size_mb": settings.max_upload_size_mb, "actual_size_bytes": file_size},
        )

    # 2. Extension validation
    clean_name = sanitize_filename(filename)
    _, ext = os.path.splitext(clean_name.lower())
    if not ext or ext not in settings.allowed_upload_extensions:
        allowed = ", ".join(settings.allowed_upload_extensions)
        raise ValidationError(
            f"Unsupported file extension '{ext}'. Allowed extensions: {allowed}",
            {"allowed_extensions": settings.allowed_upload_extensions},
        )

    # 3. MIME type validation (normalize and verify against allowed list)
    norm_content_type = (content_type or "").lower().split(";")[0].strip()
    expected_mime = MIME_MAPPING.get(ext)

    # If browser sends generic octet-stream, we accept if magic bytes match, otherwise check MIME
    if norm_content_type and norm_content_type not in settings.allowed_upload_mime_types:
        if norm_content_type != "application/octet-stream":
            raise ValidationError(
                f"Unsupported MIME type '{norm_content_type}'. Allowed types: {', '.join(settings.allowed_upload_mime_types)}",
                {"allowed_mime_types": settings.allowed_upload_mime_types},
            )

    # 4. Magic bytes content inspection
    expected_signatures = MAGIC_SIGNATURES.get(ext, [])
    magic_valid = any(content.startswith(sig) for sig in expected_signatures)

    if not magic_valid:
        raise ValidationError(
            f"File content signature does not match declared extension '{ext}'. The file may be corrupt or disguised.",
            {"extension": ext, "content_type": content_type},
        )

    # 5. Compute SHA-256 checksum
    checksum = hashlib.sha256(content).hexdigest()

    # Use strict verified MIME type
    final_mime = expected_mime or norm_content_type or "application/octet-stream"

    return clean_name, ext, final_mime, checksum
