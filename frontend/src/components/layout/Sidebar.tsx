import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  Bot,
  CheckSquare,
  BarChart3,
  Activity,
  Settings,
  Building2,
  X,
  FileCheck,
  ChevronDown,
  Shield,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Role } from '../../types/auth';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

interface NavItem {
  name: string;
  to: string;
  icon: React.ElementType;
  badge?: string;
  allowedRoles?: Role[];
}

const baseNavigation: NavItem[] = [
  { name: 'Dashboard', to: '/', icon: LayoutDashboard },
  { name: 'Documents', to: '/documents', icon: FileText },
  { name: 'AI Assistant', to: '/ai-assistant', icon: Bot, badge: 'Phase 2' },
  {
    name: 'Review Queue',
    to: '/review-queue',
    icon: CheckSquare,
    allowedRoles: ['Admin', 'Reviewer'],
  },
  { name: 'Analytics', to: '/analytics', icon: BarChart3 },
  { name: 'System Health', to: '/health', icon: Activity },
  {
    name: 'Settings',
    to: '/settings',
    icon: Settings,
    allowedRoles: ['Admin'],
  },
];

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { activeOrg, activeRole, memberships, switchOrganization } = useAuth();
  const [orgDropdownOpen, setOrgDropdownOpen] = useState(false);

  // Filter navigation items by active role
  const visibleNav = baseNavigation.filter((item) => {
    if (!item.allowedRoles) return true;
    if (!activeRole) return true;
    return item.allowedRoles.includes(activeRole);
  });

  const getRoleBadgeStyle = (role: Role | null) => {
    switch (role) {
      case 'Admin':
        return 'bg-purple-900/60 text-purple-300 border-purple-700/50';
      case 'Reviewer':
        return 'bg-amber-900/60 text-amber-300 border-amber-700/50';
      case 'Analyst':
      default:
        return 'bg-blue-900/60 text-blue-300 border-blue-700/50';
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Sidebar Panel */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-slate-900 text-white flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="h-16 flex items-center justify-between px-6 border-b border-slate-800">
          <NavLink to="/" className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-md shadow-blue-500/20">
              <FileCheck className="h-5 w-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-lg tracking-tight text-white">
                DocuFin<span className="text-blue-400">AI</span>
              </span>
              <span className="block text-[10px] tracking-wider font-semibold text-slate-400 uppercase">
                Financial Intelligence
              </span>
            </div>
          </NavLink>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 lg:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation Menu */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase flex items-center justify-between">
            <span>Platform</span>
            {activeRole && (
              <span
                className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${getRoleBadgeStyle(
                  activeRole
                )}`}
              >
                {activeRole}
              </span>
            )}
          </div>
          {visibleNav.map((item) => (
            <NavLink
              key={item.name}
              to={item.to}
              onClick={() => {
                if (window.innerWidth < 1024) onClose();
              }}
              className={({ isActive }) =>
                `flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/30'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/70'
                }`
              }
            >
              <div className="flex items-center gap-3">
                <item.icon className="h-4 w-4" />
                <span>{item.name}</span>
              </div>
              {item.badge && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </div>

        {/* Dynamic Tenant / Organization Card */}
        <div className="p-4 border-t border-slate-800 relative">
          <div
            onClick={() => memberships.length > 1 && setOrgDropdownOpen(!orgDropdownOpen)}
            className={`p-3 rounded-xl bg-slate-800/60 border border-slate-700/50 flex items-center justify-between gap-3 ${
              memberships.length > 1 ? 'cursor-pointer hover:bg-slate-800 transition' : ''
            }`}
          >
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="h-8 w-8 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-xs border border-blue-500/30 flex-shrink-0">
                <Building2 className="h-4 w-4" />
              </div>
              <div className="overflow-hidden">
                <div className="text-xs font-semibold text-slate-200 truncate">
                  {activeOrg ? activeOrg.organization_name : 'Acme Capital LP'}
                </div>
                <div className="text-[10px] text-slate-400 flex items-center gap-1.5 truncate">
                  <Shield className="h-2.5 w-2.5 text-blue-400" />
                  <span>{activeRole || 'Analyst'} Access</span>
                </div>
              </div>
            </div>
            {memberships.length > 1 && (
              <ChevronDown
                className={`h-4 w-4 text-slate-400 transition-transform ${
                  orgDropdownOpen ? 'rotate-180' : ''
                }`}
              />
            )}
          </div>

          {/* Org Switcher Dropdown */}
          {orgDropdownOpen && memberships.length > 1 && (
            <div className="absolute bottom-16 left-4 right-4 bg-slate-800 border border-slate-700 rounded-xl shadow-xl p-1.5 space-y-1 z-50">
              <div className="text-[10px] font-semibold uppercase text-slate-400 px-2 py-1">
                Switch Organization
              </div>
              {memberships.map((m) => (
                <button
                  key={m.organization_id}
                  onClick={() => {
                    switchOrganization(m.organization_id);
                    setOrgDropdownOpen(false);
                  }}
                  className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between ${
                    activeOrg?.organization_id === m.organization_id
                      ? 'bg-blue-600 text-white font-medium'
                      : 'text-slate-300 hover:bg-slate-700/60'
                  }`}
                >
                  <span className="truncate">{m.organization_name}</span>
                  <span className="text-[9px] opacity-75">{m.role}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
