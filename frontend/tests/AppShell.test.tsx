import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from '../src/components/layout/AppShell';
import { AuthProvider } from '../src/context/AuthContext';

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe('AppShell', () => {
  it('renders branding and primary navigation links', () => {
    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AuthProvider>
            <AppShell />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Verify Brand Title
    expect(screen.getByText('DocuFin')).toBeInTheDocument();
    expect(screen.getByText('Financial Intelligence')).toBeInTheDocument();

    // Verify Navigation Links
    expect(screen.getByRole('link', { name: /Dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Documents/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /AI Assistant/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Review Queue/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /System Health/i })).toBeInTheDocument();
  });
});
