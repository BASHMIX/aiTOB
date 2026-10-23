import type { ResultCardNode, ResultsCardsSchedule, StandingEntrySnapshot } from './types';
import { resolveResultCardAnimation, resolveResultCardLifecycle, resultCardLifecycleDuration, type ResolvedResultCardAnimation } from './resolveResultCardAnimation';

export interface ResolvedLinkedResultCard {
  card: ResultCardNode;
  standing: StandingEntrySnapshot;
  startTimeMs: number;
  endTimeMs: number;
  animation: ResolvedResultCardAnimation;
}

export function resolveLinkedResultCards(
  cards: ResultCardNode[],
  standings: StandingEntrySnapshot[],
  schedule: ResultsCardsSchedule,
  elapsedMs: number,
): ResolvedLinkedResultCard[] {
  const byOrdinal = new Map(standings.map((standing) => [standing.ordinal, standing]));
  const authoredOrder = new Map(cards.map((card, index) => [card.id, index]));
  const ordered = [...cards].sort((a, b) => {
    if (schedule.order === 'custom') {
      const custom = schedule.customOrdinals || [];
      const ai = custom.indexOf(a.standingOrdinal);
      const bi = custom.indexOf(b.standingOrdinal);
      if (ai >= 0 || bi >= 0) return (ai < 0 ? Number.MAX_SAFE_INTEGER : ai) - (bi < 0 ? Number.MAX_SAFE_INTEGER : bi);
      return (authoredOrder.get(a.id) || 0) - (authoredOrder.get(b.id) || 0);
    }
    const aStanding = byOrdinal.get(a.standingOrdinal);
    const bStanding = byOrdinal.get(b.standingOrdinal);
    const delta = (aStanding?.placement || a.standingOrdinal) - (bStanding?.placement || b.standingOrdinal);
    return schedule.order === 'placement-desc' ? -delta : delta;
  });

  let cursor = 0;
  const scheduled = ordered.flatMap((card, index) => {
    const standing = byOrdinal.get(card.standingOrdinal);
    const lifecycle = resolveResultCardLifecycle(card);
    if (!standing) return [];
    const startTimeMs = index === 0 ? 0 : cursor;
    cursor = schedule.trigger === 'after-previous'
      ? startTimeMs + resultCardLifecycleDuration(lifecycle) + Math.max(0, schedule.delayBetweenStartsMs)
      : startTimeMs + Math.max(0, schedule.delayBetweenStartsMs);
    return [{ card, standing, lifecycle, startTimeMs }];
  });

  const totalDuration = scheduled.reduce(
    (maximum, item) => Math.max(maximum, item.startTimeMs + resultCardLifecycleDuration(item.lifecycle)),
    0,
  );
  const resolvedElapsed = schedule.loop && totalDuration > 0
    ? ((Math.max(0, elapsedMs) % totalDuration) + totalDuration) % totalDuration
    : elapsedMs;

  return scheduled.map(({ card, standing, lifecycle, startTimeMs }) => {
    let animation = resolveResultCardAnimation(lifecycle, resolvedElapsed - startTimeMs);
    if (schedule.keepPreviousVisible && animation.phase === 'complete') {
      animation = { phase: 'complete', progress: 1, transform: lifecycle.visible, visible: true };
    }
    return {
      card,
      standing,
      startTimeMs,
      endTimeMs: startTimeMs + resultCardLifecycleDuration(lifecycle),
      animation,
    };
  });
}
