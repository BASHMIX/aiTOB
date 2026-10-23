import { describe, expect, it } from 'vitest';
import { createChampionFocusDocument } from '@/features/results/templates';
import { resizeSceneDocument } from './resizeScene';

describe('resizeSceneDocument', () => {
  it('reflows nodes, card slots, variants, and safe area into portrait output', () => {
    const source = createChampionFocusDocument();
    source.canvas.safeArea = { top: 20, right: 40, bottom: 20, left: 40 };
    const original = JSON.parse(JSON.stringify(source));
    const resized = resizeSceneDocument(source, 1080, 1350);
    const resultGroup = resized.nodes['rg-main'];
    const master = resized.nodes['master-player-card'];

    expect(resized.canvas).toMatchObject({ width: 1080, height: 1350 });
    expect(resized.canvas.safeArea).toEqual({ top: 25, right: 22.5, bottom: 25, left: 22.5 });
    expect(resultGroup.x).toBeCloseTo(original.nodes['rg-main'].x * (1080 / 1920));
    expect(resultGroup.y).toBeCloseTo(original.nodes['rg-main'].y * (1350 / 1080));
    expect(resultGroup.type === 'results-group' && resultGroup.customSlots?.[0].width)
      .toBeCloseTo(original.nodes['rg-main'].customSlots[0].width * (1080 / 1920));
    expect(master.type === 'group' && master.variants?.champion).toBeTruthy();
    expect(source.canvas).toMatchObject({ width: 1920, height: 1080 });
  });
});
