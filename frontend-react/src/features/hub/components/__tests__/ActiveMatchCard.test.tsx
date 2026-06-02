import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { ActiveMatchCard } from '../ActiveMatchCard';
import { useHubStore } from '@/store/useHubStore';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import axios from 'axios';

vi.mock('@/store/useHubStore');
vi.mock('axios');

const mockSetMatches = vi.fn();

const defaultMockMatch = {
  set_id: '123',
  p1_name: 'Player 1',
  p2_name: 'Player 2',
  p1_score: 0,
  p2_score: 0,
  bot_enabled: true,
  swapped: false,
  status: 'called',
  station_id: null,
};

let mockStoreState: any;

describe('ActiveMatchCard', () => {
  beforeEach(() => {
    mockStoreState = {
      stations: [
        { id: 'st1', name: 'Station 1' },
        { id: 'st2', name: 'Station 2' }
      ],
      matches: [{ ...defaultMockMatch }],
      setMatches: mockSetMatches,
      tournaments: [{ slug: 'test-tourney', dq_timer_seconds: 600 }],
      currentSlug: 'test-tourney',
    };
    (useHubStore as any).mockReturnValue(mockStoreState);
    (useHubStore as any).getState = vi.fn(() => mockStoreState);

    // Default resolve for all axios calls
    (axios.delete as any).mockResolvedValue({ data: {} });
    (axios.patch as any).mockResolvedValue({ data: {} });
    (axios.post as any).mockResolvedValue({ data: {} });

    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  describe('Rendering', () => {
    it('renders match information correctly', () => {
      const match = { ...defaultMockMatch, round_name: 'Winners Final', match_number: 'M-10' };
      render(<ActiveMatchCard match={match} />);

      expect(screen.getByText('Match#: M-10')).toBeInTheDocument();
      expect(screen.getByText('Player 1')).toBeInTheDocument();
      expect(screen.getByText('Player 2')).toBeInTheDocument();
      expect(screen.getByText('Winners Final')).toBeInTheDocument();
      expect(screen.getByText('NOT LIVE')).toBeInTheDocument();
    });

    it('renders LIVE ON state if station is assigned', () => {
      const match = { ...defaultMockMatch, station_id: 'st1', status: 'in_progress' };
      render(<ActiveMatchCard match={match} />);

      expect(screen.getByText('LIVE ON')).toBeInTheDocument();
      expect(screen.getByText('Station 1')).toBeInTheDocument();
    });
  });

  describe('Closing Match', () => {
    it('calls axios.delete and updates store when close button is clicked', async () => {
      render(<ActiveMatchCard match={defaultMockMatch} />);

      const closeButton = screen.getByTitle('Remove from On-Stream panel');
      fireEvent.click(closeButton);

      expect(axios.delete).toHaveBeenCalledWith(`/api/active-matches/${defaultMockMatch.set_id}`);

      // We don't want to use fake timers here as it messes with waitFor and interval timers in the component
      vi.useRealTimers();

      await waitFor(() => {
        expect(mockSetMatches).toHaveBeenCalledWith([]);
      });

      vi.useFakeTimers(); // Put back fake timers for other tests
    });
  });

  describe('Scores', () => {
    it('increments player 1 score optimistically and sends patch request', async () => {
      render(<ActiveMatchCard match={defaultMockMatch} />);

      const p1ScoreContainer = screen.getByText('Player 1').closest('div')?.parentElement;
      const upButton = p1ScoreContainer?.querySelector('button:first-of-type');

      if (upButton) {
        fireEvent.click(upButton);
      }

      expect(mockSetMatches).toHaveBeenCalledWith([
        { ...defaultMockMatch, p1_score: 1 }
      ]);

      mockStoreState.matches = [{ ...defaultMockMatch, p1_score: 1 }];

      // Fast-forward timer to trigger debounced axios call
      act(() => {
        vi.advanceTimersByTime(400);
      });

      expect(axios.patch).toHaveBeenCalledWith(`/api/active-matches/${defaultMockMatch.set_id}`, { p1_score: 1 });
    });

    it('decrements player 2 score optimistically but not below 0', async () => {
      const match = { ...defaultMockMatch, p2_score: 0 };
      render(<ActiveMatchCard match={match} />);

      const p2ScoreContainer = screen.getByText('Player 2').closest('div')?.parentElement;
      const downButton = p2ScoreContainer?.querySelectorAll('button')[1];

      if (downButton) {
        fireEvent.click(downButton);
      }

      expect(mockSetMatches).toHaveBeenCalledWith([
        { ...match, p2_score: 0 } // Score should remain 0
      ]);
    });
  });

  describe('Actions', () => {
    it('toggles bot enabled state', async () => {
      render(<ActiveMatchCard match={defaultMockMatch} />);

      const botButton = screen.getByTitle('Disable Bot for this match');
      fireEvent.click(botButton);

      expect(mockSetMatches).toHaveBeenCalledWith([
        { ...defaultMockMatch, bot_enabled: false }
      ]);
      expect(axios.patch).toHaveBeenCalledWith(`/api/active-matches/${defaultMockMatch.set_id}`, { bot_enabled: false });
    });

    it('toggles player swap state', async () => {
      render(<ActiveMatchCard match={defaultMockMatch} />);

      const swapButton = screen.getByTitle('Swap player display positions in OBS overlay');
      fireEvent.click(swapButton);

      expect(mockSetMatches).toHaveBeenCalledWith([
        { ...defaultMockMatch, swapped: true }
      ]);
      expect(axios.patch).toHaveBeenCalledWith(`/api/active-matches/${defaultMockMatch.set_id}`, { swapped: true });
    });

    it('forces DQ for a player', async () => {
      vi.useRealTimers();
      render(<ActiveMatchCard match={defaultMockMatch} />);

      // Open DQ menu
      const dqButton = screen.getByTitle('Force DQ a player');
      fireEvent.click(dqButton);

      // Click P1 DQ (using queryAllByText because 'Player 1' appears twice: once in the card, once in the dropdown)
      const p1DqButtons = screen.queryAllByText('Player 1');
      // The dropdown button is likely the second one
      fireEvent.click(p1DqButtons[1] || p1DqButtons[0]);

      // Wait for async state update
      await waitFor(() => {
        expect(axios.post).toHaveBeenCalledWith(`/api/active-matches/${defaultMockMatch.set_id}/dq`, { player: 'p1' });
      });
      await waitFor(() => {
        expect(mockSetMatches).toHaveBeenCalledWith([
          { ...defaultMockMatch, status: 'dq' }
        ]);
      });
      vi.useFakeTimers();
    });

    it('sends score and completes match', async () => {
      vi.useRealTimers();
      render(<ActiveMatchCard match={defaultMockMatch} />);

      const sendButton = screen.getByTitle('Report score to Start.gg and close match');
      fireEvent.click(sendButton);

      expect(axios.post).toHaveBeenCalledWith(`/api/active-matches/${defaultMockMatch.set_id}/send`);

      await waitFor(() => {
        expect(mockSetMatches).toHaveBeenCalledWith([
          { ...defaultMockMatch, status: 'complete' }
        ]);
      });
      vi.useFakeTimers();
    });

    it('assigns a station', async () => {
      vi.useRealTimers();
      render(<ActiveMatchCard match={defaultMockMatch} />);

      // Open station dropdown
      const stationToggle = screen.getByText(/— station —/i).closest('button');
      if (stationToggle) fireEvent.click(stationToggle);

      // Click Station 1
      const station1Button = screen.getByText('Station 1').closest('button');
      if (station1Button) {
        // use getByText inside the test and click it
        fireEvent.click(station1Button);

        await waitFor(() => {
          expect(axios.patch).toHaveBeenCalledWith(`/api/active-matches/${defaultMockMatch.set_id}`, {
            station_id: 'st1',
            status: 'in_progress'
          });
        });
        await waitFor(() => {
          expect(mockSetMatches).toHaveBeenCalledWith([
            { ...defaultMockMatch, station_id: 'st1' }
          ]);
        });
      } else {
        throw new Error("Could not find Station 1 button");
      }
      vi.useFakeTimers();
    });
  });

});
