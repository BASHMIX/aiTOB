import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import axios from 'axios';
import { TopNavigation } from './TopNavigation';
import { useHubStore } from '@/store/useHubStore';

// Mock axios
vi.mock('axios');
const mockedAxios = vi.mocked(axios);

// Mock Zustand store
vi.mock('@/store/useHubStore', () => ({
  useHubStore: vi.fn(),
}));

describe('TopNavigation Component', () => {
  const mockSetTournaments = vi.fn();
  const mockSetCurrentSlug = vi.fn();
  const mockSetMatches = vi.fn();
  const mockLogout = vi.fn();

  const baseStoreState = {
    tournaments: [
      { slug: 'tourney-1', name: 'Tournament 1' },
      { slug: 'tourney-2', name: 'Tournament 2' }
    ],
    currentSlug: 'tourney-1',
    setTournaments: mockSetTournaments,
    setCurrentSlug: mockSetCurrentSlug,
    setMatches: mockSetMatches,
    logout: mockLogout,
    status: {
      startgg_api: true,
      discord_bot: false,
      websockets: true
    }
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useHubStore).mockImplementation((selector: any) => {
      // If a selector is passed (like state => state.logout), call it with the state
      if (typeof selector === 'function') {
        return selector(baseStoreState);
      }
      return baseStoreState;
    });
  });

  it('renders initial state correctly with given status indicators', () => {
    render(<TopNavigation />);

    // Check logout button
    expect(screen.getByText('Logout')).toBeInTheDocument();

    // Check tournament dropdown options
    expect(screen.getByText('[ Tournament 1 ▼ ]')).toBeInTheDocument();
    expect(screen.getByText('[ Tournament 2 ▼ ]')).toBeInTheDocument();

    // Check Status indicators text
    expect(screen.getByText('Start.gg')).toBeInTheDocument();
    expect(screen.getByText('Bot')).toBeInTheDocument();
    expect(screen.getByText('WS')).toBeInTheDocument();

    // Check status dots colors by checking classes on the parent span elements
    // Start.gg is true -> bg-statusGreen
    const startGgDot = screen.getByText('Start.gg').previousSibling;
    expect(startGgDot).toHaveClass('bg-statusGreen');

    // Bot is false -> bg-statusRed
    const botDot = screen.getByText('Bot').previousSibling;
    expect(botDot).toHaveClass('bg-statusRed');

    // WS is true -> bg-statusGreen
    const wsDot = screen.getByText('WS').previousSibling;
    expect(wsDot).toHaveClass('bg-statusGreen');
  });

  it('calls logout when Logout button is clicked', async () => {
    render(<TopNavigation />);
    const logoutButton = screen.getByText('Logout');

    await userEvent.click(logoutButton);
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it('changes tournament selection when dropdown value changes', async () => {
    render(<TopNavigation />);

    const select = screen.getByRole('combobox');
    await userEvent.selectOptions(select, 'tourney-2');

    expect(mockSetCurrentSlug).toHaveBeenCalledWith('tourney-2');
  });

  it('calls globalRefresh and updates store when refresh button is clicked', async () => {
    mockedAxios.get.mockImplementation((url) => {
      if (url === '/api/tournaments') {
        return Promise.resolve({ data: { tournaments: [{ slug: 'refreshed-tourney', name: 'Refreshed' }] } });
      }
      if (url === '/api/active-matches') {
        return Promise.resolve({ data: { matches: [{ id: 'match-1' }] } });
      }
      return Promise.reject(new Error('not found'));
    });

    render(<TopNavigation />);

    const refreshButton = screen.getByTitle('Refresh All Data');
    await userEvent.click(refreshButton);

    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith('/api/tournaments');
      expect(mockedAxios.get).toHaveBeenCalledWith('/api/active-matches');
      expect(mockSetTournaments).toHaveBeenCalledWith([{ slug: 'refreshed-tourney', name: 'Refreshed' }]);
      expect(mockSetMatches).toHaveBeenCalledWith([{ id: 'match-1' }]);
    });
  });

  it('deletes tournament, refetches, and updates store when delete is confirmed', async () => {
    // Mock window.confirm to return true
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);

    mockedAxios.delete.mockResolvedValue({});
    mockedAxios.get.mockResolvedValue({
      data: { tournaments: [{ slug: 'remaining-tourney', name: 'Remaining' }] }
    });

    render(<TopNavigation />);

    const deleteButton = screen.getByTitle('Delete Tournament');
    await userEvent.click(deleteButton);

    expect(confirmSpy).toHaveBeenCalledWith(`Are you sure you want to delete the tournament 'tourney-1'?`);

    await waitFor(() => {
      expect(mockedAxios.delete).toHaveBeenCalledWith('/api/tournaments/tourney-1');
      expect(mockedAxios.get).toHaveBeenCalledWith('/api/tournaments');
      expect(mockSetTournaments).toHaveBeenCalledWith([{ slug: 'remaining-tourney', name: 'Remaining' }]);
      expect(mockSetCurrentSlug).toHaveBeenCalledWith('remaining-tourney');
    });

    confirmSpy.mockRestore();
  });

  it('handles empty tournament list after deletion correctly', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);

    mockedAxios.delete.mockResolvedValue({});
    mockedAxios.get.mockResolvedValue({
      data: { tournaments: [] }
    });

    render(<TopNavigation />);

    const deleteButton = screen.getByTitle('Delete Tournament');
    await userEvent.click(deleteButton);

    await waitFor(() => {
      expect(mockSetTournaments).toHaveBeenCalledWith([]);
      expect(mockSetCurrentSlug).toHaveBeenCalledWith(null);
    });

    confirmSpy.mockRestore();
  });

  it('does not delete tournament when confirm is cancelled', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => false);

    render(<TopNavigation />);

    const deleteButton = screen.getByTitle('Delete Tournament');
    await userEvent.click(deleteButton);

    expect(mockedAxios.delete).not.toHaveBeenCalled();

    confirmSpy.mockRestore();
  });
});
