import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { createFreeformResultCardBundle } from '@/scene/defaultResultCard';
import { useEditorStore } from '@/store/useEditorStore';
import { SidebarAnimation } from './SidebarAnimation';
import { DraggableElement } from './DraggableElement';

describe('result card animation integration', () => {
  const bundle = createFreeformResultCardBundle('common-animation');

  beforeEach(() => {
    useEditorStore.setState({
      elements: {
        [bundle.scheduler.id]: bundle.scheduler,
        [bundle.card.id]: bundle.card,
        [bundle.definition.id]: bundle.definition,
        ...Object.fromEntries(bundle.children.map((child) => [child.id, child])),
      },
      selectedId: bundle.card.id,
      selectedIds: [bundle.card.id],
      past: [],
      future: [],
    });
  });

  it('uses the standard Animation panel and does not expose Card Motion', () => {
    render(<SidebarAnimation />);
    expect(screen.getByRole('heading', { name: /^Animation$/i })).toBeInTheDocument();
    expect(screen.getAllByRole('combobox')[0]).toHaveValue('float-in');
    expect(screen.queryByText(/Card Motion/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Play Preview/i })).toBeInTheDocument();
  });

  it('restores the authored card when sequence preview finishes', () => {
    const { container } = render(<DraggableElement id={bundle.card.id} element={bundle.card} scale={1} />);
    const wrapper = container.querySelector(`[data-overlay-element-id="${bundle.card.id}"]`);
    const visual = wrapper?.firstElementChild as HTMLElement;
    expect(visual.style.visibility).toBe('visible');

    act(() => window.dispatchEvent(new CustomEvent('result-sequence-control', {
      detail: { groupId: bundle.scheduler.id, action: 'restart' },
    })));
    expect(visual.style.visibility).toBe('hidden');

    act(() => window.dispatchEvent(new CustomEvent('result-sequence-preview-ended', {
      detail: { groupId: bundle.scheduler.id },
    })));
    expect(visual.style.visibility).toBe('visible');
  });
});
