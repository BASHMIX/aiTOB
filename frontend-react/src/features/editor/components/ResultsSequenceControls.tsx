import React, { useState, useEffect, useRef } from 'react';
import { useEditorStore } from '@/store/useEditorStore';
import { resolveSequence } from '@/scene/resolveSequence';
import { MOCK_DATASETS } from '@/features/results/mockData';
import type { ResultsGroupNode, GroupNode } from '@/scene/types';

export const ResultsSequenceControls: React.FC = () => {
  const store = useEditorStore();
  const selId = store.selectedId;
  const element = selId ? store.elements[selId] : null;

  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const resultsGroupId = element?.type === 'results-group' && element.mode === 'sequence'
    ? element.id
    : null;

  useEffect(() => {
    if (resultsGroupId) {
      useEditorStore.getState().setResultsPreviewCueIndex(resultsGroupId, -1);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [resultsGroupId]);

  if (!element || element.type !== 'results-group' || element.mode !== 'sequence') {
    return null;
  }

  const templateGroup = (element.templateId ? store.elements[element.templateId] : null) as GroupNode | null;
  const datasetKey = element.preview?.dataset || 'normal';
  const standings = MOCK_DATASETS[datasetKey] || MOCK_DATASETS.normal;

  const cues = templateGroup
    ? resolveSequence(element as unknown as ResultsGroupNode, templateGroup, standings)
    : [];

  const totalCues = cues.length || 8;
  const activeCueIndex = store.resultsPreviewCueIndex[element.id] ?? -1;
  const setActiveCueIndex = (value: number | ((previous: number) => number)) => {
    const current = useEditorStore.getState().resultsPreviewCueIndex[element.id] ?? -1;
    store.setResultsPreviewCueIndex(
      element.id,
      typeof value === 'function' ? value(current) : value,
    );
  };

  const handleNext = () => {
    setIsPlaying(false);
    if (timerRef.current) clearTimeout(timerRef.current);
    setActiveCueIndex((prev) => Math.min(totalCues - 1, prev + 1));
  };

  const handlePrev = () => {
    setIsPlaying(false);
    if (timerRef.current) clearTimeout(timerRef.current);
    setActiveCueIndex((prev) => Math.max(0, prev - 1));
  };

  const handleHold = () => {
    setIsPlaying(false);
    if (timerRef.current) clearTimeout(timerRef.current);
  };

  const handleRestart = () => {
    setIsPlaying(false);
    if (timerRef.current) clearTimeout(timerRef.current);
    setActiveCueIndex(0);
  };

  const handleClear = () => {
    setIsPlaying(false);
    if (timerRef.current) clearTimeout(timerRef.current);
    setActiveCueIndex(-1);
  };

  const handlePlayAll = () => {
    setIsPlaying(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    setActiveCueIndex(-1);

    const startDelay = Math.max(0, element.sequence?.startDelayMs ?? 300);
    const interval = Math.max(1, element.sequence?.intervalMs ?? 800);
    const hold = Math.max(0, element.sequence?.holdMs ?? 0);
    const shouldLoop = element.sequence?.loop === true;

    const reveal = (index: number) => {
      setActiveCueIndex(index);
      if (index < totalCues - 1) {
        timerRef.current = setTimeout(() => reveal(index + 1), interval);
      } else if (shouldLoop) {
        timerRef.current = setTimeout(() => {
          setActiveCueIndex(-1);
          timerRef.current = setTimeout(() => reveal(0), startDelay);
        }, hold);
      } else {
        timerRef.current = null;
        setIsPlaying(false);
      }
    };

    timerRef.current = setTimeout(() => reveal(0), startDelay);
  };

  const currentCue = activeCueIndex >= 0 && activeCueIndex < cues.length ? cues[activeCueIndex] : null;

  return (
    <div className="bg-[#1e1e1e] border border-amber-600/40 rounded-lg p-3 space-y-3 mb-4">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
          <span>🎬</span> Sequence Controller
        </h4>
        <div className="text-[11px] font-semibold text-gray-300">
          {activeCueIndex === -1 ? (
            <span className="text-gray-500 italic">{isPlaying ? 'Starting…' : 'Cleared'}</span>
          ) : (
            <span className="text-amber-300">
              Cue {activeCueIndex + 1} of {totalCues}
              {currentCue ? ` (${currentCue.standing.entrant_name}, #${currentCue.standing.placement})` : ''}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-1.5">
        <button
          onClick={handlePlayAll}
          className={`py-1.5 px-2 rounded text-xs font-bold transition-colors ${
            isPlaying ? 'bg-amber-600 text-white' : 'bg-[#333] hover:bg-[#444] text-white'
          }`}
        >
          ▶ Play All
        </button>
        <button
          onClick={handleNext}
          className="py-1.5 px-2 bg-[#333] hover:bg-[#444] rounded text-xs font-bold text-white transition-colors"
        >
          ⏭ Next
        </button>
        <button
          onClick={handlePrev}
          disabled={activeCueIndex <= 0}
          className="py-1.5 px-2 bg-[#333] hover:bg-[#444] disabled:opacity-40 rounded text-xs font-bold text-white transition-colors"
        >
          ⏮ Previous
        </button>
      </div>

      <div className="grid grid-cols-3 gap-1.5">
        <button
          onClick={handleHold}
          className="py-1.5 px-2 bg-[#2d2d2d] hover:bg-[#3d3d3d] border border-white/10 rounded text-xs font-semibold text-gray-200"
        >
          ⏸ Hold
        </button>
        <button
          onClick={handleRestart}
          className="py-1.5 px-2 bg-[#2d2d2d] hover:bg-[#3d3d3d] border border-white/10 rounded text-xs font-semibold text-gray-200"
        >
          🔄 Restart
        </button>
        <button
          onClick={handleClear}
          className="py-1.5 px-2 bg-[#2d2d2d] hover:bg-[#3d3d3d] border border-white/10 rounded text-xs font-semibold text-red-300"
        >
          ⏹ Clear
        </button>
      </div>
    </div>
  );
};
