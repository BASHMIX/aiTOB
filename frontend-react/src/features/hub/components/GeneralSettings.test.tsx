import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { GeneralSettings } from './GeneralSettings';

vi.mock('axios');
vi.mock('./IntegrationAccounts', () => ({ IntegrationAccounts: () => null }));

const mockedAxios = vi.mocked(axios, true);

describe('GeneralSettings connection boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/env') {
        return {
          data: {
            API_BASE_URL: 'https://aitob.example',
            DISCORD_BOT_TOKEN: 'configured',
            MATCH_CALL_CHANNEL_ID: 'legacy-channel',
            CHALLONGE_API_KEY: 'configured',
          },
        } as never;
      }
      if (url === '/api/settings') return { data: { settings: {} } } as never;
      if (url === '/api/platform/email/status') return { data: {} } as never;
      return { data: {} } as never;
    });
    mockedAxios.patch.mockResolvedValue({ data: { message: 'Environment updated' } } as never);
  });

  it('does not expose workspace Discord credentials and saves only the service URL', async () => {
    const user = userEvent.setup();
    render(<GeneralSettings section="connections" embedded />);

    await waitFor(() => expect(screen.getByDisplayValue('https://aitob.example')).toBeInTheDocument());
    expect(screen.queryByText('Discord Bot Token')).not.toBeInTheDocument();
    expect(screen.queryByText('Discord Public Channel ID')).not.toBeInTheDocument();
    expect(screen.getByText(/never entered per Workspace/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Update service URL' }));
    await waitFor(() => expect(mockedAxios.patch).toHaveBeenCalledWith(
      '/api/env',
      { API_BASE_URL: 'https://aitob.example' },
    ));
  });
});
