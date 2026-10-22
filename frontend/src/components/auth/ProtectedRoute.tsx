import React from 'react';
import { Navigate, Outlet, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Role } from '../../types/auth';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

interface ProtectedRouteProps {
  allowedRoles?: Role[];
  children?: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ allowedRoles, children }) => {
  const { isAuthenticated, isLoading, activeRole, activeOrg } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 text-white">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-slate-400 font-medium tracking-wide">
            Verifying security session...
          </p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && activeRole && !allowedRoles.includes(activeRole)) {
    return (
      <div className="p-8 max-w-2xl mx-auto my-12 bg-white rounded-2xl border border-rose-200/80 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="h-12 w-12 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600 flex-shrink-0">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <div className="space-y-3">
            <h2 className="text-lg font-bold text-slate-900">Restricted Access</h2>
            <p className="text-sm text-slate-600 leading-relaxed">
              This resource requires one of the following permissions:{' '}
              <span className="font-semibold text-slate-800">
                [{allowedRoles.join(', ')}]
              </span>
              . Your current role in{' '}
              <span className="font-semibold text-slate-800">
                {activeOrg?.organization_name || 'this organization'}
              </span>{' '}
              is <span className="font-semibold text-rose-600">{activeRole}</span>.
            </p>
            <div className="flex items-center gap-3 pt-2">
              <Link
                to="/"
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-slate-900 text-white hover:bg-slate-800 transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                Return to Dashboard
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return children ? <>{children}</> : <Outlet />;
};
