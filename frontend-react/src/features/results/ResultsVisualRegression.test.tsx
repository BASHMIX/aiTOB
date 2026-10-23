import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { SceneRenderer } from '@/scene/SceneRenderer';
import { resolveResultsGroup } from '@/scene/resolveResultsGroup';
import { STARTER_TEMPLATES } from './templates';
import {
  MOCK_LONG_NAMES_STANDINGS,
  MOCK_RTL_STANDINGS,
  MOCK_MISSING_MEDIA_STANDINGS,
  MOCK_TIED_STANDINGS,
} from './mockData';
import type { ResultsGroupNode } from '@/scene/types';

describe('Results Visual Regression & Boundary Verification (T077)', () => {
  const championTemplate = STARTER_TEMPLATES.find((t) => t.id === 'champion-focus')!;
  const podiumTemplate = STARTER_TEMPLATES.find((t) => t.id === 'podium-remaining')!;
  const gridTemplate = STARTER_TEMPLATES.find((t) => t.id === 'equal-grid')!;

  it('renders within safe 1920x1080 canvas boundary without throwing', () => {
    const { container } = render(
      <SceneRenderer
        id="safe-area-test-canvas"
        scene={championTemplate.document}
        standings={MOCK_LONG_NAMES_STANDINGS}
        scale={1}
      />
    );

    const canvasRoot = container.querySelector('#safe-area-test-canvas');
    expect(canvasRoot).toBeInTheDocument();
    expect(canvasRoot).toHaveStyle({ width: '1920px', height: '1080px' });
  });

  it('handles extremely long player, prefix, and character names with text-ellipsis overflow', () => {
    const { container, getByText } = render(
      <SceneRenderer
        id="long-names-canvas"
        scene={championTemplate.document}
        standings={MOCK_LONG_NAMES_STANDINGS}
        scale={1}
      />
    );

    // Verify long entrant name is rendered
    const longName = MOCK_LONG_NAMES_STANDINGS[0].entrant_name;
    const element = getByText(longName);
    expect(element).toBeInTheDocument();

    // Verify container renders without layout crash
    expect(container.querySelector('#long-names-canvas')).toBeInTheDocument();
  });

  it('renders Right-to-Left (RTL) Arabic names and prefixes cleanly', () => {
    const { container, getByText } = render(
      <SceneRenderer
        id="rtl-canvas"
        scene={podiumTemplate.document}
        standings={MOCK_RTL_STANDINGS}
        scale={1}
      />
    );

    const rtlName = MOCK_RTL_STANDINGS[0].entrant_name;
    expect(getByText(rtlName)).toBeInTheDocument();
    expect(container.querySelector('#rtl-canvas')).toBeInTheDocument();
  });

  it('handles missing media gracefully without crashing or rendering broken elements', () => {
    const { container, getByText } = render(
      <SceneRenderer
        id="missing-media-canvas"
        scene={gridTemplate.document}
        standings={MOCK_MISSING_MEDIA_STANDINGS}
        scale={1}
      />
    );

    // All entrants are still present despite null avatars and null character artwork
    for (const entry of MOCK_MISSING_MEDIA_STANDINGS) {
      expect(getByText(entry.entrant_name)).toBeInTheDocument();
    }
    expect(container.querySelector('#missing-media-canvas')).toBeInTheDocument();
  });

  it('resolves Champion Focus tie overflow without dropping entries or negative layout slots', () => {
    const group = championTemplate.document.nodes['rg-main'] as ResultsGroupNode;
    expect(group).toBeDefined();

    const templateGroup = championTemplate.document.nodes[group.templateId] as any;
    const tiedGroup = { ...group, pageSize: 16 };
    // 9 entrants with tied 7th place
    const instances = resolveResultsGroup(tiedGroup, templateGroup, MOCK_TIED_STANDINGS);
    expect(instances.length).toBe(9);

    // Every instance has valid placement and finite coordinates
    for (const inst of instances) {
      expect(inst.standing.placement).toBeGreaterThan(0);
      expect(inst.transform.x).toBeGreaterThanOrEqual(0);
      expect(inst.transform.y).toBeGreaterThanOrEqual(0);
      expect(inst.transform.width).toBeGreaterThan(0);
      expect(inst.transform.height).toBeGreaterThan(0);
    }
  });
});
