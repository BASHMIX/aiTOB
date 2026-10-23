import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ResultCardRenderer } from './ResultCardRenderer';
import { createFreeformResultCardBundle } from './defaultResultCard';
import { MOCK_MISSING_MEDIA_STANDINGS, MOCK_NORMAL_STANDINGS } from '@/features/results/mockData';
import type { SceneDocumentV2 } from './types';
import { FLAG_IMAGE_PLACEHOLDER, PLAYER_IMAGE_PLACEHOLDER } from '@/utils/overlayAssets';

function sceneFixture(): SceneDocumentV2 {
  const bundle = createFreeformResultCardBundle('renderer');
  return {
    schemaVersion: 2,
    canvas: { width: 1920, height: 1080 },
    dataSource: { kind: 'tournament-results' },
    rootIds: [bundle.scheduler.id],
    nodes: {
      [bundle.scheduler.id]: bundle.scheduler as any,
      [bundle.card.id]: bundle.card as any,
      [bundle.definition.id]: bundle.definition as any,
      ...Object.fromEntries(bundle.children.map((child) => [child.id, child as any])),
    },
  };
}

describe('ResultCardRenderer', () => {
  it('resolves bound player fields and reuses one shared definition', () => {
    const scene = sceneFixture();
    const definitionId = 'result_card_definition_renderer';
    render(
      <>
        <ResultCardRenderer scene={scene} definitionId={definitionId} standing={MOCK_NORMAL_STANDINGS[0]} width={420} height={560} />
        <ResultCardRenderer scene={scene} definitionId={definitionId} standing={MOCK_NORMAL_STANDINGS[1]} width={420} height={560} />
      </>,
    );
    expect(screen.getByText('Knee')).toBeInTheDocument();
    expect(screen.getByText('Arslan Ash')).toBeInTheDocument();
    expect(screen.getByText('DRX')).toBeInTheDocument();
    expect(screen.getByText('Feng')).toBeInTheDocument();
    expect(screen.getAllByAltText('Country Flag')[0]).toHaveAttribute('src', expect.stringContaining('kr'));
    expect(screen.getAllByTestId(/result-card-/)).toHaveLength(2);
    expect(screen.getAllByTestId(/result-card-/).every((node) => node.dataset.resultCardDefinition === definitionId)).toBe(true);
  });

  it('uses only local deterministic fallbacks for missing player media', () => {
    const scene = sceneFixture();
    render(<ResultCardRenderer scene={scene} definitionId="result_card_definition_renderer" standing={MOCK_MISSING_MEDIA_STANDINGS[0]} width={420} height={560} />);
    const sources = screen.getAllByTestId('card-bound-image').map((image) => image.getAttribute('src'));
    expect(sources).toContain(PLAYER_IMAGE_PLACEHOLDER);
    expect(sources).toContain(FLAG_IMAGE_PLACEHOLDER);
    expect(sources.every((source) => !String(source).includes('example.com'))).toBe(true);
  });
});
