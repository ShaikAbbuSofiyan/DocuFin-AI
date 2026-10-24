import React, { useEffect, useState, useCallback } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Cpu,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
  X,
  Copy,
  Check,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';
import { apiClient } from '../../services/api';
import {
  DocumentItem,
  DocumentPageItem,
  ProcessingJob,
} from '../../types/document';

interface DocumentProcessingModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: DocumentItem | null;
  onStatusChange?: () => void;
}

export const DocumentProcessingModal: React.FC<DocumentProcessingModalProps> = ({
  isOpen,
  onClose,
  document,
  onStatusChange,
}) => {
  const [activeTab, setActiveTab] = useState<'status' | 'pages'>('status');
  const [currentJob, setCurrentJob] = useState<ProcessingJob | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // Extracted pages state
  const [pages, setPages] = useState<DocumentPageItem[]>([]);
  const [selectedPageNum, setSelectedPageNum] = useState<number>(1);
  const [isLoadingPages, setIsLoadingPages] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  const fetchJobStatus = useCallback(async () => {
    if (!document) return;
    try {
      const jobs = await apiClient.getProcessingJobs(document.id);
      if (jobs && jobs.length > 0) {
        const latest = jobs[0];
        setCurrentJob(latest);
        if (latest.status === 'COMPLETED' || latest.status === 'FAILED') {
          setIsPolling(false);
          if (onStatusChange) onStatusChange();
        }
      } else {
        setCurrentJob(null);
        setIsPolling(false);
      }
    } catch {
      // Polling error silently handled
    }
  }, [document, onStatusChange]);

  const fetchExtractedPages = useCallback(async () => {
    if (!document) return;
    try {
      setIsLoadingPages(true);
      const res = await apiClient.getDocumentExtractedText(document.id);
      setPages(res.pages || []);
      if (res.pages && res.pages.length > 0) {
        setSelectedPageNum(1);
      }
    } catch {
      setPages([]);
    } finally {
      setIsLoadingPages(false);
    }
  }, [document]);

  // Initial load
  useEffect(() => {
    if (isOpen && document) {
      setErrorBanner(null);
      fetchJobStatus();
      fetchExtractedPages();
      if (
        document.status === 'PROCESSING' ||
        document.status === 'QUEUED'
      ) {
        setIsPolling(true);
      }
    }
  }, [isOpen, document, fetchJobStatus, fetchExtractedPages]);

  // Polling loop
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (isOpen && isPolling) {
      interval = setInterval(() => {
        fetchJobStatus();
      }, 2500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isOpen, isPolling, fetchJobStatus]);

  if (!isOpen || !document) return null;

  const handleStartProcessing = async () => {
    try {
      setActionLoading(true);
      setErrorBanner(null);
      const job = await apiClient.processDocument(document.id, true);
      setCurrentJob(job);
      setIsPolling(true);
      if (onStatusChange) onStatusChange();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to queue processing job.';
      setErrorBanner(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRetryProcessing = async () => {
    try {
      setActionLoading(true);
      setErrorBanner(null);
      const job = await apiClient.retryDocument(document.id);
      setCurrentJob(job);
      setIsPolling(true);
      if (onStatusChange) onStatusChange();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Retry failed.';
      setErrorBanner(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const selectedPage = pages.find((p) => p.page_number === selectedPageNum) || pages[0];

  const handleCopyText = () => {
    if (selectedPage?.text_content) {
      navigator.clipboard.writeText(selectedPage.text_content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getStagePercent = (stage: string) => {
    switch (stage?.toUpperCase()) {
      case 'QUEUED':
        return 15;
      case 'VALIDATING':
        return 35;
      case 'EXTRACTING_TEXT':
        return 65;
      case 'RUNNING_OCR':
        return 80;
      case 'AGGREGATING':
        return 90;
      case 'COMPLETED':
        return 100;
      case 'FAILED':
        return 100;
      default:
        return 10;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden text-slate-100">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                Asynchronous Processing & OCR
                {isPolling && (
                  <span className="flex items-center gap-1.5 text-xs font-normal px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse">
                    <Loader2 className="w-3 h-3 animate-spin" /> Live Polling
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-400">{document.title} ({document.filename})</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-4 px-6 pt-3 border-b border-slate-800 bg-slate-950/30">
          <button
            onClick={() => setActiveTab('status')}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'status'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <RefreshCw className="w-4 h-4" /> Job Telemetry & Retries
          </button>
          <button
            onClick={() => {
              setActiveTab('pages');
              fetchExtractedPages();
            }}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'pages'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileText className="w-4 h-4" /> Extracted Pages & OCR
            {pages.length > 0 && (
              <span className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 text-xs">
                {pages.length}
              </span>
            )}
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {errorBanner && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="font-medium">Processing Error</p>
                <p className="text-xs text-rose-300/90 mt-1">{errorBanner}</p>
              </div>
            </div>
          )}

          {activeTab === 'status' && (
            <div className="space-y-6">
              {/* Progress & Current Stage Card */}
              <div className="p-5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm font-medium text-slate-200">Current Status:</span>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${
                        currentJob?.status === 'COMPLETED'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : currentJob?.status === 'FAILED'
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : currentJob?.status === 'RETRYING'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse'
                      }`}
                    >
                      {currentJob?.status || document.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <Clock className="w-4 h-4" />
                    <span>
                      {currentJob?.duration_ms
                        ? `${(currentJob.duration_ms / 1000).toFixed(2)}s elapsed`
                        : 'Duration tracking'}
                    </span>
                  </div>
                </div>

                {/* Progress bar */}
                <div>
                  <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
                    <span>Stage: {currentJob?.stage || 'IDLE'}</span>
                    <span>{getStagePercent(currentJob?.stage || '')}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className={`h-full transition-all duration-500 ${
                        currentJob?.status === 'FAILED'
                          ? 'bg-rose-500'
                          : currentJob?.status === 'COMPLETED'
                          ? 'bg-emerald-500'
                          : 'bg-indigo-500 animate-pulse'
                      }`}
                      style={{ width: `${getStagePercent(currentJob?.stage || '')}%` }}
                    />
                  </div>
                </div>

                {/* Attempt breakdown */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800/80">
                    <p className="text-[11px] text-slate-400">Attempts</p>
                    <p className="text-sm font-semibold text-slate-200 mt-0.5">
                      {currentJob?.attempts ?? 0} / {currentJob?.max_attempts ?? 3}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800/80">
                    <p className="text-[11px] text-slate-400">Backoff Strategy</p>
                    <p className="text-sm font-semibold text-slate-200 mt-0.5">
                      Exponential (2ⁿs)
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800/80">
                    <p className="text-[11px] text-slate-400">Worker Broker</p>
                    <p className="text-sm font-semibold text-slate-200 mt-0.5">
                      Celery / Redis
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800/80">
                    <p className="text-[11px] text-slate-400">Pages Processed</p>
                    <p className="text-sm font-semibold text-slate-200 mt-0.5">
                      {(document.extra_metadata?.total_pages as number) || pages.length || 0}
                    </p>
                  </div>
                </div>
              </div>

              {/* Error Callout if Job Failed */}
              {currentJob?.error_message && (
                <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 space-y-2">
                  <div className="flex items-center gap-2 font-medium text-rose-400">
                    <AlertCircle className="w-5 h-5" />
                    <span>Failure Reason</span>
                  </div>
                  <p className="text-xs bg-slate-950/60 p-3 rounded-lg font-mono text-rose-200 break-words">
                    {currentJob.error_message}
                  </p>
                  <p className="text-xs text-rose-300/80">
                    The job has exceeded max attempts or hit a non-recoverable error. You can click retry to force a fresh queue attempt.
                  </p>
                </div>
              )}

              {/* Success Info if Completed */}
              {currentJob?.status === 'COMPLETED' && (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 space-y-2">
                  <div className="flex items-center gap-2 font-medium text-emerald-400">
                    <CheckCircle2 className="w-5 h-5" />
                    <span>Document Processing Complete</span>
                  </div>
                  <p className="text-xs text-emerald-200/90">
                    All pages and OCR elements have been extracted and vaulted with exact page indexing. Switch to the <strong>Extracted Pages & OCR</strong> tab to view extracted financial text.
                  </p>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-2">
                {currentJob?.status === 'FAILED' ? (
                  <button
                    onClick={handleRetryProcessing}
                    disabled={actionLoading}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-medium text-sm transition-all shadow-lg shadow-amber-600/20 disabled:opacity-50"
                  >
                    <RefreshCw className={`w-4 h-4 ${actionLoading ? 'animate-spin' : ''}`} />
                    Retry Processing (Bounded)
                  </button>
                ) : (
                  <button
                    onClick={handleStartProcessing}
                    disabled={actionLoading || isPolling}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-all shadow-lg shadow-indigo-600/20 disabled:opacity-50"
                  >
                    <Sparkles className={`w-4 h-4 ${actionLoading ? 'animate-spin' : ''}`} />
                    {currentJob?.status === 'COMPLETED' ? 'Force Re-process' : 'Queue Processing'}
                  </button>
                )}
              </div>
            </div>
          )}

          {activeTab === 'pages' && (
            <div className="space-y-4">
              {/* Security Boundary Notice */}
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-950/50 border border-slate-800 text-[11px] text-slate-400">
                <ShieldAlert className="w-4 h-4 text-amber-400 flex-shrink-0" />
                <span>
                  Untrusted Document Sandbox: Embedded scripts and macros are safely neutralized.
                </span>
              </div>

              {isLoadingPages ? (
                <div className="py-12 flex flex-col items-center justify-center gap-2 text-slate-400">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
                  <p className="text-xs">Loading extracted pages...</p>
                </div>
              ) : pages.length === 0 ? (
                <div className="py-12 text-center text-slate-400 space-y-3">
                  <FileText className="w-10 h-10 mx-auto text-slate-600" />
                  <p className="text-sm">No extracted pages available yet.</p>
                  <p className="text-xs text-slate-500">
                    Trigger document processing in the status tab to extract text and run OCR.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 min-h-[350px]">
                  {/* Page Selector Sidebar */}
                  <div className="col-span-1 border border-slate-800 rounded-xl bg-slate-950/40 p-2 space-y-1 max-h-[420px] overflow-y-auto">
                    <p className="text-[11px] font-semibold text-slate-400 px-2 py-1 uppercase tracking-wider">
                      Pages ({pages.length})
                    </p>
                    {pages.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => setSelectedPageNum(p.page_number)}
                        className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-all flex items-center justify-between ${
                          selectedPageNum === p.page_number
                            ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                        }`}
                      >
                        <span className="flex items-center gap-1.5">
                          Page {p.page_number}
                          {p.ocr_applied && (
                            <span className="px-1 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30">
                              OCR
                            </span>
                          )}
                        </span>
                        <ChevronRight className="w-3 h-3 text-slate-500" />
                      </button>
                    ))}
                  </div>

                  {/* Page Content Viewer */}
                  <div className="col-span-1 md:col-span-3 border border-slate-800 rounded-xl bg-slate-950/60 flex flex-col overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800 bg-slate-900/60 text-xs text-slate-400">
                      <div className="flex items-center gap-3">
                        <span className="font-semibold text-slate-200">
                          Page {selectedPage?.page_number}
                        </span>
                        <span>{selectedPage?.word_count ?? 0} words</span>
                        <span>{selectedPage?.char_count ?? 0} chars</span>
                        {selectedPage?.is_scanned && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            Scanned Document Page
                          </span>
                        )}
                      </div>
                      <button
                        onClick={handleCopyText}
                        className="flex items-center gap-1.5 text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 px-2.5 py-1 rounded-md transition-colors"
                      >
                        {copied ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-emerald-400" /> Copied!
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5" /> Copy Text
                          </>
                        )}
                      </button>
                    </div>

                    <div className="p-4 flex-1 overflow-y-auto max-h-[360px]">
                      <pre className="text-xs font-mono text-slate-200 whitespace-pre-wrap leading-relaxed select-text">
                        {selectedPage?.text_content || 'No text content extracted on this page.'}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end px-6 py-3 border-t border-slate-800 bg-slate-900/50">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
