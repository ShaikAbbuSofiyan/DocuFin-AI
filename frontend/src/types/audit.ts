export interface AuditLogItem {
  id: string;
  organization_id?: string | null;
  user_id?: string | null;
  user_email?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  status: string;
  details?: Record<string, any> | null;
  created_at: string;
}

export interface PaginatedAuditLogResponse {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AuditLogFilterParams {
  action?: string;
  resource_type?: string;
  resource_id?: string;
  user_id?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  page?: number;
  page_size?: number;
}
