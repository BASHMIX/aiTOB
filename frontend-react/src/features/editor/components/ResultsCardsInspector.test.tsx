import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ResultsCardsInspector } from './ResultsCardsInspector';
import { createFreeformResultCardBundle } from '@/scene/defaultResultCard';
import { useEditorStore } from '@/store/useEditorStore';

describe('ResultsCardsInspector', () => {
  beforeEach(() => {
    const bundle = createFreeformResultCardBundle('schedule');
    useEditorStore.setState({
      elements: {
        [bundle.scheduler.id]: bundle.scheduler,
        [bundle.card.id]: bundle.card,
        [bundle.definition.id]: bundle.definition,
        ...Object.fromEntries(bundle.children.map((child) => [child.id, child])),
      },
      selectedId: bundle.scheduler.id,
      selectedIds: [bundle.scheduler.id],
      past: [], future: [],
    });
  });

  it('configures overlapping or after-previous member timing without layout controls', () => {
    render(<ResultsCardsInspector />);
    fireEvent.change(screen.getByLabelText(/Delay \/ stagger/i), { target: { value: '350' } });
    fireEvent.change(screen.getByLabelText(/Start next member/i), { target: { value: 'after-previous' } });
    const scheduler = Object.values(useEditorStore.getState().elements).find((item) => item.type === 'results-cards');
    expect(scheduler?.schedule).toMatchObject({ delayBetweenStartsMs: 350, trigger: 'after-previous' });
    expect(scheduler?.autoSequence).toMatchObject({ delayBetweenStartsMs: 350 });
    expect(screen.queryByLabelText(/Layout Preset/i)).not.toBeInTheDocument();
  });

  it('keeps placement and preview settings on the group instead of the card', () => {
    render(<ResultsCardsInspector />);
    fireEvent.change(screen.getByLabelText(/Placements/i), { target: { value: 'top16' } });
    fireEvent.change(screen.getByLabelText(/Preview data/i), { target: { value: 'long_names' } });
    const scheduler = Object.values(useEditorStore.getState().elements).find((item) => item.type === 'results-cards');
    expect(scheduler?.autoSequence?.range).toBe('top16');
    expect(scheduler?.preview?.dataset).toBe('long_names');
    expect(screen.queryByText(/^Result Card$/i)).not.toBeInTheDocument();
  });

  it('dispatches transport without mutating the authored nodes', () => {
    const before = JSON.stringify(useEditorStore.getState().elements);
    const dispatch = vi.spyOn(window, 'dispatchEvent');
    render(<ResultsCardsInspector />);
    fireEvent.click(screen.getByRole('button', { name: /Restart/i }));
    expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'result-sequence-control' }));
    expect(JSON.stringify(useEditorStore.getState().elements)).toBe(before);
  });
});
