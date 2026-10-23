import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { useEditorStore } from '@/store/useEditorStore';
import { PlayerCardFieldsPanel } from './PlayerCardFieldsPanel';

describe('PlayerCardFieldsPanel', () => {
  beforeEach(() => {
    useEditorStore.setState({
      elements: {
        results: {
          id: 'results', type: 'results-group', templateId: 'master', visible: true,
          x: 0, y: 0, width: 1760, height: 850,
        } as any,
        master: {
          id: 'master', type: 'group', parentId: 'results', templateRole: 'player-card',
          childIds: [], visible: true, x: 0, y: 0, width: 500, height: 700,
        } as any,
      },
      selectedId: 'master',
      selectedIds: ['master'],
      editingResultCardDefinitionId: 'master',
      past: [],
      future: [],
    });
  });

  it.each([
    ['Prefix / Team', 'prefix', 'text'],
    ['Player Photo', 'avatarUrl', 'image'],
    ['Country Flag', 'countryFlagUrl', 'image'],
  ])('adds %s as one bound child of the master template', (label, binding, type) => {
    render(<PlayerCardFieldsPanel />);

    fireEvent.click(screen.getByRole('button', { name: new RegExp(label) }));

    const state = useEditorStore.getState();
    const childId = state.elements.master.childIds?.[0];
    expect(childId).toBeTruthy();
    expect(state.elements[childId!]).toMatchObject({ parentId: 'master', binding, type });
    expect(state.selectedId).toBe(childId);
    expect(state.past).toHaveLength(1);
  });

  it('disables a field that already exists instead of creating a duplicate binding', () => {
    render(<PlayerCardFieldsPanel />);
    const button = screen.getByRole('button', { name: /Prefix \/ Team/ });
    fireEvent.click(button);

    expect(screen.getByRole('button', { name: /Prefix \/ Team.*Added/ })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /Prefix \/ Team.*Added/ }));
    expect(useEditorStore.getState().elements.master.childIds).toHaveLength(1);
  });
});
