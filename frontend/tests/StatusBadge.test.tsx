import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StatusBadge } from '../src/components/common/StatusBadge';

describe('StatusBadge', () => {
  it('renders connected status with correct label', () => {
    render(<StatusBadge status="connected" />);
    expect(screen.getByText('connected')).toBeInTheDocument();
  });

  it('renders operational and error states with normalized label', () => {
    render(<StatusBadge status="not_ready" />);
    expect(screen.getByText('not ready')).toBeInTheDocument();
  });
});
