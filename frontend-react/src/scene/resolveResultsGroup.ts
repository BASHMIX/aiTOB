import type {
  CardVariantKind,
  GroupNode,
  LayoutSlot,
  RenderCardInstance,
  ResultsGroupNode,
  StandingEntrySnapshot,
} from './types';

function determineVariant(
  placement: number,
  slotVariant?: CardVariantKind,
  variantRules?: ResultsGroupNode['variantRules'],
): CardVariantKind {
  if (variantRules && variantRules.length > 0) {
    for (const rule of variantRules) {
      const fromP = rule.fromPlacement;
      const toP = rule.toPlacement ?? rule.fromPlacement;
      if (placement >= fromP && placement <= toP) {
        return rule.variant;
      }
    }
  }
  if (slotVariant) {
    return slotVariant;
  }
  if (placement === 1) return 'champion';
  if (placement <= 4) return 'podium';
  return 'standard';
}

function generateFallbackSlot(
  resultsGroupNode: ResultsGroupNode,
  index: number,
  variant: CardVariantKind,
): LayoutSlot {
  const cols = 4;
  const col = index % cols;
  const row = Math.floor(index / cols);
  const cardW = Math.max(100, Math.floor((resultsGroupNode.width - (cols - 1) * 20) / cols));
  const cardH = 200;

  return {
    slotId: `fallback-slot-${index + 1}`,
    ordinal: index + 1,
    x: resultsGroupNode.x + col * (cardW + 20),
    y: resultsGroupNode.y + row * (cardH + 20),
    width: cardW,
    height: cardH,
    variant,
  };
}

export function resolveResultsGroup(
  resultsGroupNode: ResultsGroupNode,
  _templateGroup: GroupNode,
  standings: StandingEntrySnapshot[],
  pageOverride?: number,
): RenderCardInstance[] {
  if (!standings || standings.length === 0) {
    return [];
  }

  // 1. Cutoff filter (top8, top16, or all)
  const cutoff = resultsGroupNode.cutoff || 'top8';
  let filtered = standings;
  if (cutoff === 'top8') {
    filtered = standings.filter((s) => s.placement <= 8);
  } else if (cutoff === 'top16') {
    filtered = standings.filter((s) => s.placement <= 16);
  }

  // 2. Pagination
  const pageNumber = pageOverride ?? resultsGroupNode.pageNumber ?? 1;
  const pageSize = resultsGroupNode.pageSize ?? 8;
  const offset = Math.max(0, (pageNumber - 1) * pageSize);
  const pageStandings = filtered.slice(offset, offset + pageSize);

  // 3. Slot mapping & instance creation
  const customSlots = resultsGroupNode.customSlots || [];
  const instances: RenderCardInstance[] = [];

  for (let i = 0; i < pageStandings.length; i++) {
    const standing = pageStandings[i];
    const absoluteIndex = offset + i;

    // Match slot by ordinal or slot index
    let slot = customSlots.find((s) => s.ordinal === absoluteIndex + 1);
    if (!slot && i < customSlots.length) {
      slot = customSlots[i];
    }

    const variant = determineVariant(
      standing.placement,
      slot?.variant,
      resultsGroupNode.variantRules,
    );

    if (!slot) {
      slot = generateFallbackSlot(resultsGroupNode, i, variant);
    }

    instances.push({
      instanceId: `${resultsGroupNode.id}-card-${standing.entrant_id}-${absoluteIndex}`,
      standing,
      slot,
      variant,
      cueIndex: i,
      visible: true,
      transform: {
        x: slot.x,
        y: slot.y,
        width: slot.width,
        height: slot.height,
      },
    });
  }

  return instances;
}
