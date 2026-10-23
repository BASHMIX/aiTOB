import { describe, it, expect } from 'vitest';
import { resolveSequence, getCueVisibility } from './resolveSequence';
import { createChampionFocusDocument } from '@/features/results/templates';
import { MOCK_NORMAL_STANDINGS } from '@/features/results/mockData';
import type { ResultsGroupNode, GroupNode } from './types';

describe('resolveSequence and cue timing', () => {
  const doc = createChampionFocusDocument();
  const rgNode = doc.nodes['rg-main'] as ResultsGroupNode;
  const templateGroup = doc.nodes['master-player-card'] as GroupNode;

  it('orders cues champion-last (8th down to 1st place)', () => {
    const sequenceSettings = {
      order: 'champion-last' as const,
      startDelayMs: 200,
      intervalMs: 1000,
      holdMs: 5000,
      exit: 'together' as const,
      loop: false,
      manualCue: false,
    };
    const rg: ResultsGroupNode = {
      ...rgNode,
      mode: 'sequence',
      sequence: sequenceSettings,
    };

    const cues = resolveSequence(rg, templateGroup, MOCK_NORMAL_STANDINGS);
    expect(cues.length).toBe(8);

    // First cue is lowest placement (7th/8th)
    expect(cues[0].standing.placement).toBeGreaterThanOrEqual(7);

    // Final cue is Champion (1st place)
    expect(cues[7].standing.placement).toBe(1);
    expect(cues[7].variant).toBe('champion');

    // Timing
    expect(cues[0].enterMs).toBe(200);
    expect(cues[1].enterMs).toBe(1200);
    expect(cues[7].enterMs).toBe(7200);
  });

  it('orders cues podium-first (1st, 2nd, 3rd, then remaining)', () => {
    const rg: ResultsGroupNode = {
      ...rgNode,
      mode: 'sequence',
      sequence: {
        order: 'podium-first',
        startDelayMs: 0,
        intervalMs: 500,
        holdMs: 3000,
        exit: 'none',
        loop: false,
        manualCue: false,
      },
    };

    const cues = resolveSequence(rg, templateGroup, MOCK_NORMAL_STANDINGS);
    expect(cues[0].standing.placement).toBe(1);
    expect(cues[1].standing.placement).toBe(2);
    expect(cues[2].standing.placement).toBe(3);
  });

  it('calculates cue visibility correctly for together and sequential exit modes', () => {
    const rg: ResultsGroupNode = {
      ...rgNode,
      mode: 'sequence',
      sequence: {
        order: 'champion-last',
        startDelayMs: 0,
        intervalMs: 500,
        holdMs: 3000,
        exit: 'together',
        loop: false,
        manualCue: false,
      },
    };

    const cues = resolveSequence(rg, templateGroup, MOCK_NORMAL_STANDINGS);

    // At cue index 2 in 'together' mode: cues 0, 1, 2 are visible
    const visTogether = getCueVisibility(cues, 2, 'together');
    expect(visTogether[cues[0].cueId]).toBe(true);
    expect(visTogether[cues[1].cueId]).toBe(true);
    expect(visTogether[cues[2].cueId]).toBe(true);
    expect(visTogether[cues[3].cueId]).toBe(false);

    // At cue index 2 in 'sequential' mode: only cue 2 is visible
    const visSequential = getCueVisibility(cues, 2, 'sequential');
    expect(visSequential[cues[0].cueId]).toBe(false);
    expect(visSequential[cues[1].cueId]).toBe(false);
    expect(visSequential[cues[2].cueId]).toBe(true);
    expect(visSequential[cues[3].cueId]).toBe(false);
  });

  it('orders row-major and column-major cues by slot geometry', () => {
    const customSlots = [
      { slotId: 'bottom-left', ordinal: 1, x: 0, y: 100, width: 100, height: 100, variant: 'standard' as const },
      { slotId: 'top-right', ordinal: 2, x: 100, y: 0, width: 100, height: 100, variant: 'standard' as const },
      { slotId: 'top-left', ordinal: 3, x: 0, y: 0, width: 100, height: 100, variant: 'standard' as const },
      { slotId: 'bottom-right', ordinal: 4, x: 100, y: 100, width: 100, height: 100, variant: 'standard' as const },
    ];
    const base: ResultsGroupNode = {
      ...rgNode,
      mode: 'sequence',
      cutoff: 'top8',
      pageSize: 4,
      customSlots,
      sequence: {
        order: 'row-major', startDelayMs: 0, intervalMs: 100,
        holdMs: 1000, exit: 'none', loop: false, manualCue: false,
      },
    };

    const rowMajor = resolveSequence(base, templateGroup, MOCK_NORMAL_STANDINGS);
    expect(rowMajor.map((cue) => cue.slot.slotId)).toEqual([
      'top-left', 'top-right', 'bottom-left', 'bottom-right',
    ]);

    const columnMajor = resolveSequence({
      ...base,
      sequence: { ...base.sequence!, order: 'column-major' },
    }, templateGroup, MOCK_NORMAL_STANDINGS);
    expect(columnMajor.map((cue) => cue.slot.slotId)).toEqual([
      'top-left', 'bottom-left', 'top-right', 'bottom-right',
    ]);
  });
});
