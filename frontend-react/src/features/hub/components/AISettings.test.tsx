import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AISettings } from './AISettings';

vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

const config = {
  provider_type: 'gemini', model: 'gemini-test', mode: 'disabled',
  request_limit: 10, token_limit: 1000, context_char_limit: 2000,
  response_char_limit: 500, request_timeout_seconds: 20,
  policy_version: 'v1', key_configured: false, last_test_status: 'never',
  connections: {
    gemini: { configured: false, enabled: true },
    openai: { configured: false, enabled: true },
  },
};

describe('AISettings connection boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAxios.get.mockResolvedValue({ data: config } as never);
    mockedAxios.put.mockResolvedValue({ data: { configured: true } } as never);
  });

  it('keeps credential entry in Connections and stores it for the selected Workspace provider', async () => {
    render(<AISettings connectionOnly />);

    const input = await screen.findByPlaceholderText(/Enter a replacement key/i);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'openai' } });
    fireEvent.change(input, { target: { value: 'workspace-openai-key' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save encrypted credential' }));

    await waitFor(() => expect(mockedAxios.put).toHaveBeenCalledWith(
      '/api/ai/connections/openai/credential',
      { api_key: 'workspace-openai-key' },
    ));
  });

  it('does not expose credential entry in the AI policy screen', async () => {
    render(<AISettings />);

    await screen.findByRole('button', { name: 'Save AI & Automation' });
    expect(screen.queryByPlaceholderText(/Enter a replacement key/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Credentials are managed only in Connections/i)).toBeInTheDocument();
  });
});
