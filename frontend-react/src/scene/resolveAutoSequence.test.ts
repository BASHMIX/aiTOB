import { describe, expect, it } from 'vitest';
import { MOCK_NORMAL_STANDINGS, MOCK_TIED_STANDINGS } from '@/features/results/mockData';
import { resolveAutoSequence } from './resolveAutoSequence';
import type { AutoSequenceSettings, ResultCardLifecycle } from './types';

const lifecycle: ResultCardLifecycle = {
  start: { x: 0, y: 0, scale: 0.1, opacity: 0, rotation: 0 },
  visible: { x: 500, y: 200, scale: 1, opacity: 1, rotation: 0 },
  exit: { x: 1200, y: 200, scale: 0.8, opacity: 0, rotation: 0 },
  enterDurationMs: 500,
  visibleHoldMs: 1000,
  exitDurationMs: 500,
  enterEasing: 'linear',
  exitEasing: 'linear',
};

const settings: AutoSequenceSettings = {
  enabled: true,
  stageInstanceId: 'stage',
  range: 'top8',
  pageNumber: 1,
  pageSize: 16,
  order: 'placement-desc',
  delayBetweenStartsMs: 500,
  endBehavior: 'card-exit',
};

describe('resolveAutoSequence', () => {
  it('uses Delay Between Starts as a stagger and allows overlapping lifecycles', () => {
    const instances = resolveAutoSequence('cards', MOCK_NORMAL_STANDINGS, lifecycle, settings, 1250);
    expect(instances.map((instance) => instance.startTimeMs)).toEqual([0, 500, 1000, 1500, 2000, 2500, 3000, 3500]);
    expect(instances.filter((instance) => instance.visible).length).toBeGreaterThan(1);
    expect(instances[0].standing.placement).toBe(7);
    expect(instances.at(-1)?.standing.placement).toBe(1);
  });

  it('starts every card together when stagger is zero', () => {
    const instances = resolveAutoSequence('cards', MOCK_NORMAL_STANDINGS, lifecycle, { ...settings, delayBetweenStartsMs: 0 }, 250);
    expect(new Set(instances.map((instance) => instance.startTimeMs))).toEqual(new Set([0]));
    expect(instances.every((instance) => instance.phase === 'enter')).toBe(true);
  });

  it('preserves every entrant tied inside the Top 8 cutoff', () => {
    const instances = resolveAutoSequence('cards', MOCK_TIED_STANDINGS, lifecycle, settings, 0);
    expect(instances).toHaveLength(9);
    expect(instances.filter((instance) => instance.standing.placement === 7)).toHaveLength(3);
  });
});

