import React, { useState } from 'react';
import {
  Activity,
  RefreshCw,
  Database,
  Server,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Clock,
  Terminal,
  ShieldCheck,
  Radio,
} from 'lucide-react';
import { useLiveHealth, useReadyHealth } from '../services/health';
import { StatusBadge } from '../components/common/StatusBadge';

export const SystemHealthPage: React.FC = () => {
  const [pollInterval, setPollInterval] = useState<number | false>(10000);
  const [showRawJson, setShowRawJson] = useState(false);

  const {
    data: liveData,
    isLoading: liveLoading,
    isError: liveError,
    error: liveErrorObj,
    refetch: refetchLive,
    dataUpdatedAt: liveUpdatedAt,
  } = useLiveHealth(pollInterval);

  const {
    data: readyData,
    isLoading: readyLoading,
    isError: readyError,
    error: readyErrorObj,
    refetch: refetchReady,
  } = useReadyHealth(pollInterval);

  const handleRefreshAll = () => {
    refetchLive();
    refetchReady();
  };

  const isOverallHealthy =
    !liveError && !readyError && readyData?.status === 'ready';

  const lastChecked = liveUpdatedAt ? new Date(liveUpdatedAt).toLocaleTimeString() : 'Never';

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="p-2 rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
                <Activity className="w-5 h-5" />
              </span>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                System Health & Diagnostics
              </h1>
            </div>
            <p className="text-slate-500 text-sm max-w-2xl">
              Real-time monitoring of application runtime, PostgreSQL connectivity, and Redis message broker.
            </p>
          </div>

          {/* Action & Polling Controls */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200 text-xs">
              <Radio className={`w-3.5 h-3.5 ${pollInterval ? 'text-emerald-500 animate-pulse' : 'text-slate-400'}`} />
              <span className="text-slate-600 font-medium">Auto-poll:</span>
              <select
                value={pollInterval === false ? 'off' : pollInterval}
                onChange={(e) => {
                  const val = e.target.value;
                  setPollInterval(val === 'off' ? false : Number(val));
                }}
                className="bg-white border border-slate-200 rounded px-2 py-0.5 text-xs text-slate-700 font-medium focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value={5000}>Every 5s</option>
                <option value={10000}>Every 10s</option>
                <option value={30000}>Every 30s</option>
                <option value="off">Paused</option>
              </select>
            </div>

            <button
              onClick={handleRefreshAll}
              disabled={liveLoading || readyLoading}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800 transition disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${liveLoading || readyLoading ? 'animate-spin' : ''}`} />
              <span>Refresh Now</span>
            </button>
          </div>
        </div>

        {/* Global Operational Status Banner */}
        <div className="mt-6 pt-6 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2.5">
            <span className="text-slate-500">Overall Readiness:</span>
            {liveLoading || readyLoading ? (
              <span className="text-slate-400 font-medium">Checking services...</span>
            ) : isOverallHealthy ? (
              <span className="inline-flex items-center gap-1.5 font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> All Services Operational
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 font-semibold text-amber-700 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
                <AlertCircle className="w-3.5 h-3.5 text-amber-600" /> Partial / Degraded Connectivity
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-slate-400">
            <Clock className="w-3.5 h-3.5" />
            <span>Last checked: <strong className="text-slate-600 font-medium">{lastChecked}</strong></span>
          </div>
        </div>
      </div>

      {/* Dependency Diagnostic Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Application Core Card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
                  <Cpu className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-slate-900">Application API</h2>
                  <span className="text-[11px] text-slate-500">FastAPI & Uvicorn Runtime</span>
                </div>
              </div>
              <StatusBadge status={liveError ? 'error' : liveData?.status || 'checking'} />
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Probe Endpoint</span>
                <code className="text-slate-700 font-mono font-medium">/health/live</code>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Version</span>
                <span className="text-slate-900 font-semibold">{liveData?.version || '0.1.0'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Environment</span>
                <span className="text-slate-900 font-medium capitalize">{liveData?.environment || 'development'}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Process State</span>
                <span className="text-emerald-600 font-semibold">{liveError ? 'Offline' : 'Alive'}</span>
              </div>
            </div>
          </div>

          {liveError && (
            <div className="mt-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700">
              {liveErrorObj?.message || 'Failed to connect to backend /health/live probe.'}
            </div>
          )}
        </div>

        {/* PostgreSQL Database Card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-100">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-slate-900">PostgreSQL DB</h2>
                  <span className="text-[11px] text-slate-500">SQLAlchemy 2.0 Async</span>
                </div>
              </div>
              <StatusBadge
                status={readyData?.components.database?.status || (readyLoading ? 'checking' : 'error')}
              />
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Health Query</span>
                <code className="text-slate-700 font-mono font-medium">SELECT 1</code>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Query Latency</span>
                <span className="text-slate-900 font-semibold">
                  {readyData?.components.database?.latency_ms !== undefined
                    ? `${readyData.components.database.latency_ms} ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Connection Pool</span>
                <span className="text-slate-900 font-medium">Pre-ping Enabled</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Migrations</span>
                <span className="text-slate-900 font-medium">Alembic Async</span>
              </div>
            </div>
          </div>

          {readyData?.components.database?.details && (
            <div className="mt-4 p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 break-all font-mono">
              {readyData.components.database.details}
            </div>
          )}
        </div>

        {/* Redis Message Broker & Cache Card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100">
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-slate-900">Redis Broker</h2>
                  <span className="text-[11px] text-slate-500">AsyncIO Redis Driver</span>
                </div>
              </div>
              <StatusBadge
                status={readyData?.components.redis?.status || (readyLoading ? 'checking' : 'error')}
              />
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Health Command</span>
                <code className="text-slate-700 font-mono font-medium">PING</code>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Ping Latency</span>
                <span className="text-slate-900 font-semibold">
                  {readyData?.components.redis?.latency_ms !== undefined
                    ? `${readyData.components.redis.latency_ms} ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Socket Timeout</span>
                <span className="text-slate-900 font-medium">2.0 seconds</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Role</span>
                <span className="text-slate-900 font-medium">Cache & Queue Broker</span>
              </div>
            </div>
          </div>

          {readyData?.components.redis?.details && (
            <div className="mt-4 p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 break-all font-mono">
              {readyData.components.redis.details}
            </div>
          )}
        </div>
      </div>

      {/* Raw JSON Diagnostics Accordion */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
        <button
          onClick={() => setShowRawJson(!showRawJson)}
          className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-slate-50 transition"
        >
          <div className="flex items-center gap-2.5 text-sm font-semibold text-slate-900">
            <Terminal className="w-4 h-4 text-slate-500" />
            <span>Raw Diagnostic Payload Inspector</span>
          </div>
          <span className="text-xs font-medium text-blue-600">
            {showRawJson ? 'Hide Payloads' : 'View JSON Payloads'}
          </span>
        </button>

        {showRawJson && (
          <div className="p-6 border-t border-slate-100 bg-slate-900 text-slate-200 font-mono text-xs rounded-b-2xl overflow-x-auto">
            <div className="mb-4">
              <div className="text-slate-400 text-[11px] mb-1 font-sans font-semibold uppercase tracking-wider">
                GET /health/live Response
              </div>
              <pre className="p-3 bg-slate-950 rounded-lg text-emerald-400">
                {JSON.stringify(liveData || { error: liveErrorObj?.message }, null, 2)}
              </pre>
            </div>
            <div>
              <div className="text-slate-400 text-[11px] mb-1 font-sans font-semibold uppercase tracking-wider">
                GET /health/ready Response
              </div>
              <pre className="p-3 bg-slate-950 rounded-lg text-emerald-400">
                {JSON.stringify(readyData || { error: readyErrorObj?.message }, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* Local Environment Guidance Banner */}
      <div className="p-5 rounded-2xl bg-blue-50/70 border border-blue-200/80 text-xs text-blue-900 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div>
          <span className="font-bold">Enterprise Resilience Architecture:</span> The readiness probe validates live dependencies on each check. In development without local PostgreSQL or Redis daemons active, the API gracefully reports degraded dependency states with clear diagnostic details rather than crashing. All containers and full services are orchestrated via Docker Compose.
        </div>
      </div>
    </div>
  );
};
