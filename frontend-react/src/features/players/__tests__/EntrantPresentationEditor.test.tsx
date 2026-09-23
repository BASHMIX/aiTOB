import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EntrantPresentationEditor } from '../EntrantPresentationEditor';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import axios from 'axios';

vi.mock('axios');

describe('EntrantPresentationEditor', () => {
  const mockEntrant = {
    id: 'ent-101',
    name: 'ProviderGamer',
    prefix: 'PRV',
    country: 'US',
    participants: [
      {
        user: {
          images: [{ type: 'profile', url: 'https://cdn.example/provider.png' }]
        }
      }
    ]
  };

  const mockCharacters = [
    { id: 'c-1', name: 'Ryu', image_url: 'https://cdn.example/ryu.png' },
    { id: 'c-2', name: 'Ken', image_url: 'https://cdn.example/ken.png' },
  ];

  beforeEach(() => {
    (axios.patch as any).mockResolvedValue({ data: { ok: true } });
    (axios.delete as any).mockResolvedValue({ data: { ok: true } });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('displays player profile provenance when linked without override', () => {
    render(
      <EntrantPresentationEditor
        entrant={mockEntrant}
        currentSlug="tourney-sf6"
        currentEventId="ev-sf6"
        link={{
          gamer_tag: 'ProfileTag',
          display_name: 'ProfileTag',
          avatar_url: '/static/avatars/profile.png'
        }}
        characters={mockCharacters}
      />
    );

    // Provenance labels for name and avatar should be Player Profile
    const profileBadges = screen.getAllByText('Player Profile');
    expect(profileBadges.length).toBeGreaterThan(0);
  });

  it('displays tournament override provenance when override exists', () => {
    render(
      <EntrantPresentationEditor
        entrant={mockEntrant}
        currentSlug="tourney-sf6"
        currentEventId="ev-sf6"
        link={{
          gamer_tag: 'ProfileTag',
          display_name: 'ProfileTag',
        }}
        override={{
          display_name: 'Custom Event Name',
          character: 'Ryu',
          character_id: 'c-1',
          avatar_url: 'https://cdn.example/custom.png'
        }}
        characters={mockCharacters}
      />
    );

    const overrideBadges = screen.getAllByText('Tournament Override');
    expect(overrideBadges.length).toBeGreaterThan(0);
  });

  it('saves scoped override with event and character payload', async () => {
    const handleSave = vi.fn();
    const handleClose = vi.fn();

    render(
      <EntrantPresentationEditor
        entrant={mockEntrant}
        currentSlug="tourney-sf6"
        currentEventId="ev-sf6"
        characters={mockCharacters}
        gameName="SF6"
        onSave={handleSave}
        onClose={handleClose}
      />
    );

    // Change character
    const charSelect = screen.getByLabelText('Character Selection');
    fireEvent.change(charSelect, { target: { value: 'Ryu' } });

    // Submit form
    const saveBtn = screen.getByText('Save Player Profile');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(axios.patch).toHaveBeenCalledWith(
        '/api/players/overrides/ent-101',
        expect.objectContaining({
          tournament_slug: 'tourney-sf6',
          event_id: 'ev-sf6',
          character: 'Ryu',
          character_id: 'c-1',
        })
      );
      expect(handleSave).toHaveBeenCalled();
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it('resets override to profile on reset button click', async () => {
    const handleReset = vi.fn();
    const handleClose = vi.fn();

    render(
      <EntrantPresentationEditor
        entrant={mockEntrant}
        currentSlug="tourney-sf6"
        currentEventId="ev-sf6"
        override={{ display_name: 'Temporary' }}
        onReset={handleReset}
        onClose={handleClose}
      />
    );

    const resetBtn = screen.getByText('Reset to Profile');
    fireEvent.click(resetBtn);

    await waitFor(() => {
      expect(axios.delete).toHaveBeenCalledWith(
        '/api/players/overrides/ent-101',
        expect.objectContaining({
          params: {
            tournament_slug: 'tourney-sf6',
            event_id: 'ev-sf6',
          }
        })
      );
      expect(handleReset).toHaveBeenCalled();
      expect(handleClose).toHaveBeenCalled();
    });
  });
});
