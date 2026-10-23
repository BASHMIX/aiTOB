import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import axios from 'axios';

import { RolesPermissions } from './RolesPermissions';

vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

describe('RolesPermissions', () => {
  it('renders the canonical role matrix and highlights the current role', async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: {
      current_role: 'moderator',
      current_permissions: ['workspace.read', 'match.call'],
      roles: [
        { key: 'owner', label: 'Owner', permissions: ['workspace.read', 'dq.manual'] },
        { key: 'moderator', label: 'Moderator', permissions: ['workspace.read', 'match.call'] },
      ],
    } });

    render(<RolesPermissions />);

    await waitFor(() => expect(screen.getByText('Your role:')).toBeInTheDocument());
    expect(screen.getByText('Moderator', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText('Apply manual DQ')).toBeInTheDocument();
    expect(screen.getAllByLabelText('Not allowed').length).toBeGreaterThan(0);
  });

  it('renders user-facing labels for results.manage and results.broadcast', async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: {
      current_role: 'owner',
      current_permissions: ['results.manage', 'results.broadcast'],
      roles: [
        { key: 'owner', label: 'Owner', permissions: ['results.manage', 'results.broadcast'] },
        { key: 'stream_operator', label: 'Stream Operator', permissions: ['results.broadcast'] },
      ],
    } });

    render(<RolesPermissions />);

    await waitFor(() => expect(screen.getByText('Your role:')).toBeInTheDocument());
    expect(screen.getByText('Manage tournament results media')).toBeInTheDocument();
    expect(screen.getByText('Control live results overlay')).toBeInTheDocument();
  });
});
