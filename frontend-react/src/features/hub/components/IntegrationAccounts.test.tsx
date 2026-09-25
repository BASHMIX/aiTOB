import { render, screen, waitFor } from '@testing-library/react';
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
      if (url === '/api/auth/providers/capabilities') return { data: { oauth: { startgg: false, challonge: false } } } as never;
      throw new Error(`Unexpected GET ${url}`);
    });
  });

  it('loads account records without exposing the retired shared Start.gg credential', async () => {
    render(<IntegrationAccounts />);

    await waitFor(() => expect(mockedAxios.get).toHaveBeenCalledWith('/api/integrations'));
    expect(mockedAxios.get).not.toHaveBeenCalledWith('/api/env');
    expect(screen.queryByText(/shared service credential/i)).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Paste Start\.gg API token/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign in with Start.gg' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign in with Challonge' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Connect Discord' })).toBeInTheDocument();
  });

  it('shows only provider OAuth actions advertised by the backend', async () => {
    mockedAxios.get.mockImplementation(async (url) => {
      if (url === '/api/integrations') return { data: { accounts: [] } } as never;
      return { data: { oauth: { startgg: true, challonge: false } } } as never;
    });

    render(<IntegrationAccounts />);

    expect(await screen.findByRole('button', { name: 'Sign in with Start.gg' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign in with Challonge' })).not.toBeInTheDocument();
  });
});
