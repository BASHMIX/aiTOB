import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { IntegrationAccounts } from './IntegrationAccounts';

vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

describe('IntegrationAccounts account-scoped provider UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAxios.get.mockResolvedValue({ data: { accounts: [] } } as never);
  });

  it('loads account records without exposing the retired shared Start.gg credential', async () => {
    render(<IntegrationAccounts />);

    await waitFor(() => expect(mockedAxios.get).toHaveBeenCalledWith('/api/integrations'));
    expect(mockedAxios.get).not.toHaveBeenCalledWith('/api/env');
    expect(screen.queryByText(/shared service credential/i)).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Paste Start\.gg API token/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign in with Start.gg' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign in with Challonge' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Connect Discord' })).toBeInTheDocument();
  });
});
