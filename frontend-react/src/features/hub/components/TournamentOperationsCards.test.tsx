import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useHubStore } from '@/store/useHubStore';
import { TournamentOperationsCards } from './TournamentOperationsCards';
import { reopenTournamentSetup } from '@/features/tournament-setup/api';

const navigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

vi.mock('@/features/tournament-setup/api', async () => {
  const actual = await vi.importActual<typeof import('@/features/tournament-setup/api')>('@/features/tournament-setup/api');
  return { ...actual, reopenTournamentSetup: vi.fn() };
});

const mockedReopen = vi.mocked(reopenTournamentSetup);

describe('TournamentOperationsCards edit action', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    act(() => useHubStore.setState({
      tournaments: [{
        slug: 'tournament/testfnc', name: 'TestFNC', game: 'Street Fighter 6',
        raw_data: '{}', provider_type: 'startgg', provider_sync_status: 'ready',
      }],
      pinnedTournamentSlugs: ['tournament/testfnc'],
      currentSlug: 'tournament/testfnc',
      currentEventId: null,
      events: [],
      matches: [],
      session: { user_id: 'u', email: 'u@example.com', display_name: 'Owner', workspace_id: 'w', workspace_name: 'W', workspace_slug: 'w', role: 'owner', permissions: ['tournament.manage'] },
    }));
    mockedReopen.mockResolvedValue({ id: 'draft-123' } as never);
  });

  it('hides tournament mutations from viewers', () => {
    act(() => useHubStore.setState({
      session: { user_id: 'v', email: 'v@example.com', display_name: 'Viewer', workspace_id: 'w', workspace_name: 'W', workspace_slug: 'w', role: 'viewer', permissions: ['workspace.read'] },
    }));
    render(<TournamentOperationsCards />);
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByTitle('Start provider bracket')).not.toBeInTheDocument();
  });

  it('reopens the linked draft and navigates without triggering card selection', async () => {
    const user = userEvent.setup();
    render(<TournamentOperationsCards />);

    await user.click(screen.getByRole('button', { name: 'Edit' }));

    await waitFor(() => {
      expect(mockedReopen).toHaveBeenCalledWith('tournament/testfnc');
      expect(navigate).toHaveBeenCalledWith('/admin/tournaments/setup/draft-123/provider');
    });
  });
});
