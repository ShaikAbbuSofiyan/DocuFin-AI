import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  FileSpreadsheet,
  Info,
  Loader2,
  Plus,
  RefreshCw,
  Save,
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
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [analystNotes, setAnalystNotes] = useState<string>('');

  useEffect(() => {
    if (isOpen && doc) {
      loadExtraction();
    } else {
      setExtraction(null);
      setFormData({});
      setError(null);
      setSuccessMessage(null);
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
    } catch (err: any) {
      if (err.status === 404) {
        // Document has not yet been extracted; prompt to run extraction
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
      setSuccessMessage('Structured financial extraction completed successfully.');
      setTimeout(() => setSuccessMessage(null), 4000);
      if (onUpdateSuccess) onUpdateSuccess();
    } catch (err: any) {
      setError(err.message || 'Extraction failed. Please verify document OCR text.');
    } finally {
      setIsExtracting(false);
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
      setSuccessMessage(
        decisionStatus === 'APPROVED'
          ? 'Extraction verified and signed off for regulatory compliance.'
          : decisionStatus === 'REJECTED'
          ? 'Extraction rejected.'
          : 'Extraction modifications saved successfully.'
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-5xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-slate-100">{doc.title}</h2>
                {extraction && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    {extraction.document_type}
                  </span>
                )}
                {extraction?.status && (
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider ${
                      extraction.status === 'APPROVED'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : extraction.status === 'REVIEW_REQUIRED'
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                        : 'bg-slate-800 text-slate-300'
                    }`}
                  >
                    {extraction.status}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">{doc.filename}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {extraction && (
              <div className="text-right mr-2 hidden sm:block">
                <div className="text-[11px] text-slate-400 uppercase tracking-wider">
                  Overall Confidence
                </div>
                <div className="flex items-center gap-1.5 justify-end">
                  <span
                    className={`text-sm font-mono font-bold ${
                      extraction.confidence_score >= 0.8
                        ? 'text-emerald-400'
                        : extraction.confidence_score >= 0.7
                        ? 'text-amber-400'
                        : 'text-rose-400'
                    }`}
                  >
                    {Math.round(extraction.confidence_score * 100)}%
                  </span>
                  <span className="text-[10px] text-slate-500" title="Heuristic scoring only. Not calibrated.">
                    (uncalibrated)
                  </span>
                </div>
              </div>
            )}
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Banners */}
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
          <div className="p-4 bg-amber-500/10 border-b border-amber-500/20 text-amber-200 text-xs">
            <div className="flex items-center gap-2 font-semibold text-amber-300 mb-1">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <span>Human-in-the-Loop Review Flagged</span>
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
              <p className="text-sm">Retrieving structured financial entities...</p>
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
                bank balances, ledger reconciliations, or expense claims directly from the OCR text.
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
                  <span>Extract Structured Data</span>
                </button>
              </div>
            </div>
          ) : (
            /* Structured Form Content */
            <div className="space-y-6">
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

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerExtraction(true)}
                    disabled={isExtracting}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isExtracting ? 'animate-spin' : ''}`} />
                    <span>Re-run Extraction</span>
                  </button>
                </div>
              </div>

              {/* Document Type Specific Forms */}
              {extraction.document_type === 'INVOICE' && (
                <div className="space-y-6">
                  <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                    Invoice Summary Fields
                  </h4>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {/* Invoice Number */}
                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium">Invoice Number</label>
                      <input
                        type="text"
                        value={formData.invoice_number || ''}
                        onChange={(e) => handleFieldChange('invoice_number', e.target.value)}
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        placeholder="null"
                      />
                      {renderFieldAuditPill('invoice_number')}
                    </div>

                    {/* Vendor */}
                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium">Vendor</label>
                      <input
                        type="text"
                        value={formData.vendor || ''}
                        onChange={(e) => handleFieldChange('vendor', e.target.value)}
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                        placeholder="null"
                      />
                      {renderFieldAuditPill('vendor')}
                    </div>

                    {/* Invoice Date */}
                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium">Invoice Date</label>
                      <input
                        type="text"
                        value={formData.invoice_date || ''}
                        onChange={(e) => handleFieldChange('invoice_date', e.target.value)}
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        placeholder="YYYY-MM-DD"
                      />
                      {renderFieldAuditPill('invoice_date')}
                    </div>

                    {/* Due Date */}
                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium">Due Date</label>
                      <input
                        type="text"
                        value={formData.due_date || ''}
                        onChange={(e) => handleFieldChange('due_date', e.target.value)}
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        placeholder="YYYY-MM-DD"
                      />
                      {renderFieldAuditPill('due_date')}
                    </div>

                    {/* Currency */}
                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium">Currency</label>
                      <input
                        type="text"
                        value={formData.currency || ''}
                        onChange={(e) => handleFieldChange('currency', e.target.value)}
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        placeholder="USD"
                      />
                      {renderFieldAuditPill('currency')}
                    </div>

                    {/* Subtotal */}
                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium">Subtotal</label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.subtotal ?? ''}
                        onChange={(e) =>
                          handleFieldChange(
                            'subtotal',
                            e.target.value === '' ? null : parseFloat(e.target.value)
                          )
                        }
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        placeholder="0.00"
                      />
                      {renderFieldAuditPill('subtotal')}
                    </div>

                    {/* Tax */}
                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium">Tax</label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.tax ?? ''}
                        onChange={(e) =>
                          handleFieldChange(
                            'tax',
                            e.target.value === '' ? null : parseFloat(e.target.value)
                          )
                        }
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        placeholder="0.00"
                      />
                      {renderFieldAuditPill('tax')}
                    </div>

                    {/* Total */}
                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium font-semibold text-emerald-400">
                        Total Amount
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.total ?? ''}
                        onChange={(e) =>
                          handleFieldChange(
                            'total',
                            e.target.value === '' ? null : parseFloat(e.target.value)
                          )
                        }
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-emerald-400 font-mono font-bold focus:outline-none focus:border-emerald-500"
                        placeholder="0.00"
                      />
                      {renderFieldAuditPill('total')}
                    </div>
                  </div>

                  {/* Line Items Table */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                        Itemized Line Items
                      </h4>
                      <button
                        type="button"
                        onClick={handleAddLineItem}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 transition"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>Add Row</span>
                      </button>
                    </div>

                    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/40">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                          <tr>
                            <th className="py-2.5 px-3">Description</th>
                            <th className="py-2.5 px-3 w-24">Qty</th>
                            <th className="py-2.5 px-3 w-32">Unit Price</th>
                            <th className="py-2.5 px-3 w-32">Total</th>
                            <th className="py-2.5 px-2 w-10"></th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 text-slate-300">
                          {(formData.line_items || []).map((item: any, idx: number) => (
                            <tr key={idx} className="hover:bg-slate-800/30">
                              <td className="p-2">
                                <input
                                  type="text"
                                  value={item.description || ''}
                                  onChange={(e) =>
                                    handleLineItemChange(idx, 'description', e.target.value)
                                  }
                                  className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                                />
                              </td>
                              <td className="p-2">
                                <input
                                  type="number"
                                  value={item.quantity ?? ''}
                                  onChange={(e) =>
                                    handleLineItemChange(
                                      idx,
                                      'quantity',
                                      e.target.value === '' ? null : parseFloat(e.target.value)
                                    )
                                  }
                                  className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-slate-100 font-mono text-right focus:outline-none focus:border-emerald-500"
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
                                      e.target.value === '' ? null : parseFloat(e.target.value)
                                    )
                                  }
                                  className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-slate-100 font-mono text-right focus:outline-none focus:border-emerald-500"
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
                                      e.target.value === '' ? null : parseFloat(e.target.value)
                                    )
                                  }
                                  className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-slate-100 font-mono text-right focus:outline-none focus:border-emerald-500"
                                />
                              </td>
                              <td className="p-2 text-center">
                                <button
                                  type="button"
                                  onClick={() => handleDeleteLineItem(idx)}
                                  className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition"
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

              {/* Bank Statement Form */}
              {extraction.document_type === 'BANK_STATEMENT' && (
                <div className="space-y-6">
                  <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                    Bank Account & Balance Summary
                  </h4>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium">Opening Balance</label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.opening_balance ?? ''}
                        onChange={(e) =>
                          handleFieldChange(
                            'opening_balance',
                            e.target.value === '' ? null : parseFloat(e.target.value)
                          )
                        }
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        placeholder="0.00"
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
                            e.target.value === '' ? null : parseFloat(e.target.value)
                          )
                        }
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-emerald-400 font-mono font-bold focus:outline-none focus:border-emerald-500"
                        placeholder="0.00"
                      />
                      {renderFieldAuditPill('closing_balance')}
                    </div>

                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium">Statement Period</label>
                      <input
                        type="text"
                        value={
                          typeof formData.statement_period === 'string'
                            ? formData.statement_period
                            : formData.statement_period?.raw_period || ''
                        }
                        onChange={(e) => handleFieldChange('statement_period', e.target.value)}
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                        placeholder="YYYY-MM-DD to YYYY-MM-DD"
                      />
                      {renderFieldAuditPill('statement_period')}
                    </div>
                  </div>

                  {/* Transactions Table */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                      Ledger Transactions
                    </h4>
                    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/40">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                          <tr>
                            <th className="py-2.5 px-3 w-32">Date</th>
                            <th className="py-2.5 px-3">Description</th>
                            <th className="py-2.5 px-3 w-28 text-right">Debit</th>
                            <th className="py-2.5 px-3 w-28 text-right">Credit</th>
                            <th className="py-2.5 px-3 w-32 text-right">Running Balance</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 text-slate-300">
                          {(formData.transactions || []).map((t: any, idx: number) => (
                            <tr key={idx} className="hover:bg-slate-800/30">
                              <td className="p-2">
                                <input
                                  type="text"
                                  value={t.transaction_date || ''}
                                  onChange={(e) =>
                                    handleTransactionChange(idx, 'transaction_date', e.target.value)
                                  }
                                  className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                                />
                              </td>
                              <td className="p-2">
                                <input
                                  type="text"
                                  value={t.description || ''}
                                  onChange={(e) =>
                                    handleTransactionChange(idx, 'description', e.target.value)
                                  }
                                  className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
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
                                      e.target.value === '' ? null : parseFloat(e.target.value)
                                    )
                                  }
                                  className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-rose-400 font-mono text-right focus:outline-none focus:border-emerald-500"
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
                                      e.target.value === '' ? null : parseFloat(e.target.value)
                                    )
                                  }
                                  className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-emerald-400 font-mono text-right focus:outline-none focus:border-emerald-500"
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
                                      e.target.value === '' ? null : parseFloat(e.target.value)
                                    )
                                  }
                                  className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-slate-100 font-mono text-right focus:outline-none focus:border-emerald-500"
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

              {/* Expense Report Form */}
              {extraction.document_type === 'EXPENSE_REPORT' && (
                <div className="space-y-6">
                  <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                    Expense Claim Fields
                  </h4>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
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
                      <label className="text-xs text-slate-400 font-medium">Expense Date</label>
                      <input
                        type="text"
                        value={formData.expense_date || ''}
                        onChange={(e) => handleFieldChange('expense_date', e.target.value)}
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                      />
                      {renderFieldAuditPill('expense_date')}
                    </div>

                    <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                      <label className="text-xs text-slate-400 font-medium text-emerald-400">
                        Total Amount
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.amount ?? ''}
                        onChange={(e) =>
                          handleFieldChange(
                            'amount',
                            e.target.value === '' ? null : parseFloat(e.target.value)
                          )
                        }
                        className="w-full mt-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-emerald-400 font-mono font-bold focus:outline-none focus:border-emerald-500"
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
                  placeholder="Record cross-checking methodology, discrepancy explanation, or purchase order cross-reference..."
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>
          )}
        </div>

        {/* Modal Actions Footer */}
        {extraction && (
          <div className="p-4 border-t border-slate-800 bg-slate-900/80 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-slate-400 flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-slate-500" />
              <span>Editing fields will mark modified entities with MANUAL extraction method.</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleSave()}
                disabled={isSaving}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs transition disabled:opacity-50"
              >
                {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                <span>Save Changes</span>
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
