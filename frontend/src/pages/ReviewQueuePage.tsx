import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CheckSquare,
  Clock,
  Layers,
  RefreshCw,
  Search,
  ShieldAlert,
  User,
} from 'lucide-react';
import { AuditLogModal } from '../components/review/AuditLogModal';
import { ReviewWorkspaceModal } from '../components/review/ReviewWorkspaceModal';
import { apiClient } from '../services/api';
import { ReviewTaskQueueItem } from '../types/review';

export const ReviewQueuePage: React.FC = () => {
  const [tasks, setTasks] = useState<ReviewTaskQueueItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [search, setSearch] = useState<string>('');

  // Modals
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [isWorkspaceOpen, setIsWorkspaceOpen] = useState<boolean>(false);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState<boolean>(false);

  const pageSize = 25;

  const fetchQueue = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await apiClient.getReviewTasks({
        page,
        page_size: pageSize,
        status: statusFilter || undefined,
        document_type: typeFilter || undefined,
        search: search.trim() || undefined,
      });
      setTasks(res.items);
      setTotal(res.total);
    } catch (err: any) {
      setError(err?.message || 'Failed to retrieve review queue.');
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, typeFilter, search]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleOpenWorkspace = (taskId: string) => {
    setSelectedTaskId(taskId);
    setIsWorkspaceOpen(true);
  };

  const handleWorkspaceClose = () => {
    setIsWorkspaceOpen(false);
    setSelectedTaskId(null);
    fetchQueue();
  };

  // Metrics summary calculations
  const pendingCount = tasks.filter((t) => t.status === 'PENDING').length;
  const inReviewCount = tasks.filter((t) => t.status === 'IN_REVIEW').length;
  const criticalCount = tasks.filter((t) => t.priority === 'CRITICAL').length;
  const highPriorityCount = tasks.filter((t) => t.priority === 'HIGH').length;

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
            <CheckSquare className="w-7 h-7 text-amber-400" />
            <span>Human-in-the-Loop Review Queue</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Traceable review decisions, field-level corrections, dual-control policy compliance, and audit trails.
          </p>
        </div>

        <div className="flex items-center space-x-2.5 self-start sm:self-auto">
          <button
            onClick={() => setIsAuditModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-800/90 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition"
          >
            <ShieldAlert className="w-4 h-4 text-indigo-400" />
            <span>Audit Trail</span>
          </button>

          <button
            onClick={fetchQueue}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Total Tasks</span>
            <Layers className="w-4 h-4 text-slate-500" />
          </div>
          <p className="text-2xl font-bold text-slate-100 mt-2">{total}</p>
          <p className="text-[11px] text-slate-500 mt-0.5">Active queue items</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Critical Priority</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-2xl font-bold text-rose-400 mt-2">{criticalCount}</p>
          <p className="text-[11px] text-slate-500 mt-0.5">Ledger / Math discrepancy</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>High Priority</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-amber-400 mt-2">{highPriorityCount}</p>
          <p className="text-[11px] text-slate-500 mt-0.5">Low confidence score</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Awaiting Review</span>
            <User className="w-4 h-4 text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-indigo-400 mt-2">{pendingCount + inReviewCount}</p>
          <p className="text-[11px] text-slate-500 mt-0.5">Unresolved tasks</p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search document title, filename..."
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-950 border border-slate-700 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        <div className="flex items-center space-x-2.5">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 text-xs bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Statuses</option>
            <option value="PENDING">PENDING</option>
            <option value="IN_REVIEW">IN_REVIEW</option>
            <option value="APPROVED">APPROVED</option>
            <option value="REJECTED">REJECTED</option>
          </select>

          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 text-xs bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Document Types</option>
            <option value="INVOICE">INVOICE</option>
            <option value="BANK_STATEMENT">BANK_STATEMENT</option>
            <option value="EXPENSE_REPORT">EXPENSE_REPORT</option>
          </select>
        </div>
      </div>

      {/* Review Queue Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center py-24 text-slate-400 text-xs">
            <RefreshCw className="w-5 h-5 animate-spin mr-2 text-indigo-400" />
            Loading review queue...
          </div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-20 text-slate-500 text-xs">
            No documents currently require review. All financial records are verified.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 border-b border-slate-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Document</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Confidence</th>
                  <th className="py-3 px-4">Validation Warnings</th>
                  <th className="py-3 px-4">Assigned Reviewer</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {tasks.map((item) => (
                  <tr
                    key={item.id}
                    className="hover:bg-slate-800/40 transition group"
                  >
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase border ${
                          item.priority === 'CRITICAL'
                            ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                            : item.priority === 'HIGH'
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                            : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                        }`}
                      >
                        {item.priority}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-200 truncate max-w-xs">
                        {item.document_title || item.document_filename}
                      </div>
                      <div className="text-[11px] text-slate-500 truncate max-w-xs">
                        {item.document_filename}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px] border border-slate-700">
                        {item.document_type || 'UNKNOWN'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                          item.status === 'APPROVED'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                            : item.status === 'REJECTED'
                            ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                            : item.status === 'IN_REVIEW'
                            ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30'
                            : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                        }`}
                      >
                        {item.status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`font-mono text-xs ${
                          item.confidence_score >= 0.85
                            ? 'text-emerald-400'
                            : 'text-amber-400'
                        }`}
                      >
                        {(item.confidence_score * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {item.validation_error_count > 0 ? (
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold text-[10px] border border-amber-500/40">
                          {item.validation_error_count} check(s)
                        </span>
                      ) : (
                        <span className="text-emerald-400 text-[11px] flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Passed</span>
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      {item.assigned_to_name ? (
                        <div className="flex items-center space-x-1.5">
                          <User className="w-3.5 h-3.5 text-indigo-400" />
                          <span className="truncate max-w-[120px]">{item.assigned_to_name}</span>
                        </div>
                      ) : (
                        <span className="text-slate-500 italic">Unassigned</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleOpenWorkspace(item.id)}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600 text-indigo-200 hover:text-white border border-indigo-500/40 text-xs font-semibold transition"
                      >
                        <span>Workspace</span>
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

      {/* Review Workspace Modal */}
      {selectedTaskId && (
        <ReviewWorkspaceModal
          taskId={selectedTaskId}
          isOpen={isWorkspaceOpen}
          onClose={handleWorkspaceClose}
          onTaskUpdated={fetchQueue}
        />
      )}

      {/* Searchable Audit Log Modal */}
      <AuditLogModal
        isOpen={isAuditModalOpen}
        onClose={() => setIsAuditModalOpen(false)}
      />
    </div>
  );
};
