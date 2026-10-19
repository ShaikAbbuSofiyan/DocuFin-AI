import React from 'react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const normalized = status.toLowerCase();

  let bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
  let dotClass = 'bg-slate-400';

  if (['ok', 'live', 'ready', 'connected', 'success'].includes(normalized)) {
    bgClass = 'bg-emerald-50 text-emerald-700 border-emerald-200/80';
    dotClass = 'bg-emerald-500 animate-pulse';
  } else if (['degraded', 'warning', 'review_required', 'pending'].includes(normalized)) {
    bgClass = 'bg-amber-50 text-amber-700 border-amber-200/80';
    dotClass = 'bg-amber-500';
  } else if (['error', 'not_ready', 'failed', 'offline'].includes(normalized)) {
    bgClass = 'bg-rose-50 text-rose-700 border-rose-200/80';
    dotClass = 'bg-rose-500';
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs font-medium';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${bgClass} ${sizeClasses}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />
      <span className="capitalize">{status.replace('_', ' ')}</span>
    </span>
  );
};
