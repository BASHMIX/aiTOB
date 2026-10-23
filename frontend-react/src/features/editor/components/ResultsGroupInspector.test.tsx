import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ResultsGroupInspector } from './ResultsGroupInspector';
import { useEditorStore } from '@/store/useEditorStore';

describe('ResultsGroupInspector component', () => {
  beforeEach(() => {
    useEditorStore.setState({
      elements: {
        'rg-1': {
          id: 'rg-1',
          name: 'Tournament Results Group',
          type: 'results-group',
          templateId: 'tpl-1',
          mode: 'board',
          cutoff: 'top8',
          pageNumber: 1,
          pageSize: 8,
          layoutPresetId: 'champion-focus',
          preview: { dataset: 'normal', count: 'top8', pageNumber: 1 },
          sequence: {
            order: 'champion-last',
            startDelayMs: 300,
            intervalMs: 800,
            holdMs: 4000,
            exit: 'sequential',
            loop: false,
            manualCue: false,
          },
          visible: true,
          x: 100,
          y: 100,
          width: 1720,
          height: 880,
        },
      },
      selectedId: 'rg-1',
      selectedIds: ['rg-1'],
    });
  });

  it('renders mode switch and switches between Board and Sequence modes', () => {
    render(<ResultsGroupInspector />);

    const streamRevealButton = screen.getByRole('button', { name: /Stream Reveal/i });
    fireEvent.click(streamRevealButton);

    expect(useEditorStore.getState().elements['rg-1']?.mode).toBe('sequence');

    const staticBoardButton = screen.getByRole('button', { name: /Static Board/i });
    fireEvent.click(staticBoardButton);

    expect(useEditorStore.getState().elements['rg-1']?.mode).toBe('board');
  });

  it('allows changing mock preview dataset and cutoff count', () => {
    render(<ResultsGroupInspector />);

    const datasetSelect = screen.getByLabelText(/Standings Source/i);
    fireEvent.change(datasetSelect, { target: { value: 'long_names' } });

    expect(useEditorStore.getState().elements['rg-1']?.preview?.dataset).toBe('long_names');

    const cutoffSelect = screen.getByLabelText(/Standings Cutoff/i);
    fireEvent.change(cutoffSelect, { target: { value: 'top16' } });

    expect(useEditorStore.getState().elements['rg-1']?.cutoff).toBe('top16');
    expect(useEditorStore.getState().elements['rg-1']?.pageSize).toBe(16);
    expect(useEditorStore.getState().elements['rg-1']?.preview?.count).toBe('top16');
  });

  it('applies real layout slots and opens the shared Result Card editor', () => {
    useEditorStore.setState({
      elements: {
        ...useEditorStore.getState().elements,
        'tpl-1': {
          id: 'tpl-1', type: 'group', templateRole: 'player-card', childIds: [],
          visible: true, x: 0, y: 0, width: 500, height: 700,
        },
      },
    });
    render(<ResultsGroupInspector />);

    fireEvent.change(screen.getByLabelText(/Layout Preset/i), { target: { value: 'equal-grid' } });
    expect(useEditorStore.getState().elements['rg-1']?.customSlots).toHaveLength(8);
    expect(useEditorStore.getState().elements['rg-1']?.layoutPresetId).toBe('equal-grid');

    fireEvent.click(screen.getByRole('button', { name: /Deep Edit Master Card Design/i }));
    expect(useEditorStore.getState().selectedId).toBe('tpl-1');
    expect(useEditorStore.getState().editingResultCardDefinitionId).toBe('tpl-1');
  });

  it('displays sequence animation settings when in Sequence mode', () => {
    useEditorStore.setState({
      elements: {
        'rg-1': {
          ...useEditorStore.getState().elements['rg-1'],
          mode: 'sequence',
        },
      },
      selectedId: 'rg-1',
    });

    render(<ResultsGroupInspector />);

    expect(screen.getByLabelText(/Reveal Style/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Sequence Order/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Step Interval \(ms\)/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Start Delay \(ms\)/i)).toBeInTheDocument();
  });

  it('materializes the current template layout as linked cards without copying the definition', () => {
    useEditorStore.setState({
      elements: {
        ...useEditorStore.getState().elements,
        'tpl-1': {
          id: 'tpl-1', type: 'group', definitionRole: 'result-card', childIds: ['name'],
          visible: true, x: 0, y: 0, width: 420, height: 560,
        },
        name: {
          id: 'name', type: 'text', parentId: 'tpl-1', binding: 'displayName',
          visible: true, x: 0, y: 0, width: 200, height: 40,
        },
      },
    });
    render(<ResultsGroupInspector />);

    fireEvent.click(screen.getByRole('button', { name: /Materialize Individual Freeform Cards/i }));

    const state = useEditorStore.getState();
    const scheduler = Object.values(state.elements).find((item) => item.type === 'results-cards');
    const cards = Object.values(state.elements).filter((item) => item.type === 'result-card');
    expect(scheduler?.childIds).toHaveLength(8);
    expect(cards).toHaveLength(8);
    expect(cards.every((item) => item.definitionId === 'tpl-1')).toBe(true);
    expect(Object.values(state.elements).filter((item) => item.definitionRole === 'result-card')).toHaveLength(1);
    expect(state.selectedId).toBe(scheduler?.id);
  });
});
