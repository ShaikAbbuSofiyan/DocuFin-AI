import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  Download,
  Eye,
  FileText,
  HardDrive,
  Plus,
  RefreshCw,
  Search,
  Shield,
  Trash2,
  Cpu,
} from 'lucide-react';
import { StatusBadge } from '../components/common/StatusBadge';
import { DocumentPreviewModal } from '../components/documents/DocumentPreviewModal';
import { DocumentProcessingModal } from '../components/documents/DocumentProcessingModal';
import { DocumentUploadModal } from '../components/documents/DocumentUploadModal';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../services/api';
import { DocumentFilterParams, DocumentItem } from '../types/document';

export const DocumentsPage: React.FC = () => {
  const { activeOrg, activeRole, user } = useAuth();

  // State
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize] = useState<number>(10);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [docTypeFilter, setDocTypeFilter] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Modals
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [selectedDocument, setSelectedDocument] = useState<DocumentItem | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState<boolean>(false);
  const [selectedProcessingDoc, setSelectedProcessingDoc] = useState<DocumentItem | null>(null);
  const [isProcessingOpen, setIsProcessingOpen] = useState<boolean>(false);

  // Permissions
  const canUpload =
    activeRole?.toLowerCase() === 'admin' ||
    activeRole?.toLowerCase() === 'analyst' ||
    !!user?.is_superuser;

  const canDelete = activeRole?.toLowerCase() === 'admin' || !!user?.is_superuser;

  const fetchDocuments = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const params: DocumentFilterParams = {
        search: search.trim() || undefined,
        status: statusFilter || undefined,
        doc_type: docTypeFilter || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        page: currentPage,
        page_size: pageSize,
      };

      const res = await apiClient.getDocuments(params);
      setDocuments(res.items);
      setTotalCount(res.total);
      setTotalPages(res.total_pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve documents.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [search, statusFilter, docTypeFilter, sortBy, sortOrder, currentPage, pageSize]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleUploadSuccess = (newDoc: DocumentItem) => {
    setSuccessBanner(`Document "${newDoc.title}" uploaded and securely vaulted.`);
    setTimeout(() => setSuccessBanner(null), 4000);
    fetchDocuments();
  };

  const handleDelete = async (docId: string) => {
    await apiClient.deleteDocument(docId);
    setSuccessBanner('Document and binary artifacts purged successfully.');
    setTimeout(() => setSuccessBanner(null), 4000);
    fetchDocuments();
  };

  const openPreview = (doc: DocumentItem) => {
    setSelectedDocument(doc);
    setIsPreviewOpen(true);
  };

  const openProcessing = (doc: DocumentItem) => {
    setSelectedProcessingDoc(doc);
    setIsProcessingOpen(true);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Financial Documents Vault</h1>
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Phase 3
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Secure, encrypted multi-tenant file repository with content-verified ingestion.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchDocuments()}
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition"
            title="Refresh repository"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>

          {canUpload ? (
            <button
              onClick={() => setIsUploadModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-xs rounded-xl transition shadow-lg shadow-emerald-500/10"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              <span>Upload Document</span>
            </button>
          ) : (
            <div
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800/60 border border-slate-700/50 text-slate-400 text-xs"
              title="Reviewers have read-only access. Upload requires Analyst or Admin role."
            >
              <Shield className="w-3.5 h-3.5 text-amber-400" />
              <span>Read-only View ({activeRole || 'Reviewer'})</span>
            </div>
          )}
        </div>
      </div>

      {/* Success & Error Banners */}
      {successBanner && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{successBanner}</span>
          </div>
          <button onClick={() => setSuccessBanner(null)} className="text-emerald-400 hover:text-emerald-200">
            &times;
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => fetchDocuments()} className="underline font-medium hover:text-rose-100">
            Retry
          </button>
        </div>
      )}

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Total Documents</span>
            <FileText className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-xl font-bold text-slate-100 mt-2">{totalCount}</p>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Active Tenant</span>
            <Building2 className="w-4 h-4 text-indigo-400" />
          </div>
          <p className="text-sm font-semibold text-slate-200 mt-2 truncate">
            {activeOrg?.organization_name || 'Default Org'}
          </p>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Storage Enclave</span>
            <HardDrive className="w-4 h-4 text-cyan-400" />
          </div>
          <p className="text-sm font-semibold text-emerald-400 mt-2">Isolated Disk Vault</p>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>User Role</span>
            <Shield className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-sm font-semibold text-slate-200 mt-2">{activeRole || 'Analyst'}</p>
        </div>
      </div>

      {/* Search, Filter & Sort Controls */}
      <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          {/* Search Bar */}
          <div className="md:col-span-5 relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by title or filename..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition"
            />
          </div>

          {/* Status Filter */}
          <div className="md:col-span-3">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-emerald-500 transition"
            >
              <option value="">All Statuses</option>
              <option value="UPLOADED">Uploaded</option>
              <option value="QUEUED">Queued</option>
              <option value="PROCESSING">Processing</option>
              <option value="REVIEW_REQUIRED">Review Required</option>
              <option value="APPROVED">Approved</option>
              <option value="REJECTED">Rejected</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>

          {/* Doc Type Filter */}
          <div className="md:col-span-2">
            <select
              value={docTypeFilter}
              onChange={(e) => {
                setDocTypeFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-emerald-500 transition"
            >
              <option value="">All Types</option>
              <option value="10-K">10-K (Annual)</option>
              <option value="10-Q">10-Q (Quarterly)</option>
              <option value="INVOICE">Invoice</option>
              <option value="EARNINGS_CALL">Earnings Call</option>
              <option value="BALANCE_SHEET">Balance Sheet</option>
              <option value="OTHER">Other</option>
            </select>
          </div>

          {/* Sort Selector */}
          <div className="md:col-span-2">
            <select
              value={`${sortBy}-${sortOrder}`}
              onChange={(e) => {
                const [sb, so] = e.target.value.split('-');
                setSortBy(sb);
                setSortOrder(so as 'asc' | 'desc');
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-emerald-500 transition"
            >
              <option value="created_at-desc">Newest First</option>
              <option value="created_at-asc">Oldest First</option>
              <option value="title-asc">Title (A-Z)</option>
              <option value="title-desc">Title (Z-A)</option>
              <option value="file_size_bytes-desc">Size (Largest)</option>
              <option value="file_size_bytes-asc">Size (Smallest)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Document Library Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-3 px-4">Document Title</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">Size</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Uploaded By</th>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {isLoading ? (
                // Skeleton loading state
                Array.from({ length: 5 }).map((_, idx) => (
                  <tr key={idx} className="animate-pulse">
                    <td className="py-4 px-4">
                      <div className="h-4 bg-slate-800 rounded w-48 mb-1.5" />
                      <div className="h-3 bg-slate-800/60 rounded w-28" />
                    </td>
                    <td className="py-4 px-4"><div className="h-4 bg-slate-800 rounded w-16" /></td>
                    <td className="py-4 px-4"><div className="h-4 bg-slate-800 rounded w-14" /></td>
                    <td className="py-4 px-4"><div className="h-5 bg-slate-800 rounded-full w-20" /></td>
                    <td className="py-4 px-4"><div className="h-4 bg-slate-800 rounded w-24" /></td>
                    <td className="py-4 px-4"><div className="h-4 bg-slate-800 rounded w-20" /></td>
                    <td className="py-4 px-4 text-right"><div className="h-8 bg-slate-800 rounded w-20 ml-auto" /></td>
                  </tr>
                ))
              ) : documents.length === 0 ? (
                // Empty State
                <tr>
                  <td colSpan={7} className="py-16 text-center text-slate-400">
                    <div className="max-w-sm mx-auto flex flex-col items-center">
                      <div className="p-4 rounded-2xl bg-slate-800/50 text-slate-500 mb-3 border border-slate-700/50">
                        <FileText className="w-8 h-8" />
                      </div>
                      <h3 className="text-sm font-semibold text-slate-200">No documents found</h3>
                      <p className="text-xs text-slate-500 mt-1 mb-4">
                        {search || statusFilter || docTypeFilter
                          ? 'No filings match your current search and filter criteria.'
                          : 'Get started by uploading your first financial document to the secure library.'}
                      </p>
                      {canUpload && (
                        <button
                          onClick={() => setIsUploadModalOpen(true)}
                          className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-semibold rounded-lg transition"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          <span>Upload Now</span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                // Data rows
                documents.map((doc) => (
                  <tr
                    key={doc.id}
                    className="hover:bg-slate-800/30 transition group"
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-slate-800 border border-slate-700/60 text-slate-300 group-hover:border-emerald-500/30 transition">
                          <FileText className="w-4 h-4 text-emerald-400" />
                        </div>
                        <div className="min-w-0">
                          <p
                            onClick={() => openPreview(doc)}
                            className="font-medium text-slate-200 hover:text-emerald-400 cursor-pointer truncate max-w-xs transition"
                            title={doc.title}
                          >
                            {doc.title}
                          </p>
                          <p className="text-[11px] font-mono text-slate-500 truncate max-w-xs">
                            {doc.filename}
                          </p>
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      {doc.doc_type ? (
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          {doc.doc_type}
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[11px]">—</span>
                      )}
                    </td>

                    <td className="py-3 px-4 font-mono text-slate-400">
                      {formatFileSize(doc.file_size_bytes)}
                    </td>

                    <td className="py-3 px-4">
                      <StatusBadge status={doc.status} size="sm" />
                    </td>

                    <td className="py-3 px-4 text-slate-300">
                      <span className="truncate max-w-[120px] block" title={doc.uploader?.email || 'System'}>
                        {doc.uploader?.full_name || doc.uploader?.email || 'Direct Ingestion'}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-slate-400">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>

                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => openProcessing(doc)}
                          className={`p-1.5 rounded-lg transition ${
                            doc.status === 'PROCESSING' || doc.status === 'QUEUED'
                              ? 'text-indigo-400 bg-indigo-500/10 animate-pulse'
                              : doc.status === 'FAILED'
                              ? 'text-rose-400 bg-rose-500/10'
                              : 'text-slate-400 hover:text-indigo-400 hover:bg-slate-800'
                          }`}
                          title="Processing & OCR Telemetry / Extracted Text"
                        >
                          <Cpu className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => openPreview(doc)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
                          title="Preview Document"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <a
                          href={apiClient.getDocumentDownloadUrl(doc.id)}
                          download={doc.filename}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-emerald-400 hover:bg-slate-800 transition"
                          title="Download File"
                        >
                          <Download className="w-4 h-4" />
                        </a>
                        {canDelete && (
                          <button
                            onClick={() => {
                              setSelectedDocument(doc);
                              setIsPreviewOpen(true);
                            }}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition"
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-950/40 text-xs text-slate-400">
            <div>
              Showing <span className="font-semibold text-slate-200">{documents.length}</span> of{' '}
              <span className="font-semibold text-slate-200">{totalCount}</span> documents
            </div>
            <div className="flex items-center gap-2">
              <button
                disabled={currentPage <= 1 || isLoading}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                Previous
              </button>
              <span className="px-2 font-medium text-slate-300">
                Page {currentPage} of {totalPages}
              </span>
              <button
                disabled={currentPage >= totalPages || isLoading}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <DocumentUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onSuccess={handleUploadSuccess}
      />

      <DocumentPreviewModal
        document={selectedDocument}
        isOpen={isPreviewOpen}
        onClose={() => {
          setIsPreviewOpen(false);
          setSelectedDocument(null);
        }}
        onDelete={handleDelete}
        canDelete={canDelete}
      />

      <DocumentProcessingModal
        document={selectedProcessingDoc}
        isOpen={isProcessingOpen}
        onClose={() => {
          setIsProcessingOpen(false);
          setSelectedProcessingDoc(null);
        }}
        onStatusChange={fetchDocuments}
      />
    </div>
  );
};
