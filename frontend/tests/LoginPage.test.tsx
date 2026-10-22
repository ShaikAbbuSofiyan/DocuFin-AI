import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { LoginPage } from '../src/pages/LoginPage';
import { AuthProvider } from '../src/context/AuthContext';

vi.mock('../src/services/api', () => ({
  apiClient: {
    login: vi.fn(),
    getMe: vi.fn().mockRejectedValue(new Error('Not logged in')),
  },
  setOnUnauthorizedHandler: vi.fn(),
}));

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders login form with inputs and sign in button', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    expect(screen.getByText('Sign in to your portal')).toBeInTheDocument();
    expect(screen.getByLabelText(/Institutional Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
  });

  it('displays error if submitted with empty credentials', async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    const submitBtn = screen.getByRole('button', { name: /Sign In/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Please provide both email and password/i)).toBeInTheDocument();
    });
  });

  it('populates fields on quick-fill demo click', async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    const adminBtn = screen.getByRole('button', { name: /Admin admin@docufin.ai/i });
    fireEvent.click(adminBtn);

    expect(screen.getByDisplayValue('admin@docufin.ai')).toBeInTheDocument();
  });
});
