import { describe, expect, it } from 'vitest';
import { createFreeformResultCardBundle, createDefaultResultCardLifecycle } from './defaultResultCard';
import { resolveLinkedResultCards } from './resolveLinkedResultCards';
import { MOCK_NORMAL_STANDINGS } from '@/features/results/mockData';
import type { ResultCardNode, ResultsCardsSchedule } from './types';

const schedule: ResultsCardsSchedule = {
  order: 'placement-desc', delayBetweenStartsMs: 500,
  trigger: 'with-previous', keepPreviousVisible: false, loop: false,
};

function cards(): ResultCardNode[] {
  const base = createFreeformResultCardBundle('linked').card as ResultCardNode;
  return [1, 2, 3].map((ordinal, index) => ({
    ...base,
    id: `card-${ordinal}`,
    standingOrdinal: ordinal,
    instanceRole: index === 0 ? 'stage' : 'linked',
    animation: undefined,
    outerAnimation: createDefaultResultCardLifecycle(100 + index * 200, 200),
  }));
}

describe('resolveLinkedResultCards', () => {
  it('stagger-plays each authored card lifecycle while preserving card geometry', () => {
    const resolved = resolveLinkedResultCards(cards(), MOCK_NORMAL_STANDINGS, schedule, 750);
    expect(resolved.map((item) => item.startTimeMs)).toEqual([0, 500, 1000]);
    expect(resolved[0].card.standingOrdinal).toBe(3);
    expect(resolved.filter((item) => item.animation.visible)).toHaveLength(2);
  });

  it('supports after-previous timing and keep-visible without changing authored nodes', () => {
    const source = cards();
    const resolved = resolveLinkedResultCards(source, MOCK_NORMAL_STANDINGS, {
      ...schedule, trigger: 'after-previous', keepPreviousVisible: true,
    }, 3000);
    expect(resolved.map((item) => item.startTimeMs)).toEqual([0, 2500, 5000]);
    expect(resolved[0].animation.visible).toBe(true);
    expect(source[0].outerAnimation?.visible.x).toBe(100);
  });
});
