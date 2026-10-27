import { LivenessData, ReadinessData } from '../types/health';
import {
  LoginPayload,
  RegisterPayload,
  TokenResponse,
  UserMeResponse,
} from '../types/auth';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;

  constructor(message: string, status: number, details?: unknown, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
    this.code = code;
  }
}

function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|;\\s*)(' + name + ')=([^;]*)'));
  return match ? decodeURIComponent(match[3]) : null;
}

// Global hook for unauthorized / session expiration notifications
let onUnauthorizedCallback: (() => void) | null = null;

export function setOnUnauthorizedHandler(handler: () => void) {
  onUnauthorizedCallback = handler;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const csrfToken = getCookie('docufin_csrf_token');
  const activeOrgId = typeof localStorage !== 'undefined' ? localStorage.getItem('docufin_active_org_id') : null;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
    ...(activeOrgId ? { 'X-Organization-Id': activeOrgId } : {}),
    ...(options.headers as Record<string, string> || {}),
  };

  try {
    const response = await fetch(url, {
      ...options,
      credentials: 'include', // Essential for sending and receiving HttpOnly cookies
      headers,
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      if (response.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/register')) {
        if (onUnauthorizedCallback) {
          onUnauthorizedCallback();
        }
      }

      const errorMessage =
        data?.error?.message ||
        data?.message ||
        `HTTP ${response.status}: ${response.statusText}`;
      const errorCode = data?.error?.code;
      throw new ApiError(errorMessage, response.status, data, errorCode);
    }

    return data as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      error instanceof Error ? error.message : 'Network request failed',
      0
    );
  }
}

export const apiClient = {
  get: <T>(endpoint: string, headers?: Record<string, string>) =>
    request<T>(endpoint, { method: 'GET', headers }),

  post: <T>(endpoint: string, body?: unknown, headers?: Record<string, string>) =>
    request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
      headers,
    }),

  patch: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(endpoint: string) =>
    request<T>(endpoint, { method: 'DELETE' }),

  // Auth endpoints
  login: (payload: LoginPayload) =>
    request<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  register: (payload: RegisterPayload) =>
    request<TokenResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getMe: () => request<UserMeResponse>('/api/v1/auth/me'),

  logout: () =>
    request<{ message: string; success: boolean }>('/api/v1/auth/logout', {
      method: 'POST',
    }),

  // Health and service diagnostics
  getLiveHealth: () => request<LivenessData>('/health/live'),
  getReadyHealth: () => request<ReadinessData>('/health/ready'),

  // Document management endpoints
  getDocuments: (params?: import('../types/document').DocumentFilterParams) => {
    const query = new URLSearchParams();
    if (params?.search) query.set('search', params.search);
    if (params?.status) query.set('status', params.status);
    if (params?.doc_type) query.set('doc_type', params.doc_type);
    if (params?.sort_by) query.set('sort_by', params.sort_by);
    if (params?.sort_order) query.set('sort_order', params.sort_order);
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    const qs = query.toString();
    return request<import('../types/document').PaginatedDocumentResponse>(
      `/api/v1/documents${qs ? `?${qs}` : ''}`
    );
  },

  getDocument: (id: string) =>
    request<import('../types/document').DocumentItem>(`/api/v1/documents/${id}`),

  uploadDocument: (formData: FormData, onProgress?: (percent: number) => void) => {
    return new Promise<import('../types/document').DocumentItem>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const url = `${BASE_URL}/api/v1/documents/upload`;
      xhr.open('POST', url);
      xhr.withCredentials = true;

      const csrfToken = getCookie('docufin_csrf_token');
      if (csrfToken) {
        xhr.setRequestHeader('X-CSRF-Token', csrfToken);
      }
      const activeOrgId =
        typeof localStorage !== 'undefined'
          ? localStorage.getItem('docufin_active_org_id')
          : null;
      if (activeOrgId) {
        xhr.setRequestHeader('X-Organization-Id', activeOrgId);
      }

      if (onProgress && xhr.upload) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percentComplete = Math.round((event.loaded / event.total) * 100);
            onProgress(percentComplete);
          }
        };
      }

      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(data);
          } else {
            const errorMsg =
              data?.error?.message || data?.message || `Upload failed with status ${xhr.status}`;
            reject(new ApiError(errorMsg, xhr.status, data, data?.error?.code));
          }
        } catch {
          reject(new ApiError(`Upload failed with status ${xhr.status}`, xhr.status));
        }
      };

      xhr.onerror = () => {
        reject(new ApiError('Network error during upload', 0));
      };

      xhr.send(formData);
    });
  },

  deleteDocument: (id: string) =>
    request<{ message: string }>(`/api/v1/documents/${id}`, { method: 'DELETE' }),

  getDocumentPreviewUrl: (id: string) => `${BASE_URL}/api/v1/documents/${id}/preview`,
  getDocumentDownloadUrl: (id: string) => `${BASE_URL}/api/v1/documents/${id}/download`,

  // Phase 4: Async Processing, OCR, and Status Polling
  processDocument: (id: string, forceReprocess = false, idempotencyKey?: string) =>
    request<import('../types/document').ProcessingJob>(`/api/v1/documents/${id}/process`, {
      method: 'POST',
      body: JSON.stringify({
        force_reprocess: forceReprocess,
        idempotency_key: idempotencyKey,
      }),
    }),

  retryDocument: (id: string) =>
    request<import('../types/document').ProcessingJob>(`/api/v1/documents/${id}/retry`, {
      method: 'POST',
    }),

  getProcessingJobs: (docId: string) =>
    request<import('../types/document').ProcessingJob[]>(
      `/api/v1/documents/${docId}/processing-jobs`
    ),

  getProcessingJobStatus: (docId: string, jobId: string) =>
    request<import('../types/document').ProcessingJob>(
      `/api/v1/documents/${docId}/processing-jobs/${jobId}`
    ),

  getDocumentExtractedText: (docId: string) =>
    request<import('../types/document').DocumentExtractedTextResponse>(
      `/api/v1/documents/${docId}/extracted-text`
    ),

  // Phase 5: Structured Financial Extraction & Review Queue
  extractDocument: (docId: string, forceReextract = false, docType?: string) =>
    request<import('../types/extraction').DocumentExtractionResponse>(
      `/api/v1/documents/${docId}/extract`,
      {
        method: 'POST',
        body: JSON.stringify({
          force_reextract: forceReextract,
          document_type: docType || undefined,
        }),
      }
    ),

  getDocumentExtraction: (docId: string) =>
    request<import('../types/extraction').DocumentExtractionResponse>(
      `/api/v1/documents/${docId}/extraction`
    ),

  updateDocumentExtraction: (
    docId: string,
    payload: import('../types/extraction').DocumentExtractionUpdate
  ) =>
    request<import('../types/extraction').DocumentExtractionResponse>(
      `/api/v1/documents/${docId}/extraction`,
      {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }
    ),

  getReviewQueue: (page = 1, pageSize = 20) =>
    request<import('../types/extraction').ReviewQueueItem[]>(
      `/api/v1/documents/review-queue?page=${page}&page_size=${pageSize}`
    ),

  classifyDocument: (docId: string) =>
    request<{ document_type: string; confidence: number; signals: string[]; method: string }>(
      `/api/v1/documents/${docId}/classify`,
      {
        method: 'POST',
      }
    ),
};
