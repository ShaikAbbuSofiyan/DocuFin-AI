import React from 'react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const normalized = status.toLowerCase();

  let bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
  let dotClass = 'bg-slate-400';

  if (['ok', 'live', 'ready', 'connected', 'success', 'approved'].includes(normalized)) {
    bgClass = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    dotClass = 'bg-emerald-400 animate-pulse';
  } else if (['processing'].includes(normalized)) {
    bgClass = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30';
    dotClass = 'bg-cyan-400 animate-ping';
  } else if (['uploaded', 'queued'].includes(normalized)) {
    bgClass = 'bg-blue-500/10 text-blue-400 border-blue-500/30';
    dotClass = 'bg-blue-400';
  } else if (['degraded', 'warning', 'review_required', 'pending'].includes(normalized)) {
    bgClass = 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    dotClass = 'bg-amber-400';
  } else if (['error', 'not_ready', 'failed', 'offline', 'rejected'].includes(normalized)) {
    bgClass = 'bg-rose-500/10 text-rose-400 border-rose-500/30';
    dotClass = 'bg-rose-400';
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs font-medium';
  const displayLabel = status.toLowerCase().replace(/_/g, ' ');

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${bgClass} ${sizeClasses}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />
      <span className="capitalize">{displayLabel}</span>
    </span>
  );
};
