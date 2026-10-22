import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { FileCheck, Lock, Mail, AlertCircle, ArrowRight, ShieldCheck } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError('Please provide both email and password.');
      return;
    }

    try {
      setIsSubmitting(true);
      await login({ email: email.trim(), password });
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDemoFill = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword('Password123!');
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex h-12 w-12 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 items-center justify-center shadow-lg shadow-blue-500/25 mb-4">
          <FileCheck className="h-7 w-7 text-white" />
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          DocuFin<span className="text-blue-400">AI</span>
        </h2>
        <p className="mt-1 text-xs text-slate-400 uppercase tracking-widest font-semibold">
          Enterprise Financial Intelligence
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white/95 backdrop-blur-md py-8 px-6 sm:px-10 shadow-2xl rounded-2xl border border-white/20">
          <div className="mb-6">
            <h3 className="text-lg font-bold text-slate-900">Sign in to your portal</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Access your institutional document intelligence and SEC audit tools
            </p>
          </div>

          {error && (
            <div className="mb-5 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2.5">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5 text-rose-600" />
              <div className="leading-relaxed">{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5" htmlFor="email">
                Institutional Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst@firm.com"
                  className="w-full pl-9 pr-3.5 py-2 text-sm bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5" htmlFor="password">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-3.5 py-2 text-sm bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-2 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white text-sm font-semibold shadow-md shadow-blue-600/20 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          {/* Quick Fill Demo Helper */}
          <div className="mt-6 pt-5 border-t border-slate-200/80">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
              <ShieldCheck className="h-3.5 w-3.5 text-blue-500" />
              <span>Demo Quick-Fill</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => handleDemoFill('admin@docufin.ai')}
                className="py-1 px-2 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-left transition"
              >
                <span className="font-semibold block text-[11px]">Admin</span>
                <span className="text-[10px] text-slate-500">admin@docufin.ai</span>
              </button>
              <button
                type="button"
                onClick={() => handleDemoFill('analyst@docufin.ai')}
                className="py-1 px-2 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-left transition"
              >
                <span className="font-semibold block text-[11px]">Analyst</span>
                <span className="text-[10px] text-slate-500">analyst@docufin.ai</span>
              </button>
            </div>
          </div>

          <div className="mt-6 text-center text-xs text-slate-500">
            Don't have an institutional workspace yet?{' '}
            <Link to="/register" className="font-semibold text-blue-600 hover:text-blue-500">
              Register Organization
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
