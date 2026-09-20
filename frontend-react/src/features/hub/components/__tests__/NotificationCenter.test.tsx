import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { NotificationCenter } from '../NotificationCenter';
import { useHubStore } from '@/store/useHubStore';

vi.mock('axios');
vi.mock('@/store/useHubStore');

describe('NotificationCenter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useHubStore as any).mockImplementation(() => ({
      currentSlug: 'one',
      status: { token_scope: null },
    }));
    (axios.get as any).mockImplementation((url: string) => {
      if (url === '/api/conflicts') return Promise.resolve({ data: { conflicts: [{ id: 7, set_id: '42', p1_name: 'Alpha', p2_name: 'Beta' }] } });
      return Promise.resolve({ data: { attention: { provider_outage: { active: false }, failed_commands: [], awaiting_verification: [] } } });
    });
  });

  it('opens the console target for the selected notification', async () => {
    const user = userEvent.setup();
    const onOpenNotification = vi.fn();
    render(<NotificationCenter onOpenNotification={onOpenNotification} />);

    await user.click(screen.getByRole('button', { name: /notifications/i }));
    expect(await screen.findByText('Match #42 conflict')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /match #42 conflict/i }));

    await waitFor(() => expect(onOpenNotification).toHaveBeenCalledWith({ tab: 'conflicts', conflictId: 7 }));
  });
});
