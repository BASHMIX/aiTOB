import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ResultsOverlayControls } from './ResultsOverlayControls';
import * as api from './api';

vi.mock('./api', () => ({
  getStationResultsSession: vi.fn(),
  bindStationResultsSession: vi.fn(),
  sendStationResultsCommand: vi.fn(),
}));

describe('ResultsOverlayControls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders read-only view when user lacks results.broadcast permission', async () => {
    vi.mocked(api.getStationResultsSession).mockResolvedValueOnce({
      station_id: 'st-1',
      media_output_id: 'out-1',
      state: 'live',
      cue_index: 2,
      session_revision: 3,
      updated_at: '2026-09-28T12:00:00Z',
    });

    render(
      <ResultsOverlayControls
        stationId="st-1"
        outputId="out-1"
        canBroadcast={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('session-state-badge')).toHaveTextContent(/live/i);
    });

    // Control buttons should be hidden
    expect(screen.queryByRole('button', { name: /take live/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument();
    expect(screen.getByText(/You do not have broadcast permissions/i)).toBeInTheDocument();
  });

  it('binds output to station and issues playback commands', async () => {
    vi.mocked(api.getStationResultsSession).mockResolvedValueOnce({
      station_id: 'st-1',
      media_output_id: null,
      state: 'cleared',
      cue_index: -1,
      session_revision: 0,
      updated_at: '2026-09-28T12:00:00Z',
    });

    vi.mocked(api.bindStationResultsSession).mockResolvedValueOnce({
      station_id: 'st-1',
      media_output_id: 'out-1',
      state: 'ready',
      cue_index: -1,
      session_revision: 1,
      updated_at: '2026-09-28T12:00:01Z',
    });

    vi.mocked(api.sendStationResultsCommand).mockResolvedValueOnce({
      station_id: 'st-1',
      media_output_id: 'out-1',
      state: 'live',
      cue_index: -1,
      session_revision: 2,
      updated_at: '2026-09-28T12:00:02Z',
    });

    render(
      <ResultsOverlayControls
        stationId="st-1"
        outputId="out-1"
        canBroadcast={true}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /bind to station/i })).toBeInTheDocument();
    });

    // 1. Bind to station
    await userEvent.click(screen.getByRole('button', { name: /bind to station/i }));

    expect(api.bindStationResultsSession).toHaveBeenCalledWith('st-1', {
      media_output_id: 'out-1',
      expected_revision: 0,
    });

    await waitFor(() => {
      expect(screen.getByTestId('session-state-badge')).toHaveTextContent(/ready/i);
      expect(screen.getByRole('button', { name: /take live/i })).toBeEnabled();
    });

    // 2. Take live
    await userEvent.click(screen.getByRole('button', { name: /take live/i }));

    expect(api.sendStationResultsCommand).toHaveBeenCalledWith('st-1', {
      command: 'take_live',
      expected_revision: 1,
    });

    await waitFor(() => {
      expect(screen.getByTestId('session-state-badge')).toHaveTextContent(/live/i);
    });
  });

  it('handles 409 revision conflict gracefully by displaying alert and refreshing state', async () => {
    vi.mocked(api.getStationResultsSession)
      .mockResolvedValueOnce({
        station_id: 'st-1',
        media_output_id: 'out-1',
        state: 'live',
        cue_index: 0,
        session_revision: 2,
        updated_at: '2026-09-28T12:00:00Z',
      })
      .mockResolvedValueOnce({
        station_id: 'st-1',
        media_output_id: 'out-1',
        state: 'live',
        cue_index: 1,
        session_revision: 3,
        updated_at: '2026-09-28T12:00:05Z',
      });

    vi.mocked(api.sendStationResultsCommand).mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'Revision conflict' } },
    });

    render(
      <ResultsOverlayControls
        stationId="st-1"
        outputId="out-1"
        canBroadcast={true}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /next/i })).toBeEnabled();
    });

    await userEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(screen.getByText(/Revision conflict/i)).toBeInTheDocument();
      expect(screen.getByTestId('session-revision-badge')).toHaveTextContent(/3/i);
    });
  });
});
