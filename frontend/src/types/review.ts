export type ReviewTaskStatus = 'PENDING' | 'IN_REVIEW' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
export type ReviewTaskPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface ReviewTaskQueueItem {
  id: string;
  document_id: string;
  document_title: string;
  document_filename: string;
  document_type?: string | null;
  extraction_id?: string | null;
  status: ReviewTaskStatus;
  priority: ReviewTaskPriority;
  version: number;
  assigned_to_id?: string | null;
  assigned_to_name?: string | null;
  assigned_to_email?: string | null;
  review_reasons: string[];
  validation_error_count: number;
  confidence_score: number;
  due_date?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedReviewQueueResponse {
  items: ReviewTaskQueueItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ReviewHistoryItem {
  id: string;
  review_task_id: string;
  document_id: string;
  user_id?: string | null;
  user_email?: string | null;
  user_role?: string | null;
  action: string;
  previous_status?: string | null;
  new_status?: string | null;
  field_changes: Record<string, { old_value: unknown; new_value: unknown }>;
  notes?: string | null;
  created_at: string;
}

export interface ReviewTaskDetailResponse {
  id: string;
  document_id: string;
  extraction_id?: string | null;
  organization_id: string;
  status: ReviewTaskStatus;
  priority: ReviewTaskPriority;
  assigned_to_id?: string | null;
  assigned_to_name?: string | null;
  assigned_to_email?: string | null;
  version: number;
  due_date?: string | null;
  completed_at?: string | null;
  review_reasons: string[];
  validation_error_count: number;
  resolution_notes?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  updated_at: string;
  document_title?: string | null;
  document_filename?: string | null;
  document_type?: string | null;
  uploader_id?: string | null;
  extracted_data?: Record<string, any> | null;
  field_metadata?: Record<string, any> | null;
  validation_errors?: Array<Record<string, any>> | null;
  histories: ReviewHistoryItem[];
}

export interface AssignReviewTaskPayload {
  assigned_to_id: string | null;
}

export interface CorrectFieldsPayload {
  field_updates: Record<string, any>;
  notes?: string;
  expected_version: number;
}

export interface ApproveReviewTaskPayload {
  notes?: string;
  expected_version: number;
}

export interface RejectReviewTaskPayload {
  rejection_reason: string;
  expected_version: number;
}

export interface ReviewFilterParams {
  status?: string;
  document_type?: string;
  assigned_to_id?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  page?: number;
  page_size?: number;
}
