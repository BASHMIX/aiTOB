import React, { useEffect, useState } from 'react';
import {
  bindStationResultsSession,
  getStationResultsSession,
  sendStationResultsCommand,
  type PlaybackCommand,
  type ResultsSessionData,
} from './api';

interface ResultsOverlayControlsProps {
  stationId: string;
  outputId?: string;
  canBroadcast?: boolean;
  onSessionChange?: (session: ResultsSessionData) => void;
}

export const ResultsOverlayControls: React.FC<ResultsOverlayControlsProps> = ({
  stationId,
  outputId,
  canBroadcast = true,
  onSessionChange,
}) => {
  const [session, setSession] = useState<ResultsSessionData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadSession = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getStationResultsSession(stationId);
      setSession(data);
      onSessionChange?.(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load station results session');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSession();
  }, [stationId]);

  const handleBind = async () => {
    if (!outputId || !session) return;
    try {
      setLoading(true);
      setError(null);
      const updated = await bindStationResultsSession(stationId, {
        media_output_id: outputId,
        expected_revision: session.session_revision,
      });
      setSession(updated);
      onSessionChange?.(updated);
    } catch (err: any) {
      if (err.response?.status === 409) {
        const msg = 'Revision conflict: station state was updated. Refreshed latest state.';
        try {
          const refreshed = await getStationResultsSession(stationId);
          setSession(refreshed);
          onSessionChange?.(refreshed);
        } catch {}
        setError(msg);
      } else {
        setError(err.response?.data?.detail || 'Failed to bind media output');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCommand = async (command: PlaybackCommand) => {
    if (!session) return;
    try {
      setLoading(true);
      setError(null);
      const updated = await sendStationResultsCommand(stationId, {
        command,
        expected_revision: session.session_revision,
      });
      setSession(updated);
      onSessionChange?.(updated);
    } catch (err: any) {
      if (err.response?.status === 409) {
        const msg = 'Revision conflict: station state was updated. Refreshed latest state.';
        try {
          const refreshed = await getStationResultsSession(stationId);
          setSession(refreshed);
          onSessionChange?.(refreshed);
        } catch {}
        setError(msg);
      } else {
        setError(err.response?.data?.detail || `Failed to execute ${command}`);
      }
    } finally {
      setLoading(false);
    }
  };

  if (!session) {
    return (
      <div className="p-4 bg-gray-900 border border-gray-800 rounded-lg text-gray-400">
        {loading ? 'Loading station results overlay...' : 'No session available.'}
      </div>
    );
  }

  const isBound = Boolean(session.media_output_id && session.media_output_id === outputId);
  const state = session.state;

  return (
    <div className="p-4 bg-gray-900 border border-gray-800 rounded-lg space-y-4 text-white">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-800 pb-3">
        <div>
          <div className="text-sm font-semibold text-gray-200">
            Station Overlay: {stationId}
          </div>
          <div className="text-xs text-gray-400 flex gap-3 mt-1">
            <span data-testid="session-state-badge">Session State: <strong className="text-blue-400">{state}</strong></span>
            <span data-testid="session-cue-badge">Cue: <strong className="text-gray-200">{session.cue_index}</strong></span>
            <span data-testid="session-revision-badge">Session Revision: <strong className="text-gray-200">{session.session_revision}</strong></span>
          </div>
        </div>

        {!canBroadcast && (
          <div className="text-xs text-amber-400 bg-amber-950/40 border border-amber-800/50 px-2 py-1 rounded">
            You do not have broadcast permissions (read-only)
          </div>
        )}
      </div>

      {error && (
        <div className="text-xs text-red-300 bg-red-950/50 border border-red-800 p-2 rounded">
          {error}
        </div>
      )}

      {canBroadcast && (
        <div className="space-y-3">
          {!isBound ? (
            <div className="flex items-center justify-between gap-3 bg-gray-800/50 p-3 rounded">
              <span className="text-xs text-gray-300">
                {outputId
                  ? 'Output is not bound to this station yet.'
                  : 'Select an output before binding to station.'}
              </span>
              <button
                type="button"
                onClick={handleBind}
                disabled={loading || !outputId}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-xs font-medium rounded text-white"
              >
                Bind to Station
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => handleCommand('take_live')}
                disabled={loading || !['ready', 'held', 'complete'].includes(state)}
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-xs font-semibold rounded text-white"
              >
                Take Live
              </button>

              <button
                type="button"
                onClick={() => handleCommand('play_all')}
                disabled={loading || !['ready', 'live', 'held', 'complete'].includes(state)}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-xs font-medium rounded text-white"
              >
                Play All
              </button>

              <button
                type="button"
                onClick={() => handleCommand('next')}
                disabled={loading || !['ready', 'live', 'held'].includes(state)}
                className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-xs font-medium rounded text-white"
              >
                Next
              </button>

              <button
                type="button"
                onClick={() => handleCommand('previous')}
                disabled={loading || !['live', 'held', 'complete'].includes(state)}
                className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-xs font-medium rounded text-white"
              >
                Previous
              </button>

              <button
                type="button"
                onClick={() => handleCommand('hold')}
                disabled={loading || state !== 'live'}
                className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-xs font-medium rounded text-white"
              >
                Hold
              </button>

              <button
                type="button"
                onClick={() => handleCommand('restart')}
                disabled={loading || !['ready', 'live', 'held', 'complete'].includes(state)}
                className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-xs font-medium rounded text-white"
              >
                Restart
              </button>

              <button
                type="button"
                onClick={() => handleCommand('clear')}
                disabled={loading}
                className="px-3 py-1.5 bg-red-700 hover:bg-red-600 disabled:opacity-40 text-xs font-medium rounded text-white ml-auto"
              >
                Clear
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
