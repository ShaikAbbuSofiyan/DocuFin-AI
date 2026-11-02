import React, { useState, useEffect } from 'react';
import {
  X,
  Search,
  RefreshCw,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { apiClient } from '../../services/api';
import { AuditLogItem, PaginatedAuditLogResponse } from '../../types/audit';

interface AuditLogModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuditLogModal: React.FC<AuditLogModalProps> = ({ isOpen, onClose }) => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [actionFilter, setActionFilter] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);

  const pageSize = 20;

  useEffect(() => {
    if (isOpen) {
      loadAuditLogs();
    }
  }, [isOpen, page, actionFilter]);

  const loadAuditLogs = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res: PaginatedAuditLogResponse = await apiClient.getAuditLogs({
        page,
        page_size: pageSize,
        action: actionFilter || undefined,
        search: search.trim() || undefined,
      });
      setLogs(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages || 1);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch audit logs.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadAuditLogs();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 bg-slate-900 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-indigo-950 border border-indigo-500/40 rounded-xl text-indigo-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                <span>Regulatory Audit Trail & Compliance Log</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
                  {total} Events
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Immutable, append-only historical log of all document reviews, state changes, and decisions.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filter & Search Toolbar */}
        <div className="p-4 border-b border-slate-800/80 bg-slate-900/60 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <form onSubmit={handleSearchSubmit} className="flex items-center space-x-2 flex-1 max-w-md">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search action, actor email, or resource ID..."
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-950 border border-slate-700 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition"
            >
              Search
            </button>
          </form>

          <div className="flex items-center space-x-2">
            <select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(1);
              }}
              className="px-3 py-1.5 text-xs bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Actions</option>
              <option value="DOCUMENT_APPROVED">DOCUMENT_APPROVED</option>
              <option value="DOCUMENT_REJECTED">DOCUMENT_REJECTED</option>
              <option value="EXTRACTION_FIELD_CORRECTED">EXTRACTION_FIELD_CORRECTED</option>
              <option value="REVIEW_TASK_ASSIGNED">REVIEW_TASK_ASSIGNED</option>
              <option value="REVIEW_TASK_CREATED">REVIEW_TASK_CREATED</option>
            </select>

            <button
              onClick={loadAuditLogs}
              disabled={isLoading}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
              title="Refresh Logs"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Content Table */}
        <div className="flex-1 overflow-y-auto">
          {error && (
            <div className="m-4 p-3 bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs rounded-xl">
              {error}
            </div>
          )}

          {isLoading ? (
            <div className="flex items-center justify-center h-64 text-xs text-slate-400">
              <RefreshCw className="w-5 h-5 animate-spin mr-2 text-indigo-400" />
              Loading audit logs...
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-16 text-slate-500 text-xs">
              No audit log events match your query.
            </div>
          ) : (
            <div className="divide-y divide-slate-800/80">
              {logs.map((item) => {
                const isExpanded = expandedLogId === item.id;
                return (
                  <div
                    key={item.id}
                    onClick={() => setExpandedLogId(isExpanded ? null : item.id)}
                    className="p-4 hover:bg-slate-800/40 transition cursor-pointer text-xs"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide border ${
                            item.action.includes('APPROVED')
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                              : item.action.includes('REJECTED')
                              ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                              : item.action.includes('CORRECTED')
                              ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30'
                              : 'bg-slate-800 text-slate-300 border-slate-700'
                          }`}
                        >
                          {item.action}
                        </span>
                        <span className="font-medium text-slate-200">
                          {item.resource_type}:{' '}
                          <span className="font-mono text-slate-400">{item.resource_id}</span>
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500 font-mono">
                        {new Date(item.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>
                        Actor:{' '}
                        <span className="text-slate-300 font-mono">
                          {item.user_email || item.user_id || 'System'}
                        </span>
                      </span>
                      <span className="text-[10px] text-indigo-400 hover:underline">
                        {isExpanded ? 'Hide Details' : 'View Payload'}
                      </span>
                    </div>

                    {isExpanded && item.details && (
                      <div className="mt-2.5 p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto">
                        <pre>{JSON.stringify(item.details, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Pagination Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between shrink-0 text-xs text-slate-400">
          <span>
            Page {page} of {totalPages} ({total} total entries)
          </span>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 transition"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 transition"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
