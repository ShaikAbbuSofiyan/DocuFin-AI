# DocuFin Workers Module

## Scope & Architectural Role
This module encapsulates asynchronous and distributed background task processing for DocuFin AI.

### Planned Submodules (Phase 2+)
- `celery_app.py` / `tasks.py`: Worker process definitions using Redis as broker and result backend.
- `document_tasks.py`: Long-running OCR, PDF rasterization, table parsing, and financial data normalization.
- `indexing_tasks.py`: Async batch embedding calculation and vector database upserting.
- `export_tasks.py`: Excel, CSV, and audit report generation.
