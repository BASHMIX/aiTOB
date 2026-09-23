import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DiscordStep } from '../components/DiscordStep';
import { parseDiscordOAuthReturn } from '../store';

vi.mock('axios');

const mockedAxios = vi.mocked(axios, true);

describe('DiscordStep managed installation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url.endsWith('/discord/recheck')) {
        return {
          data: {
            channels: [
              { id: 'ready-channel', name: 'matches', ready: true },
              { id: 'blocked-channel', name: 'private', ready: false },
            ],
          },
        } as never;
      }
      if (url.endsWith('/discord/destinations')) return { data: { configured: true } } as never;
      if (url.endsWith('/discord/test-message')) return { data: { ok: true } } as never;
      return { data: {} } as never;
    });
  });

  it('restores a safe OAuth result without exposing authorization data', () => {
    expect(parseDiscordOAuthReturn('?discord=authorized&account_id=account-1&code=must-not-be-read')).toEqual({
      outcome: 'authorized',
      accountId: 'account-1',
      notice: 'Discord server connected. Recheck permissions and choose the tournament channel.',
    });
    expect(parseDiscordOAuthReturn('?discord=cancelled').notice).toContain('cancelled');
  });

  it('discovers named channels, blocks missing permissions, saves a verified destination, and sends a test', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const value = { enabled: true };
    const { rerender } = render(
      <DiscordStep
        draftId="draft-1"
        providerType="startgg"
        accounts={[{
          id: 'account-1', provider_type: 'discord', display_name: 'Arena',
          external_account_id: 'guild-1', status: 'active', configured: true,
        }]}
        value={value}
        onChange={onChange}
        connectionNotice="Discord server connected. Recheck permissions and choose the tournament channel."
      />,
    );

    expect(screen.getByText(/Discord server connected/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Connected server'), 'account-1');
    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledWith('/api/integrations/account-1/discord/recheck'));

    const connectedValue = {
      enabled: true,
      discord_account_id: 'account-1',
      guild_id: 'guild-1',
      guild_name: 'Arena',
    };
    rerender(
      <DiscordStep draftId="draft-1" providerType="startgg" accounts={[{
        id: 'account-1', provider_type: 'discord', display_name: 'Arena',
        external_account_id: 'guild-1', status: 'active', configured: true,
      }]} value={connectedValue} onChange={onChange} />,
    );
    expect(screen.getByRole('option', { name: '#private — missing permissions' })).toBeDisabled();
    await user.selectOptions(screen.getAllByRole('combobox')[1], 'ready-channel');
    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledWith(
      '/api/integrations/account-1/discord/destinations',
      { channel_id: 'ready-channel', destination_type: 'match_call_channel' },
    ));

    rerender(
      <DiscordStep draftId="draft-1" providerType="startgg" accounts={[{
        id: 'account-1', provider_type: 'discord', display_name: 'Arena',
        external_account_id: 'guild-1', status: 'active', configured: true,
      }]} value={{ ...connectedValue, destination_external_id: 'ready-channel' }} onChange={onChange} />,
    );
    await user.click(screen.getByRole('button', { name: 'Send test message' }));
    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledWith(
      '/api/integrations/account-1/discord/test-message',
      { channel_id: 'ready-channel' },
    ));
  });
});
