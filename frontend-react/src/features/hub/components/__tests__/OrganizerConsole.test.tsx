import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { OrganizerConsole } from '../OrganizerConsole';
import { useHubStore } from '@/store/useHubStore';

vi.mock('axios');
vi.mock('@/store/useHubStore');
vi.mock('@/hooks/useHubSocket', () => ({ useHubSocket: () => undefined }));

const empty = (slug: string, marker = '') => ({
  tournament: { slug, name: slug, provider_type: 'startgg' }, refreshed_at: '2026-09-07T12:00:00Z',
  attention: { conflicts: [], failed_commands: [], awaiting_verification: [], provider_outage: { active: Boolean(marker), message: marker } },
  dispatch: { state: 'paused_global', slots_available: 1, capacity: 1, active_slots: 0, decisions: marker ? [{ id: marker, decision: 'skip', set_id: marker, reason_code: marker, explanation: marker }] : [] },
  approvals: [], timeline: [],
});

describe('OrganizerConsole', () => {
  let store: any;
  beforeEach(() => {
    store = { currentSlug: 'one', tournaments: [{ slug: 'one', name: 'One', provider_type: 'startgg' }, { slug: 'two', name: 'Two', provider_type: 'challonge' }], matches: [] };
    (useHubStore as any).mockImplementation(() => store);
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('ignores a late response from the previously selected tournament', async () => {
    let first!: (value: any) => void;
    let second!: (value: any) => void;
    (axios.get as any).mockImplementation((url: string) => new Promise((resolve) => {
      if (url.endsWith('/one')) first = resolve;
      if (url.endsWith('/two')) second = resolve;
    }));
    const view = render(<OrganizerConsole />);
    fireEvent.click(screen.getByText('AI Organizer Console'));
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/organizer-console/one'));
    store = { ...store, currentSlug: 'two' };
    view.rerender(<OrganizerConsole />);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/organizer-console/two'));
    second({ data: empty('two', 'two-only') });
    await screen.findByText(/two-only/);
    first({ data: empty('one', 'one-only') });
    await waitFor(() => expect(screen.queryByText(/one-only/)).not.toBeInTheDocument());
  });

  it('distinguishes an empty projection from a local load failure', async () => {
    (axios.get as any).mockResolvedValueOnce({ data: empty('one') });
    render(<OrganizerConsole />);
    fireEvent.click(screen.getByText('AI Organizer Console'));
    expect(await screen.findByText('No attention items for this tournament.')).toBeInTheDocument();
  });

  it('shows a load failure instead of presenting it as an empty tournament', async () => {
    (axios.get as any).mockRejectedValueOnce({ response: { data: { message: 'Database unavailable' } } });
    render(<OrganizerConsole />);
    fireEvent.click(screen.getByText('AI Organizer Console'));
    expect(await screen.findByText(/Could not load local console data: Could not load local console data\./)).toBeInTheDocument();
  });
});
