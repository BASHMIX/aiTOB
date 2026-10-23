import { beforeEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { useEditorStore } from '@/store/useEditorStore';
import { MasterCardDesignView } from './MasterCardDesignView';

describe('MasterCardDesignView', () => {
  beforeEach(() => {
    useEditorStore.setState({
      elements: {
        results: {
          id: 'results', type: 'results-group', name: 'Results Group', templateId: 'master',
          mode: 'board', cutoff: 'top8', pageNumber: 1, pageSize: 8,
          layoutPresetId: 'champion-focus', variantRules: [],
          sequence: { order: 'champion-last', startDelayMs: 0, intervalMs: 500, holdMs: 0, exit: 'none', loop: false, manualCue: false },
          preview: { dataset: 'normal', count: 'top8', pageNumber: 1 },
          visible: true, x: 80, y: 150, width: 1760, height: 850,
        } as any,
        master: {
          id: 'master', type: 'group', name: 'Master Player Card', parentId: 'results',
          templateRole: 'player-card', definitionRole: 'result-card', childIds: ['name'], visible: true,
          x: 0, y: 0, width: 500, height: 700,
        } as any,
        name: {
          id: 'name', type: 'text', name: 'Player Name', parentId: 'master', binding: 'displayName',
          text: 'Player', visible: true, x: 30, y: 30, width: 300, height: 60,
        } as any,
      },
      selectedId: 'master',
      selectedIds: ['master'],
      editingResultCardDefinitionId: 'master',
    });
  });

  it('shows one isolated mock player card instead of the generated standings grid', () => {
    render(<MasterCardDesignView />);

    expect(screen.getByTestId('result-card-design-view')).toBeInTheDocument();
    expect(screen.getByText('Knee')).toBeInTheDocument();
    expect(screen.queryByTestId('results-group-results')).not.toBeInTheDocument();
  });

  it('shows the selected authored child boundary in card design view', () => {
    useEditorStore.setState({ selectedId: 'name', selectedIds: ['name'] });
    render(<MasterCardDesignView />);

    expect(screen.getByTestId('result-card-selected-child')).toHaveAttribute('data-selected', 'true');
  });

  it('does not replace the results layout while the Results Group is selected', () => {
    useEditorStore.setState({ selectedId: 'results', selectedIds: ['results'], editingResultCardDefinitionId: null });
    const { container } = render(<MasterCardDesignView />);

    expect(container).toBeEmptyDOMElement();
  });
});
