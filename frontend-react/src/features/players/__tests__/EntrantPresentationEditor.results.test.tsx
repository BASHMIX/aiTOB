import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EntrantPresentationEditor } from '../EntrantPresentationEditor';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import axios from 'axios';

vi.mock('axios');

describe('EntrantPresentationEditor - Results Media Presentation Safe Correction (US4)', () => {
  const mockEntrant = {
    id: 'ent-200',
    name: 'ProGamer',
    prefix: 'TEAM',
    country: 'JP',
    participants: [
      {
        user: {
          images: [{ type: 'profile', url: 'https://cdn.example/p.png' }]
        }
      }
    ]
  };

  const mockCharacters = [
    { id: 'c-jin', name: 'Jin Kazama', image_url: 'https://cdn.example/jin.png' },
    { id: 'c-kaz', name: 'Kazuya Mishima', image_url: 'https://cdn.example/kaz.png' },
  ];

  beforeEach(() => {
    (axios.patch as any).mockResolvedValue({ data: { ok: true } });
    (axios.post as any).mockResolvedValue({ data: { ok: true } });
    (axios.delete as any).mockResolvedValue({ data: { ok: true } });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('allows event-only override by default without profile promotion', async () => {
    const handleSave = vi.fn();

    render(
      <EntrantPresentationEditor
        entrant={mockEntrant}
        currentSlug="tekken-cup"
        currentEventId="ev-tekken"
        link={{ id: 'prof-1', display_name: 'ProGamer', default_character_id: 'c-jin', default_character_name: 'Jin Kazama' }}
        characters={mockCharacters}
        gameName="Tekken 8"
        canManageResults={true}
        onSave={handleSave}
      />
    );

    // Event-only option should be present and selected by default
    const eventOnlyOption = screen.getByLabelText(/event-only/i);
    expect(eventOnlyOption).toBeInTheDocument();
    expect((eventOnlyOption as HTMLInputElement).checked).toBe(true);

    // Change character to Kazuya
    const charSelect = screen.getByLabelText('Character Selection');
    fireEvent.change(charSelect, { target: { value: 'Kazuya Mishima' } });

    // Submit form
    const saveButton = screen.getByRole('button', { name: /save/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(axios.patch).toHaveBeenCalledWith(
        '/api/players/overrides/ent-200',
        expect.objectContaining({
          character_id: 'c-kaz',
          character_name: 'Kazuya Mishima',
          promote_to_profile: false,
        })
      );
    });
    // Promote endpoint should NOT have been called
    expect(axios.post).not.toHaveBeenCalledWith(
      '/api/player-profiles/promote-override',
      expect.anything()
    );
  });

  it('hides or disables profile promotion option when canManageResults is false', () => {
    render(
      <EntrantPresentationEditor
        entrant={mockEntrant}
        currentSlug="tekken-cup"
        currentEventId="ev-tekken"
        link={{ id: 'prof-1', display_name: 'ProGamer' }}
        characters={mockCharacters}
        gameName="Tekken 8"
        canManageResults={false}
      />
    );

    // Update profile promotion option should either not exist or be disabled
    const promoteOption = screen.queryByLabelText(/update player profile/i);
    if (promoteOption) {
      expect((promoteOption as HTMLInputElement).disabled).toBe(true);
    } else {
      expect(promoteOption).toBeNull();
    }
  });

  it('supports explicit promotion to player profile and shows refresh prompt', async () => {
    const handleSave = vi.fn();

    render(
      <EntrantPresentationEditor
        entrant={mockEntrant}
        currentSlug="tekken-cup"
        currentEventId="ev-tekken"
        link={{ id: 'prof-1', display_name: 'ProGamer', default_character_id: 'c-jin', default_character_name: 'Jin Kazama' }}
        characters={mockCharacters}
        gameName="Tekken 8"
        canManageResults={true}
        onSave={handleSave}
      />
    );

    // Select "Update Player Profile"
    const promoteOption = screen.getByLabelText(/update player profile/i);
    fireEvent.click(promoteOption);
    expect((promoteOption as HTMLInputElement).checked).toBe(true);

    // Confirmation warning / info note should be visible
    expect(screen.getByText(/will update the reusable player profile/i)).toBeInTheDocument();

    // Select Kazuya
    const charSelect = screen.getByLabelText('Character Selection');
    fireEvent.change(charSelect, { target: { value: 'Kazuya Mishima' } });

    // Submit
    const saveButton = screen.getByRole('button', { name: /save/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        '/api/player-profiles/promote-override',
        {
          tournament_slug: 'tekken-cup',
          event_id: 'ev-tekken',
          entrant_id: 'ent-200',
          provider: 'startgg',
        }
      );
    });

    // Version refresh prompt notification should be displayed
    await waitFor(() => {
      expect(screen.getByText(/refresh or create a new result version/i)).toBeInTheDocument();
    });
  });
});
