export type DocumentStatus =
  | 'UPLOADED'
  | 'QUEUED'
  | 'PROCESSING'
  | 'REVIEW_REQUIRED'
  | 'APPROVED'
  | 'REJECTED'
  | 'FAILED';

export type DocumentType =
  | '10-K'
  | '10-Q'
  | 'INVOICE'
  | 'EARNINGS_CALL'
  | 'BALANCE_SHEET'
  | 'OTHER';

export interface UploaderBrief {
  id: string;
  email: string;
  full_name: string;
}

export interface DocumentItem {
  id: string;
  organization_id?: string;
  title: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string;
  file_extension: string;
  checksum_sha256: string;
  status: DocumentStatus;
  doc_type?: string | null;
  uploader_id?: string | null;
  uploader?: UploaderBrief | null;
  extra_metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedDocumentResponse {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DocumentFilterParams {
  search?: string;
  status?: string;
  doc_type?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

export type JobStatus =
  | 'PENDING'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'FAILED'
  | 'RETRYING'
  | 'CANCELLED';

export interface ProcessingJob {
  id: string;
  document_id: string;
  organization_id: string;
  status: JobStatus;
  stage: string;
  attempts: number;
  max_attempts: number;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  error_message?: string | null;
  celery_task_id?: string | null;
  idempotency_key?: string | null;
  extra_metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentPageItem {
  id: string;
  document_id: string;
  page_number: number;
  text_content: string;
  word_count: number;
  char_count: number;
  is_scanned: boolean;
  has_images: boolean;
  ocr_applied: boolean;
  ocr_confidence?: number | null;
  extra_metadata?: Record<string, unknown> | null;
}

export interface DocumentExtractedTextResponse {
  document_id: string;
  total_pages: number;
  total_words: number;
  total_chars: number;
  ocr_applied: boolean;
  pages: DocumentPageItem[];
}
