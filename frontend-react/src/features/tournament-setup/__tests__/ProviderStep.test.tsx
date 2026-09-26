import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ProviderStep } from '../components/ProviderStep';


describe('ProviderStep BYOC connections', () => {
  it('routes provider credentials through the unified Connections workspace', () => {
    render(<ProviderStep
      value={{ provider_type: 'startgg' }}
      accounts={[]}
      oauthAvailability={{ startgg: false, challonge: false }}
      onChange={vi.fn()}
    />);

    expect(screen.queryByRole('button', { name: /Sign in with Start\.gg/i })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Manage BYOC credentials/i })).toHaveAttribute('href', '/admin/hub?settings=connections');
    expect(screen.getByText(/your own Start\.gg API token/i)).toBeInTheDocument();
  });
});
