import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SidebarAddElements } from './SidebarAddElements';
import { useEditorStore } from '@/store/useEditorStore';

describe('SidebarAddElements result tools', () => {
  beforeEach(() => {
    useEditorStore.setState({ elements: {}, selectedId: null, selectedIds: [], past: [], future: [], editingResultCardDefinitionId: null });
  });

  it('keeps Add Results Group and adds a distinct freeform Result Card action', () => {
    render(<SidebarAddElements />);
    expect(screen.getByRole('button', { name: /Add Result Card/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Add Results Group/i })).toBeInTheDocument();
  });

  it('creates one atomic card, one scheduling parent, and one shared definition', () => {
    render(<SidebarAddElements />);
    fireEvent.click(screen.getByRole('button', { name: /Add Result Card/i }));
    const state = useEditorStore.getState();
    const card = Object.values(state.elements).find((element) => element.type === 'result-card');
    const scheduler = Object.values(state.elements).find((element) => element.type === 'results-cards');
    const definition = card?.definitionId ? state.elements[card.definitionId] : null;
    expect(card).toMatchObject({ instanceRole: 'stage', standingOrdinal: 1 });
    expect(scheduler?.childIds).toEqual([card?.id]);
    expect(definition).toMatchObject({ type: 'group', definitionRole: 'result-card' });
    expect(state.selectedId).toBe(card?.id);
  });
});

