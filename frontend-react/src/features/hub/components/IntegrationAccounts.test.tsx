import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { IntegrationAccounts } from './IntegrationAccounts';

vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

describe('IntegrationAccounts account-scoped provider UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAxios.get.mockImplementation(async (url) => {
      if (url === '/api/integrations') return { data: { accounts: [] } } as never;
      throw new Error(`Unexpected GET ${url}`);
    });
  });

  it('loads account records without exposing the retired shared Start.gg credential', async () => {
    render(<IntegrationAccounts />);

    await waitFor(() => expect(mockedAxios.get).toHaveBeenCalledWith('/api/integrations'));
    expect(mockedAxios.get).not.toHaveBeenCalledWith('/api/env');
    expect(screen.queryByText(/shared service credential/i)).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Paste your Challonge API key/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Account identity/i)).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/FNC test bot/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign in with Start.gg' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign in with Challonge' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Connect Discord' })).toBeInTheDocument();
  });

  it('verifies a BYOC credential instead of trusting a typed account identity', async () => {
    mockedAxios.post.mockResolvedValueOnce({ data: { account: { display_name: 'FNC Owner' } } } as never);
    render(<IntegrationAccounts />);
    await screen.findByPlaceholderText(/Paste your Challonge API key/i);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'startgg' } });
    fireEvent.change(screen.getByPlaceholderText(/Paste your Start\.gg API token/i), { target: { value: 'workspace-token' } });
    fireEvent.click(screen.getByRole('button', { name: 'Verify & connect Start.gg' }));
    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalledWith('/api/integrations/provider-credentials/connect', {
      provider_type: 'startgg', credential: 'workspace-token',
    }));
  });
});
