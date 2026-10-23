import type { OverlayElement } from '@/store/useEditorStore';

export interface ResultsTemplateContext {
  resultsGroup: OverlayElement;
  template: OverlayElement;
}

export interface ResultCardDefinitionContext {
  definition: OverlayElement;
  owner: OverlayElement | null;
  resultsGroup: OverlayElement | null;
  resultCard: OverlayElement | null;
}

export function findResultCardDefinitionContext(
  elements: Record<string, OverlayElement>,
  definitionId: string | null,
): ResultCardDefinitionContext | null {
  if (!definitionId) return null;
  const definition = elements[definitionId];
  if (!definition || definition.type !== 'group') return null;
  const resultsGroup = Object.values(elements).find(
    (candidate) => candidate.type === 'results-group'
      && (candidate.cardDefinitionId === definitionId || candidate.templateId === definitionId),
  ) || null;
  const resultCard = Object.values(elements).find(
    (candidate) => candidate.type === 'result-card' && candidate.definitionId === definitionId,
  ) || null;
  return {
    definition,
    owner: resultCard || resultsGroup,
    resultsGroup,
    resultCard,
  };
}

export function findResultsTemplateContext(
  elements: Record<string, OverlayElement>,
  selectedId: string | null,
): ResultsTemplateContext | null {
  if (!selectedId || !elements[selectedId]) return null;

  let currentId: string | undefined = selectedId;
  const visited = new Set<string>();
  while (currentId && !visited.has(currentId)) {
    visited.add(currentId);
    const resultsGroup = Object.values(elements).find(
      (candidate) => candidate.type === 'results-group'
        && (candidate.cardDefinitionId === currentId || candidate.templateId === currentId),
    );
    if (resultsGroup) {
      return { resultsGroup, template: elements[currentId] };
    }
    currentId = elements[currentId]?.parentId || undefined;
  }

  return null;
}
