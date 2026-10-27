import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CheckSquare,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import { DocumentExtractionModal } from '../components/documents/DocumentExtractionModal';
import { apiClient } from '../services/api';
import { DocumentItem } from '../types/document';
import { ReviewQueueItem } from '../types/extraction';

export const ReviewQueuePage: React.FC = () => {
  const [queueItems, setQueueItems] = useState<ReviewQueueItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>('');
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [isExtractionModalOpen, setIsExtractionModalOpen] = useState<boolean>(false);

  const fetchReviewQueue = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const items = await apiClient.getReviewQueue(1, 50);
      setQueueItems(items);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve review queue.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReviewQueue();
  }, [fetchReviewQueue]);

  const handleOpenReview = async (item: ReviewQueueItem) => {
    try {
      // Fetch full document details
      const doc = await apiClient.getDocument(item.document_id);
      setSelectedDoc(doc);
      setIsExtractionModalOpen(true);
    } catch (err: any) {
      setError(err.message || 'Failed to open document for review.');
    }
  };

  const filteredItems = queueItems.filter((item) => {
    if (!search.trim()) return true;
    const query = search.toLowerCase();
    return (
      item.document_title.toLowerCase().includes(query) ||
      item.filename.toLowerCase().includes(query) ||
      item.document_type.toLowerCase().includes(query) ||
      item.review_reasons.some((r) => r.toLowerCase().includes(query))
    );
  });

  const mathDiscrepanciesCount = queueItems.filter((item) =>
    item.review_reasons.some((r) => r.toLowerCase().includes('discrepancy') || r.toLowerCase().includes('mathematical'))
  ).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
            <CheckSquare className="w-7 h-7 text-amber-400" />
            <span>Human-in-the-Loop Review Queue</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Reconcile low-confidence extractions, ledger mismatches, and compliance discrepancies.
          </p>
        </div>

        <button
          onClick={fetchReviewQueue}
          disabled={isLoading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium border border-slate-700/80 transition disabled:opacity-50 self-start sm:self-auto"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Queue</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center gap-4">
          <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold font-mono text-slate-100">
              {queueItems.length}
            </div>
            <div className="text-xs text-slate-400">Total Items Requiring Audit</div>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center gap-4">
          <div className="p-3 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold font-mono text-slate-100">
              {mathDiscrepanciesCount}
            </div>
            <div className="text-xs text-slate-400">Ledger / Math Discrepancies</div>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center gap-4">
          <div className="p-3 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold font-mono text-slate-100">
              {queueItems.length > 0
                ? `${Math.round(
                    (queueItems.reduce((acc, i) => acc + i.confidence_score, 0) /
                      queueItems.length) *
                      100
                  )}%`
                : '100%'}
            </div>
            <div className="text-xs text-slate-400">Avg Queue Confidence (Uncalibrated)</div>
          </div>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search review items by title, filename, or flagged reason..."
            className="w-full pl-10 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-amber-500"
          />
        </div>
      </div>

      {/* Queue Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <RefreshCw className="w-7 h-7 animate-spin text-amber-400 mb-3" />
            <p className="text-sm">Scanning organization filings for compliance discrepancies...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="text-center py-20 px-4">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h3 className="text-base font-semibold text-slate-200 mb-1">
              Review Queue Clear
            </h3>
            <p className="text-sm text-slate-400 max-w-sm mx-auto">
              All financial filings have been verified, signed off, or have met the autonomous
              confidence threshold.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800 text-xs uppercase tracking-wider">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">Document</th>
                  <th className="py-3.5 px-4 font-semibold">Category</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Extracted Amount</th>
                  <th className="py-3.5 px-4 font-semibold text-center">Confidence</th>
                  <th className="py-3.5 px-4 font-semibold">Discrepancy / Review Reason</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {filteredItems.map((item) => (
                  <tr key={item.extraction_id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3.5 px-4">
                      <div>
                        <div className="font-medium text-slate-100 hover:text-amber-400 cursor-pointer transition">
                          {item.document_title}
                        </div>
                        <div className="text-xs font-mono text-slate-500">{item.filename}</div>
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                        {item.document_type}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-right font-mono font-medium">
                      {item.total_amount != null ? (
                        <span className="text-slate-100">
                          {item.currency || '$'}{' '}
                          {item.total_amount.toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 text-center">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-mono font-bold border ${
                          item.confidence_score >= 0.8
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : item.confidence_score >= 0.7
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                        }`}
                      >
                        {Math.round(item.confidence_score * 100)}%
                      </span>
                    </td>

                    <td className="py-3.5 px-4">
                      <div className="max-w-md">
                        {item.review_reasons.length > 0 ? (
                          <div className="text-xs text-amber-300/90 flex items-start gap-1.5">
                            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-amber-400" />
                            <span className="truncate">{item.review_reasons[0]}</span>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500">Low confidence threshold</span>
                        )}
                        {item.review_reasons.length > 1 && (
                          <div className="text-[11px] text-slate-500 mt-0.5">
                            +{item.review_reasons.length - 1} more issue(s)
                          </div>
                        )}
                      </div>
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => handleOpenReview(item)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs font-medium transition"
                      >
                        <span>Audit & Resolve</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Extraction & Review Modal */}
      <DocumentExtractionModal
        document={selectedDoc}
        isOpen={isExtractionModalOpen}
        onClose={() => {
          setIsExtractionModalOpen(false);
          setSelectedDoc(null);
        }}
        onUpdateSuccess={fetchReviewQueue}
      />
    </div>
  );
};
