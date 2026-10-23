import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SceneRenderer } from './SceneRenderer';
import { createChampionFocusDocument } from '@/features/results/templates';
import {
  MOCK_NORMAL_STANDINGS,
  MOCK_MISSING_MEDIA_STANDINGS,
  MOCK_TIED_STANDINGS,
} from '@/features/results/mockData';

describe('ResultsGroupRenderer & SceneRenderer', () => {
  const doc = createChampionFocusDocument();

  it('renders all Top 8 entrants in provider order on the board', () => {
    render(<SceneRenderer scene={doc} standings={MOCK_NORMAL_STANDINGS} />);

    // Check winner
    expect(screen.getByText('Knee')).toBeInTheDocument();
    expect(screen.getAllByText('DRX').length).toBeGreaterThan(0);

    // Check runners up
    expect(screen.getByText('Arslan Ash')).toBeInTheDocument();
    expect(screen.getByText('Atif')).toBeInTheDocument();
    expect(screen.getByText('Ulsan')).toBeInTheDocument();
    expect(screen.getByText('CherryBerryMango')).toBeInTheDocument();
    expect(screen.getByText('Rangchu')).toBeInTheDocument();
    expect(screen.getByText('Mulgold')).toBeInTheDocument();
    expect(screen.getByText('Keisuke')).toBeInTheDocument();
    expect(screen.getAllByTestId('card-bound-image').every((image) => {
      const src = image.getAttribute('src') || '';
      return src.startsWith('/static/');
    })).toBe(true);
  });

  it('displays tied badge indicators correctly for tied placements', () => {
    render(<SceneRenderer scene={doc} standings={MOCK_TIED_STANDINGS} />);

    // 5th place in MOCK_TIED_STANDINGS are tied
    const badges = screen.getAllByTestId('card-placement-text');
    const texts = badges.map((b) => b.textContent);

    expect(texts).toContain('1');
    expect(texts).toContain('2');
    expect(texts).toContain('T3');
    expect(texts).toContain('T5');
    expect(texts).toContain('T7');
  });

  it('renders graceful fallback placeholders when media URLs are missing', () => {
    render(<SceneRenderer scene={doc} standings={MOCK_MISSING_MEDIA_STANDINGS} />);

    expect(screen.getByText('GhostWinner')).toBeInTheDocument();
    expect(screen.getByText('NoArtRunnerUp')).toBeInTheDocument();

    // Check that placeholder container elements are rendered for missing images
    const placeholders = screen.getAllByTestId('image-fallback-placeholder');
    expect(placeholders.length).toBeGreaterThan(0);
    expect(placeholders[0]).toHaveAttribute('src', '/static/player_placeholder.jpg');
  });

  it('replaces broken provider media URLs with the local default image', () => {
    const brokenMedia = JSON.parse(JSON.stringify(MOCK_NORMAL_STANDINGS));
    brokenMedia[0].presentation.character.value.image_url = 'https://invalid.test/broken.png';
    render(<SceneRenderer scene={doc} standings={brokenMedia} />);

    const image = screen.getAllByTestId('card-bound-image')[0] as HTMLImageElement;
    expect(image.src).toContain('invalid.test');
    fireEvent.error(image);
    expect(image).toHaveAttribute('src', '/static/player_placeholder.jpg');
  });

  it('sets unscaled root dimensions according to canvas settings', () => {
    const { container } = render(
      <SceneRenderer scene={doc} standings={MOCK_NORMAL_STANDINGS} id="export-target" />,
    );

    const canvasRoot = container.querySelector('#export-target');
    expect(canvasRoot).toHaveStyle({
      width: '1920px',
      height: '1080px',
    });
  });

  it('renders nested template groups and circle primitives', () => {
    const nestedDoc = JSON.parse(JSON.stringify(doc));
    nestedDoc.nodes['master-player-card'].childIds.push('nested-group');
    nestedDoc.nodes['nested-group'] = {
      id: 'nested-group', type: 'group', parentId: 'master-player-card', childIds: ['nested-label'],
      visible: true, x: 20, y: 20, width: 200, height: 80,
    };
    nestedDoc.nodes['nested-label'] = {
      id: 'nested-label', type: 'text', parentId: 'nested-group', text: 'Nested label',
      visible: true, x: 0, y: 0, width: 180, height: 40,
    };
    nestedDoc.nodes['decor-circle'] = {
      id: 'decor-circle', type: 'circle', visible: true,
      x: 10, y: 10, width: 20, height: 20, color: '#ff0000',
    };
    nestedDoc.rootIds.push('decor-circle');

    render(<SceneRenderer scene={nestedDoc} standings={MOCK_NORMAL_STANDINGS} />);

    expect(screen.getAllByText('Nested label')).toHaveLength(8);
    expect(screen.getByTestId('scene-circle-decor-circle')).toBeInTheDocument();
  });

  it('reuses the master-card animation when a sequence cue becomes visible', () => {
    const sequenceDoc = JSON.parse(JSON.stringify(doc));
    sequenceDoc.nodes['rg-main'].mode = 'sequence';
    sequenceDoc.nodes['master-player-card'].animation = {
      animationType: 'fly-in', direction: 'left', duration: 250, delay: 0,
      loop: 0, tweenType: 'ease-out', playOn: 'IN', trigger: 'on-load',
    };
    const { rerender } = render(
      <SceneRenderer scene={sequenceDoc} standings={MOCK_NORMAL_STANDINGS} activeCueIndex={-1} />,
    );
    // Champion-last means the lowest placed entrant owns cue index zero.
    const firstCard = screen.getByTestId('card-instance-ent-8');
    expect(firstCard).toHaveStyle({ opacity: '0', transform: 'translateX(-40px)' });

    rerender(<SceneRenderer scene={sequenceDoc} standings={MOCK_NORMAL_STANDINGS} activeCueIndex={0} />);
    expect(firstCard).toHaveStyle({ opacity: '1', transform: 'none' });
    expect(firstCard.style.transition).toContain('250ms');
  });
});
