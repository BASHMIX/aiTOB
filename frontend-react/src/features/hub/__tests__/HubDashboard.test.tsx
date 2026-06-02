import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { HubDashboard } from '../HubDashboard';
import { useHubStore } from '@/store/useHubStore';

// Mock child components
vi.mock('@/components/layout/TopNavigation', () => ({
  TopNavigation: () => <div data-testid="top-navigation">TopNavigation</div>
}));
vi.mock('../components/TournamentSettings', () => ({
  TournamentSettings: () => <div data-testid="tournament-settings">TournamentSettings</div>
}));
vi.mock('../components/ActiveMatchStatus', () => ({
  ActiveMatchStatus: () => <div data-testid="active-match-status">ActiveMatchStatus</div>
}));
vi.mock('../components/ActiveStreamsStatus', () => ({
  ActiveStreamsStatus: () => <div data-testid="active-streams-status">ActiveStreamsStatus</div>
}));
vi.mock('../components/MatchDashboard', () => ({
  MatchDashboard: () => <div data-testid="match-dashboard">MatchDashboard</div>
}));
vi.mock('../components/Conflicts', () => ({
  Conflicts: () => <div data-testid="conflicts">Conflicts</div>
}));
vi.mock('../components/BotFeed', () => ({
  BotFeed: () => <div data-testid="bot-feed">BotFeed</div>
}));
vi.mock('../components/GeneralSettings', () => ({
  GeneralSettings: () => <div data-testid="general-settings">GeneralSettings</div>
}));
vi.mock('../components/DispatcherMasterSwitch', () => ({
  DispatcherMasterSwitch: () => <div data-testid="dispatcher-master-switch">DispatcherMasterSwitch</div>
}));

// Mock axios
vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

// Mock websocket hook
const mockSocketOnEvent = { current: (_evt: any) => {} };
vi.mock('@/hooks/useHubSocket', () => ({
  useHubSocket: (onEvent: any) => {
    mockSocketOnEvent.current = onEvent;
  }
}));

describe('HubDashboard Integration', () => {
  beforeEach(() => {
    // Reset state before each test
    act(() => {
      useHubStore.setState({
        tournaments: [],
        currentSlug: null,
        matches: [],
        stations: [],
        status: { startgg_api: false, websockets: false, discord_bot: false, token_scope: null },
      });
    });

    vi.clearAllMocks();

    // Default axios mocks
    mockedAxios.get.mockImplementation(async (url) => {
      if (url === '/api/tournaments') {
        return { data: { tournaments: [{ slug: 'fnc1ststartgg', name: 'FNC 1', game: 'SF6' }] } };
      }
      if (url === '/api/active-matches') {
        return { data: { matches: [{ set_id: '1', p1_name: 'Player 1', p2_name: 'Player 2', status: 'not_started' }] } };
      }
      if (url === '/api/status') {
        return { data: { startgg_api: true, websockets: true, discord_bot: true, auto_dispatcher: false, token_scope: { valid: true, has_write_scope: true, error: null, user_name: 'Admin' } } };
      }
      if (url === '/api/settings') {
        return { data: { settings: { current_theme: 'dark' } } };
      }
      return { data: {} };
    });

    mockedAxios.post.mockResolvedValue({ data: { success: true } });
  });

  it('renders successfully and fetches initial data', async () => {
    render(<HubDashboard />);

    expect(screen.getByText('FNC Tournament Hub')).toBeInTheDocument();

    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith('/api/tournaments');
      expect(mockedAxios.get).toHaveBeenCalledWith('/api/active-matches');
      expect(mockedAxios.get).toHaveBeenCalledWith('/api/status');
    });

    const store = useHubStore.getState();
    expect(store.tournaments).toHaveLength(1);
    expect(store.matches).toHaveLength(1);
    expect(store.status.startgg_api).toBe(true);

    // Check default active tab
    expect(screen.getByTestId('active-match-status')).toBeInTheDocument();
    expect(screen.queryByTestId('tournament-settings')).not.toBeInTheDocument();
    expect(screen.queryByTestId('general-settings')).not.toBeInTheDocument();
  });

  it('displays token error and allows re-testing token', async () => {
    const user = userEvent.setup();
    mockedAxios.get.mockImplementation(async (url) => {
      if (url === '/api/status') {
        return { data: { startgg_api: true, websockets: true, discord_bot: true, auto_dispatcher: false, token_scope: { valid: false, has_write_scope: false, error: 'Token expired', user_name: 'Admin' } } };
      }
      return { data: {} };
    });

    render(<HubDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Start.gg Token Connection Impaired')).toBeInTheDocument();
    });

    const retestBtn = screen.getByRole('button', { name: /re-test token/i });
    expect(retestBtn).toBeInTheDocument();

    // Do not await the click yet, so we can check the PROBING state which is synchronous immediately after click before promise resolves
    const clickPromise = user.click(retestBtn);

    await waitFor(() => {
       expect(screen.getByText(/probing/i)).toBeInTheDocument();
    });

    await clickPromise;

    expect(mockedAxios.post).toHaveBeenCalledWith('/api/settings/token-check');

    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith('/api/tournaments'); // re-fetches
    });
  });

  it('handles tab switching correctly', async () => {
    const user = userEvent.setup();
    render(<HubDashboard />);

    // Default 'active'
    expect(screen.getByTestId('active-match-status')).toBeInTheDocument();

    // Switch to Registration
    await user.click(screen.getByRole('button', { name: 'REGISTRATION' }));
    expect(screen.queryByTestId('active-match-status')).not.toBeInTheDocument();
    expect(screen.getByTestId('tournament-settings')).toBeInTheDocument();

    // Switch to System
    await user.click(screen.getByRole('button', { name: 'SYSTEM' }));
    expect(screen.queryByTestId('tournament-settings')).not.toBeInTheDocument();
    expect(screen.getByTestId('general-settings')).toBeInTheDocument();
  });

  it('allows manual refresh via Match Dashboard button', async () => {
    const user = userEvent.setup();
    render(<HubDashboard />);

    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith('/api/tournaments');
    });

    mockedAxios.get.mockClear();

    const refreshBtn = screen.getByTitle('Refresh All Data');
    await user.click(refreshBtn);

    expect(mockedAxios.get).toHaveBeenCalledWith('/api/tournaments');
    expect(mockedAxios.get).toHaveBeenCalledWith('/api/active-matches');
  });

  it('re-fetches data when receiving socket events', async () => {
    render(<HubDashboard />);

    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith('/api/tournaments');
    });

    mockedAxios.get.mockClear();

    // Trigger mock socket (match_update triggers loadData, which fetches all endpoints)
    await act(async () => {
      mockSocketOnEvent.current({ type: 'match_update' });
    });

    expect(mockedAxios.get).toHaveBeenCalledWith('/api/tournaments');
    expect(mockedAxios.get).toHaveBeenCalledWith('/api/active-matches');

    mockedAxios.get.mockClear();

    await act(async () => {
      mockSocketOnEvent.current({ type: 'status_update' });
    });

    // loadData fetches tournaments, matches, status, settings
    expect(mockedAxios.get).toHaveBeenCalledWith('/api/status');
    expect(mockedAxios.get).toHaveBeenCalledWith('/api/tournaments');
  });
});
