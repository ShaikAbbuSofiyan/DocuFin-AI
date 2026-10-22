import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { AiAssistantPage } from './pages/AiAssistantPage';
import { ReviewQueuePage } from './pages/ReviewQueuePage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { SettingsPage } from './pages/SettingsPage';
import { SystemHealthPage } from './pages/SystemHealthPage';

export const router = createBrowserRouter([
  // Public Authentication Routes
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/register',
    element: <RegisterPage />,
  },

  // Protected Application Shell & Routes
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <DashboardPage />,
      },
      {
        path: 'documents',
        element: <DocumentsPage />,
      },
      {
        path: 'ai-assistant',
        element: <AiAssistantPage />,
      },
      {
        path: 'review-queue',
        element: (
          <ProtectedRoute allowedRoles={['Admin', 'Reviewer']}>
            <ReviewQueuePage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'analytics',
        element: <AnalyticsPage />,
      },
      {
        path: 'health',
        element: <SystemHealthPage />,
      },
      {
        path: 'settings',
        element: (
          <ProtectedRoute allowedRoles={['Admin']}>
            <SettingsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: '*',
        element: <Navigate to="/" replace />,
      },
    ],
  },
]);
