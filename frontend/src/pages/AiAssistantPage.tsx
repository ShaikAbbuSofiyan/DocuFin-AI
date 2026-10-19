import React from 'react';
import { Bot } from 'lucide-react';
import { PlaceholderView } from '../components/common/PlaceholderView';

export const AiAssistantPage: React.FC = () => {
  return (
    <PlaceholderView
      title="Financial AI Analyst Assistant"
      subtitle="Context-Aware Conversational RAG & Financial Statement Analysis"
      icon={Bot}
      targetPhase="Phase 2 & 3: Financial AI Engine"
      description="The AI Assistant empowers equity research analysts and auditors to converse directly with complex financial documentation, calculate normalized metrics, compare cross-quarter disclosures, and generate cited summaries."
      plannedFeatures={[
        'Hybrid vector search + lexical keyword retrieval over dense financial tables',
        'Direct citation and bounding box coordinates for every factual claim or extracted figure',
        'Automated reconciliation of reported GAAP to Non-GAAP reconciliations',
        'Deterministic calculations verified via sandboxed Python code interpreter',
      ]}
    />
  );
};
