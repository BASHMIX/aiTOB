import type {
  GroupNode,
  ResultsGroupNode,
  SequenceCue,
  SequenceOrderKind,
  StandingEntrySnapshot,
} from './types';
import { resolveResultsGroup } from './resolveResultsGroup';

function sortForSequence(
  standings: StandingEntrySnapshot[],
  order: SequenceOrderKind,
): StandingEntrySnapshot[] {
  const sorted = [...standings];
  switch (order) {
    case 'champion-last':
      // Reverse placement order so 1st place is last
      return sorted.sort((a, b) => b.placement - a.placement || b.ordinal - a.ordinal);
    case 'podium-first':
      return sorted.sort((a, b) => {
        const aPodium = a.placement <= 3 ? 0 : 1;
        const bPodium = b.placement <= 3 ? 0 : 1;
        if (aPodium !== bPodium) return aPodium - bPodium;
        return a.placement - b.placement || a.ordinal - b.ordinal;
      });
    case 'placement-desc':
      return sorted.sort((a, b) => b.placement - a.placement || b.ordinal - a.ordinal);
    case 'placement-asc':
    default:
      return sorted.sort((a, b) => a.placement - b.placement || a.ordinal - b.ordinal);
  }
}

function sortInstancesForSpatialOrder(
  instances: ReturnType<typeof resolveResultsGroup>,
  order: SequenceOrderKind,
) {
  if (order !== 'row-major' && order !== 'column-major') return instances;
  return [...instances].sort((a, b) => {
    const primary = order === 'row-major'
      ? a.slot.y - b.slot.y
      : a.slot.x - b.slot.x;
    if (primary !== 0) return primary;
    const secondary = order === 'row-major'
      ? a.slot.x - b.slot.x
      : a.slot.y - b.slot.y;
    return secondary || a.standing.ordinal - b.standing.ordinal;
  });
}

export function resolveSequence(
  resultsGroupNode: ResultsGroupNode,
  templateGroup: GroupNode,
  standings: StandingEntrySnapshot[],
  pageOverride?: number,
): SequenceCue[] {
  const instances = resolveResultsGroup(resultsGroupNode, templateGroup, standings, pageOverride);
  if (instances.length === 0) return [];

  const seq = resultsGroupNode.sequence || {
    order: 'champion-last',
    startDelayMs: 300,
    intervalMs: 800,
    holdMs: 4000,
    exit: 'sequential',
    loop: false,
    manualCue: false,
  };

  // Reorder instances based on sequence order
  const orderKind = seq.order || 'champion-last';
  const orderedInstances = orderKind === 'row-major' || orderKind === 'column-major'
    ? sortInstancesForSpatialOrder(instances, orderKind)
    : sortForSequence(instances.map((inst) => inst.standing), orderKind)
        .map((standing) => instances.find((inst) => inst.standing.entrant_id === standing.entrant_id))
        .filter((instance): instance is (typeof instances)[number] => Boolean(instance));

  const startDelay = seq.startDelayMs || 0;
  const interval = seq.intervalMs || 800;
  const hold = seq.holdMs || 4000;

  const cues: SequenceCue[] = [];
  for (let i = 0; i < orderedInstances.length; i++) {
    const matchInst = orderedInstances[i];
    const standing = matchInst.standing;

    const enterMs = startDelay + i * interval;
    const exitMs = enterMs + hold;

    cues.push({
      cueId: `${resultsGroupNode.id}-cue-${standing.entrant_id}-${i}`,
      standing,
      slot: matchInst.slot,
      variant: matchInst.variant,
      order: i,
      enterMs,
      holdMs: hold,
      exitMs,
    });
  }

  return cues;
}

export function getCueVisibility(
  cues: SequenceCue[],
  activeCueIndex: number,
  exitMode: 'together' | 'sequential' | 'none',
): Record<string, boolean> {
  const vis: Record<string, boolean> = {};

  if (activeCueIndex < 0 || cues.length === 0) {
    for (const cue of cues) {
      vis[cue.cueId] = false;
    }
    return vis;
  }

  for (let i = 0; i < cues.length; i++) {
    const cue = cues[i];
    if (exitMode === 'sequential') {
      vis[cue.cueId] = i === activeCueIndex;
    } else {
      // 'together' or 'none': cards stay visible as sequence advances
      vis[cue.cueId] = i <= activeCueIndex;
    }
  }

  return vis;
}
