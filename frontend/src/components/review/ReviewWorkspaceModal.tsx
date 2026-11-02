import React, { useState, useEffect } from 'react';
import {
  X,
  CheckCircle2,
  XCircle,
  Save,
  AlertTriangle,
  ShieldCheck,
  FileText,
  Eye,
  History,
  Layers,
  ArrowRight,
  ExternalLink,
  Info,
  RefreshCw,
} from 'lucide-react';
import { apiClient } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import {
  ReviewTaskDetailResponse,
  ReviewHistoryItem,
} from '../../types/review';

interface ReviewWorkspaceModalProps {
  taskId: string;
  isOpen: boolean;
  onClose: () => void;
  onTaskUpdated?: () => void;
}

export const ReviewWorkspaceModal: React.FC<ReviewWorkspaceModalProps> = ({
  taskId,
  isOpen,
  onClose,
  onTaskUpdated,
}) => {
  const { user } = useAuth();
  const [task, setTask] = useState<ReviewTaskDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Active view tab in right pane
  const [activeTab, setActiveTab] = useState<'fields' | 'history'>('fields');
  // Left preview mode: 'preview' or 'ocr'
  const [previewMode, setPreviewMode] = useState<'preview' | 'ocr'>('preview');

  // Form edit state
  const [editedFields, setEditedFields] = useState<Record<string, any>>({});
  const [notes, setNotes] = useState<string>('');

  // Rejection confirmation dialog state
  const [isRejectModalOpen, setIsRejectModalOpen] = useState<boolean>(false);
  const [rejectionReason, setRejectionReason] = useState<string>('');

  // OCR pages
  const [ocrPages, setOcrPages] = useState<Array<{ page_number: number; text_content: string }>>([]);
  const [selectedOcrPage, setSelectedOcrPage] = useState<number>(1);

  useEffect(() => {
    if (isOpen && taskId) {
      loadTaskDetails();
    }
  }, [isOpen, taskId]);

  const loadTaskDetails = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiClient.getReviewTask(taskId);
      setTask(data);
      setEditedFields(data.extracted_data || {});
      setNotes(data.resolution_notes || '');

      // Load OCR pages for the document
      if (data.document_id) {
        try {
          const pagesResp = await apiClient.getDocumentExtractedText(data.document_id);
          setOcrPages(pagesResp.pages || []);
        } catch {
          // If OCR pages fail or don't exist, preview tab remains functional
        }
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load review task workspace.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  if (isLoading && !task) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 flex items-center space-x-3 text-slate-300 text-sm">
          <RefreshCw className="w-5 h-5 animate-spin text-indigo-400" />
          <span>Loading Review Workspace...</span>
        </div>
      </div>
    );
  }

  // Determine if user is the uploader (Dual Control Policy)
  const isUploader = Boolean(task?.uploader_id && user?.id && task.uploader_id === user.id);

  // Check which fields have been edited
  const originalData = task?.extracted_data || {};
  const modifiedKeys = Object.keys(editedFields).filter(
    (k) => editedFields[k] !== originalData[k]
  );

  const handleFieldChange = (key: string, value: any) => {
    setEditedFields((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleSaveCorrections = async () => {
    if (!task) return;
    try {
      setIsSubmitting(true);
      setError(null);
      setSuccessMsg(null);

      const updated = await apiClient.correctReviewFields(task.id, {
        field_updates: editedFields,
        notes: notes || undefined,
        expected_version: task.version,
      });

      setTask(updated);
      setEditedFields(updated.extracted_data || {});
      setSuccessMsg('Field corrections saved and re-validated successfully.');
      onTaskUpdated?.();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.message || 'Failed to save field corrections.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApprove = async () => {
    if (!task) return;
    try {
      setIsSubmitting(true);
      setError(null);

      const updated = await apiClient.approveReviewTask(task.id, {
        notes: notes || 'Approved by reviewer sign-off',
        expected_version: task.version,
      });

      setTask(updated);
      setSuccessMsg('Document successfully approved and verified.');
      onTaskUpdated?.();
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err?.message || 'Failed to approve review task.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmReject = async () => {
    if (!task) return;
    if (!rejectionReason.trim()) {
      setError('A rejection reason is mandatory.');
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);

      const updated = await apiClient.rejectReviewTask(task.id, {
        rejection_reason: rejectionReason.trim(),
        expected_version: task.version,
      });

      setTask(updated);
      setIsRejectModalOpen(false);
      setSuccessMsg('Document rejected and recorded in compliance history.');
      onTaskUpdated?.();
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err?.message || 'Failed to reject review task.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isApproved = task?.status === 'APPROVED';
  const isRejected = task?.status === 'REJECTED';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-7xl h-[92vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Workspace Top Navigation Bar */}
        <div className="px-6 py-3.5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-indigo-950/80 border border-indigo-500/40 rounded-xl text-indigo-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-semibold text-slate-100 truncate max-w-md">
                  {task?.document_title || task?.document_filename || 'Review Workspace'}
                </h2>
                {task && (
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase border ${
                      task.priority === 'CRITICAL'
                        ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                        : task.priority === 'HIGH'
                        ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                        : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                    }`}
                  >
                    {task.priority} Priority
                  </span>
                )}
                {task && (
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-mono">
                    v{task.version}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                Type: {task?.document_type || 'Unknown'} • Document ID: {task?.document_id}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {task && (
              <span
                className={`px-3 py-1 rounded-full text-xs font-semibold border ${
                  isApproved
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                    : isRejected
                    ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                    : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                }`}
              >
                {task.status}
              </span>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
              title="Close Workspace"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Global Notifications & Warnings */}
        {error && (
          <div className="mx-6 mt-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between shrink-0">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-200">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {successMsg && (
          <div className="mx-6 mt-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center space-x-2 shrink-0">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Dual-Control Warning Banner */}
        {isUploader && (
          <div className="mx-6 mt-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center space-x-2 shrink-0">
            <Info className="w-4 h-4 shrink-0 text-amber-400" />
            <span>
              <strong>Dual-Control Policy:</strong> You uploaded this document. You can edit fields and record notes, but another authorized reviewer or administrator must sign off on approval.
            </span>
          </div>
        )}

        {/* Side-by-Side Split Workspace Layout */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden p-6 gap-6">
          {/* LEFT PANE: Document Preview / OCR Viewer */}
          <div className="flex-1 flex flex-col bg-slate-950/80 rounded-xl border border-slate-800 overflow-hidden shadow-inner">
            <div className="px-4 py-2.5 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between shrink-0">
              <div className="flex items-center space-x-1">
                <button
                  onClick={() => setPreviewMode('preview')}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                    previewMode === 'preview'
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <span className="flex items-center space-x-1.5">
                    <Eye className="w-3.5 h-3.5" />
                    <span>Original Document</span>
                  </span>
                </button>
                <button
                  onClick={() => setPreviewMode('ocr')}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                    previewMode === 'ocr'
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <span className="flex items-center space-x-1.5">
                    <FileText className="w-3.5 h-3.5" />
                    <span>OCR Text ({ocrPages.length} Pages)</span>
                  </span>
                </button>
              </div>

              {task?.document_id && (
                <a
                  href={`/api/v1/documents/${task.document_id}/download`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center space-x-1"
                >
                  <span>Download</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>

            <div className="flex-1 overflow-auto bg-slate-950 flex items-center justify-center p-2">
              {previewMode === 'preview' ? (
                task?.document_id ? (
                  <iframe
                    src={`/api/v1/documents/${task.document_id}/preview`}
                    title="Document Preview"
                    className="w-full h-full rounded border-0 bg-slate-900"
                  />
                ) : (
                  <div className="text-slate-500 text-xs">No document preview available.</div>
                )
              ) : (
                /* OCR Page-by-Page Viewer */
                <div className="w-full h-full flex flex-col bg-slate-950 p-4">
                  {ocrPages.length > 0 ? (
                    <>
                      <div className="flex items-center space-x-2 pb-3 border-b border-slate-800 shrink-0">
                        <span className="text-xs text-slate-400">Page:</span>
                        {ocrPages.map((p) => (
                          <button
                            key={p.page_number}
                            onClick={() => setSelectedOcrPage(p.page_number)}
                            className={`px-2.5 py-1 rounded text-xs font-mono transition ${
                              selectedOcrPage === p.page_number
                                ? 'bg-indigo-600 text-white font-bold'
                                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                            }`}
                          >
                            {p.page_number}
                          </button>
                        ))}
                      </div>
                      <div className="flex-1 overflow-auto pt-4 text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed select-text">
                        {ocrPages.find((p) => p.page_number === selectedOcrPage)?.text_content ||
                          'No text extracted for this page.'}
                      </div>
                    </>
                  ) : (
                    <div className="text-slate-500 text-xs text-center m-auto">
                      No extracted OCR text pages available.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* RIGHT PANE: Structured Data, Validations, Decisions & History */}
          <div className="flex-1 flex flex-col bg-slate-900/60 rounded-xl border border-slate-800 overflow-hidden">
            {/* Tab navigation */}
            <div className="px-4 py-2 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between shrink-0">
              <div className="flex items-center space-x-1">
                <button
                  onClick={() => setActiveTab('fields')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    activeTab === 'fields'
                      ? 'bg-slate-800 text-indigo-300 border border-slate-700'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <span className="flex items-center space-x-1.5">
                    <Layers className="w-3.5 h-3.5" />
                    <span>Structured Fields & Validation</span>
                  </span>
                </button>
                <button
                  onClick={() => setActiveTab('history')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    activeTab === 'history'
                      ? 'bg-slate-800 text-indigo-300 border border-slate-700'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <span className="flex items-center space-x-1.5">
                    <History className="w-3.5 h-3.5" />
                    <span>Audit Trail ({task?.histories?.length || 0})</span>
                  </span>
                </button>
              </div>

              {modifiedKeys.length > 0 && (
                <span className="text-[11px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  {modifiedKeys.length} Unsaved Edits
                </span>
              )}
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {activeTab === 'fields' ? (
                <>
                  {/* Validation Checks Panel */}
                  {task?.validation_errors && task.validation_errors.length > 0 && (
                    <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                      <div className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                        <span className="flex items-center gap-1.5 text-amber-400">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          Business Rule Validation Warnings ({task.validation_errors.length})
                        </span>
                      </div>
                      <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                        {task.validation_errors.map((errItem, idx) => (
                          <div
                            key={idx}
                            className={`p-2 rounded text-[11px] border ${
                              errItem.severity === 'ERROR'
                                ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                                : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                            }`}
                          >
                            <span className="font-semibold font-mono mr-1">
                              [{errItem.rule_id || 'RULE'}]
                            </span>
                            <span>{errItem.explanation || JSON.stringify(errItem)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Editable Fields Form */}
                  <div className="space-y-3">
                    <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                      Extracted Financial Fields
                    </div>
                    {Object.keys(editedFields).length === 0 ? (
                      <div className="text-center py-8 text-xs text-slate-500">
                        No structured fields extracted.
                      </div>
                    ) : (
                      Object.entries(editedFields).map(([key, val]) => {
                        const isModified = editedFields[key] !== originalData[key];
                        const meta = task?.field_metadata?.[key];
                        const conf = meta?.confidence;
                        const pageNum = meta?.source_page;

                        // Exclude nested complex dicts or lists from flat inputs
                        if (typeof val === 'object' && val !== null) {
                          return (
                            <div key={key} className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                              <label className="text-[11px] font-mono text-slate-400 capitalize block mb-1">
                                {key.replace(/_/g, ' ')}
                              </label>
                              <pre className="text-[10px] text-slate-300 overflow-x-auto p-1 bg-slate-900 rounded">
                                {JSON.stringify(val, null, 2)}
                              </pre>
                            </div>
                          );
                        }

                        return (
                          <div
                            key={key}
                            className={`p-2.5 rounded-lg border transition ${
                              isModified
                                ? 'bg-indigo-950/20 border-indigo-500/50'
                                : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <label className="text-xs font-medium text-slate-300 capitalize">
                                {key.replace(/_/g, ' ')}
                              </label>
                              <div className="flex items-center space-x-1.5">
                                {isModified && (
                                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/40">
                                    Edited
                                  </span>
                                )}
                                {pageNum && (
                                  <span className="text-[10px] px-1 py-0.2 rounded bg-slate-800 text-slate-400 font-mono">
                                    Pg {pageNum}
                                  </span>
                                )}
                                {conf !== undefined && (
                                  <span
                                    className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                                      conf >= 0.85
                                        ? 'bg-emerald-500/10 text-emerald-400'
                                        : 'bg-amber-500/10 text-amber-400'
                                    }`}
                                  >
                                    {(conf * 100).toFixed(0)}%
                                  </span>
                                )}
                              </div>
                            </div>
                            <input
                              type="text"
                              value={val ?? ''}
                              onChange={(e) => handleFieldChange(key, e.target.value)}
                              disabled={isApproved || isRejected || isSubmitting}
                              className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1.5 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500"
                            />
                            {isModified && (
                              <div className="text-[10px] text-slate-500 mt-1 flex items-center space-x-1">
                                <span>Original:</span>
                                <span className="font-mono text-slate-400 italic">
                                  {String(originalData[key] ?? 'None')}
                                </span>
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>

                  {/* Review Notes Textarea */}
                  <div className="pt-2">
                    <label className="text-xs font-semibold text-slate-300 block mb-1">
                      Reviewer Notes & Decision Rationale
                    </label>
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      disabled={isApproved || isRejected || isSubmitting}
                      placeholder="Add compliance notes, audit trail observations, or explain changes..."
                      rows={3}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </>
              ) : (
                /* History / Audit Diff Tab */
                <div className="space-y-3">
                  <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                    Review Decision & Correction Timeline
                  </div>
                  {task?.histories && task.histories.length > 0 ? (
                    task.histories.map((h: ReviewHistoryItem) => (
                      <div
                        key={h.id}
                        className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 space-y-1.5"
                      >
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center space-x-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                h.action === 'APPROVED'
                                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                                  : h.action === 'REJECTED'
                                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                                  : h.action === 'FIELD_CORRECTION'
                                  ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40'
                                  : 'bg-slate-800 text-slate-300'
                              }`}
                            >
                              {h.action}
                            </span>
                            <span className="font-medium text-slate-300">
                              {h.user_email || h.user_id || 'System'}
                            </span>
                            {h.user_role && (
                              <span className="text-[10px] text-slate-500 font-mono">
                                ({h.user_role})
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-slate-500">
                            {new Date(h.created_at).toLocaleString()}
                          </span>
                        </div>

                        {h.notes && (
                          <p className="text-xs text-slate-400 italic bg-slate-900/50 p-2 rounded">
                            "{h.notes}"
                          </p>
                        )}

                        {/* Field Diffs Table */}
                        {h.field_changes && Object.keys(h.field_changes).length > 0 && (
                          <div className="mt-2 border-t border-slate-800/80 pt-2 space-y-1">
                            <div className="text-[10px] uppercase font-semibold text-slate-500">
                              Modified Values:
                            </div>
                            <div className="grid grid-cols-1 gap-1 text-[11px] font-mono">
                              {Object.entries(h.field_changes).map(([fKey, diff]: [string, any]) => (
                                <div
                                  key={fKey}
                                  className="flex items-center justify-between bg-slate-900 px-2 py-1 rounded"
                                >
                                  <span className="text-indigo-400">{fKey}:</span>
                                  <div className="flex items-center space-x-2">
                                    <span className="text-rose-400 line-through">
                                      {String(diff.old_value ?? 'null')}
                                    </span>
                                    <ArrowRight className="w-3 h-3 text-slate-500" />
                                    <span className="text-emerald-400">
                                      {String(diff.new_value ?? 'null')}
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8 text-xs text-slate-500">
                      No review history records yet.
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Bottom Actions Footer */}
            <div className="px-6 py-4 border-t border-slate-800 bg-slate-950 flex items-center justify-between shrink-0">
              <div className="text-xs text-slate-500">
                {isApproved ? (
                  <span className="text-emerald-400 font-medium">✓ Document Approved</span>
                ) : isRejected ? (
                  <span className="text-rose-400 font-medium">✗ Document Rejected</span>
                ) : (
                  <span>Status: Awaiting Reviewer Sign-off</span>
                )}
              </div>

              {!isApproved && !isRejected && (
                <div className="flex items-center space-x-3">
                  <button
                    onClick={handleSaveCorrections}
                    disabled={isSubmitting || modifiedKeys.length === 0}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 flex items-center space-x-1.5 transition"
                  >
                    <Save className="w-3.5 h-3.5" />
                    <span>Save Edits</span>
                  </button>

                  <button
                    onClick={() => setIsRejectModalOpen(true)}
                    disabled={isSubmitting}
                    className="px-4 py-2 bg-rose-600/20 hover:bg-rose-600 text-rose-300 hover:text-white text-xs font-semibold rounded-xl border border-rose-500/40 flex items-center space-x-1.5 transition"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    <span>Reject</span>
                  </button>

                  <button
                    onClick={handleApprove}
                    disabled={isSubmitting || isUploader}
                    title={isUploader ? 'Self-approval is forbidden by dual control policy' : 'Approve document'}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold rounded-xl flex items-center space-x-1.5 shadow-md shadow-emerald-900/20 transition"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Approve Document</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Confirmation Dialog for Document Rejection */}
      {isRejectModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
            <div className="flex items-center space-x-2 text-rose-400">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <h3 className="text-base font-semibold">Confirm Document Rejection</h3>
            </div>
            <p className="text-xs text-slate-400">
              Rejection is an irreversible regulatory action. You must provide a clear reason for the audit trail.
            </p>
            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1">
                Mandatory Rejection Reason *
              </label>
              <textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="e.g. Unverified merchant, math discrepancy exceeding threshold, invalid tax invoice format..."
                rows={3}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-rose-500"
              />
            </div>
            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                onClick={() => setIsRejectModalOpen(false)}
                className="px-4 py-2 bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs font-medium rounded-xl transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReject}
                disabled={!rejectionReason.trim() || isSubmitting}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition flex items-center space-x-1.5"
              >
                <span>Confirm Rejection</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
