import type { AnimationSettings, ResultCardLifecycle, ResultCardNode, ResultCardTransform } from './types';

export interface ResolvedResultCardAnimation {
  phase: 'pending' | 'enter' | 'visible' | 'exit' | 'complete';
  progress: number;
  transform: ResultCardTransform;
  visible: boolean;
}

const visibleTransform = (card: ResultCardNode): ResultCardTransform => ({
  x: card.x,
  y: card.y,
  scale: 1,
  opacity: card.opacity ?? 1,
  rotation: card.rotation ?? 0,
});

function hiddenTransform(card: ResultCardNode, animation: AnimationSettings): ResultCardTransform {
  const visible = visibleTransform(card);
  let x = visible.x;
  let y = visible.y;
  let opacity = animation.animationType === 'fly-in' ? visible.opacity : 0;
  const width = card.width || 420;
  const height = card.height || 560;
  const distance = animation.animationType === 'fly-in' ? null : 50;

  if (animation.direction.includes('left')) x = distance === null ? -width : x - distance;
  if (animation.direction.includes('right')) x = distance === null ? 1920 + width : x + distance;
  if (animation.direction.includes('top')) y = distance === null ? -height : y - distance;
  if (animation.direction.includes('bottom')) y = distance === null ? 1080 + height : y + distance;
  if (animation.direction === 'in-place') opacity = 0;

  return { ...visible, x, y, opacity };
}

/**
 * Result cards intentionally reuse the editor's standard Animation settings.
 * The older outerAnimation shape remains a read-only compatibility fallback
 * for scenes created before result cards joined the common animation system.
 */
export function resolveResultCardLifecycle(card: ResultCardNode): ResultCardLifecycle {
  const animation = card.animation;
  if (animation) {
    const visible = visibleTransform(card);
    const hidden = animation.animationType === 'none'
      ? visible
      : hiddenTransform(card, animation);
    const hasEnter = animation.animationType !== 'none' && animation.playOn !== 'OUT';
    const hasExit = animation.animationType !== 'none' && animation.playOn !== 'IN';
    return {
      start: hasEnter ? hidden : visible,
      visible,
      exit: hasExit ? hidden : visible,
      enterDurationMs: hasEnter ? Math.max(0, animation.duration) : 0,
      visibleHoldMs: hasExit ? Math.max(0, animation.delay) : 0,
      exitDurationMs: hasExit ? Math.max(0, animation.duration) : 0,
      enterEasing: animation.tweenType,
      exitEasing: animation.tweenType,
    };
  }

  if (card.outerAnimation) {
    const override = card.animationOverride || {};
    return {
      ...card.outerAnimation,
      ...override,
      start: { ...card.outerAnimation.start, ...(override.start || {}) },
      visible: { ...card.outerAnimation.visible, ...(override.visible || {}) },
      exit: { ...card.outerAnimation.exit, ...(override.exit || {}) },
    };
  }

  const visible = visibleTransform(card);
  return {
    start: visible,
    visible,
    exit: visible,
    enterDurationMs: 0,
    visibleHoldMs: 0,
    exitDurationMs: 0,
    enterEasing: 'linear',
    exitEasing: 'linear',
  };
}

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

function easingProgress(value: number, easing: ResultCardLifecycle['enterEasing']): number {
  const t = clamp01(value);
  switch (easing) {
    case 'ease-in': return t * t;
    case 'ease-out': return 1 - ((1 - t) * (1 - t));
    case 'ease-in-out': return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    case 'bounce': return 1 - Math.abs(Math.cos(t * Math.PI * 2.5) * (1 - t));
    case 'back-out': {
      const c1 = 1.70158;
      const c3 = c1 + 1;
      return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
    }
    case 'elastic': {
      if (t === 0 || t === 1) return t;
      return Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1;
    }
    default: return t;
  }
}

function interpolate(
  from: ResultCardTransform,
  to: ResultCardTransform,
  progress: number,
): ResultCardTransform {
  const t = clamp01(progress);
  return {
    x: from.x + ((to.x - from.x) * t),
    y: from.y + ((to.y - from.y) * t),
    scale: from.scale + ((to.scale - from.scale) * t),
    opacity: from.opacity + ((to.opacity - from.opacity) * t),
    rotation: from.rotation + ((to.rotation - from.rotation) * t),
  };
}

export function resultCardLifecycleDuration(lifecycle: ResultCardLifecycle): number {
  return Math.max(0, lifecycle.enterDurationMs)
    + Math.max(0, lifecycle.visibleHoldMs)
    + Math.max(0, lifecycle.exitDurationMs);
}

export function resolveResultCardAnimation(
  lifecycle: ResultCardLifecycle,
  elapsedMs: number,
): ResolvedResultCardAnimation {
  if (elapsedMs < 0) {
    return { phase: 'pending', progress: 0, transform: lifecycle.start, visible: false };
  }

  const enterDuration = Math.max(0, lifecycle.enterDurationMs);
  const holdDuration = Math.max(0, lifecycle.visibleHoldMs);
  const exitDuration = Math.max(0, lifecycle.exitDurationMs);

  if (enterDuration > 0 && elapsedMs < enterDuration) {
    const progress = easingProgress(elapsedMs / enterDuration, lifecycle.enterEasing);
    return {
      phase: 'enter',
      progress,
      transform: interpolate(lifecycle.start, lifecycle.visible, progress),
      visible: true,
    };
  }

  const afterEnter = elapsedMs - enterDuration;
  if (afterEnter < holdDuration || exitDuration === 0) {
    const completeWithoutExit = exitDuration === 0 && afterEnter >= holdDuration;
    return {
      phase: completeWithoutExit ? 'complete' : 'visible',
      progress: 1,
      transform: lifecycle.visible,
      visible: true,
    };
  }

  const afterHold = afterEnter - holdDuration;
  if (afterHold < exitDuration) {
    const progress = easingProgress(afterHold / exitDuration, lifecycle.exitEasing);
    return {
      phase: 'exit',
      progress,
      transform: interpolate(lifecycle.visible, lifecycle.exit, progress),
      visible: true,
    };
  }

  return { phase: 'complete', progress: 1, transform: lifecycle.exit, visible: false };
}
