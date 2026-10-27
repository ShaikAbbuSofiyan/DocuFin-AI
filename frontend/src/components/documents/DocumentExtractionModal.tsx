import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  FileSpreadsheet,
  Filter,
  History,
  Info,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Scale,
  ShieldAlert,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import { apiClient } from '../../services/api';
import { DocumentItem } from '../../types/document';
import {
  DocumentExtractionResponse,
  DocumentExtractionUpdate,
  DocumentType,
  FieldMetadata,
  InvoiceLineItem,
  BankTransaction,
  ValidationRuleResult,
  ValidationRunResponse,
  ValidationSummary,
} from '../../types/extraction';

interface DocumentExtractionModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: DocumentItem | null;
  onUpdateSuccess?: () => void;
}

export const DocumentExtractionModal: React.FC<DocumentExtractionModalProps> = ({
  isOpen,
  onClose,
  document: doc,
  onUpdateSuccess,
}) => {
  const [extraction, setExtraction] = useState<DocumentExtractionResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [analystNotes, setAnalystNotes] = useState<string>('');

  // Phase 6: Validation Engine State
  const [validationSummary, setValidationSummary] = useState<ValidationSummary | null>(null);
  const [validationHistory, setValidationHistory] = useState<ValidationRunResponse[]>([]);
  const [selectedSeverity, setSelectedSeverity] = useState<'ALL' | 'ERROR' | 'WARNING' | 'INFO'>('ALL');
  const [showHistory, setShowHistory] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen && doc) {
      loadExtraction();
    } else {
      setExtraction(null);
      setFormData({});
      setValidationSummary(null);
      setValidationHistory([]);
      setError(null);
      setSuccessMessage(null);
      setShowHistory(false);
    }
  }, [isOpen, doc]);

  const loadExtraction = async () => {
    if (!doc) return;
    try {
      setIsLoading(true);
      setError(null);
      const res = await apiClient.getDocumentExtraction(doc.id);
      setExtraction(res);
      setFormData(res.extracted_data || {});
      setAnalystNotes('');

      // Load latest validation run
      try {
        const valRes = await apiClient.getLatestValidation(doc.id);
        if (valRes) {
          setValidationSummary({
            is_valid: valRes.is_valid,
            has_warnings: valRes.warning_count > 0,
            error_count: valRes.error_count,
            warning_count: valRes.warning_count,
            info_count: valRes.info_count,
            results: valRes.results,
          });
        }
      } catch {
        // Fallback: If structured validation_errors exists on extraction
        if (Array.isArray(res.validation_errors) && res.validation_errors.length > 0) {
          const structuredRules = res.validation_errors.filter(
            (e): e is ValidationRuleResult => typeof e === 'object' && e !== null && 'rule_id' in e
          );
          if (structuredRules.length > 0) {
            setValidationSummary({
              is_valid: res.is_valid,
              has_warnings: structuredRules.some((r) => r.severity === 'WARNING' && !r.is_passed),
              error_count: structuredRules.filter((r) => r.severity === 'ERROR' && !r.is_passed).length,
              warning_count: structuredRules.filter((r) => r.severity === 'WARNING' && !r.is_passed).length,
              info_count: structuredRules.filter((r) => r.severity === 'INFO').length,
              results: structuredRules,
            });
          }
        }
      }

      // Load validation history
      try {
        const historyRes = await apiClient.getValidationHistory(doc.id);
        setValidationHistory(historyRes);
      } catch {
        setValidationHistory([]);
      }
    } catch (err: any) {
      if (err.status === 404) {
        setExtraction(null);
      } else {
        setError(err.message || 'Failed to load structured financial data.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleTriggerExtraction = async (force = false, preferredType?: DocumentType) => {
    if (!doc) return;
    try {
      setIsExtracting(true);
      setError(null);
      const res = await apiClient.extractDocument(doc.id, force, preferredType);
      setExtraction(res);
      setFormData(res.extracted_data || {});
      setSuccessMessage('Structured financial extraction and rule validation completed.');
      setTimeout(() => setSuccessMessage(null), 4000);

      // Refresh validation after extraction
      const valRes = await apiClient.getLatestValidation(doc.id).catch(() => null);
      if (valRes) {
        setValidationSummary({
          is_valid: valRes.is_valid,
          has_warnings: valRes.warning_count > 0,
          error_count: valRes.error_count,
          warning_count: valRes.warning_count,
          info_count: valRes.info_count,
          results: valRes.results,
        });
      }
      const hist = await apiClient.getValidationHistory(doc.id).catch(() => []);
      setValidationHistory(hist);

      if (onUpdateSuccess) onUpdateSuccess();
    } catch (err: any) {
      setError(err.message || 'Extraction failed. Please verify document OCR text.');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleRevalidate = async () => {
    if (!doc) return;
    try {
      setIsValidating(true);
      setError(null);
      const summary = await apiClient.validateDocumentExtraction(doc.id);
      setValidationSummary(summary);

      // Refresh extraction to sync status and review flags
      const ext = await apiClient.getDocumentExtraction(doc.id);
      setExtraction(ext);

      // Refresh history
      const hist = await apiClient.getValidationHistory(doc.id);
      setValidationHistory(hist);

      setSuccessMessage('Financial business rules re-evaluated successfully.');
      setTimeout(() => setSuccessMessage(null), 3000);
      if (onUpdateSuccess) onUpdateSuccess();
    } catch (err: any) {
      setError(err.message || 'Rule validation failed.');
    } finally {
      setIsValidating(false);
    }
  };

  const handleFieldChange = (field: string, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleLineItemChange = (index: number, key: keyof InvoiceLineItem, value: any) => {
    const items = [...(formData.line_items || [])];
    items[index] = { ...items[index], [key]: value };
    handleFieldChange('line_items', items);
  };

  const handleAddLineItem = () => {
    const items = [...(formData.line_items || [])];
    items.push({ description: 'New Line Item', quantity: 1, unit_price: 0, total_price: 0 });
    handleFieldChange('line_items', items);
  };

  const handleDeleteLineItem = (index: number) => {
    const items = (formData.line_items || []).filter((_: any, i: number) => i !== index);
    handleFieldChange('line_items', items);
  };

  const handleTransactionChange = (index: number, key: keyof BankTransaction, value: any) => {
    const items = [...(formData.transactions || [])];
    items[index] = { ...items[index], [key]: value };
    handleFieldChange('transactions', items);
  };

  const handleSave = async (decisionStatus?: string) => {
    if (!doc) return;
    try {
      setIsSaving(true);
      setError(null);
      const payload: DocumentExtractionUpdate = {
        extracted_data: formData,
        status: decisionStatus,
        analyst_notes: analystNotes || undefined,
      };
      const res = await apiClient.updateDocumentExtraction(doc.id, payload);
      setExtraction(res);

      // Refresh validation after authorized correction
      const valRes = await apiClient.getLatestValidation(doc.id).catch(() => null);
      if (valRes) {
        setValidationSummary({
          is_valid: valRes.is_valid,
          has_warnings: valRes.warning_count > 0,
          error_count: valRes.error_count,
          warning_count: valRes.warning_count,
          info_count: valRes.info_count,
          results: valRes.results,
        });
      }
      const hist = await apiClient.getValidationHistory(doc.id).catch(() => []);
      setValidationHistory(hist);

      setSuccessMessage(
        decisionStatus === 'APPROVED'
          ? 'Extraction verified and signed off for regulatory compliance.'
          : decisionStatus === 'REJECTED'
          ? 'Extraction rejected.'
          : 'Extraction modifications saved and rules re-validated.'
      );
      setTimeout(() => setSuccessMessage(null), 4000);
      if (onUpdateSuccess) onUpdateSuccess();
    } catch (err: any) {
      setError(err.message || 'Failed to save extraction updates.');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen || !doc) return null;

  const getConfidenceBadgeColor = (conf: number) => {
    if (conf >= 0.85) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    if (conf >= 0.70) return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
  };

  const renderFieldAuditPill = (fieldName: string) => {
    const meta: FieldMetadata | undefined = extraction?.field_metadata?.[fieldName];
    if (!meta) return null;

    const confPct = Math.round((meta.confidence || 0) * 100);
    return (
      <div className="flex items-center gap-1.5 mt-1 text-[11px]">
        {meta.source_page && (
          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
            Pg {meta.source_page}
          </span>
        )}
        <span
          className={`px-1.5 py-0.5 rounded border font-mono ${getConfidenceBadgeColor(
            meta.confidence
          )}`}
          title="Field heuristic confidence (uncalibrated score)"
        >
          {confPct}%
        </span>
        <span className="text-slate-500 uppercase tracking-wider text-[10px]">
          {meta.extraction_method === 'DETERMINISTIC_FALLBACK'
            ? 'Regex'
            : meta.extraction_method}
        </span>
      </div>
    );
  };

  // Filter validation results by severity
  const filteredRuleResults = (validationSummary?.results || []).filter((rule) => {
    if (selectedSeverity === 'ALL') return true;
    return rule.severity === selectedSeverity;
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-7xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Scale className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-slate-100">
                  {doc.title || doc.filename}
                </h2>
                {extraction && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    {extraction.document_type}
                  </span>
                )}
                {extraction && (
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium border ${
                      extraction.status === 'APPROVED'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : extraction.status === 'REJECTED'
                        ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}
                  >
                    {extraction.status}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                Phase 5 Extraction & Phase 6 Deterministic Business Rules Engine
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {extraction && (
              <button
                onClick={() => handleTriggerExtraction(true)}
                disabled={isExtracting}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition disabled:opacity-50"
                title="Re-run extraction and business rule checks"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isExtracting ? 'animate-spin' : ''}`} />
                <span>Re-run Extraction</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Global Notifications */}
        {error && (
          <div className="p-4 bg-rose-500/10 border-b border-rose-500/20 text-rose-300 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="p-4 bg-emerald-500/10 border-b border-emerald-500/20 text-emerald-300 text-sm flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Discrepancy & Review Warning Banner */}
        {extraction && extraction.needs_review && (
          <div className="p-3.5 bg-amber-500/10 border-b border-amber-500/20 text-amber-200 text-xs">
            <div className="flex items-center gap-2 font-semibold text-amber-300 mb-1">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <span>Human-in-the-Loop Review Required</span>
            </div>
            <ul className="list-disc list-inside space-y-0.5 text-amber-300/80">
              {extraction.review_reasons.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-500 mb-3" />
              <p className="text-sm">Retrieving structured financial entities & rule evaluations...</p>
            </div>
          ) : !extraction ? (
            /* Empty State: Prompt Extraction */
            <div className="text-center py-16 px-4">
              <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center mx-auto mb-4 text-indigo-400">
                <FileSpreadsheet className="w-8 h-8" />
              </div>
              <h3 className="text-base font-semibold text-slate-200 mb-2">
                Structured Financial Extraction Not Yet Run
              </h3>
              <p className="text-sm text-slate-400 max-w-md mx-auto mb-6">
                Run financial document intelligence to extract verified accounts payable invoices,
                bank balances, ledger reconciliations, or expense claims with deterministic validation.
              </p>
              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={() => handleTriggerExtraction(false)}
                  disabled={isExtracting}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-lg shadow-emerald-950 transition disabled:opacity-50"
                >
                  {isExtracting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Sparkles className="w-4 h-4" />
                  )}
                  <span>Extract & Validate Structured Data</span>
                </button>
              </div>
            </div>
          ) : (
            /* Two-Column Layout: Left (Editable Form) + Right (Validation Results Beside Fields) */
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left Column: Editable Financial Form (7 cols) */}
              <div className="lg:col-span-7 space-y-6">
                {/* Telemetry Bar */}
                <div className="flex flex-wrap items-center justify-between p-3.5 bg-slate-950/60 rounded-xl border border-slate-800/80 text-xs text-slate-400 gap-3">
                  <div className="flex items-center gap-4">
                    <div>
                      <span className="text-slate-500">Method: </span>
                      <span className="font-semibold text-slate-300">
                        {extraction.extraction_method}
                      </span>
                    </div>
                    {extraction.llm_provider && (
                      <div>
                        <span className="text-slate-500">Provider: </span>
                        <span className="font-semibold text-indigo-400 uppercase">
                          {extraction.llm_provider}
                        </span>
                      </div>
                    )}
                    {extraction.token_usage && (
                      <div>
                        <span className="text-slate-500">Tokens: </span>
                        <span className="font-mono text-slate-300">
                          {extraction.token_usage.total_tokens}
                        </span>
                      </div>
                    )}
                  </div>
                  <div>
                    <span className="text-slate-500">Confidence: </span>
                    <span className="font-mono font-semibold text-slate-200">
                      {Math.round(extraction.confidence_score * 100)}%
                    </span>
                    <span className="text-slate-600 text-[10px] ml-1">(uncalibrated)</span>
                  </div>
                </div>

                {/* 1. INVOICE FORM */}
                {extraction.document_type === 'INVOICE' && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                      <span>Invoice Accounts Payable Fields</span>
                    </h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Invoice Number</label>
                        <input
                          type="text"
                          value={formData.invoice_number || ''}
                          onChange={(e) => handleFieldChange('invoice_number', e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('invoice_number')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Vendor / Issuer</label>
                        <input
                          type="text"
                          value={formData.vendor || ''}
                          onChange={(e) => handleFieldChange('vendor', e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('vendor')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Invoice Date</label>
                        <input
                          type="date"
                          value={formData.invoice_date || ''}
                          onChange={(e) => handleFieldChange('invoice_date', e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('invoice_date')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Due Date</label>
                        <input
                          type="date"
                          value={formData.due_date || ''}
                          onChange={(e) => handleFieldChange('due_date', e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('due_date')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Currency</label>
                        <input
                          type="text"
                          value={formData.currency || ''}
                          onChange={(e) => handleFieldChange('currency', e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('currency')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Subtotal</label>
                        <input
                          type="number"
                          step="0.01"
                          value={formData.subtotal ?? ''}
                          onChange={(e) =>
                            handleFieldChange(
                              'subtotal',
                              e.target.value ? parseFloat(e.target.value) : null
                            )
                          }
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('subtotal')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Tax</label>
                        <input
                          type="number"
                          step="0.01"
                          value={formData.tax ?? ''}
                          onChange={(e) =>
                            handleFieldChange(
                              'tax',
                              e.target.value ? parseFloat(e.target.value) : null
                            )
                          }
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('tax')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-emerald-500/30">
                        <label className="text-xs text-emerald-400 font-semibold">Total Amount</label>
                        <input
                          type="number"
                          step="0.01"
                          value={formData.total ?? ''}
                          onChange={(e) =>
                            handleFieldChange(
                              'total',
                              e.target.value ? parseFloat(e.target.value) : null
                            )
                          }
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-emerald-500/40 rounded-lg text-sm text-emerald-300 font-mono font-bold focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('total')}
                      </div>
                    </div>

                    {/* Line Items Table */}
                    <div className="space-y-2 mt-4">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-300">
                          Itemized Line Items ({formData.line_items?.length || 0})
                        </label>
                        <button
                          type="button"
                          onClick={handleAddLineItem}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          <span>Add Line</span>
                        </button>
                      </div>

                      <div className="border border-slate-800 rounded-xl overflow-hidden">
                        <table className="w-full text-left text-xs text-slate-300">
                          <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 font-medium">
                            <tr>
                              <th className="p-2.5">Description</th>
                              <th className="p-2.5 w-20">Qty</th>
                              <th className="p-2.5 w-28">Unit Price</th>
                              <th className="p-2.5 w-28">Total</th>
                              <th className="p-2.5 w-10 text-center"></th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 bg-slate-900/50">
                            {(formData.line_items || []).map((item: InvoiceLineItem, idx: number) => (
                              <tr key={idx} className="hover:bg-slate-800/30">
                                <td className="p-2">
                                  <input
                                    type="text"
                                    value={item.description || ''}
                                    onChange={(e) =>
                                      handleLineItemChange(idx, 'description', e.target.value)
                                    }
                                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 focus:outline-none focus:border-emerald-500"
                                  />
                                </td>
                                <td className="p-2">
                                  <input
                                    type="number"
                                    step="1"
                                    value={item.quantity ?? ''}
                                    onChange={(e) =>
                                      handleLineItemChange(
                                        idx,
                                        'quantity',
                                        e.target.value ? parseFloat(e.target.value) : null
                                      )
                                    }
                                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                                  />
                                </td>
                                <td className="p-2">
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={item.unit_price ?? ''}
                                    onChange={(e) =>
                                      handleLineItemChange(
                                        idx,
                                        'unit_price',
                                        e.target.value ? parseFloat(e.target.value) : null
                                      )
                                    }
                                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                                  />
                                </td>
                                <td className="p-2">
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={item.total_price ?? ''}
                                    onChange={(e) =>
                                      handleLineItemChange(
                                        idx,
                                        'total_price',
                                        e.target.value ? parseFloat(e.target.value) : null
                                      )
                                    }
                                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 font-mono font-semibold focus:outline-none focus:border-emerald-500"
                                  />
                                </td>
                                <td className="p-2 text-center">
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteLineItem(idx)}
                                    className="text-slate-500 hover:text-rose-400 transition"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}

                {/* 2. BANK STATEMENT FORM */}
                {extraction.document_type === 'BANK_STATEMENT' && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-200">
                      Bank Statement & Ledger Balances
                    </h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Opening Balance</label>
                        <input
                          type="number"
                          step="0.01"
                          value={formData.opening_balance ?? ''}
                          onChange={(e) =>
                            handleFieldChange(
                              'opening_balance',
                              e.target.value ? parseFloat(e.target.value) : null
                            )
                          }
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('opening_balance')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Closing Balance</label>
                        <input
                          type="number"
                          step="0.01"
                          value={formData.closing_balance ?? ''}
                          onChange={(e) =>
                            handleFieldChange(
                              'closing_balance',
                              e.target.value ? parseFloat(e.target.value) : null
                            )
                          }
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono font-bold focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('closing_balance')}
                      </div>
                    </div>

                    {/* Bank Transactions Register */}
                    <div className="space-y-2 mt-4">
                      <label className="text-xs font-semibold text-slate-300">
                        Transaction Register ({formData.transactions?.length || 0})
                      </label>

                      <div className="border border-slate-800 rounded-xl overflow-hidden max-h-72 overflow-y-auto">
                        <table className="w-full text-left text-xs text-slate-300">
                          <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 font-medium sticky top-0">
                            <tr>
                              <th className="p-2.5 w-28">Date</th>
                              <th className="p-2.5">Description</th>
                              <th className="p-2.5 w-24">Debit</th>
                              <th className="p-2.5 w-24">Credit</th>
                              <th className="p-2.5 w-28">Running Bal</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 bg-slate-900/50">
                            {(formData.transactions || []).map((t: BankTransaction, idx: number) => (
                              <tr key={idx} className="hover:bg-slate-800/30">
                                <td className="p-2">
                                  <input
                                    type="text"
                                    value={t.transaction_date || ''}
                                    onChange={(e) =>
                                      handleTransactionChange(idx, 'transaction_date', e.target.value)
                                    }
                                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 font-mono text-xs focus:outline-none focus:border-emerald-500"
                                  />
                                </td>
                                <td className="p-2">
                                  <input
                                    type="text"
                                    value={t.description || ''}
                                    onChange={(e) =>
                                      handleTransactionChange(idx, 'description', e.target.value)
                                    }
                                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs focus:outline-none focus:border-emerald-500"
                                  />
                                </td>
                                <td className="p-2">
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={t.debit ?? ''}
                                    onChange={(e) =>
                                      handleTransactionChange(
                                        idx,
                                        'debit',
                                        e.target.value ? parseFloat(e.target.value) : null
                                      )
                                    }
                                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-rose-300 font-mono text-xs focus:outline-none focus:border-emerald-500"
                                  />
                                </td>
                                <td className="p-2">
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={t.credit ?? ''}
                                    onChange={(e) =>
                                      handleTransactionChange(
                                        idx,
                                        'credit',
                                        e.target.value ? parseFloat(e.target.value) : null
                                      )
                                    }
                                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-emerald-300 font-mono text-xs focus:outline-none focus:border-emerald-500"
                                  />
                                </td>
                                <td className="p-2">
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={t.running_balance ?? ''}
                                    onChange={(e) =>
                                      handleTransactionChange(
                                        idx,
                                        'running_balance',
                                        e.target.value ? parseFloat(e.target.value) : null
                                      )
                                    }
                                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 font-mono font-semibold text-xs focus:outline-none focus:border-emerald-500"
                                  />
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}

                {/* 3. EXPENSE REPORT FORM */}
                {extraction.document_type === 'EXPENSE_REPORT' && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-200">
                      Corporate Expense Report Fields
                    </h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Expense Date</label>
                        <input
                          type="date"
                          value={formData.expense_date || ''}
                          onChange={(e) => handleFieldChange('expense_date', e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('expense_date')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Merchant / Payee</label>
                        <input
                          type="text"
                          value={formData.merchant || ''}
                          onChange={(e) => handleFieldChange('merchant', e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('merchant')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Category</label>
                        <input
                          type="text"
                          value={formData.category || ''}
                          onChange={(e) => handleFieldChange('category', e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('category')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Amount</label>
                        <input
                          type="number"
                          step="0.01"
                          value={formData.amount ?? ''}
                          onChange={(e) =>
                            handleFieldChange(
                              'amount',
                              e.target.value ? parseFloat(e.target.value) : null
                            )
                          }
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-emerald-300 font-mono font-bold focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('amount')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Currency</label>
                        <input
                          type="text"
                          value={formData.currency || ''}
                          onChange={(e) => handleFieldChange('currency', e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('currency')}
                      </div>

                      <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                        <label className="text-xs text-slate-400 font-medium">Business Purpose</label>
                        <input
                          type="text"
                          value={formData.description || ''}
                          onChange={(e) => handleFieldChange('description', e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                        />
                        {renderFieldAuditPill('description')}
                      </div>
                    </div>
                  </div>
                )}

                {/* Analyst Audit Notes */}
                <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
                  <label className="text-xs font-semibold text-slate-300">
                    Analyst Audit & Verification Notes
                  </label>
                  <textarea
                    rows={2}
                    value={analystNotes}
                    onChange={(e) => setAnalystNotes(e.target.value)}
                    placeholder="Record cross-checking methodology, mathematical reconciliation reason, or purchase order matching notes..."
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              {/* Right Column: Deterministic Business Rules & Validation Engine Panel (5 cols) */}
              <div className="lg:col-span-5 flex flex-col space-y-4 bg-slate-950/50 p-4 rounded-2xl border border-slate-800">
                {/* Validation Panel Header */}
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Scale className="w-4 h-4 text-emerald-400" />
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                      Validation Rules Engine
                    </h4>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setShowHistory(!showHistory)}
                      className={`p-1.5 rounded-lg border text-xs flex items-center gap-1 transition ${
                        showHistory
                          ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30'
                          : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                      }`}
                      title="Inspect validation audit history"
                    >
                      <History className="w-3.5 h-3.5" />
                      <span>{validationHistory.length}</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleRevalidate}
                      disabled={isValidating}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-medium transition disabled:opacity-50"
                      title="Re-run deterministic rules"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isValidating ? 'animate-spin' : ''}`} />
                      <span>Re-validate</span>
                    </button>
                  </div>
                </div>

                {/* Validation Status Summary Banner */}
                {validationSummary && (
                  <div
                    className={`p-3 rounded-xl border flex items-center justify-between text-xs ${
                      validationSummary.is_valid
                        ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                        : 'bg-rose-500/10 border-rose-500/20 text-rose-300'
                    }`}
                  >
                    <div className="flex items-center gap-2 font-medium">
                      {validationSummary.is_valid ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                      )}
                      <span>
                        {validationSummary.is_valid
                          ? 'Deterministic Validation Passed'
                          : `${validationSummary.error_count} Rule Violation(s) Detected`}
                      </span>
                    </div>

                    <div className="flex items-center gap-1 font-mono text-[11px]">
                      {validationSummary.error_count > 0 && (
                        <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 font-semibold">
                          {validationSummary.error_count} ERR
                        </span>
                      )}
                      {validationSummary.warning_count > 0 && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold">
                          {validationSummary.warning_count} WARN
                        </span>
                      )}
                      {validationSummary.info_count > 0 && (
                        <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 font-semibold">
                          {validationSummary.info_count} INFO
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Severity Filter Tabs */}
                <div className="flex items-center gap-1 p-1 bg-slate-900 rounded-xl border border-slate-800 text-xs">
                  <button
                    type="button"
                    onClick={() => setSelectedSeverity('ALL')}
                    className={`flex-1 py-1 px-2 rounded-lg text-center font-medium transition ${
                      selectedSeverity === 'ALL'
                        ? 'bg-slate-800 text-slate-100 shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    All ({validationSummary?.results.length || 0})
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedSeverity('ERROR')}
                    className={`flex-1 py-1 px-2 rounded-lg text-center font-medium transition ${
                      selectedSeverity === 'ERROR'
                        ? 'bg-rose-500/20 text-rose-300 font-semibold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Errors ({validationSummary?.error_count || 0})
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedSeverity('WARNING')}
                    className={`flex-1 py-1 px-2 rounded-lg text-center font-medium transition ${
                      selectedSeverity === 'WARNING'
                        ? 'bg-amber-500/20 text-amber-300 font-semibold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Warn ({validationSummary?.warning_count || 0})
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedSeverity('INFO')}
                    className={`flex-1 py-1 px-2 rounded-lg text-center font-medium transition ${
                      selectedSeverity === 'INFO'
                        ? 'bg-blue-500/20 text-blue-300 font-semibold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Info ({validationSummary?.info_count || 0})
                  </button>
                </div>

                {/* History Drawer View */}
                {showHistory ? (
                  <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
                    <div className="flex items-center justify-between text-xs text-slate-400 pb-1">
                      <span className="font-semibold text-slate-300">Historical Validation Runs</span>
                      <span>Total: {validationHistory.length}</span>
                    </div>

                    {validationHistory.length === 0 ? (
                      <p className="text-xs text-slate-500 text-center py-6">No historical runs recorded.</p>
                    ) : (
                      validationHistory.map((run, idx) => (
                        <div
                          key={run.id || idx}
                          className="p-3 bg-slate-900/80 rounded-xl border border-slate-800 text-xs space-y-1.5"
                        >
                          <div className="flex items-center justify-between">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                                run.is_valid
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              }`}
                            >
                              {run.is_valid ? 'PASSED' : `${run.error_count} ERRORS`}
                            </span>
                            <span className="text-[11px] text-slate-500 flex items-center gap-1 font-mono">
                              <Clock className="w-3 h-3" />
                              {new Date(run.created_at).toLocaleTimeString([], {
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-400 flex items-center justify-between">
                            <span>Trigger: {run.triggered_by}</span>
                            <span>{run.results?.length || 0} rules checked</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                ) : (
                  /* Rule Results Cards List */
                  <div className="space-y-2.5 max-h-[440px] overflow-y-auto pr-1">
                    {filteredRuleResults.length === 0 ? (
                      <div className="text-center py-10 text-slate-500 text-xs">
                        <Filter className="w-6 h-6 mx-auto mb-2 opacity-40" />
                        <p>No rule evaluations match filter "{selectedSeverity}".</p>
                      </div>
                    ) : (
                      filteredRuleResults.map((rule, idx) => {
                        const isErr = !rule.is_passed && rule.severity === 'ERROR';
                        const isWarn = !rule.is_passed && rule.severity === 'WARNING';
                        const isPassed = rule.is_passed;

                        return (
                          <div
                            key={rule.rule_id + idx}
                            className={`p-3 rounded-xl border transition text-xs space-y-1.5 ${
                              isErr
                                ? 'bg-rose-950/20 border-rose-500/30'
                                : isWarn
                                ? 'bg-amber-950/20 border-amber-500/30'
                                : isPassed
                                ? 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700'
                                : 'bg-slate-900/40 border-slate-800'
                            }`}
                          >
                            {/* Card Header */}
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                {isPassed ? (
                                  <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                                ) : isErr ? (
                                  <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                                ) : (
                                  <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                                )}
                                <span className="font-semibold text-slate-200">
                                  {rule.rule_name}
                                </span>
                              </div>

                              <div className="flex items-center gap-1.5">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                                    rule.severity === 'ERROR'
                                      ? 'bg-rose-500/20 text-rose-300'
                                      : rule.severity === 'WARNING'
                                      ? 'bg-amber-500/20 text-amber-300'
                                      : 'bg-blue-500/20 text-blue-300'
                                  }`}
                                >
                                  {rule.severity}
                                </span>
                              </div>
                            </div>

                            {/* Rule ID Pill */}
                            <div className="text-[10px] font-mono text-slate-500">
                              {rule.rule_id}
                            </div>

                            {/* Explanation */}
                            <p
                              className={`text-xs leading-relaxed ${
                                isErr
                                  ? 'text-rose-200/90'
                                  : isWarn
                                  ? 'text-amber-200/90'
                                  : 'text-slate-400'
                              }`}
                            >
                              {rule.explanation}
                            </p>

                            {/* Affected Fields Pills */}
                            {rule.affected_fields && rule.affected_fields.length > 0 && (
                              <div className="flex flex-wrap items-center gap-1 pt-1">
                                <span className="text-[10px] text-slate-500">Fields:</span>
                                {rule.affected_fields.map((f, fIdx) => (
                                  <span
                                    key={fIdx}
                                    className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-[10px] font-mono"
                                  >
                                    {f}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Modal Actions Footer */}
        {extraction && (
          <div className="p-4 border-t border-slate-800 bg-slate-900/80 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-slate-400 flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-slate-500" />
              <span>Editing fields will mark entities as MANUAL and immediately trigger re-validation.</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleSave()}
                disabled={isSaving}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs transition disabled:opacity-50"
              >
                {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                <span>Save & Validate</span>
              </button>

              <button
                type="button"
                onClick={() => handleSave('REJECTED')}
                disabled={isSaving}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 font-medium text-xs transition disabled:opacity-50"
              >
                <X className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>

              <button
                type="button"
                onClick={() => handleSave('APPROVED')}
                disabled={isSaving}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs shadow-lg shadow-emerald-950 transition disabled:opacity-50"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Approve & Sign Off</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
