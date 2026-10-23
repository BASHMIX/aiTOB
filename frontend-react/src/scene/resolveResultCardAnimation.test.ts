import { describe, expect, it } from 'vitest';
import { resolveResultCardAnimation, resolveResultCardLifecycle, resultCardLifecycleDuration } from './resolveResultCardAnimation';
import type { ResultCardLifecycle, ResultCardNode } from './types';

const lifecycle: ResultCardLifecycle = {
  start: { x: -100, y: 500, scale: 0.2, opacity: 0, rotation: -10 },
  visible: { x: 500, y: 200, scale: 1, opacity: 1, rotation: 0 },
  exit: { x: 1600, y: 200, scale: 0.8, opacity: 0, rotation: 10 },
  enterDurationMs: 500,
  visibleHoldMs: 1000,
  exitDurationMs: 500,
  enterEasing: 'linear',
  exitEasing: 'linear',
};

describe('resolveResultCardAnimation', () => {
  it('resolves Start, Visible, and Exit without a keyframe timeline', () => {
    expect(resolveResultCardAnimation(lifecycle, -1)).toMatchObject({ phase: 'pending', visible: false, transform: lifecycle.start });
    const entering = resolveResultCardAnimation(lifecycle, 250);
    expect(entering).toMatchObject({ phase: 'enter', visible: true, transform: { x: 200, y: 350, opacity: 0.5, rotation: -5 } });
    expect(entering.transform.scale).toBeCloseTo(0.6);
    expect(resolveResultCardAnimation(lifecycle, 1000)).toMatchObject({ phase: 'visible', transform: lifecycle.visible });
    const exiting = resolveResultCardAnimation(lifecycle, 1750);
    expect(exiting).toMatchObject({ phase: 'exit', transform: { x: 1050, y: 200, opacity: 0.5, rotation: 5 } });
    expect(exiting.transform.scale).toBeCloseTo(0.9);
    expect(resolveResultCardAnimation(lifecycle, 2000)).toMatchObject({ phase: 'complete', visible: false, transform: lifecycle.exit });
  });

  it('reports the complete lifecycle duration', () => {
    expect(resultCardLifecycleDuration(lifecycle)).toBe(2000);
  });

  it('derives result-card playback from the common editor animation settings', () => {
    const card: ResultCardNode = {
      id: 'card', type: 'result-card', definitionId: 'definition', instanceRole: 'stage', standingOrdinal: 1,
      visible: true, x: 400, y: 200, width: 420, height: 560, opacity: 0.8, rotation: 5,
      animation: {
        animationType: 'float-in', direction: 'left', duration: 600, delay: 250, loop: 0,
        tweenType: 'ease-in-out', playOn: 'BOTH', trigger: 'on-load',
      },
    };
    expect(resolveResultCardLifecycle(card)).toEqual({
      start: { x: 350, y: 200, scale: 1, opacity: 0, rotation: 5 },
      visible: { x: 400, y: 200, scale: 1, opacity: 0.8, rotation: 5 },
      exit: { x: 350, y: 200, scale: 1, opacity: 0, rotation: 5 },
      enterDurationMs: 600,
      visibleHoldMs: 250,
      exitDurationMs: 600,
      enterEasing: 'ease-in-out',
      exitEasing: 'ease-in-out',
    });
  });
});
