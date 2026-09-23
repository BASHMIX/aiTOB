import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import axios from 'axios';
import { PlayerArchivePage } from '../PlayerArchivePage';

vi.mock('axios');

const mockProfiles = [
  {
    id: 'p-1',
    workspace_id: 'ws-1',
    display_name: 'Daigo Umehara',
    prefix: 'BST',
    country: 'JP',
    avatar_url: 'https://cdn.example/daigo.png',
    discord_id: 'daigo#0001',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'p-2',
    workspace_id: 'ws-1',
    display_name: 'Tokido',
    prefix: 'ROHTO',
    country: 'JP',
    avatar_url: null,
    discord_id: 'tokido#0002',
    is_active: true,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
];

const mockDetailP1 = {
  ...mockProfiles[0],
  notes: 'Living legend of fighting games',
  game_profiles: [
    {
      id: 'gp-1',
      player_profile_id: 'p-1',
      game_id: 'SF6',
      in_game_name: 'TheBeastSF6',
      in_game_id: 'CFN-DAIGO',
      character_defaults: [
        {
          id: 'cd-1',
          player_game_profile_id: 'gp-1',
          character_id: 'ken',
          character_name: 'Ken Masters',
          character_image_url: 'https://cdn.example/ken.png',
          is_primary: true,
        },
      ],
    },
  ],
  provider_identities: [
    {
      id: 'pid-1',
      player_profile_id: 'p-1',
      provider: 'startgg',
      provider_user_id: '12345',
      provider_gamer_tag: 'DaigoU',
      verified: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
};

const mockDetailP2 = {
  ...mockProfiles[1],
  game_profiles: [],
  provider_identities: [],
};

describe('PlayerArchivePage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (axios.get as any).mockImplementation((url: string, config?: any) => {
      if (url === '/api/player-profiles') {
        const query = config?.params?.query;
        if (query) {
          const filtered = mockProfiles.filter((p) =>
            p.display_name.toLowerCase().includes(query.toLowerCase())
          );
          return Promise.resolve({ data: { profiles: filtered } });
        }
        return Promise.resolve({ data: { profiles: mockProfiles } });
      }
      if (url === '/api/player-profiles/p-1') {
        return Promise.resolve({ data: mockDetailP1 });
      }
      if (url === '/api/player-profiles/p-2') {
        return Promise.resolve({ data: mockDetailP2 });
      }
      return Promise.resolve({ data: {} });
    });

    (axios.post as any).mockImplementation((url: string, payload: any) => {
      if (url === '/api/player-profiles') {
        const newProf = {
          id: 'p-new',
          workspace_id: 'ws-1',
          ...payload,
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        return Promise.resolve({ data: newProf });
      }
      return Promise.resolve({ data: { id: 'new-id', ...payload } });
    });

    (axios.patch as any).mockResolvedValue({ data: { ok: true } });
    (axios.delete as any).mockResolvedValue({ data: { ok: true, message: 'deleted' } });
  });

  it('renders archive header, profile list, and auto-selects first profile detail', async () => {
    render(<PlayerArchivePage />);

    // Header
    expect(screen.getByText('Player Archive')).toBeInTheDocument();
    expect(screen.getByTestId('create-profile-button')).toBeInTheDocument();

    // Profiles rendered in list
    await waitFor(() => {
      expect(screen.getByText('Daigo Umehara')).toBeInTheDocument();
      expect(screen.getByText('Tokido')).toBeInTheDocument();
    });
    expect(screen.getAllByAltText('JP flag')[0]).toHaveAttribute('src', '/static/flags/jp.svg');

    // First profile detail loaded
    await waitFor(() => {
      expect(screen.getByText('Living legend of fighting games')).toBeInTheDocument();
      expect(screen.getByText('TheBeastSF6')).toBeInTheDocument();
      expect(screen.getByText('Ken Masters')).toBeInTheDocument();
      expect(screen.getByText('MAIN')).toBeInTheDocument();
      expect(screen.getByText('DaigoU')).toBeInTheDocument();
    });
  });

  it('switches detail view when clicking another profile in list', async () => {
    const user = userEvent.setup();
    render(<PlayerArchivePage />);

    await waitFor(() => {
      expect(screen.getByTestId('profile-item-p-2')).toBeInTheDocument();
    });

    // Click Tokido
    await user.click(screen.getByTestId('profile-item-p-2'));

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith('/api/player-profiles/p-2');
    });
  });

  it('filters profiles when searching', async () => {
    const user = userEvent.setup();
    render(<PlayerArchivePage />);

    await waitFor(() => {
      expect(screen.getByTestId('search-profiles-input')).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId('search-profiles-input');
    await user.type(searchInput, 'Tokido{enter}');

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith('/api/player-profiles', {
        params: { limit: 100, offset: 0, query: 'Tokido' },
      });
    });
  });

  it('opens create modal, submits new profile, and reloads list', async () => {
    const user = userEvent.setup();
    render(<PlayerArchivePage />);

    await waitFor(() => {
      expect(screen.getByTestId('create-profile-button')).toBeInTheDocument();
    });

    // Open create modal
    await user.click(screen.getByTestId('create-profile-button'));
    expect(screen.getByTestId('create-profile-modal')).toBeInTheDocument();

    // Fill form
    const nameInput = screen.getByTestId('create-profile-name-input');
    await user.type(nameInput, 'Justin Wong');

    // Submit
    const submitBtn = screen.getByTestId('create-profile-submit');
    await user.click(submitBtn);

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith('/api/player-profiles', expect.objectContaining({
        display_name: 'Justin Wong',
      }));
    });
  });

  it('allows editing a player profile', async () => {
    const user = userEvent.setup();
    render(<PlayerArchivePage />);

    await waitFor(() => {
      expect(screen.getByTestId('edit-profile-button')).toBeInTheDocument();
    });

    // Click Edit
    await user.click(screen.getByTestId('edit-profile-button'));
    expect(screen.getByText('Edit Profile Information')).toBeInTheDocument();

    // Submit Edit
    const saveBtn = screen.getByRole('button', { name: /Save Changes/i });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(axios.patch).toHaveBeenCalledWith(
        '/api/player-profiles/p-1',
        expect.objectContaining({ display_name: 'Daigo Umehara' })
      );
    });
  });
});
