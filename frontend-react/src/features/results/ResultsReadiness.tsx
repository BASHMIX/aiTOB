import React from 'react';
import type { ResultVersionDetail } from './api';

interface ResultsReadinessProps {
  version: ResultVersionDetail | null;
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export const ResultsReadiness: React.FC<ResultsReadinessProps> = ({
  version,
  onRefresh,
  isRefreshing = false,
}) => {
  if (!version) {
    return (
      <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 text-white flex items-center justify-between">
        <div>
          <span className="text-yellow-400 font-bold">No Version Loaded</span>
          <p className="text-xs text-gray-400 mt-1">
            Fetch provider standings to generate an immutable results version.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded text-xs font-semibold"
        >
          {isRefreshing ? 'Refreshing...' : 'Refresh Results'}
        </button>
      </div>
    );
  }

  const isFinal = version.readiness_state === 'final';
  const isProvisional = version.readiness_state === 'provisional';
  const warnings = version.warnings || [];

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 text-white space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {isFinal && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-green-900/60 text-green-300 border border-green-600/40">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
              Provider Final
            </span>
          )}
          {isProvisional && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-900/60 text-amber-300 border border-amber-600/40">
              <span className="w-2 h-2 rounded-full bg-amber-400"></span>
              Provisional
            </span>
          )}
          {!isFinal && !isProvisional && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-gray-800 text-gray-300 border border-gray-600">
              Stale
            </span>
          )}
          <div>
            <h3 className="text-sm font-bold text-white">
              {version.event_name} {version.game_name ? `· ${version.game_name}` : ''}
            </h3>
            <p className="text-xs text-gray-400">
              Source: <span className="text-gray-300 font-semibold">{version.provider_type === 'startgg' ? 'Start.gg' : version.provider_type === 'challonge' ? 'Challonge' : version.provider_type}</span> ({version.provider_state_raw})
              {' · '}Observed {new Date(version.observed_at).toLocaleTimeString()}
              {' · '}{version.entry_count} entrants
            </p>
          </div>
        </div>

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="px-3 py-1.5 bg-[#21262d] hover:bg-[#30363d] border border-[#30363d] text-gray-200 hover:text-white rounded text-xs font-semibold transition-colors disabled:opacity-50"
        >
          {isRefreshing ? 'Refreshing...' : 'Refresh Results'}
        </button>
      </div>

      {warnings.length > 0 && (
        <div className="bg-amber-950/40 border border-amber-800/60 rounded p-2.5 space-y-1">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-300">
            <span>⚠️</span> Preflight Warnings ({warnings.length})
          </div>
          <ul className="text-xs text-amber-200/90 list-disc list-inside space-y-0.5 pl-1">
            {warnings.map((warn, i) => (
              <li key={`${warn.code}-${warn.entrant_id || 'event'}-${i}`}>{warn.message}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
