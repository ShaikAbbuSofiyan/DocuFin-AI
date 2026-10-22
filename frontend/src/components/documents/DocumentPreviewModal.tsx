import React, { useState } from 'react';
import {
  AlertCircle,
  Calendar,
  Check,
  Copy,
  Download,
  Eye,
  File,
  HardDrive,
  Shield,
  Trash2,
  User,
  X,
} from 'lucide-react';
import { apiClient } from '../../services/api';
import { DocumentItem } from '../../types/document';
import { StatusBadge } from '../common/StatusBadge';

interface DocumentPreviewModalProps {
  document: DocumentItem | null;
  isOpen: boolean;
  onClose: () => void;
  onDelete?: (id: string) => Promise<void>;
  canDelete?: boolean;
}

export const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({
  document,
  isOpen,
  onClose,
  onDelete,
  canDelete = false,
}) => {
  const [copied, setCopied] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (!isOpen || !document) return null;

  const isPdf = document.mime_type === 'application/pdf' || document.file_extension === '.pdf';
  const isImage =
    document.mime_type.startsWith('image/') ||
    ['.png', '.jpg', '.jpeg'].includes(document.file_extension.toLowerCase());

  const previewUrl = apiClient.getDocumentPreviewUrl(document.id);
  const downloadUrl = apiClient.getDocumentDownloadUrl(document.id);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const copyChecksum = () => {
    if (document.checksum_sha256) {
      navigator.clipboard.writeText(document.checksum_sha256);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    try {
      setIsDeleting(true);
      setDeleteError(null);
      await onDelete(document.id);
      setShowDeleteConfirm(false);
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete document';
      setDeleteError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative flex flex-col w-full max-w-6xl h-[90vh] bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-900/90 backdrop-blur">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <File className="w-5 h-5" />
            </div>
            <div className="truncate">
              <h2 className="text-lg font-semibold text-slate-100 truncate">{document.title}</h2>
              <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-400">
                <span className="font-mono">{document.filename}</span>
                <span>•</span>
                <span>{formatFileSize(document.file_size_bytes)}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <StatusBadge status={document.status} />
            {document.doc_type && (
              <span className="px-2.5 py-1 text-xs font-semibold uppercase tracking-wider rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                {document.doc_type}
              </span>
            )}
            <a
              href={downloadUrl}
              download={document.filename}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
              title="Download Secure Binary"
            >
              <Download className="w-4 h-4 text-emerald-400" />
              <span>Download</span>
            </a>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body: Split into Preview Area and Metadata Sidebar */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden bg-slate-950/50">
          {/* Main Document Viewer */}
          <div className="flex-1 flex items-center justify-center p-4 overflow-auto border-b md:border-b-0 md:border-r border-slate-800/80 bg-slate-950/80">
            {isPdf ? (
              <iframe
                src={`${previewUrl}#toolbar=1`}
                title={document.title}
                className="w-full h-full rounded-xl border border-slate-800 bg-white"
              />
            ) : isImage ? (
              <div className="max-w-full max-h-full flex flex-col items-center justify-center p-4">
                <img
                  src={previewUrl}
                  alt={document.title}
                  className="max-h-[70vh] max-w-full rounded-xl object-contain shadow-lg border border-slate-800"
                />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center p-8 text-center text-slate-400">
                <Eye className="w-12 h-12 mb-3 text-slate-500 stroke-1" />
                <p className="text-sm font-medium text-slate-300">Binary preview unavailable for this format</p>
                <p className="text-xs text-slate-500 mt-1">Download file to inspect contents safely on your local device.</p>
              </div>
            )}
          </div>

          {/* Metadata & Audit Sidebar */}
          <div className="w-full md:w-80 p-6 flex flex-col gap-6 overflow-y-auto bg-slate-900/60 border-slate-800">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                Security & Verification
              </h3>
              <div className="space-y-3 bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                <div>
                  <span className="text-xs text-slate-500">MIME Type</span>
                  <p className="text-xs font-mono text-slate-300 mt-0.5">{document.mime_type}</p>
                </div>
                <div>
                  <span className="text-xs text-slate-500">SHA-256 Checksum</span>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="font-mono text-[11px] text-slate-400 truncate flex-1" title={document.checksum_sha256}>
                      {document.checksum_sha256 ? `${document.checksum_sha256.slice(0, 16)}...` : 'N/A'}
                    </span>
                    {document.checksum_sha256 && (
                      <button
                        onClick={copyChecksum}
                        className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
                        title="Copy SHA-256"
                      >
                        {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    )}
                  </div>
                </div>
                <div>
                  <span className="text-xs text-slate-500">Storage Protection</span>
                  <p className="text-xs text-emerald-400 flex items-center gap-1 mt-0.5">
                    <HardDrive className="w-3 h-3" />
                    Isolated Tenant Vault
                  </p>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                Lifecycle & Origin
              </h3>
              <div className="space-y-3 bg-slate-900/90 p-4 rounded-xl border border-slate-800 text-xs">
                <div>
                  <span className="text-slate-500">Uploaded Date</span>
                  <p className="text-slate-200 mt-0.5">
                    {new Date(document.created_at).toLocaleString()}
                  </p>
                </div>
                <div>
                  <span className="text-slate-500">Uploaded By</span>
                  <p className="text-slate-200 flex items-center gap-1 mt-0.5">
                    <User className="w-3 h-3 text-slate-400" />
                    {document.uploader?.full_name || document.uploader?.email || 'System / Direct API'}
                  </p>
                </div>
                {document.uploader?.email && (
                  <div>
                    <span className="text-slate-500">Email</span>
                    <p className="text-slate-400 font-mono mt-0.5">{document.uploader.email}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Deletion Section */}
            {canDelete && (
              <div className="mt-auto pt-4 border-t border-slate-800">
                {deleteError && (
                  <div className="mb-3 p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{deleteError}</span>
                  </div>
                )}

                {!showDeleteConfirm ? (
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 border border-rose-500/20 transition"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>Delete Document</span>
                  </button>
                ) : (
                  <div className="p-3 bg-rose-950/20 border border-rose-500/30 rounded-xl space-y-2">
                    <p className="text-xs text-rose-300 font-medium">Permanently purge this document and binary artifact?</p>
                    <div className="flex gap-2">
                      <button
                        onClick={handleDelete}
                        disabled={isDeleting}
                        className="flex-1 py-1.5 px-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-medium transition disabled:opacity-50"
                      >
                        {isDeleting ? 'Deleting...' : 'Confirm Delete'}
                      </button>
                      <button
                        onClick={() => setShowDeleteConfirm(false)}
                        disabled={isDeleting}
                        className="py-1.5 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
