import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { LoginPage } from './LoginPage';

vi.mock('axios', () => ({ default: { post: vi.fn() } }));
vi.mock('@/store/useHubStore', () => ({ useHubStore: (selector: (state: unknown) => unknown) => selector({ setSession: vi.fn() }) }));

describe('workspace login', () => {
  it('sends the optional authenticator/recovery code through the existing session login', async () => {
    vi.mocked(axios.post).mockResolvedValue({ data: { role: 'owner' } });
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'owner@example.test' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'temporary-test-password' } });
    fireEvent.change(screen.getByLabelText('Authenticator or recovery code'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'Unlock Hub' }));
    await waitFor(() => expect(axios.post).toHaveBeenCalledWith('/api/session/login', {
      email: 'owner@example.test', password: 'temporary-test-password', totp_code: '123456',
    }));
  });
});
