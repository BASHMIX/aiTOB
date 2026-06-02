export function resolveCascadeDelays(elements: Record<string, any>) {
  const sorted = Object.entries(elements).sort(
    (a, b) => (a[1].zIndex || 0) - (b[1].zIndex || 0)
  );

  const resolvedDelays: Record<string, number> = {};
  let lastDuration = 0;

  for (let i = 0; i < sorted.length; i++) {
    const [id, el] = sorted[i];
    const anim = el.animation;
    if (!anim || anim.animationType === 'none') {
      resolvedDelays[id] = 0;
      continue;
    }

    const selfDelay = anim.delay || 0;
    const selfDuration = anim.duration || 500;

    if (anim.trigger === 'after-prev' && i > 0) {
      const prevId = sorted[i - 1][0];
      const start = (resolvedDelays[prevId] || 0) + lastDuration + selfDelay;
      resolvedDelays[id] = start;
    } else if (anim.trigger === 'with-prev' && i > 0) {
      const prevId = sorted[i - 1][0];
      const start = (resolvedDelays[prevId] || 0) + selfDelay;
      resolvedDelays[id] = start;
    } else {
      resolvedDelays[id] = selfDelay;
    }

    lastDuration = selfDuration;
  }

  return resolvedDelays;
}

export const getAnimationStyles = (el: any, cascadeDelay: number, transitionState: string) => {
  const anim = el.animation;
  if (!anim || anim.animationType === 'none') return {};

  const { animationType, direction, duration, delay, tweenType, playOn } = anim;

  // 1. Idle state - disable all transitions to prevent telemetry-triggered updates replaying
  if (transitionState === 'idle') {
    return {
      transition: 'none',
    };
  }

  const easings: Record<string, string> = {
    'linear': 'linear',
    'ease-in': 'ease-in',
    'ease-out': 'ease-out',
    'ease-in-out': 'ease-in-out',
    'bounce': 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
    'back-out': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
    'elastic': 'cubic-bezier(0.25, 1.36, 0.49, 1.16)'
  };
  const easing = easings[tweenType] || 'ease-out';

  let startX = 0;
  let startY = 0;
  let startOpacity = 1;

  const w = el.width || 250;
  const h = el.height || 60;
  const x = el.x || 0;
  const y = el.y || 0;

  const canvasWidth = 1920;
  const canvasHeight = 1080;

  if (animationType === 'fly-in') {
    if (direction === 'bottom') startY = canvasHeight - y;
    else if (direction === 'top') startY = -y - h;
    else if (direction === 'left') startX = -x - w;
    else if (direction === 'right') startX = canvasWidth - x;
    else if (direction === 'bottom-left') { startX = -x - w; startY = canvasHeight - y; }
    else if (direction === 'bottom-right') { startX = canvasWidth - x; startY = canvasHeight - y; }
    else if (direction === 'top-left') { startX = -x - w; startY = -y - h; }
    else if (direction === 'top-right') { startX = canvasWidth - x; startY = -y - h; }
  } else if (animationType === 'float-in') {
    startOpacity = 0;
    if (direction === 'bottom') startY = 50;
    else if (direction === 'top') startY = -50;
    else if (direction === 'left') startX = -50;
    else if (direction === 'right') startX = 50;
    else if (direction === 'bottom-left') { startX = -35; startY = 35; }
    else if (direction === 'bottom-right') { startX = 35; startY = 35; }
    else if (direction === 'top-left') { startX = -35; startY = -35; }
    else if (direction === 'top-right') { startX = 35; startY = -35; }
  } else if (animationType === 'fade-in') {
    startOpacity = 0;
  }

  const resolvedDelay = cascadeDelay;

  // Exit transition
  const isExit = transitionState === 'out' && (playOn === 'OUT' || playOn === 'BOTH');
  if (isExit) {
    return {
      transition: `transform ${duration}ms ${easing} ${delay}ms, opacity ${duration}ms ${easing} ${delay}ms`,
      transform: `translate(${startX}px, ${startY}px)`,
      opacity: startOpacity,
    };
  }

  // Entrance transition
  const isEntranceEnabled = playOn === 'IN' || playOn === 'BOTH';
  if (isEntranceEnabled) {
    if (transitionState === 'in') {
      return {
        transition: 'none',
        transform: `translate(${startX}px, ${startY}px)`,
        opacity: startOpacity,
      };
    }
    if (transitionState === 'run') {
      return {
        transition: `transform ${duration}ms ${easing} ${resolvedDelay}ms, opacity ${duration}ms ${easing} ${resolvedDelay}ms`,
        transform: 'translate(0, 0)',
        opacity: 1,
      };
    }
  }

  // Default stable state for elements not animating in or out
  return {
    transition: 'none',
    transform: 'translate(0, 0)',
    opacity: 1,
  };
};
