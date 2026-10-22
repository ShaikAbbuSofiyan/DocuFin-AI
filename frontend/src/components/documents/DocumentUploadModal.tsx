import React, { useRef, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Image,
  UploadCloud,
  X,
} from 'lucide-react';
import { apiClient } from '../../services/api';
import { DocumentItem, DocumentType } from '../../types/document';

interface DocumentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newDoc: DocumentItem) => void;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg'];
const MAX_SIZE_MB = 50;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

export const DocumentUploadModal: React.FC<DocumentUploadModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [docType, setDocType] = useState<DocumentType>('10-K');
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const validateAndSetFile = (file: File) => {
    setErrorMessage(null);
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setErrorMessage(
        `Invalid file format "${ext}". Supported formats are: PDF, PNG, and JPEG.`
      );
      return;
    }

    if (file.size > MAX_SIZE_BYTES) {
      setErrorMessage(
        `File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds maximum limit of ${MAX_SIZE_MB}MB.`
      );
      return;
    }

    if (file.size === 0) {
      setErrorMessage('Selected file is empty (0 bytes).');
      return;
    }

    setSelectedFile(file);
    if (!title) {
      // Default title to filename without extension
      const baseName = file.name.replace(/\.[^/.]+$/, '');
      setTitle(baseName.replace(/[_-]/g, ' '));
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMessage('Please select a file to upload.');
      return;
    }

    try {
      setIsUploading(true);
      setErrorMessage(null);
      setUploadProgress(0);

      const formData = new FormData();
      formData.append('file', selectedFile);
      if (title.trim()) {
        formData.append('title', title.trim());
      }
      if (docType) {
        formData.append('doc_type', docType);
      }

      const uploadedDoc = await apiClient.uploadDocument(formData, (progress) => {
        setUploadProgress(progress);
      });

      setUploadProgress(100);
      setTimeout(() => {
        onSuccess(uploadedDoc);
        handleReset();
        onClose();
      }, 500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed. Please try again.';
      setErrorMessage(msg);
      setUploadProgress(null);
    } finally {
      setIsUploading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setTitle('');
    setDocType('10-K');
    setUploadProgress(null);
    setErrorMessage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-100">Upload Financial Document</h2>
              <p className="text-xs text-slate-400">PDF, PNG, or JPEG up to 50MB</p>
            </div>
          </div>
          <button
            onClick={() => {
              handleReset();
              onClose();
            }}
            disabled={isUploading}
            className="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {errorMessage && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Drag & Drop Area */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`relative flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-xl cursor-pointer transition ${
              dragActive
                ? 'border-emerald-500 bg-emerald-500/5'
                : selectedFile
                ? 'border-slate-700 bg-slate-800/40 hover:border-slate-600'
                : 'border-slate-700 hover:border-slate-600 bg-slate-950/40'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
              onChange={handleFileChange}
              className="hidden"
            />

            {selectedFile ? (
              <div className="flex flex-col items-center text-center">
                <div className="p-3 rounded-full bg-emerald-500/10 text-emerald-400 mb-2 border border-emerald-500/20">
                  <CheckCircle2 className="w-7 h-7" />
                </div>
                <p className="text-sm font-medium text-slate-200">{selectedFile.name}</p>
                <p className="text-xs text-slate-400 mt-1">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Click or drag to replace
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center text-center">
                <div className="p-3 rounded-full bg-slate-800 text-slate-400 mb-3 border border-slate-700">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <p className="text-sm font-medium text-slate-200">
                  Drag & drop your file here, or <span className="text-emerald-400 hover:underline">browse</span>
                </p>
                <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" /> PDF
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Image className="w-3.5 h-3.5" /> PNG, JPEG
                  </span>
                  <span>•</span>
                  <span>Max 50MB</span>
                </div>
              </div>
            )}
          </div>

          {/* Form Fields */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Document Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Q3 10-Q Disclosure"
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500 transition"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Document Type
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value as DocumentType)}
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500 transition"
              >
                <option value="10-K">10-K (Annual Report)</option>
                <option value="10-Q">10-Q (Quarterly Report)</option>
                <option value="INVOICE">Corporate Invoice</option>
                <option value="EARNINGS_CALL">Earnings Transcript</option>
                <option value="BALANCE_SHEET">Balance Sheet / Audit</option>
                <option value="OTHER">Other Financial Filing</option>
              </select>
            </div>
          </div>

          {/* Upload Progress Bar */}
          {uploadProgress !== null && (
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-slate-400">
                <span>Ingesting file...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-300 rounded-full"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={() => {
                handleReset();
                onClose();
              }}
              disabled={isUploading}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!selectedFile || isUploading}
              className="inline-flex items-center gap-2 px-5 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-xs rounded-lg transition shadow-md shadow-emerald-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isUploading ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-4 h-4" />
                  <span>Upload & Ingest</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
