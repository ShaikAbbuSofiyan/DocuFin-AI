import React from 'react';
import { LucideIcon, Sparkles, Clock, Layers } from 'lucide-react';

interface PlaceholderViewProps {
  title: string;
  subtitle: string;
  icon: LucideIcon;
  targetPhase: string;
  description: string;
  plannedFeatures: string[];
}

export const PlaceholderView: React.FC<PlaceholderViewProps> = ({
  title,
  subtitle,
  icon: Icon,
  targetPhase,
  description,
  plannedFeatures,
}) => {
  return (
    <div className="max-w-5xl mx-auto py-8 px-4 sm:px-6">
      {/* Header Banner */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 sm:p-8 mb-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-blue-50 text-blue-600 rounded-xl border border-blue-100 shadow-sm">
              <Icon className="h-7 w-7" />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{title}</h1>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200/70">
                  <Clock className="w-3 h-3" /> Coming Soon
                </span>
              </div>
              <p className="text-slate-500 text-sm">{subtitle}</p>
            </div>
          </div>
          <div className="inline-flex items-center gap-2 self-start sm:self-auto px-3.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-xs font-medium text-slate-600">
            <Layers className="w-4 h-4 text-slate-400" />
            Target: <span className="text-slate-900 font-semibold">{targetPhase}</span>
          </div>
        </div>
      </div>

      {/* Architecture & Feature Preview Card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6">
          <h2 className="text-base font-semibold text-slate-900 mb-2">Module Overview</h2>
          <p className="text-slate-600 text-sm leading-relaxed mb-6">{description}</p>

          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">
            Planned Technical Deliverables
          </h3>
          <ul className="space-y-3">
            {plannedFeatures.map((feature, idx) => (
              <li key={idx} className="flex items-start gap-3 text-sm text-slate-700">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center text-xs font-bold mt-0.5">
                  {idx + 1}
                </span>
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl text-white p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-400/30 text-xs font-medium mb-4">
              <Sparkles className="w-3.5 h-3.5 text-blue-400" /> Phase 1 Foundation
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Active Architecture</h3>
            <p className="text-slate-300 text-xs leading-relaxed">
              Phase 1 provides the core infrastructure (PostgreSQL, Redis, FastAPI async session management, Alembic migrations, and React query pipeline).
            </p>
          </div>
          <div className="mt-6 pt-4 border-t border-slate-700/60 text-xs text-slate-400">
            DocuFin Enterprise Monolith • v0.1.0
          </div>
        </div>
      </div>
    </div>
  );
};
