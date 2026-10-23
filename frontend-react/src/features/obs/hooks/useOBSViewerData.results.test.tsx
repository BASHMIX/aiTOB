import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useOBSViewerData } from './useOBSViewerData';

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();

  constructor() {
    MockWebSocket.instances.push(this);
    setTimeout(() => this.onopen?.(), 10);
  }
}

describe('useOBSViewerData Results Projection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    MockWebSocket.instances = [];
    (globalThis as any).WebSocket = MockWebSocket;
  });

  it('selects tournament-results projection without match merge', async () => {
    const mockResultsData = {
      projection_kind: 'tournament-results',
      config: {
        schemaVersion: 2,
        dataSource: { kind: 'tournament-results' },
        rootIds: ['res-1'],
        nodes: {
          'res-1': { id: 'res-1', type: 'results-group', templateId: 'tpl', mode: 'board' },
        },
      },
      active_match: null,
      results_projection: {
        output_id: 'out-1',
        result_version_id: 'ver-1',
        capture_status: 'final',
        event: { id: 'ev-1', name: 'SF6' },
        entries: [{ ordinal: 1, placement: 1, entrant_id: 'p1', entrant_name: 'Hero' }],
        session: {
          state: 'live',
          cue_index: 0,
          session_revision: 5,
        },
      },
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => mockResultsData,
    } as any);

    const { result } = renderHook(() => useOBSViewerData('station_1'));

    await waitFor(() => {
      expect(result.current.projectionKind).toBe('tournament-results');
      expect(result.current.resultsProjection).not.toBeNull();
      expect(result.current.resultsProjection?.output_id).toBe('out-1');
      expect(result.current.resultsProjection?.session?.cue_index).toBe(0);
      expect(result.current.resultsProjection?.session?.session_revision).toBe(5);
    });
  });

  it('enforces revision monotonicity on WebSocket updates', async () => {
    const mockResultsData = {
      projection_kind: 'tournament-results',
      config: { schemaVersion: 2, rootIds: [], nodes: {} },
      active_match: null,
      results_projection: {
        output_id: 'out-1',
        session: {
          state: 'live',
          cue_index: 0,
          session_revision: 5,
        },
      },
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => mockResultsData,
    } as any);

    const { result } = renderHook(() => useOBSViewerData('station_1'));

    await waitFor(() => {
      expect(result.current.resultsProjection?.session?.session_revision).toBe(5);
    });

    const ws = MockWebSocket.instances[0];

    // 1. Send stale revision (revision 4 <= 5): should be ignored
    act(() => {
      ws.onmessage?.({
        data: JSON.stringify({
          type: 'results_session_update',
          station_id: 'station_1',
          session: {
            media_output_id: 'out-1',
            state: 'held',
            cue_index: 0,
            session_revision: 4,
          },
        }),
      });
    });

    expect(result.current.resultsProjection?.session?.session_revision).toBe(5);
    expect(result.current.resultsProjection?.session?.state).toBe('live');

    // 2. Send newer revision (revision 6 > 5): should apply
    act(() => {
      ws.onmessage?.({
        data: JSON.stringify({
          type: 'results_session_update',
          station_id: 'station_1',
          session: {
            media_output_id: 'out-1',
            state: 'held',
            cue_index: 1,
            session_revision: 6,
          },
        }),
      });
    });

    expect(result.current.resultsProjection?.session?.session_revision).toBe(6);
    expect(result.current.resultsProjection?.session?.cue_index).toBe(1);
    expect(result.current.resultsProjection?.session?.state).toBe('held');
  });

  it('retains current-match mode when projection_kind is current-match', async () => {
    const mockMatchData = {
      projection_kind: 'current-match',
      config: { elements: { p1_name: { text: 'Player 1', visible: true } } },
      active_match: { p1_name: 'Knee', p2_name: 'Arslan', status: 'in_progress' },
      results_projection: null,
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => mockMatchData,
    } as any);

    const { result } = renderHook(() => useOBSViewerData('station_1'));

    await waitFor(() => {
      expect(result.current.projectionKind).toBe('current-match');
      expect(result.current.resultsProjection).toBeNull();
      expect(result.current.state?.elements?.p1_name?.text).toBe('Knee');
    });
  });
});
