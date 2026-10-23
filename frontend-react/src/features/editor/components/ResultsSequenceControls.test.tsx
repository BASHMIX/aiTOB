import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ResultsSequenceControls } from './ResultsSequenceControls';
import { useEditorStore } from '@/store/useEditorStore';

describe('ResultsSequenceControls component', () => {
  beforeEach(() => {
    useEditorStore.setState({
      elements: {
        'rg-seq': {
          id: 'rg-seq',
          name: 'Results Group',
          type: 'results-group',
          templateId: 'tpl-1',
          mode: 'sequence',
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
            exit: 'together',
            loop: false,
            manualCue: false,
          },
          visible: true,
          x: 100,
          y: 100,
        },
        'tpl-1': {
          id: 'tpl-1',
          name: 'Master Card',
          type: 'group',
          templateRole: 'player-card',
          childIds: [],
          visible: true,
          x: 0,
          y: 0,
        },
      },
      selectedId: 'rg-seq',
      selectedIds: ['rg-seq'],
    });
  });

  it('renders Play All, Next, Previous, Hold, Restart, and Clear control buttons', () => {
    render(<ResultsSequenceControls />);

    expect(screen.getByRole('button', { name: /Play All/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Next/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Previous/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Hold/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Restart/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Clear/i })).toBeInTheDocument();
  });

  it('advances cue index on Next and decreases on Previous', () => {
    render(<ResultsSequenceControls />);

    const nextBtn = screen.getByRole('button', { name: /Next/i });
    fireEvent.click(nextBtn);

    expect(screen.getByText(/Cue 1 of 8/i)).toBeInTheDocument();

    fireEvent.click(nextBtn);
    expect(screen.getByText(/Cue 2 of 8/i)).toBeInTheDocument();

    const prevBtn = screen.getByRole('button', { name: /Previous/i });
    fireEvent.click(prevBtn);
    expect(screen.getByText(/Cue 1 of 8/i)).toBeInTheDocument();
  });

  it('clears active cues on Clear button click', () => {
    render(<ResultsSequenceControls />);

    const nextBtn = screen.getByRole('button', { name: /Next/i });
    fireEvent.click(nextBtn);
    expect(screen.getByText(/Cue 1 of 8/i)).toBeInTheDocument();

    const clearBtn = screen.getByRole('button', { name: /Clear/i });
    fireEvent.click(clearBtn);

    expect(screen.getByText(/Cleared/i)).toBeInTheDocument();
  });
});
