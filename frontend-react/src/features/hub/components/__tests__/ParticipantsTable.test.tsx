import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ParticipantsTable } from '../ParticipantsTable';
import { useHubStore } from '@/store/useHubStore';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import axios from 'axios';

vi.mock('@/store/useHubStore');
vi.mock('axios');

describe('ParticipantsTable', () => {
  const mockTournamentRawData = JSON.stringify({
    events: [
      {
        id: 'ev-1',
        name: 'Street Fighter 6',
        entrants: {
          nodes: [
            {
              id: 'entrant-1',
              name: 'LinkedPlayer',
              participants: [
                {
                  user: {
                    images: [
                      { type: 'profile', url: 'https://cdn.example/provider_p1.png' }
                    ]
                  }
                }
              ]
            },
            {
              id: 'entrant-2',
              name: 'UnlinkedPlayer',
              participants: [
                {
                  user: {
                    images: [
                      { type: 'profile', url: 'https://cdn.example/provider_p2.png' }
                    ]
                  }
                }
              ]
            },
            {
              id: 'entrant-3',
              name: 'OverriddenPlayer',
              participants: [
                {
                  user: {
                    images: [
                      { type: 'profile', url: 'https://cdn.example/provider_p3.png' }
                    ]
                  }
                }
              ]
            }
          ]
        }
      }
    ]
  });

  const mockCharacters = [
    { id: 'c-1', name: 'Ryu', image_url: 'https://cdn.example/ryu.png' },
    { id: 'c-2', name: 'Ken', image_url: 'https://cdn.example/ken.png' },
  ];

  beforeEach(() => {
    (useHubStore as any).mockReturnValue({
      tournaments: [
        {
          slug: 'test-slug',
          name: 'Test Tournament',
          raw_data: mockTournamentRawData,
          event_id: 'ev-1'
        }
      ],
      currentSlug: 'test-slug',
      currentEventId: 'ev-1',
      events: [{ id: 'ev-1', name: 'Street Fighter 6' }],
    });

    (axios.get as any).mockImplementation((url: string) => {
      if (url === '/api/players/overrides') {
        return Promise.resolve({
          data: {
            'entrant-2': {
              character: 'Ryu',
              character_id: 'c-1',
              character_image_url: 'https://cdn.example/ryu.png',
            },
            'entrant-3': {
              avatar_url: 'https://cdn.example/override_p3.png',
              display_name: 'Overridden Name',
            }
          }
        });
      }
      if (url === '/api/players') {
        return Promise.resolve({
          data: {
            players: [
              { discord_id: 'disc-1', gamer_tag: 'SavedProfile1', avatar_path: '/static/avatars/saved_p1.png' }
            ]
          }
        });
      }
      if (url === '/api/players/links') {
        return Promise.resolve({
          data: {
            links: {
              'entrant-1': {
                discord_id: 'disc-1',
                gamer_tag: 'SavedProfile1',
                display_name: 'SavedProfile1',
                avatar_url: '/static/avatars/saved_p1.png',
              },
              'entrant-3': {
                discord_id: 'disc-3',
                gamer_tag: 'SavedProfile3',
                avatar_url: '/static/avatars/saved_p3.png',
              }
            }
          }
        });
      }
      if (url === '/api/player-profiles') {
        return Promise.resolve({
          data: {
            profiles: [
              { id: 'profile-1', display_name: 'SavedProfile1', prefix: 'FNC', country: 'JO' },
            ],
          },
        });
      }
      return Promise.resolve({ data: {} });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders linked profile avatar instead of provider avatar for linked entrant', async () => {
    render(<ParticipantsTable characters={mockCharacters} gameName="SF6" />);

    await waitFor(() => {
      expect(screen.getAllByText(/Linked to:/)[0]).toBeInTheDocument();
    });

    const images = screen.getAllByRole('img');
    // entrant-1 should have linked avatar (/static/avatars/saved_p1.png)
    const p1Img = images.find(img => img.getAttribute('src') === '/static/avatars/saved_p1.png');
    expect(p1Img).toBeDefined();
  });

  it('renders provider fallback avatar for unlinked entrant', async () => {
    render(<ParticipantsTable characters={mockCharacters} gameName="SF6" />);

    await waitFor(() => {
      expect(screen.getAllByText('UnlinkedPlayer').length).toBeGreaterThan(0);
    });

    const images = screen.getAllByRole('img');
    const p2Img = images.find(img => img.getAttribute('src') === 'https://cdn.example/provider_p2.png');
    expect(p2Img).toBeDefined();
  });

  it('links an entrant directly to a persistent player profile', async () => {
    const user = userEvent.setup();
    (axios.put as any).mockResolvedValue({
      data: { link: { player_profile_id: 'profile-1', display_name: 'SavedProfile1' } },
    });
    render(<ParticipantsTable characters={mockCharacters} gameName="SF6" />);

    const selector = await screen.findByLabelText('Link UnlinkedPlayer to a player profile');
    await user.selectOptions(selector, 'profile-1');

    await waitFor(() => {
      expect(axios.put).toHaveBeenCalledWith('/api/players/links', {
        tournament_slug: 'test-slug',
        entrant_id: 'entrant-2',
        player_profile_id: 'profile-1',
      });
    });
  });

  it('renders override avatar over linked profile avatar when override is set', async () => {
    render(<ParticipantsTable characters={mockCharacters} gameName="SF6" />);

    await waitFor(() => {
      expect(screen.getAllByText('Overridden Name').length).toBeGreaterThan(0);
    });

    const images = screen.getAllByRole('img');
    // entrant-3 has an override avatar which takes precedence over its linked avatar
    const p3Img = images.find(img => img.getAttribute('src') === 'https://cdn.example/override_p3.png');
    expect(p3Img).toBeDefined();
  });

  it('persists and displays saved character selection and image', async () => {
    render(<ParticipantsTable characters={mockCharacters} gameName="SF6" />);

    await waitFor(() => {
      expect(screen.getAllByText('UnlinkedPlayer').length).toBeGreaterThan(0);
    });

    const select = screen.getByLabelText('Choose SF6 character for UnlinkedPlayer') as HTMLSelectElement;
    expect(select.value).toBe('Ryu');

    const images = screen.getAllByRole('img');
    const charImg = images.find(img => img.getAttribute('src') === 'https://cdn.example/ryu.png');
    expect(charImg).toBeDefined();
  });
});
