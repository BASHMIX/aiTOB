import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ProviderStep } from '../components/ProviderStep';


describe('ProviderStep OAuth rollout', () => {
  it('uses encrypted-token guidance when provider OAuth is unavailable', () => {
    render(<ProviderStep
      value={{ provider_type: 'startgg' }}
      accounts={[]}
      oauthAvailability={{ startgg: false, challonge: false }}
      onChange={vi.fn()}
    />);

    expect(screen.queryByRole('button', { name: /Sign in with Start\.gg/i })).not.toBeInTheDocument();
    expect(screen.getByText(/encrypted access token/i)).toBeInTheDocument();
  });
});
