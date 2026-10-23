import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ResultsStudioPage } from './ResultsStudioPage';
import * as resultsApi from './api';
import * as resultsExport from '@/utils/resultsExport';
import { MOCK_NORMAL_STANDINGS } from './mockData';
import { useHubStore } from '@/store/useHubStore';

vi.mock('./api', () => ({
  getLatestEventResults: vi.fn(),
  refreshEventResults: vi.fn(),
  getResultVersion: vi.fn(),
  createMediaOutput: vi.fn(),
  recordExportReceipt: vi.fn(),
  listResultsStations: vi.fn(),
}));

vi.mock('./ResultsOverlayControls', () => ({
  ResultsOverlayControls: ({ stationId, outputId }: { stationId: string; outputId: string }) => (
    <div data-testid="live-results-controls">{stationId}:{outputId}</div>
  ),
}));

vi.mock('@/components/layout/TopNavigation', () => ({
  TopNavigation: () => <nav data-testid="top-nav" />,
}));

vi.mock('@/utils/resultsExport', () => ({
  exportSceneToPng: vi.fn().mockResolvedValue({
    blob: new Blob(['png-bytes'], { type: 'image/png' }),
    byteSize: 1024,
    sha256: 'deadbeef1234567890abcdef',
  }),
  downloadPngBlob: vi.fn(),
}));

