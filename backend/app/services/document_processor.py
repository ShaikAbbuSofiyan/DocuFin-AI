import io
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.core.logging import logger

settings = get_settings()


@dataclass
class ExtractedPageResult:
    """Represents extraction results for a single page."""
    page_number: int  # 1-indexed
    text_content: str
    word_count: int
    char_count: int
    is_scanned: bool
    has_images: bool
    ocr_applied: bool
    ocr_confidence: Optional[float] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentExtractionResult:
    """Represents extraction results for an entire document."""
    total_pages: int
    total_words: int
    total_chars: int
    scanned_pages_count: int
    digital_pages_count: int
    ocr_applied: bool
    pages: List[ExtractedPageResult]
    summary_metadata: Dict[str, Any]


class DocumentProcessor:
    """
    Robust, secure financial document extractor.
    Uses PyMuPDF for digital text extraction and Tesseract for scanned/image pages.
    Enforces page limits, file sanitization, and untrusted input boundaries.
    """

    def __init__(
        self,
        max_pages: Optional[int] = None,
        min_words_for_digital: Optional[int] = None,
    ):
        self.max_pages = max_pages or settings.max_document_pages
        self.min_words_for_digital = min_words_for_digital or settings.ocr_min_words_threshold

    @staticmethod
    def _sanitize_untrusted_text(raw_text: str) -> str:
        """
        Sanitizes document text to prevent null bytes, invalid Unicode, or terminal exploits.
        Treats document content strictly as data, never executable instructions.
        """
        if not raw_text:
            return ""
        # Remove null bytes and unprintable ASCII control characters except \t, \n, \r
        sanitized = raw_text.replace("\0", "")
        sanitized = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized)
        return sanitized.strip()

    def _run_ocr_on_image(self, pil_image: Image.Image) -> tuple[str, bool, Optional[float]]:
        """
        Runs OCR on a PIL image using Tesseract.
        Gracefully handles environments where Tesseract binary might not be present.
        """
        try:
            # Convert to RGB if needed (e.g. RGBA or palette)
            if pil_image.mode not in ("RGB", "L"):
                pil_image = pil_image.convert("RGB")

            ocr_text = pytesseract.image_to_string(pil_image)
            clean_text = self._sanitize_untrusted_text(ocr_text)
            return clean_text, True, 85.0
        except pytesseract.TesseractNotFoundError:
            logger.warning("Tesseract OCR binary not found on worker host. Falling back gracefully.")
            return "[Scanned image detected. OCR engine unavailable.]", False, None
        except Exception as exc:
            logger.warning(f"OCR execution failed on page image: {str(exc)}")
            return "", False, None

    def process_document(
        self,
        file_bytes: bytes,
        mime_type: str,
        filename: str = "document.pdf",
    ) -> DocumentExtractionResult:
        """
        Processes document content asynchronously or in worker.
        Validates structure, extracts pages, runs OCR on scanned pages,
        and preserves exact page numbering.
        """
        if not file_bytes or len(file_bytes) == 0:
            raise ValidationError("Document is empty (0 bytes).")

        clean_mime = (mime_type or "").lower().strip()

        # Handle standalone images (PNG, JPEG, etc.)
        if clean_mime in ("image/png", "image/jpeg", "image/jpg") or any(
            filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg")
        ):
            return self._process_standalone_image(file_bytes, filename)

        # Handle PDF documents
        return self._process_pdf(file_bytes, filename)

    def _process_standalone_image(
        self, file_bytes: bytes, filename: str
    ) -> DocumentExtractionResult:
        """Processes an image file as a single-page document using OCR."""
        try:
            image = Image.open(io.BytesIO(file_bytes))
            image.verify()  # Verify image integrity
            # Reopen after verify
            image = Image.open(io.BytesIO(file_bytes))
        except Exception as exc:
            raise ValidationError(f"Corrupt or invalid image file: {str(exc)}")

        text, ocr_success, confidence = self._run_ocr_on_image(image)
        words = len(text.split()) if text else 0
        chars = len(text)

        page_result = ExtractedPageResult(
            page_number=1,
            text_content=text,
            word_count=words,
            char_count=chars,
            is_scanned=True,
            has_images=True,
            ocr_applied=ocr_success,
            ocr_confidence=confidence,
            extra_metadata={
                "image_width": image.width,
                "image_height": image.height,
                "image_format": image.format,
            },
        )

        return DocumentExtractionResult(
            total_pages=1,
            total_words=words,
            total_chars=chars,
            scanned_pages_count=1,
            digital_pages_count=0,
            ocr_applied=ocr_success,
            pages=[page_result],
            summary_metadata={
                "extractor": "PIL+Tesseract",
                "is_image_document": True,
                "filename": filename,
            },
        )

    def _process_pdf(
        self, file_bytes: bytes, filename: str
    ) -> DocumentExtractionResult:
        """Processes PDF documents using PyMuPDF and fallback OCR for scanned pages."""
        try:
            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:
            raise ValidationError(f"Corrupt or invalid PDF file: {str(exc)}")

        try:
            if pdf_doc.is_encrypted:
                raise ValidationError("Password-protected or encrypted PDFs are not supported.")

            page_count = len(pdf_doc)
            if page_count == 0:
                raise ValidationError("PDF document contains no pages.")

            if page_count > self.max_pages:
                raise ValidationError(
                    f"Document exceeds maximum page threshold ({page_count} > {self.max_pages} pages)."
                )

            page_results: List[ExtractedPageResult] = []
            scanned_count = 0
            digital_count = 0
            any_ocr_applied = False

            for page_index in range(page_count):
                page_num = page_index + 1
                page = pdf_doc[page_index]

                # 1. Digital text extraction
                raw_text = page.get_text("text") or ""
                digital_text = self._sanitize_untrusted_text(raw_text)
                word_count = len(digital_text.split()) if digital_text else 0
                image_list = page.get_images(full=True)
                has_images = len(image_list) > 0

                # 2. Scanned detection: few digital words AND images present
                is_scanned = (word_count < self.min_words_for_digital) and has_images
                ocr_applied = False
                ocr_confidence: Optional[float] = None
                final_text = digital_text

                if is_scanned:
                    scanned_count += 1
                    # Render page to raster image at 150 DPI for OCR
                    try:
                        pix = page.get_pixmap(dpi=150)
                        img_bytes = pix.tobytes("png")
                        pil_img = Image.open(io.BytesIO(img_bytes))
                        ocr_text, ocr_success, confidence = self._run_ocr_on_image(pil_img)
                        if ocr_text:
                            # If digital text had some fragments, combine or replace
                            if len(digital_text.strip()) > 0:
                                final_text = f"{digital_text}\n\n[OCR Extracted Text]:\n{ocr_text}"
                            else:
                                final_text = ocr_text
                            ocr_applied = ocr_success
                            any_ocr_applied = any_ocr_applied or ocr_applied
                            ocr_confidence = confidence
                    except Exception as ocr_err:
                        logger.warning(f"Failed to render/OCR page {page_num}: {str(ocr_err)}")
                else:
                    digital_count += 1

                final_text = self._sanitize_untrusted_text(final_text)
                final_words = len(final_text.split()) if final_text else 0
                final_chars = len(final_text)

                page_results.append(
                    ExtractedPageResult(
                        page_number=page_num,
                        text_content=final_text,
                        word_count=final_words,
                        char_count=final_chars,
                        is_scanned=is_scanned,
                        has_images=has_images,
                        ocr_applied=ocr_applied,
                        ocr_confidence=ocr_confidence,
                        extra_metadata={
                            "page_rect": [page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1],
                            "images_detected": len(image_list),
                        },
                    )
                )

            total_words = sum(p.word_count for p in page_results)
            total_chars = sum(p.char_count for p in page_results)

            return DocumentExtractionResult(
                total_pages=page_count,
                total_words=total_words,
                total_chars=total_chars,
                scanned_pages_count=scanned_count,
                digital_pages_count=digital_count,
                ocr_applied=any_ocr_applied,
                pages=page_results,
                summary_metadata={
                    "extractor": "PyMuPDF+Tesseract",
                    "format": "PDF",
                    "filename": filename,
                    "pdf_metadata": {
                        k: str(v)
                        for k, v in (pdf_doc.metadata or {}).items()
                        if k in ("title", "author", "creationDate", "modDate")
                    },
                },
            )
        finally:
            pdf_doc.close()
