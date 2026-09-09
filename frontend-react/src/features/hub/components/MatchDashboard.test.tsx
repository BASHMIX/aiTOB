import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { MatchDashboard } from './MatchDashboard';
import { useHubStore } from '@/store/useHubStore';

vi.mock('axios');
vi.mock('@/hooks/useHubSocket', () => ({ useHubSocket: () => undefined }));
vi.mock('./MatchSettingsModal', () => ({ MatchSettingsModal: () => null }));
vi.mock('./MatchesList', () => ({
  MatchesList: ({ matches }: { matches: Array<{ raw: { set_id: string; actions?: { call?: { enabled: boolean } } }; status: string }> }) => (
    <div>
      {matches.map((match) => (
        <div key={match.raw.set_id} data-testid={`match-${match.raw.set_id}`}>
          {match.status}:{String(match.raw.actions?.call?.enabled)}
        </div>
      ))}
    </div>
  ),
}));

const mockedAxios = vi.mocked(axios, true);
const repaired = ['471045156', '471045157', '471045159', '471045161'];

describe('MatchDashboard repaired Challonge projection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    act(() => useHubStore.setState({
      currentSlug: 'challonge:18449397', currentEventId: null, events: [], tournaments: [], stations: [],
      matches: repaired.map((id) => ({
        set_id: `challonge:fnc-jo:18449397:${id}`,
        tournament_slug: 'challonge:18449397', p1_name: 'Player A', p1_score: 0,
        p2_name: 'Player B', p2_score: 0, round_name: 'Round 1',
        status: 'not_started', hub_status: 'not_started', provider_state_raw: 'open',
        eligibility: { two_sided: true, actionable: true },
        actions: { call: { kind: 'local', enabled: true, label: 'Call in aiTOB' } },
      })),
      plannedStreamIds: [], streamGate: null,
    }));
    mockedAxios.get.mockImplementation(async (url) => {
      if (url === '/api/active-matches') return { data: { matches: useHubStore.getState().matches } };
      if (String(url).includes('/sets')) return { data: { sets: [] } };
      if (url === '/api/planned-streams') return { data: { planned: [] } };
      return { data: {} };
    });
  });

  it('renders repaired matches as waiting with local Call available', async () => {
    render(<MatchDashboard />);
    await waitFor(() => {
      for (const id of repaired) {
        expect(screen.getByTestId(`match-challonge:fnc-jo:18449397:${id}`)).toHaveTextContent('waiting:true');
      }
    });
  });

  it('keeps provider-native Challonge rounds, including loser-side negative rounds, without a Start.gg stream check', async () => {
    act(() => useHubStore.setState({
      tournaments: [{ slug: 'challonge:18449397', name: 'Challonge test', game: 'SF6', raw_data: '{}', provider_type: 'challonge' }],
      matches: [
        {
          set_id: 'challonge:round-12', tournament_slug: 'challonge:18449397',
          p1_name: 'Player A', p2_name: 'Player B', p1_score: 0, p2_score: 0,
          round_name: 'Round 12 · Semi Finals', status: 'not_started',
          actions: { call: { kind: 'local', enabled: true, label: 'Call in aiTOB' } },
        },
        {
          set_id: 'challonge:round-minus-1', tournament_slug: 'challonge:18449397',
          p1_name: 'Player C', p2_name: 'Player D', p1_score: 0, p2_score: 0,
          round_name: 'Losers Round -1', status: 'not_started',
          actions: { call: { kind: 'local', enabled: true, label: 'Call in aiTOB' } },
        },
      ],
      streamGate: { ok: false, reason: 'unlinked', warning: 'Start.gg-only warning', startgg_streams: [], stations: [] },
    }));
    // A previous dashboard instance may finish its async cleanup just before this
    // render; only inspect calls caused by this explicit Challonge render.
    mockedAxios.get.mockClear();

    render(<MatchDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Bracket round:')).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Round 12 · Semi Finals' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Losers Round -1' })).toBeInTheDocument();
    });
    expect(screen.queryByText('Event:')).not.toBeInTheDocument();
    expect(screen.queryByText('Pool:')).not.toBeInTheDocument();
    expect(screen.queryByText('Start.gg-only warning')).not.toBeInTheDocument();
    expect(mockedAxios.get.mock.calls.some(([url]) => url === '/api/tournaments/challonge:18449397/verify-stream')).toBe(false);
  });

  it('labels a verified Challonge single-player forfeit as DQ rather than a generic completion', async () => {
    act(() => useHubStore.setState({
      tournaments: [{ slug: 'challonge:18449397', name: 'Challonge test', game: 'SF6', raw_data: '{}', provider_type: 'challonge' }],
      matches: [{
        set_id: 'challonge:dq-result', tournament_slug: 'challonge:18449397',
        p1_name: 'Winner', p2_name: 'Withdrawn player', p1_score: 0, p2_score: -1,
        round_name: 'Bracket · Round 2', status: 'complete', hub_status: 'complete',
        result_kind: 'dq', dq_player: 'p2',
      }],
    }));

    render(<MatchDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('match-challonge:dq-result')).toHaveTextContent('dq:undefined');
    });
  });
});