const mockVersion: resultsApi.ResultVersionDetail = {
  id: 'ver-evo-1',
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

describe('ResultsStudioPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(resultsApi.listResultsStations).mockResolvedValue([]);
    useHubStore.setState({
      currentSlug: 'evo-2026',
      currentEventId: 'ev-1',
      tournaments: [
        {
          id: 't-1',
          name: 'EVO 2026',
          slug: 'evo-2026',
          provider_type: 'startgg',
        } as any,
      ],
      events: [
        {
          id: 'ev-1',
          name: 'Tekken 8 Top 8',
          game: 'Tekken 8',
        } as any,
      ],
      session: {
        user_id: 'organizer-1',
        email: 'organizer@example.com',
        display_name: 'Organizer',
        workspace_id: 'ws-1',
        workspace_name: 'Workspace',
        workspace_slug: 'workspace',
        role: 'tournament_organizer',
        permissions: ['workspace.read', 'results.manage'],
      },
    });
  });

  it('loads and displays latest version standings with Champion Focus template', async () => {
    vi.mocked(resultsApi.getLatestEventResults).mockResolvedValue(mockVersion);
    vi.mocked(resultsApi.getResultVersion).mockResolvedValue(mockVersion);

    render(<ResultsStudioPage />);

    expect(screen.getByRole('heading', { name: /Results Studio/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText('Knee').length).toBeGreaterThan(0);
      expect(screen.getByText('Provider Final')).toBeInTheDocument();
    });

    const exportCanvas = document.getElementById('results-canvas-export-target');
    expect(exportCanvas).toBeInTheDocument();
    expect(exportCanvas?.style.transform).toBe('');
  });

  it('allows switching starter templates and preserves provider standings', async () => {
    vi.mocked(resultsApi.getLatestEventResults).mockResolvedValue(mockVersion);
    vi.mocked(resultsApi.getResultVersion).mockResolvedValue(mockVersion);

    render(<ResultsStudioPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Knee').length).toBeGreaterThan(0);
    });

    // Switch to Equal Grid
    const templateSelect = screen.getByLabelText(/Template Layout/i);
    fireEvent.change(templateSelect, { target: { value: 'equal-grid' } });

    // Standings are still rendered
    expect(screen.getAllByText('Knee').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Arslan Ash').length).toBeGreaterThan(0);
  });

  it('creates media output and records export receipt on Export PNG click', async () => {
    vi.mocked(resultsApi.getLatestEventResults).mockResolvedValue(mockVersion);
    vi.mocked(resultsApi.getResultVersion).mockResolvedValue(mockVersion);
    vi.mocked(resultsApi.createMediaOutput).mockResolvedValue({
      id: 'out-123',
      result_version_id: 'ver-evo-1',
      output_kind: 'static',
      scene_hash: 'scene-hash-abc',
      cutoff: 'top8',
      page_number: 1,
      output_profile: { width: 1920, height: 1080 },
      created_at: '2026-09-28T10:05:00Z',
    });
    vi.mocked(resultsApi.recordExportReceipt).mockResolvedValue({ output_id: 'out-123', recorded: true });

    render(<ResultsStudioPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Knee').length).toBeGreaterThan(0);
    });

    const exportBtn = screen.getByRole('button', { name: /Export PNG/i });
    fireEvent.click(exportBtn);

    await waitFor(() => {
      expect(resultsApi.createMediaOutput).toHaveBeenCalledWith(
        'ver-evo-1',
        expect.objectContaining({
          output_kind: 'static',
          cutoff: 'top8',
        }),
      );
      expect(resultsApi.recordExportReceipt).toHaveBeenCalledWith(
        'out-123',
        expect.objectContaining({
          byte_size: 1024,
          sha256: 'deadbeef1234567890abcdef',
        }),
      );
    });
    const rasterOrder = vi.mocked(resultsExport.exportSceneToPng).mock.invocationCallOrder[0];
    const outputOrder = vi.mocked(resultsApi.createMediaOutput).mock.invocationCallOrder[0];
    const receiptOrder = vi.mocked(resultsApi.recordExportReceipt).mock.invocationCallOrder[0];
    const downloadOrder = vi.mocked(resultsExport.downloadPngBlob).mock.invocationCallOrder[0];
    expect(rasterOrder).toBeLessThan(outputOrder);
    expect(outputOrder).toBeLessThan(receiptOrder);
    expect(receiptOrder).toBeLessThan(downloadOrder);
  });

  it('surfaces featured-character provenance badges in entrant presentation table', async () => {
    const versionWithProvenance: resultsApi.ResultVersionDetail = {
      ...mockVersion,
      entries: [
        {
          ...mockVersion.entries[0],
          presentation: {
            ...mockVersion.entries[0].presentation,
            character: {
              value: { id: 'c-1', name: 'Jin', image_url: '' },
              source: 'player_profile',
            },
          },
        },
        {
          ...mockVersion.entries[1],
          presentation: {
            ...mockVersion.entries[1].presentation,
            character: {
              value: { id: 'c-2', name: 'Kazuya', image_url: '' },
              source: 'entrant_override',
            },
          },
        },
      ],
    };
    vi.mocked(resultsApi.getLatestEventResults).mockResolvedValue(versionWithProvenance);
    vi.mocked(resultsApi.getResultVersion).mockResolvedValue(versionWithProvenance);

    render(<ResultsStudioPage />);

    await waitFor(() => {
      expect(screen.getByText('Entrant Presentation & Featured Characters')).toBeInTheDocument();
      expect(screen.getByText('Player Archive')).toBeInTheDocument();
      expect(screen.getByText('Event Override')).toBeInTheDocument();
    });
  });

  it('creates a reachable sequence-mode live output and exposes station controls', async () => {
    useHubStore.setState({
      session: {
        user_id: 'owner-1',
        email: 'owner@example.com',
        display_name: 'Owner',
        workspace_id: 'ws-1',
        workspace_name: 'Workspace',
        workspace_slug: 'workspace',
        role: 'owner',
        permissions: ['workspace.read', 'results.manage', 'results.broadcast'],
      },
    });
    vi.mocked(resultsApi.getLatestEventResults).mockResolvedValue(mockVersion);
    vi.mocked(resultsApi.getResultVersion).mockResolvedValue(mockVersion);
    vi.mocked(resultsApi.listResultsStations).mockResolvedValue([
      { id: 'station-main', name: 'Main Stream' },
    ]);
    vi.mocked(resultsApi.createMediaOutput).mockResolvedValue({
      id: 'live-out-1',
      result_version_id: mockVersion.id,
      output_kind: 'live',
      scene_hash: 'live-scene-hash',
      cutoff: 'top8',
      page_number: 1,
      output_profile: { width: 1920, height: 1080 },
      created_at: '2026-09-28T10:05:00Z',
    });

    render(<ResultsStudioPage />);

    await waitFor(() => expect(screen.getByLabelText('Live Station')).toHaveValue('station-main'));
    fireEvent.click(screen.getByRole('button', { name: 'Prepare Live Output' }));

    await waitFor(() => {
      expect(resultsApi.createMediaOutput).toHaveBeenCalledWith(
        mockVersion.id,
        expect.objectContaining({
          output_kind: 'live',
          scene: expect.objectContaining({
            dataSource: { kind: 'tournament-results', resultVersionId: mockVersion.id },
          }),
        }),
      );
      expect(screen.getByTestId('live-results-controls')).toHaveTextContent('station-main:live-out-1');
    });

    const payload = vi.mocked(resultsApi.createMediaOutput).mock.calls[0][1];
    const resultsGroup = Object.values(payload.scene.nodes).find((node) => node.type === 'results-group');
    expect(resultsGroup?.type === 'results-group' && resultsGroup.mode).toBe('sequence');
  });

  it('displays stale-version alert banner when version capture_status is stale', async () => {
    const staleVersion = {
      ...mockVersion,
      readiness_state: 'stale' as const,
    };
    vi.mocked(resultsApi.getLatestEventResults).mockResolvedValue(staleVersion);
    vi.mocked(resultsApi.getResultVersion).mockResolvedValue(staleVersion);

    render(<ResultsStudioPage />);

    await waitFor(() => {
      expect(screen.getByText(/Stale Result Version/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Refresh Version/i })).toBeInTheDocument();
    });
  });
});
