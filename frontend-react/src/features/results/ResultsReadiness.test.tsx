import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ResultsReadiness } from './ResultsReadiness';
import type { ResultVersionDetail } from './api';
import { MOCK_NORMAL_STANDINGS, MOCK_TIED_STANDINGS } from './mockData';

const baseVersion: ResultVersionDetail = {
  id: 'ver-123',
  tournament_slug: 'evo-2026',
  provider_type: 'startgg',
  event_id: 'ev-1',
  event_name: 'Tekken 8 Top 8',
  game_id: 't8',
  game_name: 'Tekken 8',
  capture_status: 'final',
  readiness_state: 'final',
  provider_state_raw: 'COMPLETED',
  observed_at: '2026-09-28T10:00:00Z',
  warnings: [],
  entry_count: 8,
  entries: MOCK_NORMAL_STANDINGS,
  page: { number: 1, size: 8, total_entries: 8, has_more: false },
};

describe('ResultsReadiness preflight UI', () => {
  it('displays green Final badge and provider evidence for completed events', () => {
    render(<ResultsReadiness version={baseVersion} onRefresh={vi.fn()} />);

    expect(screen.getByText('Provider Final')).toBeInTheDocument();
    expect(screen.getByText(/Tekken 8 Top 8/)).toBeInTheDocument();
    expect(screen.getByText(/Start.gg/i)).toBeInTheDocument();
  });

  it('displays yellow Provisional badge and warning when bracket is incomplete', () => {
    const provisionalVersion: ResultVersionDetail = {
      ...baseVersion,
      capture_status: 'provisional',
      readiness_state: 'provisional',
      provider_state_raw: 'ACTIVE',
      warnings: [{ code: 'in_progress', severity: 'warning', message: 'Event bracket is currently in progress.' }],
    };

    render(<ResultsReadiness version={provisionalVersion} onRefresh={vi.fn()} />);

    expect(screen.getByText('Provisional')).toBeInTheDocument();
    expect(screen.getByText(/Event bracket is currently in progress/)).toBeInTheDocument();
  });

  it('surfaces tied placement warnings when ties exist at cutoff boundary', () => {
    const tiedVersion: ResultVersionDetail = {
      ...baseVersion,
      warnings: [{ code: 'tie_boundary', severity: 'warning', message: 'Tied placements exist at the Top 8 boundary. Additional cards may be rendered.' }],
      entries: MOCK_TIED_STANDINGS,
    };

    render(<ResultsReadiness version={tiedVersion} onRefresh={vi.fn()} />);

    expect(screen.getByText(/Tied placements exist at the Top 8 boundary/)).toBeInTheDocument();
  });

  it('triggers onRefresh callback when refresh button is clicked', () => {
    const handleRefresh = vi.fn();
    render(<ResultsReadiness version={baseVersion} onRefresh={handleRefresh} isRefreshing={false} />);

    const refreshBtn = screen.getByRole('button', { name: /Refresh Results/i });
    fireEvent.click(refreshBtn);

    expect(handleRefresh).toHaveBeenCalledTimes(1);
  });
});
