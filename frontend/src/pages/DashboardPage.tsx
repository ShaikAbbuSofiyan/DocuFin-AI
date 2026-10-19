import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  FileText,
  Activity,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ShieldAlert,
  Server,
  Database,
  Cpu,
} from 'lucide-react';
import { useReadyHealth } from '../services/health';
import { StatusBadge } from '../components/common/StatusBadge';

export const DashboardPage: React.FC = () => {
  const { data: healthData, isSuccess, isLoading } = useReadyHealth(10000);

  const kpis = [
    {
      title: 'Platform Readiness',
      value: isLoading ? 'Checking...' : isSuccess && healthData?.status === 'ready' ? 'Operational' : 'Attention Needed',
      badge: isSuccess ? healthData?.status || 'Active' : 'Checking',
      icon: Activity,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      title: 'Database Engine',
      value: isSuccess && healthData?.components.database?.status === 'connected' ? 'Connected' : 'Offline / Mock',
      badge: healthData?.components.database?.latency_ms ? `${healthData.components.database.latency_ms} ms` : 'N/A',
      icon: Database,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
    },
    {
      title: 'Redis Broker',
      value: isSuccess && healthData?.components.redis?.status === 'connected' ? 'Connected' : 'Offline / Mock',
      badge: healthData?.components.redis?.latency_ms ? `${healthData.components.redis.latency_ms} ms` : 'N/A',
      icon: Server,
      color: 'text-indigo-600',
      bg: 'bg-indigo-50',
    },
    {
      title: 'API Version',
      value: healthData?.version || 'v0.1.0',
      badge: healthData?.environment || 'Development',
      icon: Cpu,
      color: 'text-slate-600',
      bg: 'bg-slate-100',
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Welcome Banner */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200/60 mb-3">
              <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" /> Phase 1 Foundation Active
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
              DocuFin Financial Intelligence
            </h1>
            <p className="text-slate-500 text-sm mt-1 max-w-2xl">
              Enterprise modular monolith for financial statements, SEC 10-K/10-Q auditing, and real-time ledger extraction.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <NavLink
              to="/health"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 text-white font-medium text-xs sm:text-sm hover:bg-blue-700 transition shadow-sm shadow-blue-600/20"
            >
              <Activity className="w-4 h-4" />
              <span>System Health Diagnostics</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </NavLink>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {kpis.map((kpi, idx) => (
          <div
            key={idx}
            className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm hover:border-slate-300 transition"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-slate-500">{kpi.title}</span>
              <div className={`p-2 rounded-lg ${kpi.bg} ${kpi.color}`}>
                <kpi.icon className="w-4 h-4" />
              </div>
            </div>
            <div className="text-lg font-bold text-slate-900 mb-1">{kpi.value}</div>
            <div className="flex items-center gap-2">
              <StatusBadge status={kpi.badge} size="sm" />
            </div>
          </div>
        ))}
      </div>

      {/* Main Grid: Phase Roadmap & Recent Ingestion Schema */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Architecture Progression Roadmap */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Platform Implementation Phases</h2>
              <p className="text-xs text-slate-500">Enterprise architectural milestones</p>
            </div>
            <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-100 text-slate-600">
              Phase 1 / 4
            </span>
          </div>

          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-blue-50/60 border border-blue-200/70">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-pulse" />
                  <span className="text-xs font-bold text-blue-900">Phase 1: Architecture & Project Foundation</span>
                </div>
                <span className="text-[11px] font-bold text-blue-700 uppercase">Complete / Active</span>
              </div>
              <p className="text-xs text-blue-800 leading-relaxed">
                Modular monolith structure, FastAPI core config & exception handling, SQLAlchemy 2.0 session factory, Alembic migrations, Redis client, App shell, and Docker Compose configuration.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-400" />
                  <span className="text-xs font-bold text-slate-700">Phase 2: Document Ingestion & AI Parsing</span>
                </div>
                <span className="text-[11px] font-semibold text-slate-500 uppercase">Next Milestone</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Async document upload pipelines, PDF rasterization & OCR, table extraction, chunking, and financial embedding generation.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-400" />
                  <span className="text-xs font-bold text-slate-700">Phase 3: Financial RAG & Human-in-the-Loop Review</span>
                </div>
                <span className="text-[11px] font-semibold text-slate-500 uppercase">Planned</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Domain-specific vector retrieval, discrepancy reconciliation, confidence scoring, and reviewer queue workflows.
              </p>
            </div>
          </div>
        </div>

        {/* Right: Quick Launch & Diagnostics */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm flex flex-col justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900 mb-1">Quick Links</h2>
            <p className="text-xs text-slate-500 mb-4">Fast navigation to platform modules</p>

            <div className="space-y-2.5">
              <NavLink
                to="/health"
                className="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:border-blue-300 hover:bg-blue-50/40 transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-blue-50 text-blue-600 group-hover:bg-blue-100">
                    <Activity className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-800">System Diagnostics</div>
                    <div className="text-[10px] text-slate-500">Live & Ready probes</div>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600" />
              </NavLink>

              <NavLink
                to="/documents"
                className="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-slate-100 text-slate-600">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-800">Documents Vault</div>
                    <div className="text-[10px] text-slate-500">Phase 2 Ingestion</div>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-400" />
              </NavLink>

              <NavLink
                to="/review-queue"
                className="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-slate-100 text-slate-600">
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-800">Review Queue</div>
                    <div className="text-[10px] text-slate-500">Phase 3 Verification</div>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-400" />
              </NavLink>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-100">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <ShieldAlert className="w-4 h-4 text-slate-400" />
              <span>Production secrets isolated via Pydantic Settings.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
