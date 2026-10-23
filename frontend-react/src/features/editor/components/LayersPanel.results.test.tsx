import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { getStructuralParentId, LayersPanel } from './LayersPanel';
import { useEditorStore } from '@/store/useEditorStore';
import { createFreeformResultCardBundle } from '@/scene/defaultResultCard';

describe('LayersPanel Scene v2 nested authoring', () => {
  beforeEach(() => {
    useEditorStore.setState({
      elements: {
        'rg-main': {
          id: 'rg-main',
          name: 'Results Group',
          type: 'results-group',
          templateId: 'tpl-card',
          visible: true,
          x: 100,
          y: 100,
          zIndex: 10,
        },
        'tpl-card': {
          id: 'tpl-card',
          name: 'Master Player Card',
          type: 'group',
          templateRole: 'player-card',
          childIds: ['card-name', 'card-art'],
          visible: true,
          x: 0,
          y: 0,
          zIndex: 9,
        },
        'card-name': {
          id: 'card-name',
          name: 'Player Name',
          parentId: 'tpl-card',
          type: 'text',
          visible: true,
          x: 20,
          y: 20,
          zIndex: 1,
        },
        'card-art': {
          id: 'card-art',
          name: 'Character Art',
          parentId: 'tpl-card',
          type: 'image',
          visible: true,
          x: 20,
          y: 60,
          zIndex: 2,
        },
        'bg-image': {
          id: 'bg-image',
          name: 'Background Art',
          type: 'image',
          visible: true,
          x: 0,
          y: 0,
          zIndex: 0,
        },
      },
      selectedId: null,
      selectedIds: [],
    });
  });

  it('renders Results Group and shared Result Card design badges in layers', () => {
    render(<LayersPanel />);

    expect(screen.getByText('Results Group')).toBeInTheDocument();
    expect(screen.getByText('Master Player Card')).toBeInTheDocument();
    expect(screen.getByText('Results')).toBeInTheDocument();
    expect(screen.getByText('Design')).toBeInTheDocument();
  });

  it('indents template child nodes under their parent group in the hierarchy', () => {
    render(<LayersPanel />);

    const childLayer = screen.getByText('Player Name').closest('[data-testid^="layer-row-"]');
    expect(childLayer).toHaveAttribute('data-nested', 'true');
    expect(childLayer).toHaveAttribute('data-depth', '2');
  });

  it('collapses the recursive results authoring tree without creating generated rows', () => {
    render(<LayersPanel />);

    fireEvent.click(screen.getByRole('button', { name: 'Collapse Results Group' }));

    expect(screen.queryByTestId('layer-row-tpl-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('layer-row-card-name')).not.toBeInTheDocument();
    expect(screen.getByTestId('layer-row-rg-main')).toBeInTheDocument();
  });

  it('contains zero generated player card rows (e.g. Player 1...8)', () => {
    render(<LayersPanel />);

    // Verify no generated card instances are in the layers list
    const allLayers = screen.getAllByTestId(/^layer-row-/);
    const layerNames = allLayers.map((l) => l.textContent);

    expect(layerNames.some((t) => t?.includes('Player 1'))).toBe(false);
    expect(layerNames.some((t) => t?.includes('Player 2'))).toBe(false);
    expect(layerNames.some((t) => t?.includes('Player 8'))).toBe(false);
    expect(allLayers.length).toBe(5); // Only authored nodes
  });

  it('allows selecting and toggling visibility on template and results nodes', () => {
    render(<LayersPanel />);

    const tplLayer = screen.getByText('Master Player Card');
    fireEvent.click(tplLayer);
    expect(useEditorStore.getState().selectedId).toBe('tpl-card');
    expect(screen.getByTestId('layer-row-tpl-card')).toHaveAttribute('data-selected', 'true');
    expect(screen.getByTestId('layer-row-tpl-card')).toHaveAttribute('aria-current', 'true');
  });

  it('does not offer manual instances for results groups or their master templates', () => {
    render(<LayersPanel />);

    expect(screen.queryByLabelText('Create instance of rg-main')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Create instance of tpl-card')).not.toBeInTheDocument();
  });

  it('keeps ordinary slide elements at root level and nests only structural group children', () => {
    const bundle = createFreeformResultCardBundle('layer-depth');
    useEditorStore.setState({
      elements: {
        image: {
          id: 'image', name: 'Image', type: 'image', visible: true,
          x: 0, y: 0, width: 100, height: 100, zIndex: 12,
        },
        text: {
          id: 'text', name: 'Text', type: 'text', visible: true,
          parentId: 'image', x: 0, y: 0, width: 100, height: 50, zIndex: 11,
        },
        [bundle.scheduler.id]: { ...bundle.scheduler, parentId: 'text', zIndex: 10 },
        [bundle.card.id]: bundle.card,
        [bundle.definition.id]: bundle.definition,
        ...Object.fromEntries(bundle.children.map((child) => [child.id, child])),
      },
      selectedId: null,
      selectedIds: [],
    });

    const currentElements = useEditorStore.getState().elements;
    expect(getStructuralParentId(currentElements, currentElements.text)).toBeNull();
    expect(getStructuralParentId(currentElements, currentElements[bundle.scheduler.id])).toBeNull();
    expect(getStructuralParentId(currentElements, currentElements[bundle.card.id])).toBe(bundle.scheduler.id);

    render(<LayersPanel />);

    expect(screen.getByTestId('layer-row-image')).toHaveAttribute('data-depth', '0');
    expect(screen.getByTestId('layer-row-text')).toHaveAttribute('data-depth', '0');
    expect(screen.getByTestId(`layer-row-${bundle.scheduler.id}`)).toHaveAttribute('data-depth', '0');
    expect(screen.getByTestId(`layer-row-${bundle.card.id}`)).toHaveAttribute('data-depth', '1');
  });
});
