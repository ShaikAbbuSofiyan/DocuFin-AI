import React from 'react';
import { Settings } from 'lucide-react';
import { PlaceholderView } from '../components/common/PlaceholderView';

export const SettingsPage: React.FC = () => {
  return (
    <PlaceholderView
      title="Platform Settings & Administration"
      subtitle="Security Controls, Tenant Configuration & Model Parameters"
      icon={Settings}
      targetPhase="Phase 4: Enterprise Administration"
      description="Manage role-based access control (RBAC), multi-tenant isolation policies, API keys for programmatic ingestion, model hyperparameters, and automated retention compliance."
      plannedFeatures={[
        'Role-Based Access Control (RBAC) with granular analyst, auditor, and admin roles',
        'API Key management with strict rate-limiting, IP allowlisting, and scope controls',
        'LLM provider configuration (Azure OpenAI, AWS Bedrock, Google Vertex AI, Anthropic)',
        'Comprehensive audit log export and immutable compliance archive policies',
      ]}
    />
  );
};
