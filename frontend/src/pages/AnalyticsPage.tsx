import React from 'react';
import { BarChart3 } from 'lucide-react';
import { PlaceholderView } from '../components/common/PlaceholderView';

export const AnalyticsPage: React.FC = () => {
  return (
    <PlaceholderView
      title="Financial Analytics & Insights"
      subtitle="Cross-Portfolio Trends, Ratio Comparison & Anomaly Visualizations"
      icon={BarChart3}
      targetPhase="Phase 4: Financial Analytics"
      description="The Analytics engine aggregates normalized financial data across companies and reporting periods, rendering interactive charts for EBITDA margins, debt covenants, revenue run rates, and working capital cycles."
      plannedFeatures={[
        'Interactive financial ratio visualizer with benchmark industry comparisons',
        'Time-series anomaly detection highlighting restatements or uncharacteristic accruals',
        'Exportable executive summary decks in PDF and Excel financial model format',
        'Custom formula builder for bespoke internal enterprise financial metrics',
      ]}
    />
  );
};
