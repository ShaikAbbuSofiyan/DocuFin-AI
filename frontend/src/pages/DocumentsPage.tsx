import React from 'react';
import { FileText } from 'lucide-react';
import { PlaceholderView } from '../components/common/PlaceholderView';

export const DocumentsPage: React.FC = () => {
  return (
    <PlaceholderView
      title="Financial Documents Vault"
      subtitle="SEC Filings, Balance Sheets, Invoices, and Earnings Transcripts"
      icon={FileText}
      targetPhase="Phase 2: Ingestion & Document Processing"
      description="The Documents Vault manages secure multi-tenant upload, automated PDF rasterization, OCR extraction, financial table detection, and metadata tagging across corporate filings."
      plannedFeatures={[
        'High-throughput asynchronous document upload with virus scanning and format validation',
        'Automatic classification of SEC filings (10-K, 10-Q, 8-K) and corporate financial statements',
        'Multi-column financial table parsing with bounding box retention for auditability',
        'Direct integration with PostgreSQL metadata registry and object storage (S3 / Local filesystem)',
      ]}
    />
  );
};
