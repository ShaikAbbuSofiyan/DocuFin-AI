import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { DocumentsPage } from '../src/pages/DocumentsPage';
import { apiClient } from '../src/services/api';
import { AuthProvider } from '../src/context/AuthContext';

vi.mock('../src/services/api', () => ({
  apiClient: {
    getDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    getDocumentPreviewUrl: (id: string) => `/api/v1/documents/${id}/preview`,
    getDocumentDownloadUrl: (id: string) => `/api/v1/documents/${id}/download`,
    getMe: vi.fn().mockResolvedValue({
      user: { id: 'u1', email: 'analyst@docufin.ai', full_name: 'Lead Analyst' },
      memberships: [{ organization_id: 'org-1', organization_name: 'Acme Capital', role: 'Analyst' }],
      active_organization_id: 'org-1',
      active_role: 'Analyst',
    }),
  },
  setOnUnauthorizedHandler: vi.fn(),
}));

describe('DocumentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the documents vault header and controls', async () => {
    vi.mocked(apiClient.getDocuments).mockResolvedValue({
      items: [
        {
          id: 'doc-123',
          title: 'Tesla Q3 10-Q Filing',
          filename: 'tsla_q3.pdf',
          file_size_bytes: 1048576,
          mime_type: 'application/pdf',
          file_extension: '.pdf',
          checksum_sha256: 'abc123sha256',
          status: 'UPLOADED',
          doc_type: '10-Q',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
      total_pages: 1,
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <DocumentsPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Header verification
    expect(screen.getByText('Financial Documents Vault')).toBeInTheDocument();

    // Wait for document row to render
    await waitFor(() => {
      expect(screen.getByText('Tesla Q3 10-Q Filing')).toBeInTheDocument();
      expect(screen.getByText('tsla_q3.pdf')).toBeInTheDocument();
      expect(screen.getByText('10-Q')).toBeInTheDocument();
      expect(screen.getAllByText(/uploaded/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders empty state when no documents are returned', async () => {
    vi.mocked(apiClient.getDocuments).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      total_pages: 1,
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <DocumentsPage />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('No documents found')).toBeInTheDocument();
    });
  });
});
