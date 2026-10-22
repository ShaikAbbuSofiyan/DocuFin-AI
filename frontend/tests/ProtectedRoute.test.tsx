import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from '../src/components/auth/ProtectedRoute';
import * as AuthContextModule from '../src/context/AuthContext';
import { AuthContextType } from '../src/types/auth';

describe('ProtectedRoute', () => {
  it('redirects to /login when user is unauthenticated', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: null,
      memberships: [],
      activeOrg: null,
      activeRole: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      switchOrganization: vi.fn(),
      refreshUser: vi.fn(),
    } as AuthContextType);

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div>Login Page Target</div>} />
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Secret Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Login Page Target')).toBeInTheDocument();
    expect(screen.queryByText('Secret Content')).not.toBeInTheDocument();
  });

  it('renders children when authenticated and permitted', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: 'u1',
        email: 'analyst@docufin.ai',
        full_name: 'Alex Vance',
        is_active: true,
        is_superuser: false,
        created_at: '2026-10-20T00:00:00Z',
      },
      memberships: [
        {
          id: 'm1',
          organization_id: 'org1',
          organization_name: 'Alpha Capital',
          organization_slug: 'alpha-cap',
          role: 'Analyst',
          is_active: true,
        },
      ],
      activeOrg: {
        id: 'm1',
        organization_id: 'org1',
        organization_name: 'Alpha Capital',
        organization_slug: 'alpha-cap',
        role: 'Analyst',
        is_active: true,
      },
      activeRole: 'Analyst',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      switchOrganization: vi.fn(),
      refreshUser: vi.fn(),
    } as AuthContextType);

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route
            path="/protected"
            element={
              <ProtectedRoute allowedRoles={['Analyst', 'Admin']}>
                <div>Permitted Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Permitted Content')).toBeInTheDocument();
  });

  it('displays restricted access notice when role is insufficient', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: 'u2',
        email: 'reviewer@docufin.ai',
        full_name: 'Rita Reviewer',
        is_active: true,
        is_superuser: false,
        created_at: '2026-10-20T00:00:00Z',
      },
      memberships: [],
      activeOrg: {
        id: 'm2',
        organization_id: 'org1',
        organization_name: 'Alpha Capital',
        organization_slug: 'alpha-cap',
        role: 'Reviewer',
        is_active: true,
      },
      activeRole: 'Reviewer',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      switchOrganization: vi.fn(),
      refreshUser: vi.fn(),
    } as AuthContextType);

    render(
      <MemoryRouter initialEntries={['/admin-only']}>
        <Routes>
          <Route
            path="/admin-only"
            element={
              <ProtectedRoute allowedRoles={['Admin']}>
                <div>Admin Only View</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Restricted Access')).toBeInTheDocument();
    expect(screen.queryByText('Admin Only View')).not.toBeInTheDocument();
  });
});
