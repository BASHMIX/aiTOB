import React from 'react';
import type { CutoffKind, OutputProfile } from '@/scene/types';

interface ResultsExportPanelProps {
  cutoff: CutoffKind;
  onCutoffChange: (cutoff: CutoffKind) => void;
  outputProfile: OutputProfile;
  onProfileChange: (profile: OutputProfile) => void;
  onExport: () => void;
  isExporting: boolean;
  exportSuccessMessage?: string | null;
  exportErrorMessage?: string | null;
  hasVersion: boolean;
  canExport?: boolean;
  hasExportPermission?: boolean;
  page?: number;
  hasMore?: boolean;
  totalEntries?: number;
  onPageChange?: (page: number) => void;
}

export const ResultsExportPanel: React.FC<ResultsExportPanelProps> = ({
  cutoff,
  onCutoffChange,
  outputProfile,
  onProfileChange,
  onExport,
  isExporting,
  exportSuccessMessage,
  exportErrorMessage,
  hasVersion,
  canExport = hasVersion,
  hasExportPermission = true,
  page = 1,
  hasMore = false,
  totalEntries = 0,
  onPageChange,
}) => {
  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-5 text-white space-y-5">
      <div>
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <span>📤</span> Export Results Media
        </h3>
        <p className="text-xs text-gray-400 mt-1">
          Export verified tournament standings as an auditable high-resolution graphic.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label htmlFor="cutoff-select" className="block text-xs font-semibold text-gray-300 mb-1">
            Standings Cutoff
          </label>
          <select
            id="cutoff-select"
            value={cutoff}
            onChange={(e) => onCutoffChange(e.target.value as CutoffKind)}
            className="w-full bg-[#0d1117] border border-[#30363d] rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
          >
            <option value="top8">Top 8 Standings</option>
            <option value="top16">Top 16 Standings</option>
            <option value="all">Full Standings (All)</option>
          </select>
        </div>

        {cutoff === 'all' && (
          <div className="rounded border border-[#30363d] bg-[#0d1117] p-3 space-y-2">
            <div className="flex items-center justify-between text-xs text-gray-300">
              <span>Results page {page}</span>
              <span>{totalEntries} entrants</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => onPageChange?.(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="rounded border border-[#30363d] px-2 py-1 text-xs disabled:opacity-40"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => onPageChange?.(page + 1)}
                disabled={!hasMore}
                className="rounded border border-[#30363d] px-2 py-1 text-xs disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}

        <div>
          <label htmlFor="aspect-select" className="block text-xs font-semibold text-gray-300 mb-1">
            Canvas Output Profile
          </label>
          <select
            id="aspect-select"
            value={`${outputProfile.width}x${outputProfile.height}`}
            onChange={(e) => {
              const [w, h] = e.target.value.split('x').map(Number);
              onProfileChange({ width: w, height: h, transparent: outputProfile.transparent });
            }}
            className="w-full bg-[#0d1117] border border-[#30363d] rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
          >
            <option value="1920x1080">16:9 Landscape (1920 × 1080) — Stream / Twitter</option>
            <option value="1080x1080">1:1 Square (1080 × 1080) — Social Post</option>
            <option value="1080x1350">4:5 Portrait (1080 × 1350) — Instagram Post</option>
            <option value="1080x1920">9:16 Story (1080 × 1920) — Reels / Stories</option>
          </select>
        </div>

        <div className="pt-2">
          <button
            onClick={onExport}
            disabled={!hasVersion || !canExport || isExporting}
            className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white text-sm font-bold rounded-md shadow-md transition-colors flex items-center justify-center gap-2"
          >
            {isExporting ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                <span>Exporting PNG...</span>
              </>
            ) : (
              <>
                <span>📸</span>
                <span>Export PNG</span>
              </>
            )}
          </button>
        </div>

        {hasVersion && !canExport && (
          <p className="text-xs text-amber-300">
            {hasExportPermission
              ? 'Refresh the provider results before publishing. Only a current Final version can be exported.'
              : 'Your role does not include results.manage, so static publishing is read-only.'}
          </p>
        )}

        {exportSuccessMessage && (
          <div className="p-3 bg-green-950/50 border border-green-800/80 rounded text-xs text-green-300 break-all space-y-1">
            <div className="font-bold flex items-center gap-1">
              <span>✅</span> Export Receipt Recorded
            </div>
            <div>{exportSuccessMessage}</div>
          </div>
        )}

        {exportErrorMessage && (
          <div className="p-3 bg-red-950/50 border border-red-800/80 rounded text-xs text-red-300">
            {exportErrorMessage}
          </div>
        )}
      </div>
    </div>
  );
};
