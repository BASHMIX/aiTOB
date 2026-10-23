import type {
  AutoSequenceRuntimeInstance,
  AutoSequenceSettings,
  ResultCardLifecycle,
  StandingEntrySnapshot,
} from './types';
import { resolveResultCardAnimation, resultCardLifecycleDuration } from './resolveResultCardAnimation';

function selectStandings(
  standings: StandingEntrySnapshot[],
  settings: AutoSequenceSettings,
): StandingEntrySnapshot[] {
  const cutoff = settings.range === 'top8' ? 8 : settings.range === 'top16' ? 16 : Number.POSITIVE_INFINITY;
  const eligible = standings.filter((standing) => standing.placement <= cutoff);
  const ordered = [...eligible].sort((a, b) => {
    if (settings.order === 'placement-desc') {
      return b.placement - a.placement || b.ordinal - a.ordinal;
    }
    return a.placement - b.placement || a.ordinal - b.ordinal;
  });

  if (settings.order === 'custom' && settings.customOrdinals?.length) {
    const byOrdinal = new Map(ordered.map((standing) => [standing.ordinal, standing]));
    const custom = settings.customOrdinals.map((ordinal) => byOrdinal.get(ordinal)).filter(Boolean) as StandingEntrySnapshot[];
    const used = new Set(custom.map((standing) => standing.ordinal));
    custom.push(...ordered.filter((standing) => !used.has(standing.ordinal)));
    ordered.splice(0, ordered.length, ...custom);
  }

  if (settings.range !== 'all') return ordered;
  const pageSize = Math.max(1, settings.pageSize || 16);
  const offset = Math.max(0, ((settings.pageNumber || 1) - 1) * pageSize);
  return ordered.slice(offset, offset + pageSize);
}

export function resolveAutoSequence(
  consumerId: string,
  standings: StandingEntrySnapshot[],
  lifecycle: ResultCardLifecycle,
  settings: AutoSequenceSettings,
  elapsedMs: number,
): AutoSequenceRuntimeInstance[] {
  const selected = selectStandings(standings, settings);
  const delay = Math.max(0, settings.delayBetweenStartsMs || 0);
  const lifecycleDuration = resultCardLifecycleDuration(lifecycle);

  return selected.map((standing, index) => {
    const startTimeMs = index * delay;
    const localElapsed = elapsedMs - startTimeMs;
    let resolved = resolveResultCardAnimation(lifecycle, localElapsed);

    if (resolved.phase === 'complete' && settings.endBehavior === 'keep-visible') {
      resolved = { phase: 'complete', progress: 1, transform: lifecycle.visible, visible: true };
    } else if (
      settings.endBehavior === 'clear-after-hold'
      && localElapsed >= Math.max(0, lifecycle.enterDurationMs) + Math.max(0, lifecycle.visibleHoldMs)
    ) {
      resolved = { phase: 'complete', progress: 1, transform: lifecycle.visible, visible: false };
    }

    return {
      runtimeId: `${consumerId}-runtime-${standing.entrant_id}-${standing.ordinal}`,
      standing,
      ordinalIndex: index,
      startTimeMs,
      endTimeMs: startTimeMs + lifecycleDuration,
      ...resolved,
    };
  });
}

