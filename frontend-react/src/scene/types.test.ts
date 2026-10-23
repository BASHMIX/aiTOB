import { describe, expect, it } from 'vitest';
import type { ResultCardNode, ResultsCardsNode, SceneDocumentV2 } from './types';
import { createFreeformResultCardBundle } from './defaultResultCard';

describe('Result Card scene contract', () => {
  it('creates one canonical definition, one stage instance, and one scheduling parent', () => {
    const bundle = createFreeformResultCardBundle('contract');
    const card = bundle.card as ResultCardNode;
    const scheduler = bundle.scheduler as ResultsCardsNode;
    const scene: SceneDocumentV2 = {
      schemaVersion: 2,
      canvas: { width: 1920, height: 1080 },
      dataSource: { kind: 'tournament-results' },
      rootIds: [scheduler.id],
      nodes: {
        [scheduler.id]: scheduler,
        [card.id]: card,
        [bundle.definition.id]: bundle.definition as any,
        ...Object.fromEntries(bundle.children.map((child) => [child.id, child])),
      },
    };

    expect(scene.rootIds).toEqual([scheduler.id]);
    expect(scheduler.childIds).toEqual([card.id]);
    expect(card.definitionId).toBe(bundle.definition.id);
    expect(card.animation).toMatchObject({
      animationType: 'float-in',
      direction: 'bottom',
      duration: 500,
      playOn: 'IN',
    });
    expect(card.outerAnimation).toBeUndefined();
    expect(bundle.definition).toMatchObject({ definitionRole: 'result-card' });
  });
});
