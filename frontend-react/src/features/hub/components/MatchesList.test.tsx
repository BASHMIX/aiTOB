import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MatchesList } from './MatchesList';
import type { MatchData } from './MatchCard';

// Mock the MatchCard component to simplify our testing of the MatchesList
vi.mock('./MatchCard', () => ({
  MatchCard: ({ match }: { match: MatchData }) => (
    <div data-testid="match-card" data-match-id={match.id} data-match-status={match.status}>
      Match {match.id} - {match.status}
    </div>
  ),
}));

const mockProps = {
  dqTimerSeconds: 600,
  autoDqEnabled: true,
  onAction: vi.fn(),
  onToggleStream: vi.fn(),
  stations: [],
};

const createMockMatch = (id: string, status: MatchData['status']): MatchData => ({
  id,
  status,
  pool: 'Pool 1',
  round: 'Round 1',
  players: [{ name: 'Player 1' }, { name: 'Player 2' }],
  isLocal: true,
  raw: {},
});

describe('MatchesList', () => {
  it('renders all group headers', () => {
    render(<MatchesList matches={[]} {...mockProps} />);

    expect(screen.getByText('Not Started')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Players Called')).toBeInTheDocument();
    expect(screen.getByText('Complete / DQ')).toBeInTheDocument();
  });

  it('renders empty state indicator when there are no matches for a group', () => {
    const { container } = render(<MatchesList matches={[]} {...mockProps} />);

    // There are 4 groups, so we expect 4 empty state indicators ('—')
    const emptyIndicators = container.querySelectorAll('.italic');
    expect(emptyIndicators.length).toBe(4);
    emptyIndicators.forEach(indicator => {
      expect(indicator).toHaveTextContent('—');
    });
  });

  it('distributes matches into correct groups', () => {
    const matches: MatchData[] = [
      createMockMatch('1', 'waiting'),
      createMockMatch('2', 'live'),
      createMockMatch('3', 'called'),
      createMockMatch('4', 'done'),
      createMockMatch('5', 'dq'),
    ];

    render(<MatchesList matches={matches} {...mockProps} />);

    const matchCards = screen.getAllByTestId('match-card');
    expect(matchCards).toHaveLength(5);

    // Each match should render correctly based on our mock
    expect(screen.getByText('Match 1 - waiting')).toBeInTheDocument();
    expect(screen.getByText('Match 2 - live')).toBeInTheDocument();
    expect(screen.getByText('Match 3 - called')).toBeInTheDocument();
    expect(screen.getByText('Match 4 - done')).toBeInTheDocument();
    expect(screen.getByText('Match 5 - dq')).toBeInTheDocument();

    // The empty indicator should not be present for groups with matches
    // But since all 4 groups have matches ("done" and "dq" go to "Complete / DQ",
    // "waiting" goes to "Not Started", "live" to "In Progress", "called" to "Players Called"),
    // there should be 0 empty state indicators.
    const { container } = render(<MatchesList matches={matches} {...mockProps} />);
    const emptyIndicators = container.querySelectorAll('.italic');
    expect(emptyIndicators.length).toBe(0);
  });

  it('buckets done and dq matches into the "Complete / DQ" group correctly', () => {
    const matches: MatchData[] = [
      createMockMatch('1', 'done'),
      createMockMatch('2', 'dq'),
    ];

    const { container } = render(<MatchesList matches={matches} {...mockProps} />);

    // Groups: Not Started, In Progress, Players Called should be empty (3 groups)
    const emptyIndicators = container.querySelectorAll('.italic');
    expect(emptyIndicators.length).toBe(3);

    const matchCards = screen.getAllByTestId('match-card');
    expect(matchCards).toHaveLength(2);
    expect(screen.getByText('Match 1 - done')).toBeInTheDocument();
    expect(screen.getByText('Match 2 - dq')).toBeInTheDocument();
  });
});
