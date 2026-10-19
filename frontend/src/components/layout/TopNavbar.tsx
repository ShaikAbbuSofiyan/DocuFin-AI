import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Menu,
  Search,
  Bell,
  Activity,
  ShieldCheck,
} from 'lucide-react';
import { useLiveHealth } from '../../services/health';

interface TopNavbarProps {
  onOpenSidebar: () => void;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({ onOpenSidebar }) => {
  const { data: healthData, isSuccess } = useLiveHealth(15000);

  return (
    <header className="h-16 bg-white border-b border-slate-200/80 sticky top-0 z-30 flex items-center justify-between px-4 sm:px-6">
      {/* Left: Mobile hamburger & Global Search */}
      <div className="flex items-center gap-3 sm:gap-4 flex-1 max-w-lg">
        <button
          onClick={onOpenSidebar}
          className="p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 lg:hidden"
          aria-label="Open navigation menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="relative w-full max-w-md hidden sm:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search financial disclosures, SEC filings, 10-K..."
            disabled
            className="w-full pl-9 pr-4 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 cursor-not-allowed"
            title="Search will be activated with vector retrieval in Phase 2"
          />
        </div>
      </div>

      {/* Right: Operational Health, Notifications, User */}
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Service Connectivity Status Indicator */}
        <NavLink
          to="/health"
          className="flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-50 border border-slate-200 hover:bg-slate-100 transition-colors"
          title="Click to view detailed system health diagnostics"
        >
          <span className="relative flex h-2 w-2">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isSuccess ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                isSuccess ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            />
          </span>
          <span className="text-slate-700 hidden sm:inline">
            API {isSuccess ? healthData?.version || 'v0.1.0' : 'Connecting...'}
          </span>
          <Activity className="h-3.5 w-3.5 text-slate-400" />
        </NavLink>

        {/* SOC2 / Compliance Indicator */}
        <div className="hidden md:flex items-center gap-1 text-[11px] font-semibold text-slate-500 px-2 py-0.5 rounded bg-slate-100 border border-slate-200">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
          <span>Audit Active</span>
        </div>

        {/* Notifications Icon Placeholder */}
        <button
          className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 relative"
          aria-label="View notifications"
          title="Notifications coming soon"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 bg-blue-600 rounded-full" />
        </button>

        <div className="h-6 w-px bg-slate-200" />

        {/* User Profile */}
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-full bg-slate-800 text-white flex items-center justify-center font-medium text-xs shadow-sm">
            AV
          </div>
          <div className="hidden sm:block text-left">
            <div className="text-xs font-semibold text-slate-800">Alex Vance</div>
            <div className="text-[10px] text-slate-500">Lead Financial Analyst</div>
          </div>
        </div>
      </div>
    </header>
  );
};
